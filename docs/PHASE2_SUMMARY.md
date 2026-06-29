# Phase 2 Summary — ActiStruct-nebwalk TMC Reliability Benchmark

**Date started:** 2026-06-29
**Repo:** `D:/Research/Dr.Kulik_MIT`
**Branch:** `feature/tmc-reliability-benchmark`
**Trigger:** Phase 1 closed with all 4 primary systems converged via real `pw.x` (see `docs/PHASE1_SUMMARY.md`).

## Step 1: production QE output parser (`scripts/07_parse_qe_outputs.py`)

Recursively scans a directory (default `runs/initial_relax/`) for any file containing a QE `Program PWSCF` banner (content-based detection, not filename-based) and extracts, per job:

`parser_version`, `system_id`, `input_filename`, `output_filename`, `error_filename`, `job_done`, `convergence_status`, `final_energy_ry`, `final_energy_ev`, `ionic_steps`, `scf_iterations_total`, `max_force_ry_per_bohr`, `wall_time_sec`, `final_lattice_angstrom`, `final_positions_angstrom`, `warnings`, `failures`.

Outputs:
- `data/processed/initial_relax_parsed_v0.1.csv` (nested fields JSON-encoded per cell)
- `data/processed/initial_relax_parsed_v0.1.json` (native nested structures)
- `reports/parser_summary_v0.1.md` (generated programmatically from the parsed records, not hand-written, so it can't drift from the actual data)

### Parsed results (real data, 2026-06-29)

| system_id | convergence | job_done | final_energy_ry | ionic_steps | scf_iterations_total | max_force_ry_per_bohr | wall_time_sec |
|---|---|---|---|---|---|---|---|
| cr_co6 | converged | True | -536.0152471419 | 7 | 182 | 3.7e-05 | 4620.0 |
| fe_co5 | converged | True | -629.6772928617 | 10 | 254 | 0.000109 | 5940.0 |
| ferrocene | converged | True | -525.3618442398 | 15 | 319 | 3.3e-05 | 4980.0 |
| ni_co4 | converged | True | -583.5691160575 | 7 | 238 | 2.3e-05 | 3220.07 |

0 failures across all 4. Warnings collected: `negative_rho` observed in all 4 (informational, not fatal); `ni_co4` and `fe_co5` still carry the `ibrav=0 ... DISCOURAGED` warning because their saved real outputs predate the `ibrav=1` fix (they converged fine anyway and were not rerun - their data is valid, just generated before that particular fix existed).

### Design decisions (never-fabricate compliance)

- **Convergence status** is only ever set from QE's own explicit text (`bfgs converged` / `bfgs failed` / `convergence has been achieved` + `JOB DONE` for plain SCF). Never inferred from energy or force values.
- **`final_energy_ry`** prefers the one-time `Final energy` BFGS summary line (highest precision QE prints); falls back to the last `!  total energy` SCF line only if no BFGS summary exists. Verified these are the same value to printed precision in real data (e.g. cr_co6: `-536.01524714` vs `-536.0152471419`).
- **`scf_iterations_total`** counts every `iteration #` line in the file (total electronic iterations across all ionic steps) - explicitly not the same as the `N scf cycles` count in QE's own BFGS summary line, which is closer to the ionic-step count. Documented in the generated report so this isn't ambiguous later.
- **Geometry** (`final_lattice_angstrom`, `final_positions_angstrom`) parsed via ASE's `espresso-out` reader, only attempted when `JOB DONE` is present, `null` otherwise rather than guessing from a partial/crashed trajectory.
- Every field absent from the source text is `null`, never a placeholder or estimate.

### Test fixtures

`tests/fixtures/qe_outputs/{ferrocene,ni_co4,cr_co6,fe_co5}/` - exact copies of the real converged outputs/errs from `runs/initial_relax/`, used as ground-truth fixtures.

`tests/fixtures/qe_outputs/synthetic_failures/` - two hand-written, clearly-labeled **synthetic** (not real DFT data) QE-output-like text fixtures used only to exercise the parser's failure-detection paths:
- `bfgs_failed.relax.out` - mimics the real cr_co6 BFGS-failure text pattern (`bfgs failed after N scf cycles and M bfgs steps`).
- `mpi_crash.relax.out` / `.relax.err` - mimics the real ferrocene 9p-mount crash (`create_directory` error banner, no `JOB DONE`, non-empty stderr with `MPI_ABORT`).

`tests/test_qe_parser.py` - 13 tests covering: QE-output detection (content-based, ignores non-QE files), wall-time string parsing, all 4 real systems' energy/convergence/geometry extraction matching known values, the `ibrav=0` warning correctly appearing only for ni_co4/fe_co5, both synthetic failure paths, null-not-fabricated behavior on a minimal/empty fixture, CSV JSON-encoding round-trip, and report-generation counts matching input records.

**41/41 tests pass** (28 from phase 1 + 13 new parser tests).

## Step 2: dataset validation (`scripts/08_validate_dataset.py`)

Reads `data/processed/initial_relax_parsed_v0.1.json` and labels every row `reliable` / `usable_with_caution` / `failed` / `needs_rerun` / `outlier`, per `CLAUDE_ACTISTRUCT_TMC_PLAN.md` Sec 7.9. Rows are never deleted - only labeled, with specific reasons recorded. Checks implemented: missing energy/geometry, non-converged, duplicate `system_id`, unrealistic bond lengths, extreme (implausibly small) energy, missing pseudopotentials, missing/unverified reference source, and surfaces every parser warning/failure.

Outputs `data/processed/full_dataset_v0.csv` (all rows + `label`/`validation_issues`), `data/processed/reliable_subset_v0.csv` (rows with `label == reliable`), and `reports/dataset_validation_report_v0.md` (programmatically generated, same pattern as the parser summary).

### Result on real data (2026-06-29)

All 4 systems land in **`usable_with_caution`** - none reach `reliable` yet, and that's the correct, intentional outcome: `policy.require_reference_verification: true` plus every system still being `needs_manual_review` in `references/reference_values_tmc_v0.yaml` caps everything below `reliable` until real literature/database comparison happens. No bond-length or energy red flags on any system - the underlying QE relaxes are sound. The only caveats surfaced are already-known ones: ni_co4/cr_co6's pseudopotential naming caution, and the (harmless, pre-`ibrav=1`-fix) `DISCOURAGED` warning text still present in ni_co4/fe_co5's saved real outputs.

### A real bug caught and fixed during development

The first version of the bond-length sanity check used a flat distance-pair approach (any two atoms of a relevant element pair within a fixed radius) and produced **30+ false positives on ferrocene** - it was catching non-bonded 1,3-transannular C-C/C-H distances across the Cp ring (~2.3 A) as if they were real bonds. After narrowing to nearest-neighbor-only checking, a *second* false-positive class appeared: Ni(CO)4/Cr(CO)6/Fe(CO)5 were flagged for "unrealistic" C-C bonds, because their carbonyl carbons aren't bonded to each other at all (only to the metal and their own O) - the "nearest C-C" found was just the closest non-bonded inter-ligand distance. Fixed by making bond checks system-topology-aware (`EXPECTED_BOND_PAIRS`, derived from how `scripts/04_build_initial_structures.py` actually built each molecule, not an external claim) rather than assuming any element pair with a defined sanity range must be bonded everywhere it appears. `tests/test_dataset_validation.py` includes explicit regression tests for both false-positive classes plus a true-positive check (an artificially stretched Ni-C bond is still correctly flagged).

`tests/test_dataset_validation.py`: 18 tests (bond-topology false-positive regressions, reference/pseudopotential check units, all 6 `classify()` label paths, and end-to-end validation of the real 4-system dataset). **59/59 tests pass total** (41 prior + 18 new).

## Next action

Dataset is validated and labeled. Next per the plan is feature building (`scripts/09_build_features.py`) - but with only 4 labeled rows total, this is far below any reasonable threshold for ML/uncertainty work (per the standing caution in `project-actistruct-kulik-plan` memory). Reasonable next steps in order of value: (1) get the missing reference values collected/verified to actually unlock `reliable` status, (2) generate more QE data (the 52 perturbation candidates from script 05 already exist and are unused), or (3) proceed to feature building anyway if Rifat wants to validate the pipeline mechanics ahead of having enough data for real model training.
