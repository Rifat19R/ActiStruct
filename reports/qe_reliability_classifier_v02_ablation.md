# QE Reliability Classifier v0.2 Ablation

## Purpose

This model predicts whether a Quantum ESPRESSO calculation record is expected to be successful using setup metadata only. The binary label is `success=1` when `failure_label == "success"`; all other failure labels are `success=0`.

The goal is not to reduce the failure count by relabeling data. The failure rows are the signal needed to learn failure risk. The right way to improve success rate is to use this model later as a penalty inside active acquisition.

## Files

- Input records: `data/parsed_records/qe_reliability_records.csv`
- ML table: `data/qe_reliability_ml_table.csv`
- Predictions: `data/qe_reliability_predictions_v02.csv`
- Rows modeled: **976**

## Experiments

- `baseline_random_split`: current leakage-safe setup metadata.
- `no_material_id_random_split`: removes `material_id` to test whether the model relies on local material/workflow identity.
- `material_group_split`: holds out whole `material_id` groups to test cross-material generalization.

## Leakage Controls

Excluded post-run or result-derived fields:

`calculation_hash`, `converged`, `energy_ev`, `failure_reason`, `final_energy_ry`, `job_done`, `max_force`, `pressure_kbar`, `scf_iterations`, `wall_time`

These excluded fields include energies, forces, wall time, SCF iteration count, convergence flags, and failure labels. They are outcomes or post-run diagnostics, not valid pre-run predictors.

## Metrics

| Experiment | Model | Status | Train | Test | Train S/F | Test S/F | Accuracy | Precision | Recall | Failure Recall | F1 | ROC-AUC |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline_random_split | LogisticRegression | trained | 780 | 196 | 471/309 | 118/78 | 0.918 | 0.990 | 0.873 | 0.987 | 0.928 | 0.970 |
| baseline_random_split | RandomForestClassifier | trained | 780 | 196 | 471/309 | 118/78 | 0.959 | 0.974 | 0.958 | 0.962 | 0.966 | 0.990 |
| baseline_random_split | CatBoostClassifier | skipped: dependency not installed | 780 | 196 | 471/309 | 118/78 | NA | NA | NA | NA | NA | NA |
| no_material_id_random_split | LogisticRegression | trained | 780 | 196 | 471/309 | 118/78 | 0.903 | 0.981 | 0.856 | 0.974 | 0.914 | 0.940 |
| no_material_id_random_split | RandomForestClassifier | trained | 780 | 196 | 471/309 | 118/78 | 0.934 | 0.973 | 0.915 | 0.962 | 0.943 | 0.982 |
| no_material_id_random_split | CatBoostClassifier | skipped: dependency not installed | 780 | 196 | 471/309 | 118/78 | NA | NA | NA | NA | NA | NA |
| material_group_split | LogisticRegression | trained | 704 | 272 | 500/204 | 89/183 | 0.228 | 0.253 | 0.697 | 0.000 | 0.371 | 0.352 |
| material_group_split | RandomForestClassifier | trained | 704 | 272 | 500/204 | 89/183 | 0.324 | 0.325 | 0.989 | 0.000 | 0.489 | 0.907 |
| material_group_split | CatBoostClassifier | skipped: dependency not installed | 704 | 272 | 500/204 | 89/183 | NA | NA | NA | NA | NA | NA |

## Feature Sets

| Experiment | Features |
| --- | --- |
| baseline_random_split | `material_id`, `ecutwfc`, `ecutrho`, `k1`, `k2`, `k3`, `kpoint_product`, `smearing`, `mixing_beta`, `pseudo_family`, `n_species`, `elements` |
| no_material_id_random_split | `ecutwfc`, `ecutrho`, `k1`, `k2`, `k3`, `kpoint_product`, `smearing`, `mixing_beta`, `pseudo_family`, `n_species`, `elements` |
| material_group_split | `material_id`, `ecutwfc`, `ecutrho`, `k1`, `k2`, `k3`, `kpoint_product`, `smearing`, `mixing_beta`, `pseudo_family`, `n_species`, `elements` |

## Confusion Matrices

### baseline_random_split / LogisticRegression

|  | Predicted failure | Predicted success |
| --- | ---: | ---: |
| Actual failure | 77 | 1 |
| Actual success | 15 | 103 |


### baseline_random_split / RandomForestClassifier

|  | Predicted failure | Predicted success |
| --- | ---: | ---: |
| Actual failure | 75 | 3 |
| Actual success | 5 | 113 |


### no_material_id_random_split / LogisticRegression

|  | Predicted failure | Predicted success |
| --- | ---: | ---: |
| Actual failure | 76 | 2 |
| Actual success | 17 | 101 |


### no_material_id_random_split / RandomForestClassifier

|  | Predicted failure | Predicted success |
| --- | ---: | ---: |
| Actual failure | 75 | 3 |
| Actual success | 10 | 108 |


### material_group_split / LogisticRegression

|  | Predicted failure | Predicted success |
| --- | ---: | ---: |
| Actual failure | 0 | 183 |
| Actual success | 27 | 62 |


### material_group_split / RandomForestClassifier

|  | Predicted failure | Predicted success |
| --- | ---: | ---: |
| Actual failure | 0 | 183 |
| Actual success | 1 | 88 |


## Top Features

### baseline_random_split / LogisticRegression

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

### baseline_random_split / RandomForestClassifier

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

### no_material_id_random_split / LogisticRegression

| Feature | Weight/importances |
| --- | ---: |
| `elements=Ni O` | -3.5594 |
| `elements=C O Pt` | -3.55676 |
| `elements=H` | -3.02346 |
| `elements=Co Na O` | -1.69248 |
| `elements=Fe Li O P` | -1.57798 |
| `elements=Co Li O` | -1.57524 |
| `elements=Cu` | -1.50195 |
| `elements=C H` | -1.47858 |
| `pseudo_family=PSLibrary` | -1.38323 |
| `elements=C` | 1.36036 |
| `elements=C Ni O` | 1.24828 |
| `mixing_beta` | 1.24419 |
| `elements=H O` | 1.12177 |
| `elements=Fe` | 1.0899 |
| `pseudo_family=ONCV` | 1.08001 |

### no_material_id_random_split / RandomForestClassifier

| Feature | Weight/importances |
| --- | ---: |
| `ecutrho` | 0.164849 |
| `ecutwfc` | 0.156513 |
| `mixing_beta` | 0.0691279 |
| `kpoint_product` | 0.063998 |
| `elements=C O Pt` | 0.0543899 |
| `n_species` | 0.0532134 |
| `k2` | 0.0457092 |
| `elements=H` | 0.0433589 |
| `k3` | 0.0401737 |
| `k1` | 0.0386697 |
| `elements=Ni O` | 0.0338446 |
| `smearing=mv` | 0.0327605 |
| `smearing=gaussian` | 0.0315118 |
| `pseudo_family=PSLibrary` | 0.0302958 |
| `pseudo_family=ONCV` | 0.0166715 |

### material_group_split / LogisticRegression

| Feature | Weight/importances |
| --- | ---: |
| `material_id=h2_r1p984848` | -2.50104 |
| `material_id=h2_r2p000000` | -2.50104 |
| `material_id=h2_generated` | 2.36708 |
| `elements=H` | -2.29847 |
| `material_id=bulk_si` | -2.25926 |
| `material_id=bulk_cu` | -2.07278 |
| `elements=Co Na O` | -1.61443 |
| `material_id=bulk_nacoo2` | -1.61443 |
| `material_id=bulk_cu_generated` | 1.60705 |
| `elements=Co Li O` | -1.4704 |
| `material_id=bulk_licoo2_generated` | -1.4704 |
| `material_id=bulk_si_generated` | 1.45375 |
| `pseudo_family=PSLibrary` | -1.39689 |
| `elements=C H` | -1.3154 |
| `material_id=ch4` | -1.3154 |

### material_group_split / RandomForestClassifier

| Feature | Weight/importances |
| --- | ---: |
| `ecutrho` | 0.112202 |
| `ecutwfc` | 0.102598 |
| `kpoint_product` | 0.0649096 |
| `k1` | 0.0554857 |
| `k2` | 0.0482107 |
| `n_species` | 0.0466011 |
| `material_id=bulk_cu` | 0.0465767 |
| `k3` | 0.0397602 |
| `material_id=h2_generated` | 0.0379751 |
| `mixing_beta` | 0.0350861 |
| `elements=H` | 0.0295832 |
| `pseudo_family=PSLibrary` | 0.0240377 |
| `material_id=bulk_si` | 0.0233941 |
| `material_id=h2_r2p000000` | 0.0233858 |
| `smearing=gaussian` | 0.021774 |

## Scientific Caveats

- The observed failure fraction is not a target to hide. It is the training signal for failure-risk-aware acquisition.
- The random split can overestimate performance because related records from the same material can appear in both train and test sets.
- The group split is stricter and should be treated as the more honest generalization test.
- `material_id` is pre-run metadata, but it can encode local workflow history. The no-material ablation helps quantify that dependence.
- The model does not inspect atomic geometry directly, so it should not replace the pre-QE overlap validator.
- Metrics are v0.2 engineering evidence, not a publication-level claim.

## Next Step

Connect predicted failure risk to Bayesian acquisition, for example by using `score = acquisition_value - lambda_failure * failure_risk` for maximization or adding a failure penalty for minimization.
