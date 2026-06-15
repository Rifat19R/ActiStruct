"""
2D active learning + inverse design for bulk layered LiCoO2 using QE via ASE.

Objective:
    Minimize total energy per atom by varying the hexagonal in-plane lattice
    constant a and out-of-plane lattice constant c.

System:
    Layered LiCoO2, R-3m hexagonal setting, conventional 12-atom cell
    = 3 Li + 3 Co + 6 O.

Run:
    cd <ACTISTRUCT_ROOT>
    source .venv/bin/activate
    python examples/manual_qe/bulk_licoo2_qe_active_inverse.py
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
QE_RUN_DIR = ROOT / "outputs" / "qe_runs_bulk_licoo2"
PLOT_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)
QE_RUN_DIR.mkdir(parents=True, exist_ok=True)

CACHE_DIR = ROOT / "outputs" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_FILE = CACHE_DIR / "bulk_licoo2_12_qe_energy_cache_sssp_efficiency.pkl"
CACHE_LOCK = ROOT / "bulk_licoo2_12_qe_energy_cache_sssp_efficiency.lock"
REPORT_FILE = REPORT_DIR / "bulk_licoo2_12_qe_active_inverse_report.txt"

PSEUDO_DIR_ABS = os.environ.get("ESPRESSO_PSEUDO", "")
PSEUDOPOTENTIALS = {
    "Li": "li_pbe_v1.4.uspp.F.UPF",
    "Co": "Co_pbe_v1.2.uspp.F.UPF",
    "O": "O.pbe-n-kjpaw_psl.0.1.UPF",
}
ECUTWFC_RY = 60.0
ECUTRHO_RY = 480.0
KPTS = (4, 4, 2)
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
    a_min: float = 2.74
    a_max: float = 2.90
    c_min: float = 13.70
    c_max: float = 14.40
    n_a_candidates: int = 11
    n_c_candidates: int = 11
    initial_points: tuple[tuple[float, float], ...] = (
        (2.76, 13.85),
        (2.82, 14.05),
        (2.88, 14.25),
        (2.76, 14.25),
        (2.88, 13.85),
    )
    oxygen_z: float = 0.241
    max_iterations: int = 12
    uncertainty_threshold: float = 0.03  # eV/atom
    active_labels_per_iter: int = 2
    kappa: float = 1.0
    convergence_uncertainty: float = 0.03  # eV/atom
    convergence_predicted_improvement: float = 0.001  # eV/atom
    duplicate_tol: float = 1e-6
    cache_round_digits: int = 6
    random_state: int = 91
    retries: int = 2
    retry_wait_seconds: int = 5
    spin_polarized: bool = True
    co_initial_moment: float = 0.6


CONFIG = Config()


def hexagonal_cell(a: float, c: float) -> np.ndarray:
    """Return conventional hexagonal cell vectors."""
    a = float(a)
    c = float(c)
    return np.asarray(
        [
            [a, 0.0, 0.0],
            [-0.5 * a, 0.5 * np.sqrt(3.0) * a, 0.0],
            [0.0, 0.0, c],
        ],
        dtype=float,
    )


def wrap_scaled(position: tuple[float, float, float]) -> list[float]:
    return [float(x % 1.0) for x in position]


def build_licoo2_r3m(a: float, c: float, oxygen_z: float = CONFIG.oxygen_z) -> Atoms:
    """Build layered LiCoO2 R-3m conventional hexagonal cell with 12 atoms."""
    oxygen_z = float(oxygen_z)
    centering = [
        (0.0, 0.0, 0.0),
        (2.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0),
        (1.0 / 3.0, 2.0 / 3.0, 2.0 / 3.0),
    ]

    li_scaled = [wrap_scaled((tx, ty, tz)) for tx, ty, tz in centering]
    co_scaled = [wrap_scaled((tx, ty, tz + 0.5)) for tx, ty, tz in centering]
    o_scaled: list[list[float]] = []
    for tx, ty, tz in centering:
        o_scaled.append(wrap_scaled((tx, ty, tz + oxygen_z)))
        o_scaled.append(wrap_scaled((tx, ty, tz - oxygen_z)))

    symbols = ["Li"] * 3 + ["Co"] * 3 + ["O"] * 6
    atoms = Atoms(symbols, cell=hexagonal_cell(a, c), pbc=True)
    atoms.set_scaled_positions(li_scaled + co_scaled + o_scaled)

    if len(atoms) != 12:
        raise RuntimeError(f"Expected 12 atoms, got {len(atoms)}")
    counts = {symbol: atoms.get_chemical_symbols().count(symbol) for symbol in ("Li", "Co", "O")}
    if counts != {"Li": 3, "Co": 3, "O": 6}:
        raise RuntimeError(f"Unexpected LiCoO2 composition: {counts}")

    if CONFIG.spin_polarized:
        moments = [0.0 if atom.symbol != "Co" else CONFIG.co_initial_moment for atom in atoms]
        atoms.set_initial_magnetic_moments(moments)
    return atoms


def qe_input_data(prefix: str) -> dict:
    """Quantum ESPRESSO pw.x input for layered LiCoO2 SCF."""
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
            "electron_maxstep": 300,
            "mixing_beta": 0.25,
        },
    }
    if CONFIG.spin_polarized:
        input_data["system"]["nspin"] = 2
        input_data["system"]["starting_magnetization(1)"] = 0.0
        input_data["system"]["starting_magnetization(2)"] = 0.5
        input_data["system"]["starting_magnetization(3)"] = 0.0
    return input_data


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
    a_values = np.linspace(CONFIG.a_min, CONFIG.a_max, CONFIG.n_a_candidates)
    c_values = np.linspace(CONFIG.c_min, CONFIG.c_max, CONFIG.n_c_candidates)
    return np.asarray([(a, c) for a in a_values for c in c_values], dtype=float)


def point_key(point: tuple[float, float] | np.ndarray) -> str:
    a, c = np.asarray(point, dtype=float)
    return f"a={a:.{CONFIG.cache_round_digits}f}:c={c:.{CONFIG.cache_round_digits}f}"


def cache_key_lattice(point: tuple[float, float] | np.ndarray) -> str:
    return (
        f"bulklicoo2_12:energy_per_atom:{point_key(point)}:"
        f"oxygen_z={CONFIG.oxygen_z}:pseudo={PSEUDOPOTENTIALS}:"
        f"ecut={ECUTWFC_RY}-{ECUTRHO_RY}:kpts={KPTS}:spin={CONFIG.spin_polarized}"
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


def compute_energy_per_atom(point: tuple[float, float] | np.ndarray, retries: int = 2) -> float | None:
    """Compute/cached LiCoO2 energy per atom at lattice constants (a, c)."""
    a, c = np.asarray(point, dtype=float)
    key = cache_key_lattice((a, c))
    cached = get_cached_value(key)
    if cached is not None:
        return float(cached)

    last_error = None
    for attempt in range(1, retries + 2):
        tag = point_key((a, c)).replace("=", "").replace(":", "_").replace(".", "p")
        work_dir = QE_RUN_DIR / f"bulklicoo2_{tag}_pid{os.getpid()}_attempt{attempt}"
        try:
            atoms = build_licoo2_r3m(a, c)
            atoms.calc = get_qe_calculator(work_dir, prefix=f"bulklicoo2_{tag}")
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
            print(f"WARNING: QE failed for a={a:.6f} A, c={c:.6f} A attempt {attempt}/{retries + 1}: {exc}")
            if attempt <= retries:
                time.sleep(CONFIG.retry_wait_seconds)

    print(f"WARNING: skip a={a:.6f} A, c={c:.6f} A after QE failures: {last_error}")
    return None


def evaluate_point(point: tuple[float, float] | np.ndarray) -> tuple[float, float, float | None]:
    a, c = np.asarray(point, dtype=float)
    try:
        return float(a), float(c), compute_energy_per_atom((a, c), retries=CONFIG.retries)
    except Exception:
        print(f"WARNING: unexpected failure at a={a:.6f} A, c={c:.6f} A")
        traceback.print_exc()
        return float(a), float(c), None


class GPModel:
    """Gaussian-process forward model: (a, c) -> energy per atom."""

    def __init__(self) -> None:
        kernel = (
            ConstantKernel(1.0, (1e-3, 1e3))
            * RBF(length_scale=[0.04, 0.18], length_scale_bounds=[(1e-3, 0.5), (1e-2, 2.0)])
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
    for a, c, energy in raw_results:
        if energy is None:
            print(f"WARNING: no label added for a={a:.6f} A, c={c:.6f} A")
            continue
        results.append(((float(a), float(c)), float(energy)))
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
    offsets = [(0.0, 0.0), (-0.01, 0.0), (0.01, 0.0), (0.0, -0.04), (0.0, 0.04)]

    for base_a, base_c in CONFIG.initial_points:
        added = False
        for da, dc in offsets:
            trial = (
                float(np.clip(base_a + da, CONFIG.a_min, CONFIG.a_max)),
                float(np.clip(base_c + dc, CONFIG.c_min, CONFIG.c_max)),
            )
            if not is_new_point(trial, points):
                continue
            energy = compute_energy_per_atom(trial, retries=CONFIG.retries)
            if energy is None:
                continue
            points.append(trial)
            energies.append(float(energy))
            print(f"Initial label: a={trial[0]:.6f} A, c={trial[1]:.6f} A -> E/atom={energy:.8f} eV")
            added = True
            break
        if not added:
            raise RuntimeError(f"Could not create initial label near a={base_a:.6f}, c={base_c:.6f}")

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

    Searches (a, c) lattice-constant space continuously. Scales to any dimension.
    """
    bounds = [(CONFIG.a_min, CONFIG.a_max), (CONFIG.c_min, CONFIG.c_max)]

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
    a_coarse = np.linspace(CONFIG.a_min, CONFIG.a_max, CONFIG.n_a_candidates)
    c_coarse = np.linspace(CONFIG.c_min, CONFIG.c_max, CONFIG.n_c_candidates)
    aa, cc = np.meshgrid(a_coarse, c_coarse)
    coarse_pts = np.column_stack([aa.ravel(), cc.ravel()])
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

    a_values = np.unique(candidate_points[:, 0])
    c_values = np.unique(candidate_points[:, 1])
    energy_grid = mean.reshape(len(a_values), len(c_values)).T

    fig, ax = plt.subplots(figsize=(9, 6.5))
    contour = ax.contourf(a_values, c_values, energy_grid, levels=30, cmap="viridis")
    fig.colorbar(contour, ax=ax, label="GP predicted E/atom (eV)")
    labeled = np.asarray(labeled_points)
    ax.scatter(labeled[:, 0], labeled[:, 1], c="white", edgecolor="black", s=52, label="QE labels")
    ax.scatter([best_point[0]], [best_point[1]], c="red", marker="*", s=180, label="Best observed")
    ax.axvline(2.815, color="white", linestyle="--", lw=1.2, alpha=0.8)
    ax.axhline(14.05, color="white", linestyle="--", lw=1.2, alpha=0.8)
    ax.set_xlabel("hexagonal lattice constant a (A)")
    ax.set_ylabel("hexagonal lattice constant c (A)")
    ax.set_title("Bulk LiCoO2 12 atoms: QE Active Learning + Inverse Minimization")
    ax.legend()
    fig.tight_layout()

    path = PLOT_DIR / "bulk_licoo2_12_qe_energy_surface.png"
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
    path = PLOT_DIR / "bulk_licoo2_12_qe_convergence.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def write_report(lines: list[str]) -> Path:
    REPORT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return REPORT_FILE


def main() -> None:
    ensure_qe_environment()
    candidate_points = make_candidate_grid()
    test_atoms = build_licoo2_r3m(2.815, 14.05)
    counts = {symbol: test_atoms.get_chemical_symbols().count(symbol) for symbol in ("Li", "Co", "O")}

    report: list[str] = []
    header = [
        "=" * 90,
        "Bulk layered LiCoO2 12 atoms active learning + inverse minimization using QE via ASE",
        f"Atoms: {len(test_atoms)} conventional R-3m hexagonal cell; composition: {counts}",
        f"a range: {CONFIG.a_min:.3f} to {CONFIG.a_max:.3f} A",
        f"c range: {CONFIG.c_min:.3f} to {CONFIG.c_max:.3f} A",
        f"Oxygen internal z: {CONFIG.oxygen_z:.6f}",
        f"Initial points: {list(CONFIG.initial_points)}",
        f"QE command base: {QE_COMMAND}",
        f"Pseudo dir: {PSEUDO_DIR_ABS}",
        f"Pseudopotentials: {PSEUDOPOTENTIALS}",
        f"ecutwfc / ecutrho: {ECUTWFC_RY:.1f} / {ECUTRHO_RY:.1f} Ry",
        f"kpts: {KPTS}",
        f"Spin polarized: {CONFIG.spin_polarized}; Co initial moment: {CONFIG.co_initial_moment:.2f} mu_B",
        "=" * 90,
    ]
    print("\n".join(header))
    report.extend(header)

    labeled_points, labeled_energies = build_initial_training_set()
    model = GPModel()
    model.train(labeled_points, labeled_energies)

    history: dict[str, list[float]] = {
        "iteration": [],
        "best_a": [],
        "best_c": [],
        "best_energy": [],
        "best_uncertainty": [],
        "predicted_min_a": [],
        "predicted_min_c": [],
        "predicted_min_energy": [],
        "n_qe": [],
    }

    for iteration in range(1, CONFIG.max_iterations + 1):
        print(f"\nIteration {iteration}")
        report.append(f"\nIteration {iteration}")

        al_points = active_learning_query(model, candidate_points, labeled_points)
        if al_points:
            msg = f"  Active labels requested: {[(round(a, 6), round(c, 6)) for a, c in al_points]}"
            print(msg)
            report.append(msg)
            al_pairs = evaluate_new_points(al_points, parallel=True)
            added = add_successful_labels(al_pairs, labeled_points, labeled_energies)
            for (a, c), energy in added:
                msg = f"    Added AL label: a={a:.6f} A, c={c:.6f} A -> E/atom={energy:.8f} eV"
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
            f"  Inverse minimization proposal: a={proposal[0]:.6f} A, c={proposal[1]:.6f} A, "
            f"GP E/atom={pred_mean:.8f} +/- {pred_std:.8f} eV, "
            f"predicted improvement proxy={pred_improvement:.8f} eV/atom"
        )
        print(msg)
        report.append(msg)

        if is_new_point(proposal, labeled_points):
            energy = compute_energy_per_atom(proposal, retries=CONFIG.retries)
            if energy is not None:
                labeled_points.append(proposal)
                labeled_energies.append(float(energy))
                model.train(labeled_points, labeled_energies)
                msg = f"    Added inverse label: a={proposal[0]:.6f} A, c={proposal[1]:.6f} A -> E/atom={energy:.8f} eV"
                print(msg)
                report.append(msg)
            else:
                msg = f"    Inverse proposal skipped after QE failure: a={proposal[0]:.6f}, c={proposal[1]:.6f}"
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
        history["best_a"].append(best_point[0])
        history["best_c"].append(best_point[1])
        history["best_energy"].append(best_e)
        history["best_uncertainty"].append(best_std)
        history["predicted_min_a"].append(pred_min_point[0])
        history["predicted_min_c"].append(pred_min_point[1])
        history["predicted_min_energy"].append(pred_min_e)
        history["n_qe"].append(len(labeled_points))

        msg = (
            f"  Best observed: a={best_point[0]:.6f} A, c={best_point[1]:.6f} A, "
            f"E/atom={best_e:.8f} eV, GP std={best_std:.8f} eV, "
            f"predicted min=({pred_min_point[0]:.6f}, {pred_min_point[1]:.6f}), "
            f"predicted gap={predicted_gap:.8f} eV/atom, QE labels={len(labeled_points)}"
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
        "=" * 90,
        "Final result",
        f"Best lattice constant a: {best_point[0]:.6f} A",
        f"Best lattice constant c: {best_point[1]:.6f} A",
        f"Best QE energy per atom: {best_e:.8f} eV/atom",
        f"GP uncertainty at best lattice pair: {best_std:.8f} eV/atom",
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
