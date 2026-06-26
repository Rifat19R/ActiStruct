"""
qe_active_inverse_common.py
============================
Shared engine for the ActiStruct 50-workflow benchmark.

Implements:
  - Variable / ActiveSystem dataclasses (the public API)
  - Full active learning + inverse design loop (run_system)
  - GP surrogate model (sklearn)
  - DE-based acquisition — Fix 2, no grid blowup (scipy.optimize)
  - Caching with file locks (safe for parallel runs)
  - 1D and 2D parameter spaces
  - Optional reference-energy subtraction when a workflow explicitly defines references
  - QE calculator via ASE with scratch output on a local Linux filesystem
  - Plots and text report per system

Usage in a wrapper file
-----------------------
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

    from qe_active_inverse_common import ActiveSystem, Variable, run_system
    from ase import Atoms
    from ase.build import bulk

    def build_al(a: float) -> Atoms:
        return bulk("Al", "fcc", a=a) * (1, 1, 1)   # 4-atom conventional cell

    SYSTEM = ActiveSystem(
        key="bulk_al",
        title="FCC Aluminium",
        builder=build_al,
        variables=(Variable("a", 3.90, 4.20, (3.94, 4.04, 4.15)),),
        pseudopotentials={"Al": "Al.pbe-n-rrkjus_psl.1.0.0.UPF"},
        ecutwfc=30.0,
        ecutrho=240.0,
        kpts=(8, 8, 8),
        smearing="mv",
        degauss=0.02,
        energy_per_atom=True,
        category="FCC metal",
    )

    if __name__ == "__main__":
        run_system(SYSTEM)

Rules for wrapper authors
--------------------------
1.  builder must be a MODULE-LEVEL function (not a lambda/closure).
    Child processes must be able to pickle it.
2.  All pseudopotentials must be the same type (all US or all PAW).
3.  For a true referenced adsorption/binding energy, supply reference_builders.
    Each takes no arguments and returns an Atoms object.
    target = E(system) - sum(E(ref) for ref in reference_builders).
    Without reference_builders, surface systems report structure-search objective energy.
4.  Set energy_per_atom=False for molecule and surface objective energies.
5.  N_PROCS and PARALLEL_WORKERS at the top of this file control parallelism.
    N_PROCS * PARALLEL_WORKERS must not exceed your CPU core count (nproc).
"""

from __future__ import annotations

import os
import pickle
import shutil
import time
import traceback
import warnings
from dataclasses import dataclass, field
from multiprocessing import Pool
from pathlib import Path
from typing import Callable

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from ase import Atoms
from ase.calculators.espresso import Espresso
from scipy.optimize import differential_evolution
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, RBF, WhiteKernel

try:
    from ase.calculators.espresso import EspressoProfile
except ImportError:
    EspressoProfile = None

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=RuntimeWarning)


# ── Global paths and MPI settings ─────────────────────────────────────────────
# Change N_PROCS * PARALLEL_WORKERS to match your core count (run `nproc`).
# e.g. for 4 cores: N_PROCS=2, PARALLEL_WORKERS=2
#      for 2 cores: N_PROCS=2, PARALLEL_WORKERS=1
N_PROCS          = 2
PARALLEL_WORKERS = 2

PSEUDO_DIR = os.environ.get("ESPRESSO_PSEUDO", "")

# qe_active_inverse_common.py lives in the project root.
ROOT = Path(__file__).resolve().parent

_PW_X_CANDIDATES = [
    os.environ.get("ESPRESSO_PW"),
    shutil.which("pw.x"),
]
PW_X = next(
    (str(Path(path)) for path in _PW_X_CANDIDATES if path and Path(path).exists()),
    "pw.x",
)
QE_COMMAND = os.environ.get("ESPRESSO_COMMAND", f"mpirun -np {N_PROCS} {PW_X}")
QE_CONV_THR = 5e-9
QE_MIXING_BETA = 0.3
MIN_INTERATOMIC_DISTANCE_A = 0.25


# ═══════════════════════════════════════════════════════════════════════════════
# Public dataclasses — the only API wrapper files need to know
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Variable:
    """One design variable for the optimisation.

    Parameters
    ----------
    name    : short label used in plots/reports (e.g. "a", "height", "u")
    lo      : minimum value (Å or degrees)
    hi      : maximum value
    initial : 3-6 starting values spread across [lo, hi]
              For 2D systems both variables must have the same number of
              initial values; they are paired element-wise.
    """
    name:    str
    lo:      float
    hi:      float
    initial: tuple[float, ...]


@dataclass
class ActiveSystem:
    """Complete specification of one material optimisation problem.

    Required
    --------
    key             : unique string id — used in filenames and cache keys
    title           : human-readable title for plots/reports
    builder         : MODULE-LEVEL callable (*params) -> Atoms
                      1D: builder(x)   2D: builder(x, y)
    variables       : tuple of 1 or 2 Variable objects
    pseudopotentials: {element: filename} — all must be same type (PAW or US)
    ecutwfc         : plane-wave cutoff in Ry
    ecutrho         : charge-density cutoff in Ry  (8× ecutwfc for US/PAW)
    kpts            : (k1, k2, k3) Monkhorst-Pack grid

    Optional QE settings
    --------------------
    smearing        : 'mv' for metals, 'gaussian' for insulators/molecules
    degauss         : smearing width in Ry (0.02 metals, 0.01 insulators)
    spin_polarized  : add nspin=2 to QE input (for Fe, Ni, Co, Mn)
    relax           : run BFGS relaxation instead of single SCF
    relax_fmax      : force convergence threshold in eV/Å
    relax_steps     : max BFGS steps

    Adsorption energy
    -----------------
    reference_builders : tuple of no-argument MODULE-LEVEL callables,
                         each returning an Atoms object.
                         target = E(system) - Σ E(reference_i)
                         Example: (build_clean_slab, build_isolated_co)

    Energy normalisation
    --------------------
    energy_per_atom : True  → divide total energy by number of atoms (bulk/2D)
                      False → use raw energy difference (adsorption, molecules)

    Active learning / inverse design
    ---------------------------------
    n_candidates    : candidate grid points (per dimension)
    max_iterations  : hard limit on AL+ID iterations
    uncertainty_threshold       : GP std above which a point is queried (eV)
    active_labels_per_iter      : how many uncertain points to label per iter
    kappa           : exploration weight in LCB (higher = more exploration)
    convergence_uncertainty     : stop when GP std at best point < this (eV)
    convergence_predicted_improvement : stop when DE finds no gain > this (eV)
    retries         : QE retry attempts on failure
    retry_wait_seconds : sleep between retries
    random_state    : seed for GP and DE (set uniquely per system)
    category        : string label for the report (e.g. "FCC metal")
    notes           : any free-text notes written to the report
    """
    # Required
    key:              str
    title:            str
    builder:          Callable
    variables:        tuple[Variable, ...]
    pseudopotentials: dict[str, str]
    ecutwfc:          float
    ecutrho:          float
    kpts:             tuple[int, int, int]

    # QE settings
    smearing:         str   = "gaussian"
    degauss:          float = 0.01
    spin_polarized:   bool  = False
    relax:            bool  = False
    relax_fmax:       float = 0.05
    relax_steps:      int   = 50

    # Adsorption reference calculations
    reference_builders: tuple[Callable, ...] = field(default_factory=tuple)

    # Energy normalisation
    energy_per_atom:  bool  = True

    # Active learning / inverse design
    n_candidates:     int   = 61
    max_iterations:   int   = 12
    uncertainty_threshold:           float = 0.03
    active_labels_per_iter:          int   = 2
    kappa:            float = 1.0
    convergence_uncertainty:         float = 0.03
    convergence_predicted_improvement: float = 0.001
    retries:          int   = 2
    retry_wait_seconds: int = 5
    random_state:     int   = 42
    category:         str   = ""
    notes:            str   = ""

    # Result metadata printed in reports/final output.
    result_quantity:          str = "Computed target energy"
    result_units:             str = "eV"


# ═══════════════════════════════════════════════════════════════════════════════
# Internal helpers — file paths
# ═══════════════════════════════════════════════════════════════════════════════

def _paths(system: ActiveSystem) -> dict[str, Path]:
    """Create output directories and return a dict of useful paths."""
    cache_dir = ROOT / "outputs" / "cache"
    cache = cache_dir / f"{system.key}_cache.pkl"
    lock = cache_dir / f"{system.key}_cache.lock"
    qedir = ROOT / "outputs" / f"qe_runs_{system.key}"
    plots = ROOT / "outputs" / "plots"
    rpts = ROOT / "outputs" / "reports"
    for p in (cache_dir, qedir, plots, rpts):
        p.mkdir(parents=True, exist_ok=True)
    return dict(cache=cache, lock=lock, qedir=qedir, plots=plots, reports=rpts)


# ═══════════════════════════════════════════════════════════════════════════════
# Internal helpers — cache (file-locked pickle)
# ═══════════════════════════════════════════════════════════════════════════════

def _acquire_lock(lock_path: Path, timeout: float = 600.0, poll: float = 0.1) -> int:
    start = time.time()
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_RDWR)
            os.write(fd, str(os.getpid()).encode())
            return fd
        except FileExistsError:
            if time.time() - start > timeout:
                raise TimeoutError(f"Cache lock timeout: {lock_path}")
            time.sleep(poll)


def _release_lock(fd: int, lock_path: Path) -> None:
    try:
        os.close(fd)
    finally:
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def _load_cache(cache_path: Path) -> dict:
    if not cache_path.exists():
        return {}
    with cache_path.open("rb") as f:
        return pickle.load(f)


def _save_cache(cache_path: Path, data: dict) -> None:
    tmp = cache_path.with_suffix(".tmp")
    with tmp.open("wb") as f:
        pickle.dump(data, f)
    os.replace(tmp, cache_path)


def _get_cached(cache_path: Path, lock_path: Path, key: str) -> float | None:
    fd = _acquire_lock(lock_path)
    try:
        return _load_cache(cache_path).get(key)
    finally:
        _release_lock(fd, lock_path)


def _set_cached(cache_path: Path, lock_path: Path, key: str, value: float) -> None:
    fd = _acquire_lock(lock_path)
    try:
        data = _load_cache(cache_path)
        data[key] = float(value)
        _save_cache(cache_path, data)
    finally:
        _release_lock(fd, lock_path)


def _cache_key(system: ActiveSystem, params: tuple[float, ...], label: str = "e") -> str:
    param_str = ":".join(f"{v.name}={p:.6f}" for v, p in zip(system.variables, params))
    pseudo_str = str(sorted(system.pseudopotentials.items()))
    return (
        f"{system.key}:{label}:{param_str}"
        f":ps={pseudo_str}"
        f":ec={system.ecutwfc}-{system.ecutrho}"
        f":kp={system.kpts}:sm={system.smearing}:dg={system.degauss}"
        f":conv={QE_CONV_THR}:mix={QE_MIXING_BETA}:sp={system.spin_polarized}"
    )


def _ref_cache_key(system: ActiveSystem, ref_idx: int) -> str:
    pseudo_str = str(sorted(system.pseudopotentials.items()))
    return (
        f"{system.key}:ref{ref_idx}"
        f":ps={pseudo_str}"
        f":ec={system.ecutwfc}-{system.ecutrho}"
        f":kp={system.kpts}:sm={system.smearing}:dg={system.degauss}"
        f":conv={QE_CONV_THR}:mix={QE_MIXING_BETA}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Internal helpers — QE calculator
# ═══════════════════════════════════════════════════════════════════════════════

def _qe_input_data(system: ActiveSystem, prefix: str) -> dict:
    # Keep QE scratch on a local Linux filesystem; network/translated filesystems can break QE locking.
    safe_key    = system.key[:12].replace("-", "_")
    safe_prefix = prefix[:12].replace("-", "_")
    outdir = f"/tmp/qe_{safe_key}_{safe_prefix}_{os.getpid()}"

    data: dict = {
        "control": {
            "calculation": "scf",
            "prefix":      prefix[:40],   # QE prefix length limit ~80 chars
            "outdir":      outdir,
            "pseudo_dir":  PSEUDO_DIR,
            "verbosity":   "high",
            "tprnfor":     True,
            "tstress":     True,
        },
        "system": {
            "ecutwfc":     system.ecutwfc,
            "ecutrho":     system.ecutrho,
            "occupations": "smearing",
            "smearing":    system.smearing,
            "degauss":     system.degauss,
        },
        "electrons": {
            "conv_thr":          QE_CONV_THR,
            "electron_maxstep":  200,
            "mixing_beta":       QE_MIXING_BETA,
        },
    }
    if system.spin_polarized:
        data["system"]["nspin"] = 2
        for idx, _element in enumerate(system.pseudopotentials, start=1):
            data["system"][f"starting_magnetization({idx})"] = 0.5
    return data


def _build_calculator(system: ActiveSystem, directory: Path, prefix: str) -> Espresso:
    directory.mkdir(parents=True, exist_ok=True)
    kwargs: dict = dict(
        pseudopotentials=system.pseudopotentials,
        input_data=_qe_input_data(system, prefix),
        kpts=system.kpts,
        directory=str(directory),
    )
    if EspressoProfile is not None:
        profile = EspressoProfile(command=QE_COMMAND, pseudo_dir=PSEUDO_DIR)
        return Espresso(profile=profile, **kwargs)
    return Espresso(command=f"{QE_COMMAND} -in PREFIX.pwi > PREFIX.pwo", **kwargs)


# ═══════════════════════════════════════════════════════════════════════════════
# Internal helpers — geometry validation
# ═══════════════════════════════════════════════════════════════════════════════

def _validate_no_atomic_overlap(
    atoms: Atoms,
    min_distance: float = MIN_INTERATOMIC_DISTANCE_A,
) -> None:
    """Reject exact or near-exact atomic overlaps before launching QE.

    This is intentionally conservative. It catches pathological duplicate
    positions while allowing chemically short bonds such as H2.
    """
    if len(atoms) < 2:
        return
    distances = atoms.get_all_distances(mic=True)
    np.fill_diagonal(distances, np.inf)
    min_seen = float(np.min(distances))
    if min_seen < min_distance:
        raise ValueError(
            f"Atomic overlap detected before QE: minimum interatomic distance "
            f"{min_seen:.4f} Å is below {min_distance:.4f} Å."
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Internal helpers — single QE run
# ═══════════════════════════════════════════════════════════════════════════════

def _run_one_qe(
    system:   ActiveSystem,
    atoms:    Atoms,
    work_dir: Path,
    prefix:   str,
    retries:  int,
) -> float | None:
    """Run QE (SCF or relaxation) and return total energy in eV. None = failure."""
    last_err = None
    for attempt in range(1, retries + 2):
        run_dir = work_dir.parent / f"{work_dir.name}_att{attempt}"
        try:
            calc   = _build_calculator(system, run_dir, prefix)
            local  = atoms.copy()
            local.calc = calc
            if system.relax:
                from ase.optimize import BFGS
                opt = BFGS(local, logfile=str(run_dir / "bfgs.log"))
                opt.run(fmax=system.relax_fmax, steps=system.relax_steps)
            energy = float(local.get_potential_energy())
            return energy
        except Exception as exc:
            last_err = exc
            print(f"    WARNING QE attempt {attempt}/{retries + 1}: {exc}")
            if attempt <= retries:
                time.sleep(system.retry_wait_seconds)
    print(f"    WARNING: skipping after all QE attempts failed: {last_err}")
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# Internal helpers — reference energies (adsorption)
# ═══════════════════════════════════════════════════════════════════════════════

def _get_reference_energies(
    system: ActiveSystem,
    paths:  dict,
) -> list[float]:
    """Run QE once per reference builder, cache, return list of energies."""
    ref_energies: list[float] = []
    for i, ref_fn in enumerate(system.reference_builders):
        key    = _ref_cache_key(system, i)
        cached = _get_cached(paths["cache"], paths["lock"], key)
        if cached is not None:
            print(f"  Reference {i} (cached): {cached:.8f} eV")
            ref_energies.append(cached)
            continue
        atoms   = ref_fn()
        _validate_no_atomic_overlap(atoms)
        prefix  = f"ref{i}"
        workdir = paths["qedir"] / f"reference_{i}_pid{os.getpid()}"
        energy  = _run_one_qe(system, atoms, workdir, prefix, system.retries)
        if energy is None:
            raise RuntimeError(
                f"Reference calculation {i} failed for {system.title}. "
                f"Cannot compute referenced objective energy without it."
            )
        _set_cached(paths["cache"], paths["lock"], key, energy)
        print(f"  Reference {i}: {energy:.8f} eV")
        ref_energies.append(energy)
    return ref_energies


# ═══════════════════════════════════════════════════════════════════════════════
# Internal helpers — energy computation for one point
# ═══════════════════════════════════════════════════════════════════════════════

def _compute_energy(
    system:      ActiveSystem,
    params:      tuple[float, ...],
    ref_energies: list[float],
    paths:       dict,
) -> float | None:
    """Return target energy for params. Checks cache first. None on failure."""
    key    = _cache_key(system, params)
    cached = _get_cached(paths["cache"], paths["lock"], key)
    if cached is not None:
        return cached

    atoms = system.builder(*params)
    try:
        _validate_no_atomic_overlap(atoms)
    except ValueError as exc:
        print(f"    WARNING: invalid geometry skipped before QE: {exc}")
        return None
    tag   = "_".join(
        f"{v.name}{p:.4f}".replace(".", "p").replace("-", "m")
        for v, p in zip(system.variables, params)
    )
    prefix   = f"{system.key[:15]}_{tag}"[:40]
    work_dir = paths["qedir"] / f"{tag[:40]}_pid{os.getpid()}"

    total = _run_one_qe(system, atoms, work_dir, prefix, system.retries)
    if total is None:
        return None

    target = total - sum(ref_energies)
    if system.energy_per_atom:
        target /= len(atoms)

    _set_cached(paths["cache"], paths["lock"], key, target)
    return target


# ═══════════════════════════════════════════════════════════════════════════════
# Multiprocessing worker — must be module-level for pickle to work
# ═══════════════════════════════════════════════════════════════════════════════

def _worker(packed: tuple) -> tuple[tuple, float | None]:
    """Module-level worker for Pool.map — receives (system, ref_e, paths, params)."""
    system, ref_energies, paths, params = packed
    return params, _compute_energy(system, params, ref_energies, paths)


def _evaluate_batch(
    system:      ActiveSystem,
    params_list: list[tuple[float, ...]],
    ref_energies: list[float],
    paths:       dict,
    parallel:    bool = True,
) -> list[tuple[tuple, float]]:
    """Evaluate multiple parameter points, in parallel if possible."""
    if not params_list:
        return []
    packed = [(system, ref_energies, paths, p) for p in params_list]
    if parallel and PARALLEL_WORKERS > 1 and len(params_list) > 1:
        n = min(PARALLEL_WORKERS, len(params_list))
        with Pool(processes=n) as pool:
            raw = pool.map(_worker, packed)
    else:
        raw = [_worker(p) for p in packed]
    return [(p, e) for p, e in raw if e is not None]


# ═══════════════════════════════════════════════════════════════════════════════
# GP model
# ═══════════════════════════════════════════════════════════════════════════════

class GPModel:
    """Gaussian-process surrogate: params → (mean energy, uncertainty)."""

    def __init__(self, n_vars: int, random_state: int = 42) -> None:
        ls        = [0.1] * n_vars
        ls_bounds = [(1e-3, 5.0)] * n_vars
        kernel = (
            ConstantKernel(1.0, (1e-3, 1e3))
            * RBF(length_scale=ls, length_scale_bounds=ls_bounds)
            + WhiteKernel(noise_level=1e-5, noise_level_bounds=(1e-9, 1e-2))
        )
        self.gp = GaussianProcessRegressor(
            kernel=kernel,
            normalize_y=True,
            n_restarts_optimizer=8,
            random_state=random_state,
        )

    def train(self, X: list[tuple], y: list[float]) -> None:
        self.gp.fit(
            np.array(X, dtype=float),
            np.array(y, dtype=float),
        )

    def predict(self, X) -> tuple[np.ndarray, np.ndarray]:
        X = np.atleast_2d(np.array(X, dtype=float))
        return self.gp.predict(X, return_std=True)


# ═══════════════════════════════════════════════════════════════════════════════
# Candidate grid (for active learning uncertainty evaluation — NOT for DE)
# ═══════════════════════════════════════════════════════════════════════════════

def _make_candidate_grid(system: ActiveSystem) -> np.ndarray:
    """Return array of shape (n_points, n_vars) for uncertainty evaluation."""
    n = system.n_candidates
    if len(system.variables) == 1:
        v   = system.variables[0]
        pts = np.linspace(v.lo, v.hi, n)
        return pts.reshape(-1, 1)
    v1, v2 = system.variables[0], system.variables[1]
    # Per-dimension size: sqrt(n_candidates), minimum 7
    n2d = max(7, int(np.sqrt(n)))
    g1  = np.linspace(v1.lo, v1.hi, n2d)
    g2  = np.linspace(v2.lo, v2.hi, n2d)
    gg1, gg2 = np.meshgrid(g1, g2)
    return np.column_stack([gg1.ravel(), gg2.ravel()])


# ═══════════════════════════════════════════════════════════════════════════════
# Initial training set
# ═══════════════════════════════════════════════════════════════════════════════

def _make_initial_params(system: ActiveSystem) -> list[tuple[float, ...]]:
    """Build initial parameter tuples from Variable.initial fields."""
    if len(system.variables) == 1:
        return [(float(x),) for x in system.variables[0].initial]
    v1, v2 = system.variables[0], system.variables[1]
    if len(v1.initial) != len(v2.initial):
        raise ValueError(
            f"2D system requires equal-length initial tuples in both Variables. "
            f"Got {len(v1.initial)} and {len(v2.initial)}."
        )
    return [(float(a), float(b)) for a, b in zip(v1.initial, v2.initial)]


def _generate_offsets(
    system: ActiveSystem,
    base:   tuple[float, ...],
) -> list[tuple[float, ...]]:
    """Base point + small ±offsets per dimension (for retry if base fails)."""
    results = [base]
    step = 0.03
    for i, v in enumerate(system.variables):
        for sign in (-1, +1):
            perturbed    = list(base)
            perturbed[i] = float(np.clip(base[i] + sign * step, v.lo, v.hi))
            results.append(tuple(perturbed))  # type: ignore[arg-type]
    return results


def _build_initial_set(
    system:      ActiveSystem,
    ref_energies: list[float],
    paths:       dict,
) -> tuple[list[tuple], list[float]]:
    base_params = _make_initial_params(system)
    labeled_X:  list[tuple]  = []
    labeled_y:  list[float]  = []
    tol = 1e-6

    for base in base_params:
        added  = False
        trials = _generate_offsets(system, base)
        for trial in trials:
            if not _is_new(trial, labeled_X, tol):
                continue
            energy = _compute_energy(system, trial, ref_energies, paths)
            if energy is not None:
                labeled_X.append(trial)
                labeled_y.append(energy)
                print(f"  Initial: {_fmt(system, trial)} -> E = {energy:.8f} eV")
                added = True
                break
        if not added:
            print(f"  WARNING: could not get initial label near {_fmt(system, base)}")

    min_needed = 3 if len(system.variables) == 1 else 5
    if len(labeled_X) < min_needed:
        raise RuntimeError(
            f"Only {len(labeled_X)} successful initial labels (need {min_needed}). "
            f"Check QE setup before retrying."
        )
    return labeled_X, labeled_y


# ═══════════════════════════════════════════════════════════════════════════════
# Duplicate detection
# ═══════════════════════════════════════════════════════════════════════════════

def _is_new(params: tuple, existing: list[tuple], tol: float = 1e-6) -> bool:
    if not existing:
        return True
    arr = np.array(existing, dtype=float)
    p   = np.array(params,   dtype=float)
    return not bool(np.any(np.all(np.isclose(arr, p, atol=tol, rtol=0), axis=1)))


# ═══════════════════════════════════════════════════════════════════════════════
# Active learning
# ═══════════════════════════════════════════════════════════════════════════════

def _active_learning_query(
    model:          GPModel,
    candidate_grid: np.ndarray,
    labeled_X:      list[tuple],
    system:         ActiveSystem,
) -> list[tuple[float, ...]]:
    """Return up to active_labels_per_iter unlabeled candidates with high std."""
    _, std   = model.predict(candidate_grid)
    high_idx = np.where(std > system.uncertainty_threshold)[0]
    if len(high_idx) == 0:
        return []
    ordered  = high_idx[np.argsort(std[high_idx])[::-1]]
    selected: list[tuple[float, ...]] = []
    for idx in ordered:
        pt = tuple(float(x) for x in candidate_grid[idx])
        if _is_new(pt, labeled_X + selected):
            selected.append(pt)
        if len(selected) >= system.active_labels_per_iter:
            break
    return selected


# ═══════════════════════════════════════════════════════════════════════════════
# Inverse design — Fix 2: differential_evolution, no grid blowup
# ═══════════════════════════════════════════════════════════════════════════════

def _propose_inverse(
    model:          GPModel,
    system:         ActiveSystem,
    candidate_grid: np.ndarray,
) -> tuple[tuple[float, ...], float, float, float]:
    """Minimise LCB via DE. Returns (params, mean, std, predicted_improvement)."""
    bounds = [(v.lo, v.hi) for v in system.variables]

    def _lcb(x: np.ndarray) -> float:
        mean, std = model.predict(x.reshape(1, -1))
        return float(mean[0] - system.kappa * std[0])

    result = differential_evolution(
        _lcb, bounds,
        seed=system.random_state, maxiter=500, tol=1e-7,
        polish=True, mutation=(0.5, 1.5), recombination=0.9,
    )
    best_x    = tuple(float(v) for v in result.x)
    mean_at, std_at = model.predict([list(best_x)])
    # predicted_improvement uses coarse grid (for reporting only — not for proposal)
    coarse_mean, _ = model.predict(candidate_grid)
    improvement = float(max(0.0, float(np.min(coarse_mean)) - float(mean_at[0])))
    return best_x, float(mean_at[0]), float(std_at[0]), improvement


# ═══════════════════════════════════════════════════════════════════════════════
# Utility
# ═══════════════════════════════════════════════════════════════════════════════

def _best_observed(labeled_X: list[tuple], labeled_y: list[float]) -> tuple[tuple, float]:
    idx = int(np.argmin(labeled_y))
    return labeled_X[idx], labeled_y[idx]


def _gp_uncertainty_at(model: GPModel, params: tuple) -> float:
    _, std = model.predict([list(params)])
    return float(std[0])


def _fmt(system: ActiveSystem, params: tuple[float, ...]) -> str:
    return "  ".join(f"{v.name}={p:.6f}" for v, p in zip(system.variables, params))


# ═══════════════════════════════════════════════════════════════════════════════
# Plotting
# ═══════════════════════════════════════════════════════════════════════════════

def _plot_results(
    system:         ActiveSystem,
    model:          GPModel,
    candidate_grid: np.ndarray,
    labeled_X:      list[tuple],
    labeled_y:      list[float],
    paths:          dict,
) -> None:
    if len(system.variables) == 1:
        _plot_1d(system, model, candidate_grid, labeled_X, labeled_y, paths)
    else:
        _plot_2d(system, model, candidate_grid, labeled_X, labeled_y, paths)


def _plot_1d(system, model, grid, labeled_X, labeled_y, paths):
    mean, std  = model.predict(grid)
    best_p, _  = _best_observed(labeled_X, labeled_y)
    x          = grid.ravel()

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(x, mean, color="tab:red",  ls="--", lw=2, label="GP mean")
    ax.fill_between(x, mean - std, mean + std, color="tab:red", alpha=0.22, label="GP ±1σ")
    lx = [p[0] for p in labeled_X]
    ax.scatter(lx, labeled_y, s=60, color="tab:blue", zorder=5, label="QE labels")
    ax.axvline(best_p[0], color="tab:green", ls=":", lw=2,
               label=f"Best {system.variables[0].name}={best_p[0]:.4f}")
    ax.set_xlabel(system.variables[0].name)
    ax.set_ylabel(f"{system.result_quantity} ({system.result_units})")
    ax.set_title(f"{system.title} — Active Learning + Inverse Design")
    ax.legend(); ax.grid(alpha=0.25); fig.tight_layout()
    fig.savefig(paths["plots"] / f"{system.key}_energy_curve.png", dpi=180)
    plt.close(fig)


def _plot_2d(system, model, grid, labeled_X, labeled_y, paths):
    mean, _   = model.predict(grid)
    best_p, _ = _best_observed(labeled_X, labeled_y)
    v1, v2    = system.variables[0], system.variables[1]
    n2d       = max(7, int(np.sqrt(system.n_candidates)))
    u_vals    = np.linspace(v1.lo, v1.hi, n2d)
    v_vals    = np.linspace(v2.lo, v2.hi, n2d)
    # mean is ordered as meshgrid(u_vals, v_vals).ravel()
    # → reshape to (n2d, n2d) where row=v index, col=u index
    energy_grid = mean.reshape(n2d, n2d)

    fig, ax = plt.subplots(figsize=(8, 6))
    cf = ax.contourf(u_vals, v_vals, energy_grid, levels=30, cmap="viridis")
    fig.colorbar(cf, ax=ax, label=f"GP predicted {system.result_quantity} ({system.result_units})")
    lx = np.array(labeled_X, dtype=float)
    ax.scatter(lx[:, 0], lx[:, 1], c="white", edgecolor="black", s=52, label="QE labels")
    ax.scatter([best_p[0]], [best_p[1]], c="red", marker="*", s=220,
               label="Best observed", zorder=6)
    ax.set_xlabel(v1.name); ax.set_ylabel(v2.name)
    ax.set_title(f"{system.title} — Active Learning + Inverse Design")
    ax.legend(); fig.tight_layout()
    fig.savefig(paths["plots"] / f"{system.key}_surface.png", dpi=180)
    plt.close(fig)


def _plot_convergence(system: ActiveSystem, history: dict, paths: dict) -> None:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.5))
    iters = history["iteration"]
    ax1.plot(iters, history["best_energy"], marker="o", color="tab:orange")
    ax1.set_xlabel("Iteration"); ax1.set_ylabel(f"Best {system.result_quantity} ({system.result_units})")
    ax1.set_title("Energy convergence"); ax1.grid(alpha=0.25)
    ax2.plot(iters, history["n_qe"], marker="s", color="tab:purple")
    ax2.set_xlabel("Iteration"); ax2.set_ylabel("Total QE evaluations")
    ax2.set_title("Data efficiency"); ax2.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(paths["plots"] / f"{system.key}_convergence.png", dpi=180)
    plt.close(fig)


# ═══════════════════════════════════════════════════════════════════════════════
# Report
# ═══════════════════════════════════════════════════════════════════════════════

def _write_report(system: ActiveSystem, lines: list[str], paths: dict) -> Path:
    rpt = paths["reports"] / f"{system.key}_report.txt"
    rpt.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return rpt


# ═══════════════════════════════════════════════════════════════════════════════
# Public entry point
# ═══════════════════════════════════════════════════════════════════════════════

def run_system(system: ActiveSystem) -> None:
    """Run the full active learning + inverse design loop for one material.

    Call this from `if __name__ == '__main__':` in every wrapper script.
    """
    # ── Validate environment ──────────────────────────────────────────────────
    if not PSEUDO_DIR:
        raise RuntimeError(
            "Set ESPRESSO_PSEUDO to the directory containing required UPF files."
        )
    for elem, pseudo in system.pseudopotentials.items():
        p = Path(PSEUDO_DIR) / pseudo
        if not p.exists():
            raise FileNotFoundError(
                f"Missing {elem} pseudopotential: {p}\n"
                f"Check ESPRESSO_PSEUDO = {PSEUDO_DIR}"
            )

    paths          = _paths(system)
    candidate_grid = _make_candidate_grid(system)

    # ── Header ───────────────────────────────────────────────────────────────
    report: list[str] = []
    header = [
        "=" * 80,
        f"{system.title}",
        f"Key: {system.key}   Category: {system.category}",
        f"Variables: { {v.name: (v.lo, v.hi) for v in system.variables} }",
        "QE command:       configured by ESPRESSO_COMMAND",
        "Pseudo dir:       configured by ESPRESSO_PSEUDO",
        f"Pseudopotentials: {system.pseudopotentials}",
        f"ecutwfc / ecutrho: {system.ecutwfc} / {system.ecutrho} Ry",
        f"kpts: {system.kpts}   smearing: {system.smearing} {system.degauss} Ry",
        f"conv_thr: {QE_CONV_THR}   mixing_beta: {QE_MIXING_BETA}",
        f"spin_polarized: {system.spin_polarized}   relax: {system.relax}",
        f"energy_per_atom: {system.energy_per_atom}",
        f"Computed quantity: {system.result_quantity} ({system.result_units})",
        f"Notes: {system.notes}",
        "=" * 80,
    ]
    print("\n".join(header))
    report.extend(header)

    # ── Reference energies (adsorption systems) ───────────────────────────────
    ref_energies = _get_reference_energies(system, paths)

    # ── Initial training set ──────────────────────────────────────────────────
    labeled_X, labeled_y = _build_initial_set(system, ref_energies, paths)

    model = GPModel(n_vars=len(system.variables), random_state=system.random_state)
    model.train(labeled_X, labeled_y)

    history: dict[str, list] = {
        "iteration":            [],
        "best_energy":          [],
        "best_uncertainty":     [],
        "predicted_improvement":[],
        "n_qe":                 [],
    }

    # ── Main loop ─────────────────────────────────────────────────────────────
    for iteration in range(1, system.max_iterations + 1):
        msg = f"\nIteration {iteration}"
        print(msg); report.append(msg)

        # Active learning step
        al_params = _active_learning_query(model, candidate_grid, labeled_X, system)
        if al_params:
            msg = f"  AL requested: {[_fmt(system, p) for p in al_params]}"
            print(msg); report.append(msg)
            al_results = _evaluate_batch(
                system, al_params, ref_energies, paths, parallel=True
            )
            for params, energy in al_results:
                if _is_new(params, labeled_X):
                    labeled_X.append(params)
                    labeled_y.append(energy)
                    msg = f"    Added AL:  {_fmt(system, params)} -> E={energy:.8f} eV"
                    print(msg); report.append(msg)
            if al_results:
                model.train(labeled_X, labeled_y)
        else:
            msg = "  AL: no points above uncertainty threshold"
            print(msg); report.append(msg)

        # Inverse design step (DE acquisition)
        proposal, pred_mean, pred_std, pred_improvement = _propose_inverse(
            model, system, candidate_grid
        )
        msg = (
            f"  Inverse proposal: {_fmt(system, proposal)}\n"
            f"    GP E={pred_mean:.8f} ± {pred_std:.8f} eV   "
            f"predicted improvement={pred_improvement:.8f} eV"
        )
        print(msg); report.append(msg)

        if _is_new(proposal, labeled_X):
            energy = _compute_energy(system, proposal, ref_energies, paths)
            if energy is not None:
                labeled_X.append(proposal)
                labeled_y.append(energy)
                model.train(labeled_X, labeled_y)
                msg = f"    Added ID:  {_fmt(system, proposal)} -> E={energy:.8f} eV"
                print(msg); report.append(msg)
        else:
            msg = "    Inverse proposal already labeled — skipping DFT"
            print(msg); report.append(msg)

        # Convergence check
        best_p, best_e = _best_observed(labeled_X, labeled_y)
        best_std       = _gp_uncertainty_at(model, best_p)

        history["iteration"].append(iteration)
        history["best_energy"].append(best_e)
        history["best_uncertainty"].append(best_std)
        history["predicted_improvement"].append(pred_improvement)
        history["n_qe"].append(len(labeled_X))

        msg = (
            f"  Best: {_fmt(system, best_p)}  E={best_e:.8f} eV  "
            f"GP std={best_std:.8f} eV  QE labels={len(labeled_X)}"
        )
        print(msg); report.append(msg)

        if (best_std       < system.convergence_uncertainty and
                pred_improvement < system.convergence_predicted_improvement):
            msg = "  ✓ Converged."
            print(msg); report.append(msg)
            break

    # ── Final output ──────────────────────────────────────────────────────────
    best_p, best_e = _best_observed(labeled_X, labeled_y)
    best_std       = _gp_uncertainty_at(model, best_p)

    final = [
        "",
        "=" * 80,
        "FINAL RESULT",
        f"  Best parameters : {_fmt(system, best_p)}",
        f"  Best {system.result_quantity}: {best_e:.8f} {system.result_units}",
        f"  GP uncertainty  : {best_std:.8f} {system.result_units}",
        f"  Total QE calls  : {len(labeled_X)}",
        f"  Cache file      : outputs/cache/{system.key}_cache.pkl",
        "=" * 80,
    ]
    print("\n".join(final))
    report.extend(final)

    _plot_results(system, model, candidate_grid, labeled_X, labeled_y, paths)
    _plot_convergence(system, history, paths)
    rpt = _write_report(system, report, paths)
    print(f"\nReport saved: {rpt}")
