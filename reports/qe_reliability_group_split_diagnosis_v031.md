# QE Reliability Group-Split Diagnosis v0.3.1

## Purpose

This report diagnoses why the material-group split in v0.3 failed to detect held-out failures. It does not run QE/DFT, change parser logic, delete records, or relabel failures.

## Files

- Input records: `data/parsed_records/qe_reliability_records.csv`
- Per-row predictions: `data/qe_reliability_group_split_predictions_v031.csv`

## Failure Taxonomy

- `success`: original success rows
- `setup_error`: original `qe_error` rows
- `scf_not_converged`: original `scf_not_converged` rows
- `runtime_incomplete`: original `job_not_completed` rows
- `invalid_geometry`: reserved for invalid geometry quarantine rows
- `unknown_failure`: any unmapped non-success failure label

## Held-Out Material Groups

| material_id | total | taxonomy distribution |
| --- | ---: | --- |
| `aln_2d` | 4 | success=4 |
| `bulk_au` | 6 | success=6 |
| `bulk_cspbi3` | 4 | success=4 |
| `bulk_fe` | 26 | success=26 |
| `bulk_li2nav2po43` | 3 | success=3 |
| `bulk_ni` | 6 | success=6 |
| `ch4_generated` | 6 | success=6 |
| `co_on_pt111` | 128 | setup_error=120, success=8 |
| `h2_r0p620000` | 1 | success=1 |
| `hbn` | 6 | success=6 |
| `n2` | 6 | success=6 |
| `o_on_ni111` | 70 | scf_not_converged=3, setup_error=60, success=7 |
| `silicene` | 6 | success=6 |

## Training Material Groups

| material_id | total | taxonomy distribution |
| --- | ---: | --- |
| `bulk_ag` | 6 | success=6 |
| `bulk_al` | 14 | runtime_incomplete=2, success=12 |
| `bulk_al2o3` | 6 | success=6 |
| `bulk_alas` | 6 | success=6 |
| `bulk_batio3` | 4 | success=4 |
| `bulk_cao` | 4 | success=4 |
| `bulk_co2feal` | 4 | success=4 |
| `bulk_cu` | 36 | runtime_incomplete=30, success=6 |
| `bulk_cu_generated` | 26 | success=26 |
| `bulk_gaas` | 6 | success=6 |
| `bulk_ge` | 4 | success=4 |
| `bulk_inp` | 4 | success=4 |
| `bulk_licoo2_generated` | 47 | runtime_incomplete=1, scf_not_converged=22, success=24 |
| `bulk_lifepo4` | 28 | runtime_incomplete=4, scf_not_converged=11, success=13 |
| `bulk_limn2o4` | 5 | runtime_incomplete=1, success=4 |
| `bulk_limnpo4` | 4 | success=4 |
| `bulk_litio2` | 12 | success=12 |
| `bulk_mgo_generated` | 24 | success=24 |
| `bulk_mo` | 6 | success=6 |
| `bulk_nacoo2` | 41 | runtime_incomplete=6, scf_not_converged=18, success=17 |
| `bulk_nial` | 6 | success=6 |
| `bulk_si` | 21 | runtime_incomplete=15, success=6 |
| `bulk_si_generated` | 24 | success=24 |
| `bulk_sic` | 5 | success=5 |
| `bulk_sio2` | 9 | runtime_incomplete=1, success=8 |
| `bulk_srtio3` | 6 | success=6 |
| `bulk_tio2` | 6 | success=6 |
| `bulk_w` | 6 | success=6 |
| `bulk_zno` | 8 | success=8 |
| `ch4` | 21 | runtime_incomplete=15, success=6 |
| `co` | 6 | success=6 |
| `co_on_cu111` | 14 | success=14 |
| `co_on_ni111` | 17 | success=17 |
| `graphene_generated` | 6 | success=6 |
| `h2_generated` | 21 | success=21 |
| `h2_r0p774544` | 3 | runtime_incomplete=3 |
| `h2_r0p900000` | 1 | success=1 |
| `h2_r1p300000` | 1 | success=1 |
| `h2_r1p984848` | 37 | runtime_incomplete=37 |
| `h2_r2p000000` | 37 | runtime_incomplete=37 |
| `h2o` | 11 | success=11 |
| `h2o_generated` | 11 | success=11 |
| `h_atom` | 1 | success=1 |
| `h_on_cu111` | 14 | success=14 |
| `h_on_ni111` | 9 | runtime_incomplete=1, success=8 |
| `h_on_pt111` | 14 | success=14 |
| `mos2` | 76 | success=76 |
| `nh3` | 6 | success=6 |
| `o_on_cu111` | 14 | success=14 |
| `ws2` | 6 | success=6 |

## Failure-Risk Threshold Sweep

| Failure-risk threshold | Failure recall | Failure precision | F1 | Confusion [[TN, FP], [FN, TP]] |
| ---: | ---: | ---: | ---: | --- |
| 0.05 | 0.328 | 0.526 | 0.404 | [[35, 54], [123, 60]] |
| 0.10 | 0.328 | 0.526 | 0.404 | [[35, 54], [123, 60]] |
| 0.15 | 0.000 | 0.000 | 0.000 | [[67, 22], [183, 0]] |
| 0.20 | 0.000 | 0.000 | 0.000 | [[73, 16], [183, 0]] |
| 0.25 | 0.000 | 0.000 | 0.000 | [[73, 16], [183, 0]] |
| 0.30 | 0.000 | 0.000 | 0.000 | [[76, 13], [183, 0]] |
| 0.40 | 0.000 | 0.000 | 0.000 | [[76, 13], [183, 0]] |
| 0.50 | 0.000 | 0.000 | 0.000 | [[82, 7], [183, 0]] |

## Diagnosis

- True-failure median failure risk: 0.038.
- Diagnosis: feature/data problem: true failures receive near-zero risk.
