"""
2D active learning + inverse design for H adsorption on Cu(111) using QE via ASE.

Objective:
    Minimize adsorption energy

        E_ads = E(Cu slab + H) - E(Cu slab) - E(H atom)

    by varying the in-plane fractional coordinates (u, v) of H on a p(2x2)
    Cu(111) slab.

System:
    Cu(111), 3 layers, p(2x2) supercell = 12 Cu atoms + 1 H adsorbate.
    Bottom Cu layer is fixed. Top two Cu layers and H relax for each site.

Run:
    cd /mnt/d/Rifat_kh/inverse_active
    source .venv/bin/activate
    python h_cu111_qe_active_inverse.py
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
from ase.build import fcc111
from ase.calculators.espresso import Espresso
from ase.constraints import FixAtoms
from ase.optimize import BFGS
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
QE_RUN_DIR = ROOT / "outputs" / "qe_runs_h_cu111"
PLOT_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)
QE_RUN_DIR.mkdir(parents=True, exist_ok=True)

CACHE_FILE = ROOT / "h_cu111_qe_adsorption_cache_sssp_efficiency.pkl"
CACHE_LOCK = ROOT / "h_cu111_qe_adsorption_cache_sssp_efficiency.lock"
REPORT_FILE = REPORT_DIR / "h_cu111_qe_active_inverse_report.txt"

PSEUDO_DIR_ABS = "/mnt/d/Rifat_kh/SSSP_1.3.0_PBE_efficiency"
# The markdown names Cu rrkjus pseudopotentials. This local SSSP efficiency
# folder contains the validated Cu PAW file below. H uses the SSSP file.
PSEUDOPOTENTIALS = {
    "Cu": "Cu.paw.z_11.ld1.psl.v1.0.0-low.upf",
    "H": "H.pbe-rrkjus_psl.1.0.0.UPF",
}
ECUTWFC_RY = 50.0
ECUTRHO_RY = 400.0
KPTS_SLAB = (4, 4, 1)
KPTS_ATOM = (1, 1, 1)
6
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
    lattice_constant_cu: float = 3.61
    layers: int = 3
    slab_size: tuple[int, int] = (2, 2)
    vacuum: float = 15.0
    h_initial_height: float = 1.5
    h_atom_box: float = 10.0
    n_u_candidates: int = 7
    n_v_candidates: int = 7
    initial_points: tuple[tuple[float, float], ...] = (
        (0.00, 0.00),  # top-like
        (0.50, 0.00),  # bridge-like
        (1.0 / 3.0, 1.0 / 3.0),  # hollow-like
        (2.0 / 3.0, 2.0 / 3.0),  # hollow-like
        (0.50, 0.50),
    )
    max_iterations: int = 12
    uncertainty_threshold: float = 0.03  # eV
    active_labels_per_iter: int = 2
    kappa: float = 1.0
    convergence_uncertainty: float = 0.03  # eV
    convergence_predicted_improvement: float = 0.003  # eV
    duplicate_tol: float = 1e-6
    cache_round_digits: int = 6
    random_state: int = 111
    retries: int = 2
    retry_wait_seconds: int = 5
    relax_clean_slab: bool = True
    relax_adsorbed_slab: bool = True
    relax_fmax: float = 0.05
    relax_steps: int = 30
    bottom_layer_tolerance: float = 0.5


CONFIG = Config()


def bottom_layer_indices(atoms: Atoms, tolerance: float = CONFIG.bottom_layer_tolerance) -> list[int]:
    """Return atoms in the bottom layer by z coordinate."""
    z_positions = atoms.positions[:, 2]
    bottom_z = float(np.min(z_positions))
    return [i for i, z in enumerate(z_positions) if float(z) < bottom_z + float(tolerance)]


def apply_bottom_layer_constraint(atoms: Atoms) -> None:
    """Fix bottom Cu layer; top Cu layers and H remain free."""
    indices = bottom_layer_indices(atoms)
    atoms.set_constraint(FixAtoms(indices=indices))


def build_clean_slab(
    lattice_constant: float = CONFIG.lattice_constant_cu,
    layers: int = CONFIG.layers,
    vacuum: float = CONFIG.vacuum,
    size: tuple[int, int] = CONFIG.slab_size,
) -> Atoms:
    """Build Cu(111) slab with p(2x2) surface cell and bottom layer fixed."""
    ase_size = (size[0], size[1], layers)
    slab = fcc111("Cu", size=ase_size, a=float(lattice_constant), vacuum=float(vacuum), periodic=True)
    if len(slab) != size[0] * size[1] * layers:
        raise RuntimeError(f"Expected {size[0] * size[1] * layers} Cu atoms, got {len(slab)}")
    apply_bottom_layer_constraint(slab)
    return slab


def fractional_surface_to_cartesian_xy(slab: Atoms, u: float, v: float) -> np.ndarray:
    """Convert surface fractional coordinates (u, v) to Cartesian xy position."""
    cell = slab.cell.array
    vector = float(u) * cell[0] + float(v) * cell[1]
    return np.asarray([vector[0], vector[1]], dtype=float)


def add_h_to_slab(slab: Atoms, u: float, v: float, height: float = CONFIG.h_initial_height) -> Atoms:
    """Add H at fractional surface coordinate (u, v), height above top Cu layer."""
    atoms = slab.copy()
    xy = fractional_surface_to_cartesian_xy(atoms, u % 1.0, v % 1.0)
    top_z = float(np.max([atom.position[2] for atom in atoms if atom.symbol == "Cu"]))
    atoms += Atoms("H", positions=[[xy[0], xy[1], top_z + float(height)]])
    apply_bottom_layer_constraint(atoms)
    return atoms


def build_h_atom(box: float = CONFIG.h_atom_box) -> Atoms:
    """Build isolated spin-polarized H atom reference in a cubic box."""
    center = box / 2.0
    atoms = Atoms("H", positions=[[center, center, center]], cell=[box, box, box], pbc=True)
    atoms.set_initial_magnetic_moments([1.0])
    return atoms


def qe_input_data(prefix: str, spin_polarized: bool = False) -> dict:
    """Quantum ESPRESSO pw.x input."""
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
            "smearing": "mv",
            "degauss": 0.02,
        },
        "electrons": {
            "conv_thr": 1e-8,
            "electron_maxstep": 300,
            "mixing_beta": 0.3,
        },
    }
    if spin_polarized:
        input_data["system"]["nspin"] = 2
    return input_data


def get_qe_calculator(directory: Path, prefix: str, kpts: tuple[int, int, int], spin_polarized: bool = False) -> Espresso:
    """Return ASE Espresso calculator configured for QE pw.x."""
    directory.mkdir(parents=True, exist_ok=True)
    kwargs = dict(
        pseudopotentials=PSEUDOPOTENTIALS,
        input_data=qe_input_data(prefix=prefix, spin_polarized=spin_polarized),
        kpts=kpts,
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
    u_values = np.linspace(0.0, 1.0, CONFIG.n_u_candidates, endpoint=False)
    v_values = np.linspace(0.0, 1.0, CONFIG.n_v_candidates, endpoint=False)
    return np.asarray([(u, v) for u in u_values for v in v_values], dtype=float)


def point_key(point: tuple[float, float] | np.ndarray) -> str:
    u, v = np.asarray(point, dtype=float) % 1.0
    return f"u={u:.{CONFIG.cache_round_digits}f}:v={v:.{CONFIG.cache_round_digits}f}"


def cache_key_adsorption(point: tuple[float, float] | np.ndarray) -> str:
    return (
        f"hcu111:eads:{point_key(point)}:pseudo={PSEUDOPOTENTIALS}:"
        f"ecut={ECUTWFC_RY}-{ECUTRHO_RY}:kpts={KPTS_SLAB}:"
        f"relax_ads={CONFIG.relax_adsorbed_slab}:relax_clean={CONFIG.relax_clean_slab}"
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


def run_static_or_relaxed_energy(
    atoms: Atoms,
    work_dir: Path,
    prefix: str,
    kpts: tuple[int, int, int],
    spin_polarized: bool = False,
    relax: bool = False,
) -> float:
    """Run QE static energy or ASE BFGS relaxation with existing constraints."""
    atoms.calc = get_qe_calculator(work_dir, prefix=prefix, kpts=kpts, spin_polarized=spin_polarized)
    if relax:
        opt = BFGS(
            atoms,
            logfile=str(work_dir / "ase_bfgs.log"),
            trajectory=str(work_dir / "ase_bfgs.traj"),
        )
        opt.run(fmax=CONFIG.relax_fmax, steps=CONFIG.relax_steps)
    try:
        return float(atoms.get_potential_energy())
    except Exception:
        parsed_energy = parse_qe_total_energy(work_dir / "espresso.pwo")
        if parsed_energy is None:
            raise
        return parsed_energy


def get_h_atom_energy(retries: int = 2) -> float:
    """Compute isolated spin-polarized H atom energy once and cache it."""
    key = f"hcu111:h_atom:pseudo={PSEUDOPOTENTIALS['H']}:ecut={ECUTWFC_RY}-{ECUTRHO_RY}"
    cached = get_cached_value(key)
    if cached is not None:
        return float(cached)

    last_error = None
    for attempt in range(1, retries + 2):
        work_dir = QE_RUN_DIR / f"h_atom_pid{os.getpid()}_attempt{attempt}"
        try:
            atoms = build_h_atom(CONFIG.h_atom_box)
            energy = run_static_or_relaxed_energy(
                atoms,
                work_dir=work_dir,
                prefix="h_atom",
                kpts=KPTS_ATOM,
                spin_polarized=False,
                relax=False,
            )
            set_cached_value(key, energy)
            return energy
        except Exception as exc:
            last_error = exc
            print(f"WARNING: H atom QE failed attempt {attempt}/{retries + 1}: {exc}")
            if attempt <= retries:
                time.sleep(CONFIG.retry_wait_seconds)

    raise RuntimeError(f"H atom QE failed after {retries + 1} attempts: {last_error}")


def get_clean_slab_energy(retries: int = 2) -> float:
    """Compute clean Cu(111) slab energy once and cache it."""
    key = (
        f"hcu111:clean_slab:a={CONFIG.lattice_constant_cu}:layers={CONFIG.layers}:"
        f"size={CONFIG.slab_size}:pseudo={PSEUDOPOTENTIALS['Cu']}:"
        f"ecut={ECUTWFC_RY}-{ECUTRHO_RY}:kpts={KPTS_SLAB}:relax={CONFIG.relax_clean_slab}"
    )
    cached = get_cached_value(key)
    if cached is not None:
        return float(cached)

    last_error = None
    for attempt in range(1, retries + 2):
        work_dir = QE_RUN_DIR / f"clean_slab_pid{os.getpid()}_attempt{attempt}"
        try:
            atoms = build_clean_slab()
            energy = run_static_or_relaxed_energy(
                atoms,
                work_dir=work_dir,
                prefix="clean_cu111",
                kpts=KPTS_SLAB,
                spin_polarized=False,
                relax=CONFIG.relax_clean_slab,
            )
            set_cached_value(key, energy)
            return energy
        except Exception as exc:
            last_error = exc
            print(f"WARNING: clean slab QE failed attempt {attempt}/{retries + 1}: {exc}")
            if attempt <= retries:
                time.sleep(CONFIG.retry_wait_seconds)

    raise RuntimeError(f"Clean slab QE failed after {retries + 1} attempts: {last_error}")


def compute_adsorption_energy(point: tuple[float, float] | np.ndarray, retries: int = 2) -> float | None:
    """Compute/cached H adsorption energy at surface fractional point (u, v)."""
    u, v = np.asarray(point, dtype=float) % 1.0
    key = cache_key_adsorption((u, v))
    cached = get_cached_value(key)
    if cached is not None:
        return float(cached)

    slab_energy = get_clean_slab_energy(retries=retries)
    h_energy = get_h_atom_energy(retries=retries)

    last_error = None
    for attempt in range(1, retries + 2):
        tag = point_key((u, v)).replace("=", "").replace(":", "_").replace(".", "p")
        work_dir = QE_RUN_DIR / f"slab_h_{tag}_pid{os.getpid()}_attempt{attempt}"
        try:
            slab = build_clean_slab()
            atoms = add_h_to_slab(slab, u, v, height=CONFIG.h_initial_height)
            total_energy = run_static_or_relaxed_energy(
                atoms,
                work_dir=work_dir,
                prefix=f"cu111_h_{tag}",
                kpts=KPTS_SLAB,
                spin_polarized=False,
                relax=CONFIG.relax_adsorbed_slab,
            )
            adsorption_energy = total_energy - slab_energy - h_energy
            set_cached_value(key, adsorption_energy)
            return adsorption_energy
        except Exception as exc:
            last_error = exc
            print(f"WARNING: QE failed for u={u:.6f}, v={v:.6f} attempt {attempt}/{retries + 1}: {exc}")
            if attempt <= retries:
                time.sleep(CONFIG.retry_wait_seconds)

    print(f"WARNING: skip u={u:.6f}, v={v:.6f} after QE failures: {last_error}")
    return None


def evaluate_point(point: tuple[float, float] | np.ndarray) -> tuple[float, float, float | None]:
    u, v = np.asarray(point, dtype=float) % 1.0
    try:
        return float(u), float(v), compute_adsorption_energy((u, v), retries=CONFIG.retries)
    except Exception:
        print(f"WARNING: unexpected failure at u={u:.6f}, v={v:.6f}")
        traceback.print_exc()
        return float(u), float(v), None


class GPModel:
    """Gaussian-process forward model: (u, v) -> adsorption energy."""

    def __init__(self) -> None:
        kernel = (
            ConstantKernel(1.0, (1e-3, 1e3))
            * RBF(length_scale=[0.20, 0.20], length_scale_bounds=[(1e-3, 2.0), (1e-3, 2.0)])
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
    point_array = np.asarray(point, dtype=float) % 1.0
    labeled = np.asarray(labeled_points, dtype=float) % 1.0
    return not np.any(np.all(np.isclose(labeled, point_array, atol=CONFIG.duplicate_tol, rtol=0.0), axis=1))


def evaluate_new_points(points: list[tuple[float, float]], parallel: bool = True) -> list[tuple[tuple[float, float], float]]:
    unique_points: list[tuple[float, float]] = []
    for point in points:
        point_tuple = (float(point[0] % 1.0), float(point[1] % 1.0))
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
    for u, v, energy in raw_results:
        if energy is None:
            print(f"WARNING: no label added for u={u:.6f}, v={v:.6f}")
            continue
        results.append(((float(u), float(v)), float(energy)))
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
    offsets = [(0.0, 0.0), (0.02, 0.0), (-0.02, 0.0), (0.0, 0.02), (0.0, -0.02)]

    for base_u, base_v in CONFIG.initial_points:
        added = False
        for du, dv in offsets:
            trial = ((base_u + du) % 1.0, (base_v + dv) % 1.0)
            if not is_new_point(trial, points):
                continue
            energy = compute_adsorption_energy(trial, retries=CONFIG.retries)
            if energy is None:
                continue
            points.append(trial)
            energies.append(float(energy))
            print(f"Initial label: u={trial[0]:.6f}, v={trial[1]:.6f} -> E_ads={energy:.8f} eV")
            added = True
            break
        if not added:
            raise RuntimeError(f"Could not create initial label near u={base_u:.6f}, v={base_v:.6f}")

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
    """Minimize this: predicted adsorption energy minus exploration bonus."""
    return mean - CONFIG.kappa * std


def propose_inverse_candidate(model: GPModel) -> tuple[tuple[float, float], float, float, float]:
    """Find the 2D LCB minimum via Differential Evolution — no grid required.

    Searches fractional (u, v) ∈ [0, 1)² continuously. No grid needed.
    Scales to any number of surface coordinates.
    """
    bounds = [(0.0, 1.0), (0.0, 1.0)]

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
    best_point = (float(best_x[0]) % 1.0, float(best_x[1]) % 1.0)
    mean_at, std_at = model.predict([best_point])
    # Coarse grid for predicted_improvement reporting only
    u_coarse = np.linspace(0.0, 1.0, CONFIG.n_u_candidates, endpoint=False)
    v_coarse = np.linspace(0.0, 1.0, CONFIG.n_v_candidates, endpoint=False)
    uu, vv = np.meshgrid(u_coarse, v_coarse)
    coarse_pts = np.column_stack([uu.ravel(), vv.ravel()])
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


def plot_adsorption_surface(
    model: GPModel,
    candidate_points: np.ndarray,
    labeled_points: list[tuple[float, float]],
    labeled_energies: list[float],
) -> Path:
    mean, _ = model.predict(candidate_points)
    best_point, _ = best_observed(labeled_points, labeled_energies)

    u_values = np.unique(candidate_points[:, 0])
    v_values = np.unique(candidate_points[:, 1])
    energy_grid = mean.reshape(len(u_values), len(v_values)).T

    fig, ax = plt.subplots(figsize=(8, 6.5))
    contour = ax.contourf(u_values, v_values, energy_grid, levels=30, cmap="viridis")
    fig.colorbar(contour, ax=ax, label="GP predicted E_ads (eV)")
    labeled = np.asarray(labeled_points)
    ax.scatter(labeled[:, 0], labeled[:, 1], c="white", edgecolor="black", s=52, label="QE labels")
    ax.scatter([best_point[0]], [best_point[1]], c="red", marker="*", s=180, label="Best observed")
    for label, point in {
        "top": (0.0, 0.0),
        "bridge": (0.5, 0.0),
        "fcc/hcp hollow A": (1.0 / 3.0, 1.0 / 3.0),
        "fcc/hcp hollow B": (2.0 / 3.0, 2.0 / 3.0),
    }.items():
        ax.scatter([point[0]], [point[1]], marker="x", s=70, color="cyan")
        ax.text(point[0], point[1], f" {label}", color="cyan", fontsize=8)
    ax.set_xlabel("surface fractional u")
    ax.set_ylabel("surface fractional v")
    ax.set_title("H/Cu(111) 2D QE Active Learning + Adsorption Minimization")
    ax.legend()
    fig.tight_layout()

    path = PLOT_DIR / "h_cu111_qe_adsorption_surface.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def plot_convergence(history: dict[str, list[float]]) -> Path:
    fig, (ax_e, ax_n) = plt.subplots(1, 2, figsize=(12, 4.5))
    ax_e.plot(history["iteration"], history["best_energy"], marker="o", color="tab:orange")
    ax_e.set_xlabel("Iteration")
    ax_e.set_ylabel("Best observed E_ads (eV)")
    ax_e.set_title("Adsorption-energy minimization")
    ax_e.grid(alpha=0.25)

    ax_n.plot(history["iteration"], history["n_qe"], marker="s", color="tab:purple")
    ax_n.set_xlabel("Iteration")
    ax_n.set_ylabel("Successful QE adsorption labels")
    ax_n.set_title("QE evaluation count")
    ax_n.grid(alpha=0.25)

    fig.tight_layout()
    path = PLOT_DIR / "h_cu111_qe_convergence.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def write_report(lines: list[str]) -> Path:
    REPORT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return REPORT_FILE


def main() -> None:
    ensure_qe_environment()
    candidate_points = make_candidate_grid()
    test_slab = build_clean_slab()
    test_ads = add_h_to_slab(test_slab, 1.0 / 3.0, 1.0 / 3.0)

    report: list[str] = []
    header = [
        "=" * 92,
        "H/Cu(111) 2D active learning + inverse adsorption minimization using QE via ASE",
        f"Slab atoms: {len(test_slab)} Cu; adsorbed system atoms: {len(test_ads)}",
        f"Cu lattice constant: {CONFIG.lattice_constant_cu:.3f} A",
        f"Surface cell replication: {CONFIG.slab_size}; layers: {CONFIG.layers}; vacuum: {CONFIG.vacuum:.1f} A",
        f"Bottom fixed Cu atoms: {bottom_layer_indices(test_slab)}",
        f"Candidate grid: {CONFIG.n_u_candidates} x {CONFIG.n_v_candidates} fractional points",
        f"Initial points: {list(CONFIG.initial_points)}",
        f"QE command base: {QE_COMMAND}",
        f"Pseudo dir: {PSEUDO_DIR_ABS}",
        f"Pseudopotentials: {PSEUDOPOTENTIALS}",
        f"ecutwfc / ecutrho: {ECUTWFC_RY:.1f} / {ECUTRHO_RY:.1f} Ry",
        f"kpts slab / atom: {KPTS_SLAB} / {KPTS_ATOM}",
        f"Relax clean slab: {CONFIG.relax_clean_slab}; relax adsorbed slab: {CONFIG.relax_adsorbed_slab}",
        f"Relax fmax / steps: {CONFIG.relax_fmax:.3f} eV/A / {CONFIG.relax_steps}",
        "=" * 92,
    ]
    print("\n".join(header))
    report.extend(header)

    slab_energy = get_clean_slab_energy(retries=CONFIG.retries)
    h_energy = get_h_atom_energy(retries=CONFIG.retries)
    refs = [
        f"Clean Cu slab energy: {slab_energy:.8f} eV",
        f"Isolated H atom energy: {h_energy:.8f} eV",
    ]
    print("\n".join(refs))
    report.extend(refs)

    labeled_points, labeled_energies = build_initial_training_set()
    model = GPModel()
    model.train(labeled_points, labeled_energies)

    history: dict[str, list[float]] = {
        "iteration": [],
        "best_u": [],
        "best_v": [],
        "best_energy": [],
        "best_uncertainty": [],
        "predicted_min_u": [],
        "predicted_min_v": [],
        "predicted_min_energy": [],
        "n_qe": [],
    }

    for iteration in range(1, CONFIG.max_iterations + 1):
        print(f"\nIteration {iteration}")
        report.append(f"\nIteration {iteration}")

        al_points = active_learning_query(model, candidate_points, labeled_points)
        if al_points:
            msg = f"  Active labels requested: {[(round(u, 6), round(v, 6)) for u, v in al_points]}"
            print(msg)
            report.append(msg)
            al_pairs = evaluate_new_points(al_points, parallel=True)
            added = add_successful_labels(al_pairs, labeled_points, labeled_energies)
            for (u, v), energy in added:
                msg = f"    Added AL label: u={u:.6f}, v={v:.6f} -> E_ads={energy:.8f} eV"
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
            f"  Inverse adsorption proposal: u={proposal[0]:.6f}, v={proposal[1]:.6f}, "
            f"GP E_ads={pred_mean:.8f} +/- {pred_std:.8f} eV, "
            f"predicted improvement proxy={pred_improvement:.8f} eV"
        )
        print(msg)
        report.append(msg)

        if is_new_point(proposal, labeled_points):
            energy = compute_adsorption_energy(proposal, retries=CONFIG.retries)
            if energy is not None:
                labeled_points.append(proposal)
                labeled_energies.append(float(energy))
                model.train(labeled_points, labeled_energies)
                msg = f"    Added inverse label: u={proposal[0]:.6f}, v={proposal[1]:.6f} -> E_ads={energy:.8f} eV"
                print(msg)
                report.append(msg)
            else:
                msg = f"    Inverse proposal skipped after QE failure: u={proposal[0]:.6f}, v={proposal[1]:.6f}"
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
        history["best_u"].append(best_point[0])
        history["best_v"].append(best_point[1])
        history["best_energy"].append(best_e)
        history["best_uncertainty"].append(best_std)
        history["predicted_min_u"].append(pred_min_point[0])
        history["predicted_min_v"].append(pred_min_point[1])
        history["predicted_min_energy"].append(pred_min_e)
        history["n_qe"].append(len(labeled_points))

        msg = (
            f"  Best observed: u={best_point[0]:.6f}, v={best_point[1]:.6f}, "
            f"E_ads={best_e:.8f} eV, GP std={best_std:.8f} eV, "
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
    surface_plot = plot_adsorption_surface(model, candidate_points, labeled_points, labeled_energies)
    convergence_plot = plot_convergence(history)

    final_lines = [
        "",
        "=" * 92,
        "Final result",
        f"Best surface coordinate u: {best_point[0]:.6f}",
        f"Best surface coordinate v: {best_point[1]:.6f}",
        f"Best QE adsorption energy: {best_e:.8f} eV",
        f"GP uncertainty at best site: {best_std:.8f} eV",
        f"Successful QE adsorption labels: {len(labeled_points)}",
        f"Adsorption surface plot: {surface_plot}",
        f"Convergence plot: {convergence_plot}",
        f"Cache file: {CACHE_FILE}",
    ]
    print("\n".join(final_lines))
    report.extend(final_lines)
    report_path = write_report(report)
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()
