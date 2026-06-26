# Simulated Failure-Aware Active-Learning Stress Benchmark v0.5.1

## Objective

Stress-test whether failure-aware GP/LCB candidate re-ranking helps under harder, repeated candidate-pool conditions, instead of relying on a single offline sample as v0.5.0 did.

## Why v0.5.1 is needed

v0.5.0 ran one offline trial on the naturally-occurring candidate pool. `lcb_only` already selected zero known failures at top-10 in that single sample, so v0.5.0 could not show whether failure-aware re-ranking reduces failed selections relative to LCB-only - only that it can lower mean predicted failure risk without increasing failures. v0.5.1 repeats the comparison across **50** trials and four candidate-pool conditions so that genuine LCB-only failures can occur and be compared against.

## Data source

Same offline data as v0.5.0: completed QE reliability records (`data/parsed_records/qe_reliability_records.csv`) and v0.3.2 failure-risk predictions (`data/qe_reliability_predictions_v032.csv`), loaded via `analysis.simulated_failure_aware_al_benchmark_v05.load_candidates`. Base candidate pool: **976** records. No new QE/DFT jobs were run and no records were deleted or relabeled.

## Policies

- `random_selection`
- `lcb_only` (gamma = 0.0)
- `failure_aware_mild` (gamma = 0.1)
- `failure_aware_balanced` (gamma = 0.3)
- `failure_aware_aggressive` (gamma = 1.0)

A `gamma=0` check is run separately to confirm the failure-aware ranking function reduces exactly to `lcb_only` ranking (no hidden risk influence) when gamma is zero; see `gamma_zero_matches_lcb_only()` and its test.

## Pool modes

- `normal_pool`: random sub-sample of 150 candidates from the full v0.5.0 pool, at the pool's natural failure rate.
- `failure_enriched_pool`: random sub-sample re-weighted to ~60% known failures (sampled without replacement from real failure/success records; no labels are fabricated).
- `heldout_material_pool`: whole materials (not individual records) are sampled until the pool reaches at least 150 records, so failures/successes cluster by material the way they would if entire materials were held out together, rather than being i.i.d. across records. Implemented because `material_id` is present in the v0.3.2 prediction data.
- `high_uncertainty_pool`: sub-sample drawn from the highest-uncertainty 50% of candidates (by the existing normalized OOD-distance proxy used in v0.5.0), to test exploration vs. failure-risk competition. Implemented because an uncertainty proxy (`ood_distance`) is present.

All four requested pool modes were implemented; none were skipped, since both `material_id` and an uncertainty proxy are present in the existing v0.3.2 prediction data.

## Metrics

Per trial/policy/pool_mode/top_k: `failures_selected`, `successes_selected`, `failure_fraction`, `mean_failure_risk`, `mean_acquisition_score`, `best_known_candidate_found`, `top_k_overlap_with_lcb`, `mean_rank_shift`, `delta_failures_vs_lcb`, `delta_mean_risk_vs_lcb`. Full per-trial data: `data/simulated_failure_aware_al_benchmark_v051.csv`.

## Results

### normal_pool

| Policy | Top-k | Mean failures ± std | Mean risk ± std | Best-known found rate | Δ failures vs LCB ± std | Δ risk vs LCB ± std |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| random_selection | 5 | 2.02 ± 1.12 | 0.230 ± 0.095 | 0.000 | +1.96 ± 1.12 | +0.072 ± 0.114 |
| lcb_only | 5 | 0.06 ± 0.24 | 0.158 ± 0.048 | 0.000 | +0.00 ± 0.00 | +0.000 ± 0.000 |
| failure_aware_mild | 5 | 0.04 ± 0.20 | 0.158 ± 0.048 | 0.000 | -0.02 ± 0.14 | -0.000 ± 0.002 |
| failure_aware_balanced | 5 | 0.04 ± 0.20 | 0.141 ± 0.051 | 0.000 | -0.02 ± 0.14 | -0.018 ± 0.039 |
| failure_aware_aggressive | 5 | 0.00 ± 0.00 | 0.105 ± 0.043 | 0.000 | -0.06 ± 0.24 | -0.053 ± 0.047 |
| random_selection | 10 | 3.90 ± 1.58 | 0.237 ± 0.063 | 0.020 | +2.42 ± 2.03 | +0.074 ± 0.077 |
| lcb_only | 10 | 1.48 ± 1.33 | 0.163 ± 0.038 | 0.000 | +0.00 ± 0.00 | +0.000 ± 0.000 |
| failure_aware_mild | 10 | 1.38 ± 1.29 | 0.161 ± 0.037 | 0.000 | -0.10 ± 0.36 | -0.002 ± 0.005 |
| failure_aware_balanced | 10 | 1.38 ± 1.29 | 0.156 ± 0.038 | 0.000 | -0.10 ± 0.36 | -0.007 ± 0.018 |
| failure_aware_aggressive | 10 | 0.30 ± 0.54 | 0.096 ± 0.027 | 0.000 | -1.18 ± 1.32 | -0.067 ± 0.042 |
| random_selection | 20 | 7.88 ± 2.11 | 0.242 ± 0.044 | 0.100 | +4.48 ± 2.32 | +0.093 ± 0.049 |
| lcb_only | 20 | 3.40 ± 1.80 | 0.149 ± 0.025 | 0.000 | +0.00 ± 0.00 | +0.000 ± 0.000 |
| failure_aware_mild | 20 | 3.40 ± 1.80 | 0.147 ± 0.024 | 0.000 | +0.00 ± 0.00 | -0.002 ± 0.003 |
| failure_aware_balanced | 20 | 3.40 ± 1.80 | 0.144 ± 0.024 | 0.000 | +0.00 ± 0.00 | -0.005 ± 0.006 |
| failure_aware_aggressive | 20 | 3.12 ± 1.66 | 0.127 ± 0.022 | 0.000 | -0.28 ± 0.76 | -0.022 ± 0.018 |

### failure_enriched_pool

| Policy | Top-k | Mean failures ± std | Mean risk ± std | Best-known found rate | Δ failures vs LCB ± std | Δ risk vs LCB ± std |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| random_selection | 5 | 3.20 ± 1.09 | 0.210 ± 0.084 | 0.000 | +2.18 ± 1.73 | +0.032 ± 0.112 |
| lcb_only | 5 | 1.02 ± 1.20 | 0.178 ± 0.055 | 0.000 | +0.00 ± 0.00 | +0.000 ± 0.000 |
| failure_aware_mild | 5 | 0.78 ± 1.09 | 0.174 ± 0.056 | 0.000 | -0.24 ± 0.48 | -0.004 ± 0.008 |
| failure_aware_balanced | 5 | 0.78 ± 1.09 | 0.157 ± 0.053 | 0.000 | -0.24 ± 0.48 | -0.021 ± 0.038 |
| failure_aware_aggressive | 5 | 0.20 ± 0.40 | 0.094 ± 0.038 | 0.000 | -0.82 ± 1.08 | -0.085 ± 0.058 |
| random_selection | 10 | 6.12 ± 1.55 | 0.233 ± 0.075 | 0.000 | +2.26 ± 2.65 | +0.040 ± 0.085 |
| lcb_only | 10 | 3.86 ± 1.74 | 0.193 ± 0.036 | 0.000 | +0.00 ± 0.00 | +0.000 ± 0.000 |
| failure_aware_mild | 10 | 3.72 ± 1.84 | 0.191 ± 0.036 | 0.000 | -0.14 ± 0.40 | -0.002 ± 0.004 |
| failure_aware_balanced | 10 | 3.72 ± 1.84 | 0.190 ± 0.036 | 0.000 | -0.14 ± 0.40 | -0.002 ± 0.005 |
| failure_aware_aggressive | 10 | 1.80 ± 1.67 | 0.115 ± 0.036 | 0.000 | -2.06 ± 1.52 | -0.078 ± 0.043 |
| random_selection | 20 | 12.18 ± 2.40 | 0.237 ± 0.058 | 0.100 | +6.74 ± 3.36 | +0.073 ± 0.063 |
| lcb_only | 20 | 5.44 ± 1.92 | 0.164 ± 0.021 | 0.000 | +0.00 ± 0.00 | +0.000 ± 0.000 |
| failure_aware_mild | 20 | 5.48 ± 1.94 | 0.163 ± 0.020 | 0.000 | +0.04 ± 0.20 | -0.001 ± 0.004 |
| failure_aware_balanced | 20 | 5.48 ± 1.94 | 0.162 ± 0.020 | 0.000 | +0.04 ± 0.20 | -0.002 ± 0.005 |
| failure_aware_aggressive | 20 | 5.34 ± 1.88 | 0.157 ± 0.018 | 0.000 | -0.10 ± 0.46 | -0.007 ± 0.012 |

### heldout_material_pool

| Policy | Top-k | Mean failures ± std | Mean risk ± std | Best-known found rate | Δ failures vs LCB ± std | Δ risk vs LCB ± std |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| random_selection | 5 | 2.22 ± 1.39 | 0.249 ± 0.141 | 0.040 | +2.04 ± 1.41 | +0.135 ± 0.183 |
| lcb_only | 5 | 0.18 ± 0.66 | 0.114 ± 0.089 | 0.040 | +0.00 ± 0.00 | +0.000 ± 0.000 |
| failure_aware_mild | 5 | 0.14 ± 0.61 | 0.112 ± 0.088 | 0.060 | -0.04 ± 0.28 | -0.002 ± 0.009 |
| failure_aware_balanced | 5 | 0.14 ± 0.61 | 0.108 ± 0.089 | 0.060 | -0.04 ± 0.28 | -0.006 ± 0.030 |
| failure_aware_aggressive | 5 | 0.10 ± 0.46 | 0.098 ± 0.082 | 0.060 | -0.08 ± 0.40 | -0.016 ± 0.054 |
| random_selection | 10 | 4.12 ± 2.66 | 0.245 ± 0.129 | 0.060 | +3.38 ± 2.98 | +0.116 ± 0.158 |
| lcb_only | 10 | 0.74 ± 1.98 | 0.129 ± 0.078 | 0.100 | +0.00 ± 0.00 | +0.000 ± 0.000 |
| failure_aware_mild | 10 | 0.54 ± 1.70 | 0.124 ± 0.078 | 0.120 | -0.20 ± 0.90 | -0.005 ± 0.020 |
| failure_aware_balanced | 10 | 0.62 ± 1.71 | 0.116 ± 0.076 | 0.120 | -0.12 ± 0.98 | -0.014 ± 0.038 |
| failure_aware_aggressive | 10 | 0.62 ± 1.51 | 0.103 ± 0.070 | 0.120 | -0.12 ± 1.61 | -0.026 ± 0.056 |
| random_selection | 20 | 7.74 ± 5.32 | 0.254 ± 0.122 | 0.060 | +5.02 ± 6.55 | +0.115 ± 0.146 |
| lcb_only | 20 | 2.72 ± 5.07 | 0.139 ± 0.066 | 0.120 | +0.00 ± 0.00 | +0.000 ± 0.000 |
| failure_aware_mild | 20 | 2.32 ± 4.48 | 0.134 ± 0.063 | 0.140 | -0.40 ± 1.31 | -0.005 ± 0.015 |
| failure_aware_balanced | 20 | 2.78 ± 4.77 | 0.125 ± 0.063 | 0.120 | +0.06 ± 2.65 | -0.014 ± 0.042 |
| failure_aware_aggressive | 20 | 2.50 ± 4.75 | 0.104 ± 0.059 | 0.160 | -0.22 ± 4.11 | -0.035 ± 0.058 |

### high_uncertainty_pool

| Policy | Top-k | Mean failures ± std | Mean risk ± std | Best-known found rate | Δ failures vs LCB ± std | Δ risk vs LCB ± std |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| random_selection | 5 | 1.26 ± 1.07 | 0.146 ± 0.041 | 0.060 | +1.26 ± 1.07 | -0.029 ± 0.052 |
| lcb_only | 5 | 0.00 ± 0.00 | 0.174 ± 0.046 | 0.000 | +0.00 ± 0.00 | +0.000 ± 0.000 |
| failure_aware_mild | 5 | 0.00 ± 0.00 | 0.174 ± 0.046 | 0.000 | +0.00 ± 0.00 | +0.000 ± 0.000 |
| failure_aware_balanced | 5 | 0.00 ± 0.00 | 0.171 ± 0.045 | 0.000 | +0.00 ± 0.00 | -0.004 ± 0.017 |
| failure_aware_aggressive | 5 | 0.00 ± 0.00 | 0.093 ± 0.039 | 0.000 | +0.00 ± 0.00 | -0.081 ± 0.042 |
| random_selection | 10 | 3.02 ± 1.57 | 0.138 ± 0.031 | 0.060 | +3.02 ± 1.57 | -0.031 ± 0.049 |
| lcb_only | 10 | 0.00 ± 0.00 | 0.169 ± 0.043 | 0.000 | +0.00 ± 0.00 | +0.000 ± 0.000 |
| failure_aware_mild | 10 | 0.00 ± 0.00 | 0.169 ± 0.043 | 0.000 | +0.00 ± 0.00 | +0.000 ± 0.000 |
| failure_aware_balanced | 10 | 0.00 ± 0.00 | 0.131 ± 0.029 | 0.000 | +0.00 ± 0.00 | -0.038 ± 0.040 |
| failure_aware_aggressive | 10 | 0.06 ± 0.24 | 0.120 ± 0.026 | 0.000 | +0.06 ± 0.24 | -0.049 ± 0.039 |
| random_selection | 20 | 6.30 ± 1.82 | 0.141 ± 0.023 | 0.160 | +2.90 ± 2.34 | -0.034 ± 0.032 |
| lcb_only | 20 | 3.40 ± 1.84 | 0.175 ± 0.023 | 0.000 | +0.00 ± 0.00 | +0.000 ± 0.000 |
| failure_aware_mild | 20 | 2.62 ± 1.87 | 0.171 ± 0.022 | 0.000 | -0.78 ± 0.82 | -0.004 ± 0.004 |
| failure_aware_balanced | 20 | 2.62 ± 1.87 | 0.171 ± 0.023 | 0.000 | -0.78 ± 0.82 | -0.004 ± 0.004 |
| failure_aware_aggressive | 20 | 0.26 ± 0.44 | 0.091 ± 0.016 | 0.000 | -3.14 ± 1.83 | -0.083 ± 0.025 |

## Comparison vs v0.5.0

v0.5.0 ran a single offline trial on the full natural candidate pool (no repeated trials). v0.5.1's `normal_pool` mode is the closest equivalent here, repeated over 50 random sub-samples of that same pool:

- `lcb_only` (v0.5.0, single trial): 0 known failures, mean risk 0.152. `lcb_only` (v0.5.1, `normal_pool`, mean over 50 trials): 1.48 ± 1.33 known failures, mean risk 0.163 ± 0.038.
- `failure_aware_lcb_aggressive` (v0.5.0, single trial): 0 known failures, mean risk 0.066. `failure_aware_aggressive` (v0.5.1, `normal_pool`, mean over 50 trials): 0.30 ± 0.54 known failures, mean risk 0.096 ± 0.027.

## Scientific Caveats

1. This is an offline simulation using completed records; no new QE/PBE validation was performed.
2. Failure-risk estimates are inherited from earlier reliability modeling (v0.3.2) and may have split-to-split variance, as documented in the v0.5.0 report.
3. v0.5.1 stress-tests selection policy; it does not prove live DFT savings.
4. `predicted_value` remains a constant 0.0 placeholder, as in v0.5.0; policy differences come from the uncertainty proxy and the failure-risk penalty, not a live energy prediction.
5. `failure_enriched_pool` and `high_uncertainty_pool` resample existing real records (with replacement only if a target exceeds availability, which did not occur in this run); they do not fabricate new candidates or labels.
6. Because ranking has no live predicted-energy signal (caveat 4), `best_known_candidate_found_rate` mainly reflects incidental overlap between the uncertainty/risk-based ranking and the single lowest-known-energy success in each trial's pool. It is not a measure of optimization quality and is expected to be low.
7. Results should be interpreted as triage evidence, not a guarantee.

## Safe Claims

ActiStruct v0.5.1 extends the v0.5.0 offline benchmark into repeated stress tests. Across 50 trials, failure-aware LCB reduced the mean predicted failure risk in all tested pool modes. It also reduced known failed selections relative to LCB-only most clearly in `normal_pool` and `failure_enriched_pool`, while behavior was weaker (small, noisy mean reduction) in `heldout_material_pool` and not universally better in `high_uncertainty_pool`. These results support failure risk as a soft DFT triage signal, not a guarantee of live DFT savings.

## Next Steps

If failure-aware re-ranking shows a consistent advantage under stressed pools, the next step would be validating that advantage against a live GP/QE active-learning run (not yet performed here). v0.6 GNN-based surrogate modeling is out of scope until the offline failure-aware acquisition path itself is validated live.
