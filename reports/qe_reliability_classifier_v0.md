# QE Reliability Classifier v0.1

## Purpose

This model predicts whether a Quantum ESPRESSO calculation record is expected to be successful using setup metadata only. The binary label is `success=1` when `failure_label == "success"`; all other failure labels are `success=0`.

## Data

- Input records: `data/parsed_records/qe_reliability_records.csv`
- ML table: `data/qe_reliability_ml_table.csv`
- Total rows: **976**
- Train rows: **780**
- Test rows: **196**
- Success rows: **589**
- Failure rows: **387**

## Features Used

`material_id`, `ecutwfc`, `ecutrho`, `k1`, `k2`, `k3`, `kpoint_product`, `smearing`, `mixing_beta`, `pseudo_family`, `n_species`, `elements`

## Leakage Controls

The classifier excludes post-run or result-derived fields:

`calculation_hash`, `converged`, `energy_ev`, `failure_reason`, `final_energy_ry`, `job_done`, `max_force`, `pressure_kbar`, `scf_iterations`, `wall_time`

These excluded fields include energies, forces, wall time, SCF iteration count, convergence flags, and failure labels. They are outcomes or post-run diagnostics, not valid pre-run predictors.

## Metrics

| Model | Status | Accuracy | Precision | Recall | F1 | ROC-AUC |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| LogisticRegression | trained | 0.918 | 0.990 | 0.873 | 0.928 | 0.970 |
| RandomForestClassifier | trained | 0.959 | 0.974 | 0.958 | 0.966 | 0.990 |
| CatBoostClassifier | skipped: dependency not installed | NA | NA | NA | NA | NA |

## Confusion Matrices

### LogisticRegression

|  | Predicted failure | Predicted success |
| --- | ---: | ---: |
| Actual failure | 77 | 1 |
| Actual success | 15 | 103 |


### RandomForestClassifier

|  | Predicted failure | Predicted success |
| --- | ---: | ---: |
| Actual failure | 75 | 3 |
| Actual success | 5 | 113 |


## Top Features

### LogisticRegression

| Feature | Weight/importances |
| --- | ---: |
| `material_id=bulk_si` | -2.62889 |
| `material_id=h2_r1p984848` | -2.58974 |
| `material_id=h2_r2p000000` | -2.46579 |
| `elements=H` | -2.44359 |
| `material_id=bulk_cu` | -2.26945 |
| `material_id=h2_generated` | 1.9056 |
| `elements=C O Pt` | -1.83866 |
| `material_id=co_on_pt111` | -1.83866 |
| `elements=Ni O` | -1.77009 |
| `material_id=o_on_ni111` | -1.77009 |
| `material_id=ch4` | -1.69925 |
| `material_id=bulk_cu_generated` | 1.4375 |
| `mixing_beta` | 1.29209 |
| `pseudo_family=PSLibrary` | -1.17054 |
| `elements=Fe Li O P` | -1.16575 |

### RandomForestClassifier

| Feature | Weight/importances |
| --- | ---: |
| `ecutwfc` | 0.118135 |
| `ecutrho` | 0.107686 |
| `mixing_beta` | 0.0568618 |
| `kpoint_product` | 0.0479066 |
| `material_id=co_on_pt111` | 0.0431937 |
| `elements=C O Pt` | 0.0415524 |
| `n_species` | 0.0413911 |
| `k2` | 0.040232 |
| `k1` | 0.0376011 |
| `k3` | 0.0356449 |
| `elements=H` | 0.0321922 |
| `material_id=bulk_cu` | 0.0275374 |
| `material_id=h2_r1p984848` | 0.0256331 |
| `pseudo_family=PSLibrary` | 0.0245026 |
| `material_id=o_on_ni111` | 0.0240438 |

## Scientific Caveats

- The current dataset is local and scratch-heavy, so the model may learn project-specific workflow patterns rather than general DFT reliability.
- `material_id` is a pre-run metadata field, but it can encode local workflow history and should be ablated in the next version.
- The model does not inspect atomic geometry directly, so it should not replace the pre-QE overlap validator.
- Metrics are a v0.1 baseline on one train/test split, not a publication claim.
- Records from other electronic-structure codes must be modeled with source-code provenance preserved.

## Next Step

Connect predicted failure risk to Bayesian acquisition, for example by using `score = acquisition_value - lambda_failure * failure_risk` for maximization or adding a failure penalty for minimization.
