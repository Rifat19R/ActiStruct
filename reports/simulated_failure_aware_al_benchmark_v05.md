# Simulated Failure-Aware Active-Learning Benchmark v0.5

## Purpose

This offline benchmark compares candidate-selection policies using existing completed QE reliability records and v0.3.2 failure-risk predictions. It does not run QE/DFT and does not modify parser logic or labels.

## Policies

- `random_selection`
- `lcb_only`
- `failure_aware_lcb_mild`: gamma = 0.1
- `failure_aware_lcb_balanced`: gamma = 0.3
- `failure_aware_lcb_aggressive`: gamma = 1.0

## Output

- Benchmark table: `data/simulated_failure_aware_al_benchmark_v05.csv`
- Candidate pool: **976** records

## Results

| Policy | Top-k | Failures | Successes | Avoidance | Mean risk | Mean score | LCB overlap | Mean shift | Best candidate | Best energy eV |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| random_selection | 5 | 1 | 4 | 0.800 | 0.285 | -0.123 | 0.000 | 0.000 | `880` | -35353.335 |
| random_selection | 10 | 2 | 8 | 0.800 | 0.200 | -0.148 | 0.000 | 0.000 | `880` | -35353.335 |
| random_selection | 20 | 5 | 15 | 0.750 | 0.202 | -0.149 | 0.000 | 0.000 | `880` | -35353.335 |
| lcb_only | 5 | 0 | 5 | 1.000 | 0.055 | -2.000 | 1.000 | 0.000 | `418` | -5209.307 |
| lcb_only | 10 | 0 | 10 | 1.000 | 0.152 | -1.553 | 1.000 | 0.000 | `418` | -5209.307 |
| lcb_only | 20 | 0 | 20 | 1.000 | 0.160 | -1.172 | 1.000 | 0.000 | `505` | -13695.123 |
| failure_aware_lcb_mild | 5 | 0 | 5 | 1.000 | 0.055 | -1.994 | 1.000 | 0.000 | `418` | -5209.307 |
| failure_aware_lcb_mild | 10 | 0 | 10 | 1.000 | 0.152 | -1.538 | 1.000 | 0.000 | `418` | -5209.307 |
| failure_aware_lcb_mild | 20 | 0 | 20 | 1.000 | 0.160 | -1.156 | 1.000 | 0.000 | `505` | -13695.123 |
| failure_aware_lcb_balanced | 5 | 0 | 5 | 1.000 | 0.055 | -1.983 | 1.000 | 0.000 | `418` | -5209.307 |
| failure_aware_lcb_balanced | 10 | 0 | 10 | 1.000 | 0.152 | -1.508 | 1.000 | 0.000 | `418` | -5209.307 |
| failure_aware_lcb_balanced | 20 | 0 | 20 | 1.000 | 0.160 | -1.124 | 1.000 | 0.000 | `505` | -13695.123 |
| failure_aware_lcb_aggressive | 5 | 0 | 5 | 1.000 | 0.055 | -1.945 | 1.000 | 0.000 | `418` | -5209.307 |
| failure_aware_lcb_aggressive | 10 | 0 | 10 | 1.000 | 0.066 | -1.426 | 0.600 | 3.200 | `503` | -13695.106 |
| failure_aware_lcb_aggressive | 20 | 0 | 20 | 1.000 | 0.083 | -1.019 | 0.600 | 5.600 | `505` | -13695.123 |

## Interpretation

- `lcb_only` selected 0 known failures at top-10 with mean risk 0.152.
- `failure_aware_lcb_mild` selected 0 known failures at top-10 with mean risk 0.152.
- `failure_aware_lcb_balanced` selected 0 known failures at top-10 with mean risk 0.152.
- `failure_aware_lcb_aggressive` selected 0 known failures at top-10 with mean risk 0.066.

`failure_aware_lcb_mild` preserved the same known failed-selection count as `lcb_only` at top-10 (0) while changing mean predicted failure risk from 0.152 to 0.152. `failure_aware_lcb_balanced` preserved the same known failed-selection count as `lcb_only` at top-10 (0) while changing mean predicted failure risk from 0.152 to 0.152. `failure_aware_lcb_aggressive` preserved the same known failed-selection count as `lcb_only` at top-10 (0) while changing mean predicted failure risk from 0.152 to 0.066.

## Scientific Caveats

- This is a simulated policy benchmark, not a live GP retraining study.
- The LCB uncertainty proxy uses existing v0.3.2 OOD distances because no new GP/QE jobs are launched here.
- `predicted_value` is a constant placeholder (0.0) for every candidate in this offline simulation, since no live GP energy model is being queried. Policy differences therefore come entirely from the uncertainty proxy and the failure-risk penalty, not from a predicted energy signal.
- Each candidate's failure risk comes from a single v0.3.2 held-out group split in which that material was not used for training (not averaged across the 20 repeated splits). Because split-to-split risk variance is known to be large, the absolute risk value used for any one candidate here could differ under a different held-out split.
- Failure-risk generalization still has high split-to-split variance, so failure risk should remain a soft penalty for DFT triage, not a hard rejection rule.
- Known failures/successes are evaluated from completed records after selection; failed records are not deleted or relabeled.
