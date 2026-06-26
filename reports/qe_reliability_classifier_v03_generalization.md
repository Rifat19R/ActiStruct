# QE Reliability Classifier v0.3 Generalization

## Purpose

This model predicts whether a Quantum ESPRESSO calculation record is expected to be successful using setup metadata only. The binary label is `success=1` when `failure_label == "success"`; all other failure labels are `success=0`.

The goal is not to reduce the failure count by relabeling data. The failure rows are the signal needed to learn failure risk. The right way to improve success rate is to use this model later as a penalty inside active acquisition.

## Files

- Input records: `data/parsed_records/qe_reliability_records.csv`
- ML table: `data/qe_reliability_ml_table.csv`
- Predictions: `data/qe_reliability_predictions_v03.csv`
- Rows modeled: **976**

## Experiments

- `baseline_random_split`: current leakage-safe setup metadata.
- `no_material_id_random_split`: removes `material_id` to test whether the model relies on local material/workflow identity.
- `material_group_split`: holds out whole `material_id` groups to test cross-material generalization.

## Leakage Controls

Excluded post-run or result-derived fields:

`calculation_hash`, `converged`, `energy_ev`, `failure_reason`, `final_energy_ry`, `job_done`, `max_force`, `pressure_kbar`, `scf_iterations`, `wall_time`

These excluded fields include energies, forces, wall time, SCF iteration count, convergence flags, and failure labels. They are outcomes or post-run diagnostics, not valid pre-run predictors.

## Descriptor Features

v0.3 adds pre-run descriptors derived from setup metadata: species count, element presence/count indicators, atomic number/mass/electronegativity summaries, transition-metal/oxygen/hydrogen flags, `ecutrho/ecutwfc`, and k-point product.

`n_atoms` and `volume_per_atom` are included as nullable columns because the current parsed reliability records do not carry trustworthy atom counts or cell volumes. Element counts are species-presence indicators from pseudopotential declarations, not stoichiometric atom counts.

## Default Threshold Metrics

| Experiment | Model | Status | Train | Test | Train S/F | Test S/F | Accuracy | Precision | Recall | Failure Recall | F1 | ROC-AUC |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline_random_split | LogisticRegression | trained | 780 | 196 | 471/309 | 118/78 | 0.913 | 0.990 | 0.864 | 0.987 | 0.923 | 0.976 |
| baseline_random_split | RandomForestClassifier | trained | 780 | 196 | 471/309 | 118/78 | 0.959 | 0.974 | 0.958 | 0.962 | 0.966 | 0.992 |
| baseline_random_split | CatBoostClassifier | skipped: dependency not installed | 780 | 196 | 471/309 | 118/78 | NA | NA | NA | NA | NA | NA |
| no_material_id_random_split | LogisticRegression | trained | 780 | 196 | 471/309 | 118/78 | 0.908 | 0.981 | 0.864 | 0.974 | 0.919 | 0.955 |
| no_material_id_random_split | RandomForestClassifier | trained | 780 | 196 | 471/309 | 118/78 | 0.934 | 0.973 | 0.915 | 0.962 | 0.943 | 0.983 |
| no_material_id_random_split | CatBoostClassifier | skipped: dependency not installed | 780 | 196 | 471/309 | 118/78 | NA | NA | NA | NA | NA | NA |
| material_group_split | LogisticRegression | trained | 704 | 272 | 500/204 | 89/183 | 0.228 | 0.253 | 0.697 | 0.000 | 0.371 | 0.367 |
| material_group_split | RandomForestClassifier | trained | 704 | 272 | 500/204 | 89/183 | 0.324 | 0.325 | 0.989 | 0.000 | 0.489 | 0.455 |
| material_group_split | CatBoostClassifier | skipped: dependency not installed | 704 | 272 | 500/204 | 89/183 | NA | NA | NA | NA | NA | NA |

## Threshold Sweep

Thresholds are applied to `success_probability`. Higher thresholds are more conservative: they classify more calculations as risky, which can improve failure recall at the cost of rejecting more potentially successful candidates.

| Experiment | Model | Threshold | Precision | Recall | Failure Recall | F1 | Confusion [[TN, FP], [FN, TP]] |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| baseline_random_split | LogisticRegression | 0.3 | 0.925 | 0.941 | 0.885 | 0.933 | [[69, 9], [7, 111]] |
| baseline_random_split | LogisticRegression | 0.4 | 0.973 | 0.932 | 0.962 | 0.952 | [[75, 3], [8, 110]] |
| baseline_random_split | LogisticRegression | 0.5 | 0.990 | 0.864 | 0.987 | 0.923 | [[77, 1], [16, 102]] |
| baseline_random_split | LogisticRegression | 0.6 | 0.990 | 0.864 | 0.987 | 0.923 | [[77, 1], [16, 102]] |
| baseline_random_split | LogisticRegression | 0.7 | 0.990 | 0.856 | 0.987 | 0.918 | [[77, 1], [17, 101]] |
| baseline_random_split | RandomForestClassifier | 0.3 | 0.958 | 0.975 | 0.936 | 0.966 | [[73, 5], [3, 115]] |
| baseline_random_split | RandomForestClassifier | 0.4 | 0.958 | 0.975 | 0.936 | 0.966 | [[73, 5], [3, 115]] |
| baseline_random_split | RandomForestClassifier | 0.5 | 0.974 | 0.958 | 0.962 | 0.966 | [[75, 3], [5, 113]] |
| baseline_random_split | RandomForestClassifier | 0.6 | 0.972 | 0.898 | 0.962 | 0.934 | [[75, 3], [12, 106]] |
| baseline_random_split | RandomForestClassifier | 0.7 | 0.972 | 0.898 | 0.962 | 0.934 | [[75, 3], [12, 106]] |
| no_material_id_random_split | LogisticRegression | 0.3 | 0.893 | 0.915 | 0.833 | 0.904 | [[65, 13], [10, 108]] |
| no_material_id_random_split | LogisticRegression | 0.4 | 0.893 | 0.915 | 0.833 | 0.904 | [[65, 13], [10, 108]] |
| no_material_id_random_split | LogisticRegression | 0.5 | 0.981 | 0.864 | 0.974 | 0.919 | [[76, 2], [16, 102]] |
| no_material_id_random_split | LogisticRegression | 0.6 | 0.989 | 0.771 | 0.987 | 0.867 | [[77, 1], [27, 91]] |
| no_material_id_random_split | LogisticRegression | 0.7 | 0.989 | 0.746 | 0.987 | 0.850 | [[77, 1], [30, 88]] |
| no_material_id_random_split | RandomForestClassifier | 0.3 | 0.949 | 0.949 | 0.923 | 0.949 | [[72, 6], [6, 112]] |
| no_material_id_random_split | RandomForestClassifier | 0.4 | 0.957 | 0.932 | 0.936 | 0.944 | [[73, 5], [8, 110]] |
| no_material_id_random_split | RandomForestClassifier | 0.5 | 0.973 | 0.915 | 0.962 | 0.943 | [[75, 3], [10, 108]] |
| no_material_id_random_split | RandomForestClassifier | 0.6 | 0.972 | 0.898 | 0.962 | 0.934 | [[75, 3], [12, 106]] |
| no_material_id_random_split | RandomForestClassifier | 0.7 | 0.981 | 0.856 | 0.974 | 0.914 | [[76, 2], [17, 101]] |
| material_group_split | LogisticRegression | 0.3 | 0.253 | 0.697 | 0.000 | 0.371 | [[0, 183], [27, 62]] |
| material_group_split | LogisticRegression | 0.4 | 0.253 | 0.697 | 0.000 | 0.371 | [[0, 183], [27, 62]] |
| material_group_split | LogisticRegression | 0.5 | 0.253 | 0.697 | 0.000 | 0.371 | [[0, 183], [27, 62]] |
| material_group_split | LogisticRegression | 0.6 | 0.234 | 0.629 | 0.000 | 0.341 | [[0, 183], [33, 56]] |
| material_group_split | LogisticRegression | 0.7 | 0.234 | 0.629 | 0.000 | 0.341 | [[0, 183], [33, 56]] |
| material_group_split | RandomForestClassifier | 0.3 | 0.325 | 0.989 | 0.000 | 0.489 | [[0, 183], [1, 88]] |
| material_group_split | RandomForestClassifier | 0.4 | 0.325 | 0.989 | 0.000 | 0.489 | [[0, 183], [1, 88]] |
| material_group_split | RandomForestClassifier | 0.5 | 0.325 | 0.989 | 0.000 | 0.489 | [[0, 183], [1, 88]] |
| material_group_split | RandomForestClassifier | 0.6 | 0.309 | 0.921 | 0.000 | 0.463 | [[0, 183], [7, 82]] |
| material_group_split | RandomForestClassifier | 0.7 | 0.285 | 0.820 | 0.000 | 0.423 | [[0, 183], [16, 73]] |

## Generalization Readout

- In-domain performance is represented by `baseline_random_split`.
- Out-of-domain performance is represented by `material_group_split`, where complete `material_id` groups are held out.
- Random-split RandomForest default failure recall: 0.962.
- Group-split RandomForest default failure recall: 0.000.
- Best random-split threshold failure recall: 0.962.
- Best group-split threshold failure recall: 0.000.
- Threshold tuning does not improve group-split failure recall relative to the default 0.5 operating point.

## Feature Sets

| Experiment | Features |
| --- | --- |
| baseline_random_split | `material_id`, `ecutwfc`, `ecutrho`, `k1`, `k2`, `k3`, `kpoint_product`, `smearing`, `mixing_beta`, `pseudo_family`, `n_atoms`, `n_species`, `elements`, `atomic_number_mean`, `atomic_number_min`, `atomic_number_max`, `atomic_mass_mean`, `electronegativity_mean`, `has_transition_metal`, `has_oxygen`, `has_hydrogen`, `ecutrho_over_ecutwfc`, `volume_per_atom`, `element_count_Ag`, `element_count_Al`, `element_count_As`, `element_count_Au`, `element_count_Ba`, `element_count_C`, `element_count_Ca`, `element_count_Co`, `element_count_Cu`, `element_count_Fe`, `element_count_H`, `element_count_I`, `element_count_K`, `element_count_Li`, `element_count_Mg`, `element_count_Mo`, `element_count_N`, `element_count_Na`, `element_count_Ni`, `element_count_O`, `element_count_P`, `element_count_Pb`, `element_count_Pt`, `element_count_S`, `element_count_Si`, `element_count_Sr`, `element_count_Ti`, `element_count_V`, `element_count_W`, `element_count_Zn` |
| no_material_id_random_split | `ecutwfc`, `ecutrho`, `k1`, `k2`, `k3`, `kpoint_product`, `smearing`, `mixing_beta`, `pseudo_family`, `n_atoms`, `n_species`, `elements`, `atomic_number_mean`, `atomic_number_min`, `atomic_number_max`, `atomic_mass_mean`, `electronegativity_mean`, `has_transition_metal`, `has_oxygen`, `has_hydrogen`, `ecutrho_over_ecutwfc`, `volume_per_atom`, `element_count_Ag`, `element_count_Al`, `element_count_As`, `element_count_Au`, `element_count_Ba`, `element_count_C`, `element_count_Ca`, `element_count_Co`, `element_count_Cu`, `element_count_Fe`, `element_count_H`, `element_count_I`, `element_count_K`, `element_count_Li`, `element_count_Mg`, `element_count_Mo`, `element_count_N`, `element_count_Na`, `element_count_Ni`, `element_count_O`, `element_count_P`, `element_count_Pb`, `element_count_Pt`, `element_count_S`, `element_count_Si`, `element_count_Sr`, `element_count_Ti`, `element_count_V`, `element_count_W`, `element_count_Zn` |
| material_group_split | `material_id`, `ecutwfc`, `ecutrho`, `k1`, `k2`, `k3`, `kpoint_product`, `smearing`, `mixing_beta`, `pseudo_family`, `n_atoms`, `n_species`, `elements`, `atomic_number_mean`, `atomic_number_min`, `atomic_number_max`, `atomic_mass_mean`, `electronegativity_mean`, `has_transition_metal`, `has_oxygen`, `has_hydrogen`, `ecutrho_over_ecutwfc`, `volume_per_atom`, `element_count_Ag`, `element_count_Al`, `element_count_As`, `element_count_Au`, `element_count_Ba`, `element_count_C`, `element_count_Ca`, `element_count_Co`, `element_count_Cu`, `element_count_Fe`, `element_count_H`, `element_count_I`, `element_count_K`, `element_count_Li`, `element_count_Mg`, `element_count_Mo`, `element_count_N`, `element_count_Na`, `element_count_Ni`, `element_count_O`, `element_count_P`, `element_count_Pb`, `element_count_Pt`, `element_count_S`, `element_count_Si`, `element_count_Sr`, `element_count_Ti`, `element_count_V`, `element_count_W`, `element_count_Zn` |

## Confusion Matrices

### baseline_random_split / LogisticRegression

|  | Predicted failure | Predicted success |
| --- | ---: | ---: |
| Actual failure | 77 | 1 |
| Actual success | 16 | 102 |


### baseline_random_split / RandomForestClassifier

|  | Predicted failure | Predicted success |
| --- | ---: | ---: |
| Actual failure | 75 | 3 |
| Actual success | 5 | 113 |


### no_material_id_random_split / LogisticRegression

|  | Predicted failure | Predicted success |
| --- | ---: | ---: |
| Actual failure | 76 | 2 |
| Actual success | 16 | 102 |


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
| `material_id=h2_r1p984848` | -2.39663 |
| `material_id=bulk_cu` | -2.30685 |
| `elements=Ni O` | -2.29254 |
| `material_id=o_on_ni111` | -2.29254 |
| `material_id=h2_r2p000000` | -2.27741 |
| `material_id=bulk_si` | -2.26821 |
| `material_id=h2_generated` | 2.04672 |
| `material_id=ch4` | -1.83135 |
| `elements=H` | -1.67453 |
| `elements=C H` | -1.32134 |
| `elements=Cu` | -1.2782 |
| `material_id=bulk_si_generated` | 1.19852 |
| `elements=Fe Li O P` | -1.16893 |
| `material_id=bulk_lifepo4` | -1.16893 |
| `element_count_H` | -1.10619 |

### baseline_random_split / RandomForestClassifier

| Feature | Weight/importances |
| --- | ---: |
| `ecutrho` | 0.0927148 |
| `ecutwfc` | 0.0898975 |
| `electronegativity_mean` | 0.0682938 |
| `atomic_number_max` | 0.0433098 |
| `atomic_mass_mean` | 0.042715 |
| `mixing_beta` | 0.0415214 |
| `atomic_number_mean` | 0.0390944 |
| `kpoint_product` | 0.0345224 |
| `k2` | 0.0291474 |
| `elements=C O Pt` | 0.0267589 |
| `atomic_number_min` | 0.0262041 |
| `material_id=bulk_cu` | 0.0240411 |
| `k1` | 0.0234081 |
| `material_id=bulk_si` | 0.0210561 |
| `k3` | 0.0209978 |

### no_material_id_random_split / LogisticRegression

| Feature | Weight/importances |
| --- | ---: |
| `elements=Ni O` | -4.01041 |
| `elements=C H` | -2.1161 |
| `elements=H` | -2.02788 |
| `elements=Fe Li O P` | -1.70127 |
| `elements=Cu` | -1.68504 |
| `element_count_Ni` | -1.50236 |
| `element_count_Ti` | 1.46064 |
| `elements=C` | 1.24577 |
| `elements=Fe` | 1.22303 |
| `elements=C Ni O` | 1.22243 |
| `elements=H O` | 1.21075 |
| `element_count_H` | -1.11692 |
| `has_hydrogen` | -1.11692 |
| `elements=Li O Ti` | 1.11647 |
| `has_transition_metal` | -1.1035 |

### no_material_id_random_split / RandomForestClassifier

| Feature | Weight/importances |
| --- | ---: |
| `ecutwfc` | 0.125687 |
| `ecutrho` | 0.123965 |
| `electronegativity_mean` | 0.0726209 |
| `mixing_beta` | 0.0595344 |
| `atomic_number_max` | 0.0498583 |
| `atomic_mass_mean` | 0.0496113 |
| `atomic_number_mean` | 0.042425 |
| `kpoint_product` | 0.0390031 |
| `k2` | 0.0298097 |
| `smearing=gaussian` | 0.0270944 |
| `k1` | 0.0261918 |
| `atomic_number_min` | 0.025635 |
| `smearing=mv` | 0.0255269 |
| `k3` | 0.0245292 |
| `n_species` | 0.0239039 |

### material_group_split / LogisticRegression

| Feature | Weight/importances |
| --- | ---: |
| `material_id=h2_generated` | 2.61085 |
| `material_id=h2_r1p984848` | -2.23132 |
| `material_id=h2_r2p000000` | -2.23132 |
| `material_id=bulk_cu` | -2.10801 |
| `material_id=bulk_si` | -2.01029 |
| `material_id=bulk_si_generated` | 1.60399 |
| `material_id=bulk_cu_generated` | 1.43341 |
| `elements=H` | -1.23064 |
| `element_count_Co` | -1.20362 |
| `elements=C H` | -1.13049 |
| `material_id=ch4` | -1.13049 |
| `element_count_H` | -1.03029 |
| `has_hydrogen` | -1.03029 |
| `element_count_Al` | 1.01071 |
| `elements=H O` | 0.962467 |

### material_group_split / RandomForestClassifier

| Feature | Weight/importances |
| --- | ---: |
| `electronegativity_mean` | 0.0842613 |
| `ecutrho` | 0.0732909 |
| `ecutwfc` | 0.0705025 |
| `atomic_number_max` | 0.0548411 |
| `atomic_mass_mean` | 0.0490277 |
| `material_id=bulk_cu` | 0.0420814 |
| `atomic_number_mean` | 0.0419006 |
| `kpoint_product` | 0.0380037 |
| `material_id=h2_generated` | 0.0362036 |
| `k2` | 0.0360016 |
| `k1` | 0.0334528 |
| `k3` | 0.0284083 |
| `n_species` | 0.0282364 |
| `element_count_Co` | 0.0231808 |
| `material_id=bulk_si_generated` | 0.0230898 |

## Scientific Caveats

- The observed failure fraction is not a target to hide. It is the training signal for failure-risk-aware acquisition.
- The random split measures in-domain interpolation over current records and can overestimate performance because related records can appear in both train and test sets.
- The group split is the stricter held-out-material test and should guide deployment caution.
- Missing atom counts and cell volumes limit descriptor strength. Current element indicators describe species presence, not full composition.
- `material_id` is pre-run metadata, but it can encode local workflow history. The no-material ablation helps quantify that dependence.
- The model does not inspect atomic geometry directly, so it should not replace the pre-QE overlap validator.
- Metrics are v0.3 engineering evidence, not a publication-level claim.

## Next Step

Connect predicted failure risk to Bayesian acquisition, for example by using `score = acquisition_value - lambda_failure * failure_risk` for maximization or adding a failure penalty for minimization. Choose the operating threshold from the grouped split, where possible, because it is the more honest proxy for new-material behavior.
