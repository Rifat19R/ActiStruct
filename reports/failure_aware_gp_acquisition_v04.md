# Failure-Aware GP Acquisition v0.4

## Purpose

This integrates v0.3.2 failure-risk predictions into the live GP/LCB candidate ranking path as a soft penalty. No QE/DFT jobs are launched.

## Formula

For minimization:

```text
score = predicted_value - beta * uncertainty + gamma * failure_risk
```

Defaults: `beta=2.0`, `gamma=1.0`, `failure_risk_threshold=0.1`.

Candidates are never hard rejected by failure risk. Elevated-risk candidates are only penalized in the acquisition score.

## Output

- Ranked table: `data/failure_aware_gp_acquisition_v04.csv`
- Ranked candidates: **50**
- Elevated-risk candidates: **36**

## Top Candidates

| Rank | Candidate | Failure risk | Penalty | Score | Risk flag | Reason |
| ---: | --- | ---: | ---: | ---: | --- | --- |
| 1 | `81` | 0.024 | 0.024 | 0.024 | low | ranked by failure-aware LCB soft penalty |
| 2 | `82` | 0.024 | 0.024 | 0.024 | low | ranked by failure-aware LCB soft penalty |
| 3 | `83` | 0.024 | 0.024 | 0.024 | low | ranked by failure-aware LCB soft penalty |
| 4 | `84` | 0.024 | 0.024 | 0.024 | low | ranked by failure-aware LCB soft penalty |
| 5 | `117` | 0.026 | 0.026 | 0.026 | low | ranked by failure-aware LCB soft penalty |
| 6 | `118` | 0.026 | 0.026 | 0.026 | low | ranked by failure-aware LCB soft penalty |
| 7 | `119` | 0.026 | 0.026 | 0.026 | low | ranked by failure-aware LCB soft penalty |
| 8 | `120` | 0.026 | 0.026 | 0.026 | low | ranked by failure-aware LCB soft penalty |
| 9 | `121` | 0.026 | 0.026 | 0.026 | low | ranked by failure-aware LCB soft penalty |
| 10 | `122` | 0.026 | 0.026 | 0.026 | low | ranked by failure-aware LCB soft penalty |

## Scientific Caveat

The included CSV is an offline integration artifact. In production, `predicted_value` and `uncertainty` should come from the active GP surrogate for proposed candidates; the same ranking function now accepts optional `failure_risk` and falls back to original LCB if it is absent.
