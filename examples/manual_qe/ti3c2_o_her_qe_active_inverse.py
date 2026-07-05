"""
2D active learning + inverse design for H on Ti3C2-O MXene (HER catalyst).

Objective:
    Minimize the Norskov DeltaG_H descriptor:

        DeltaG_H = E_H_on_slab - E_slab - 0.5 * E_H2 + 0.04 eV

    by varying the in-plane fractional coordinates (u, v) of adsorbed H on the
    Ti3C2-O(0001) surface.  BFGS handles z relaxation (H height + top slab layers).

System:
    Ti3C2-O 2x2 supercell (28 atoms) loaded from traj file.
    Bottom O, Ti, C layers are fixed.  Top O, Ti, C layers and H relax.

Pseudopotentials (all SSSP 1.3.0 PBE efficiency):
    Ti: ti_pbe_v1.4.uspp.F.UPF  (USPP)
    C:  C.pbe-n-kjpaw_psl.1.0.0.UPF  (PAW)
    O:  O.pbe-n-kjpaw_psl.0.1.UPF    (PAW)
    H:  H.pbe-rrkjus_psl.1.0.0.UPF   (USPP)
    4-way PAW+USPP combination verified JOB DONE 2026-07-03.

Fidelity:
    LF: ecutwfc=40, ecutrho=320, kpts=(3,3,1)  -- trend-capturing, ~40-60 min each
    HF: ecutwfc=60, ecutrho=480, kpts=(6,6,1)  -- production accuracy

GNN cutoff rationale (5.0 A):
    Ti-C bond ~2.1 A, Ti-O bond ~2.0 A (first shell up to ~2.5 A).
    Second shell ~3.5-4.0 A.  5.0 A provides margin to capture second-shell
    Ti-Ti (~3.1 A) and O-O (~3.1 A) interactions that distinguish hollow vs
    atop sites.  (CaAlN2-era default was 6.0 A for Ca-Al ~3.2 A -- not applicable.)

H2 reference:
    Computed fresh at each fidelity level (LF: ecutwfc=40; HF: ecutwfc=60).
    Cached as separate keys.  nebwalk e_h2.pkl (ecutwfc=60) is compatible with
    HF runs but script computes independently for self-containedness.

Run (low fidelity):
    FIDELITY=low python generated_models/ti3c2_o_her_qe_active_inverse.py

Run (high fidelity):
    FIDELITY=high python generated_models/ti3c2_o_her_qe_active_inverse.py
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import math
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
from ase.constraints import FixAtoms
from ase.io import read as ase_read, write as ase_write
from ase.optimize import BFGS
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, RBF, WhiteKernel
from scipy.optimize import differential_evolution

try:
    from ase.calculators.espresso import EspressoProfile
except ImportError:
    EspressoProfile = None

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=RuntimeWarning)

# -- fidelity selector ---------------------------------------------------------

FIDELITY = os.environ.get("FIDELITY", "low").lower()
if FIDELITY not in ("low", "high"):
    raise ValueError(f"FIDELITY must be 'low' or 'high', got {FIDELITY!r}")

# -- paths ---------------------------------------------------------------------

# parents[2]: script is at <repo>/examples/manual_qe/<file>.py, so parents[1]
# would land on examples/, not the repo root outputs/.gitignore rules target.
ROOT = Path(__file__).resolve().parents[2]

# Overridable so this doesn't hardcode one machine's home/data layout (was
# /mnt/d/Rifat/Research/actistruct_nebwalk/mxenes -- a different user/machine
# path that doesn't exist here). Defaults to an in-repo location built by
# generated_models/structure_builders.py:build_ti3c2o2_slab().
_MXENE_ROOT = Path(os.environ.get("TI3C2_O_STRUCTURES_DIR", str(ROOT / "data" / "structures" / "ti3c2_o")))
_SLAB_RELAXED = _MXENE_ROOT / "ti3c2_o_slab_relaxed.traj"
_SLAB_UNRELAXED = _MXENE_ROOT / "ti3c2_o_slab.traj"

# Use relaxed slab if available (relax job is running); fall back to ASE-built.
SLAB_TRAJ = _SLAB_RELAXED if _SLAB_RELAXED.exists() else _SLAB_UNRELAXED
SLAB_LABEL = "relaxed" if _SLAB_RELAXED.exists() else "unrelaxed"
PLOT_DIR = ROOT / "outputs" / "plots"
REPORT_DIR = ROOT / "outputs" / "reports"
# QE scratch must stay on the native Linux filesystem, never under /mnt/d
# (NTFS silently corrupts QE scratch writes) -- see docs/qe_setup.md.
QE_SCRATCH_ROOT = Path(os.environ.get("QE_SCRATCH_ROOT", "/tmp/qe_scratch"))
QE_RUN_DIR = QE_SCRATCH_ROOT / "ti3c2_o_her" / FIDELITY
CACHE_DIR = ROOT / "outputs" / "cache"
PLOT_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)
QE_RUN_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

CACHE_FILE = CACHE_DIR / f"ti3c2_o_her_{FIDELITY}.pkl"
CACHE_LOCK = CACHE_DIR / f"ti3c2_o_her_{FIDELITY}.lock"
REPORT_FILE = REPORT_DIR / f"ti3c2_o_her_{FIDELITY}_report.txt"

# -- QE parameters -------------------------------------------------------------

PSEUDO_DIR = Path(os.environ.get("ESPRESSO_PSEUDO",
                  "/mnt/d/Rifat/Research/SSSP_1.3.0_PBE_efficiency"))

PSEUDOPOTENTIALS = {
    "Ti": "ti_pbe_v1.4.uspp.F.UPF",         # USPP (SSSP 1.3.0 efficiency)
    "C":  "C.pbe-n-kjpaw_psl.1.0.0.UPF",    # PAW  (SSSP 1.3.0 efficiency)
    "O":  "O.pbe-n-kjpaw_psl.0.1.UPF",      # PAW  (SSSP 1.3.0 efficiency)
    "H":  "H.pbe-rrkjus_psl.1.0.0.UPF",     # USPP (SSSP 1.3.0 efficiency)
    # 4-way PAW+USPP combo verified JOB DONE 2026-07-03
    # (8-atom 1x1 gamma, ecutwfc=40). Each new element combination requires
    # its own verification before campaign use.
}

if FIDELITY == "low":
    ECUTWFC = 40.0
    ECUTRHO = 320.0
    KPTS_SLAB = (3, 3, 1)
else:
    ECUTWFC = 60.0
    ECUTRHO = 480.0
    KPTS_SLAB = (6, 6, 1)

KPTS_H2 = (1, 1, 1)         # isolated H2 in a box, gamma only

# Norskov ZPE-entropy correction for HER (Norskov et al. 2004)
DELTA_ZPE_TS_EV = 0.04      # eV

# QE binary
PW_X = Path(os.environ.get("ESPRESSO_PW", "/home/alchemist/q-e/bin/pw.x"))
N_PROCS = int(os.environ.get("QE_NPROCS", "2"))
QE_COMMAND = f"mpirun -np {N_PROCS} {PW_X}"

RY_TO_EV = 13.605693122994


# -- active learning config ----------------------------------------------------

@dataclass
class Config:
    h_initial_height: float = 1.8           # A above top surface atom
    h2_box: float = 12.0                    # cubic box for isolated H2
    h2_bond: float = 0.74                   # initial H-H bond length (A)
    bottom_layer_tol: float = 0.5           # A tolerance for bottom-layer detection
    n_fixed_layers: int = 3                 # fix bottom N atomic layers

    n_u_candidates: int = 7
    n_v_candidates: int = 7
    initial_points: tuple = (
        (0.00, 0.00),           # atop Ti (top layer center)
        (0.50, 0.00),           # bridge
        (1.0/3.0, 1.0/3.0),    # hollow A
        (2.0/3.0, 2.0/3.0),    # hollow B
        (0.50, 0.50),
    )
    max_iterations: int = 15
    uncertainty_threshold: float = 0.03     # eV
    active_labels_per_iter: int = 2
    kappa: float = 1.0
    convergence_uncertainty: float = 0.03   # eV
    convergence_predicted_improvement: float = 0.003  # eV
    duplicate_tol: float = 1e-6
    cache_round_digits: int = 6
    random_state: int = 42
    retries: int = 2
    retry_wait_seconds: int = 5
    relax_slab: bool = True                 # BFGS H + top slab layers per point
    relax_fmax: float = 0.05               # eV/A BFGS convergence
    relax_steps: int = 50


CONFIG = Config()


# -- slab builder -------------------------------------------------------------

def load_clean_slab() -> Atoms:
    """Load Ti3C2-O slab from traj file and apply bottom-layer constraint."""
    atoms = ase_read(str(SLAB_TRAJ))
    _apply_bottom_constraint(atoms)
    return atoms


def _bottom_layer_indices(atoms: Atoms) -> list[int]:
    """Return atom indices in the bottom N atomic layers by z-position."""
    z = atoms.positions[:, 2]
    z_sorted = np.sort(np.unique(np.round(z, 1)))
    if len(z_sorted) == 0:
        return []
    cutoff_z = float(z_sorted[CONFIG.n_fixed_layers - 1]) + CONFIG.bottom_layer_tol
    return [i for i, zi in enumerate(z) if zi <= cutoff_z]


def _apply_bottom_constraint(atoms: Atoms) -> None:
    """Fix bottom N layers; top layers and adsorbates relax freely."""
    atoms.set_constraint(FixAtoms(indices=_bottom_layer_indices(atoms)))


def fractional_to_cartesian_xy(atoms: Atoms, u: float, v: float) -> np.ndarray:
    """Convert in-plane fractional (u, v) to Cartesian xy."""
    cell = atoms.cell.array
    vec = float(u) * cell[0] + float(v) * cell[1]
    return np.array([vec[0], vec[1]], dtype=float)


def add_h_to_slab(slab: Atoms, u: float, v: float) -> Atoms:
    """Place H at fractional (u, v), CONFIG.h_initial_height above top slab atom."""
    atoms = slab.copy()
    xy = fractional_to_cartesian_xy(atoms, u % 1.0, v % 1.0)
    top_z = float(np.max(atoms.positions[:, 2]))
    z_h = top_z + CONFIG.h_initial_height
    atoms += Atoms("H", positions=[[xy[0], xy[1], z_h]])
    _apply_bottom_constraint(atoms)
    return atoms


def build_h2_molecule() -> Atoms:
    """Isolated H2 in a cubic box (spin-paired, gamma only)."""
    box = CONFIG.h2_box
    center = box / 2.0
    bond = CONFIG.h2_bond
    atoms = Atoms(
        "H2",
        positions=[[center - bond/2.0, center, center],
                   [center + bond/2.0, center, center]],
        cell=[box, box, box],
        pbc=True,
    )
    return atoms


# -- QE calculator factory ----------------------------------------------------

def _qe_input(prefix: str, outdir: str, extra_system: dict | None = None) -> dict:
    sys_block: dict = {
        "ecutwfc":     ECUTWFC,
        "ecutrho":     ECUTRHO,
        "occupations": "smearing",
        "smearing":    "mv",
        "degauss":     0.02,
        "nspin":       1,
    }
    if extra_system:
        sys_block.update(extra_system)
    return {
        "control": {
            "calculation":  "scf",
            "prefix":       prefix,
            "outdir":       outdir,
            "pseudo_dir":   str(PSEUDO_DIR),
            "verbosity":    "high",
            "tprnfor":      True,
            "tstress":      False,
        },
        "system": sys_block,
        "electrons": {
            "conv_thr":         1e-8,
            "electron_maxstep": 300,
            "mixing_beta":      0.2,
            "mixing_mode":      "local-TF",
        },
    }


def get_calculator(
    directory: Path,
    prefix: str,
    kpts: tuple[int, int, int],
    outdir: str | None = None,
    extra_system: dict | None = None,
) -> Espresso:
    directory.mkdir(parents=True, exist_ok=True)
    outdir = outdir or str(QE_SCRATCH_ROOT / "ti3c2_o_her" / FIDELITY / prefix)
    Path(outdir).mkdir(parents=True, exist_ok=True)
    input_data = _qe_input(prefix, outdir, extra_system)
    kwargs = dict(
        pseudopotentials=PSEUDOPOTENTIALS,
        input_data=input_data,
        kpts=kpts,
        directory=str(directory),
    )
    if EspressoProfile is not None:
        profile = EspressoProfile(command=QE_COMMAND, pseudo_dir=str(PSEUDO_DIR))
        return Espresso(profile=profile, **kwargs)
    old_cmd = f"{QE_COMMAND} -in PREFIX.pwi > PREFIX.pwo"
    return Espresso(command=old_cmd, **kwargs)


def parse_qe_total_energy(pwo: Path) -> float | None:
    if not pwo.exists():
        return None
    text = pwo.read_text(errors="ignore")
    matches = re.findall(r"!\s+total energy\s+=\s+([-+0-9.Ee]+)\s+Ry", text)
    return float(matches[-1]) * RY_TO_EV if matches else None


def run_energy(
    atoms: Atoms,
    work_dir: Path,
    prefix: str,
    kpts: tuple[int, int, int],
    relax: bool = False,
    extra_system: dict | None = None,
) -> float:
    """Run static SCF or BFGS relaxation, return total energy in eV."""
    atoms.calc = get_calculator(work_dir, prefix, kpts, extra_system=extra_system)
    if relax:
        opt = BFGS(
            atoms,
            logfile=str(work_dir / "bfgs.log"),
            trajectory=str(work_dir / "bfgs.traj"),
        )
        opt.run(fmax=CONFIG.relax_fmax, steps=CONFIG.relax_steps)
    try:
        return float(atoms.get_potential_energy())
    except Exception:
        parsed = parse_qe_total_energy(work_dir / "espresso.pwo")
        if parsed is None:
            raise
        return parsed


# -- cache helpers -------------------------------------------------------------

def _acquire_lock(timeout: float = 600.0) -> int:
    t0 = time.time()
    while True:
        try:
            fd = os.open(str(CACHE_LOCK), os.O_CREAT | os.O_EXCL | os.O_RDWR)
            os.write(fd, str(os.getpid()).encode("ascii"))
            return fd
        except FileExistsError:
            if time.time() - t0 > timeout:
                raise TimeoutError(f"Cache lock timeout: {CACHE_LOCK}")
            time.sleep(0.1)


def _release_lock(fd: int) -> None:
    try:
        os.close(fd)
    finally:
        try:
            CACHE_LOCK.unlink()
        except FileNotFoundError:
            pass


def _load_cache() -> dict:
    if not CACHE_FILE.exists():
        return {}
    with CACHE_FILE.open("rb") as f:
        return pickle.load(f)


def _save_cache(cache: dict) -> None:
    tmp = CACHE_FILE.with_suffix(".tmp")
    with tmp.open("wb") as f:
        pickle.dump(cache, f)
    os.replace(tmp, CACHE_FILE)


def cache_get(key: str) -> float | None:
    fd = _acquire_lock()
    try:
        return _load_cache().get(key)
    finally:
        _release_lock(fd)


def cache_set(key: str, value: float) -> None:
    fd = _acquire_lock()
    try:
        c = _load_cache()
        c[key] = float(value)
        _save_cache(c)
    finally:
        _release_lock(fd)


# -- energy oracles ------------------------------------------------------------

def _pseudo_str() -> str:
    return ":".join(f"{el}={fn}" for el, fn in sorted(PSEUDOPOTENTIALS.items()))


def get_h2_energy(retries: int = 2) -> float:
    """Compute isolated H2 energy at current fidelity level, cache it."""
    key = (
        f"ti3c2o:h2:pseudo={PSEUDOPOTENTIALS['H']}:"
        f"ecut={ECUTWFC}-{ECUTRHO}:kpts={KPTS_H2}"
    )
    cached = cache_get(key)
    if cached is not None:
        return float(cached)

    last_err = None
    for attempt in range(1, retries + 2):
        wdir = QE_RUN_DIR / f"h2_pid{os.getpid()}_attempt{attempt}"
        try:
            mol = build_h2_molecule()
            # H2 uses H pseudopotential only; suppress Ti/C/O entries
            h2_pseudos = {"H": PSEUDOPOTENTIALS["H"]}
            mol.calc = get_calculator(
                wdir, "h2_ref", KPTS_H2,
                extra_system={"ecutwfc": ECUTWFC, "ecutrho": ECUTRHO},
            )
            mol.calc.parameters["pseudopotentials"] = h2_pseudos
            energy = float(mol.get_potential_energy())
            cache_set(key, energy)
            print(f"H2 energy ({FIDELITY}): {energy:.8f} eV", flush=True)
            return energy
        except Exception as exc:
            last_err = exc
            print(f"WARNING: H2 QE failed attempt {attempt}: {exc}", flush=True)
            if attempt <= retries:
                time.sleep(CONFIG.retry_wait_seconds)

    raise RuntimeError(f"H2 QE failed after {retries + 1} attempts: {last_err}")


def get_clean_slab_energy(retries: int = 2) -> float:
    """Compute clean Ti3C2-O slab energy (static SCF), cache it."""
    key = (
        f"ti3c2o:clean_slab:slab={SLAB_LABEL}:"
        f"pseudo={_pseudo_str()}:ecut={ECUTWFC}-{ECUTRHO}:kpts={KPTS_SLAB}"
    )
    cached = cache_get(key)
    if cached is not None:
        return float(cached)

    last_err = None
    for attempt in range(1, retries + 2):
        wdir = QE_RUN_DIR / f"clean_slab_pid{os.getpid()}_attempt{attempt}"
        try:
            atoms = load_clean_slab()
            energy = run_energy(atoms, wdir, "ti3c2o_clean", KPTS_SLAB)
            cache_set(key, energy)
            print(f"Clean slab energy ({FIDELITY}): {energy:.8f} eV", flush=True)
            return energy
        except Exception as exc:
            last_err = exc
            print(f"WARNING: clean slab QE failed attempt {attempt}: {exc}", flush=True)
            if attempt <= retries:
                time.sleep(CONFIG.retry_wait_seconds)

    raise RuntimeError(f"Clean slab QE failed: {last_err}")


def _point_key(u: float, v: float) -> str:
    return f"u={u:.{CONFIG.cache_round_digits}f}:v={v:.{CONFIG.cache_round_digits}f}"


def compute_delta_g_h(point: tuple[float, float] | np.ndarray, retries: int = 2) -> float | None:
    """Compute DeltaG_H = E_slab+H - E_slab - 0.5*E_H2 + 0.04 eV at (u, v)."""
    u, v = float(np.asarray(point)[0]) % 1.0, float(np.asarray(point)[1]) % 1.0
    key = (
        f"ti3c2o:delta_g_h:{_point_key(u, v)}:slab={SLAB_LABEL}:"
        f"pseudo={_pseudo_str()}:ecut={ECUTWFC}-{ECUTRHO}:kpts={KPTS_SLAB}:"
        f"relax={CONFIG.relax_slab}"
    )
    cached = cache_get(key)
    if cached is not None:
        return float(cached)

    e_slab = get_clean_slab_energy(retries=retries)
    e_h2 = get_h2_energy(retries=retries)

    last_err = None
    for attempt in range(1, retries + 2):
        tag = _point_key(u, v).replace("=", "").replace(":", "_").replace(".", "p")
        wdir = QE_RUN_DIR / f"slab_h_{tag}_pid{os.getpid()}_attempt{attempt}"
        try:
            slab = load_clean_slab()
            atoms = add_h_to_slab(slab, u, v)
            e_ads = run_energy(
                atoms, wdir, f"ti3c2o_h_{tag}", KPTS_SLAB,
                relax=CONFIG.relax_slab,
            )
            delta_g = e_ads - e_slab - 0.5 * e_h2 + DELTA_ZPE_TS_EV
            cache_set(key, delta_g)
            return delta_g
        except Exception as exc:
            last_err = exc
            print(
                f"WARNING: QE failed u={u:.6f}, v={v:.6f} "
                f"attempt {attempt}/{retries + 1}: {exc}",
                flush=True,
            )
            if attempt <= retries:
                time.sleep(CONFIG.retry_wait_seconds)

    print(f"WARNING: skip u={u:.6f}, v={v:.6f} after QE failures: {last_err}", flush=True)
    return None


def evaluate_point(point: tuple[float, float] | np.ndarray) -> tuple[float, float, float | None]:
    u = float(np.asarray(point)[0]) % 1.0
    v = float(np.asarray(point)[1]) % 1.0
    try:
        return u, v, compute_delta_g_h((u, v), retries=CONFIG.retries)
    except Exception:
        print(f"WARNING: unexpected failure at u={u:.6f}, v={v:.6f}", flush=True)
        traceback.print_exc()
        return u, v, None


# -- GP surrogate --------------------------------------------------------------

class GPModel:
    """Gaussian-process surrogate: (u, v) -> DeltaG_H."""

    def __init__(self) -> None:
        kernel = (
            ConstantKernel(1.0, (1e-3, 1e3))
            * RBF(length_scale=[0.20, 0.20], length_scale_bounds=[(1e-3, 2.0)] * 2)
            + WhiteKernel(noise_level=1e-5, noise_level_bounds=(1e-9, 1e-2))
        )
        self.gp = GaussianProcessRegressor(
            kernel=kernel,
            normalize_y=True,
            n_restarts_optimizer=8,
            random_state=CONFIG.random_state,
        )

    def train(self, points: list[tuple[float, float]], values: list[float]) -> None:
        self.gp.fit(np.array(points, dtype=float), np.array(values, dtype=float))

    def predict(self, points) -> tuple[np.ndarray, np.ndarray]:
        x = np.asarray(points, dtype=float)
        if x.ndim == 1:
            x = x.reshape(1, -1)
        return self.gp.predict(x, return_std=True)


# -- active learning helpers ---------------------------------------------------

def make_candidate_grid() -> np.ndarray:
    u = np.linspace(0.0, 1.0, CONFIG.n_u_candidates, endpoint=False)
    v = np.linspace(0.0, 1.0, CONFIG.n_v_candidates, endpoint=False)
    return np.array([(ui, vi) for ui in u for vi in v], dtype=float)


def is_new(point, labeled: list[tuple[float, float]]) -> bool:
    if not labeled:
        return True
    p = np.array(point, dtype=float) % 1.0
    lab = np.array(labeled, dtype=float) % 1.0
    return not np.any(np.all(np.isclose(lab, p, atol=CONFIG.duplicate_tol, rtol=0.0), axis=1))


def active_learning_query(
    model: GPModel, candidates: np.ndarray, labeled: list[tuple[float, float]]
) -> list[tuple[float, float]]:
    _, std = model.predict(candidates)
    high_idx = np.where(std > CONFIG.uncertainty_threshold)[0]
    if len(high_idx) == 0:
        return []
    ordered = high_idx[np.argsort(std[high_idx])[::-1]]
    selected: list[tuple[float, float]] = []
    for idx in ordered:
        p = (float(candidates[idx, 0]), float(candidates[idx, 1]))
        if is_new(p, labeled + selected):
            selected.append(p)
        if len(selected) >= CONFIG.active_labels_per_iter:
            break
    return selected


def propose_inverse(model: GPModel) -> tuple[tuple[float, float], float, float, float]:
    """LCB minimization via Differential Evolution in (u, v) in [0, 1)^2."""

    def _lcb(x: np.ndarray) -> float:
        mean, std = model.predict(x.reshape(1, -1))
        return float(mean[0] - CONFIG.kappa * std[0])

    result = differential_evolution(
        _lcb, [(0.0, 1.0), (0.0, 1.0)],
        seed=CONFIG.random_state, maxiter=500, tol=1e-7,
        polish=True, mutation=(0.5, 1.5), recombination=0.9,
    )
    best = (float(result.x[0]) % 1.0, float(result.x[1]) % 1.0)
    mean_at, std_at = model.predict([best])
    # Report predicted improvement vs coarse grid minimum
    u_c = np.linspace(0.0, 1.0, CONFIG.n_u_candidates, endpoint=False)
    v_c = np.linspace(0.0, 1.0, CONFIG.n_v_candidates, endpoint=False)
    coarse = np.array([(ui, vi) for ui in u_c for vi in v_c])
    coarse_mean, _ = model.predict(coarse)
    pred_imp = max(0.0, float(np.min(coarse_mean)) - float(mean_at[0]))
    return best, float(mean_at[0]), float(std_at[0]), pred_imp


def best_observed(
    points: list[tuple[float, float]], values: list[float]
) -> tuple[tuple[float, float], float]:
    idx = int(np.argmin(np.array(values, dtype=float)))
    return points[idx], float(values[idx])


# -- plotting -----------------------------------------------------------------

def plot_delta_g_surface(
    model: GPModel,
    candidates: np.ndarray,
    labeled: list[tuple[float, float]],
    values: list[float],
) -> Path:
    mean, _ = model.predict(candidates)
    best_pt, _ = best_observed(labeled, values)
    u_vals = np.unique(candidates[:, 0])
    v_vals = np.unique(candidates[:, 1])
    grid = mean.reshape(len(u_vals), len(v_vals)).T

    fig, ax = plt.subplots(figsize=(8, 6.5))
    cf = ax.contourf(u_vals, v_vals, grid, levels=30, cmap="viridis")
    fig.colorbar(cf, ax=ax, label="GP predicted DeltaG_H (eV)")
    lab = np.array(labeled)
    ax.scatter(lab[:, 0], lab[:, 1], c="white", edgecolor="black", s=52, label="QE labels")
    ax.scatter([best_pt[0]], [best_pt[1]], c="red", marker="*", s=180, label="Best observed")
    ax.set_xlabel("fractional u")
    ax.set_ylabel("fractional v")
    ax.set_title(f"Ti3C2-O HER -- DeltaG_H surface ({FIDELITY} fidelity, {SLAB_LABEL} slab)")
    ax.legend()
    fig.tight_layout()
    path = PLOT_DIR / f"ti3c2_o_her_{FIDELITY}_delta_g_surface.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def plot_convergence(history: dict) -> Path:
    fig, (ax_e, ax_n) = plt.subplots(1, 2, figsize=(12, 4.5))
    ax_e.plot(history["iteration"], history["best_delta_g"], marker="o", color="tab:orange")
    ax_e.set_xlabel("Iteration")
    ax_e.set_ylabel("Best DeltaG_H (eV)")
    ax_e.set_title("DeltaG_H minimization (target: |DeltaG_H| near 0)")
    ax_e.grid(alpha=0.25)
    ax_n.plot(history["iteration"], history["n_qe"], marker="s", color="tab:purple")
    ax_n.set_xlabel("Iteration")
    ax_n.set_ylabel("QE labels")
    ax_n.set_title("Oracle evaluation count")
    ax_n.grid(alpha=0.25)
    fig.tight_layout()
    path = PLOT_DIR / f"ti3c2_o_her_{FIDELITY}_convergence.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


# -- sanity checks -------------------------------------------------------------

def ensure_environment() -> None:
    if not PW_X.exists() and shutil.which("pw.x") is None:
        raise RuntimeError(f"pw.x not found: {PW_X}. Set ESPRESSO_PW.")
    if not PSEUDO_DIR.is_dir():
        raise RuntimeError(f"PSEUDO_DIR not found: {PSEUDO_DIR}. Set ESPRESSO_PSEUDO.")
    for el, fn in PSEUDOPOTENTIALS.items():
        p = PSEUDO_DIR / fn
        if not p.exists():
            raise FileNotFoundError(f"Missing {el} pseudopotential: {p}")
    if not SLAB_TRAJ.exists():
        raise FileNotFoundError(
            f"Slab traj not found: {SLAB_TRAJ}. "
            "Build it with examples/manual_qe/build_ti3c2_o_slab.py, or set "
            "TI3C2_O_STRUCTURES_DIR to point at an existing structures dir."
        )


# -- main ----------------------------------------------------------------------

def main() -> None:
    ensure_environment()

    candidates = make_candidate_grid()
    test_slab = load_clean_slab()
    test_ads = add_h_to_slab(test_slab, 1.0/3.0, 1.0/3.0)

    header = [
        "=" * 92,
        f"Ti3C2-O MXene HER -- 2D active learning + inverse DeltaG_H minimization",
        f"Fidelity: {FIDELITY}  |  Slab: {SLAB_LABEL}  |  Slab file: {SLAB_TRAJ}",
        f"Slab atoms: {len(test_slab)}  |  Adsorbed system: {len(test_ads)} atoms",
        f"ecutwfc: {ECUTWFC:.0f} Ry  |  ecutrho: {ECUTRHO:.0f} Ry  |  kpts: {KPTS_SLAB}",
        f"QE command: {QE_COMMAND}",
        f"Pseudo dir: {PSEUDO_DIR}",
        f"Pseudopotentials: {PSEUDOPOTENTIALS}",
        f"DeltaG_H = E_slab+H - E_slab - 0.5*E_H2 + {DELTA_ZPE_TS_EV} eV (Norskov ZPE-entropy)",
        f"GNN encoder cutoff for this system: 5.0 A (Ti-C ~2.1 A, Ti-O ~2.0 A + 2nd shell)",
        f"Candidate grid: {CONFIG.n_u_candidates} x {CONFIG.n_v_candidates}",
        f"Initial points: {[f'({u:.3f},{v:.3f})' for u, v in CONFIG.initial_points]}",
        f"Fixed bottom layers: {CONFIG.n_fixed_layers}",
        f"Relax H+top per point: {CONFIG.relax_slab}  (BFGS fmax={CONFIG.relax_fmax} eV/A)",
        "=" * 92,
    ]
    print("\n".join(header), flush=True)

    labeled_points: list[tuple[float, float]] = []
    labeled_values: list[float] = []

    # Build initial training set from CONFIG.initial_points
    for base_u, base_v in CONFIG.initial_points:
        for du, dv in [(0.0, 0.0), (0.02, 0.0), (-0.02, 0.0), (0.0, 0.02)]:
            trial = ((base_u + du) % 1.0, (base_v + dv) % 1.0)
            if not is_new(trial, labeled_points):
                continue
            dg = compute_delta_g_h(trial, retries=CONFIG.retries)
            if dg is None:
                continue
            labeled_points.append(trial)
            labeled_values.append(dg)
            print(
                f"Initial: u={trial[0]:.6f}, v={trial[1]:.6f} -> DeltaG_H={dg:.6f} eV",
                flush=True,
            )
            break
        else:
            raise RuntimeError(f"Could not compute initial label near u={base_u:.4f}, v={base_v:.4f}")

    if len(labeled_points) < 5:
        raise RuntimeError("Need at least 5 initial labels for GP fitting.")

    model = GPModel()
    model.train(labeled_points, labeled_values)

    history: dict = {
        "iteration": [], "best_u": [], "best_v": [], "best_delta_g": [],
        "best_uncertainty": [], "n_qe": [],
    }

    for iteration in range(1, CONFIG.max_iterations + 1):
        print(f"\n--- Iteration {iteration} ---", flush=True)

        # Active learning: query high-uncertainty points
        al_pts = active_learning_query(model, candidates, labeled_points)
        for p in al_pts:
            u, v = float(p[0]) % 1.0, float(p[1]) % 1.0
            dg = compute_delta_g_h((u, v), retries=CONFIG.retries)
            if dg is None:
                continue
            if is_new((u, v), labeled_points):
                labeled_points.append((u, v))
                labeled_values.append(dg)
                print(f"  AL label: u={u:.6f}, v={v:.6f} -> DeltaG_H={dg:.6f} eV", flush=True)
                model.train(labeled_points, labeled_values)

        # Inverse design: propose via LCB minimization
        proposal, pred_mean, pred_std, pred_imp = propose_inverse(model)
        print(
            f"  Proposal: u={proposal[0]:.6f}, v={proposal[1]:.6f}  "
            f"GP DeltaG_H={pred_mean:.6f}+/-{pred_std:.6f} eV  "
            f"pred_improvement={pred_imp:.6f} eV",
            flush=True,
        )
        if is_new(proposal, labeled_points):
            dg = compute_delta_g_h(proposal, retries=CONFIG.retries)
            if dg is not None:
                labeled_points.append(proposal)
                labeled_values.append(dg)
                model.train(labeled_points, labeled_values)
                print(
                    f"  Added proposal: DeltaG_H={dg:.6f} eV",
                    flush=True,
                )

        best_pt, best_dg = best_observed(labeled_points, labeled_values)
        _, best_std = model.predict([best_pt])
        best_std_val = float(best_std[0])

        history["iteration"].append(iteration)
        history["best_u"].append(best_pt[0])
        history["best_v"].append(best_pt[1])
        history["best_delta_g"].append(best_dg)
        history["best_uncertainty"].append(best_std_val)
        history["n_qe"].append(len(labeled_points))

        print(
            f"  Best: u={best_pt[0]:.6f}, v={best_pt[1]:.6f}  "
            f"DeltaG_H={best_dg:.6f} eV  GP_std={best_std_val:.6f} eV  "
            f"QE_labels={len(labeled_points)}",
            flush=True,
        )
        print(
            f"  |DeltaG_H| = {abs(best_dg):.6f} eV "
            f"(ideal=0; <0.1 eV is close to thermoneutral)",
            flush=True,
        )

        if (best_std_val < CONFIG.convergence_uncertainty
                and pred_imp < CONFIG.convergence_predicted_improvement):
            print("  Converged: low uncertainty, minimal predicted improvement.", flush=True)
            break

    best_pt, best_dg = best_observed(labeled_points, labeled_values)
    surf_plot = plot_delta_g_surface(model, candidates, labeled_points, labeled_values)
    conv_plot = plot_convergence(history)

    final = [
        "",
        "=" * 92,
        f"FINAL RESULT ({FIDELITY} fidelity, {SLAB_LABEL} slab)",
        f"Best fractional u: {best_pt[0]:.6f}",
        f"Best fractional v: {best_pt[1]:.6f}",
        f"Best DeltaG_H: {best_dg:.8f} eV  (|DeltaG_H|={abs(best_dg):.6f} eV)",
        f"QE oracle calls: {len(labeled_points)}",
        f"DeltaG_H surface plot: {surf_plot}",
        f"Convergence plot: {conv_plot}",
        f"Cache: {CACHE_FILE}",
    ]
    print("\n".join(final), flush=True)
    REPORT_FILE.write_text("\n".join(header + ["\n"] + final) + "\n", encoding="utf-8")
    print(f"Report: {REPORT_FILE}", flush=True)


if __name__ == "__main__":
    main()
