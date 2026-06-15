"""
apply_fix2.py
=============
Patches all inverse_active pipeline scripts to replace the grid-based
propose_inverse_candidate() with scipy.optimize.differential_evolution.

Fix 2: Optimize the acquisition function directly — no grid required.
This removes the exponential blowup for 3D+ parameter spaces.

Run from /home/claude/fix2/:
    python apply_fix2.py
"""

import re
from pathlib import Path

WORKDIR = Path(__file__).parent

# ---------------------------------------------------------------------------
# Shared helper: insert scipy import after the sklearn import block
# ---------------------------------------------------------------------------
SCIPY_IMPORT = "from scipy.optimize import differential_evolution"

def insert_scipy_import(src: str) -> str:
    """Add scipy DE import after the last sklearn import line."""
    if SCIPY_IMPORT in src:
        return src  # already patched
    lines = src.splitlines(keepends=True)
    insert_after = -1
    for i, line in enumerate(lines):
        if line.startswith("from sklearn.gaussian_process"):
            insert_after = i
    if insert_after == -1:
        raise ValueError("Could not find sklearn import block")
    lines.insert(insert_after + 1, SCIPY_IMPORT + "\n")
    return "".join(lines)


# ---------------------------------------------------------------------------
# GROUP 1  –  1D LCB scripts (bulk_si, bulk_cu, bulk_mgo, graphene)
#             parameter variable: CONFIG.lattice_min / lattice_max / n_candidates
#             candidate array name in main(): candidate_lattices
# ---------------------------------------------------------------------------
OLD_LCB_LATTICE = '''\
def lower_confidence_bound(mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    """Minimize this: predicted energy minus exploration bonus."""
    return mean - CONFIG.kappa * std


def propose_inverse_candidate(model: GPModel, candidate_lattices: np.ndarray) -> tuple[float, float, float, float]:
    mean, std = model.predict(candidate_lattices)
    lcb = lower_confidence_bound(mean, std)
    idx = int(np.argmin(lcb))
    predicted_best_idx = int(np.argmin(mean))
    predicted_improvement = float(mean[predicted_best_idx] - mean[idx])
    return float(candidate_lattices[idx]), float(mean[idx]), float(std[idx]), predicted_improvement'''

NEW_LCB_LATTICE = '''\
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
    return best_x, float(mean_at[0]), float(std_at[0]), predicted_improvement'''

OLD_CALL_LATTICE = "propose_inverse_candidate(model, candidate_lattices)"
NEW_CALL_LATTICE = "propose_inverse_candidate(model)"


# ---------------------------------------------------------------------------
# GROUP 1b  –  ch4 (1D, r_min/r_max, candidate_bonds)
# ---------------------------------------------------------------------------
OLD_LCB_BONDS = '''\
def lower_confidence_bound(mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    """Minimize this: predicted energy minus exploration bonus."""
    return mean - CONFIG.kappa * std


def propose_inverse_candidate(model: GPModel, candidate_bonds: np.ndarray) -> tuple[float, float, float, float]:
    mean, std = model.predict(candidate_bonds)
    lcb = lower_confidence_bound(mean, std)
    idx = int(np.argmin(lcb))
    predicted_best_idx = int(np.argmin(mean))
    predicted_improvement = float(mean[predicted_best_idx] - mean[idx])
    return float(candidate_bonds[idx]), float(mean[idx]), float(std[idx]), predicted_improvement'''

NEW_LCB_BONDS = '''\
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
    return best_x, float(mean_at[0]), float(std_at[0]), predicted_improvement'''

OLD_CALL_BONDS = "propose_inverse_candidate(model, candidate_bonds)"
NEW_CALL_BONDS = "propose_inverse_candidate(model)"


# ---------------------------------------------------------------------------
# GROUP 2  –  h2o (2D: r × theta)
# ---------------------------------------------------------------------------
OLD_LCB_H2O = '''\
def lower_confidence_bound(mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    """Minimize this: predicted energy minus exploration bonus."""
    return mean - CONFIG.kappa * std


def propose_inverse_candidate(model: GPModel, candidate_points: np.ndarray) -> tuple[tuple[float, float], float, float, float]:
    mean, std = model.predict(candidate_points)
    lcb = lower_confidence_bound(mean, std)
    idx = int(np.argmin(lcb))
    predicted_best_idx = int(np.argmin(mean))
    predicted_improvement = float(mean[predicted_best_idx] - mean[idx])
    point = (float(candidate_points[idx, 0]), float(candidate_points[idx, 1]))
    return point, float(mean[idx]), float(std[idx]), predicted_improvement'''

NEW_LCB_H2O = '''\
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
    return best_point, float(mean_at[0]), float(std_at[0]), predicted_improvement'''

OLD_CALL_H2O = "propose_inverse_candidate(model, candidate_points)"
NEW_CALL_H2O = "propose_inverse_candidate(model)"


# ---------------------------------------------------------------------------
# GROUP 3  –  bulk_licoo2 (2D: a × c)
# ---------------------------------------------------------------------------
OLD_LCB_LICOO2 = '''\
def lower_confidence_bound(mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    """Minimize this: predicted energy per atom minus exploration bonus."""
    return mean - CONFIG.kappa * std


def propose_inverse_candidate(model: GPModel, candidate_points: np.ndarray) -> tuple[tuple[float, float], float, float, float]:
    mean, std = model.predict(candidate_points)
    lcb = lower_confidence_bound(mean, std)
    idx = int(np.argmin(lcb))
    predicted_best_idx = int(np.argmin(mean))
    predicted_improvement = float(mean[predicted_best_idx] - mean[idx])
    point = (float(candidate_points[idx, 0]), float(candidate_points[idx, 1]))
    return point, float(mean[idx]), float(std[idx]), predicted_improvement'''

NEW_LCB_LICOO2 = '''\
def lower_confidence_bound(mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    """Minimize this: predicted energy per atom minus exploration bonus."""
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
    # Coarse grid for predicted_improvement reporting only
    a_coarse = np.linspace(CONFIG.a_min, CONFIG.a_max, CONFIG.n_a_candidates)
    c_coarse = np.linspace(CONFIG.c_min, CONFIG.c_max, CONFIG.n_c_candidates)
    aa, cc = np.meshgrid(a_coarse, c_coarse)
    coarse_pts = np.column_stack([aa.ravel(), cc.ravel()])
    coarse_mean, _ = model.predict(coarse_pts)
    predicted_improvement = float(max(0.0, float(np.min(coarse_mean)) - float(mean_at[0])))
    return best_point, float(mean_at[0]), float(std_at[0]), predicted_improvement'''

OLD_CALL_LICOO2 = "propose_inverse_candidate(model, candidate_points)"
NEW_CALL_LICOO2 = "propose_inverse_candidate(model)"


# ---------------------------------------------------------------------------
# GROUP 4  –  h_cu111 (2D: u × v, fractional [0,1]×[0,1])
# ---------------------------------------------------------------------------
OLD_LCB_CU111 = '''\
def lower_confidence_bound(mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    """Minimize this: predicted adsorption energy minus exploration bonus."""
    return mean - CONFIG.kappa * std


def propose_inverse_candidate(model: GPModel, candidate_points: np.ndarray) -> tuple[tuple[float, float], float, float, float]:
    mean, std = model.predict(candidate_points)
    lcb = lower_confidence_bound(mean, std)
    idx = int(np.argmin(lcb))
    predicted_best_idx = int(np.argmin(mean))
    predicted_improvement = float(mean[predicted_best_idx] - mean[idx])
    point = (float(candidate_points[idx, 0]), float(candidate_points[idx, 1]))
    return point, float(mean[idx]), float(std[idx]), predicted_improvement'''

NEW_LCB_CU111 = '''\
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
    return best_point, float(mean_at[0]), float(std_at[0]), predicted_improvement'''

OLD_CALL_CU111 = "propose_inverse_candidate(model, candidate_points)"
NEW_CALL_CU111 = "propose_inverse_candidate(model)"


# ---------------------------------------------------------------------------
# GROUP 5  –  h2_qe (1D, target-matching, uses argmax of acquisition_score)
# ---------------------------------------------------------------------------
OLD_H2QE_PROPOSE = '''\
def propose_inverse_candidate(model: GPModel, candidate_distances: np.ndarray) -> tuple[float, float, float, float]:
    mean, std = model.predict(candidate_distances)
    score = acquisition_score(mean, std)
    idx = int(np.argmax(score))
    distance = float(candidate_distances[idx])
    return distance, float(mean[idx]), float(std[idx]), float(abs(mean[idx] - CONFIG.target_binding_energy))'''

NEW_H2QE_PROPOSE = '''\
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
    return distance, float(mean_at[0]), float(std_at[0]), float(abs(mean_at[0] - CONFIG.target_binding_energy))'''

OLD_CALL_H2QE = "propose_inverse_candidate(model, candidate_distances)"
NEW_CALL_H2QE = "propose_inverse_candidate(model)"


# ---------------------------------------------------------------------------
# GROUP 6  –  cu2_dimer.py (1D, target-matching, inline in main loop)
#             Uses config (lowercase), not CONFIG
# ---------------------------------------------------------------------------
OLD_CU2_INLINE = '''\
        scores = acquisition_score(mean, std, target_energy, config.kappa)
        proposal_idx = int(np.argmax(scores))
        proposal = float(candidate_distances[proposal_idx])'''

NEW_CU2_INLINE = '''\
        # --- Fix 2: DE-based acquisition optimisation (replaces grid argmax) ---
        def _neg_acq_cu2(x: np.ndarray) -> float:
            m, s = model.predict(x.reshape(1, -1))
            return float(abs(m[0] - target_energy) - config.kappa * s[0])
        _de_result = differential_evolution(
            _neg_acq_cu2,
            [(config.distance_min, config.distance_max)],
            seed=config.random_state,
            maxiter=500, tol=1e-7, polish=True,
            mutation=(0.5, 1.5), recombination=0.9,
        )
        proposal = float(_de_result.x[0])'''

# h2_dimer is structurally identical to cu2_dimer
OLD_H2_INLINE = '''\
        scores = acquisition_score(mean, std, target_energy, config.kappa)
        proposal_idx = int(np.argmax(scores))
        proposal = float(candidate_distances[proposal_idx])'''

NEW_H2_INLINE = '''\
        # --- Fix 2: DE-based acquisition optimisation (replaces grid argmax) ---
        def _neg_acq_h2(x: np.ndarray) -> float:
            m, s = model.predict(x.reshape(1, -1))
            return float(abs(m[0] - target_energy) - config.kappa * s[0])
        _de_result = differential_evolution(
            _neg_acq_h2,
            [(config.distance_min, config.distance_max)],
            seed=config.random_state,
            maxiter=500, tol=1e-7, polish=True,
            mutation=(0.5, 1.5), recombination=0.9,
        )
        proposal = float(_de_result.x[0])'''


# ---------------------------------------------------------------------------
# Apply patches
# ---------------------------------------------------------------------------
PATCHES = [
    # (filename, old_str, new_str, description)
    ("bulk_si_qe_active_inverse.py", OLD_LCB_LATTICE, NEW_LCB_LATTICE, "propose_inverse_candidate"),
    ("bulk_si_qe_active_inverse.py", OLD_CALL_LATTICE, NEW_CALL_LATTICE, "main() call"),
    ("bulk_cu_qe_active_inverse.py", OLD_LCB_LATTICE, NEW_LCB_LATTICE, "propose_inverse_candidate"),
    ("bulk_cu_qe_active_inverse.py", OLD_CALL_LATTICE, NEW_CALL_LATTICE, "main() call"),
    ("bulk_mgo_qe_active_inverse.py", OLD_LCB_LATTICE, NEW_LCB_LATTICE, "propose_inverse_candidate"),
    ("bulk_mgo_qe_active_inverse.py", OLD_CALL_LATTICE, NEW_CALL_LATTICE, "main() call"),
    ("graphene_qe_active_inverse.py", OLD_LCB_LATTICE, NEW_LCB_LATTICE, "propose_inverse_candidate"),
    ("graphene_qe_active_inverse.py", OLD_CALL_LATTICE, NEW_CALL_LATTICE, "main() call"),
    ("ch4_qe_active_inverse.py",      OLD_LCB_BONDS,   NEW_LCB_BONDS,   "propose_inverse_candidate"),
    ("ch4_qe_active_inverse.py",      OLD_CALL_BONDS,  NEW_CALL_BONDS,  "main() call"),
    ("h2o_qe_active_inverse.py",      OLD_LCB_H2O,     NEW_LCB_H2O,     "propose_inverse_candidate"),
    ("h2o_qe_active_inverse.py",      OLD_CALL_H2O,    NEW_CALL_H2O,    "main() call"),
    ("bulk_licoo2_qe_active_inverse.py", OLD_LCB_LICOO2, NEW_LCB_LICOO2, "propose_inverse_candidate"),
    ("bulk_licoo2_qe_active_inverse.py", OLD_CALL_LICOO2, NEW_CALL_LICOO2, "main() call"),
    ("h_cu111_qe_active_inverse.py",  OLD_LCB_CU111,   NEW_LCB_CU111,   "propose_inverse_candidate"),
    ("h_cu111_qe_active_inverse.py",  OLD_CALL_CU111,  NEW_CALL_CU111,  "main() call"),
    ("h2_qe_active_inverse.py",       OLD_H2QE_PROPOSE, NEW_H2QE_PROPOSE, "propose_inverse_candidate"),
    ("h2_qe_active_inverse.py",       OLD_CALL_H2QE,   NEW_CALL_H2QE,   "main() call"),
    ("cu2_dimer.py",                  OLD_CU2_INLINE,  NEW_CU2_INLINE,  "inline acquisition"),
    ("h2_dimer.py",                   OLD_H2_INLINE,   NEW_H2_INLINE,   "inline acquisition"),
]


def apply_all():
    results = {}
    for fname, old, new, desc in PATCHES:
        path = WORKDIR / fname
        src = path.read_text(encoding="utf-8")

        # Insert scipy import once per file
        src = insert_scipy_import(src)

        if old in src:
            src = src.replace(old, new, 1)
            results.setdefault(fname, []).append(f"  ✓  {desc}")
        else:
            results.setdefault(fname, []).append(f"  ✗  FAILED to find: {desc[:60]!r}")

        path.write_text(src, encoding="utf-8")

    print("\n=== Fix 2 patch results ===")
    for fname, msgs in results.items():
        print(f"\n{fname}")
        for m in msgs:
            print(m)


if __name__ == "__main__":
    apply_all()
    print("\nDone. All patched files are in this directory.")
