"""
Active learning + inverse design for methane (CH4) using Quantum ESPRESSO via ASE.

Objective:
    Minimize total energy by varying the C-H bond length r while preserving
    tetrahedral geometry.

System:
    One gas-phase CH4 molecule in a 10 A cubic box.

Run:
    cd <ACTISTRUCT_ROOT>
    source .venv/bin/activate
    python examples/manual_qe/ch4_qe_active_inverse.py
"""

from __future__ import annotations

from dataclasses import dataclass
from multiprocessing import Pool
from pathlib import Path
import os
import pickle
import re
import shutil
import time
import traceback
import warnings

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from ase import Atoms
from ase.calculators.espresso import Espresso
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, RBF, WhiteKernel
from scipy.optimize import differential_evolution

try:
    from ase.calculators.espresso import EspressoProfile
except ImportError:  # Older ASE fallback.
    EspressoProfile = None

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=RuntimeWarning)


ROOT = Path(__file__).resolve().parents[2]
PLOT_DIR = ROOT / "outputs" / "plots"
REPORT_DIR = ROOT / "outputs" / "reports"
QE_RUN_DIR = ROOT / "outputs" / "qe_runs_ch4"
PLOT_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)
QE_RUN_DIR.mkdir(parents=True, exist_ok=True)

CACHE_DIR = ROOT / "outputs" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_FILE = CACHE_DIR / "ch4_qe_energy_cache_sssp_efficiency.pkl"
CACHE_LOCK = ROOT / "ch4_qe_energy_cache_sssp_efficiency.lock"
REPORT_FILE = REPORT_DIR / "ch4_qe_active_inverse_report.txt"

PSEUDO_DIR_ABS = os.environ.get("ESPRESSO_PSEUDO", "")
PSEUDOPOTENTIALS = {
    # The markdown names C.pbe-n-rrkjus_psl.1.0.0.UPF, but this SSSP
    # efficiency folder contains the standard C PAW/USPP file below.
    "C": "C.pbe-n-rrkjus_psl.1.0.0.UPF",
    "H": "H.pbe-rrkjus_psl.1.0.0.UPF",
}
ECUTWFC_RY = 50.0
ECUTRHO_RY = 400.0
KPTS = (1, 1, 1)
N_PROCS = 2
PARALLEL_WORKERS = 2
PW_X_CANDIDATES = [
    os.environ.get("ESPRESSO_PW"),
    shutil.which("pw.x"),
]
PW_X = next((str(Path(path)) for path in PW_X_CANDIDATES if path and Path(path).exists()), "pw.x")
QE_COMMAND = os.environ.get("ESPRESSO_COMMAND", f"mpirun -np {N_PROCS} {PW_X}")
RY_TO_EV = 13.605693122994


@dataclass
class Config:
    r_min: float = 1.05
    r_max: float = 1.15
    n_candidates: int = 41
    initial_bonds: tuple[float, ...] = (1.055, 1.090, 1.145)
    max_iterations: int = 10
    uncertainty_threshold: float = 0.03  # eV
    active_labels_per_iter: int = 2
    kappa: float = 1.0
    convergence_uncertainty: float = 0.03  # eV
    convergence_predicted_improvement: float = 0.001  # eV
    duplicate_tol: float = 1e-6
    cache_round_digits: int = 6
    random_state: int = 101
    box_size: float = 10.0
    retries: int = 2
    retry_wait_seconds: int = 5


CONFIG = Config()


def build_ch4(r: float, box: float = CONFIG.box_size) -> Atoms:
    """Build CH4 molecule with C-H bond length r in a cubic box."""
    r = float(r)
    box = float(box)
    center = np.array([box / 2.0, box / 2.0, box / 2.0], dtype=float)
    directions = np.asarray(
        [
            [1.0, 1.0, 1.0],
            [1.0, -1.0, -1.0],
            [-1.0, 1.0, -1.0],
            [-1.0, -1.0, 1.0],
        ],
        dtype=float,
    )
    directions /= np.linalg.norm(directions[0])
    h_positions = center + directions * r
    atoms = Atoms("CH4", positions=[center] + [tuple(pos) for pos in h_positions], cell=[box, box, box], pbc=True)
    if len(atoms) != 5:
        raise RuntimeError(f"Expected 5 atoms, got {len(atoms)}")
    return atoms


def qe_input_data(prefix: str) -> dict:
    """Quantum ESPRESSO pw.x input for CH4 SCF."""
    return {
        "control": {
            "calculation": "scf",
            "prefix": prefix,
            "outdir": f"/tmp/qe_{prefix}_{os.getpid()}",
            "pseudo_dir": PSEUDO_DIR_ABS,
            "verbosity": "high",
            "tprnfor": True,
            "tstress": True,
        },
        "system": {
            "ecutwfc": ECUTWFC_RY,
            "ecutrho": ECUTRHO_RY,
            "occupations": "smearing",
            "smearing": "gaussian",
            "degauss": 0.01,
        },
        "electrons": {
            "conv_thr": 1e-8,
            "electron_maxstep": 200,
            "mixing_beta": 0.4,
        },
    }


def get_qe_calculator(directory: Path, prefix: str) -> Espresso:
    """Return ASE Espresso calculator configured for QE pw.x."""
    directory.mkdir(parents=True, exist_ok=True)
    kwargs = dict(
        pseudopotentials=PSEUDOPOTENTIALS,
        input_data=qe_input_data(prefix=prefix),
        kpts=KPTS,
        directory=str(directory),
    )
    if EspressoProfile is not None:
        profile = EspressoProfile(command=QE_COMMAND, pseudo_dir=PSEUDO_DIR_ABS)
        return Espresso(profile=profile, **kwargs)

    old_command = f"{QE_COMMAND} -in PREFIX.pwi > PREFIX.pwo"
    return Espresso(command=old_command, **kwargs)


def ensure_qe_environment() -> None:
    if PW_X == "pw.x" and shutil.which("pw.x") is None:
        raise RuntimeError("pw.x not found in PATH. Set ESPRESSO_COMMAND or add pw.x to PATH.")
    if not PSEUDO_DIR_ABS:
        raise RuntimeError("Set ESPRESSO_PSEUDO to the directory containing required UPF files.")
    for element, pseudo in PSEUDOPOTENTIALS.items():
        pseudo_path = Path(PSEUDO_DIR_ABS) / pseudo
        if not pseudo_path.exists():
            raise FileNotFoundError(f"Missing {element} pseudopotential: {pseudo_path}")


def make_candidate_grid() -> np.ndarray:
    return np.linspace(CONFIG.r_min, CONFIG.r_max, CONFIG.n_candidates)


def cache_key_bond(r: float) -> str:
    return (
        f"ch4:energy:r={float(r):.{CONFIG.cache_round_digits}f}:"
        f"box={CONFIG.box_size}:pseudo={PSEUDOPOTENTIALS}:"
        f"ecut={ECUTWFC_RY}-{ECUTRHO_RY}:kpts={KPTS}"
    )


def acquire_cache_lock(timeout: float = 600.0, poll: float = 0.1) -> int:
    start = time.time()
    while True:
        try:
            fd = os.open(str(CACHE_LOCK), os.O_CREAT | os.O_EXCL | os.O_RDWR)
            os.write(fd, str(os.getpid()).encode("ascii"))
            return fd
        except FileExistsError:
            if time.time() - start > timeout:
                raise TimeoutError(f"Timed out waiting for cache lock: {CACHE_LOCK}")
            time.sleep(poll)


def release_cache_lock(fd: int) -> None:
    try:
        os.close(fd)
    finally:
        try:
            CACHE_LOCK.unlink()
        except FileNotFoundError:
            pass


def load_cache_unlocked() -> dict:
    if not CACHE_FILE.exists():
        return {}
    with CACHE_FILE.open("rb") as handle:
        return pickle.load(handle)


def save_cache_unlocked(cache: dict) -> None:
    tmp_path = CACHE_FILE.with_suffix(".tmp")
    with tmp_path.open("wb") as handle:
        pickle.dump(cache, handle)
    os.replace(tmp_path, CACHE_FILE)


def get_cached_value(key: str) -> float | None:
    fd = acquire_cache_lock()
    try:
        return load_cache_unlocked().get(key)
    finally:
        release_cache_lock(fd)


def set_cached_value(key: str, value: float) -> None:
    fd = acquire_cache_lock()
    try:
        cache = load_cache_unlocked()
        cache[key] = float(value)
        save_cache_unlocked(cache)
    finally:
        release_cache_lock(fd)


def parse_qe_total_energy(output_path: Path) -> float | None:
    """Return final QE total energy in eV from espresso.pwo, if present."""
    if not output_path.exists():
        return None
    text = output_path.read_text(errors="ignore")
    matches = re.findall(r"!\s+total energy\s+=\s+([-+0-9.Ee]+)\s+Ry", text)
    if not matches:
        return None
    return float(matches[-1]) * RY_TO_EV


def compute_total_energy(r: float, retries: int = 2) -> float | None:
    """Compute/cached CH4 total energy at C-H bond length r."""
    r = float(r)
    key = cache_key_bond(r)
    cached = get_cached_value(key)
    if cached is not None:
        return float(cached)

    last_error = None
    for attempt in range(1, retries + 2):
        r_tag = f"{r:.{CONFIG.cache_round_digits}f}".replace(".", "p")
        work_dir = QE_RUN_DIR / f"ch4_r{r_tag}_pid{os.getpid()}_attempt{attempt}"
        try:
            atoms = build_ch4(r, CONFIG.box_size)
            atoms.calc = get_qe_calculator(work_dir, prefix=f"ch4_r{r_tag}")
            try:
                total_energy = float(atoms.get_potential_energy())
            except Exception:
                parsed_energy = parse_qe_total_energy(work_dir / "espresso.pwo")
                if parsed_energy is None:
                    raise
                total_energy = parsed_energy
            set_cached_value(key, total_energy)
            return total_energy
        except Exception as exc:
            last_error = exc
            print(f"WARNING: QE failed for r={r:.6f} A attempt {attempt}/{retries + 1}: {exc}")
            if attempt <= retries:
                time.sleep(CONFIG.retry_wait_seconds)

    print(f"WARNING: skip r={r:.6f} A after QE failures: {last_error}")
    return None


def evaluate_bond(r: float) -> tuple[float, float | None]:
    try:
        return float(r), compute_total_energy(float(r), retries=CONFIG.retries)
    except Exception:
        print(f"WARNING: unexpected failure at r={float(r):.6f} A")
        traceback.print_exc()
        return float(r), None


class GPModel:
    """Gaussian-process forward model: C-H bond length -> total energy."""

    def __init__(self) -> None:
        kernel = (
            ConstantKernel(1.0, (1e-3, 1e3))
            * RBF(length_scale=0.02, length_scale_bounds=(1e-3, 0.3))
            + WhiteKernel(noise_level=1e-5, noise_level_bounds=(1e-9, 1e-2))
        )
        self.gp = GaussianProcessRegressor(
            kernel=kernel,
            normalize_y=True,
            n_restarts_optimizer=8,
            random_state=CONFIG.random_state,
        )

    def train(self, bonds: list[float], energies: list[float]) -> None:
        x_train = np.asarray(bonds, dtype=float).reshape(-1, 1)
        y_train = np.asarray(energies, dtype=float)
        self.gp.fit(x_train, y_train)

    def predict(self, bonds: np.ndarray | list[float]) -> tuple[np.ndarray, np.ndarray]:
        x = np.asarray(bonds, dtype=float).reshape(-1, 1)
        mean, std = self.gp.predict(x, return_std=True)
        return mean, std


def is_new_bond(r: float, labeled_bonds: list[float]) -> bool:
    return not np.any(np.isclose(float(r), np.asarray(labeled_bonds), atol=CONFIG.duplicate_tol, rtol=0.0))


def evaluate_new_bonds(bonds: list[float], parallel: bool = True) -> list[tuple[float, float]]:
    unique_bonds: list[float] = []
    for bond in bonds:
        if is_new_bond(bond, unique_bonds):
            unique_bonds.append(float(bond))

    if not unique_bonds:
        return []
    if parallel and len(unique_bonds) > 1:
        with Pool(processes=min(PARALLEL_WORKERS, len(unique_bonds))) as pool:
            raw_results = pool.map(evaluate_bond, unique_bonds)
    else:
        raw_results = [evaluate_bond(bond) for bond in unique_bonds]

    results: list[tuple[float, float]] = []
    for bond, energy in raw_results:
        if energy is None:
            print(f"WARNING: no label added for r={bond:.6f} A")
            continue
        results.append((float(bond), float(energy)))
    return results


def add_successful_labels(pairs: list[tuple[float, float]], bonds: list[float], energies: list[float]) -> list[tuple[float, float]]:
    added: list[tuple[float, float]] = []
    for bond, energy in pairs:
        if is_new_bond(bond, bonds):
            bonds.append(float(bond))
            energies.append(float(energy))
            added.append((float(bond), float(energy)))
    return added


def build_initial_training_set() -> tuple[list[float], list[float]]:
    bonds: list[float] = []
    energies: list[float] = []
    offsets = [0.0, -0.0025, 0.0025, -0.005, 0.005]

    for base_bond in CONFIG.initial_bonds:
        added = False
        for offset in offsets:
            trial = float(np.clip(base_bond + offset, CONFIG.r_min, CONFIG.r_max))
            if not is_new_bond(trial, bonds):
                continue
            energy = compute_total_energy(trial, retries=CONFIG.retries)
            if energy is None:
                continue
            bonds.append(trial)
            energies.append(float(energy))
            print(f"Initial label: r={trial:.6f} A -> E={energy:.8f} eV")
            added = True
            break
        if not added:
            raise RuntimeError(f"Could not create initial label near r={base_bond:.6f} A")

    if len(bonds) < 3:
        raise RuntimeError("Need at least 3 successful labels for GP training.")
    return bonds, energies


def active_learning_query(model: GPModel, candidate_bonds: np.ndarray, labeled_bonds: list[float]) -> list[float]:
    _, std = model.predict(candidate_bonds)
    high_idx = np.where(std > CONFIG.uncertainty_threshold)[0]
    if len(high_idx) == 0:
        return []

    ordered = high_idx[np.argsort(std[high_idx])[::-1]]
    selected: list[float] = []
    for idx in ordered:
        bond = float(candidate_bonds[idx])
        if is_new_bond(bond, labeled_bonds + selected):
            selected.append(bond)
        if len(selected) >= CONFIG.active_labels_per_iter:
            break
    return selected


def lower_confidence_bound(mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    """Minimize this: predicted energy minus exploration bonus."""
    return mean - CONFIG.kappa * std


def propose_inverse_candidate(model: GPModel) -> tuple[float, float, float, float]:
    """Find the LCB minimum via Differential Evolution — no grid required.

    Replaces the previous grid-argmin approach. Differential Evolution
    searches the continuous parameter space directly, so the method scales
    to any number of dimensions without exponential blowup.
    """
    bounds = [(CONFIG.r_min, CONFIG.r_max)]

    def _lcb(x: np.ndarray) -> float:
        mean, std = model.predict(x.reshape(1, -1))
        return float(mean[0] - CONFIG.kappa * std[0])

    result = differential_evolution(
        _lcb,
        bounds,
        seed=CONFIG.random_state,
        maxiter=500,
        tol=1e-7,
        polish=True,
        mutation=(0.5, 1.5),
        recombination=0.9,
    )
    best_x = float(result.x[0])
    mean_at, std_at = model.predict([[best_x]])
    coarse = np.linspace(CONFIG.r_min, CONFIG.r_max, CONFIG.n_candidates)
    coarse_mean, _ = model.predict(coarse)
    predicted_improvement = float(max(0.0, float(np.min(coarse_mean)) - float(mean_at[0])))
    return best_x, float(mean_at[0]), float(std_at[0]), predicted_improvement


def best_observed(bonds: list[float], energies: list[float]) -> tuple[float, float]:
    idx = int(np.argmin(np.asarray(energies, dtype=float)))
    return float(bonds[idx]), float(energies[idx])


def predicted_best(model: GPModel, candidate_bonds: np.ndarray) -> tuple[float, float, float]:
    mean, std = model.predict(candidate_bonds)
    idx = int(np.argmin(mean))
    return float(candidate_bonds[idx]), float(mean[idx]), float(std[idx])


def gp_uncertainty_at(model: GPModel, bond: float) -> float:
    _, std = model.predict([bond])
    return float(std[0])


def plot_energy_curve(model: GPModel, candidate_bonds: np.ndarray, labeled_bonds: list[float], labeled_energies: list[float]) -> Path:
    mean, std = model.predict(candidate_bonds)
    best_r, best_e = best_observed(labeled_bonds, labeled_energies)

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(candidate_bonds, mean, color="tab:red", linestyle="--", lw=2, label="GP prediction")
    ax.fill_between(candidate_bonds, mean - std, mean + std, color="tab:red", alpha=0.22, label="GP uncertainty (+/- 1 std)")
    ax.scatter(labeled_bonds, labeled_energies, s=58, color="tab:blue", zorder=5, label="QE labels")
    ax.axvline(best_r, color="tab:green", linestyle=":", lw=2, label=f"Best observed r={best_r:.4f} A")
    ax.axvline(1.087, color="tab:gray", linestyle="-.", lw=1.5, label="Reference r~1.087 A")
    ax.axhline(best_e, color="tab:gray", linestyle=":", lw=1.2, label="Best observed energy")
    ax.set_xlabel("C-H bond length r (A)")
    ax.set_ylabel("Total energy (eV)")
    ax.set_title("CH4: QE Active Learning + Inverse Minimization")
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()

    path = PLOT_DIR / "ch4_qe_energy_curve.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def plot_convergence(history: dict[str, list[float]]) -> Path:
    fig, (ax_e, ax_n) = plt.subplots(1, 2, figsize=(12, 4.5))
    ax_e.plot(history["iteration"], history["best_energy"], marker="o", color="tab:orange")
    ax_e.set_xlabel("Iteration")
    ax_e.set_ylabel("Best observed total energy (eV)")
    ax_e.set_title("Energy minimization")
    ax_e.grid(alpha=0.25)

    ax_n.plot(history["iteration"], history["n_qe"], marker="s", color="tab:purple")
    ax_n.set_xlabel("Iteration")
    ax_n.set_ylabel("Successful QE evaluations")
    ax_n.set_title("QE evaluation count")
    ax_n.grid(alpha=0.25)

    fig.tight_layout()
    path = PLOT_DIR / "ch4_qe_convergence.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def write_report(lines: list[str]) -> Path:
    REPORT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return REPORT_FILE


def main() -> None:
    ensure_qe_environment()
    candidate_bonds = make_candidate_grid()
    test_atoms = build_ch4(1.087, CONFIG.box_size)

    report: list[str] = []
    header = [
        "=" * 84,
        "CH4 active learning + inverse minimization using QE via ASE",
        f"Atoms: {len(test_atoms)} molecule in {CONFIG.box_size:.1f} A cubic box",
        f"C-H bond range: {CONFIG.r_min:.3f} to {CONFIG.r_max:.3f} A",
        f"Initial bonds: {list(CONFIG.initial_bonds)} A",
        f"QE command base: {QE_COMMAND}",
        f"Pseudo dir: {PSEUDO_DIR_ABS}",
        f"Pseudopotentials: {PSEUDOPOTENTIALS}",
        f"ecutwfc / ecutrho: {ECUTWFC_RY:.1f} / {ECUTRHO_RY:.1f} Ry",
        f"kpts: {KPTS}",
        "=" * 84,
    ]
    print("\n".join(header))
    report.extend(header)

    labeled_bonds, labeled_energies = build_initial_training_set()
    model = GPModel()
    model.train(labeled_bonds, labeled_energies)

    history: dict[str, list[float]] = {
        "iteration": [],
        "best_bond": [],
        "best_energy": [],
        "best_uncertainty": [],
        "predicted_min_bond": [],
        "predicted_min_energy": [],
        "n_qe": [],
    }

    for iteration in range(1, CONFIG.max_iterations + 1):
        print(f"\nIteration {iteration}")
        report.append(f"\nIteration {iteration}")

        al_bonds = active_learning_query(model, candidate_bonds, labeled_bonds)
        if al_bonds:
            msg = f"  Active labels requested: {[round(r, 6) for r in al_bonds]} A"
            print(msg)
            report.append(msg)
            al_pairs = evaluate_new_bonds(al_bonds, parallel=True)
            added = add_successful_labels(al_pairs, labeled_bonds, labeled_energies)
            for bond, energy in added:
                msg = f"    Added AL label: r={bond:.6f} A -> E={energy:.8f} eV"
                print(msg)
                report.append(msg)
            if added:
                model.train(labeled_bonds, labeled_energies)
        else:
            msg = "  Active labels requested: none above uncertainty threshold"
            print(msg)
            report.append(msg)

        proposal, pred_mean, pred_std, pred_improvement = propose_inverse_candidate(model)
        msg = (
            f"  Inverse minimization proposal: r={proposal:.6f} A, "
            f"GP E={pred_mean:.8f} +/- {pred_std:.8f} eV, "
            f"predicted improvement proxy={pred_improvement:.8f} eV"
        )
        print(msg)
        report.append(msg)

        if is_new_bond(proposal, labeled_bonds):
            energy = compute_total_energy(proposal, retries=CONFIG.retries)
            if energy is not None:
                labeled_bonds.append(proposal)
                labeled_energies.append(float(energy))
                model.train(labeled_bonds, labeled_energies)
                msg = f"    Added inverse label: r={proposal:.6f} A -> E={energy:.8f} eV"
                print(msg)
                report.append(msg)
            else:
                msg = f"    Inverse proposal skipped after QE failure: r={proposal:.6f} A"
                print(msg)
                report.append(msg)
        else:
            msg = "    Inverse proposal already labeled"
            print(msg)
            report.append(msg)

        best_r, best_e = best_observed(labeled_bonds, labeled_energies)
        best_std = gp_uncertainty_at(model, best_r)
        pred_min_r, pred_min_e, pred_min_std = predicted_best(model, candidate_bonds)
        predicted_gap = max(0.0, best_e - pred_min_e)

        history["iteration"].append(iteration)
        history["best_bond"].append(best_r)
        history["best_energy"].append(best_e)
        history["best_uncertainty"].append(best_std)
        history["predicted_min_bond"].append(pred_min_r)
        history["predicted_min_energy"].append(pred_min_e)
        history["n_qe"].append(len(labeled_bonds))

        msg = (
            f"  Best observed: r={best_r:.6f} A, E={best_e:.8f} eV, "
            f"GP std={best_std:.8f} eV, predicted min r={pred_min_r:.6f} A, "
            f"predicted gap={predicted_gap:.8f} eV, QE labels={len(labeled_bonds)}"
        )
        print(msg)
        report.append(msg)

        if best_std < CONFIG.convergence_uncertainty and predicted_gap < CONFIG.convergence_predicted_improvement:
            msg = "  Converged: best observed point is low-uncertainty and no meaningful GP improvement remains"
            print(msg)
            report.append(msg)
            break

    best_r, best_e = best_observed(labeled_bonds, labeled_energies)
    best_std = gp_uncertainty_at(model, best_r)
    energy_plot = plot_energy_curve(model, candidate_bonds, labeled_bonds, labeled_energies)
    convergence_plot = plot_convergence(history)

    final_lines = [
        "",
        "=" * 84,
        "Final result",
        f"Best C-H bond length: {best_r:.6f} A",
        f"Best QE total energy: {best_e:.8f} eV",
        f"GP uncertainty at best bond length: {best_std:.8f} eV",
        f"Successful QE evaluations: {len(labeled_bonds)}",
        f"Energy plot: {energy_plot}",
        f"Convergence plot: {convergence_plot}",
        f"Cache file: {CACHE_FILE}",
    ]
    print("\n".join(final_lines))
    report.extend(final_lines)
    report_path = write_report(report)
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()
