"""
Active learning + inverse design for H2 using Quantum ESPRESSO via ASE.

Target property:
    Binding energy = E_H2(r) - 2 * E_H(atom)

Before running:
    1. Install Quantum ESPRESSO and make pw.x/mpirun available in WSL PATH.
    2. Keep SSSP 1.3.0 PBE efficiency pseudopotentials available at
       the directory configured by ESPRESSO_PSEUDO.
    3. Activate Python environment with numpy, matplotlib, scikit-learn, ase.

Run:
    cd <ACTISTRUCT_ROOT>
    source .venv/bin/activate
    python examples/manual_qe/h2_qe_active_inverse.py
"""

from __future__ import annotations

from dataclasses import dataclass
from multiprocessing import Pool
from pathlib import Path
import os
import pickle
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
from sklearn.gaussian_process.kernels import RBF, WhiteKernel
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
QE_RUN_DIR = ROOT / "outputs" / "qe_runs"
PLOT_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)
QE_RUN_DIR.mkdir(parents=True, exist_ok=True)

CACHE_DIR = ROOT / "outputs" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_FILE = CACHE_DIR / "h2_energy_cache_sssp_efficiency_spinref.pkl"
CACHE_LOCK = ROOT / "h2_energy_cache_sssp_efficiency_spinref.lock"
REPORT_FILE = REPORT_DIR / "h2_qe_active_inverse_report.txt"

PSEUDO_DIR_ABS = os.environ.get("ESPRESSO_PSEUDO", "")
PSEUDOPOTENTIALS = {"H": "H.pbe-rrkjus_psl.1.0.0.UPF"}
ECUTWFC_RY = 50.0
ECUTRHO_RY = 400.0
N_PROCS = 2
PARALLEL_WORKERS = 2
KPTS = (1, 1, 1)
PW_X_CANDIDATES = [
    os.environ.get("ESPRESSO_PW"),
    shutil.which("pw.x"),
]
PW_X = next((str(Path(path)) for path in PW_X_CANDIDATES if path and Path(path).exists()), "pw.x")
QE_COMMAND = os.environ.get("ESPRESSO_COMMAND", f"mpirun -np {N_PROCS} {PW_X}")
# ASE's current EspressoProfile appends "-in espresso.pwi" and captures stdout
# to espresso.pwo. This is equivalent to: mpirun -np 2 pw.x -in PREFIX.pwi > PREFIX.pwo


@dataclass
class Config:
    target_binding_energy: float = -4.5
    distance_min: float = 0.5
    distance_max: float = 2.0
    n_candidates: int = 100
    initial_distances: tuple[float, ...] = (0.62, 0.90, 1.30)
    max_iterations: int = 12
    uncertainty_threshold: float = 0.05
    active_labels_per_iter: int = 2
    kappa: float = 1.0
    convergence_error: float = 0.03
    duplicate_tol: float = 1e-6
    cache_round_digits: int = 6
    random_state: int = 23
    box_size: float = 10.0
    retries: int = 2
    retry_wait_seconds: int = 5


CONFIG = Config()


def make_h2(r: float, box_size: float = 10.0) -> Atoms:
    """Return H2 in a cubic box with bond distance r in Angstrom."""
    center = box_size / 2.0
    half = float(r) / 2.0
    atoms = Atoms(
        "H2",
        positions=[[center - half, center, center], [center + half, center, center]],
        cell=[box_size, box_size, box_size],
        pbc=True,
    )
    return atoms


def make_h_atom(box_size: float = 10.0) -> Atoms:
    """Return isolated H atom in same cubic box used for H2."""
    center = box_size / 2.0
    atoms = Atoms(
        "H",
        positions=[[center, center, center]],
        cell=[box_size, box_size, box_size],
        pbc=True,
    )
    atoms.set_initial_magnetic_moments([1.0])
    return atoms


def qe_input_data(prefix: str, spin_polarized: bool = False) -> dict:
    """Quantum ESPRESSO pw.x input parameters."""
    input_data = {
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
    if spin_polarized:
        input_data["system"]["nspin"] = 2
    return input_data


def get_qe_calculator(directory: Path, prefix: str, spin_polarized: bool = False) -> Espresso:
    """Return ASE Espresso calculator configured for QE pw.x."""
    directory.mkdir(parents=True, exist_ok=True)

    kwargs = dict(
        pseudopotentials=PSEUDOPOTENTIALS,
        input_data=qe_input_data(prefix=prefix, spin_polarized=spin_polarized),
        kpts=KPTS,
        directory=str(directory),
    )

    if EspressoProfile is not None:
        profile = EspressoProfile(command=QE_COMMAND, pseudo_dir=PSEUDO_DIR_ABS)
        return Espresso(profile=profile, **kwargs)

    # Older ASE accepted command directly. Kept for portability.
    old_command = f"{QE_COMMAND} -in PREFIX.pwi > PREFIX.pwo"
    return Espresso(command=old_command, **kwargs)


def ensure_qe_environment() -> None:
    if PW_X == "pw.x" and shutil.which("pw.x") is None:
        raise RuntimeError("pw.x not found in PATH. Set ESPRESSO_COMMAND or add pw.x to PATH.")
    if not PSEUDO_DIR_ABS:
        raise RuntimeError("Set ESPRESSO_PSEUDO to the directory containing required UPF files.")
    pseudo_path = Path(PSEUDO_DIR_ABS) / PSEUDOPOTENTIALS["H"]
    if not pseudo_path.exists():
        raise FileNotFoundError(f"Missing H pseudopotential: {pseudo_path}")


def cache_key_distance(r: float) -> str:
    return f"binding:{float(r):.{CONFIG.cache_round_digits}f}"


def acquire_cache_lock(timeout: float = 600.0, poll: float = 0.1) -> int:
    """Create simple cross-process lock file. Returns lock fd."""
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
        cache = load_cache_unlocked()
        return cache.get(key)
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


def get_h_atom_energy(retries: int = 2) -> float:
    """Compute isolated H atom total energy once and cache it."""
    key = "h_atom_total_energy"
    cached = get_cached_value(key)
    if cached is not None:
        return float(cached)

    last_error = None
    for attempt in range(1, retries + 2):
        work_dir = QE_RUN_DIR / f"h_atom_pid{os.getpid()}_attempt{attempt}"
        try:
            atoms = make_h_atom(CONFIG.box_size)
            atoms.calc = get_qe_calculator(work_dir, prefix="h_atom", spin_polarized=False)
            energy = float(atoms.get_potential_energy())
            set_cached_value(key, energy)
            return energy
        except Exception as exc:
            last_error = exc
            print(f"WARNING: H atom QE failed attempt {attempt}/{retries + 1}: {exc}")
            if attempt <= retries:
                time.sleep(CONFIG.retry_wait_seconds)

    raise RuntimeError(f"H atom QE failed after {retries + 1} attempts: {last_error}")


def compute_binding_energy(r: float, retries: int = 2) -> float | None:
    """
    Compute H2 binding energy at bond distance r.

    Returns cached value if available. On repeated QE failure, returns None.
    """
    key = cache_key_distance(r)
    cached = get_cached_value(key)
    if cached is not None:
        return float(cached)

    last_error = None
    h_atom_energy = get_h_atom_energy(retries=retries)

    for attempt in range(1, retries + 2):
        r_tag = f"{float(r):.{CONFIG.cache_round_digits}f}".replace(".", "p")
        work_dir = QE_RUN_DIR / f"h2_r{r_tag}_pid{os.getpid()}_attempt{attempt}"
        try:
            atoms = make_h2(float(r), CONFIG.box_size)
            atoms.calc = get_qe_calculator(work_dir, prefix=f"h2_r{r_tag}", spin_polarized=False)
            total_energy = float(atoms.get_potential_energy())
            binding_energy = total_energy - 2.0 * h_atom_energy
            set_cached_value(key, binding_energy)
            return binding_energy
        except Exception as exc:
            last_error = exc
            print(f"WARNING: QE failed for R={float(r):.6f} A attempt {attempt}/{retries + 1}: {exc}")
            if attempt <= retries:
                time.sleep(CONFIG.retry_wait_seconds)

    print(f"WARNING: skip R={float(r):.6f} A after QE failures: {last_error}")
    return None


def evaluate_distance(r: float) -> tuple[float, float | None]:
    """Multiprocessing helper."""
    try:
        return float(r), compute_binding_energy(float(r), retries=CONFIG.retries)
    except Exception:
        print(f"WARNING: unexpected failure at R={float(r):.6f} A")
        traceback.print_exc()
        return float(r), None


class GPModel:
    """Gaussian-process forward model: bond distance -> binding energy mean/std."""

    def __init__(self) -> None:
        kernel = RBF(length_scale=0.2) + WhiteKernel(noise_level=0.02)
        self.gp = GaussianProcessRegressor(
            kernel=kernel,
            normalize_y=True,
            n_restarts_optimizer=5,
            random_state=CONFIG.random_state,
        )

    def train(self, distances: list[float], energies: list[float]) -> None:
        x_train = np.asarray(distances, dtype=float).reshape(-1, 1)
        y_train = np.asarray(energies, dtype=float)
        self.gp.fit(x_train, y_train)

    def predict(self, distances: np.ndarray | list[float]) -> tuple[np.ndarray, np.ndarray]:
        x = np.asarray(distances, dtype=float).reshape(-1, 1)
        mean, std = self.gp.predict(x, return_std=True)
        return mean, std


def is_new_distance(distance: float, labeled_distances: list[float]) -> bool:
    return not np.any(
        np.isclose(float(distance), np.asarray(labeled_distances, dtype=float), atol=CONFIG.duplicate_tol, rtol=0.0)
    )


def evaluate_new_distances(distances: list[float], parallel: bool = True) -> list[tuple[float, float]]:
    """Evaluate distances and return successful (distance, energy) pairs."""
    if not distances:
        return []

    unique_distances: list[float] = []
    for distance in distances:
        if is_new_distance(distance, unique_distances):
            unique_distances.append(float(distance))

    if parallel and len(unique_distances) > 1:
        with Pool(processes=min(PARALLEL_WORKERS, len(unique_distances))) as pool:
            raw_results = pool.map(evaluate_distance, unique_distances)
    else:
        raw_results = [evaluate_distance(distance) for distance in unique_distances]

    results: list[tuple[float, float]] = []
    for distance, energy in raw_results:
        if energy is None:
            print(f"WARNING: no label added for R={distance:.6f} A")
            continue
        results.append((float(distance), float(energy)))
    return results


def add_successful_labels(
    pairs: list[tuple[float, float]],
    distances: list[float],
    energies: list[float],
) -> list[tuple[float, float]]:
    added: list[tuple[float, float]] = []
    for distance, energy in pairs:
        if is_new_distance(distance, distances):
            distances.append(float(distance))
            energies.append(float(energy))
            added.append((float(distance), float(energy)))
    return added


def build_initial_training_set() -> tuple[list[float], list[float]]:
    """Evaluate initial distances; try nearby replacements if one fails."""
    distances: list[float] = []
    energies: list[float] = []
    offsets = [0.0, -0.03, 0.03, -0.06, 0.06, -0.09, 0.09]

    for base_distance in CONFIG.initial_distances:
        added = False
        for offset in offsets:
            trial = float(np.clip(base_distance + offset, CONFIG.distance_min, CONFIG.distance_max))
            if not is_new_distance(trial, distances):
                continue
            energy = compute_binding_energy(trial, retries=CONFIG.retries)
            if energy is None:
                continue
            distances.append(trial)
            energies.append(float(energy))
            print(f"Initial label: R={trial:.6f} A -> E_bind={energy:.6f} eV")
            added = True
            break
        if not added:
            raise RuntimeError(f"Could not create initial training label near R={base_distance:.6f} A")

    if len(distances) < 3:
        raise RuntimeError("Need at least 3 successful initial labels for GP training.")
    return distances, energies


def active_learning_query(
    model: GPModel,
    candidate_distances: np.ndarray,
    labeled_distances: list[float],
) -> list[float]:
    """Return top-K unlabeled distances with uncertainty above threshold."""
    _, std = model.predict(candidate_distances)
    high_idx = np.where(std > CONFIG.uncertainty_threshold)[0]
    if len(high_idx) == 0:
        return []

    ordered = high_idx[np.argsort(std[high_idx])[::-1]]
    selected: list[float] = []
    for idx in ordered:
        distance = float(candidate_distances[idx])
        if is_new_distance(distance, labeled_distances + selected):
            selected.append(distance)
        if len(selected) >= CONFIG.active_labels_per_iter:
            break
    return selected


def acquisition_score(mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    return -np.abs(mean - CONFIG.target_binding_energy) + CONFIG.kappa * std


def propose_inverse_candidate(model: GPModel) -> tuple[float, float, float, float]:
    """Find the acquisition-score maximum via Differential Evolution — no grid required.

    Minimizes the negative acquisition score (equivalent to maximizing it).
    Scales to any number of dimensions without exponential blowup.
    """
    bounds = [(CONFIG.distance_min, CONFIG.distance_max)]

    def _neg_score(x: np.ndarray) -> float:
        mean, std = model.predict(x.reshape(1, -1))
        # acquisition_score = -|mean - target| + kappa*std  (maximize)
        # → minimize the negative
        return float(abs(mean[0] - CONFIG.target_binding_energy) - CONFIG.kappa * std[0])

    result = differential_evolution(
        _neg_score,
        bounds,
        seed=CONFIG.random_state,
        maxiter=500,
        tol=1e-7,
        polish=True,
        mutation=(0.5, 1.5),
        recombination=0.9,
    )
    distance = float(result.x[0])
    mean_at, std_at = model.predict([[distance]])
    return distance, float(mean_at[0]), float(std_at[0]), float(abs(mean_at[0] - CONFIG.target_binding_energy))


def best_observed(distances: list[float], energies: list[float]) -> tuple[float, float, float]:
    errors = np.abs(np.asarray(energies, dtype=float) - CONFIG.target_binding_energy)
    idx = int(np.argmin(errors))
    return float(distances[idx]), float(energies[idx]), float(errors[idx])


def gp_uncertainty_at(model: GPModel, distance: float) -> float:
    _, std = model.predict([distance])
    return float(std[0])


def plot_energy_curve(
    model: GPModel,
    candidate_distances: np.ndarray,
    labeled_distances: list[float],
    labeled_energies: list[float],
) -> Path:
    mean, std = model.predict(candidate_distances)

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(candidate_distances, mean, color="tab:red", linestyle="--", lw=2, label="GP prediction")
    ax.fill_between(
        candidate_distances,
        mean - std,
        mean + std,
        color="tab:red",
        alpha=0.22,
        label="GP uncertainty (+/- 1 std)",
    )
    ax.scatter(
        labeled_distances,
        labeled_energies,
        s=58,
        color="tab:blue",
        zorder=5,
        label="QE binding energies",
    )
    ax.axhline(CONFIG.target_binding_energy, color="tab:green", linestyle=":", lw=2, label="Target")
    ax.set_xlabel("H-H distance (A)")
    ax.set_ylabel("Binding energy (eV)")
    ax.set_title("H2 Active Learning + Inverse Design with Quantum ESPRESSO")
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()

    path = PLOT_DIR / "h2_qe_energy_curve.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def plot_convergence(history: dict[str, list[float]]) -> Path:
    fig, (ax_err, ax_eval) = plt.subplots(1, 2, figsize=(12, 4.5))

    ax_err.plot(history["iteration"], history["best_error"], marker="o", color="tab:orange")
    ax_err.axhline(CONFIG.convergence_error, color="tab:gray", linestyle=":", lw=1.5)
    ax_err.set_xlabel("Iteration")
    ax_err.set_ylabel("Best absolute error (eV)")
    ax_err.set_title("Convergence")
    ax_err.grid(alpha=0.25)

    ax_eval.plot(history["iteration"], history["n_qe"], marker="s", color="tab:purple")
    ax_eval.set_xlabel("Iteration")
    ax_eval.set_ylabel("Successful QE evaluations")
    ax_eval.set_title("QE evaluation count")
    ax_eval.grid(alpha=0.25)

    fig.tight_layout()
    path = PLOT_DIR / "h2_qe_convergence.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def write_report(lines: list[str]) -> Path:
    REPORT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return REPORT_FILE


def main() -> None:
    ensure_qe_environment()
    candidate_distances = np.linspace(CONFIG.distance_min, CONFIG.distance_max, CONFIG.n_candidates)

    report: list[str] = []
    header = [
        "=" * 78,
        "H2 active learning + inverse design using Quantum ESPRESSO via ASE",
        f"Target binding energy: {CONFIG.target_binding_energy:.6f} eV",
        f"Distance range: {CONFIG.distance_min:.3f} to {CONFIG.distance_max:.3f} A",
            f"QE command base: {QE_COMMAND}",
            f"Pseudo dir: {PSEUDO_DIR_ABS}",
            f"Pseudopotentials: {PSEUDOPOTENTIALS}",
            f"ecutwfc / ecutrho: {ECUTWFC_RY:.1f} / {ECUTRHO_RY:.1f} Ry",
        "=" * 78,
    ]
    print("\n".join(header))
    report.extend(header)

    h_atom_energy = get_h_atom_energy(retries=CONFIG.retries)
    line = f"Cached H atom total energy: {h_atom_energy:.10f} eV"
    print(line)
    report.append(line)

    labeled_distances, labeled_energies = build_initial_training_set()
    model = GPModel()
    model.train(labeled_distances, labeled_energies)

    history: dict[str, list[float]] = {
        "iteration": [],
        "best_distance": [],
        "best_energy": [],
        "best_error": [],
        "best_uncertainty": [],
        "n_qe": [],
    }

    for iteration in range(1, CONFIG.max_iterations + 1):
        print(f"\nIteration {iteration}")
        report.append(f"\nIteration {iteration}")

        # Active learning step.
        al_distances = active_learning_query(model, candidate_distances, labeled_distances)
        if al_distances:
            msg = f"  Active labels requested: {[round(d, 6) for d in al_distances]} A"
            print(msg)
            report.append(msg)
            al_pairs = evaluate_new_distances(al_distances, parallel=True)
            added = add_successful_labels(al_pairs, labeled_distances, labeled_energies)
            for distance, energy in added:
                msg = f"    Added AL label: R={distance:.6f} A -> E_bind={energy:.6f} eV"
                print(msg)
                report.append(msg)
            if added:
                model.train(labeled_distances, labeled_energies)
        else:
            msg = "  Active labels requested: none above uncertainty threshold"
            print(msg)
            report.append(msg)

        # Inverse design step.
        proposal, pred_mean, pred_std, pred_error = propose_inverse_candidate(model)
        msg = (
            f"  Inverse proposal: R={proposal:.6f} A, "
            f"GP E_bind={pred_mean:.6f} +/- {pred_std:.6f} eV, "
            f"pred error={pred_error:.6f} eV"
        )
        print(msg)
        report.append(msg)

        if is_new_distance(proposal, labeled_distances):
            energy = compute_binding_energy(proposal, retries=CONFIG.retries)
            if energy is not None:
                labeled_distances.append(proposal)
                labeled_energies.append(float(energy))
                model.train(labeled_distances, labeled_energies)
                msg = f"    Added inverse label: R={proposal:.6f} A -> E_bind={energy:.6f} eV"
                print(msg)
                report.append(msg)
            else:
                msg = f"    Inverse proposal skipped after QE failure: R={proposal:.6f} A"
                print(msg)
                report.append(msg)
        else:
            msg = "    Inverse proposal already labeled"
            print(msg)
            report.append(msg)

        best_r, best_e, best_err = best_observed(labeled_distances, labeled_energies)
        best_std = gp_uncertainty_at(model, best_r)
        history["iteration"].append(iteration)
        history["best_distance"].append(best_r)
        history["best_energy"].append(best_e)
        history["best_error"].append(best_err)
        history["best_uncertainty"].append(best_std)
        history["n_qe"].append(len(labeled_distances))

        msg = (
            f"  Best observed: R={best_r:.6f} A, E_bind={best_e:.6f} eV, "
            f"error={best_err:.6f} eV, GP std={best_std:.6f} eV, "
            f"QE labels={len(labeled_distances)}"
        )
        print(msg)
        report.append(msg)

        if best_err < CONFIG.convergence_error and best_std < CONFIG.uncertainty_threshold:
            msg = "  Converged: target error and uncertainty thresholds met"
            print(msg)
            report.append(msg)
            break

    best_r, best_e, best_err = best_observed(labeled_distances, labeled_energies)
    best_std = gp_uncertainty_at(model, best_r)
    energy_plot = plot_energy_curve(model, candidate_distances, labeled_distances, labeled_energies)
    convergence_plot = plot_convergence(history)

    final_lines = [
        "",
        "=" * 78,
        "Final result",
        f"Best distance: {best_r:.6f} A",
        f"Best QE binding energy: {best_e:.6f} eV",
        f"Target binding energy: {CONFIG.target_binding_energy:.6f} eV",
        f"Absolute error: {best_err:.6f} eV",
        f"GP uncertainty at best distance: {best_std:.6f} eV",
        f"Successful QE evaluations: {len(labeled_distances)}",
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
