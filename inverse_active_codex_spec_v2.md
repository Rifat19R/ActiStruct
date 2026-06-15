# inverse_active — Codex Generation Spec v2
## Active Learning + Inverse Design for DFT Optimisation (Quantum ESPRESSO)

> **This file is the authoritative specification for Codex.**
> Read every section before generating any Python script.
> Do not invent parameters — use only what is listed here.

---

## 1. What This Project Is

A closed-loop Python pipeline that finds the optimal geometry of a material
(bond length, lattice constant, adsorption site, etc.) using as few DFT
calculations as possible. It combines:

- **Gaussian Process (GP)** surrogate model — predicts energy and uncertainty.
- **Active learning** — queries the most uncertain structures and labels them with DFT.
- **Inverse design** — proposes the next candidate that minimises the target energy.

**Result:** 5–25 DFT evaluations instead of 50–1000.

---

## 2. Core Loop (Unchanged from v1)

```
1.  Build initial training set (3–6 structures with DFT energies).
2.  Train GP on (geometry → energy).
3.  Active learning: evaluate uncertainty over a coarse candidate grid.
4.  Select K points with highest uncertainty above threshold.
5.  Run DFT on those points, add to training set, retrain GP.
6.  Inverse design: run differential_evolution to minimise LCB = mean − κ·std.
7.  Run DFT on proposed point if new, add to training set, retrain GP.
8.  Check convergence: uncertainty at best point < tol AND predicted gap < tol.
9.  If not converged, go to step 3.
```

---

## 3. KEY CHANGE IN v2 — Fix 2: DE-Based Acquisition

### What changed
`propose_inverse_candidate()` no longer evaluates the acquisition function on a
fixed grid. It now calls `scipy.optimize.differential_evolution` to minimise the
LCB directly in continuous parameter space.

### Why this matters
- Grid approach: O(n^d) evaluations (exponential in d dimensions).
- DE approach: ~500 function evaluations regardless of d.
- Scales to 3D, 4D, or any number of design variables.

### Required import (add to every QE script)
```python
from scipy.optimize import differential_evolution
```

### 1D template for propose_inverse_candidate
```python
def propose_inverse_candidate(model: GPModel) -> tuple[float, float, float, float]:
    """Find LCB minimum via Differential Evolution — no grid required."""
    bounds = [(CONFIG.param_min, CONFIG.param_max)]

    def _lcb(x: np.ndarray) -> float:
        mean, std = model.predict(x.reshape(1, -1))
        return float(mean[0] - CONFIG.kappa * std[0])

    result = differential_evolution(
        _lcb, bounds,
        seed=CONFIG.random_state, maxiter=500, tol=1e-7, polish=True,
        mutation=(0.5, 1.5), recombination=0.9,
    )
    best_x = float(result.x[0])
    mean_at, std_at = model.predict([[best_x]])
    coarse = np.linspace(CONFIG.param_min, CONFIG.param_max, CONFIG.n_candidates)
    coarse_mean, _ = model.predict(coarse)
    predicted_improvement = float(max(0.0, float(np.min(coarse_mean)) - float(mean_at[0])))
    return best_x, float(mean_at[0]), float(std_at[0]), predicted_improvement
```

### 2D template for propose_inverse_candidate
```python
def propose_inverse_candidate(model: GPModel) -> tuple[tuple[float, float], float, float, float]:
    """Find 2D LCB minimum via Differential Evolution — no grid required."""
    bounds = [(CONFIG.param1_min, CONFIG.param1_max), (CONFIG.param2_min, CONFIG.param2_max)]

    def _lcb(x: np.ndarray) -> float:
        mean, std = model.predict(x.reshape(1, -1))
        return float(mean[0] - CONFIG.kappa * std[0])

    result = differential_evolution(
        _lcb, bounds,
        seed=CONFIG.random_state, maxiter=500, tol=1e-7, polish=True,
        mutation=(0.5, 1.5), recombination=0.9,
    )
    best_x = result.x
    best_point = (float(best_x[0]), float(best_x[1]))
    mean_at, std_at = model.predict([best_point])
    # coarse grid for reporting only
    p1 = np.linspace(CONFIG.param1_min, CONFIG.param1_max, CONFIG.n_p1_candidates)
    p2 = np.linspace(CONFIG.param2_min, CONFIG.param2_max, CONFIG.n_p2_candidates)
    g1, g2 = np.meshgrid(p1, p2)
    coarse_pts = np.column_stack([g1.ravel(), g2.ravel()])
    coarse_mean, _ = model.predict(coarse_pts)
    predicted_improvement = float(max(0.0, float(np.min(coarse_mean)) - float(mean_at[0])))
    return best_point, float(mean_at[0]), float(std_at[0]), predicted_improvement
```

### Call site in main() — IMPORTANT
```python
# CORRECT (v2):
proposal, pred_mean, pred_std, pred_improvement = propose_inverse_candidate(model)

# WRONG (v1, do not use):
proposal, pred_mean, pred_std, pred_improvement = propose_inverse_candidate(model, candidate_grid)
```

---

## 4. MPI and Parallelism Rules

This is critical. Wrong settings crash QE or overload the machine.

| System type | `N_PROCS` | `PARALLEL_WORKERS` | Reason |
|---|---|---|---|
| Molecules (H₂, H₂O, CH₄, NH₃, N₂, CO) | **2** | **1** | Γ-point only, tiny FFT grid |
| 2D materials (graphene, BN, MoS₂) | **4** | **1** | Moderate k-grid |
| Bulk crystals (Si, Cu, MgO, Fe, Al...) | **6** | **1** | Large k-grid, benefits from MPI |
| Surface slabs (H/Cu, CO/Ni, O/Ru...) | **6** | **1** | Large cell, large k-grid |
| Battery materials (LiCoO₂, LiFePO₄) | **6** | **1** | Complex structure |

`PARALLEL_WORKERS = 1` always when `N_PROCS = 6`. Total cores = `N_PROCS × PARALLEL_WORKERS`.

---

## 5. Pseudopotential Rules — CRITICAL

### Rule 1: Never mix PAW and Ultrasoft in the same calculation
QE will crash with exit status 1 if you mix types. Every element in one script
must use the same pseudopotential family.

| Family | Identifier in filename | `ecutrho` |
|---|---|---|
| Ultrasoft (US) | `rrkjus`, `uspp` | 8 × ecutwfc |
| PAW | `kjpaw`, `paw` | 4 × ecutwfc (but use 8× to be safe) |

### Rule 2: All elements in one script → same family

**If ANY element only has PAW available → use PAW for all elements.**
**If all elements have US available → use US for all elements.**

### Validated pseudopotential table (SSSP 1.3.0 PBE efficiency)

| Element | Ultrasoft (preferred) | PAW (alternative) | Notes |
|---|---|---|---|
| H | `H.pbe-rrkjus_psl.1.0.0.UPF` | `H.pbe-kjpaw_psl.1.0.0.UPF` | Use US unless forced to PAW |
| C | `C.pbe-n-rrkjus_psl.1.0.0.UPF` | `C.pbe-n-kjpaw_psl.1.0.0.UPF` | Always use US with H |
| N | `N.pbe-n-rrkjus_psl.1.0.0.UPF` | — | US only |
| O | `O.pbe-n-rrkjus_psl.1.0.0.UPF` | `O.pbe-n-kjpaw_psl.0.1.UPF` | Check file exists first |
| Si | `Si.pbe-n-rrkjus_psl.1.0.0.UPF` | — | US only |
| Mg | `Mg.pbe-spnl-rrkjus_psl.1.0.0.UPF` | `Mg.pbe-n-kjpaw_psl.0.3.0.UPF` | |
| Al | `Al.pbe-n-rrkjus_psl.1.0.0.UPF` | — | US only |
| Fe | `Fe.pbe-spn-kjpaw_psl.0.2.1.UPF` | — | PAW only, use spin |
| Ni | `Ni.pbe-spn-kjpaw_psl.0.1.UPF` | — | PAW only, use spin |
| Cu | `Cu.paw.z_11.ld1.psl.v1.0.0-low.upf` | — | PAW, local SSSP efficiency |
| Pt | `Pt.pbe-n-rrkjus_psl.1.0.0.UPF` | — | US |
| Au | `Au.pbe-n-rrkjus_psl.1.0.0.UPF` | — | US |
| Li | `li_pbe_v1.4.uspp.F.UPF` | — | US |
| Co | `Co_pbe_v1.2.uspp.F.UPF` | — | US; add Hubbard U for LiCoO₂ |
| Ti | `Ti.pbe-spn-kjpaw_psl.1.0.0.UPF` | — | PAW |
| Zn | `Zn.pbe-dnl-rrkjus_psl.1.0.0.UPF` | — | US |
| S  | `S.pbe-nl-rrkjus_psl.1.0.0.UPF` | — | US |
| Mo | `Mo_ONCV_PBE-1.0.oncvpsp.upf` | — | NC, check availability |
| W  | `W.pbe-spn-kjpaw_psl.1.0.0.UPF` | — | PAW |
| Ge | `Ge.pbe-dn-rrkjus_psl.1.0.0.UPF` | — | US |
| Ga | `Ga.pbe-dn-rrkjus_psl.1.0.0.UPF` | — | US |
| As | `As.pbe-n-rrkjus_psl.1.0.0.UPF` | — | US |
| In | `In.pbe-dn-rrkjus_psl.1.0.0.UPF` | — | US |
| P  | `P.pbe-n-rrkjus_psl.1.0.0.UPF` | — | US |
| Ca | `Ca.pbe-spn-kjpaw_psl.1.0.0.UPF` | — | PAW |
| Sr | `Sr.pbe-spn-kjpaw_psl.1.0.0.UPF` | — | PAW |
| Ba | `Ba.pbe-spn-kjpaw_psl.1.0.0.UPF` | — | PAW |
| Mn | `Mn.pbe-spn-kjpaw_psl.0.3.1.UPF` | — | PAW, use spin |

> **Before generating a script:** verify the exact filename exists with `ls /mnt/d/Rifat_kh/SSSP_1.3.0_PBE_efficiency/<filename>`.

---

## 6. DFT Parameters by System Type

### Molecules (0D, in a box)
```
box_size    = 10.0 Å  (12.0 Å for large molecules like C₆H₆)
pbc         = True (required by QE, but physically isolated)
kpts        = (1, 1, 1)
ecutwfc     = 50 Ry
ecutrho     = 400 Ry  (8×)
smearing    = 'gaussian', degauss = 0.01
conv_thr    = 1e-8
N_PROCS     = 2
```

### Bulk crystals (3D periodic)
```
kpts        = (8,8,8) for cubic; (8,8,4) for hexagonal; (6,6,6) for large cells
ecutwfc     = 50 Ry for main-group; 70 Ry for d-block metals
ecutrho     = 8 × ecutwfc
smearing    = 'mv' for metals; 'gaussian' for insulators
degauss     = 0.02 for metals; 0.01 for insulators
conv_thr    = 1e-8
N_PROCS     = 6
```

### 2D materials (slab with vacuum)
```
vacuum      = 15.0 Å  (pbc=True, but z-direction is vacuum)
kpts        = (8,8,1) for small cells; (4,4,1) for larger supercells
ecutwfc     = 50 Ry
ecutrho     = 400 Ry
smearing    = 'mv' for metals; 'gaussian' for insulators
N_PROCS     = 4
```

### Surface adsorption (slab + adsorbate)
```
layers      = 3–4
vacuum      = 15.0 Å
kpts        = (4,4,1)
fix_bottom  = True (FixAtoms on bottom layer)
relax       = True (BFGS, fmax=0.05 eV/Å, steps=50)
ecutwfc     = 50–70 Ry depending on metal
N_PROCS     = 6
```

### Spin-polarised systems
For Fe, Ni, Co, Mn — add to qe_input_data:
```python
"system": {
    "nspin": 2,
    "starting_magnetization(1)": 0.5,  # adjust per element
}
```

---

## 7. GP Model Parameters

```python
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, RBF, WhiteKernel

kernel = (
    ConstantKernel(1.0, (1e-3, 1e3))
    * RBF(length_scale=LS, length_scale_bounds=(1e-2, 10.0))
    + WhiteKernel(noise_level=1e-5, noise_level_bounds=(1e-9, 1e-2))
)
gp = GaussianProcessRegressor(
    kernel=kernel,
    normalize_y=True,
    n_restarts_optimizer=8,
    random_state=CONFIG.random_state,
)
```

### Length scale (LS) selection
| Problem type | LS value | Reason |
|---|---|---|
| Bond length (molecules) | 0.05–0.10 | Narrow range ~0.5 Å |
| Lattice constant (bulk) | 0.05–0.10 | Range ~0.3–0.5 Å |
| Lattice constant (hexagonal a, c) | [0.05, 0.3] | a narrow, c wide |
| Surface adsorption (u, v) | [0.20, 0.20] | Fractional coords [0,1] |
| Bond angle (degrees) | 2.0–5.0 | Range ~20° |

For 2D problems, pass `length_scale` as a list with one value per dimension.

---

## 8. Active Learning Parameters

```python
uncertainty_threshold      = 0.005–0.05 eV   # lower for bulk, higher for adsorption
active_labels_per_iter     = 2               # 1D problems
active_labels_per_iter     = 3               # 2D problems
```

The active learning query still uses a coarse grid to evaluate uncertainty:
- 1D: `np.linspace(min, max, n_candidates)` where `n_candidates = 41–101`
- 2D: meshgrid with `n_p1 × n_p2` where each axis has 7–15 points

This grid is **only for uncertainty evaluation**, not for the inverse design proposal.

---

## 9. Convergence Criteria

```python
convergence_uncertainty            = 0.005–0.03 eV/atom
convergence_predicted_improvement  = 0.001–0.003 eV/atom
max_iterations                     = 12–15
```

Stop when BOTH conditions hold for the same iteration:
```python
if best_std < CONFIG.convergence_uncertainty and \
   predicted_gap < CONFIG.convergence_predicted_improvement:
    break
```

---

## 10. Full Script Structure (Codex must follow this exactly)

Every new script must have these sections in this order:

```
1.  Module docstring (system description, run instructions)
2.  Imports:
      from __future__ import annotations
      standard library (dataclasses, multiprocessing, pathlib, os, pickle,
                        re, shutil, time, traceback, warnings)
      matplotlib (use Agg backend)
      numpy as np
      ase and ase.calculators.espresso
      scipy.optimize.differential_evolution          ← NEW in v2
      sklearn.gaussian_process (GP + kernels)
      try: EspressoProfile except ImportError: None
3.  Path constants (ROOT, PLOT_DIR, REPORT_DIR, QE_RUN_DIR)
    CACHE_FILE, CACHE_LOCK, REPORT_FILE
4.  QE constants (PSEUDO_DIR_ABS, PSEUDOPOTENTIALS, ECUTWFC_RY,
                  ECUTRHO_RY, KPTS, N_PROCS, PARALLEL_WORKERS,
                  PW_X, QE_COMMAND)
5.  Config dataclass (all tunable parameters)
6.  CONFIG = Config()
7.  build_<material>(params) → Atoms
8.  qe_input_data(prefix, ...) → dict
9.  get_qe_calculator(directory, prefix, ...) → Espresso
10. ensure_qe_environment()
11. cache_key_*(params) → str
12. Cache lock/load/save functions (acquire_cache_lock, release_cache_lock,
    load_cache_unlocked, save_cache_unlocked, get_cached_value, set_cached_value)
13. compute_energy_*(params, retries) → float | None
14. evaluate_new_*(params_list, parallel) → list
15. add_successful_labels(pairs, X_list, y_list) → list
16. build_initial_training_set() → tuple
17. is_new_*(param, existing_list) → bool
18. GPModel class (train, predict)
19. active_learning_query(model, candidate_grid, labeled_X) → list
20. lower_confidence_bound(mean, std) → np.ndarray
21. propose_inverse_candidate(model) → tuple          ← v2 signature (no grid arg)
22. best_observed(X_list, y_list) → tuple
23. predicted_best(model, candidate_grid) → tuple
24. gp_uncertainty_at(model, point) → float
25. plot_energy_curve / plot_adsorption_surface
26. plot_convergence
27. write_report(lines) → Path
28. main()
29. if __name__ == "__main__": main()
```

---

## 11. Caching Rules

- Cache file: `{material}_qe_energy_cache_sssp_efficiency.pkl`
- Cache key must include: parameter values (6 decimal places), pseudopotential names, ecutwfc, ecutrho, kpts.
- Use file-lock (os.O_CREAT | os.O_EXCL) for concurrent access safety.
- On QE failure: retry `CONFIG.retries` times with `CONFIG.retry_wait_seconds` sleep, then return `None`.
- On `None` return: skip that point (do not crash the loop).

---

## 12. Output Structure

Each script writes to:
```
outputs/
  plots/     → {material}_energy_curve.png, {material}_convergence.png
  reports/   → {material}_qe_active_inverse_report.txt
  qe_runs_{material}/  → QE working directories (gitignored)
```

The report must log every iteration: AL points requested, inverse proposal, best observed, GP uncertainty, QE count.

---

## 13. Benchmark Material List (50 Systems)

Use this list for systematic testing. Run in order — easier systems first.

### Group A: Simple molecules (1D, fast, no spin) — 6 systems
| # | Material | Variable | Range | Pseudo family | N_PROCS |
|---|---|---|---|---|---|
| 1 | H₂ | H-H bond r | 0.5–2.0 Å | US | 2 |
| 2 | N₂ | N-N bond r | 0.9–1.4 Å | US | 2 |
| 3 | CO | C-O bond r | 0.9–1.4 Å | US | 2 |
| 4 | CH₄ | C-H bond r | 1.05–1.15 Å | US (C+H both US) | 2 |
| 5 | NH₃ | N-H bond r | 0.9–1.1 Å | US | 2 |
| 6 | H₂O | O-H r, H-O-H θ | 2D | US | 2 |

### Group B: FCC/BCC metals (1D, fast) — 8 systems
| # | Material | Variable | Range | Notes |
|---|---|---|---|---|
| 7 | FCC Cu | a | 3.40–3.80 Å | PAW |
| 8 | FCC Al | a | 3.90–4.20 Å | US |
| 9 | FCC Ni | a | 3.40–3.70 Å | PAW, spin |
| 10 | FCC Au | a | 4.00–4.30 Å | US |
| 11 | FCC Pt | a | 3.80–4.10 Å | US |
| 12 | FCC Ag | a | 4.00–4.30 Å | US |
| 13 | BCC Fe | a | 2.70–3.00 Å | PAW, spin |
| 14 | BCC Mo | a | 3.10–3.30 Å | NC or PAW |

### Group C: Semiconductors (1D) — 6 systems
| # | Material | Variable | Range | Notes |
|---|---|---|---|---|
| 15 | Diamond Si | a | 5.20–5.60 Å | US |
| 16 | Diamond Ge | a | 5.50–5.90 Å | US |
| 17 | Zinc-blende GaAs | a | 5.50–5.80 Å | US |
| 18 | Zinc-blende InP | a | 5.70–6.10 Å | US |
| 19 | Wurtzite ZnO | a, c | 2D | US |
| 20 | Diamond C | a | 3.40–3.70 Å | US |

### Group D: Ionic/oxide bulk (1D and 2D) — 6 systems
| # | Material | Variable | Range | Notes |
|---|---|---|---|---|
| 21 | Rocksalt MgO | a | 4.10–4.40 Å | PAW (both Mg, O PAW) |
| 22 | Rocksalt NaCl | a | 5.40–5.80 Å | US |
| 23 | Rocksalt LiF | a | 3.90–4.20 Å | US |
| 24 | Rutile TiO₂ | a, c | 2D | PAW Ti, PAW O |
| 25 | Perovskite SrTiO₃ | a | 3.80–4.10 Å | PAW |
| 26 | Corundum Al₂O₃ | a, c | 2D | US |

### Group E: 2D materials (1D lattice constant) — 6 systems
| # | Material | Variable | Range | Notes |
|---|---|---|---|---|
| 27 | Graphene (12 atoms) | a | 2.30–2.70 Å | US C |
| 28 | h-BN (12 atoms) | a | 2.40–2.70 Å | US B, US N |
| 29 | MoS₂ (monolayer) | a | 3.10–3.30 Å | NC Mo, US S |
| 30 | WS₂ (monolayer) | a | 3.10–3.30 Å | PAW W, US S |
| 31 | Silicene | a | 3.70–4.00 Å | US Si |
| 32 | MoSe₂ | a | 3.20–3.40 Å | NC Mo, US Se |

### Group F: Battery / complex bulk (2D) — 5 systems
| # | Material | Variable | Range | Notes |
|---|---|---|---|---|
| 33 | Layered LiCoO₂ | a, c | 2D | US Li+Co, check O type |
| 34 | Spinel LiMn₂O₄ | a | 8.10–8.50 Å | US |
| 35 | Olivine LiFePO₄ | a, b | 2D | PAW Fe, US rest |
| 36 | NMC LiNiMnCoO₂ | a, c | 2D | mixed — use PAW all |
| 37 | Li metal (BCC) | a | 3.40–3.70 Å | US |

### Group G: Surface adsorption (2D, most expensive) — 8 systems
| # | System | Variables | Notes |
|---|---|---|---|
| 38 | H/Cu(111) | u, v fractional | PAW Cu, US H |
| 39 | H/Pt(111) | u, v fractional | US Pt, US H |
| 40 | CO/Ni(111) | u, v fractional | PAW Ni, US C+O |
| 41 | O/Ru(0001) | u, v fractional | US Ru, US O |
| 42 | N/Fe(110) | u, v fractional | PAW Fe, US N |
| 43 | H/Au(111) | u, v fractional | US Au, US H |
| 44 | OH/Cu(111) | u, v fractional | PAW Cu, US O+H |
| 45 | CO/Pt(111) | u, v fractional | US Pt, US C+O |

### Group H: Heusler / intermetallic (1D) — 5 systems
| # | Material | Variable | Range | Notes |
|---|---|---|---|---|
| 46 | L1₂ Ni₃Al | a | 3.50–3.70 Å | PAW Ni, US Al |
| 47 | B2 NiAl | a | 2.80–3.00 Å | PAW Ni, US Al |
| 48 | L1₀ FePt | a, c | 2D | PAW Fe, US Pt |
| 49 | Heusler Cu₂MnAl | a | 5.60–6.00 Å | US |
| 50 | B20 FeSi | a | 4.40–4.60 Å | PAW Fe, US Si |

---

## 14. Comparison Baseline for Paper

For each material, compare:
1. **Accuracy**: `|E_best_observed − E_literature|` in meV/atom or meV/formula unit.
2. **Geometry**: `|a_best − a_literature|` in mÅ.
3. **Efficiency**: number of QE DFT calls used vs full grid (N_candidates).
4. **Wall time**: total script runtime vs estimated full-grid time.

Literature sources to cite:
- SSSP efficiency benchmark paper (Prandini et al., npj Comput. Mater. 2018)
- Materials Project database (mp.org) — use as reference geometry
- Experimental lattice constants from CRC Handbook or ICSD

---

## 15. Checklist for Codex Before Generating a Script

- [ ] System type identified (molecule / bulk / 2D / slab)
- [ ] Design variables defined (1D or 2D, physical range set)
- [ ] All pseudopotentials same family (all US or all PAW)
- [ ] `N_PROCS` set correctly for system size (2 / 4 / 6)
- [ ] `PARALLEL_WORKERS = 1`
- [ ] `ecutrho = 8 × ecutwfc`
- [ ] k-points appropriate for system (Γ for molecules, dense mesh for bulk)
- [ ] `propose_inverse_candidate(model)` — no grid argument (v2 signature)
- [ ] `from scipy.optimize import differential_evolution` imported
- [ ] Cache key includes pseudo name, ecut, kpts
- [ ] Spin polarisation added for Fe, Ni, Co, Mn
- [ ] Outputs written to `outputs/plots/` and `outputs/reports/`
- [ ] Script ends with `if __name__ == "__main__": main()`

---

## 16. Paths (Do Not Change)

```
Project root:    /mnt/d/Rifat_kh/inverse_active
Pseudo dir:      /mnt/d/Rifat_kh/SSSP_1.3.0_PBE_efficiency
pw.x binary:     /home/duets/q-e-qe-7.4.1/bin/pw.x
venv activate:   source .venv/bin/activate
```

---

## 17. Quick-Reference: Config Dataclass Fields

Every script's `Config` must include all of the following that apply:

```python
@dataclass
class Config:
    # Search space
    param_min: float = ...
    param_max: float = ...
    n_candidates: int = ...        # coarse grid points (41–101 for 1D)
    initial_params: tuple = ...    # 3–6 initial DFT points

    # Loop control
    max_iterations: int = 12
    retries: int = 2
    retry_wait_seconds: int = 5

    # Active learning
    uncertainty_threshold: float = ...   # eV or eV/atom
    active_labels_per_iter: int = 2      # or 3 for 2D

    # Inverse design
    kappa: float = 1.0

    # Convergence
    convergence_uncertainty: float = ...
    convergence_predicted_improvement: float = ...

    # Misc
    duplicate_tol: float = 1e-6
    cache_round_digits: int = 6
    random_state: int = ...   # unique per script, e.g. 42
```

---

*End of spec. Codex should generate a complete, runnable Python script from any
material entry in Section 13 using the templates in Sections 3, 6, 7, and 10.*
