# QE Reliability Dataset Summary

## Files

- Main dataset: `data/parsed_records/qe_reliability_records.csv`
- Invalid-geometry quarantine: `data/parsed_records/qe_invalid_geometry_records.csv`

## Record Counts

- Main records: **976**
- Converged records: **589**
- Non-converged, failed, or incomplete records: **387**
- Invalid-geometry quarantine records: **90**
- Total parsed local records: **1066**

## Main Failure Labels

| Value | Count |
| --- | ---: |
| `success` | 589 |
| `qe_error` | 180 |
| `job_not_completed` | 153 |
| `scf_not_converged` | 54 |

## Top Materials In Main Dataset

| Value | Count |
| --- | ---: |
| `co_on_pt111` | 128 |
| `mos2` | 76 |
| `o_on_ni111` | 70 |
| `bulk_licoo2_generated` | 47 |
| `bulk_nacoo2` | 41 |
| `h2_r1p984848` | 37 |
| `h2_r2p000000` | 37 |
| `bulk_cu` | 36 |
| `bulk_lifepo4` | 28 |
| `bulk_cu_generated` | 26 |
| `bulk_fe` | 26 |
| `bulk_mgo_generated` | 24 |
| `bulk_si_generated` | 24 |
| `bulk_si` | 21 |
| `ch4` | 21 |
| `h2_generated` | 21 |
| `co_on_ni111` | 17 |
| `bulk_al` | 14 |
| `co_on_cu111` | 14 |
| `h_on_cu111` | 14 |

## Pseudopotential Families

| Value | Count |
| --- | ---: |
| `PSLibrary` | 848 |
| `ONCV` | 94 |
| `USPP` | 28 |
| `mixed_or_unknown` | 6 |

## Element Coverage

| Value | Count |
| --- | ---: |
| `O` | 478 |
| `C` | 203 |
| `H` | 194 |
| `Pt` | 142 |
| `Ni` | 108 |
| `Cu` | 104 |
| `Li` | 99 |
| `Co` | 92 |
| `Mo` | 82 |
| `S` | 82 |
| `Si` | 65 |
| `Fe` | 58 |
| `Na` | 44 |
| `Al` | 40 |
| `P` | 39 |
| `Ti` | 28 |
| `Mg` | 24 |
| `N` | 22 |
| `As` | 12 |
| `W` | 12 |

## Smearing Settings

| Value | Count |
| --- | ---: |
| `mv` | 505 |
| `gaussian` | 471 |

## ecutwfc Values

| Value | Count |
| --- | ---: |
| `70` | 356 |
| `80` | 291 |
| `50` | 237 |
| `60` | 84 |
| `30` | 8 |

## K-Point Settings

| Value | Count |
| --- | ---: |
| `6 6 1 0 0 0` | 293 |
| `1 1 1 0 0 0` | 169 |
| `8 8 8 0 0 0` | 111 |
| `12 12 12 0 0 0` | 86 |
| `4 4 1 0 0 0` | 75 |
| `6 6 2 0 0 0` | 55 |
| `14 14 14 0 0 0` | 38 |
| `8 8 4 0 0 0` | 26 |
| `2 2 2 0 0 0` | 21 |
| `6 6 3 0 0 0` | 19 |
| `6 6 6 0 0 0` | 18 |
| `8 8 1 0 0 0` | 16 |
| `4 4 4 0 0 0` | 9 |
| `8 8 6 0 0 0` | 8 |
| `10 10 10 0 0 0` | 6 |
| `6 6 4 0 0 0` | 6 |
| `8 8 10 0 0 0` | 6 |
| `4 3 2 0 0 0` | 5 |
| `2 2 1 0 0 0` | 3 |
| `3 3 3 0 0 0` | 3 |

## Missing Metadata In Main Dataset

| Value | Count |
| --- | ---: |
| `failure_reason` | 589 |
| `max_force` | 387 |
| `pressure_kbar` | 387 |
| `wall_time` | 333 |
| `energy_ev` | 317 |
| `final_energy_ry` | 317 |
| `scf_iterations` | 315 |
| `calculation_hash` | 0 |
| `converged` | 0 |
| `ecutrho` | 0 |
| `ecutwfc` | 0 |
| `job_done` | 0 |
| `kpoints` | 0 |
| `material_id` | 0 |
| `mixing_beta` | 0 |
| `pseudo_family` | 0 |
| `pseudopotentials` | 0 |
| `qe_input_path` | 0 |
| `qe_output_path` | 0 |
| `smearing` | 0 |

## Scientific Interpretation

This dataset is strong enough for reliability parsing, descriptive statistics, failure-mode accounting, and an initial baseline classifier for calculation completion/convergence. It is not yet strong enough for a general DFT reliability claim because the records are local, scratch-heavy, and unevenly distributed across materials.

The quarantine file separates invalid structure-generation failures from electronic-structure workflow failures. Those records are useful for builder validation, but they should not be mixed into a model that is intended to learn SCF or QE reliability.

## Next Data Scaling Step

The next scalable source should be public calculation metadata, starting with a lightweight NOMAD connector. Public metadata must be mapped into ActiStruct fields without pretending that VASP/other-code records are Quantum ESPRESSO `.pwo` records.
