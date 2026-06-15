"""
2D active learning + inverse design for H2O using Quantum ESPRESSO via ASE.

Objective:
    Minimize total energy by varying two molecular geometry variables:
    O-H bond length r and H-O-H angle theta.

System:
    One gas-phase H2O molecule in a 10 A cubic box.

Run:
    cd /mnt/d/Rifat_kh/inverse_active
    source .venv/bin/activate
    python h2o_qe_active_inverse.py
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
QE_RUN_DIR = ROOT / "outputs" / "qe_runs_h2o"
PLOT_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)
QE_RUN_DIR.mkdir(parents=True, exist_ok=True)

CACHE_FILE = ROOT / "h2o_qe_energy_cache_sssp_efficiency.pkl"
CACHE_LOCK = ROOT / "h2o_qe_energy_cache_sssp_efficiency.lock"
REPORT_FILE = REPORT_DIR / "h2o_qe_active_inverse_report.txt"

PSEUDO_DIR_ABS = "/mnt/d/Rifat_kh/SSSP_1.3.0_PBE_efficiency"
PSEUDOPOTENTIALS = {
    "H": "H.pbe-rrkjus_psl.1.0.0.UPF",
    # The markdown names O.pbe-n-rrkjus_psl.1.0.0.UPF, but this SSSP
    # efficiency folder contains the standard O PAW/USPP file below.
    "O": "O.pbe-n-kjpaw_psl.0.1.UPF",
}
ECUTWFC_RY = 50.0
ECUTRHO_RY = 400.0
KPTS = (1, 1, 1)
N_PROCS = 2
PARALLEL_WORKERS = 2
PW_X_CANDIDATES = [
    shutil.which("pw.x"),
    "/home/alchemist/q-e/bin/pw.x",
]
PW_X = next((str(Path(path)) for path in PW_X_CANDIDATES if path and Path(path).exists()), "pw.x")
QE_COMMAND = f"mpirun -np {N_PROCS} {PW_X}"
RY_TO_EV = 13.605693122994


@dataclass
class Config:
    r_min: float = 0.85
    r_max: float = 1.05
    theta_min: float = 95.0
    theta_max: float = 115.0
    n_r_candidates: int = 11
    n_theta_candidates: int = 11
    initial_points: tuple[tuple[float, float], ...] = (
        (0.90, 100.0),
        (0.96, 104.5),
        (1.02, 110.0),
        (0.90, 110.0),
        (1.02, 100.0),
    )
    max_iterations: int = 12
    uncertainty_threshold: float = 0.03  # eV
    active_labels_per_iter: int = 2
    kappa: float = 1.0
    convergence_uncertainty: float = 0.03  # eV
    convergence_predicted_improvement: float = 0.001  # eV
    duplicate_tol: float = 1e-6
    cache_round_digits: int = 6
    random_state: int = 61
    box_size: float = 10.0
    retries: int = 2
    retry_wait_seconds: int = 5


CONFIG = Config()


def build_h2o(r: float, theta_deg: float, box: float = 10.0) -> Atoms:
    """Build H2O molecule with O-H distance r and H-O-H angle theta_deg."""
    r = float(r)
    theta_rad = np.radians(float(theta_deg))
    center = np.array([box / 2.0, box / 2.0, box / 2.0])

    oxygen = center
    h1 = center + np.array([r, 0.0, 0.0])
    h2 = center + np.array([r * np.cos(theta_rad), 0.0, r * np.sin(theta_rad)])

    atoms = Atoms("OH2", positions=[oxygen, h1, h2], cell=[box, box, box], pbc=True)
    if len(atoms) != 3:
        raise RuntimeError(f"Expected 3 atoms, got {len(atoms)}")
    return atoms


def qe_input_data(prefix: str) -> dict:
    """Quantum ESPRESSO pw.x input for H2O SCF."""
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
        raise RuntimeError("pw.x not found in PATH and /home/alchemist/q-e/bin/pw.x does not exist.")
    for element, pseudo in PSEUDOPOTENTIALS.items():
        pseudo_path = Path(PSEUDO_DIR_ABS) / pseudo
        if not pseudo_path.exists():
            raise FileNotFoundError(f"Missing {element} pseudopotential: {pseudo_path}")


def make_candidate_grid() -> np.ndarray:
    r_values = np.linspace(CONFIG.r_min, CONFIG.r_max, CONFIG.n_r_candidates)
    theta_values = np.linspace(CONFIG.theta_min, CONFIG.theta_max, CONFIG.n_theta_candidates)
    return np.asarray([(r, theta) for r in r_values for theta in theta_values], dtype=float)


def cache_key_geometry(point: tuple[float, float] | np.ndarray) -> str:
    r, theta = np.asarray(point, dtype=float)
    return (
        f"h2o:energy:r={r:.{CONFIG.cache_round_digits}f}:"
        f"theta={theta:.{CONFIG.cache_round_digits}f}:"
        f"pseudo={PSEUDOPOTENTIALS}:ecut={ECUTWFC_RY}-{ECUTRHO_RY}:kpts={KPTS}"
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


def compute_total_energy(point: tuple[float, float] | np.ndarray, retries: int = 2) -> float | None:
    """Compute/cached H2O total energy at geometry (r, theta)."""
    r, theta = np.asarray(point, dtype=float)
    key = cache_key_geometry((r, theta))
    cached = get_cached_value(key)
    if cached is not None:
        return float(cached)

    last_error = None
    for attempt in range(1, retries + 2):
        r_tag = f"{r:.{CONFIG.cache_round_digits}f}".replace(".", "p")
        theta_tag = f"{theta:.{CONFIG.cache_round_digits}f}".replace(".", "p")
        work_dir = QE_RUN_DIR / f"h2o_r{r_tag}_t{theta_tag}_pid{os.getpid()}_attempt{attempt}"
        try:
            atoms = build_h2o(r, theta, CONFIG.box_size)
            atoms.calc = get_qe_calculator(work_dir, prefix=f"h2o_r{r_tag}_t{theta_tag}")
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
            print(
                f"WARNING: QE failed for r={r:.6f} A, theta={theta:.6f} deg "
                f"attempt {attempt}/{retries + 1}: {exc}"
            )
            if attempt <= retries:
                time.sleep(CONFIG.retry_wait_seconds)

    print(f"WARNING: skip r={r:.6f} A, theta={theta:.6f} deg after QE failures: {last_error}")
    return None


def evaluate_point(point: tuple[float, float] | np.ndarray) -> tuple[float, float, float | None]:
    r, theta = np.asarray(point, dtype=float)
    try:
        return float(r), float(theta), compute_total_energy((r, theta), retries=CONFIG.retries)
    except Exception:
        print(f"WARNING: unexpected failure at r={r:.6f} A, theta={theta:.6f} deg")
        traceback.print_exc()
        return float(r), float(theta), None


class GPModel:
    """Gaussian-process forward model: (r, theta) -> total energy."""

    def __init__(self) -> None:
        kernel = (
            ConstantKernel(1.0, (1e-3, 1e3))
            * RBF(length_scale=[0.04, 4.0], length_scale_bounds=[(1e-3, 0.5), (0.1, 30.0)])
            + WhiteKernel(noise_level=1e-5, noise_level_bounds=(1e-9, 1e-2))
        )
        self.gp = GaussianProcessRegressor(
            kernel=kernel,
            normalize_y=True,
            n_restarts_optimizer=8,
            random_state=CONFIG.random_state,
        )

    def train(self, points: list[tuple[float, float]], energies: list[float]) -> None:
        x_train = np.asarray(points, dtype=float)
        y_train = np.asarray(energies, dtype=float)
        self.gp.fit(x_train, y_train)

    def predict(self, points: np.ndarray | list[tuple[float, float]]) -> tuple[np.ndarray, np.ndarray]:
        x = np.asarray(points, dtype=float)
        mean, std = self.gp.predict(x, return_std=True)
        return mean, std


def is_new_point(point: tuple[float, float] | np.ndarray, labeled_points: list[tuple[float, float]]) -> bool:
    if not labeled_points:
        return True
    point_array = np.asarray(point, dtype=float)
    labeled = np.asarray(labeled_points, dtype=float)
    return not np.any(np.all(np.isclose(labeled, point_array, atol=CONFIG.duplicate_tol, rtol=0.0), axis=1))


def evaluate_new_points(points: list[tuple[float, float]], parallel: bool = True) -> list[tuple[tuple[float, float], float]]:
    unique_points: list[tuple[float, float]] = []
    for point in points:
        point_tuple = (float(point[0]), float(point[1]))
        if is_new_point(point_tuple, unique_points):
            unique_points.append(point_tuple)

    if not unique_points:
        return []
    if parallel and len(unique_points) > 1:
        with Pool(processes=min(PARALLEL_WORKERS, len(unique_points))) as pool:
            raw_results = pool.map(evaluate_point, unique_points)
    else:
        raw_results = [evaluate_point(point) for point in unique_points]

    results: list[tuple[tuple[float, float], float]] = []
    for r, theta, energy in raw_results:
        if energy is None:
            print(f"WARNING: no label added for r={r:.6f} A, theta={theta:.6f} deg")
            continue
        results.append(((float(r), float(theta)), float(energy)))
    return results


def add_successful_labels(
    pairs: list[tuple[tuple[float, float], float]],
    points: list[tuple[float, float]],
    energies: list[float],
) -> list[tuple[tuple[float, float], float]]:
    added: list[tuple[tuple[float, float], float]] = []
    for point, energy in pairs:
        if is_new_point(point, points):
            points.append((float(point[0]), float(point[1])))
            energies.append(float(energy))
            added.append((point, float(energy)))
    return added


def build_initial_training_set() -> tuple[list[tuple[float, float]], list[float]]:
    points: list[tuple[float, float]] = []
    energies: list[float] = []
    offset_points = [(0.0, 0.0), (-0.01, 0.0), (0.01, 0.0), (0.0, -1.0), (0.0, 1.0)]

    for base_r, base_theta in CONFIG.initial_points:
        added = False
        for dr, dtheta in offset_points:
            trial = (
                float(np.clip(base_r + dr, CONFIG.r_min, CONFIG.r_max)),
                float(np.clip(base_theta + dtheta, CONFIG.theta_min, CONFIG.theta_max)),
            )
            if not is_new_point(trial, points):
                continue
            energy = compute_total_energy(trial, retries=CONFIG.retries)
            if energy is None:
                continue
            points.append(trial)
            energies.append(float(energy))
            print(f"Initial label: r={trial[0]:.6f} A, theta={trial[1]:.6f} deg -> E={energy:.8f} eV")
            added = True
            break
        if not added:
            raise RuntimeError(f"Could not create initial label near r={base_r:.6f}, theta={base_theta:.6f}")

    if len(points) < 5:
        raise RuntimeError("Need at least 5 successful labels for 2D GP training.")
    return points, energies


def active_learning_query(model: GPModel, candidate_points: np.ndarray, labeled_points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    _, std = model.predict(candidate_points)
    high_idx = np.where(std > CONFIG.uncertainty_threshold)[0]
    if len(high_idx) == 0:
        return []

    ordered = high_idx[np.argsort(std[high_idx])[::-1]]
    selected: list[tuple[float, float]] = []
    for idx in ordered:
        point = (float(candidate_points[idx, 0]), float(candidate_points[idx, 1]))
        if is_new_point(point, labeled_points + selected):
            selected.append(point)
        if len(selected) >= CONFIG.active_labels_per_iter:
            break
    return selected


def lower_confidence_bound(mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    """Minimize this: predicted energy minus exploration bonus."""
    return mean - CONFIG.kappa * std


def propose_inverse_candidate(model: GPModel) -> tuple[tuple[float, float], float, float, float]:
    """Find the 2D LCB minimum via Differential Evolution — no grid required.

    Searches (r, theta) space continuously. Works for any number of dimensions.
    """
    bounds = [(CONFIG.r_min, CONFIG.r_max), (CONFIG.theta_min, CONFIG.theta_max)]

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
    best_x = result.x
    best_point = (float(best_x[0]), float(best_x[1]))
    mean_at, std_at = model.predict([best_point])
    # Coarse grid for predicted_improvement reporting only
    r_coarse = np.linspace(CONFIG.r_min, CONFIG.r_max, CONFIG.n_r_candidates)
    t_coarse = np.linspace(CONFIG.theta_min, CONFIG.theta_max, CONFIG.n_theta_candidates)
    rr, tt = np.meshgrid(r_coarse, t_coarse)
    coarse_pts = np.column_stack([rr.ravel(), tt.ravel()])
    coarse_mean, _ = model.predict(coarse_pts)
    predicted_improvement = float(max(0.0, float(np.min(coarse_mean)) - float(mean_at[0])))
    return best_point, float(mean_at[0]), float(std_at[0]), predicted_improvement


def best_observed(points: list[tuple[float, float]], energies: list[float]) -> tuple[tuple[float, float], float]:
    idx = int(np.argmin(np.asarray(energies, dtype=float)))
    return points[idx], float(energies[idx])


def predicted_best(model: GPModel, candidate_points: np.ndarray) -> tuple[tuple[float, float], float, float]:
    mean, std = model.predict(candidate_points)
    idx = int(np.argmin(mean))
    return (float(candidate_points[idx, 0]), float(candidate_points[idx, 1])), float(mean[idx]), float(std[idx])


def gp_uncertainty_at(model: GPModel, point: tuple[float, float]) -> float:
    _, std = model.predict([point])
    return float(std[0])


def plot_energy_surface(
    model: GPModel,
    candidate_points: np.ndarray,
    labeled_points: list[tuple[float, float]],
    labeled_energies: list[float],
) -> Path:
    mean, _ = model.predict(candidate_points)
    best_point, _ = best_observed(labeled_points, labeled_energies)

    r_values = np.unique(candidate_points[:, 0])
    theta_values = np.unique(candidate_points[:, 1])
    energy_grid = mean.reshape(len(r_values), len(theta_values)).T

    fig, ax = plt.subplots(figsize=(9, 6.5))
    contour = ax.contourf(r_values, theta_values, energy_grid, levels=30, cmap="viridis")
    fig.colorbar(contour, ax=ax, label="GP predicted total energy (eV)")
    labeled = np.asarray(labeled_points)
    ax.scatter(labeled[:, 0], labeled[:, 1], c="white", edgecolor="black", s=52, label="QE labels")
    ax.scatter([best_point[0]], [best_point[1]], c="red", marker="*", s=180, label="Best observed")
    ax.axvline(0.96, color="white", linestyle="--", lw=1.2, alpha=0.8)
    ax.axhline(104.5, color="white", linestyle="--", lw=1.2, alpha=0.8)
    ax.set_xlabel("O-H bond length r (A)")
    ax.set_ylabel("H-O-H angle theta (deg)")
    ax.set_title("H2O 2D QE Active Learning + Inverse Minimization")
    ax.legend()
    fig.tight_layout()

    path = PLOT_DIR / "h2o_qe_energy_surface.png"
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
    path = PLOT_DIR / "h2o_qe_convergence.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def write_report(lines: list[str]) -> Path:
    REPORT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return REPORT_FILE


def main() -> None:
    ensure_qe_environment()
    candidate_points = make_candidate_grid()
    test_atoms = build_h2o(0.96, 104.5, CONFIG.box_size)

    report: list[str] = []
    header = [
        "=" * 88,
        "H2O 2D active learning + inverse minimization using QE via ASE",
        f"Atoms: {len(test_atoms)} molecule in {CONFIG.box_size:.1f} A cubic box",
        f"r range: {CONFIG.r_min:.3f} to {CONFIG.r_max:.3f} A",
        f"theta range: {CONFIG.theta_min:.3f} to {CONFIG.theta_max:.3f} deg",
        f"Initial points: {list(CONFIG.initial_points)}",
        f"QE command base: {QE_COMMAND}",
        f"Pseudo dir: {PSEUDO_DIR_ABS}",
        f"Pseudopotentials: {PSEUDOPOTENTIALS}",
        f"ecutwfc / ecutrho: {ECUTWFC_RY:.1f} / {ECUTRHO_RY:.1f} Ry",
        f"kpts: {KPTS}",
        "=" * 88,
    ]
    print("\n".join(header))
    report.extend(header)

    labeled_points, labeled_energies = build_initial_training_set()
    model = GPModel()
    model.train(labeled_points, labeled_energies)

    history: dict[str, list[float]] = {
        "iteration": [],
        "best_r": [],
        "best_theta": [],
        "best_energy": [],
        "best_uncertainty": [],
        "predicted_min_r": [],
        "predicted_min_theta": [],
        "predicted_min_energy": [],
        "n_qe": [],
    }

    for iteration in range(1, CONFIG.max_iterations + 1):
        print(f"\nIteration {iteration}")
        report.append(f"\nIteration {iteration}")

        al_points = active_learning_query(model, candidate_points, labeled_points)
        if al_points:
            msg = f"  Active labels requested: {[(round(r, 6), round(t, 6)) for r, t in al_points]}"
            print(msg)
            report.append(msg)
            al_pairs = evaluate_new_points(al_points, parallel=True)
            added = add_successful_labels(al_pairs, labeled_points, labeled_energies)
            for (r, theta), energy in added:
                msg = f"    Added AL label: r={r:.6f} A, theta={theta:.6f} deg -> E={energy:.8f} eV"
                print(msg)
                report.append(msg)
            if added:
                model.train(labeled_points, labeled_energies)
        else:
            msg = "  Active labels requested: none above uncertainty threshold"
            print(msg)
            report.append(msg)

        proposal, pred_mean, pred_std, pred_improvement = propose_inverse_candidate(model)
        msg = (
            f"  Inverse minimization proposal: r={proposal[0]:.6f} A, theta={proposal[1]:.6f} deg, "
            f"GP E={pred_mean:.8f} +/- {pred_std:.8f} eV, "
            f"predicted improvement proxy={pred_improvement:.8f} eV"
        )
        print(msg)
        report.append(msg)

        if is_new_point(proposal, labeled_points):
            energy = compute_total_energy(proposal, retries=CONFIG.retries)
            if energy is not None:
                labeled_points.append(proposal)
                labeled_energies.append(float(energy))
                model.train(labeled_points, labeled_energies)
                msg = f"    Added inverse label: r={proposal[0]:.6f} A, theta={proposal[1]:.6f} deg -> E={energy:.8f} eV"
                print(msg)
                report.append(msg)
            else:
                msg = f"    Inverse proposal skipped after QE failure: r={proposal[0]:.6f}, theta={proposal[1]:.6f}"
                print(msg)
                report.append(msg)
        else:
            msg = "    Inverse proposal already labeled"
            print(msg)
            report.append(msg)

        best_point, best_e = best_observed(labeled_points, labeled_energies)
        best_std = gp_uncertainty_at(model, best_point)
        pred_min_point, pred_min_e, pred_min_std = predicted_best(model, candidate_points)
        predicted_gap = max(0.0, best_e - pred_min_e)

        history["iteration"].append(iteration)
        history["best_r"].append(best_point[0])
        history["best_theta"].append(best_point[1])
        history["best_energy"].append(best_e)
        history["best_uncertainty"].append(best_std)
        history["predicted_min_r"].append(pred_min_point[0])
        history["predicted_min_theta"].append(pred_min_point[1])
        history["predicted_min_energy"].append(pred_min_e)
        history["n_qe"].append(len(labeled_points))

        msg = (
            f"  Best observed: r={best_point[0]:.6f} A, theta={best_point[1]:.6f} deg, "
            f"E={best_e:.8f} eV, GP std={best_std:.8f} eV, "
            f"predicted min=({pred_min_point[0]:.6f}, {pred_min_point[1]:.6f}), "
            f"predicted gap={predicted_gap:.8f} eV, QE labels={len(labeled_points)}"
        )
        print(msg)
        report.append(msg)

        if best_std < CONFIG.convergence_uncertainty and predicted_gap < CONFIG.convergence_predicted_improvement:
            msg = "  Converged: best observed point is low-uncertainty and no meaningful GP improvement remains"
            print(msg)
            report.append(msg)
            break

    best_point, best_e = best_observed(labeled_points, labeled_energies)
    best_std = gp_uncertainty_at(model, best_point)
    surface_plot = plot_energy_surface(model, candidate_points, labeled_points, labeled_energies)
    convergence_plot = plot_convergence(history)

    final_lines = [
        "",
        "=" * 88,
        "Final result",
        f"Best O-H bond length: {best_point[0]:.6f} A",
        f"Best H-O-H angle: {best_point[1]:.6f} deg",
        f"Best QE total energy: {best_e:.8f} eV",
        f"GP uncertainty at best geometry: {best_std:.8f} eV",
        f"Successful QE evaluations: {len(labeled_points)}",
        f"Energy surface plot: {surface_plot}",
        f"Convergence plot: {convergence_plot}",
        f"Cache file: {CACHE_FILE}",
    ]
    print("\n".join(final_lines))
    report.extend(final_lines)
    report_path = write_report(report)
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()
