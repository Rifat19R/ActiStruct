# TMC Reliability Benchmark v1.0

*ActiStruct-nebwalk Transition-Metal Complex Benchmark — v1.0 release report.*

---

## 1. Motivation

Active-learning (AL) workflows for DFT-guided materials discovery depend on a
reliable energy oracle — a DFT calculator that consistently converges, produces
physically correct geometries, and agrees with established literature values.
Before deploying an AL loop on transition-metal complexes (TMCs), the underlying
QE pipeline must be validated on well-characterised benchmark molecules whose
experimental geometries are available in the literature.

This benchmark serves three purposes:

1. **Validate the QE automation pipeline** end-to-end on four canonical TMCs.
2. **Demonstrate PES sampling** via controlled perturbation candidates, providing
   the first evidence that the perturbation generator explores meaningfully distinct
   regions of the energy surface.
3. **Establish a validated, reproducible dataset** as the foundation for future
   feature extraction, ML training, and active-learning experiments.

---

## 2. Systems

| System | Formula | Point group | Bonding type |
|---|---|---|---|
| Ferrocene | Fe(C₅H₅)₂ | D₅h (eclipsed) | η⁵-Cp sandwich |
| Ni(CO)₄ | Ni(CO)₄ | T_d | Metal-carbonyl Td |
| Cr(CO)₆ | Cr(CO)₆ | O_h | Metal-carbonyl Oh |
| Fe(CO)₅ | Fe(CO)₅ | D₃h | Metal-carbonyl TBP |

These four systems span the most common TMC bonding motifs (sandwich, tetrahedral
carbonyl, octahedral carbonyl, trigonal-bipyramidal carbonyl) and cover six elements
(Fe, Ni, Cr, C, H, O) — representative of the broader TMC design space relevant to
homogeneous catalysis.

---

## 3. Computational Setup

| Parameter | Value |
|---|---|
| Code | Quantum ESPRESSO pw.x v7.4.1 |
| Functional | PBE (GGA) |
| Pseudopotentials | SSSP efficiency tier v1.3.0; Fe/C/H/O from PSLibrary, Ni/Cr from GBRV entries selected by SSSP efficiency |
| Wavefunction cutoff | 60 Ry for original PBE benchmark; Fe(CO)5 cutoff scan shows 90 Ry is required for Fe energy claims |
| Charge density cutoff | 480 Ry for 60 Ry runs; 720 Ry for the 90 Ry Fe cutoff/PBE-D3 follow-up |
| k-points | Γ-point only (isolated molecules) |
| Isolation correction | Martyna-Tuckerman (`assume_isolated = 'mt'`) |
| Vacuum padding | 6.0 Å per side (cubic supercell) |
| Convergence thresholds | SCF: 10⁻⁸ Ry; forces: 10⁻⁴ Ry/bohr; energy: 10⁻⁵ Ry |
| BFGS trust radius min | 10⁻⁶ bohr |
| Cell type | Cubic (`ibrav = 1`, `celldm(1)`) |
| MPI ranks | 4 |
| Hardware | WSL2 Ubuntu on Windows 11, 16 GB RAM allocated |

**Reproducibility.** All inputs are generated programmatically by
`scripts/06_build_qe_inputs.py`. Inputs are validated before execution by
`scripts/06_build_qe_inputs.py::validate_generated_input()` which checks ibrav,
`outdir` placement, pseudo file existence, and atom overlap. The batch runner
(`scripts/06b_run_qe_candidates_batch.sh`) is idempotent: it skips any calculation
whose output already contains `bfgs converged` or `JOB DONE`, allowing safe
resumption after hardware failure (this project experienced two power-loss
interruptions during Phase 2B execution — both were recovered without data loss).

---

## 4. Phase 1: Primary Relaxations

All four primary structures were built from literature geometries using
`scripts/04_build_initial_structures.py` and relaxed to their DFT equilibrium
geometries.

| System | Final energy (Ry) | Ionic steps | Convergence |
|---|---|---|---|
| ferrocene | −525.3618442398 | 10 | ✓ bfgs converged |
| ni_co4 | −583.5691160575 | 9 | ✓ bfgs converged |
| cr_co6 | −536.0152471419 | 7 | ✓ bfgs converged |
| fe_co5 | −629.6772928617 | 13 | ✓ bfgs converged |

**Known issues resolved during Phase 1:**

- *OOM crash (ferrocene)*: original vacuum padding of 12 Å/side inflated the cubic
  cell to ~28 Å, requiring ~55 GB RAM. Reduced to 6 Å/side (~10.5 GB) — within
  the 16 GB WSL ceiling and still standard for the MT correction.
- *BFGS failure (cr_co6)*: `ibrav=0` with a generic `CELL_PARAMETERS` block
  introduced floating-point asymmetry that appeared as spurious force noise near
  the symmetric stationary point, collapsing the BFGS trust radius. Fixed by
  switching to `ibrav=1`/`celldm(1)` and setting `trust_radius_min = 1e-6` bohr.
- *Checkpoint crash (ferrocene)*: QE's scratch writes (`outdir`) failed on the 9p
  DrvFs-mounted Windows drive (`/mnt/d`) under multi-rank MPI I/O. Fixed by
  pointing `outdir` to native WSL ext4 (`/home/duets/qe_workdirs/`).

---

## 5. Phase 2A: Reference Validation

Relaxed geometries were compared to crystallographic/gas-phase electron diffraction
reference values sourced from the peer-reviewed literature.

| System | Key bond | DFT (Å) | Literature (Å) | Deviation | Source |
|---|---|---|---|---|---|
| ferrocene | Fe–C | 2.0437 | 2.064 ± 0.003 | −0.98% | Haaland & Nilsson 1968, Acta Chem. Scand. 22, 2653 |
| ferrocene | C–C (Cp) | 1.4340 | 1.440 | −0.42% | Haaland & Nilsson 1968 |
| ni_co4 | Ni–C | 1.8119 | 1.838 ± 0.002 | −1.42% | Hedberg et al. 1979, J. Chem. Phys. 70, 3224 |
| ni_co4 | C–O | 1.1504 | 1.141 ± 0.002 | +0.82% | Hedberg et al. 1979 |
| cr_co6 | Cr–C | 1.9001 | 1.916 ± 0.003 | −0.83% | Whitaker & Jeffery 1967, Acta Cryst. 23, 977 |
| cr_co6 | C–O | 1.1540 | 1.171 ± 0.003 | −1.45% | Whitaker & Jeffery 1967 |
| fe_co5 | Fe–C (ax) | 1.8025 | 1.810 ± 0.003 | −0.41% | McClelland et al. 2001, Inorg. Chem. 40, 1358 |
| fe_co5 | Fe–C (eq) | 1.8004 | 1.842 ± 0.003 | −2.26% | McClelland et al. 2001, Inorg. Chem. 40, 1358 |
| fe_co5 | C–O (ax) | 1.1527 | 1.142 ± 0.003 | +0.94% | McClelland et al. 2001 |
| fe_co5 | C–O (eq) | 1.1556 | 1.149 ± 0.003 | +0.58% | McClelland et al. 2001 |

All deviations are within normal PBE-GGA-vs-experiment agreement (max −2.26% for
Fe(CO)₅ equatorial Fe–C, typical for this functional). PBE-GGA systematically
underestimates bond lengths slightly relative to gas-phase electron diffraction
data. All four systems labelled `validated` by `scripts/13_compare_to_references.py`
(tolerance: 0.03 Å absolute or 3% relative, whichever is looser).

> **Important:** ferrocene is now primary-PDF verified against Haaland &
> Nilsson 1968, Table 1. Ni(CO)4, Cr(CO)6, and Fe(CO)5 remain below full
> primary-PDF verification; PDF-level review is still required before those
> reference bond lengths are cited externally.

---

## 6. Phase 2B: Perturbation Campaign

### 6.1 Perturbation design

52 one-at-a-time (OAT) perturbation candidates were generated by
`scripts/05_generate_perturbation_candidates.py`, covering the primary geometric
degrees of freedom for each system: metal–ligand bond lengths, ligand internal
bond lengths, angular distortions, and conformational rotations.

12 representatives were selected by `scripts/05b_audit_perturbation_candidates.py`
(3 per system, one per family, largest accepted magnitude), with sign-alternation
across families to ensure both compression and expansion directions are sampled.
All 52 candidates passed the chemical-reasonableness audit (no atom overlaps, no
unrealistic bond lengths, no RMSD duplicates within system).

### 6.2 Convergence

All 12 perturbation candidates converged (100% convergence rate). Combined with
Phase 1: **16/16 DFT calculations converged** across both campaigns.

### 6.3 Per-candidate results

| Candidate | ΔE (meV) | Ionic steps | SCF iters | RMS disp (Å) | Basin |
|---|---|---|---|---|---|
| ferrocene__fe_cp_dist__-0.05 | +0.00 | 15 | 308 | 0.0000 | same |
| ferrocene__ring2_rotation_deg__+36 | **+41.68** | 15 | 287 | **0.8100** | **different** |
| ferrocene__cc_bond__-0.03 | +0.24 | 14 | 327 | 0.0420 | same |
| ni_co4__mc_dist__+0.06 | +0.26 | 8 | 310 | 0.0600 | same |
| ni_co4__co_dist__-0.04 | +0.34 | 8 | 265 | 0.0400 | same |
| ni_co4__tetra_angle_perturb_deg__-6 | −0.10 | **38** | **772** | 0.1258 | same |
| cr_co6__mc_dist__+0.06 | +0.31 | 7 | 228 | 0.1039 | same |
| cr_co6__co_dist__-0.04 | +0.40 | 7 | 188 | 0.0693 | same |
| cr_co6__axial_stretch__-0.05 | −0.00 | 11 | 232 | 0.0000 | same |
| fe_co5__axial_fe_c__-0.06 | −0.67 | 10 | 232 | 0.1039 | same |
| fe_co5__eq_fe_c__+0.06 | +0.00 | 9 | 224 | 0.0001 | same |
| fe_co5__eq_angle_perturb_deg__-6 | +0.03 | **35** | **625** | 0.0628 | same |

ΔE = final energy relative to parent relaxed minimum. RMS disp = RMSD of relaxed
positions vs parent (same atom ordering).

---

## 7. Key Scientific Findings

### 7.1 Bond-stretch perturbations are PES-redundant

All 8 bond-stretch candidates (Fe–Cp, C–C ring, M–C, C–O, Fe–C axial, Fe–C
equatorial) relaxed back to within |ΔE| < 1 meV of their parent minimum with
7–15 BFGS steps. RMS displacements are small (0.00–0.13 Å), confirming return
to the same basin. Stretch degrees of freedom in these rigid organometallics lie
along the steep side of the PES well — no barrier exists to the equilibrium
geometry.

**Implication for active learning:** stretch-only perturbations are poor candidates
for expanding dataset diversity. They add computational cost without sampling new
PES regions.

### 7.2 In-plane angle distortions take harder relaxation paths

Four angle/rotation candidates were tested across the four systems. Of these, the
two in-plane angle distortions — Ni(CO)₄ tetrahedral distortion (38 BFGS steps,
772 SCF iters) and Fe(CO)₅ equatorial angle distortion (35 BFGS steps, 625 SCF
iters) — required 3–5× more steps than comparable stretch perturbations (7–15
steps). Despite the higher cost, both returned to the same PES basin (|ΔE| < 0.1
meV), indicating a corrugated but still funnel-like PES.

By contrast, the Cr(CO)₆ axial distortion (11 BFGS steps) and ferrocene Cp ring
rotation (15 BFGS steps) were not significantly more expensive than stretches —
though the ring rotation found a genuinely different basin (§7.3). The "harder
path" pattern is therefore specific to in-plane angle distortions in T_d and D₃h
geometries, not a general property of all non-stretch perturbations.

### 7.3 Ferrocene Cp ring rotation reaches a distinct conformer

The +36° Cp ring rotation (ferrocene) is the only perturbation that found a
genuinely different PES minimum: ΔE = +41.68 meV, RMS displacement = 0.81 Å.
This is consistent with ferrocene's known low rotational barrier (~4 kJ/mol, ~41
meV) between its D₅h eclipsed and D₅d staggered conformers. The BFGS optimizer
relaxed into the staggered-like geometry rather than crossing back over the
rotational barrier.

This finding validates that the perturbation generator *can* produce starting
geometries that sample genuinely distinct PES minima — a prerequisite for the
active-learning use case.

### 7.4 Cr(CO)₆ fully restores O_h symmetry

The axial distortion of Cr(CO)₆ (−0.05 Å tetragonal stretch) relaxed back to
|ΔE| = 0.00 meV and RMS = 0.00 Å — essentially machine precision. Cr(CO)₆ is
d⁶ low-spin octahedral with no Jahn-Teller driving force, so the symmetric
minimum is a true energy minimum with no symmetry-breaking tendency. This
provides an independent verification of the relaxation quality for this system.

---

## 8. Limitations and Open Questions

| Item | Status |
|---|---|
| Reference values PDF-verified | ❌ Needs manual check before external use |
| Ni/Cr pseudopotential tier confirmed | ✅ Confirmed as official SSSP efficiency GBRV entries; naming difference from `_psl` is expected |
| Fe cutoff convergence | ✅ Fe(CO)5 60/75/90 Ry scan complete; 90 Ry adopted for Fe energy claims because 60/75 Ry fail the energy criterion vs 90 Ry |
| `negative_rho` warnings | ⚠️ Present in all 16 calculations; retained in parser output and should be reviewed case-by-case before external publication |
| Dataset size for ML | ⚠️ 16 calculations are sufficient for workflow demonstration; not sufficient for statistically robust ML/AL (target: ≥30–50 per system) |
| Dispersion correction | ⚠️ Ferrocene PBE-D3/90 Ry relaxation completed and D5h conformer check passed; dispersion-only energy effect is not isolated from the cutoff change |
| Spin polarisation | ❌ All calculations non-spin-polarised; appropriate for closed-shell systems studied here but must be revisited for open-shell TMCs |

---

## 9. Repository Structure

```
ActiStruct/
├── scripts/
│   ├── 04_build_initial_structures.py   — structure generation
│   ├── 05_generate_perturbation_candidates.py
│   ├── 05b_audit_perturbation_candidates.py
│   ├── 06_build_qe_inputs.py            — QE input generation + validation
│   ├── 06b_run_qe_candidates_batch.sh   — idempotent batch runner
│   ├── 07_parse_qe_outputs.py           — production QE parser (17 fields)
│   ├── 08_validate_dataset.py           — label rows, never delete
│   ├── 09_dataset_diagnostics.py        — merge, metrics, this report's data
│   ├── 10_build_features.py             — 16-row descriptor table
│   ├── 11_dataset_loader.py             — ML-ready loader + LOO splits
│   ├── 12_baseline_model.py             — GP uncertainty demo
│   └── 13_compare_to_references.py      — geometry vs literature comparison
├── data/processed/
│   ├── full_dataset_v0.2.csv            — merged 16-row validated dataset
│   ├── candidate_audit_v0.csv           — 52-candidate audit with metadata
│   └── ...
├── references/
│   └── reference_values_tmc_v0.yaml     — sourced literature values
├── configs/
│   ├── qe_molecule_settings.yaml
│   └── project_config.yaml
├── tests/                               — 417 passing tests
└── reports/
    ├── dataset_diagnostics_v0.1.md      — programmatic diagnostics
    └── tmc_benchmark_v1.0.md            — this document
```

---

## 10. Next Steps

1. **Manual PDF verification** of reference values (§5, §8).
2. **Fe 90 Ry policy** — use 90 Ry for Fe-containing energy claims; treat the
   original 60 Ry Fe energies as workflow-validation data unless explicitly
   re-run at the adopted cutoff.
3. **Feature extraction** (`scripts/10_extract_features.py`) — compute structural
   descriptors (bond lengths, angles, coordination numbers, Coulomb matrix
   elements) for all 16 relaxed geometries.
4. **Dataset loader and train/test split** scaffolding — with explicit
   "not yet predictive" disclaimer.
5. **Active-learning demonstration** — begin once ≥30–50 validated calculations
   per system are available.
