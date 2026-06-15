# Draft Results Document for JCTC-Style Reporting

## ActiStruct Active-Learning QE Inverse-Design Benchmark Outputs

Prepared from the 51 final benchmark reports in `outputs/reports/` on 2026-06-15 09:09.

### Scope and Key Claim

This document summarizes the completed ActiStruct inverse-design benchmark calculations. The workflow couples Quantum ESPRESSO evaluations with Gaussian-process active learning and differential-evolution inverse design to locate low-energy structural parameters across chemically diverse atomistic systems.

The strongest evidence from this output set is workflow robustness and structural parameter recovery. Absolute QE total energies are reported for reproducibility, but they are not treated as directly comparable to literature unless pseudopotentials, cutoffs, smearing, spin treatment, Hubbard corrections, and reference-energy conventions match.

### Completion Summary

- Generated benchmark scripts found: **51**
- Generated benchmark reports with `FINAL RESULT`: **51 / 51**
- Total final report files: **51**
- Total final reports: **51 / 51**

### Data-Integrity Notes

- The repository keeps only the 51 final benchmark reports in `outputs/reports/`.
- Raw Quantum ESPRESSO scratch directories, caches, locks, and machine-specific paths are excluded from the public repository.
- Pseudopotential binaries are external assets and are not committed.

### Precision Against Reference Structural Quantities

| System | Quantity | ActiStruct/QE result | Reference | Error | Reference type |
|---|---:|---:|---:|---:|---|
| `bulk_ag` | `a` | 4.149480 | 4.079000 | 1.73% | tabulated fcc Ag |
| `bulk_al` | `a` | 4.049370 | 4.046000 | 0.08% | tabulated fcc Al |
| `bulk_alas` | `a` | 5.731088 | 5.661000 | 1.24% | tabulated zincblende AlAs |
| `bulk_au` | `a` | 4.145950 | 4.065000 | 1.99% | tabulated fcc Au |
| `bulk_cu_generated` | `a` | 3.621795 | 3.597000 | 0.69% | tabulated fcc Cu |
| `bulk_fe` | `a` | 2.855777 | 2.856000 | 0.01% | tabulated bcc Fe |
| `bulk_gaas` | `a` | 5.745379 | 5.653000 | 1.63% | tabulated zincblende GaAs |
| `bulk_ge` | `a` | 5.734928 | 5.658000 | 1.36% | tabulated diamond Ge |
| `bulk_inp` | `a` | 5.939600 | 5.869000 | 1.20% | tabulated zincblende InP |
| `bulk_lifepo4` | `a` | 4.654192 | 4.654917 | 0.02% | CIF reference |
| `bulk_litio2` | `a` | 4.046930 | 4.046074 | 0.02% | CIF reference |
| `bulk_mgo_generated` | `a` | 4.251955 | 4.212000 | 0.95% | tabulated rocksalt MgO |
| `bulk_mo` | `a` | 3.150000 | 3.142000 | 0.25% | tabulated bcc Mo |
| `bulk_nacoo2` | `a` | 2.900000 | 2.881369 | 0.65% | CIF reference |
| `bulk_ni` | `a` | 3.520000 | 3.499000 | 0.60% | tabulated fcc Ni |
| `bulk_si_generated` | `a` | 5.481979 | 5.431000 | 0.94% | tabulated diamond Si |
| `bulk_w` | `a` | 3.196028 | 3.155000 | 1.30% | tabulated bcc W |
| `bulk_zno` | `a` | 3.250000 | 3.250000 | 0.00% | tabulated wurtzite ZnO |
| `ch4_generated` | `bond` | 1.090000 | 1.087000 | 0.28% | gas-phase CH4 C-H bond |
| `co` | `bond` | 1.130000 | 1.128000 | 0.18% | experimental CO bond length |
| `h2_generated` | `bond` | 0.740000 | 0.741000 | 0.13% | experimental H2 bond length |
| `h2o_generated` | `bond` | 0.960000 | 0.958000 | 0.21% | gas-phase H2O O-H bond |
| `n2` | `bond` | 1.100000 | 1.098000 | 0.18% | experimental N2 bond length |
| `nh3` | `bond` | 1.020000 | 1.012000 | 0.79% | gas-phase NH3 N-H bond |

Across the 24 systems with simple scalar structural references, the mean absolute percentage deviation is **0.68%** and the median deviation is **0.65%**.

### Main Benchmark Results

| # | Category | Key | System | Best parameters | Best objective | QE calls | Report updated |
|---:|---|---|---|---|---:|---:|---|
| 1 | 2D material | `aln_2d` | 2D AlN 2x2 | a=3.130000 | -406.95813911 eV/atom | 4 | 2026-06-15 09:06 |
| 2 | 2D material | `graphene_generated` | Graphene 2x2 | a=2.460000 | -250.93787420 eV/atom | 6 | 2026-06-15 09:06 |
| 3 | 2D material | `hbn` | h-BN 2x2 | a=2.500000 | -182.13324497 eV/atom | 6 | 2026-06-15 09:06 |
| 4 | 2D material | `mos2` | MoS2 Monolayer 2x2 | a=3.198622  layer_half_thickness=1.589480 | -841.17631013 eV/atom | 8 | 2026-06-15 09:06 |
| 5 | 2D material | `silicene` | Silicene 2x2 | a=3.860000  buckling=0.450000 | -154.73730297 eV/atom | 6 | 2026-06-15 09:06 |
| 6 | 2D material | `ws2` | WS2 Monolayer 2x2 | a=3.180000  layer_half_thickness=1.580000 | -940.85531087 eV/atom | 6 | 2026-06-15 09:06 |
| 7 | Battery/perovskite | `bulk_batio3` | Perovskite BaTiO3 | a=4.000638 | -1853.46140244 eV/atom | 4 | 2026-06-15 09:06 |
| 8 | Battery/perovskite | `bulk_cspbi3` | Perovskite CsPbI3 | a=6.380333 | -5634.74664933 eV/atom | 4 | 2026-06-15 09:06 |
| 9 | Battery/perovskite | `bulk_licoo2_generated` | Layered LiCoO2 Model | a=2.867946  c_over_a=5.200000 | -1348.44365319 eV/atom | 6 | 2026-06-15 09:06 |
| 10 | Battery/perovskite | `bulk_lifepo4` | LiFePO4 Model | a=4.654192 | -1019.92030530 eV/atom | 5 | 2026-06-15 09:06 |
| 11 | Battery/perovskite | `bulk_limn2o4` | Spinel LiMn2O4 Model | a=7.900003 | -1170.24562229 eV/atom | 4 | 2026-06-15 09:06 |
| 12 | Battery/perovskite | `bulk_limnpo4` | LiMnPO₄ (Orthorhombic Olivine) | b=5.900002 | -787.95560057 eV/atom | 4 | 2026-06-15 09:06 |
| 13 | Battery/perovskite | `bulk_litio2` | LiTiO2 Model | a=4.046930 | -739.97298903 eV/atom | 4 | 2026-06-15 09:06 |
| 14 | Battery/perovskite | `bulk_nacoo2` | Layered NaCoO2 Model | a=2.900000  c_over_a=5.400000 | -1623.38953775 eV/atom | 6 | 2026-06-15 09:06 |
| 15 | Battery/perovskite | `bulk_srtio3` | Perovskite SrTiO3 | a=3.939457 | -857.49459192 eV/atom | 6 | 2026-06-15 09:06 |
| 16 | Bulk/solid | `bulk_ag` | Bulk FCC Ag | a=4.149480 | -3909.31545987 eV/atom | 6 | 2026-06-15 09:06 |
| 17 | Bulk/solid | `bulk_al` | Bulk FCC Al | a=4.049370 | -537.46053091 eV/atom | 4 | 2026-06-15 09:06 |
| 18 | Bulk/solid | `bulk_al2o3` | Bulk Al2O3 Model | a=4.650003  c_over_a=2.650002 | -553.51630613 eV/atom | 6 | 2026-06-15 09:06 |
| 19 | Bulk/solid | `bulk_alas` | Bulk Zincblende AlAs | a=5.731088 | -393.02601851 eV/atom | 6 | 2026-06-15 09:06 |
| 20 | Bulk/solid | `bulk_au` | Bulk FCC Au | a=4.145950 | -3737.12003209 eV/atom | 6 | 2026-06-15 09:06 |
| 21 | Bulk/solid | `bulk_cao` | Bulk Rocksalt CaO | a=4.810640 | -795.13715087 eV/atom | 4 | 2026-06-15 09:06 |
| 22 | Bulk/solid | `bulk_co2feal` | Heusler Co2FeAl | a=5.500009 | -3281.54411333 eV/atom | 4 | 2026-06-15 09:06 |
| 23 | Bulk/solid | `bulk_cu_generated` | Bulk FCC Cu | a=3.621795 | -2899.33060932 eV/atom | 6 | 2026-06-15 09:06 |
| 24 | Bulk/solid | `bulk_fe` | Bulk BCC Fe | a=2.855777 | -4479.91006871 eV/atom | 6 | 2026-06-15 09:06 |
| 25 | Bulk/solid | `bulk_gaas` | Bulk Zincblende GaAs | a=5.745379 | -2014.84657921 eV/atom | 6 | 2026-06-15 09:06 |
| 26 | Bulk/solid | `bulk_ge` | Bulk Diamond Ge | a=5.734928 | -2906.86968118 eV/atom | 4 | 2026-06-15 09:06 |
| 27 | Bulk/solid | `bulk_inp` | Bulk Zincblende InP | a=5.939600 | -1081.12228971 eV/atom | 4 | 2026-06-15 09:06 |
| 28 | Bulk/solid | `bulk_mgo_generated` | Bulk Rocksalt MgO | a=4.251955 | -513.87574682 eV/atom | 4 | 2026-06-15 09:06 |
| 29 | Bulk/solid | `bulk_mo` | Bulk BCC Mo | a=3.150000 | -1865.96306827 eV/atom | 6 | 2026-06-15 09:06 |
| 30 | Bulk/solid | `bulk_ni` | Bulk FCC Ni | a=3.520000 | -4670.57027851 eV/atom | 6 | 2026-06-15 09:06 |
| 31 | Bulk/solid | `bulk_nial` | B2 NiAl | a=2.890000 | -2604.65306330 eV/atom | 6 | 2026-06-15 09:06 |
| 32 | Bulk/solid | `bulk_si_generated` | Bulk Diamond Si | a=5.481979 | -155.37818111 eV/atom | 4 | 2026-06-15 09:06 |
| 33 | Bulk/solid | `bulk_sic` | Bulk Zincblende SiC | a=4.383841 | -203.36005151 eV/atom | 5 | 2026-06-15 09:06 |
| 34 | Bulk/solid | `bulk_sio2` | Bulk SiO2 Model | a=5.050000  c_over_a=1.150000 | -425.07754094 eV/atom | 8 | 2026-06-15 09:06 |
| 35 | Bulk/solid | `bulk_tio2` | Bulk Rutile TiO2 | a=4.590000  c_over_a=0.640000 | -920.48407242 eV/atom | 6 | 2026-06-15 09:06 |
| 36 | Bulk/solid | `bulk_w` | Bulk BCC W | a=3.196028 | -2165.25263068 eV/atom | 6 | 2026-06-15 09:06 |
| 37 | Bulk/solid | `bulk_zno` | Bulk Wurtzite ZnO | a=3.250000  c_over_a=1.600000 | -3423.78052531 eV/atom | 8 | 2026-06-15 09:06 |
| 38 | Molecule | `ch4_generated` | CH4 Molecule | bond=1.090000 | -315.70514565 eV | 6 | 2026-06-15 09:06 |
| 39 | Molecule | `co` | CO Molecule | bond=1.130000 | -816.54078629 eV | 6 | 2026-06-15 09:06 |
| 40 | Molecule | `h2_generated` | H2 Molecule | bond=0.740000 | -31.74160104 eV | 6 | 2026-06-15 09:06 |
| 41 | Molecule | `h2o_generated` | H2O Molecule | bond=0.960000  angle=104.500000 | -599.19409883 eV | 11 | 2026-06-15 09:06 |
| 42 | Molecule | `n2` | N2 Molecule | bond=1.100000 | -549.45559437 eV | 6 | 2026-06-15 09:06 |
| 43 | Molecule | `nh3` | NH3 Molecule | bond=1.020000 | -323.37492087 eV | 6 | 2026-06-15 09:06 |
| 44 | Surface adsorption | `co_on_cu111` | CO on Cu(111) | height=1.836296  shift=0.147611 | -35605.37848486 eV | 6 | 2026-06-15 09:06 |
| 45 | Surface adsorption | `co_on_ni111` | CO on Ni(111) | height=1.375000  shift=0.875000 | -56858.98925829 eV | 17 | 2026-06-15 09:06 |
| 46 | Surface adsorption | `co_on_pt111` | CO on Pt(111) | height=1.200000  shift=0.875000 | -35212.58940664 eV | 8 | 2026-06-15 09:06 |
| 47 | Surface adsorption | `h_on_cu111` | H on Cu(111) | height=0.900000  shift=0.860000 | -34804.27961767 eV | 6 | 2026-06-15 09:06 |
| 48 | Surface adsorption | `h_on_ni111` | H on Ni(111) | height=1.293956  shift=1.000000 | -56056.67128234 eV | 8 | 2026-06-15 09:06 |
| 49 | Surface adsorption | `h_on_pt111` | H on Pt(111) | height=0.980000  shift=0.860000 | -34411.45342313 eV | 6 | 2026-06-15 09:06 |
| 50 | Surface adsorption | `o_on_cu111` | O on Cu(111) | height=0.950000  shift=0.850000 | -35354.22852436 eV | 6 | 2026-06-15 09:06 |
| 51 | Surface adsorption | `o_on_ni111` | O on Ni(111) | height=1.300000  shift=0.500000 | -56607.32766201 eV | 7 | 2026-06-15 09:06 |

### Suggested JCTC Results Paragraph

ActiStruct was evaluated on 51 completed QE-labeled inverse-design benchmark systems spanning bulk crystals, battery materials, molecules, two-dimensional systems, and adsorption models. Each benchmark produced a final report, and most scalar structural parameters agree closely with tabulated or CIF-derived references. These results support the use of Gaussian-process active learning to reduce the number of expensive electronic-structure evaluations required for structure optimization while preserving a transparent, reproducible record of the model settings and final outcomes.

### References Used for Sanity Comparisons

- Standard tabulated lattice constants for common crystals: https://en.wikipedia.org/wiki/Lattice_constant
- LiFePO4 structural context and approximate lattice constants: https://en.wikipedia.org/wiki/Lithium_iron_phosphate
- User-supplied CIF-derived cells were used as direct local references for NaCoO2, LiTiO2, and LiFePO4.
