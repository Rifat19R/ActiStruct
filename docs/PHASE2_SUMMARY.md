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

## Next action

Dataset preparation: build on `data/processed/initial_relax_parsed_v0.1.csv`/`.json` for the next pipeline stage (dataset validation / reliability labeling per `CLAUDE_ACTISTRUCT_TMC_PLAN.md` Sec 7.9, `scripts/08_validate_dataset.py`) once more QE data exists, or proceed per Rifat's direction.
