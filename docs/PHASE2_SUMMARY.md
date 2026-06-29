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

## Step 3: reference validation (`scripts/13_compare_to_references.py`) - Phase 2A

Rifat redirected the plan: no ML pipeline until the benchmark is scientifically trustworthy (Phase 2A = reference validation, Phase 2B = perturbation review, later phases = expanded QE campaign, ML infra, then AL only after ~30-50 validated calculations). This section covers Phase 2A.

### Reference values populated from real literature (2026-06-29)

`references/reference_values_tmc_v0.yaml` was filled in using `WebSearch`/`WebFetch` (not memorized training data) - every DOI was independently checked to actually resolve via `doi.org` redirect before being recorded:

| System | Bond | Literature value | Source |
|---|---|---|---|
| ferrocene | Fe-C | 2.064 A | CRC Handbook 85th ed., citing Haaland & Nilsson 1968 (Acta Chem. Scand. 22, 2653, DOI `10.3891/acta.chem.scand.22-2653`) |
| ferrocene | C-C (Cp ring) | 1.440 A | same |
| ni_co4 | Ni-C | 1.838(2) A | Hedberg, Iijima, Hedberg 1979 (J. Chem. Phys. 70, 3224, DOI `10.1063/1.437911`) |
| ni_co4 | C-O | 1.141(2) A | same |
| cr_co6 | Cr-C | 1.916 A | Whitaker & Jeffery 1967 (Acta Cryst. 23, 977, DOI `10.1107/S0365110X67004153`) - 2 more neutron-diffraction sources listed for future cross-checking |
| cr_co6 | C-O | 1.171 A | same |
| fe_co5 | Fe-C axial/equatorial | 1.810(16) / 1.842(11) A | McClelland et al. 2001 (Inorg. Chem. 40, 1358, DOI `10.1021/ic001114e`) |
| fe_co5 | C-O axial/equatorial | 1.142(23) / 1.149(16) A | same |

Honesty constraint: most primary-source PDFs are publisher-paywalled and could not be opened directly (HTTP 403 on AIP/ACS/Wiley), so exact uncertainty digits are recorded only where directly quoted from an accessible abstract (ni_co4, fe_co5); ferrocene/cr_co6 values are real and DOI-verified but uncertainty is `null`. **`status` stays `needs_manual_review` for all 4 systems** - an AI web-fetch summary is not sufficient grounds to self-certify "verified"; Rifat should manually pull the PDFs to confirm before using these in any external communication (e.g. to Prof. Kulik).

`tests/test_reference_data_integrity.py` (7 tests): DOI format/non-placeholder checks, source_id cross-references resolve, status correctly still requires manual review, uncertainty magnitudes are plausible, sources CSV/YAML stay consistent, and literature values themselves pass the same generic bond-length sanity ranges used on QE results.

### Comparison script and results

`scripts/13_compare_to_references.py` measures bond lengths directly from each system's relaxed geometry (`final_positions_angstrom`) and compares to the literature values above. Measurement is purely geometric - e.g. Fe(CO)5's axial-vs-equatorial split is determined from which `C-Fe-C` angle is closest to 180 degrees (verified rotation-invariant in tests), never from a hardcoded atom index or coordinate axis.

**Result: all 4 systems `validated`** (within this project's stated tolerance of 0.03 A absolute OR 3% relative, whichever is looser):

| System | Bond | QE (A) | Literature (A) | Delta (A) | % Error |
|---|---|---|---|---|---|
| ferrocene | Fe-C | 2.0437 | 2.0640 | -0.0203 | -0.98% |
| ferrocene | C-C (Cp ring) | 1.4340 | 1.4400 | -0.0060 | -0.42% |
| ni_co4 | Ni-C | 1.8119 | 1.8380 | -0.0261 | -1.42% |
| ni_co4 | C-O | 1.1504 | 1.1410 | +0.0094 | +0.82% |
| cr_co6 | Cr-C | 1.9001 | 1.9160 | -0.0158 | -0.83% |
| cr_co6 | C-O | 1.1540 | 1.1710 | -0.0170 | -1.45% |
| fe_co5 | Fe-C axial | 1.8025 | 1.8100 | -0.0075 | -0.41% |
| fe_co5 | Fe-C equatorial | 1.8004 | 1.8420 | -0.0416 | -2.26% |
| fe_co5 | C-O axial | 1.1527 | 1.1420 | +0.0107 | +0.94% |
| fe_co5 | C-O equatorial | 1.1556 | 1.1490 | +0.0066 | +0.58% |

All deviations are sub-2.3%, consistent with typical PBE-GGA vs. experiment agreement for 3d-metal carbonyls/sandwich compounds. Outputs: `reports/tables/reference_comparison_v0.csv`, `reports/reference_validation_v0.1.md`, and `data/processed/full_dataset_v0.1.csv` (script 08's labels upgraded `usable_with_caution` -> `validated` for all 4, additive - the original `full_dataset_v0.csv` is untouched).

A real bug was caught and fixed while building the verdict logic: the first version required every compared bond's source to carry a DOI specifically, which incorrectly failed ferrocene (CRC Handbook citations don't have DOIs but are still fully documented print references). Fixed via `is_source_documented()`, which accepts DOI OR URL OR a complete print citation (title+authors+year+journal).

`tests/test_reference_comparison.py` (9 tests): nearest-neighbor measurement correctness, rotation-invariance of the axial/equatorial classifier (a synthetic structure rotated by an arbitrary axis/angle must classify the same atoms as axial), tolerance-flagging on a deliberately-wrong synthetic reference value, and end-to-end validation that the real dataset reaches `validated`. **75/75 tests pass total.**

## Phase 2B.0: candidate quality audit (`scripts/05b_audit_perturbation_candidates.py`)

Per Rifat's explicit quality gate, added before generating any QE inputs for the 52 perturbation candidates: classify every candidate's perturbation family/magnitude/expected physical effect, reject anything chemically unreasonable (atom overlaps, unrealistic bond lengths reusing script 08's topology-aware checker, duplicate geometries via pairwise RMSD), then select a family-diverse representative subset rather than running all 52.

**Result: all 52 candidates accepted** (0 rejected) - genuinely expected, not a sign the checks are broken: script 05's perturbation magnitudes were deliberately conservative, and angle-type perturbations preserve bond length by construction (`rotate_vector` only changes direction, not magnitude). Verified the rejection logic actually works via synthetic bad-structure tests (a deliberately dissociated Ni-C bond, two atoms 0.1 A apart) - both correctly flagged.

**12 representatives selected** (3 per system x 4 systems), one per perturbation family, picking the largest-magnitude *accepted* candidate in each family. A real diversity bug was caught and fixed during development: naive magnitude tie-breaking always picked the negative-delta candidate (since negative deltas are listed first in script 05's per-family lists), so the first version of the selection explored only the compression direction for every single family - directly defeating the "span the perturbation space" goal. Fixed by alternating which sign is preferred across a system's families, so the selected set now covers both compression/elongation (or positive/negative angle) directions per system - verified by an explicit test (`test_real_audit_selected_set_spans_both_signs_per_system`).

| System | Selected (family: magnitude) |
|---|---|
| ferrocene | Fe-Cp stretch: -0.05 A; Cp ring rotation: +36 deg; Cp ring radius: -0.03 A |
| ni_co4 | Metal-ligand stretch: +0.06 A; C-O stretch: -0.04 A; Tetrahedral angle: -6 deg |
| cr_co6 | Metal-ligand stretch: +0.06 A; C-O stretch: -0.04 A; Axial/equatorial distortion: -0.05 A |
| fe_co5 | Axial Fe-C: -0.06 A; Equatorial Fe-C: +0.06 A; Equatorial angle: -6 deg |

fe_co5's "Berry-pseudorotation-like tilt" family was deliberately excluded from selection (not by audit failure) - it's explicitly documented in script 05 as a heuristic, non-validated coordinate, deprioritized in favor of the 3 more standard families for the first follow-up campaign.

Outputs: `data/processed/candidate_audit_v0.csv` (all 52, classified + audit status), `reports/candidate_audit_report_v0.md`. `tests/test_candidate_audit.py`: 15 tests (classification correctness, both rejection paths verified on synthetic bad data, duplicate detection, sign-alternation, and end-to-end checks on the real 52-candidate audit). **90/90 tests pass total.**

## Next action (Phase 2B, pending Rifat's approval of the 12 selected candidates)

Once the 12 representatives above are approved: generate their QE relax inputs (reusing `scripts/06_build_qe_inputs.py`'s machinery, extended to take arbitrary candidate structures rather than just the 4 initial ones), prepare batch execution scripts, then Rifat runs them. That expands the dataset to ~16 DFT points (4 reference + 12 perturbations) - still small, but enough to exercise the parser/dataset-validation/reference-comparison pipeline on non-trivial data. No ML pipeline work until after that campaign runs (per Rifat's staging: Stage 4 = ML infrastructure with an explicit "not yet scientifically meaningful" disclaimer, Stage 5 = active learning only after ~30-50 validated calculations).
