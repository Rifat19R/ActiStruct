# ActiStruct v0.7 Live QE/PBE Validation Batch Design

**No QE/DFT was run to produce this document.** This is a design-only
report: it specifies what a future live QE/PBE validation batch should look
like, the metadata it must record, and the checks that must pass before it
runs. The desktop is currently busy with other DFT jobs, so no calculations
are launched here or scheduled by this document. No real candidate IDs are
selected in this report (see Section 6) — only the design schema is
defined.

## 1. Objective

Specify, in advance and without running any calculation, how ActiStruct's
first live QE/PBE validation batch should be selected, recorded, and
evaluated, so that when desktop/HPC resources are free, the batch can be
launched against a pre-agreed, conservative, reproducible plan rather than
an ad hoc one.

## 2. Why Live Validation Is Needed

Every result presented so far — the v0.3.2 reliability classifier, the
v0.4/v0.4.1 failure-aware acquisition wiring, and the v0.5.0/v0.5.1 offline
benchmarks — is evidence from **completed historical records** or
**offline simulation** over those records. None of it shows whether
failure-aware re-ranking changes what actually happens when it is used to
pick the *next* QE/PBE calculation to run, live, before the outcome is
known. Only a live batch, selected by the failure-aware acquisition path
and then actually computed, can test that.

## 3. Current Evidence Before Live Validation

Summarized from `reports/actistruct_technical_report_v06.md`,
`reports/actistruct_status_v051.md`, and
`reports/simulated_failure_aware_al_benchmark_v051.md`:

- The v0.3.2 reliability classifier reaches strong in-domain accuracy but
  highly variable held-out-material failure recall (0.776±0.344 at
  threshold 0.05, dropping at higher thresholds).
- Failure-aware GP/LCB acquisition (`actistruct/acquisition/reliability.py`)
  is tested to be a strict soft penalty: it never hard-rejects a candidate,
  and reduces exactly to plain LCB when failure risk is unavailable or
  gamma = 0.
- The v0.5.1 repeated-trial offline stress benchmark (50 trials, 4 pool
  modes) shows failure-aware LCB reduced mean predicted failure risk in
  every tested pool mode, and reduced known failed selections relative to
  LCB-only most clearly in `normal_pool` and `failure_enriched_pool` —
  weaker in `heldout_material_pool`, not universal in
  `high_uncertainty_pool`.

## 4. What Remains Unproven

- Whether the offline risk-reduction signal holds up when the candidates
  selected are actually computed live, rather than looked up from already-
  completed records.
- Whether failure-aware re-ranking changes the *number of QE jobs needed*
  to reach a usable result, in practice.
- Whether the v0.3.2 classifier's held-out-material weakness manifests as
  an actual missed failure in a live batch, or whether the batch happens to
  fall into a more favorable regime (as v0.5.0's single offline trial did).
- Anything about new materials, materials discovery, or DFT replacement —
  none of these are in scope for this batch design or claimed by it.

## 5. Batch Size

**5–10 candidates.** Small enough to review every candidate's metadata by
hand before submission, and to evaluate every outcome individually after
the run, while still being large enough to populate every category in
Section 6.

## 6. Candidate-Selection Strategy

No real candidates are selected in this document. Existing records in
`data/qe_reliability_predictions_v032.csv` / `data/parsed_records/qe_reliability_records.csv`
are **already-completed historical calculations** used for offline
benchmarking — they have known `true_failure` and (for successes)
`known_energy_ev` values, which is precisely why they cannot stand in for
*future, not-yet-run* candidates. No file in this repository currently
holds a list of pending, unevaluated candidate proposals (checked: no
`*proposal*`/pending-candidate artifacts exist). Selecting real IDs here
would either reuse already-known outcomes (scientifically meaningless for
a "live" test) or fabricate candidates that were never actually proposed by
the GP/LCB engine — both unacceptable. This section therefore defines the
*category schema* a future real batch must populate, once
`qe_active_inverse_common.py`'s `_propose_inverse()` path is actually run
live with `failure_risk_provider` configured.

| Category | Count | Selection rule |
| --- | --- | --- |
| Exploitation | 2 | Lowest predicted value (`predicted_value`) at low uncertainty — the GP surrogate's best current guess. |
| Uncertainty/exploration | 2 | Highest GP uncertainty (`sigma(x)` / LCB uncertainty term) among in-bounds candidates — where the surrogate knows the least. |
| Low failure-risk | 2 | `failure_risk` well below the operating threshold (`DEFAULT_FAILURE_RISK_THRESHOLD = 0.10` in `actistruct/acquisition/reliability.py`) — expected-safe candidates. |
| Failure-risk challenge | 2 | `failure_risk` at or above the operating threshold — to directly test whether the penalty correctly down-ranks/flags candidates that go on to actually fail. |
| Diversity (optional) | 1–2 | Different material/composition than the rest of the batch, to avoid the whole batch collapsing onto one material's parameter sweep. |

Every candidate, real or hypothetical, must carry an explicit
`selection_reason` (Section 7) stating which category and why — no
candidate is added to a batch without one.

## 7. Required Candidate Metadata

Every future candidate selected for a live batch must have all of the
following recorded **before** submission:

| Field | Meaning |
| --- | --- |
| `candidate_id` | Stable identifier for this candidate within the batch. |
| `material_id` | Which material/system this candidate belongs to. |
| `material_family` | Coarse class (e.g. bulk metal, 2D material, oxide, surface-adsorption system) — see Section 15 of `reports/actistruct_technical_report_v06.md` for current scope. |
| `formula/composition` | Chemical formula or composition string. |
| `structure_source` | How the structure was built (e.g. generated builder script, manual structure, literature-derived). |
| `candidate variables` | The design variable values being proposed (e.g. lattice constant, bond length, fractional coordinates). |
| `predicted_value` | GP surrogate's predicted property value at this candidate. |
| `uncertainty / LCB score` | GP uncertainty and the resulting LCB score. |
| `failure_risk` | Predicted failure risk from the reliability classifier (or `None`/missing if unavailable — must be recorded as missing, not silently defaulted). |
| `acquisition_score` | Final failure-aware acquisition score (`base_lcb_score + gamma * failure_risk`, per `actistruct/acquisition/reliability.py`). |
| `selection_reason` | Free text: which Section 6 category this candidate fills and why it was chosen within that category. |
| `selection_category` | One of: exploitation, exploration, low-risk, risk-challenge, diversity. |
| `DFT_settings_profile` | Which QE settings profile (cutoffs/k-points/smearing set) this candidate uses. |
| `pseudopotential_family` | Pseudopotential family/source used. |
| `expected_runtime_risk` | Qualitative pre-run note on expected runtime or known fragility (e.g. "large k-point grid, expect long wall time"). |
| `status` | Pre-run status (e.g. `pending`, `submitted`); updated post-run per Section 9. |
| `notes` | Any other context a reviewer should know before approving the run. |

**No candidate may be added to a live batch without a `selection_reason`.**

## 8. Required QE/PBE Metadata

For every calculation actually run in a future batch, record:

```text
QE version
calculation type (scf, relax, vc-relax, etc.)
pseudopotential files/family
ecutwfc
ecutrho
k-points
smearing type/width
mixing_beta
conv_thr
spin setting
vdW correction if used
cell/atomic relaxation settings
wall time
convergence status
failure reason if failed
output path
calculation hash
```

This mirrors the fields the existing QE parser
(`actistruct/parsers/qe.py`, see `docs/qe_reliability_parser.md`) already
extracts from completed `pw.x` output, so a future live batch's results can
be parsed by the same pipeline that built the current reliability dataset
without any new parser logic.

**Failed, incomplete, and unconverged calculations must be preserved.**
They are training signal for the next round of reliability modeling, not
noise to be deleted.

## 9. Success/Failure Definitions

Future per-candidate outcome labels (mirroring and extending the taxonomy
already used in `reports/qe_reliability_group_split_diagnosis_v031.md`):

| Label | Meaning |
| --- | --- |
| `successful_converged` | SCF (and ionic, if relaxation) converged; usable result. |
| `scf_not_converged` | Electronic SCF failed to converge within `electron_maxstep`. |
| `ionic_not_converged` | SCF converged but ionic/cell relaxation did not converge within step limit. |
| `job_not_completed` | Job did not finish (walltime, crash, queue kill) before any convergence determination. |
| `qe_error` | QE raised an input/namelist/runtime error before meaningful SCF progress. |
| `geometry_failed` | Pre-QE geometry validation rejected the candidate (e.g. atomic overlap) before launch. |
| `needs_rerun` | Ambiguous or interrupted run that should be resubmitted, not scored as failure or success. |
| `usable_with_caution` | Converged but with a flagged caveat (e.g. borderline force/SCF residual) that a reviewer should check before trusting the result. |

**Failures must not be relabeled to improve apparent results.** A
candidate that fails stays labeled as failed; no record is deleted,
hidden, or reclassified to make the batch look more successful than it
was.

## 10. Comparison Plan After Calculations

Once a future batch is actually computed and parsed, ActiStruct will
compare:

- failure-aware selected candidates vs. an `lcb_only` baseline ranking
  (same candidate pool, gamma = 0) vs. a `random_selection` baseline —
  mirroring the three-way comparison already used in
  `analysis/simulated_failure_aware_al_benchmark_v05.py`/`_v051.py`.
- mean predicted failure risk of the selected batch **before** the run vs.
  actual failed selections **after** the run.
- converged/successful selections per policy.
- the best candidate found, if a comparable objective is defined for the
  batch's material(s).
- wall-time and failure-mode distribution across the batch, if enough
  candidates fail to make a distribution meaningful.

**Safe interpretation:** only after the live QE/PBE batch runs and is
parsed can ActiStruct claim any evidence about live DFT triage behavior.
Nothing in this document is that evidence — it is the plan for producing
it.

## 11. Go/No-Go Checklist Before Running DFT

```text
[ ] Desktop/HPC resources are free
[ ] No other critical QE jobs are running
[ ] Pseudopotentials are verified (files present, family consistent, checksums recorded)
[ ] QE settings are documented (DFT_settings_profile filled for every candidate)
[ ] Candidate structures are checked (geometry validated, no atomic overlaps)
[ ] Disk space is sufficient for the expected scratch/output volume
[ ] All selected candidates have complete metadata (Section 7), including selection_reason
[ ] Failure records will be preserved, not deleted, regardless of outcome
[ ] No manual deletion of failed jobs is planned or performed
```

**As of this report, the desktop is busy with other DFT jobs.** This
report is design-only; none of the above items have been checked off
because no batch has been scheduled yet. The checklist exists so that the
next time resources are free, the go/no-go decision is explicit rather than
assumed.

## 12. What Not to Claim Before the Batch Runs

```text
Do not claim live DFT validation has been performed.
Do not claim live DFT savings.
Do not claim new materials have been discovered.
Do not claim failure-aware LCB always outperforms LCB-only.
Do not claim this design document is itself evidence of anything beyond a plan.
```

## 13. Expected Output Files After Future Execution

If and when this batch is actually run, expect (using existing, unmodified
tooling — no new parser/benchmark logic required):

```text
outputs/qe_runs_<key>/...                         # raw QE scratch per candidate (gitignored)
data/parsed_records/qe_reliability_records.csv    # appended with the new records (success and failure)
reports/live_qe_validation_batch_results_v07x.md  # a future results report, written after parsing
data/live_qe_validation_batch_v07x.csv            # a future per-candidate comparison table (Section 10)
```

None of these files exist yet. This report does not create them.

## 14. Next Action After Desktop Resources Are Free

1. Confirm the go/no-go checklist (Section 11) is fully satisfied.
2. Populate Section 7's metadata table with real candidates selected by
   actually running the live GP/LCB proposal path
   (`qe_active_inverse_common.py` with `failure_risk_provider` configured)
   — not by reusing historical offline-benchmark records.
3. Run the batch, preserving every outcome including failures.
4. Parse results through the existing QE reliability parser
   (`actistruct/parsers/qe.py`) so they become new training/evaluation
   records, not a disconnected dataset.
5. Write the comparison report described in Section 10, using only the
   actual results obtained — and no claim stronger than Section 12 permits
   until that comparison is complete.
