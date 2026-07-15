# Dataset Diagnostics Report — TMC Benchmark v0.1

*Generated programmatically by `scripts/09_dataset_diagnostics.py`. Do not edit by hand.*

## 1. Dataset Overview

| Source | Rows |
|---|---|
| Primary relaxations (Phase 1) | 4 |
| Perturbation candidates (Phase 2B) | 12 |
| **Total** | **16** |

**Label distribution (all rows):**

- `usable_with_caution`: 12
- `validated`: 4

> Note: primary systems carry `validated` because reference comparison passed (script 13). Perturbation candidates carry `usable_with_caution` because no independent literature reference exists for perturbed geometries — correct by design, not a data quality failure.

## 2. Convergence Summary

**16/16** calculations converged (100%).

| Parent system | Primary converged | Candidates converged |
|---|---|---|
| cr_co6 | 1/1 | 3/3 |
| fe_co5 | 1/1 | 3/3 |
| ferrocene | 1/1 | 3/3 |
| ni_co4 | 1/1 | 3/3 |

## 3. Per-Candidate Metrics

ΔE = candidate final energy − parent final energy (positive = higher energy). RMS disp = RMSD of relaxed positions vs parent relaxed positions (same atom ordering).

| Candidate | Family | Dir | ΔE (meV) | Ionic steps | SCF iters | RMS disp (Å) | Basin |
|---|---|---|---|---|---|---|---|
| cr_co6__axial_stretch__-0.05 | Octahedral axial/equatorial distortion | negative | -0.00 | 11 | 232 | 0.0000 | same |
| cr_co6__co_dist__-0.04 | Carbonyl C-O stretch | negative | 0.40 | 7 | 188 | 0.0693 | same |
| cr_co6__mc_dist__+0.06 | Metal-ligand stretch | positive | 0.31 | 7 | 228 | 0.1039 | same |
| fe_co5__axial_fe_c__-0.06 | Axial Fe-C stretch | negative | -0.67 | 10 | 232 | 0.1039 | same |
| fe_co5__eq_angle_perturb_deg__-6 | Equatorial angle distortion | negative | 0.03 | 35 | 625 | 0.0628 | same |
| fe_co5__eq_fe_c__+0.06 | Equatorial Fe-C stretch | positive | 0.00 | 9 | 224 | 0.0001 | same |
| ferrocene__cc_bond__-0.03 | Cp ring radius (C-C stretch) | negative | 0.24 | 14 | 327 | 0.0420 | same |
| ferrocene__fe_cp_dist__-0.05 | Fe-Cp stretch | negative | 0.00 | 15 | 308 | 0.0000 | same |
| ferrocene__ring2_rotation_deg__+36 | Cp ring rotation | positive | 41.68 | 15 | 287 | 0.8100 | different |
| ni_co4__co_dist__-0.04 | Carbonyl C-O stretch | negative | 0.34 | 8 | 265 | 0.0400 | same |
| ni_co4__mc_dist__+0.06 | Metal-ligand stretch | positive | 0.26 | 8 | 310 | 0.0600 | same |
| ni_co4__tetra_angle_perturb_deg__-6 | Tetrahedral angle distortion | negative | -0.10 | 38 | 772 | 0.1258 | same |

## 4. Perturbation Family Analysis

### 4a. Stretch vs Angle/Rotation

| Type | Count | Mean ionic steps | Mean SCF iters | Mean |ΔE| (meV) | Mean RMS disp (Å) | Same-basin rate |
|---|---|---|---|---|---|---|
| Stretch | 8 | 9.8 | 260.2 | 0.28 | 0.0524 | 8/8 |
| Angle / rotation | 4 | 24.8 | 479.0 | 10.45 | 0.2497 | 3/4 |

> **Note on mean |ΔE| for angle/rotation:** the 10.45 meV value is almost entirely driven by the ferrocene Cp ring rotation (+41.68 meV, a genuine conformational change). The other 3 angle perturbations all have |ΔE| < 0.11 meV — consistent with stretches. Do not interpret the mean as representative of all angle perturbations; use the per-candidate table (§3) for accurate comparison.

### 4b. Per-family summary

| Family | N | Mean ionic steps | Mean SCF iters | Same-basin |
|---|---|---|---|---|
| Axial Fe-C stretch | 1 | 10.0 | 232.0 | 1/1 |
| Carbonyl C-O stretch | 2 | 7.5 | 226.5 | 2/2 |
| Cp ring radius (C-C stretch) | 1 | 14.0 | 327.0 | 1/1 |
| Cp ring rotation | 1 | 15.0 | 287.0 | 0/1 |
| Equatorial Fe-C stretch | 1 | 9.0 | 224.0 | 1/1 |
| Equatorial angle distortion | 1 | 35.0 | 625.0 | 1/1 |
| Fe-Cp stretch | 1 | 15.0 | 308.0 | 1/1 |
| Metal-ligand stretch | 2 | 7.5 | 269.0 | 2/2 |
| Octahedral axial/equatorial distortion | 1 | 11.0 | 232.0 | 1/1 |
| Tetrahedral angle distortion | 1 | 38.0 | 772.0 | 1/1 |

## 5. Energy Ranges

| System | Primary energy (Ry) | Candidate range (Ry) | ΔE range (meV) |
|---|---|---|---|
| cr_co6 | -536.0152471419 | 3 candidates | [-0.00, +0.40] |
| fe_co5 | -629.6772928617 | 3 candidates | [-0.67, +0.03] |
| ferrocene | -525.3618442398 | 3 candidates | [+0.00, +41.68] |
| ni_co4 | -583.5691160575 | 3 candidates | [-0.10, +0.34] |

## 6. Geometry Optimization Cost

BFGS ionic steps and total SCF iterations indicate how difficult the relaxation was from the perturbed starting geometry.

| Candidate | Ionic steps | SCF iters | Wall time (s) |
|---|---|---|---|
| ni_co4__tetra_angle_perturb_deg__-6 | 38 | 772 | 10380.0 |
| fe_co5__eq_angle_perturb_deg__-6 | 35 | 625 | 14640.0 |
| ferrocene__fe_cp_dist__-0.05 | 15 | 308 | 5100.0 |
| ferrocene__ring2_rotation_deg__+36 | 15 | 287 | 4860.0 |
| ferrocene__cc_bond__-0.03 | 14 | 327 | 5100.0 |
| cr_co6__axial_stretch__-0.05 | 11 | 232 | 5820.0 |
| fe_co5__axial_fe_c__-0.06 | 10 | 232 | 5160.0 |
| fe_co5__eq_fe_c__+0.06 | 9 | 224 | 5040.0 |
| ni_co4__co_dist__-0.04 | 8 | 265 | 3348.21 |
| ni_co4__mc_dist__+0.06 | 8 | 310 | 3960.0 |
| cr_co6__co_dist__-0.04 | 7 | 188 | 4620.0 |
| cr_co6__mc_dist__+0.06 | 7 | 228 | 5700.0 |

## 7. Basin Assignment and Duplicate Detection

- **Same basin as parent** (|ΔE| < 10 meV): 11/12
- **Different basin** (|ΔE| ≥ 10 meV): 1/12

Different-basin candidates:

- `ferrocene__ring2_rotation_deg__+36`: ΔE = 41.68 meV, RMS disp = 0.8100 Å

Geometric near-duplicates of parent (RMS disp < 0.05 Å): 5/12

> These candidates relaxed back to a geometry essentially identical to the parent, confirming they probe the same PES basin. Expected for bond-stretch perturbations.

## 8. Key Scientific Findings

### 8.1 Stretch-redundancy pattern

All 8/8 bond-stretch perturbations relaxed back to the parent basin (|ΔE| < 10 meV, mean RMSD consistent with small geometry variation). Stretch degrees of freedom in these rigid organometallics have no barrier — the PES is essentially monotonic back to the equilibrium bond length.

### 8.2 In-plane angle distortions: harder relaxation path

2/4 angle/rotation perturbations required >15 ionic steps (fe_co5__eq_angle_perturb_deg__-6, ni_co4__tetra_angle_perturb_deg__-6). This pattern is specific to in-plane angle distortions in T_d/D3h geometries — not a general property of all angle perturbations. The Cp ring rotation (15 steps) and the Cr(CO)6 axial distortion (11 steps) are not significantly more expensive than stretches, despite also being non-stretch perturbations.

### 8.3 Ferrocene Cp ring rotation — different conformer found

`ferrocene__ring2_rotation_deg__+36`: ΔE = 41.68 meV, RMS disp = 0.8100 Å. This is the only candidate to reach a genuinely different PES minimum. Consistent with ferrocene's known low rotational barrier (~4 kJ/mol) between eclipsed (D5h) and staggered (D5d) conformers — the +36° rotation places the ring in a staggered-like geometry that the BFGS cannot relax back to eclipsed without crossing the barrier.

### 8.4 Cr(CO)6 axial distortion — symmetric Oh restored

`cr_co6__axial_stretch__-0.05`: ΔE = -0.00 meV. Cr(CO)6 is d6 low-spin octahedral — no Jahn-Teller driving force. The tetragonal distortion relaxed fully back to Oh symmetry, confirming the PES is smooth and symmetric around this equilibrium.

## 9. Metadata Completeness

| Field | Present (all rows) |
|---|---|
| `system_id` | 16/16 |
| `convergence_status` | 16/16 |
| `final_energy_ry` | 16/16 |
| `ionic_steps` | 16/16 |
| `scf_iterations_total` | 16/16 |
| `label` | 16/16 |

## 10. Known Limitations

- **No `reliable` rows in this dataset.** Primary systems are `validated` (passed reference comparison, script 13), but perturbation candidates have no literature counterparts — correct by design.
- **`negative_rho` warnings present in all calculations.** Small negative charge density arises from incomplete Fourier series truncation in plane-wave DFT. The warnings are retained in the parsed dataset and should be reviewed case-by-case before external publication.
- **Ni/Cr pseudopotential naming convention resolved.** `ni_pbe_v1.4.uspp.F.UPF` and `cr_pbe_v1.5.uspp.F.UPF` are official SSSP efficiency GBRV entries; the naming difference from `_psl.` files is expected because SSSP mixes source libraries by element.
- **Dataset size.** 16 DFT calculations across 4 systems are sufficient for workflow demonstration and PES sampling characterization, but not for statistically robust ML training. ML/AL infrastructure should carry an explicit 'not yet predictive' disclaimer until ≥30–50 validated calculations per system are available.

