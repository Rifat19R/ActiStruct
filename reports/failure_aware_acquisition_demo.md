# Failure-Aware Acquisition Demo

## Purpose

This offline demo shows how predicted `failure_risk` can enter an active-learning acquisition score before launching new DFT jobs.

No QE or DFT calculations are launched. The demo uses v0.2 classifier predictions as candidate metadata and applies the minimization score:

```text
score = predicted_value - exploration_weight * uncertainty + failure_penalty * failure_risk
```

Lower score is preferred for minimization.

## Output

- Demo table: `data/failure_aware_acquisition_demo.csv`

## Penalty Sweep

### failure_penalty = 0

- Top-10 known failures: **3**
- Top-10 mean predicted failure risk: **0.327**

| Rank | Material | Failure label | True success | Failure risk | Score |
| ---: | --- | --- | ---: | ---: | ---: |
| 1 | `n2` | `success` | 1 | 0.043 | 0.000 |
| 2 | `bulk_cu` | `job_not_completed` | 0 | 0.959 | 0.000 |
| 3 | `mos2` | `success` | 1 | 0.000 | 0.000 |
| 4 | `o_on_ni111` | `success` | 1 | 0.255 | 0.000 |
| 5 | `bulk_fe` | `success` | 1 | 0.018 | 0.000 |
| 6 | `co_on_pt111` | `qe_error` | 0 | 0.977 | 0.000 |
| 7 | `h_on_cu111` | `success` | 1 | 0.266 | 0.000 |
| 8 | `bulk_fe` | `success` | 1 | 0.015 | 0.000 |
| 9 | `ch4` | `job_not_completed` | 0 | 0.722 | 0.000 |
| 10 | `bulk_fe` | `success` | 1 | 0.018 | 0.000 |

### failure_penalty = 0.5

- Top-10 known failures: **0**
- Top-10 mean predicted failure risk: **0.006**

| Rank | Material | Failure label | True success | Failure risk | Score |
| ---: | --- | --- | ---: | ---: | ---: |
| 1 | `mos2` | `success` | 1 | 0.000 | 0.000 |
| 2 | `mos2` | `success` | 1 | 0.000 | 0.000 |
| 3 | `mos2` | `success` | 1 | 0.000 | 0.000 |
| 4 | `bulk_tio2` | `success` | 1 | 0.002 | 0.001 |
| 5 | `bulk_alas` | `success` | 1 | 0.003 | 0.001 |
| 6 | `bulk_nial` | `success` | 1 | 0.007 | 0.004 |
| 7 | `bulk_ni` | `success` | 1 | 0.008 | 0.004 |
| 8 | `h_on_pt111` | `success` | 1 | 0.012 | 0.006 |
| 9 | `o_on_cu111` | `success` | 1 | 0.013 | 0.006 |
| 10 | `bulk_fe` | `success` | 1 | 0.015 | 0.008 |

### failure_penalty = 1

- Top-10 known failures: **0**
- Top-10 mean predicted failure risk: **0.006**

| Rank | Material | Failure label | True success | Failure risk | Score |
| ---: | --- | --- | ---: | ---: | ---: |
| 1 | `mos2` | `success` | 1 | 0.000 | 0.000 |
| 2 | `mos2` | `success` | 1 | 0.000 | 0.000 |
| 3 | `mos2` | `success` | 1 | 0.000 | 0.000 |
| 4 | `bulk_tio2` | `success` | 1 | 0.002 | 0.002 |
| 5 | `bulk_alas` | `success` | 1 | 0.003 | 0.003 |
| 6 | `bulk_nial` | `success` | 1 | 0.007 | 0.007 |
| 7 | `bulk_ni` | `success` | 1 | 0.008 | 0.008 |
| 8 | `h_on_pt111` | `success` | 1 | 0.012 | 0.012 |
| 9 | `o_on_cu111` | `success` | 1 | 0.013 | 0.013 |
| 10 | `bulk_fe` | `success` | 1 | 0.015 | 0.015 |

### failure_penalty = 2

- Top-10 known failures: **0**
- Top-10 mean predicted failure risk: **0.006**

| Rank | Material | Failure label | True success | Failure risk | Score |
| ---: | --- | --- | ---: | ---: | ---: |
| 1 | `mos2` | `success` | 1 | 0.000 | 0.000 |
| 2 | `mos2` | `success` | 1 | 0.000 | 0.000 |
| 3 | `mos2` | `success` | 1 | 0.000 | 0.000 |
| 4 | `bulk_tio2` | `success` | 1 | 0.002 | 0.003 |
| 5 | `bulk_alas` | `success` | 1 | 0.003 | 0.006 |
| 6 | `bulk_nial` | `success` | 1 | 0.007 | 0.015 |
| 7 | `bulk_ni` | `success` | 1 | 0.008 | 0.016 |
| 8 | `h_on_pt111` | `success` | 1 | 0.012 | 0.024 |
| 9 | `o_on_cu111` | `success` | 1 | 0.013 | 0.026 |
| 10 | `bulk_fe` | `success` | 1 | 0.015 | 0.031 |

## Scientific Caveat

This is a ranking-policy demonstration, not a final production acquisition loop. `predicted_value` and `uncertainty` are neutral placeholders here because the rows come from completed reliability records, not from a live GP candidate grid. The next production step is to compute these terms from the existing GP surrogate and apply the same failure penalty before choosing new DFT candidates.
