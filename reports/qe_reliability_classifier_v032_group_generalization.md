# QE Reliability Classifier v0.3.2 Group Generalization

## Purpose

This experiment improves the v0.3 held-out-material analysis by using separate failure-risk targets, lower failure-risk thresholds, repeated group splits, and an OOD distance flag.

## Files

- Input records: `data/parsed_records/qe_reliability_records.csv`
- Predictions: `data/qe_reliability_predictions_v032.csv`
- Repeated group splits: **20**

## Model

Separate balanced RandomForest risk models are trained for setup errors, SCF non-convergence, and runtime incompletion. Total failure risk is `1 - product(1 - component_risk)`.

## Repeated Group-Split Metrics

| Threshold | Failure recall mean +/- std | Failure precision mean +/- std | F1 mean +/- std | ROC-AUC mean +/- std |
| ---: | ---: | ---: | ---: | ---: |
| 0.05 | 0.776 +/- 0.344 | 0.363 +/- 0.250 | 0.442 +/- 0.283 | 0.604 +/- 0.200 |
| 0.10 | 0.725 +/- 0.377 | 0.367 +/- 0.250 | 0.429 +/- 0.291 | 0.604 +/- 0.200 |
| 0.15 | 0.571 +/- 0.385 | 0.365 +/- 0.274 | 0.392 +/- 0.312 | 0.604 +/- 0.200 |
| 0.20 | 0.465 +/- 0.392 | 0.376 +/- 0.285 | 0.386 +/- 0.310 | 0.604 +/- 0.200 |
| 0.25 | 0.364 +/- 0.386 | 0.345 +/- 0.307 | 0.326 +/- 0.310 | 0.604 +/- 0.200 |
| 0.30 | 0.300 +/- 0.359 | 0.329 +/- 0.316 | 0.281 +/- 0.297 | 0.604 +/- 0.200 |
| 0.40 | 0.285 +/- 0.339 | 0.342 +/- 0.330 | 0.281 +/- 0.297 | 0.604 +/- 0.200 |
| 0.50 | 0.251 +/- 0.308 | 0.455 +/- 0.400 | 0.274 +/- 0.305 | 0.604 +/- 0.200 |

## Scientific Caveats

- The current records still lack trustworthy atom counts, cell volumes, and true stoichiometric fractions, so some requested descriptors remain nullable or species-presence approximations.
- Runtime incompletion may reflect walltime or machine interruption rather than chemistry, so it is modeled separately.
- Group-split metrics are the honest signal for new materials. If failure recall remains low, this model should be used only as an in-domain workflow triage aid.
