# ActiStruct Project Status — Post v0.5.1

## Current Repo State

```text
branch: main
pytest -q: 73 passed
working tree: clean
v0.5.1 merged into main
```

No QE/DFT jobs were launched to produce this status note or the v0.5.0/v0.5.1
benchmarks it summarizes. No failed records have been deleted or relabeled.

## What ActiStruct Is

ActiStruct is an experimental **reliability-aware active-learning workflow
for DFT-guided materials discovery**. It is built on top of a GP/LCB
active-learning engine for DFT structure optimization
(`qe_active_inverse_common.py`, 50 generated workflows). The reliability
layer adds: a QE output parser/dataset builder that keeps failed
calculations as first-class data, a failure-risk classifier trained only on
pre-run setup features, and a soft failure-risk penalty wired into the
GP/LCB acquisition score. ActiStruct does not replace QE/PBE; it helps
triage which candidates are worth running.

## Completed Milestones

- **v0.1–v0.3**: QE reliability parser, dataset builder, and reliability
  classifier (random split → no-`material_id` ablation → material-group
  split → repeated group-split generalization fix, v0.3.2).
- **v0.4–v0.4.1**: Failure-aware acquisition wired into the live GP/LCB
  proposal path (`failure_risk_provider`, gamma modes), with old LCB
  behavior preserved when risk is unavailable or gamma = 0.
- **v0.5.0**: First offline simulated benchmark comparing
  `random_selection`, `lcb_only`, and failure-aware LCB (mild/balanced/
  aggressive) on the full natural candidate pool, single trial.
- **v0.5.1**: Repeated-trial (50 trials) offline stress benchmark across
  four candidate-pool modes (`normal_pool`, `failure_enriched_pool`,
  `heldout_material_pool`, `high_uncertainty_pool`), with a noise-aware
  (mean-vs-standard-error) claim-wording audit completed and merged.

## v0.5.0 Result Summary

Single offline trial, full natural candidate pool, top-10:

- `lcb_only` selected **0 known failures** at top-10 (mean predicted risk
  0.152).
- `failure_aware_lcb_aggressive` also selected **0 known failures** at
  top-10, reducing mean predicted failure risk from **0.152 to 0.066**.
- Because `lcb_only` already selected 0 known failures, v0.5.0 could not
  claim a failure-count improvement over LCB-only — only a reduction in
  mean predicted risk while preserving 0 known failures.

Source: `reports/simulated_failure_aware_al_benchmark_v05.md`,
`data/simulated_failure_aware_al_benchmark_v05.csv`.

## v0.5.1 Result Summary

Repeated stress benchmark, 50 trials, top_k=10, `failure_aware_aggressive`
vs `lcb_only` (mean ± std over trials):

| Pool mode | Failures: LCB-only → aggressive | Risk: LCB-only → aggressive | Failure-count verdict |
| --- | --- | --- | --- |
| `normal_pool` | 1.48±1.33 → 0.30±0.54 | 0.163±0.038 → 0.096±0.027 | reduced, clearly (mean delta well outside its own noise) |
| `failure_enriched_pool` | 3.86±1.74 → 1.80±1.67 | 0.193±0.036 → 0.115±0.036 | reduced, clearly |
| `heldout_material_pool` | 0.74±1.98 → 0.62±1.51 | 0.129±0.078 → 0.103±0.070 | small/noisy reduction (mean delta smaller than its own standard error) |
| `high_uncertainty_pool` | 0.00±0.00 → 0.06±0.24 | 0.169±0.043 → 0.120±0.026 | risk improved; failure-count improvement not universal |

Source: `reports/simulated_failure_aware_al_benchmark_v051.md`,
`data/simulated_failure_aware_al_benchmark_v051.csv`.

## Current Safe Scientific Claim

> ActiStruct v0.5.1 extends the v0.5.0 offline benchmark into repeated
> stress tests. Across 50 trials, failure-aware LCB reduced the mean
> predicted failure risk in all tested pool modes. It also reduced known
> failed selections relative to LCB-only most clearly in normal and
> failure-enriched pools, while behavior was weaker in heldout-material
> pools and not universally better in high-uncertainty pools. These results
> support failure risk as a soft DFT triage signal, not a guarantee of live
> DFT savings.

ActiStruct does not claim: a universal materials-discovery engine,
guaranteed reduction of failed DFT jobs, that failure-aware LCB always
outperforms LCB-only, live DFT savings, or QE/PBE validation from these
offline results.

## Known Limitations

1. All reliability/acquisition evidence to date is from **offline
   simulations on completed records** — no new QE/PBE validation has been
   performed for v0.5.0/v0.5.1.
2. Failure-risk estimates are inherited from v0.3.2 and have large
   split-to-split variance on held-out materials (failure recall
   0.776±0.344 at threshold 0.05, dropping with higher thresholds).
3. `predicted_value` is a constant 0.0 placeholder in the v0.5.x
   benchmarks — policy differences come from the uncertainty proxy and the
   failure-risk penalty, not a live predicted-energy signal.
4. Each v0.5.x candidate's failure risk comes from a single v0.3.2
   held-out group split, not averaged across the 20 repeated splits.
5. `heldout_material_pool` and `high_uncertainty_pool` did not show a clear
   failure-count improvement; only the risk reduction is consistent across
   all four pool modes.
6. No live GP/QE active-learning run with failure-aware acquisition has
   been performed yet.

## What Is Ready Now

- The failure-aware acquisition scoring function (`actistruct/acquisition/reliability.py`)
  is tested, handles NaN/negative uncertainty and malformed failure-risk
  inputs safely, and never hard-rejects candidates.
- The live GP/LCB proposal path in `qe_active_inverse_common.py` supports an
  optional `failure_risk_provider` with verified fallback to old LCB
  behavior.
- The v0.5.0 and v0.5.1 offline benchmarks are deterministic, reproducible
  (verified byte-identical across repeated runs), and reviewed for
  scientific claim accuracy.
- The full test suite (73 tests) passes with no QE/DFT launched.

## What Is Not Ready Yet

- A live QE/PBE active-learning run using failure-aware acquisition, to
  test whether offline risk-reduction translates into actual DFT time
  saved.
- Any explanation for why `heldout_material_pool` and `high_uncertainty_pool`
  show weaker/non-universal failure-count benefit — this is an open
  question, not yet investigated.
- v0.6-scale feature work (e.g. GNN-based surrogates) — explicitly out of
  scope until the offline failure-aware acquisition path is validated live.

## Recommended Next Steps

1. Design and run a small live GP/QE active-learning trial with
   failure-aware acquisition enabled, on a system with known, reachable
   failure modes, to test whether the offline risk-reduction signal holds
   up live.
2. Investigate the `heldout_material_pool` / `high_uncertainty_pool` weak
   results — likely candidates are the small per-trial pool sizes for those
   modes and the lack of a live energy signal driving `predicted_value`.
3. Keep failure-risk classification as a soft triage signal; do not promote
   it to a hard accept/reject gate until split-to-split variance (v0.3.2)
   is reduced.
4. Defer GNN/v0.6 feature work until step 1 produces a live validation
   result.
