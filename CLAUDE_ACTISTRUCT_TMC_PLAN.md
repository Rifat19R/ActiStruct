# CLAUDE.md — ActiStruct–nebwalk Transition-Metal Complex Reliability Benchmark

**Project owner:** Md. Rifat Khandaker  
**Working directory:** `D:\Research\Dr.Kulik_MIT`  
**Installed/local model:** ActiStruct / inverse_active is inside or installed from this working directory  
**Pseudopotential directory:** `D:\Rifat_kh\SSSP_1.3.0_PBE_efficiency`  
**Main assistant:** Claude Code  
**Main scientific target:** Build a professor-safe, reproducible, reliability-aware DFT + ML + active-learning benchmark aligned with Dr. Heather J. Kulik's research themes: electronic-structure reliability, transition-metal chemistry, machine learning, uncertainty, and automated workflows.

---

## 0.1 Verified Environment Corrections (2026-06-29, Phase 1)

The assumptions above were written before the environment was inspected. Phase 1 inspection (`scripts/00_inspect_environment.py`) found the following corrections — treat these as authoritative over the original assumptions in the header and in Section 0:

- **Working repo:** `D:/Research/Dr.Kulik_MIT`, git-initialized, phase 1 built on branch `feature/tmc-reliability-benchmark`.
- **ActiStruct is not inside this working directory.** The real importable package is `actistruct` (not `inverse_active`), editable-installed from the canonical repo at `D:/Rifat_kh/inverse_active` (v0.7.2) into the global Windows Python 3.14.4 environment (`C:\Users\duets\AppData\Local\Python\pythoncore-3.14-64\python.exe`). That repo's own `.venv` is WSL-targeted (`/usr/bin/python3.12`) and not used for this project.
- **QE binary:** `pw.x` v7.4.1 is not on Windows PATH and not on WSL's default PATH. It runs at the exact path `/home/duets/q-e-qe-7.4.1/bin/pw.x` under WSL Ubuntu (user `duets`). Confirmed runnable — smoke-tested against a generated `.in` file, parsed cleanly, pseudopotentials loaded, SCF setup began with no errors.
- **Pseudopotential directory from WSL:** `/mnt/d/Rifat_kh/SSSP_1.3.0_PBE_efficiency` (Windows path `D:\Rifat_kh\SSSP_1.3.0_PBE_efficiency` translated for use by `pw.x`, which only runs under WSL). `scripts/06_build_qe_inputs.py` performs this translation automatically for `pseudo_dir`/`outdir`.
- **Ni and Cr pseudopotentials need manual review.** `ni_pbe_v1.4.uspp.F.UPF` and `cr_pbe_v1.5.uspp.F.UPF` exist in the directory but don't match the `_psl.` SSSP-efficiency naming convention used by Fe/C/H/O in the same folder — may be a different pseudopotential family/accuracy tier. Flagged in `configs/pseudo_manifest_required.yaml` under `naming_convention_warnings`. Confirm these are the correct SSSP-efficiency pseudopotentials before any production (non-smoke-test) run.
- **Phase 1 test status:** 28/28 tests passed (`pytest tests/ -v`), covering environment inspection, pseudo manifest, reference schema (no fabricated values), structure generation, perturbation candidates, and QE input building.
- **`vacuum_padding_angstrom` reduced 12.0 -> 6.0` (2026-06-29):** the original 12 A/side value OOM'd a real ferrocene relax attempt (estimated 54.79 GB total dynamical RAM vs. 16 GB WSL allocation + 20 GB swap on a 32 GB host) and briefly destabilized the WSL VM itself. 6 A/side is a standard working value for the `assume_isolated='mt'` correction and brought the estimate down to ~10.5 GB/process - re-verified against the real `pw.x` binary, which ran cleanly through several SCF iterations with no memory error.
- See `docs/PHASE1_SUMMARY.md` for the full phase 1 deliverable summary.

---

## 0. Immediate Instruction to Claude Code

You are acting as a senior scientific Python engineer and computational chemistry workflow assistant.

Your first job is **not** to write random scripts. Your first job is to inspect the existing ActiStruct/inverse_active codebase, understand its architecture, read its README, and then create a clean project scaffold around it without breaking the existing package.

Before modifying anything:

1. Print current working directory.
2. List the directory tree to depth 3.
3. Locate the ActiStruct/inverse_active source package.
4. Read `README.md`, `pyproject.toml`, `setup.py`, `setup.cfg`, and any `docs/` files if they exist.
5. Check import names:
   - `actistruct`
   - `inverse_active`
6. Report what package name actually works.
7. Detect the active Python environment.
8. Check whether `pw.x` from Quantum ESPRESSO is available in PATH.
9. Check whether the pseudopotential directory exists.
10. Create a plan before writing files.

Never assume the package layout. Inspect first.

---

## 1. Core Scientific Goal

The goal is to build a small, rigorous, reproducible benchmark showing that ActiStruct can support **reliability-aware active learning for DFT-guided transition-metal complex optimization**.

The goal is **not** to claim that ActiStruct or nebwalk solves transition-metal chemistry.

The safe scientific story is:

> ActiStruct organizes DFT calculations, records convergence and failure behavior, estimates uncertainty, and actively selects informative candidate geometries for validation. nebwalk is used only as a secondary demonstration for one simple molecular pathway after reliable endpoints exist.

---

## 2. Non-Negotiable Scientific Rules

Follow these rules strictly:

1. Do not fabricate literature values.
2. Do not invent DOIs, bond lengths, barriers, or benchmark values.
3. Do not hide failed DFT calculations.
4. Do not delete outliers silently.
5. Do not claim discovery.
6. Do not claim ML replaces DFT.
7. Do not claim MACE/MLIP final accuracy for organometallic transition-metal complexes.
8. Do not use charged complexes in the first benchmark.
9. Do not start with SSE17 spin-state energetics before the neutral benchmark works.
10. Do not over-engineer; build a clean minimum viable research workflow first.
11. Every result must be traceable to input file, output file, pseudopotentials, settings, parser version, and reference source.
12. Every script must support a `--dry-run` mode where possible.
13. Every script must fail loudly with clear error messages.
14. Every script must write logs.
15. Every Python module must have a sanity test.

---

## 3. Correct Benchmark Scope

### 3.1 Primary Benchmark Systems

Start with exactly these four neutral, closed-shell or relatively safe organometallic complexes:

| ID | Complex | Formula | Charge | Spin treatment | Geometry class | Main use |
|---|---|---|---:|---|---|---|
| `ferrocene` | Ferrocene | Fe(C5H5)2 | 0 | closed-shell first pass | sandwich | ActiStruct geometry benchmark; optional Cp rotation path |
| `ni_co4` | Nickel tetracarbonyl | Ni(CO)4 | 0 | closed-shell first pass | tetrahedral | sanity benchmark |
| `cr_co6` | Chromium hexacarbonyl | Cr(CO)6 | 0 | closed-shell first pass | octahedral | ligand-field geometry benchmark |
| `fe_co5` | Iron pentacarbonyl | Fe(CO)5 | 0 | closed-shell first pass | trigonal bipyramidal | geometry benchmark; optional fluxional path |

These are the only first-phase systems.

### 3.2 Secondary Systems — Do Not Start Until Primary Works

Only after the primary workflow is tested:

| Complex | Reason | Risk |
|---|---|---|
| V(CO)6 | open-shell carbonyl test | spin-sensitive |
| (eta6-C6H6)Cr(CO)3 | piano-stool organometallic | larger system |
| TiCl4 | neutral inorganic control | less aligned but simple |
| 1–2 SSE17 systems | spin-state extension | high difficulty |

### 3.3 Systems to Avoid in Phase 1

Do not use these in the first benchmark:

- `[Cu(NH3)4]2+`
- `[Co(NH3)6]3+`
- `[Fe(CN)6]4-`

Reason: charged complexes in periodic plane-wave DFT require careful treatment of vacuum, background charge, electrostatic corrections, possible solvation/counterions, and spin/charge-state validation. They are scientifically important but not suitable for the first professor-facing demo.

---

## 4. Correct Source Strategy for Reference Data

The source priority must be:

1. Peer-reviewed literature and original experimental/theoretical studies.
2. Trusted reference databases for molecular structure and thermochemistry when applicable.
3. COD for CIF/crystal structures when relevant and properly cited.
4. Materials Project only for crystalline materials or later solid-state extension.
5. OQMD only for crystalline inorganic materials or later solid-state extension.
6. General websites only if official, traceable, and not used as the only source for final claims.

Important correction:

Materials Project and OQMD are excellent for crystalline materials, but they are not the primary validation source for isolated molecular organometallic complexes such as ferrocene, Ni(CO)4, Cr(CO)6, or Fe(CO)5. For this project, literature and molecule/crystal-structure references come first.

### 4.1 Reference Data File

Create:

```text
references/reference_values_tmc_v0.yaml
```

Each reference entry must contain:

```yaml
complex_id:
  name:
  formula:
  charge:
  spin_or_multiplicity:
  geometry_class:
  reference_values:
    bond_lengths:
      - label:
        value_angstrom:
        uncertainty_angstrom:
        source_id:
    angles:
      - label:
        value_degree:
        uncertainty_degree:
        source_id:
    relative_energies:
      - label:
        value_ev:
        source_id:
    barriers:
      - label:
        value_ev:
        source_id:
  sources:
    source_id:
      type: literature/database/website
      title:
      authors:
      year:
      journal_or_database:
      doi:
      url_or_accession:
      notes:
  status: verified/unverified/needs_manual_review
```

If a value is not verified, write `null` and mark `needs_manual_review`. Never guess.

---

## 5. Required Directory Architecture

Inside `D:\Research\Dr.Kulik_MIT`, create the following project structure.

```text
Dr.Kulik_MIT/
│
├── README.md
├── CLAUDE.md
├── pyproject.toml                         # only if this is a standalone project; otherwise do not overwrite existing package config
├── .gitignore
│
├── configs/
│   ├── project_config.yaml
│   ├── qe_molecule_settings.yaml
│   ├── pseudo_manifest_required.yaml
│   └── source_policy.yaml
│
├── references/
│   ├── reference_values_tmc_v0.yaml
│   ├── reference_sources_v0.csv
│   ├── literature_notes/
│   │   └── README.md
│   └── raw_downloads/
│       └── README.md
│
├── structures/
│   ├── initial_xyz/
│   ├── generated_candidates/
│   ├── optimized_xyz/
│   ├── neb_endpoints/
│   └── README.md
│
├── qe/
│   ├── inputs/
│   │   ├── relax/
│   │   └── scf/
│   ├── outputs/
│   │   ├── relax/
│   │   └── scf/
│   ├── workdirs/
│   └── README.md
│
├── data/
│   ├── raw/
│   ├── parsed/
│   ├── processed/
│   ├── features/
│   ├── selected_batches/
│   └── README.md
│
├── models/
│   ├── baseline/
│   ├── uncertainty/
│   └── README.md
│
├── reports/
│   ├── daily_logs/
│   ├── figures/
│   ├── tables/
│   ├── benchmark_reports/
│   ├── actistruct_tmc_benchmark_report_v0.md
│   └── README.md
│
├── scripts/
│   ├── 00_inspect_environment.py
│   ├── 01_bootstrap_project.py
│   ├── 02_scan_pseudos.py
│   ├── 03_collect_reference_stub.py
│   ├── 04_build_initial_structures.py
│   ├── 05_generate_perturbation_candidates.py
│   ├── 06_build_qe_inputs.py
│   ├── 07_parse_qe_outputs.py
│   ├── 08_validate_dataset.py
│   ├── 09_build_features.py
│   ├── 10_train_baseline_surrogate.py
│   ├── 11_estimate_uncertainty.py
│   ├── 12_select_next_candidates.py
│   ├── 13_compare_to_references.py
│   ├── 14_make_benchmark_report.py
│   └── 15_prepare_nebwalk_demo.py
│
├── tests/
│   ├── test_environment.py
│   ├── test_pseudo_manifest.py
│   ├── test_reference_schema.py
│   ├── test_structure_generation.py
│   ├── test_qe_input_builder.py
│   ├── test_qe_parser.py
│   ├── test_dataset_validation.py
│   ├── test_feature_builder.py
│   ├── test_acquisition.py
│   └── fixtures/
│
└── logs/
    ├── bootstrap.log
    ├── dft_runs.log
    ├── parser.log
    ├── ml.log
    └── errors.log
```

Do not copy pseudopotential files into the Git repository. Only store a manifest with absolute/local paths and filenames.

---

## 6. Project Configuration Files

### 6.1 `configs/project_config.yaml`

Create:

```yaml
project:
  name: actistruct_tmc_reliability_benchmark
  root_dir: "D:/Research/Dr.Kulik_MIT"
  actistruct_expected_names:
    - actistruct
    - inverse_active
  benchmark_version: v0

paths:
  pseudo_dir: "D:/Rifat_kh/SSSP_1.3.0_PBE_efficiency"
  structures_dir: structures
  qe_inputs_dir: qe/inputs
  qe_outputs_dir: qe/outputs
  data_dir: data
  references_dir: references
  reports_dir: reports

systems:
  primary:
    - ferrocene
    - ni_co4
    - cr_co6
    - fe_co5
  secondary:
    - v_co6
    - benzene_cr_co3
    - ticl4

policy:
  allow_charged_complexes_phase1: false
  allow_sse17_phase1: false
  allow_ml_final_claims: false
  keep_failed_calculations: true
  require_reference_verification: true
```

### 6.2 `configs/qe_molecule_settings.yaml`

Create a conservative first-pass QE settings file:

```yaml
qe:
  executable: pw.x
  calculation: relax
  functional: PBE
  pseudo_family: SSSP_1.3.0_PBE_efficiency
  ecutwfc_ry: 60
  ecutrho_ry: 480
  occupations: fixed
  smearing: null
  kpoints: [1, 1, 1]
  gamma_only: true
  cell_type: cubic_supercell
  vacuum_padding_angstrom: 12.0
  assume_isolated: mt
  conv_thr: 1.0e-8
  forc_conv_thr: 1.0e-4
  etot_conv_thr: 1.0e-5
  mixing_beta: 0.3
  max_seconds: null
  disk_io: low

closed_shell_phase1:
  nspin: 1
  starting_magnetization: null

required_elements_phase1:
  - Fe
  - C
  - H
  - Ni
  - O
  - Cr
```

If `assume_isolated = mt` causes QE compatibility issues, log the issue and use the safest supported molecular-supercell setting available in the local QE installation.

---

## 7. Required Python Scripts and Responsibilities

Each script must have:

- command-line interface with `argparse`,
- `--dry-run` if file-writing or DFT-running is involved,
- clear logging,
- no hardcoded hidden paths except values loaded from config,
- helpful error messages,
- unit tests or smoke tests.

### 7.1 `scripts/00_inspect_environment.py`

Purpose:

- Print Python version.
- Print current working directory.
- Detect Windows vs WSL path behavior.
- Check import of `actistruct` and `inverse_active`.
- Locate installed package path.
- Check `pw.x` availability.
- Check pseudopotential directory.
- Check core dependencies.

Expected output:

```text
reports/tables/environment_report.json
logs/bootstrap.log
```

### 7.2 `scripts/01_bootstrap_project.py`

Purpose:

- Create the directory architecture.
- Create placeholder README files.
- Create default config files if missing.
- Never overwrite existing important files without backup.

Rules:

- If a file exists, do not overwrite unless `--force` is passed.
- If `--force` is passed, create `.bak` backup first.

### 7.3 `scripts/02_scan_pseudos.py`

Purpose:

- Scan `D:/Rifat_kh/SSSP_1.3.0_PBE_efficiency`.
- Identify pseudopotentials for Fe, C, H, Ni, O, Cr.
- Write a manifest.

Output:

```text
configs/pseudo_manifest_required.yaml
reports/tables/pseudo_scan_report.csv
```

Manifest schema:

```yaml
pseudo_family: SSSP_1.3.0_PBE_efficiency
pseudo_dir: "D:/Rifat_kh/SSSP_1.3.0_PBE_efficiency"
elements:
  Fe:
    filename:
    path:
    exists:
    suggested_ecutwfc_ry:
    suggested_ecutrho_ry:
  C:
    filename:
    path:
    exists:
  H:
    filename:
    path:
    exists:
  Ni:
    filename:
    path:
    exists:
  O:
    filename:
    path:
    exists:
  Cr:
    filename:
    path:
    exists:
status: ready/not_ready
missing_elements: []
```

### 7.4 `scripts/03_collect_reference_stub.py`

Purpose:

- Create structured reference files.
- Search/collect references only if web/API tools are available.
- Otherwise create empty verified schema for manual filling.

Rules:

- Literature values must be source-tagged.
- Database values must include accession IDs.
- Every source must include access date.
- No value without source.
- If uncertain, mark `needs_manual_review`.

Outputs:

```text
references/reference_values_tmc_v0.yaml
references/reference_sources_v0.csv
reports/tables/reference_completeness_report.csv
```

### 7.5 `scripts/04_build_initial_structures.py`

Purpose:

Generate chemically reasonable initial molecular structures for:

- ferrocene,
- Ni(CO)4,
- Cr(CO)6,
- Fe(CO)5.

Preferred method:

- Use internal coordinate builders based on symmetry and approximate literature starting values.
- Save as XYZ and ASE-readable files.
- Mark starting values as initial guesses, not final references.

Outputs:

```text
structures/initial_xyz/ferrocene_initial.xyz
structures/initial_xyz/ni_co4_initial.xyz
structures/initial_xyz/cr_co6_initial.xyz
structures/initial_xyz/fe_co5_initial.xyz
reports/tables/initial_structure_summary.csv
```

### 7.6 `scripts/05_generate_perturbation_candidates.py`

Purpose:

Generate local geometry perturbation candidates for active learning.

Candidate counts:

- Start with 10–20 candidates per complex.
- Do not generate hundreds in phase 1.

Perturbation variables:

Ferrocene:

- Fe–Cp centroid distance,
- Cp ring rotation angle,
- small ring radius perturbation.

Ni(CO)4:

- Ni–C distance,
- C–O distance,
- tetrahedral angle perturbation.

Cr(CO)6:

- Cr–C distance,
- C–O distance,
- axial/equatorial distortion mode.

Fe(CO)5:

- axial Fe–C distance,
- equatorial Fe–C distance,
- axial/equatorial angle,
- Berry-like distortion coordinate.

Outputs:

```text
structures/generated_candidates/*.xyz
data/raw/candidate_manifest_v0.csv
```

Candidate manifest columns:

```csv
candidate_id,complex_id,formula,charge,spin_setting,structure_path,generation_method,variables_json,notes
```

### 7.7 `scripts/06_build_qe_inputs.py`

Purpose:

Build QE input files from generated structures.

Inputs:

- candidate manifest,
- QE settings YAML,
- pseudo manifest.

Outputs:

```text
qe/inputs/relax/{candidate_id}.in
qe/inputs/scf/{candidate_id}.in
qe/run_manifest_v0.csv
```

Rules:

- Use large cubic cell for molecules.
- Use Gamma point.
- Use charge = 0 for all phase-1 systems.
- Use closed-shell first-pass settings.
- Write pseudopotential filenames explicitly.
- Include calculation metadata in comments where possible.

### 7.8 `scripts/07_parse_qe_outputs.py`

Purpose:

Parse QE outputs using ActiStruct/inverse_active if existing parser supports it. If not, write a local parser wrapper but do not duplicate package logic unnecessarily.

Extract:

```text
run_id
candidate_id
complex_id
converged
scf_converged
ionic_converged
n_scf_steps
final_energy_ry
final_energy_ev
energy_per_atom_ev
max_force_ev_a
walltime_sec
warning_flags
failure_reason
final_xyz_path
parser_version
```

Outputs:

```text
data/parsed/parsed_qe_results_v0.csv
structures/optimized_xyz/*.xyz
logs/parser.log
```

### 7.9 `scripts/08_validate_dataset.py`

Purpose:

Validate parsed data before ML.

Checks:

- missing energies,
- missing pseudopotentials,
- non-converged calculations,
- duplicate candidate IDs,
- unrealistic bond lengths,
- extreme energies,
- missing reference source,
- inconsistent charge/spin metadata.

Outputs:

```text
data/processed/full_dataset_v0.csv
data/processed/reliable_subset_v0.csv
reports/dataset_validation_report_v0.md
```

Do not delete bad rows. Add labels:

```text
reliable
usable_with_caution
failed
needs_rerun
outlier
```

### 7.10 `scripts/09_build_features.py`

Purpose:

Build ML features from candidate variables and parsed DFT metadata.

Feature categories:

- complex identity,
- metal identity,
- ligand type,
- geometry class,
- candidate variables,
- bond length descriptors,
- angle descriptors,
- DFT settings for failure-risk model only.

Avoid target leakage.

Outputs:

```text
data/features/features_v0.csv
reports/tables/feature_summary_v0.csv
```

### 7.11 `scripts/10_train_baseline_surrogate.py`

Purpose:

Train baseline models for relative energy within each complex family.

Models:

- RandomForestRegressor baseline,
- GradientBoostingRegressor or XGBoost/CatBoost if available,
- GaussianProcessRegressor only if dataset size is small and stable.

Targets:

- relative energy within same complex family,
- optional convergence/failure label.

Outputs:

```text
models/baseline/*.pkl
reports/ml_baseline_report_v0.md
reports/tables/ml_metrics_v0.csv
reports/figures/parity_plot_v0.png
```

If the dataset is too small, write a clear warning and do not report misleading R2.

### 7.12 `scripts/11_estimate_uncertainty.py`

Purpose:

Estimate uncertainty using ensemble or bootstrap models.

Outputs:

```text
data/processed/predictions_with_uncertainty_v0.csv
reports/uncertainty_report_v0.md
reports/figures/uncertainty_vs_error_v0.png
```

Do not claim calibrated uncertainty unless coverage is measured.

### 7.13 `scripts/12_select_next_candidates.py`

Purpose:

Implement acquisition-based candidate selection.

For minimization:

```text
score = predicted_relative_energy - alpha * uncertainty + beta * failure_risk - gamma * diversity_bonus
```

Each selected candidate must include a reason:

```text
best predicted low-energy candidate
high-uncertainty exploration candidate
chemically diverse candidate
low-failure-risk candidate
reference/control candidate
```

Outputs:

```text
data/selected_batches/next_dft_batch_v0.csv
reports/batch_selection_rationale_v0.md
```

### 7.14 `scripts/13_compare_to_references.py`

Purpose:

Compare optimized DFT geometries and relative energies to verified references.

Metrics:

- metal–ligand bond length error,
- ligand internal bond length error,
- key angle error,
- conformer energy difference if available,
- RMSD if alignment is reliable.

Outputs:

```text
reports/tables/reference_comparison_v0.csv
reports/reference_comparison_report_v0.md
```

If reference data are incomplete, clearly state what is missing.

### 7.15 `scripts/14_make_benchmark_report.py`

Purpose:

Generate a short technical report in Markdown.

Output:

```text
reports/benchmark_reports/actistruct_tmc_benchmark_report_v0.md
```

Required sections:

1. Motivation
2. Benchmark systems
3. Source/reference strategy
4. DFT settings
5. ActiStruct workflow
6. Candidate generation
7. Parsing and reliability labels
8. ML baseline
9. Uncertainty
10. Active-learning selection
11. Reference comparison
12. Failure analysis
13. nebwalk demo status
14. Limitations
15. Next steps

### 7.16 `scripts/15_prepare_nebwalk_demo.py`

Purpose:

Prepare only one nebwalk pathway after reliable endpoints exist.

Allowed phase-1 pathways:

1. Ferrocene Cp-ring rotation.
2. Fe(CO)5 Berry pseudorotation-like pathway.

Preferred first choice:

```text
ferrocene Cp-ring rotation
```

Rules:

- Do not run nebwalk before ActiStruct endpoints are validated.
- Do not claim final barrier accuracy from MLIP.
- If using MLIP/MACE, label it as pre-screening only.
- Final claims require QE/PBE validation.

Outputs:

```text
structures/neb_endpoints/
reports/nebwalk_demo_plan_v0.md
```

---

## 8. Tests and Sanity Checks

Create and run tests after each module.

Minimum tests:

```text
pytest tests/test_environment.py
pytest tests/test_pseudo_manifest.py
pytest tests/test_reference_schema.py
pytest tests/test_structure_generation.py
pytest tests/test_qe_input_builder.py
pytest tests/test_qe_parser.py
pytest tests/test_dataset_validation.py
pytest tests/test_feature_builder.py
pytest tests/test_acquisition.py
```

Every script must pass:

```bash
python scripts/<script_name>.py --help
```

Every file-writing script must pass:

```bash
python scripts/<script_name>.py --dry-run
```

Before generating QE inputs:

- verify all required pseudopotentials exist,
- verify all structures can be read by ASE,
- verify charge and spin metadata exist,
- verify output directories exist.

Before training ML:

- verify dataset has enough rows,
- verify target column exists,
- verify no target leakage,
- verify failed rows are not mixed into regression training unless intentionally handled.

---

## 9. Git and File Safety Rules

Use Git safely.

Recommended branch:

```text
feature/tmc-reliability-benchmark
```

Commit after each stable milestone:

```text
chore: add TMC benchmark project scaffold
feat: add pseudo manifest scanner
feat: add neutral TMC initial structure builders
feat: add QE input generation for molecular benchmarks
test: add sanity tests for TMC workflow
feat: add QE parser wrapper and dataset validation
docs: add ActiStruct TMC benchmark plan
```

Never commit:

- pseudopotential files,
- huge QE outputs unless intentionally tracked outside Git or via Git LFS,
- private API keys,
- temporary scratch files,
- fabricated reference data,
- failed experimental scripts in root directory.

Add to `.gitignore`:

```gitignore
*.UPF
*.upf
qe/workdirs/
qe/outputs/**/*.wfc*
qe/outputs/**/*.save/
*.tmp
*.bak
__pycache__/
.venv/
.env
.env.*
*.pkl
*.joblib
```

Keep model files if small and intentional; otherwise store only instructions to reproduce them.

---

## 10. Daily Workflow for Claude Code

At the start of each session:

1. Read this `CLAUDE.md`.
2. Check current Git status.
3. Inspect current directory tree.
4. Summarize what already exists.
5. Identify the next smallest safe task.
6. Propose files to edit.
7. Implement only after the plan is clear.
8. Run relevant tests.
9. Fix bugs immediately.
10. Write a short daily log.

Daily log file:

```text
reports/daily_logs/YYYY-MM-DD.md
```

Daily log format:

```markdown
# Daily Log — YYYY-MM-DD

## Goal

## Files changed

## Commands run

## Tests passed

## Results generated

## Scientific meaning

## Bugs found and fixed

## Known limitations

## Next action
```

---

## 11. Initial Execution Order

Claude Code should execute in this order.

### Step 1 — Inspect

```bash
python --version
python -c "import os; print(os.getcwd())"
python -c "import importlib.util; print('actistruct', importlib.util.find_spec('actistruct')); print('inverse_active', importlib.util.find_spec('inverse_active'))"
where pw.x
```

On Git Bash/WSL, use equivalent commands.

### Step 2 — Bootstrap

Create:

```text
configs/
references/
structures/
qe/
data/
models/
reports/
scripts/
tests/
logs/
```

### Step 3 — Scan Pseudos

Run pseudo scanner and confirm Fe, C, H, Ni, O, Cr exist.

### Step 4 — Create Reference Stub

Create reference schema with empty verified fields. Do not fabricate values.

### Step 5 — Generate Initial Structures

Generate four initial molecular structures.

### Step 6 — Run Dry QE Input Build

Generate input files in dry-run mode first.

### Step 7 — Run Real QE Input Build

Only after dry-run passes.

### Step 8 — Parse Outputs

After Rifat runs QE calculations, parse outputs and generate dataset.

### Step 9 — Validate Dataset

Label reliable, caution, failed, needs_rerun, outlier.

### Step 10 — ML/Uncertainty/AL

Only after enough DFT rows exist.

### Step 11 — nebwalk Demo

Only after reliable endpoints exist.

---

## 12. Done Criteria for Phase 1

Phase 1 is successful only when all of the following exist:

- project scaffold created,
- ActiStruct/inverse_active import verified,
- pseudopotential manifest ready,
- four initial structures generated,
- QE inputs generated for all four systems,
- reference schema created with source-tracking,
- parser can parse at least one completed QE output,
- dataset validation works,
- at least one small active-learning ranking table exists,
- one short benchmark report exists,
- all scripts have dry-run/help mode,
- tests pass,
- limitations are written clearly.

---

## 13. Professor-Safe Final Wording

Use this wording in reports:

> This project presents an early-stage reliability-aware active-learning workflow for DFT-guided transition-metal complex optimization. The workflow does not replace electronic-structure calculations. Instead, it organizes DFT inputs and outputs, tracks convergence and failure behavior, estimates uncertainty, and selects informative candidate geometries for validation. The first benchmark focuses on neutral organometallic complexes to keep the demonstration chemically controlled and reproducible.

Do not write:

> This tool discovers new transition-metal catalysts with minimal error.

Do not write:

> This workflow solves DFT uncertainty.

Do not write:

> nebwalk gives accurate transition states for all organometallic reactions.

---

## 14. Final Reminder to Claude Code

Be conservative, reproducible, and precise.

The goal is to help Rifat produce a serious research signal, not a flashy but fragile demo.

Every generated file should make the project more trustworthy.
