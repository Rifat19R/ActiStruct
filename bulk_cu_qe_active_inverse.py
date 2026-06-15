"""
Active learning + inverse design for bulk FCC Cu using Quantum ESPRESSO via ASE.

Objective:
    Minimize total energy per atom by varying the conventional FCC lattice constant a.

System:
    FCC copper conventional cubic cell = 4 atoms.

Run:
    cd <ACTISTRUCT_ROOT>
    source .venv/bin/activate
    python bulk_cu_qe_active_inverse.py
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


ROOT = Path(__file__).resolve().parent
PLOT_DIR = ROOT / "outputs" / "plots"
REPORT_DIR = ROOT / "outputs" / "reports"
QE_RUN_DIR = ROOT / "outputs" / "qe_runs_bulk_cu"
PLOT_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)
QE_RUN_DIR.mkdir(parents=True, exist_ok=True)

CACHE_FILE = ROOT / "bulk_cu_4_qe_energy_cache_sssp_efficiency.pkl"
CACHE_LOCK = ROOT / "bulk_cu_4_qe_energy_cache_sssp_efficiency.lock"
REPORT_FILE = REPORT_DIR / "bulk_cu_4_qe_active_inverse_report.txt"

PSEUDO_DIR_ABS = os.environ.get("ESPRESSO_PSEUDO", "")
# SSSP 1.3.0 PBE efficiency folder on this machine contains this Cu PAW pseudo.
# It has z_valence=11, so Cu 3d electrons are included.
# The markdown names Cu.pbe-dn-rrkjus_psl.1.0.0.UPF, but that file is not present there.
PSEUDOPOTENTIALS = {"Cu": "Cu.paw.z_11.ld1.psl.v1.0.0-low.upf"}
ECUTWFC_RY = 70.0
ECUTRHO_RY = 560.0
KPTS = (12, 12, 12)
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
    lattice_min: float = 3.40
    lattice_max: float = 3.80
    n_candidates: int = 81
    initial_lattices: tuple[float, ...] = (3.45, 3.61, 3.75)
    max_iterations: int = 12
    uncertainty_threshold: float = 0.03  # eV/atom
    active_labels_per_iter: int = 2
    kappa: float = 1.0
    convergence_uncertainty: float = 0.03  # eV/atom
    convergence_predicted_improvement: float = 0.001  # eV/atom
    duplicate_tol: float = 1e-6
    cache_round_digits: int = 6
    random_state: int = 41
    retries: int = 2
    retry_wait_seconds: int = 5


CONFIG = Config()


def build_fcc_cu(a: float) -> Atoms:
    """Create conventional FCC Cu cell with 4 atoms and lattice constant a in Angstrom."""
    a = float(a)
    atoms = Atoms(
        "Cu4",
        positions=[
            [0.0, 0.0, 0.0],
            [0.0, a / 2.0, a / 2.0],
            [a / 2.0, 0.0, a / 2.0],
            [a / 2.0, a / 2.0, 0.0],
        ],
        cell=[a, a, a],
        pbc=True,
    )
    if len(atoms) != 4:
        raise RuntimeError(f"Expected 4 atoms, got {len(atoms)}")
    return atoms


def qe_input_data(prefix: str) -> dict:
    """Quantum ESPRESSO pw.x input for bulk Cu SCF."""
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
            "degauss": 0.02,
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
    pseudo_path = Path(PSEUDO_DIR_ABS) / PSEUDOPOTENTIALS["Cu"]
    if not pseudo_path.exists():
        raise FileNotFoundError(f"Missing Cu pseudopotential: {pseudo_path}")


def cache_key_lattice(a: float) -> str:
    return f"bulkcu4:energy_per_atom:a={float(a):.{CONFIG.cache_round_digits}f}:pseudo={PSEUDOPOTENTIALS['Cu']}:ecut={ECUTWFC_RY}-{ECUTRHO_RY}:kpts={KPTS}"


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


def compute_energy_per_atom(a: float, retries: int = 2) -> float | None:
    """Compute/cached bulk Cu total energy per atom at lattice constant a."""
    key = cache_key_lattice(a)
    cached = get_cached_value(key)
    if cached is not None:
        return float(cached)

    last_error = None
    for attempt in range(1, retries + 2):
        a_tag = f"{float(a):.{CONFIG.cache_round_digits}f}".replace(".", "p")
        work_dir = QE_RUN_DIR / f"bulkcu4_a{a_tag}_pid{os.getpid()}_attempt{attempt}"
        try:
            atoms = build_fcc_cu(float(a))
            atoms.calc = get_qe_calculator(work_dir, prefix=f"bulkcu4_a{a_tag}")
            try:
                total_energy = float(atoms.get_potential_energy())
            except Exception:
                parsed_energy = parse_qe_total_energy(work_dir / "espresso.pwo")
                if parsed_energy is None:
                    raise
                total_energy = parsed_energy
            energy_per_atom = total_energy / len(atoms)
            set_cached_value(key, energy_per_atom)
            return energy_per_atom
        except Exception as exc:
            last_error = exc
            print(f"WARNING: QE failed for a={float(a):.6f} A attempt {attempt}/{retries + 1}: {exc}")
            if attempt <= retries:
                time.sleep(CONFIG.retry_wait_seconds)

    print(f"WARNING: skip a={float(a):.6f} A after QE failures: {last_error}")
    return None


def evaluate_lattice(a: float) -> tuple[float, float | None]:
    try:
        return float(a), compute_energy_per_atom(float(a), retries=CONFIG.retries)
    except Exception:
        print(f"WARNING: unexpected failure at a={float(a):.6f} A")
        traceback.print_exc()
        return float(a), None


class GPModel:
    """Gaussian-process forward model: lattice constant -> energy per atom."""

    def __init__(self) -> None:
        kernel = (
            ConstantKernel(1.0, (1e-3, 1e3))
            * RBF(length_scale=0.08, length_scale_bounds=(1e-3, 1.0))
            + WhiteKernel(noise_level=1e-5, noise_level_bounds=(1e-9, 1e-2))
        )
        self.gp = GaussianProcessRegressor(
            kernel=kernel,
            normalize_y=True,
            n_restarts_optimizer=8,
            random_state=CONFIG.random_state,
        )

    def train(self, lattices: list[float], energies: list[float]) -> None:
        x_train = np.asarray(lattices, dtype=float).reshape(-1, 1)
        y_train = np.asarray(energies, dtype=float)
        self.gp.fit(x_train, y_train)

    def predict(self, lattices: np.ndarray | list[float]) -> tuple[np.ndarray, np.ndarray]:
        x = np.asarray(lattices, dtype=float).reshape(-1, 1)
        mean, std = self.gp.predict(x, return_std=True)
        return mean, std


def is_new_lattice(a: float, labeled_lattices: list[float]) -> bool:
    return not np.any(np.isclose(float(a), np.asarray(labeled_lattices), atol=CONFIG.duplicate_tol, rtol=0.0))


def evaluate_new_lattices(lattices: list[float], parallel: bool = True) -> list[tuple[float, float]]:
    unique_lattices: list[float] = []
    for lattice in lattices:
        if is_new_lattice(lattice, unique_lattices):
            unique_lattices.append(float(lattice))

    if not unique_lattices:
        return []
    if parallel and len(unique_lattices) > 1:
        with Pool(processes=min(PARALLEL_WORKERS, len(unique_lattices))) as pool:
            raw_results = pool.map(evaluate_lattice, unique_lattices)
    else:
        raw_results = [evaluate_lattice(lattice) for lattice in unique_lattices]

    results: list[tuple[float, float]] = []
    for lattice, energy in raw_results:
        if energy is None:
            print(f"WARNING: no label added for a={lattice:.6f} A")
            continue
        results.append((float(lattice), float(energy)))
    return results


def add_successful_labels(pairs: list[tuple[float, float]], lattices: list[float], energies: list[float]) -> list[tuple[float, float]]:
    added: list[tuple[float, float]] = []
    for lattice, energy in pairs:
        if is_new_lattice(lattice, lattices):
            lattices.append(float(lattice))
            energies.append(float(energy))
            added.append((float(lattice), float(energy)))
    return added


def build_initial_training_set() -> tuple[list[float], list[float]]:
    lattices: list[float] = []
    energies: list[float] = []
    offsets = [0.0, -0.02, 0.02, -0.04, 0.04]

    for base_lattice in CONFIG.initial_lattices:
        added = False
        for offset in offsets:
            trial = float(np.clip(base_lattice + offset, CONFIG.lattice_min, CONFIG.lattice_max))
            if not is_new_lattice(trial, lattices):
                continue
            energy = compute_energy_per_atom(trial, retries=CONFIG.retries)
            if energy is None:
                continue
            lattices.append(trial)
            energies.append(float(energy))
            print(f"Initial label: a={trial:.6f} A -> E/atom={energy:.8f} eV")
            added = True
            break
        if not added:
            raise RuntimeError(f"Could not create initial label near a={base_lattice:.6f} A")

    if len(lattices) < 3:
        raise RuntimeError("Need at least 3 successful labels for GP training.")
    return lattices, energies


def active_learning_query(model: GPModel, candidate_lattices: np.ndarray, labeled_lattices: list[float]) -> list[float]:
    _, std = model.predict(candidate_lattices)
    high_idx = np.where(std > CONFIG.uncertainty_threshold)[0]
    if len(high_idx) == 0:
        return []

    ordered = high_idx[np.argsort(std[high_idx])[::-1]]
    selected: list[float] = []
    for idx in ordered:
        lattice = float(candidate_lattices[idx])
        if is_new_lattice(lattice, labeled_lattices + selected):
            selected.append(lattice)
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
    bounds = [(CONFIG.lattice_min, CONFIG.lattice_max)]

    def _lcb(x: np.ndarray) -> float:
        mean, std = model.predict(x.reshape(1, -1))
        return float(mean[0] - CONFIG.kappa * std[0])

    result = differential_evolution(
        _lcb,
        bounds,
        seed=CONFIG.random_state,
        maxiter=500,
        tol=1e-7,
        polish=True,       # L-BFGS-B local refinement after DE
        mutation=(0.5, 1.5),
        recombination=0.9,
    )
    best_x = float(result.x[0])
    mean_at, std_at = model.predict([[best_x]])
    # predicted_improvement: coarse grid used for reporting only, not for proposal
    coarse = np.linspace(CONFIG.lattice_min, CONFIG.lattice_max, CONFIG.n_candidates)
    coarse_mean, _ = model.predict(coarse)
    predicted_improvement = float(max(0.0, float(np.min(coarse_mean)) - float(mean_at[0])))
    return best_x, float(mean_at[0]), float(std_at[0]), predicted_improvement


def best_observed(lattices: list[float], energies: list[float]) -> tuple[float, float]:
    idx = int(np.argmin(np.asarray(energies, dtype=float)))
    return float(lattices[idx]), float(energies[idx])


def predicted_best(model: GPModel, candidate_lattices: np.ndarray) -> tuple[float, float, float]:
    mean, std = model.predict(candidate_lattices)
    idx = int(np.argmin(mean))
    return float(candidate_lattices[idx]), float(mean[idx]), float(std[idx])


def gp_uncertainty_at(model: GPModel, lattice: float) -> float:
    _, std = model.predict([lattice])
    return float(std[0])


def plot_energy_curve(model: GPModel, candidate_lattices: np.ndarray, labeled_lattices: list[float], labeled_energies: list[float]) -> Path:
    mean, std = model.predict(candidate_lattices)
    best_a, best_e = best_observed(labeled_lattices, labeled_energies)

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(candidate_lattices, mean, color="tab:red", linestyle="--", lw=2, label="GP prediction")
    ax.fill_between(candidate_lattices, mean - std, mean + std, color="tab:red", alpha=0.22, label="GP uncertainty (+/- 1 std)")
    ax.scatter(labeled_lattices, labeled_energies, s=58, color="tab:blue", zorder=5, label="QE labels")
    ax.axvline(best_a, color="tab:green", linestyle=":", lw=2, label=f"Best observed a={best_a:.3f} A")
    ax.axvline(3.61, color="tab:gray", linestyle="-.", lw=1.5, label="Reference a~3.61 A")
    ax.axhline(best_e, color="tab:gray", linestyle=":", lw=1.2, label="Best observed E/atom")
    ax.set_xlabel("FCC Cu lattice constant a (A)")
    ax.set_ylabel("Total energy per atom (eV)")
    ax.set_title("Bulk Cu 4 atoms: QE Active Learning + Inverse Minimization")
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()

    path = PLOT_DIR / "bulk_cu_4_qe_energy_curve.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def plot_convergence(history: dict[str, list[float]]) -> Path:
    fig, (ax_e, ax_n) = plt.subplots(1, 2, figsize=(12, 4.5))
    ax_e.plot(history["iteration"], history["best_energy"], marker="o", color="tab:orange")
    ax_e.set_xlabel("Iteration")
    ax_e.set_ylabel("Best observed E/atom (eV)")
    ax_e.set_title("Energy minimization")
    ax_e.grid(alpha=0.25)

    ax_n.plot(history["iteration"], history["n_qe"], marker="s", color="tab:purple")
    ax_n.set_xlabel("Iteration")
    ax_n.set_ylabel("Successful QE evaluations")
    ax_n.set_title("QE evaluation count")
    ax_n.grid(alpha=0.25)

    fig.tight_layout()
    path = PLOT_DIR / "bulk_cu_4_qe_convergence.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def write_report(lines: list[str]) -> Path:
    REPORT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return REPORT_FILE


def main() -> None:
    ensure_qe_environment()
    candidate_lattices = np.linspace(CONFIG.lattice_min, CONFIG.lattice_max, CONFIG.n_candidates)
    test_atoms = build_fcc_cu(3.61)

    report: list[str] = []
    header = [
        "=" * 82,
        "Bulk FCC Cu 4 atoms active learning + inverse minimization using QE via ASE",
        f"Atoms: {len(test_atoms)} conventional FCC cell",
        f"Lattice range: {CONFIG.lattice_min:.3f} to {CONFIG.lattice_max:.3f} A",
        f"Initial lattices: {list(CONFIG.initial_lattices)} A",
        f"QE command base: {QE_COMMAND}",
        f"Pseudo dir: {PSEUDO_DIR_ABS}",
        f"Pseudopotentials: {PSEUDOPOTENTIALS}",
        f"ecutwfc / ecutrho: {ECUTWFC_RY:.1f} / {ECUTRHO_RY:.1f} Ry",
        f"kpts: {KPTS}",
        "=" * 82,
    ]
    print("\n".join(header))
    report.extend(header)

    labeled_lattices, labeled_energies = build_initial_training_set()
    model = GPModel()
    model.train(labeled_lattices, labeled_energies)

    history: dict[str, list[float]] = {
        "iteration": [],
        "best_lattice": [],
        "best_energy": [],
        "best_uncertainty": [],
        "predicted_min_lattice": [],
        "predicted_min_energy": [],
        "n_qe": [],
    }

    for iteration in range(1, CONFIG.max_iterations + 1):
        print(f"\nIteration {iteration}")
        report.append(f"\nIteration {iteration}")

        al_lattices = active_learning_query(model, candidate_lattices, labeled_lattices)
        if al_lattices:
            msg = f"  Active labels requested: {[round(a, 6) for a in al_lattices]} A"
            print(msg)
            report.append(msg)
            al_pairs = evaluate_new_lattices(al_lattices, parallel=True)
            added = add_successful_labels(al_pairs, labeled_lattices, labeled_energies)
            for lattice, energy in added:
                msg = f"    Added AL label: a={lattice:.6f} A -> E/atom={energy:.8f} eV"
                print(msg)
                report.append(msg)
            if added:
                model.train(labeled_lattices, labeled_energies)
        else:
            msg = "  Active labels requested: none above uncertainty threshold"
            print(msg)
            report.append(msg)

        proposal, pred_mean, pred_std, pred_improvement = propose_inverse_candidate(model)
        msg = (
            f"  Inverse minimization proposal: a={proposal:.6f} A, "
            f"GP E/atom={pred_mean:.8f} +/- {pred_std:.8f} eV, "
            f"predicted improvement proxy={pred_improvement:.8f} eV/atom"
        )
        print(msg)
        report.append(msg)

        if is_new_lattice(proposal, labeled_lattices):
            energy = compute_energy_per_atom(proposal, retries=CONFIG.retries)
            if energy is not None:
                labeled_lattices.append(proposal)
                labeled_energies.append(float(energy))
                model.train(labeled_lattices, labeled_energies)
                msg = f"    Added inverse label: a={proposal:.6f} A -> E/atom={energy:.8f} eV"
                print(msg)
                report.append(msg)
            else:
                msg = f"    Inverse proposal skipped after QE failure: a={proposal:.6f} A"
                print(msg)
                report.append(msg)
        else:
            msg = "    Inverse proposal already labeled"
            print(msg)
            report.append(msg)

        best_a, best_e = best_observed(labeled_lattices, labeled_energies)
        best_std = gp_uncertainty_at(model, best_a)
        pred_min_a, pred_min_e, pred_min_std = predicted_best(model, candidate_lattices)
        predicted_gap = max(0.0, best_e - pred_min_e)

        history["iteration"].append(iteration)
        history["best_lattice"].append(best_a)
        history["best_energy"].append(best_e)
        history["best_uncertainty"].append(best_std)
        history["predicted_min_lattice"].append(pred_min_a)
        history["predicted_min_energy"].append(pred_min_e)
        history["n_qe"].append(len(labeled_lattices))

        msg = (
            f"  Best observed: a={best_a:.6f} A, E/atom={best_e:.8f} eV, "
            f"GP std={best_std:.8f} eV, predicted min a={pred_min_a:.6f} A, "
            f"predicted gap={predicted_gap:.8f} eV/atom, QE labels={len(labeled_lattices)}"
        )
        print(msg)
        report.append(msg)

        if best_std < CONFIG.convergence_uncertainty and predicted_gap < CONFIG.convergence_predicted_improvement:
            msg = "  Converged: best observed point is low-uncertainty and no meaningful GP improvement remains"
            print(msg)
            report.append(msg)
            break

    best_a, best_e = best_observed(labeled_lattices, labeled_energies)
    best_std = gp_uncertainty_at(model, best_a)
    energy_plot = plot_energy_curve(model, candidate_lattices, labeled_lattices, labeled_energies)
    convergence_plot = plot_convergence(history)

    final_lines = [
        "",
        "=" * 82,
        "Final result",
        f"Best lattice constant: {best_a:.6f} A",
        f"Best QE energy per atom: {best_e:.8f} eV/atom",
        f"GP uncertainty at best lattice: {best_std:.8f} eV/atom",
        f"Successful QE evaluations: {len(labeled_lattices)}",
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
