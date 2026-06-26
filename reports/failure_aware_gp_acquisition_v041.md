# Failure-Aware GP Acquisition v0.4.1

## Purpose

This integrates v0.3.2 failure-risk predictions into the live GP/LCB candidate ranking path as a soft penalty. No QE/DFT jobs are launched.

## Formula

For minimization:

```text
score = predicted_value - beta * uncertainty + gamma * failure_risk
```

Defaults: `beta=2.0`, `gamma=1.0`, `failure_risk_threshold=0.1`.
Gamma modes: `mild=0.1`, `balanced=0.3`, `aggressive=1.0`.

Candidates are never hard rejected by failure risk. Elevated-risk candidates are only penalized in the acquisition score.

## Output

- Ranked table: `data/failure_aware_gp_acquisition_v041.csv`
- Ranked candidates: **50**
- Elevated-risk candidates: **36**

## Default Top Candidates

| Rank | Candidate | Base LCB | Failure risk | Penalty | Score | Base rank | Risk rank | Shift | Risk flag |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | `81` | 0.000 | 0.024 | 0.024 | 0.024 | 2 | 1 | 1 | low |
| 2 | `82` | 0.000 | 0.024 | 0.024 | 0.024 | 3 | 2 | 1 | low |
| 3 | `83` | 0.000 | 0.024 | 0.024 | 0.024 | 4 | 3 | 1 | low |
| 4 | `84` | 0.000 | 0.024 | 0.024 | 0.024 | 5 | 4 | 1 | low |
| 5 | `117` | 0.000 | 0.026 | 0.026 | 0.026 | 6 | 5 | 1 | low |
| 6 | `118` | 0.000 | 0.026 | 0.026 | 0.026 | 7 | 6 | 1 | low |
| 7 | `119` | 0.000 | 0.026 | 0.026 | 0.026 | 8 | 7 | 1 | low |
| 8 | `120` | 0.000 | 0.026 | 0.026 | 0.026 | 9 | 8 | 1 | low |
| 9 | `121` | 0.000 | 0.026 | 0.026 | 0.026 | 10 | 9 | 1 | low |
| 10 | `122` | 0.000 | 0.026 | 0.026 | 0.026 | 11 | 10 | 1 | low |

## Gamma Mode Top-10 Changes

### mild gamma = 0.1

- Top-10 mean failure risk: **0.025**
- Top-10 candidates shifted by risk penalty: **10**

| Rank | Candidate | Failure risk | Score | Base rank | Shift |
| ---: | --- | ---: | ---: | ---: | ---: |
| 1 | `81` | 0.024 | 0.002 | 2 | 1 |
| 2 | `82` | 0.024 | 0.002 | 3 | 1 |
| 3 | `83` | 0.024 | 0.002 | 4 | 1 |
| 4 | `84` | 0.024 | 0.002 | 5 | 1 |
| 5 | `117` | 0.026 | 0.003 | 6 | 1 |
| 6 | `118` | 0.026 | 0.003 | 7 | 1 |
| 7 | `119` | 0.026 | 0.003 | 8 | 1 |
| 8 | `120` | 0.026 | 0.003 | 9 | 1 |
| 9 | `121` | 0.026 | 0.003 | 10 | 1 |
| 10 | `122` | 0.026 | 0.003 | 11 | 1 |

### balanced gamma = 0.3

- Top-10 mean failure risk: **0.025**
- Top-10 candidates shifted by risk penalty: **10**

| Rank | Candidate | Failure risk | Score | Base rank | Shift |
| ---: | --- | ---: | ---: | ---: | ---: |
| 1 | `81` | 0.024 | 0.007 | 2 | 1 |
| 2 | `82` | 0.024 | 0.007 | 3 | 1 |
| 3 | `83` | 0.024 | 0.007 | 4 | 1 |
| 4 | `84` | 0.024 | 0.007 | 5 | 1 |
| 5 | `117` | 0.026 | 0.008 | 6 | 1 |
| 6 | `118` | 0.026 | 0.008 | 7 | 1 |
| 7 | `119` | 0.026 | 0.008 | 8 | 1 |
| 8 | `120` | 0.026 | 0.008 | 9 | 1 |
| 9 | `121` | 0.026 | 0.008 | 10 | 1 |
| 10 | `122` | 0.026 | 0.008 | 11 | 1 |

### aggressive gamma = 1.0

- Top-10 mean failure risk: **0.025**
- Top-10 candidates shifted by risk penalty: **10**

| Rank | Candidate | Failure risk | Score | Base rank | Shift |
| ---: | --- | ---: | ---: | ---: | ---: |
| 1 | `81` | 0.024 | 0.024 | 2 | 1 |
| 2 | `82` | 0.024 | 0.024 | 3 | 1 |
| 3 | `83` | 0.024 | 0.024 | 4 | 1 |
| 4 | `84` | 0.024 | 0.024 | 5 | 1 |
| 5 | `117` | 0.026 | 0.026 | 6 | 1 |
| 6 | `118` | 0.026 | 0.026 | 7 | 1 |
| 7 | `119` | 0.026 | 0.026 | 8 | 1 |
| 8 | `120` | 0.026 | 0.026 | 9 | 1 |
| 9 | `121` | 0.026 | 0.026 | 10 | 1 |
| 10 | `122` | 0.026 | 0.026 | 11 | 1 |


## Scientific Caveat

The included CSV is an offline integration artifact. The production engine now exposes an optional `failure_risk_provider` on `ActiveSystem`; when it is absent, the original DE LCB path is preserved.
