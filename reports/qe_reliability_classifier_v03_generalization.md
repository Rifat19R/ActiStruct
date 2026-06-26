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
| baseline_random_split | LogisticRegression | trained | 780 | 196 | 471/309 | 118/78 | 0.929 | 0.991 | 0.890 | 0.987 | 0.938 | 0.981 |
| baseline_random_split | RandomForestClassifier | trained | 780 | 196 | 471/309 | 118/78 | 0.959 | 0.974 | 0.958 | 0.962 | 0.966 | 0.991 |
| baseline_random_split | CatBoostClassifier | skipped: dependency not installed | 780 | 196 | 471/309 | 118/78 | NA | NA | NA | NA | NA | NA |
| no_material_id_random_split | LogisticRegression | trained | 780 | 196 | 471/309 | 118/78 | 0.908 | 0.981 | 0.864 | 0.974 | 0.919 | 0.960 |
| no_material_id_random_split | RandomForestClassifier | trained | 780 | 196 | 471/309 | 118/78 | 0.934 | 0.973 | 0.915 | 0.962 | 0.943 | 0.984 |
| no_material_id_random_split | CatBoostClassifier | skipped: dependency not installed | 780 | 196 | 471/309 | 118/78 | NA | NA | NA | NA | NA | NA |
| material_group_split | LogisticRegression | trained | 704 | 272 | 500/204 | 89/183 | 0.217 | 0.244 | 0.663 | 0.000 | 0.356 | 0.229 |
| material_group_split | RandomForestClassifier | trained | 704 | 272 | 500/204 | 89/183 | 0.301 | 0.309 | 0.921 | 0.000 | 0.463 | 0.369 |
| material_group_split | CatBoostClassifier | skipped: dependency not installed | 704 | 272 | 500/204 | 89/183 | NA | NA | NA | NA | NA | NA |

## Threshold Sweep

Thresholds are applied to `success_probability`. Higher thresholds are more conservative: they classify more calculations as risky, which can improve failure recall at the cost of rejecting more potentially successful candidates.

| Experiment | Model | Threshold | Precision | Recall | Failure Recall | F1 | Confusion [[TN, FP], [FN, TP]] |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| baseline_random_split | LogisticRegression | 0.3 | 0.925 | 0.941 | 0.885 | 0.933 | [[69, 9], [7, 111]] |
| baseline_random_split | LogisticRegression | 0.4 | 0.973 | 0.932 | 0.962 | 0.952 | [[75, 3], [8, 110]] |
| baseline_random_split | LogisticRegression | 0.5 | 0.991 | 0.890 | 0.987 | 0.938 | [[77, 1], [13, 105]] |
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
| no_material_id_random_split | LogisticRegression | 0.7 | 0.989 | 0.754 | 0.987 | 0.856 | [[77, 1], [29, 89]] |
| no_material_id_random_split | RandomForestClassifier | 0.3 | 0.957 | 0.932 | 0.936 | 0.944 | [[73, 5], [8, 110]] |
| no_material_id_random_split | RandomForestClassifier | 0.4 | 0.957 | 0.932 | 0.936 | 0.944 | [[73, 5], [8, 110]] |
| no_material_id_random_split | RandomForestClassifier | 0.5 | 0.973 | 0.915 | 0.962 | 0.943 | [[75, 3], [10, 108]] |
| no_material_id_random_split | RandomForestClassifier | 0.6 | 0.972 | 0.898 | 0.962 | 0.934 | [[75, 3], [12, 106]] |
| no_material_id_random_split | RandomForestClassifier | 0.7 | 0.972 | 0.898 | 0.962 | 0.934 | [[75, 3], [12, 106]] |
| material_group_split | LogisticRegression | 0.3 | 0.253 | 0.697 | 0.000 | 0.371 | [[0, 183], [27, 62]] |
| material_group_split | LogisticRegression | 0.4 | 0.253 | 0.697 | 0.000 | 0.371 | [[0, 183], [27, 62]] |
| material_group_split | LogisticRegression | 0.5 | 0.244 | 0.663 | 0.000 | 0.356 | [[0, 183], [30, 59]] |
| material_group_split | LogisticRegression | 0.6 | 0.225 | 0.596 | 0.000 | 0.326 | [[0, 183], [36, 53]] |
| material_group_split | LogisticRegression | 0.7 | 0.204 | 0.528 | 0.000 | 0.295 | [[0, 183], [42, 47]] |
| material_group_split | RandomForestClassifier | 0.3 | 0.325 | 0.989 | 0.000 | 0.489 | [[0, 183], [1, 88]] |
| material_group_split | RandomForestClassifier | 0.4 | 0.325 | 0.989 | 0.000 | 0.489 | [[0, 183], [1, 88]] |
| material_group_split | RandomForestClassifier | 0.5 | 0.309 | 0.921 | 0.000 | 0.463 | [[0, 183], [7, 82]] |
| material_group_split | RandomForestClassifier | 0.6 | 0.293 | 0.854 | 0.000 | 0.437 | [[0, 183], [13, 76]] |
| material_group_split | RandomForestClassifier | 0.7 | 0.293 | 0.854 | 0.000 | 0.437 | [[0, 183], [13, 76]] |

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
| baseline_random_split | `material_id`, `ecutwfc`, `ecutrho`, `k1`, `k2`, `k3`, `kpoint_product`, `smearing`, `mixing_beta`, `pseudo_family`, `n_atoms`, `n_species`, `elements`, `atomic_number_mean`, `atomic_number_std`, `atomic_number_min`, `atomic_number_max`, `atomic_mass_mean`, `atomic_mass_std`, `electronegativity_mean`, `electronegativity_std`, `atomic_radius_mean`, `atomic_radius_std`, `metal_fraction`, `transition_metal_fraction`, `has_transition_metal`, `has_oxygen`, `has_hydrogen`, `has_fluorine`, `has_sulfur`, `has_heavy_element`, `ecutrho_over_ecutwfc`, `natoms_times_kpoints`, `natoms_times_ecutwfc`, `volume_per_atom`, `element_count_Ag`, `element_count_Al`, `element_count_As`, `element_count_Au`, `element_count_Ba`, `element_count_C`, `element_count_Ca`, `element_count_Co`, `element_count_Cu`, `element_count_F`, `element_count_Fe`, `element_count_H`, `element_count_I`, `element_count_K`, `element_count_Li`, `element_count_Mg`, `element_count_Mo`, `element_count_N`, `element_count_Na`, `element_count_Ni`, `element_count_O`, `element_count_P`, `element_count_Pb`, `element_count_Pt`, `element_count_S`, `element_count_Si`, `element_count_Sr`, `element_count_Ti`, `element_count_V`, `element_count_W`, `element_count_Zn`, `element_fraction_Ag`, `element_fraction_Al`, `element_fraction_As`, `element_fraction_Au`, `element_fraction_Ba`, `element_fraction_C`, `element_fraction_Ca`, `element_fraction_Co`, `element_fraction_Cu`, `element_fraction_F`, `element_fraction_Fe`, `element_fraction_H`, `element_fraction_I`, `element_fraction_K`, `element_fraction_Li`, `element_fraction_Mg`, `element_fraction_Mo`, `element_fraction_N`, `element_fraction_Na`, `element_fraction_Ni`, `element_fraction_O`, `element_fraction_P`, `element_fraction_Pb`, `element_fraction_Pt`, `element_fraction_S`, `element_fraction_Si`, `element_fraction_Sr`, `element_fraction_Ti`, `element_fraction_V`, `element_fraction_W`, `element_fraction_Zn` |
| no_material_id_random_split | `ecutwfc`, `ecutrho`, `k1`, `k2`, `k3`, `kpoint_product`, `smearing`, `mixing_beta`, `pseudo_family`, `n_atoms`, `n_species`, `elements`, `atomic_number_mean`, `atomic_number_std`, `atomic_number_min`, `atomic_number_max`, `atomic_mass_mean`, `atomic_mass_std`, `electronegativity_mean`, `electronegativity_std`, `atomic_radius_mean`, `atomic_radius_std`, `metal_fraction`, `transition_metal_fraction`, `has_transition_metal`, `has_oxygen`, `has_hydrogen`, `has_fluorine`, `has_sulfur`, `has_heavy_element`, `ecutrho_over_ecutwfc`, `natoms_times_kpoints`, `natoms_times_ecutwfc`, `volume_per_atom`, `element_count_Ag`, `element_count_Al`, `element_count_As`, `element_count_Au`, `element_count_Ba`, `element_count_C`, `element_count_Ca`, `element_count_Co`, `element_count_Cu`, `element_count_F`, `element_count_Fe`, `element_count_H`, `element_count_I`, `element_count_K`, `element_count_Li`, `element_count_Mg`, `element_count_Mo`, `element_count_N`, `element_count_Na`, `element_count_Ni`, `element_count_O`, `element_count_P`, `element_count_Pb`, `element_count_Pt`, `element_count_S`, `element_count_Si`, `element_count_Sr`, `element_count_Ti`, `element_count_V`, `element_count_W`, `element_count_Zn`, `element_fraction_Ag`, `element_fraction_Al`, `element_fraction_As`, `element_fraction_Au`, `element_fraction_Ba`, `element_fraction_C`, `element_fraction_Ca`, `element_fraction_Co`, `element_fraction_Cu`, `element_fraction_F`, `element_fraction_Fe`, `element_fraction_H`, `element_fraction_I`, `element_fraction_K`, `element_fraction_Li`, `element_fraction_Mg`, `element_fraction_Mo`, `element_fraction_N`, `element_fraction_Na`, `element_fraction_Ni`, `element_fraction_O`, `element_fraction_P`, `element_fraction_Pb`, `element_fraction_Pt`, `element_fraction_S`, `element_fraction_Si`, `element_fraction_Sr`, `element_fraction_Ti`, `element_fraction_V`, `element_fraction_W`, `element_fraction_Zn` |
| material_group_split | `material_id`, `ecutwfc`, `ecutrho`, `k1`, `k2`, `k3`, `kpoint_product`, `smearing`, `mixing_beta`, `pseudo_family`, `n_atoms`, `n_species`, `elements`, `atomic_number_mean`, `atomic_number_std`, `atomic_number_min`, `atomic_number_max`, `atomic_mass_mean`, `atomic_mass_std`, `electronegativity_mean`, `electronegativity_std`, `atomic_radius_mean`, `atomic_radius_std`, `metal_fraction`, `transition_metal_fraction`, `has_transition_metal`, `has_oxygen`, `has_hydrogen`, `has_fluorine`, `has_sulfur`, `has_heavy_element`, `ecutrho_over_ecutwfc`, `natoms_times_kpoints`, `natoms_times_ecutwfc`, `volume_per_atom`, `element_count_Ag`, `element_count_Al`, `element_count_As`, `element_count_Au`, `element_count_Ba`, `element_count_C`, `element_count_Ca`, `element_count_Co`, `element_count_Cu`, `element_count_F`, `element_count_Fe`, `element_count_H`, `element_count_I`, `element_count_K`, `element_count_Li`, `element_count_Mg`, `element_count_Mo`, `element_count_N`, `element_count_Na`, `element_count_Ni`, `element_count_O`, `element_count_P`, `element_count_Pb`, `element_count_Pt`, `element_count_S`, `element_count_Si`, `element_count_Sr`, `element_count_Ti`, `element_count_V`, `element_count_W`, `element_count_Zn`, `element_fraction_Ag`, `element_fraction_Al`, `element_fraction_As`, `element_fraction_Au`, `element_fraction_Ba`, `element_fraction_C`, `element_fraction_Ca`, `element_fraction_Co`, `element_fraction_Cu`, `element_fraction_F`, `element_fraction_Fe`, `element_fraction_H`, `element_fraction_I`, `element_fraction_K`, `element_fraction_Li`, `element_fraction_Mg`, `element_fraction_Mo`, `element_fraction_N`, `element_fraction_Na`, `element_fraction_Ni`, `element_fraction_O`, `element_fraction_P`, `element_fraction_Pb`, `element_fraction_Pt`, `element_fraction_S`, `element_fraction_Si`, `element_fraction_Sr`, `element_fraction_Ti`, `element_fraction_V`, `element_fraction_W`, `element_fraction_Zn` |

## Confusion Matrices

### baseline_random_split / LogisticRegression

|  | Predicted failure | Predicted success |
| --- | ---: | ---: |
| Actual failure | 77 | 1 |
| Actual success | 13 | 105 |


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
| Actual success | 30 | 59 |


### material_group_split / RandomForestClassifier

|  | Predicted failure | Predicted success |
| --- | ---: | ---: |
| Actual failure | 0 | 183 |
| Actual success | 7 | 82 |


## Top Features

### baseline_random_split / LogisticRegression

| Feature | Weight/importances |
| --- | ---: |
| `material_id=h2_r1p984848` | -2.34194 |
| `elements=Ni O` | -2.30588 |
| `material_id=o_on_ni111` | -2.30588 |
| `material_id=bulk_si` | -2.26174 |
| `material_id=h2_r2p000000` | -2.22272 |
| `material_id=bulk_cu` | -2.16847 |
| `material_id=h2_generated` | 2.14127 |
| `material_id=ch4` | -1.92389 |
| `elements=C H` | -1.47284 |
| `elements=H` | -1.34815 |
| `material_id=bulk_si_generated` | 1.22886 |
| `element_fraction_H` | -1.16111 |
| `k2` | -1.14384 |
| `material_id=bulk_cu_generated` | 1.11263 |
| `elements=Cu` | -1.05585 |

### baseline_random_split / RandomForestClassifier

| Feature | Weight/importances |
| --- | ---: |
| `ecutwfc` | 0.0857056 |
| `ecutrho` | 0.0761591 |
| `electronegativity_mean` | 0.05056 |
| `atomic_number_max` | 0.0336696 |
| `atomic_number_std` | 0.0319764 |
| `atomic_mass_mean` | 0.0315745 |
| `atomic_radius_mean` | 0.0307275 |
| `atomic_mass_std` | 0.0305253 |
| `mixing_beta` | 0.0292599 |
| `k1` | 0.0287152 |
| `kpoint_product` | 0.0281469 |
| `atomic_number_mean` | 0.021482 |
| `material_id=bulk_cu` | 0.0194549 |
| `atomic_radius_std` | 0.0193415 |
| `k2` | 0.0191706 |

### no_material_id_random_split / LogisticRegression

| Feature | Weight/importances |
| --- | ---: |
| `elements=Ni O` | -3.98295 |
| `elements=C H` | -2.3398 |
| `elements=H` | -1.58376 |
| `element_count_Ti` | 1.43962 |
| `elements=Fe Li O P` | -1.42974 |
| `element_count_Ni` | -1.32252 |
| `elements=Cu` | -1.31481 |
| `elements=C Ni O` | 1.27679 |
| `element_fraction_H` | -1.26973 |
| `elements=C` | 1.21063 |
| `elements=H O` | 1.20088 |
| `pseudo_family=PSLibrary` | -1.08743 |
| `elements=Li O Ti` | 1.04142 |
| `elements=Fe` | 0.961381 |
| `element_count_H` | -0.955691 |

### no_material_id_random_split / RandomForestClassifier

| Feature | Weight/importances |
| --- | ---: |
| `ecutwfc` | 0.104202 |
| `ecutrho` | 0.0934673 |
| `electronegativity_mean` | 0.0592833 |
| `mixing_beta` | 0.0543077 |
| `atomic_mass_mean` | 0.0369919 |
| `atomic_number_max` | 0.0359374 |
| `atomic_number_mean` | 0.0304845 |
| `atomic_radius_mean` | 0.0299389 |
| `atomic_mass_std` | 0.02962 |
| `k1` | 0.028296 |
| `atomic_number_std` | 0.0275011 |
| `atomic_radius_std` | 0.0274591 |
| `kpoint_product` | 0.026404 |
| `elements=C O Pt` | 0.0263509 |
| `smearing=mv` | 0.0241547 |

### material_group_split / LogisticRegression

| Feature | Weight/importances |
| --- | ---: |
| `material_id=h2_generated` | 2.74271 |
| `material_id=h2_r1p984848` | -2.11302 |
| `material_id=h2_r2p000000` | -2.11302 |
| `material_id=bulk_cu` | -2.05546 |
| `material_id=bulk_si` | -1.90068 |
| `material_id=bulk_si_generated` | 1.69056 |
| `material_id=bulk_cu_generated` | 1.4493 |
| `elements=C H` | -1.16786 |
| `material_id=ch4` | -1.16786 |
| `element_count_H` | -1.10726 |
| `has_hydrogen` | -1.10726 |
| `element_count_Co` | -1.03381 |
| `k2` | -0.996299 |
| `element_fraction_H` | -0.913038 |
| `element_count_Ti` | 0.861715 |

### material_group_split / RandomForestClassifier

| Feature | Weight/importances |
| --- | ---: |
| `ecutrho` | 0.0605586 |
| `electronegativity_mean` | 0.0565757 |
| `ecutwfc` | 0.0460717 |
| `atomic_mass_mean` | 0.0409294 |
| `atomic_number_max` | 0.0406314 |
| `material_id=h2_generated` | 0.0383552 |
| `atomic_number_mean` | 0.0337124 |
| `kpoint_product` | 0.0319857 |
| `atomic_number_std` | 0.0315907 |
| `atomic_mass_std` | 0.0310971 |
| `k2` | 0.0283065 |
| `atomic_radius_mean` | 0.0268979 |
| `k1` | 0.0261159 |
| `material_id=bulk_si_generated` | 0.0240039 |
| `material_id=bulk_cu` | 0.023721 |

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
