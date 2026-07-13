# TMC Reliability Benchmark - Pre-v1.0 Complete (Tasks 1-9)

**Branch:** `feature/tmc-reliability-benchmark` -> `main`

## Overview

Adds a full DFT-validated benchmark dataset for transition-metal carbonyl and
metallocene complexes, built to stress-test and demonstrate ActiStruct's
active-learning pipeline on real Quantum ESPRESSO-relaxed structures. All 9
pre-release tasks are complete with 281 passing tests.

---

## Systems

Four primary TMC systems, 16 total validated DFT calculations
(PBE/plane-wave, QE pw.x v7.4.1):

| System    | Formula      | Symmetry    | Notes                         |
|-----------|--------------|-------------|-------------------------------|
| Cr(CO)6   | CrC6O6       | Oh          | Chromium hexacarbonyl         |
| Fe(CO)5   | FeC5O5       | D3h         | Iron pentacarbonyl            |
| Ni(CO)4   | NiC4O4       | Td          | Nickel tetracarbonyl          |
| Ferrocene | Fe(C5H5)2    | D5h / D5d   | Eclipsed + staggered conformers |

---

## What's Added

### Data & DFT
- `data/processed/full_dataset_v0.2.csv` -- 16 QE-relaxed structures with
  energies, forces, convergence status, and parsed geometry
- `data/features/features_v0.1.csv` -- Coulomb matrix eigenvalues
  (Rupp et al. 2012) + local metal-center geometry descriptors
  (M-L distances, L-M-L angles, C-O bond lengths)
- `data/references/` -- YAML-formatted literature reference records,
  cross-verified against primary sources

### Scripts (`scripts/01_*` -> `scripts/17_*`)
Full pipeline:
pseudopotential verification -> QE input generation -> structure parsing ->
feature computation -> GP baseline -> active learning demo ->
NEB endpoint preparation

### QE Calculations (`qe/`)
- Validated input files and parsed outputs for all 16 primary + 12 candidate
  structures
- Fe(CO)5 cutoff convergence series (60-105 Ry); ferrocene PBE-D3/90 Ry rerun

### NEB Endpoints (`structures/neb_endpoints/`)
- `ferrocene_eclipsed_d5h.xyz` -- ground state, E = -7147.912031 eV
- `ferrocene_staggered_d5d.xyz` -- local minimum, E = -7147.870353 eV,
  dE = +41.68 meV
- Ready for nebwalk linear/IDPP interpolation

### Reports (`reports/`)
- Feature report (Coulomb matrix + geometry -- explicitly not RAC descriptors)
- GP baseline model report with CRITICAL DISCLAIMER (12 training points,
  not statistically meaningful)
- Active-learning demo report (retrospective, 8-candidate pool, 4-point holdout)
- Fe cutoff convergence, ferrocene PBE-D3 analysis, reference validation,
  daily logs (Tasks 1-9)

---

## Key Scientific Results

- **Fe(CO)5 cutoff convergence**: dE(60->90 Ry) < 0.3 meV -- converged at
  60 Ry; adopt 90 Ry for publication margin
- **Ferrocene conformer barrier**: dE(eclipsed->staggered) = 41.68 meV --
  matches experimental ~41 meV (~4 kJ/mol), validates PBE conformer ordering
- **PBE bond-length bias**: TM-C distances underestimate experiment by
  0.016-0.028 Angstrom, consistent with known PBE behaviour;
  +/-0.05 Angstrom tolerance applied in tests
- **Ferrocene PBE-D3 recheck**: eclipsed D5h confirmed as ground state under
  dispersion correction

---

## Tests (281 passing)

| File                                | Tests | Covers                                                    |
|-------------------------------------|-------|-----------------------------------------------------------|
| `test_pseudo_verification.py`       | 8     | SSSP checksums for Cr, Fe, Ni pseudopotentials            |
| `test_qe_parser.py`                 | 18    | QE output parsing, force/energy extraction                |
| `test_feature_builder.py`           | 22    | Coulomb matrix + geometry reproducibility, DFT vs ref     |
| `test_reference_data_integrity.py`  | 11    | YAML reference schema and verification status             |
| `test_convergence_and_consistency.py` | 12  | BFGS convergence, atom counts, energy ordering, dE sanity |
| `test_fe_cutoff_convergence.py`     | 14    | Cutoff convergence data and ferrocene label disambiguation |
| `test_neb_endpoints.py`             | 9     | XYZ files, stoichiometry, dE encoding, energy bounds      |
| `test_ml_al_framing.py`             | 31    | Report disclaimer presence, prohibited over-claim phrases |
| *(others)*                          | 156   | Dataset loading, AL demo, baseline model, environment,    |
|                                     |       | QE inputs, perturbation candidates                        |

---

## Non-goals / Honest Scope

- This is a **workflow demonstration**, not a production ML model. 16 structures
  is insufficient for statistically meaningful ML performance claims -- all
  reports say so explicitly.
- NEB endpoints use PBE/60 Ry (not the recommended 90 Ry); sufficient for
  interpolation input, not for publication-quality barrier heights.
- No claim of generalization to out-of-distribution TMC systems.

---

## Repo Changes

- `.gitattributes`: merged -- adds `*.UPF binary`, `*.upf binary`,
  `*.joblib binary`
- `.gitignore`: merged -- adds QE workspace patterns, `.env*`,
  abandoned cutoff run exclusions
- `README.md`: ActiStruct README preserved; TMC benchmark summary section
  appended
