# ActiStruct v0.7.1 Candidate-Source Audit for Future Live QE/PBE Validation

**No QE/DFT was run to produce this document.** This is a read-only audit:
every file below was inspected, not modified, and no candidate data was
fabricated. No real candidates were selected.

## 1. Objective

Answer one question precisely: does ActiStruct currently contain a valid,
unresolved candidate pool that a future live QE/PBE validation batch
(`reports/live_qe_validation_batch_design_v070.md`) could select real
candidates from, or is a new candidate-generation/selection step needed
first?

## 2. Why This Audit Is Needed

The v0.7 design report explicitly declined to populate real candidates,
reasoning informally that the existing v0.5.0/v0.5.1 benchmark data is
historical. This audit checks that reasoning systematically against every
candidate-like file in the repository, rather than against memory of a few
files, so the v0.7.2 recommendation rests on a complete inventory.

## 3. Files/Directories Inspected

```bash
find . -maxdepth 4 -type f | grep -Ei "candidate|selected|proposal|next|batch|rank|acquisition|lcb|qe_input|workflow|inverse|grid|results|csv|json|yaml|yml|md"
```

No `selected_candidates/`, `qe_inputs/`, or `workflows/` directory exists.
Directories/files actually inspected:

```text
data/ (all *.csv)
reports/ (all *.md)
analysis/ (scripts + analysis/outputs/raw/*.csv, analysis/outputs/tables/*)
examples/manual_qe/*.py
templates/live_validation_batch_schema_v070.csv
generated_models/*.py (50 workflow definitions) + qe_active_inverse_common.py
actistruct/parsers/qe.py, actistruct/datasets/qe_records.py, actistruct/acquisition/reliability.py
outputs/cache/*.pkl (local, gitignored — not committed; inspected by directory listing only)
```

## 4. Candidate-Source Classification Table

| Path | Type/category | Contains real candidates? | Contains completed outcomes? | Safe for future live selection? | Reason | Next action |
| --- | --- | --- | --- | --- | --- | --- |
| `data/parsed_records/qe_reliability_records.csv` | historical_completed_records | yes (976 records) | yes (`converged`, `final_energy_ry`, `failure_reason`) | no | every row is an already-finished QE calculation | use only as training data for reliability modeling |
| `data/parsed_records/qe_invalid_geometry_records.csv` | historical_completed_records | yes (90 records) | yes (rejected pre-QE for atomic overlap) | no | already-resolved, quarantined outcomes | keep quarantined; do not reuse as live candidates |
| `data/qe_reliability_ml_table.csv` | historical_completed_records | yes (derived from above) | yes (`success` label column) | no | feature table built from completed records | training data only |
| `data/qe_reliability_predictions_v02.csv` | offline_benchmark_records | yes (predictions on completed rows) | yes (`true_failure`/equivalent ground truth present) | no | classifier predictions evaluated against known outcomes | offline classifier evaluation only |
| `data/qe_reliability_predictions_v03.csv` | offline_benchmark_records | yes | yes | no | same as above (v0.3 generalization test) | offline classifier evaluation only |
| `data/qe_reliability_predictions_v032.csv` | offline_benchmark_records | yes | yes (`true_failure`, `failure_label`) | no | same as above (v0.3.2, repeated group splits) | source data for v0.5.0/v0.5.1 benchmarks only |
| `data/qe_reliability_group_split_predictions_v031.csv` | offline_benchmark_records | yes | yes | no | v0.3.1 diagnosis predictions on held-out groups | offline diagnosis only |
| `data/failure_aware_acquisition_demo.csv` | offline_benchmark_records | yes (`record_id`) | yes (`true_success`, `failure_label`) | no | re-ranks already-completed records to demo the scoring function | demo/illustration only |
| `data/failure_aware_gp_acquisition_v04.csv` | offline_benchmark_records | yes (`candidate_id`) | yes (`failure_label` column present) | no | same 50 historical records, ranked for v0.4 demo | demo/illustration only |
| `data/failure_aware_gp_acquisition_v041.csv` | offline_benchmark_records | yes (`candidate_id`) | yes (`failure_label` column present) | no | same as v0.4, with the production-wiring contract test | demo/illustration only |
| `data/simulated_failure_aware_al_benchmark_v05.csv` | offline_benchmark_records | yes, but historical/completed | yes (`known_failures_selected`, etc., from `true_failure`) | no | single-trial offline policy comparison | offline benchmark interpretation only |
| `data/simulated_failure_aware_al_benchmark_v051.csv` | offline_benchmark_records | yes, but historical/completed | yes (`failures_selected`, `delta_failures_vs_lcb` derived from `true_failure`) | no | 50-trial repeated stress benchmark on the same historical pool | offline benchmark interpretation only |
| `analysis/outputs/raw/all_results.csv` | legacy_original_engine_benchmark | yes (50 systems) | yes (`best_energy_eV_per_atom`, `converged=True`) | no | completed results from the original 50-workflow manuscript benchmark | manuscript/results reporting only |
| `analysis/outputs/raw/system_status_manifest.csv` | legacy_original_engine_benchmark | yes | yes (`converged`, `status=included`) | no | tracks completion status of the 50-workflow benchmark | manuscript bookkeeping only |
| `analysis/outputs/raw/qe_settings_by_system.csv` | legacy_original_engine_benchmark | no (settings only, no candidate values/outcomes) | n/a | not as a candidate source; possibly reusable as a settings reference | lists QE settings per already-defined system, not candidate variable values | could inform a future `DFT_settings_profile` lookup, not a candidate pool itself |
| `analysis/outputs/raw/direct_grid_validations*.csv`, `grid_search_comparison.csv`, `grid_validation_cu.csv`, `grid_validation_mos2.csv` | legacy_original_engine_benchmark | yes (grid points) | yes (computed energies) | no | direct grid-search validation, already computed | manuscript validation only |
| `generated_models/*.py` (50 files) + `qe_active_inverse_common.py` | legacy_original_engine_benchmark | no (define a design-variable *range* + a few seed values, not a resolved next-candidate) | mostly yes, indirectly (`outputs/cache/*.pkl`, local/gitignored, hold cached energies for most of these systems already) | not directly; only as a *generation mechanism* | these are workflow configs; a concrete "next candidate" only exists transiently inside a live `run_system()` call (`_propose_inverse()`), and most of these systems already have cached completed results | re-running would require live QE and either a new material or a deliberately reopened variable range — out of scope here |
| `examples/manual_qe/*.py` | legacy_original_engine_benchmark | no (same nature as above, smaller standalone set) | mostly yes (matching cache files exist, e.g. `h2_energy_cache_sssp_efficiency_spinref.pkl`) | not directly | same reasoning as `generated_models/*.py` | same as above |
| `templates/live_validation_batch_schema_v070.csv` | candidate_schema_only | no (header row only) | no | yes, as a schema — not as data | exactly the v0.7 schema, zero rows | fill in once real candidates are actually proposed live |
| `reports/live_qe_validation_batch_design_v070.md` | candidate_schema_only | no | no | yes, as a design document | explicitly declined to populate real candidates (Section 6 of that report) | superseded/confirmed by this audit |
| `actistruct/parsers/qe.py`, `actistruct/datasets/qe_records.py`, `actistruct/acquisition/reliability.py` | tooling (not a data source) | n/a | n/a | n/a | code that processes candidates/records, not a candidate list itself | reusable as-is once a real candidate pool exists; no changes needed |

## 5. Historical/Completed Records That Must Not Be Reused as Future Candidates

Every row in the following files carries a known outcome
(`true_failure`/`true_success`/`failure_label`/`converged`/`final_energy_ry`/
`known_energy_ev` or equivalent) and must not be presented as an unresolved
future candidate:

```text
data/parsed_records/qe_reliability_records.csv
data/parsed_records/qe_invalid_geometry_records.csv
data/qe_reliability_ml_table.csv
data/qe_reliability_predictions_v02.csv
data/qe_reliability_predictions_v03.csv
data/qe_reliability_predictions_v032.csv
data/qe_reliability_group_split_predictions_v031.csv
data/failure_aware_acquisition_demo.csv
data/failure_aware_gp_acquisition_v04.csv
data/failure_aware_gp_acquisition_v041.csv
data/simulated_failure_aware_al_benchmark_v05.csv
data/simulated_failure_aware_al_benchmark_v051.csv
analysis/outputs/raw/all_results.csv
analysis/outputs/raw/system_status_manifest.csv
analysis/outputs/raw/direct_grid_validations.csv
analysis/outputs/raw/direct_grid_validations_internal.csv
analysis/outputs/raw/grid_search_comparison.csv
analysis/outputs/raw/grid_validation_cu.csv
analysis/outputs/raw/grid_validation_mos2.csv
```

These remain exactly as they are — none were deleted, relabeled, or hidden
by this audit.

## 6. Candidate Schemas/Templates Available

Only one schema-only artifact exists, with zero fabricated rows:

```text
templates/live_validation_batch_schema_v070.csv  (header row only)
```

`reports/live_qe_validation_batch_design_v070.md` Section 7 defines the
same 16-field schema in prose/table form.

## 7. Possible Future Candidate Sources, If Any

**None currently exist as static, unresolved candidate records.** The only
mechanism capable of producing a genuinely new, not-yet-evaluated candidate
is `qe_active_inverse_common.py`'s `_propose_inverse()` / active-learning
loop, invoked live (with QE installed and `failure_risk_provider`
configured) against one of the `generated_models/*.py` workflow
definitions — or a newly written workflow definition for a material not
yet in the dataset. That proposal is generated and consumed within the same
live loop iteration; it is not written out as a standing "next candidate"
file today. No such live run has been performed.

## 8. Missing Fields for Live Validation

Comparing the closest available source — `generated_models/*.py` workflow
definitions — against the v0.7 schema (Section 6 of
`reports/live_qe_validation_batch_design_v070.md`):

| Schema field | Present in `generated_models/*.py`? | Note |
| --- | --- | --- |
| `candidate_id` | No | only a design-variable range exists, not a resolved candidate |
| `material_id` | Yes (`key`) | |
| `material_family` | Partial (`category`) | coarser label than "family," usable as a starting point |
| `formula/composition` | Indirect (`pseudopotentials` dict + `builder`) | not a single explicit field |
| `structure_source` | Indirect (`builder` function name) | not an explicit recorded field |
| `candidate variables` | Yes (`Variable` ranges + `initial` seed values) | range only, not a specific proposed value |
| `predicted_value` | No | only exists transiently during a live GP run |
| `uncertainty / LCB score` | No | same as above |
| `failure_risk` | No | requires a `failure_risk_provider` configured and run |
| `acquisition_score` | No | computed live, not stored |
| `selection_reason` | No | must be written by a human/process at selection time |
| `selection_category` | No | new field, not produced by the engine |
| `DFT_settings_profile` | Yes (`ecutwfc`, `ecutrho`, `kpts`, `smearing`, `degauss`) | present but not packaged as a single named "profile" |
| `pseudopotential_family` | Indirect (`pseudopotentials` dict) | inferable, not an explicit field |
| `expected_runtime_risk` | No | qualitative judgment call, not currently recorded |
| `status` | No | no pre-run status field exists |
| `notes` | No | |

The offline/historical CSVs in Sections 4–5 score better on raw field
coverage (many already have `candidate_id`, `predicted_value`,
`failure_risk`, `acquisition_score`, `selection_reason`) but are
**disqualified outright** by Section 5's rule regardless of field
completeness, since every row also carries a known outcome.

## 9. Required Next Step Before Selecting Real Candidates

A live or live-adjacent candidate-generation/selection step is required
before any real candidate can be entered into the v0.7 schema:

1. Choose a target material/system (existing `generated_models/*.py`
   workflow, or a new one) and confirm its variable range is still
   scientifically open (i.e., not already exhaustively cached).
2. Run the GP/LCB active-learning loop live, with
   `failure_risk_provider` configured, far enough to obtain a real
   `_propose_inverse()` candidate with `predicted_value`, uncertainty,
   `failure_risk`, and `acquisition_score` populated.
3. Record that proposal into the v0.7 schema
   (`templates/live_validation_batch_schema_v070.csv`) with an explicit
   `selection_reason` and `selection_category`, **before** submitting it to
   QE/PBE.

This step itself requires either a live QE-connected run (out of scope for
this audit and for v0.7) or a dry-run mode that calls the ranking/proposal
functions without launching QE — which does not currently exist as a
documented, standalone tool.

## 10. What Not to Claim Yet

```text
Do not claim a valid future candidate pool already exists.
Do not claim any historical/offline record is an unresolved future candidate.
Do not claim live QE/PBE validation has started.
Do not claim live DFT savings.
Do not claim new materials have been discovered.
```

## 11. Recommended Path Toward v0.7.2

**Option B: no valid future candidate pool exists.** The recommended next
step is to build a small, QE-free **dry-run candidate selector**: a script
that loads a `generated_models/*.py` (or new) workflow definition, runs
only the GP-surrogate/acquisition math from `qe_active_inverse_common.py`
and `actistruct/acquisition/reliability.py` against already-cached training
points (no new QE calls), and writes out a small set of real, fully
populated v0.7-schema rows for human review — still with zero QE/DFT
executed. Only after that dry-run output is reviewed against the Section 11
go/no-go checklist in `reports/live_qe_validation_batch_design_v070.md`
should an actual live QE/PBE batch be considered.
