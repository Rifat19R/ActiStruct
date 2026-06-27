# ActiStruct v0.7.2 QE-Free Dry-Run Live-Candidate Selector

**No QE/PBE was run. No live validation has started. No completed
historical records were reused as future candidates. No
prediction/acquisition values were fabricated.** These four statements
hold for every row produced by this task; see Section 10 for the full
safe-claim list.

## 1. Objective

Produce a small, schema-valid candidate-proposal table for human review,
without running QE/DFT and without reusing completed/historical records as
if they were unresolved future candidates — addressing the gap the v0.7.1
audit identified (no standing future-candidate pool exists).

## 2. Relation to v0.7 and v0.7.1

`reports/live_qe_validation_batch_design_v070.md` defined the 16-field
candidate schema and explicitly declined to populate real candidates.
`reports/live_candidate_source_audit_v071.md` confirmed systematically that
no file in the repository is a valid standing future-candidate pool, and
recommended (Option B) building a small dry-run selector before any real
live batch. This report and its script are that dry-run selector.

## 3. Whether Existing Proposal Machinery Was Usable

Investigated directly: `qe_active_inverse_common.py::_propose_inverse()`
is pure math (differential evolution / failure-aware ranking over an
already-trained `GPModel`) and does not itself call QE. However, it
requires a `GPModel` trained on real `(params, energy)` pairs. Those pairs
exist in this environment only as local, **gitignored**
`outputs/cache/*.pkl` files (confirmed: `git ls-files outputs/cache` returns
nothing — 58 cache files exist on disk here but zero are committed to the
repository). Depending on them would make this script non-portable for any
other researcher cloning the repo, and would also violate the "no
local-machine-path dependence" testing requirement. Fabricating energies to
bootstrap a GP instead would be fabricating a scientific result.

**Decision: Approach B.** The real proposal machinery is not safely
isolatable here without either a portability violation or fabrication. No
existing proposal/ranking code was bypassed or modified — it simply was not
the safest tool for this specific, QE-free, portable dry-run.

## 4. Dry-Run Generation Method

`analysis/dry_run_live_candidate_selector_v072.py`:

1. Imports a small, fixed set of existing `generated_models/*.py` workflow
   modules. Importing them is safe and already relied upon by
   `tests/test_generated_workflows.py` for all 50 workflows — each module
   only builds an `ActiveSystem` at import time; QE is launched only inside
   an `if __name__ == "__main__":` guard, never on import.
2. For each planned candidate, computes one design-variable value as
   `lo + frac * (hi - lo)` for an explicit, hardcoded fraction, using each
   workflow's real, documented `Variable.lo`/`Variable.hi` range.
3. **Checks every computed value against that workflow's documented
   `Variable.initial` seed values** and raises an error if it collides
   (within 1e-6) — a programmatic guard against accidentally presenting an
   already-used design point as if it were unresolved. All current
   fractions were verified not to collide.
4. Fills `material_id`, `material_family`, `formula_composition`,
   `structure_source`, `DFT_settings_profile`, and `pseudopotential_family`
   from the real, already-committed workflow definition — these are real
   metadata, not placeholders.
5. Leaves every science field (`predicted_value`, `uncertainty_lcb_score`,
   `failure_risk`, `acquisition_score`) explicitly as the literal string
   `not_computed`.

No QE/DFT call, no GP training, no cache file access, and no network
access occur anywhere in this script.

## 5. Candidate Schema

`data/dry_run_live_candidates_v072.csv` uses the v0.7 schema (with
`formula_composition` and `uncertainty_lcb_score` as CSV-safe column names,
per this task's instruction):

```text
candidate_id, material_id, material_family, formula_composition,
structure_source, candidate_variables, predicted_value,
uncertainty_lcb_score, failure_risk, acquisition_score, selection_reason,
selection_category, DFT_settings_profile, pseudopotential_family,
expected_runtime_risk, status, notes
```

## 6. Candidate Table Summary

9 rows, across 5 materials and the 5 v0.7 design categories:

| candidate_id | material_id | selection_category | candidate_variables |
| --- | --- | --- | --- |
| `dryrun_bulk_al_qe_active_inverse_1` | bulk_al | exploitation | a=3.9500 |
| `dryrun_bulk_al_qe_active_inverse_2` | bulk_al | exploitation | a=4.1250 |
| `dryrun_mos2_qe_active_inverse_1` | mos2 | uncertainty_exploration | a=3.0625; layer_half_thickness=1.4750 |
| `dryrun_mos2_qe_active_inverse_2` | mos2 | uncertainty_exploration | a=3.2875; layer_half_thickness=1.6750 |
| `dryrun_bulk_mgo_generated_qe_active_inverse_1` | bulk_mgo_generated | low_failure_risk | a=4.1400 |
| `dryrun_bulk_mgo_generated_qe_active_inverse_2` | bulk_mgo_generated | low_failure_risk | a=4.2625 |
| `dryrun_bulk_si_generated_qe_active_inverse_1` | bulk_si_generated | failure_risk_challenge | a=5.2400 |
| `dryrun_bulk_si_generated_qe_active_inverse_2` | bulk_si_generated | failure_risk_challenge | a=5.5600 |
| `dryrun_graphene_generated_qe_active_inverse_1` | graphene_generated | diversity | a=2.5000 |

Every row has `predicted_value`/`uncertainty_lcb_score`/`failure_risk`/
`acquisition_score` = `not_computed`, `status` = `dry_run_only`, and a
`notes` field stating it is not selected for QE/PBE execution and requires
human review.

## 7. Fields Computed vs Pending

| Field | Status |
| --- | --- |
| `candidate_id`, `material_id`, `material_family`, `formula_composition`, `structure_source`, `DFT_settings_profile`, `pseudopotential_family` | **Computed** — read directly from the real, committed `generated_models/*.py` workflow definitions. |
| `candidate_variables` | **Computed** — arithmetic placeholder within the documented range, verified not to collide with documented seed values. |
| `selection_category` | **Computed** — assigned by this script's plan, but reflects design *intent* only, not a score. |
| `selection_reason` | **Computed** — explicit text per category, stating plainly that no real scoring occurred. |
| `predicted_value`, `uncertainty_lcb_score`, `failure_risk`, `acquisition_score` | **Pending** — explicitly `not_computed`; require a real, live (or cache-backed, portable) GP/LCB + classifier run. |
| `expected_runtime_risk` | **Pending** — `not_computed`; a qualitative judgment not made here. |
| `status` | **Computed** — `dry_run_only` for every row. |
| `notes` | **Computed** — explicit non-execution/review-required statement for every row. |

## 8. Why No QE/PBE Was Run

This task is explicitly design/selection-only. Running QE/DFT was a hard
constraint violation regardless of convenience; no `pw.x`, `mpirun`, or any
external DFT command was invoked anywhere in this script, its tests, or
this report. Verified by inspection of the script's imports (only
`csv`, `importlib`, `sys`, `pathlib`, plus the repo's own
`generated_models` package) and by the absence of any subprocess/execution
call.

## 9. What Must Happen Before Real Live Validation

1. A real, portable way to obtain training `(params, energy)` pairs without
   depending on local gitignored caches — e.g., committing a small,
   explicitly-labeled seed dataset, or accepting that the first live batch
   trains on whatever local cache exists on the machine that runs it.
2. Running the real GP/LCB proposal path
   (`qe_active_inverse_common.py::_propose_inverse`) live, with
   `failure_risk_provider` configured, to replace this report's
   placeholder `candidate_variables`/`selection_category` rows with real
   `predicted_value`/`uncertainty_lcb_score`/`failure_risk`/
   `acquisition_score` numbers.
3. Human review of the resulting real candidates against the go/no-go
   checklist in `reports/live_qe_validation_batch_design_v070.md` Section
   11.
4. Only then, submission to QE/PBE — preserving every outcome, including
   failures, per existing project policy.

## 10. Safe Claims

```text
No QE/PBE was run.
No live validation has started.
No completed historical records were reused as future candidates.
No prediction/acquisition values were fabricated.
These rows are proposal-review artifacts only. They are not QE/PBE inputs
and must not be treated as validated candidates.
```

## 11. Unsafe Claims Avoided

This report and script do not claim, anywhere:

```text
that these candidates have been scored by a real GP/LCB or failure-risk model,
that live validation has started,
that live DFT savings have been demonstrated,
that any new material has been discovered,
that the selection_category labels reflect anything beyond placeholder design intent.
```

## 12. Next Recommended Step

Address Section 9 item 1 first (a portable, non-fabricated source of
training data) before attempting to run the real GP/LCB proposal path. Only
after that is resolved should a v0.7.3-or-later task attempt to produce
*scored* (not placeholder) candidate rows — still without running QE/DFT,
since scoring itself requires no new DFT calculation, only a trained
surrogate.
