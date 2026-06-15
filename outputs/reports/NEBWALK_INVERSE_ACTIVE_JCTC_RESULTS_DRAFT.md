# Draft Results Document for JCTC-Style Reporting

## Active-Learning QE Inverse-Design Benchmark Outputs

Prepared from local output reports in `/mnt/d/Rifat_kh/inverse_active/outputs/reports` on 2026-06-15 01:16.

### Scope and Key Claim

This document summarizes the completed inverse-active benchmark calculations generated for the `inverse_active` workflow. The purpose is to support a JCTC-style methods/results narrative: the workflow couples a small number of Quantum ESPRESSO evaluations with Gaussian-process active learning and differential-evolution inverse design to locate low-energy structural parameters for chemically diverse systems.

The strongest evidence from the present output set is **workflow robustness and parameter recovery** across bulk solids, battery materials, molecules, two-dimensional materials, and adsorption models. Absolute QE total energies are reported for reproducibility, but they are not treated as directly comparable to literature unless the reference uses the same pseudopotentials, cutoffs, smearing, spin treatment, Hubbard corrections, and energy reference convention.

### Completion Summary

- Generated benchmark scripts found: **51**
- Generated benchmark reports with `FINAL RESULT`: **51 / 51**
- Total report files found: **59**
- Total reports with `FINAL RESULT`: **51 / 59**
- Legacy/non-final report files: **8**

### Important Data-Integrity Notes

- `bulk_licoo2_generated_qe_active_inverse.py` was corrected after the old LiCoO2 report was produced. The current LiCoO2 report is therefore marked as **stale** and should be regenerated before using it in a manuscript table.
- `bulk_nacoo2`, `bulk_litio2`, and `bulk_lifepo4` are based on CIF-derived structures supplied by the user and show close agreement with those input reference cells.
- Some legacy reports were produced by older demo scripts and do not contain the modern `FINAL RESULT` block. They are retained in the appendix but excluded from the main benchmark count.

### Precision Against Reference Structural Quantities

| System | Quantity | Nebwalk/QE result | Reference | Error | Reference type |
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
| `bulk_lifepo4` | `a` | 4.654192 | 4.654917 | 0.02% | user-supplied LiFePO4 CIF |
| `bulk_litio2` | `a` | 4.046930 | 4.046074 | 0.02% | user-supplied LiTiO2 CIF |
| `bulk_mgo_generated` | `a` | 4.251955 | 4.212000 | 0.95% | tabulated rocksalt MgO |
| `bulk_mo` | `a` | 3.150000 | 3.142000 | 0.25% | tabulated bcc Mo |
| `bulk_nacoo2` | `a` | 2.900000 | 2.881369 | 0.65% | user-supplied NaCoO2 CIF |
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

Across the 24 systems with simple scalar structural references, the mean absolute percentage deviation is **0.68%** and the median deviation is **0.65%**. These values should be interpreted as a sanity check of structural parameter recovery, not a complete thermochemical validation.

### Main Generated Benchmark Results

| # | Category | Key | System | Status | Best parameters | Best objective | QE calls | Report updated |
|---:|---|---|---|---|---|---:|---:|---|
| 1 | 2D material | `aln_2d` | 2D AlN 2x2 | complete | a=3.130000 | -406.95813911 eV/atom | 4 | 2026-06-08 06:23 |
| 2 | 2D material | `graphene_generated` | Graphene 2x2 | complete | a=2.460000 | -250.93787420 eV/atom | 6 | 2026-06-08 04:41 |
| 3 | 2D material | `hbn` | h-BN 2x2 | complete | a=2.500000 | -182.13324497 eV/atom | 6 | 2026-06-08 04:48 |
| 4 | 2D material | `mos2` | MoS2 Monolayer 2x2 | complete | a=3.198622  layer_half_thickness=1.589480 | -841.17631013 eV/atom | 8 | 2026-06-08 05:34 |
| 5 | 2D material | `silicene` | Silicene 2x2 | complete | a=3.860000  buckling=0.450000 | -154.73730297 eV/atom | 6 | 2026-06-08 04:58 |
| 6 | 2D material | `ws2` | WS2 Monolayer 2x2 | complete | a=3.180000  layer_half_thickness=1.580000 | -940.85531087 eV/atom | 6 | 2026-06-08 06:15 |
| 7 | Battery/perovskite | `bulk_batio3` | Perovskite BaTiO3 | complete | a=4.000638 | -1853.46140244 eV/atom | 4 | 2026-06-09 12:58 |
| 8 | Battery/perovskite | `bulk_cspbi3` | Perovskite CsPbI3 | complete | a=6.380333 | -5634.74664933 eV/atom | 4 | 2026-06-09 13:03 |
| 9 | Battery/perovskite | `bulk_lifepo4` | LiFePO4 Model | complete | a=4.654192 | -1019.92030530 eV/atom | 5 | 2026-06-14 23:36 |
| 10 | Battery/perovskite | `bulk_limnpo4` | LiMnPO₄ (Orthorhombic Olivine) | complete | b=5.900002 | -787.95560057 eV/atom | 4 | 2026-06-10 17:18 |
| 11 | Battery/perovskite | `bulk_litio2` | LiTiO2 Model | complete | a=4.046930 | -739.97298903 eV/atom | 4 | 2026-06-15 00:23 |
| 12 | Battery/perovskite | `bulk_srtio3` | Perovskite SrTiO3 | complete | a=3.939457 | -857.49459192 eV/atom | 6 | 2026-06-09 12:55 |
| 13 | Bulk/solid | `bulk_ag` | Bulk FCC Ag | complete | a=4.149480 | -3909.31545987 eV/atom | 6 | 2026-06-08 01:26 |
| 14 | Bulk/solid | `bulk_al` | Bulk FCC Al | complete | a=4.049370 | -537.46053091 eV/atom | 4 | 2026-06-08 00:44 |
| 15 | Bulk/solid | `bulk_al2o3` | Bulk Al2O3 Model | complete | a=4.650003  c_over_a=2.650002 | -553.51630613 eV/atom | 6 | 2026-06-08 03:58 |
| 16 | Bulk/solid | `bulk_alas` | Bulk Zincblende AlAs | complete | a=5.731088 | -393.02601851 eV/atom | 6 | 2026-06-08 02:55 |
| 17 | Bulk/solid | `bulk_au` | Bulk FCC Au | complete | a=4.145950 | -3737.12003209 eV/atom | 6 | 2026-06-08 01:37 |
| 18 | Bulk/solid | `bulk_cao` | Bulk Rocksalt CaO | complete | a=4.810640 | -795.13715087 eV/atom | 4 | 2026-06-08 03:15 |
| 19 | Bulk/solid | `bulk_co2feal` | Heusler Co2FeAl | complete | a=5.500009 | -3281.54411333 eV/atom | 4 | 2026-06-09 13:33 |
| 20 | Bulk/solid | `bulk_cu_generated` | Bulk FCC Cu | complete | a=3.621795 | -2899.33060932 eV/atom | 6 | 2026-06-08 00:54 |
| 21 | Bulk/solid | `bulk_fe` | Bulk BCC Fe | complete | a=2.855777 | -4479.91006871 eV/atom | 6 | 2026-06-08 01:56 |
| 22 | Bulk/solid | `bulk_gaas` | Bulk Zincblende GaAs | complete | a=5.745379 | -2014.84657921 eV/atom | 6 | 2026-06-08 02:46 |
| 23 | Bulk/solid | `bulk_ge` | Bulk Diamond Ge | complete | a=5.734928 | -2906.86968118 eV/atom | 4 | 2026-06-08 02:20 |
| 24 | Bulk/solid | `bulk_inp` | Bulk Zincblende InP | complete | a=5.939600 | -1081.12228971 eV/atom | 4 | 2026-06-08 03:05 |
| 25 | Bulk/solid | `bulk_mgo_generated` | Bulk Rocksalt MgO | complete | a=4.251955 | -513.87574682 eV/atom | 4 | 2026-06-08 03:10 |
| 26 | Bulk/solid | `bulk_mo` | Bulk BCC Mo | complete | a=3.150000 | -1865.96306827 eV/atom | 6 | 2026-06-08 02:04 |
| 27 | Bulk/solid | `bulk_ni` | Bulk FCC Ni | complete | a=3.520000 | -4670.57027851 eV/atom | 6 | 2026-06-08 01:16 |
| 28 | Bulk/solid | `bulk_nial` | B2 NiAl | complete | a=2.890000 | -2604.65306330 eV/atom | 6 | 2026-06-09 13:08 |
| 29 | Bulk/solid | `bulk_si_generated` | Bulk Diamond Si | complete | a=5.481979 | -155.37818111 eV/atom | 4 | 2026-06-08 02:13 |
| 30 | Bulk/solid | `bulk_sic` | Bulk Zincblende SiC | complete | a=4.383841 | -203.36005151 eV/atom | 5 | 2026-06-08 03:08 |
| 31 | Bulk/solid | `bulk_sio2` | Bulk SiO2 Model | complete | a=5.050000  c_over_a=1.150000 | -425.07754094 eV/atom | 8 | 2026-06-08 04:39 |
| 32 | Bulk/solid | `bulk_tio2` | Bulk Rutile TiO2 | complete | a=4.590000  c_over_a=0.640000 | -920.48407242 eV/atom | 6 | 2026-06-08 03:28 |
| 33 | Bulk/solid | `bulk_w` | Bulk BCC W | complete | a=3.196028 | -2165.25263068 eV/atom | 6 | 2026-06-08 02:11 |
| 34 | Bulk/solid | `bulk_zno` | Bulk Wurtzite ZnO | complete | a=3.250000  c_over_a=1.600000 | -3423.78052531 eV/atom | 8 | 2026-06-08 03:21 |
| 35 | Molecule | `bulk_licoo2_generated` | Layered LiCoO2 Model | complete (stale after script edit) | a=2.700000  c_over_a=4.600000 | -1344.77219939 eV/atom | 6 | 2026-06-08 09:06 |
| 36 | Molecule | `bulk_limn2o4` | Spinel LiMn2O4 Model | complete | a=7.900003 | -1170.24562229 eV/atom | 4 | 2026-06-10 08:15 |
| 37 | Molecule | `bulk_nacoo2` | Layered NaCoO2 Model | complete | a=2.900000  c_over_a=5.400000 | -1623.38953775 eV/atom | 6 | 2026-06-14 20:57 |
| 38 | Molecule | `ch4_generated` | CH4 Molecule | complete | bond=1.090000 | -315.70514565 eV | 6 | 2026-06-08 06:52 |
| 39 | Molecule | `co` | CO Molecule | complete | bond=1.130000 | -816.54078629 eV | 6 | 2026-06-08 06:33 |
| 40 | Molecule | `h2_generated` | H2 Molecule | complete | bond=0.740000 | -31.74160104 eV | 6 | 2026-06-08 06:23 |
| 41 | Molecule | `h2o_generated` | H2O Molecule | complete | bond=0.960000  angle=104.500000 | -599.19409883 eV | 11 | 2026-06-08 06:41 |
| 42 | Molecule | `n2` | N2 Molecule | complete | bond=1.100000 | -549.45559437 eV | 6 | 2026-06-08 06:27 |
| 43 | Molecule | `nh3` | NH3 Molecule | complete | bond=1.020000 | -323.37492087 eV | 6 | 2026-06-08 06:47 |
| 44 | Surface adsorption | `co_on_cu111` | CO on Cu(111) | complete | height=1.800000  shift=0.500000 | -35605.13445507 eV | 8 | 2026-06-08 16:24 |
| 45 | Surface adsorption | `co_on_ni111` | CO on Ni(111) | complete | height=1.375000  shift=0.875000 | -56858.98925829 eV | 17 | 2026-06-09 12:51 |
| 46 | Surface adsorption | `co_on_pt111` | CO on Pt(111) | complete | height=1.200000  shift=0.875000 | -35212.58940664 eV | 8 | 2026-06-10 15:52 |
| 47 | Surface adsorption | `h_on_cu111` | H on Cu(111) | complete | height=0.900000  shift=0.860000 | -34804.27961767 eV | 6 | 2026-06-14 18:08 |
| 48 | Surface adsorption | `h_on_ni111` | H on Ni(111) | complete | height=1.293956  shift=1.000000 | -56056.67128234 eV | 8 | 2026-06-08 18:57 |
| 49 | Surface adsorption | `h_on_pt111` | H on Pt(111) | complete | height=0.980000  shift=0.860000 | -34411.45342313 eV | 6 | 2026-06-14 18:04 |
| 50 | Surface adsorption | `o_on_cu111` | O on Cu(111) | complete | height=0.950000  shift=0.850000 | -35354.22852436 eV | 6 | 2026-06-14 18:00 |
| 51 | Surface adsorption | `o_on_ni111` | O on Ni(111) | complete | height=1.300000  shift=0.500000 | -56607.32766201 eV | 7 | 2026-06-09 04:39 |

### Interpretation for Manuscript Drafting

1. **Data efficiency.** Most completed systems required only 4-8 QE labels; the most demanding adsorption case, `co_on_ni111`, required 17 labels. This supports the central active-learning claim: the workflow can identify useful low-energy regions without exhaustive grid enumeration.
2. **Chemical breadth.** The completed set spans metals, semiconductors, oxides, cathode materials, molecules, 2D materials, and surface adsorption models. This breadth is useful for arguing generality, provided the manuscript clearly labels simplified model systems as models rather than high-fidelity production calculations.
3. **Structural fidelity.** For standard crystals and molecules where scalar references are available, the optimized parameters are usually within a few percent of known values. CIF-derived LiTiO2 and LiFePO4 agree especially closely with the supplied reference cells.
4. **Energy interpretation.** Reported energies are QE total-energy objectives under the local pseudopotential/cutoff settings. They are valid for ranking within each model search but should not be presented as literature formation energies, adsorption energies, or cohesive energies without reference-state corrections.
5. **Battery-material caution.** Transition-metal oxides such as NaCoO2, LiCoO2, LiTiO2, and LiFePO4 can be sensitive to spin state, magnetic ordering, and DFT+U. Current outputs demonstrate workflow operation and structural targeting; final publication-quality energetics should specify or validate the magnetic/electronic treatment.

### Suggested JCTC Results Paragraph

The inverse-active workflow was evaluated on a diverse collection of periodic and molecular systems using Quantum ESPRESSO as the labeling engine. All 51 generated benchmark scripts produced final reports, covering bulk metals and semiconductors, ionic and battery materials, molecules, two-dimensional materials, and surface adsorption models. Most systems converged with fewer than ten QE labels, demonstrating that the Gaussian-process active-learning loop can focus expensive electronic-structure evaluations on informative regions of the design space. For systems with well-defined scalar structural references, the recovered parameters were generally close to standard tabulated or CIF-derived values, supporting the numerical stability of the workflow. The calculations should be interpreted as model-structure optimization benchmarks; absolute total energies are not compared directly across literature sources because they depend on pseudopotentials, exchange-correlation details, smearing, spin state, and reference-energy conventions.

### Appendix A: All Report Files

| # | Report key | Final result | Best parameters | Best objective | QE calls | Updated | File |
|---:|---|---|---|---:|---:|---|---|
| 1 | `aln_2d` | yes | a=3.130000 | -406.95813911 eV/atom | 4 | 2026-06-08 06:23 | `aln_2d_report.txt` |
| 2 | `bulk_ag` | yes | a=4.149480 | -3909.31545987 eV/atom | 6 | 2026-06-08 01:26 | `bulk_ag_report.txt` |
| 3 | `bulk_al` | yes | a=4.049370 | -537.46053091 eV/atom | 4 | 2026-06-08 00:44 | `bulk_al_report.txt` |
| 4 | `bulk_al2o3` | yes | a=4.650003  c_over_a=2.650002 | -553.51630613 eV/atom | 6 | 2026-06-08 03:58 | `bulk_al2o3_report.txt` |
| 5 | `bulk_alas` | yes | a=5.731088 | -393.02601851 eV/atom | 6 | 2026-06-08 02:55 | `bulk_alas_report.txt` |
| 6 | `bulk_au` | yes | a=4.145950 | -3737.12003209 eV/atom | 6 | 2026-06-08 01:37 | `bulk_au_report.txt` |
| 7 | `bulk_batio3` | yes | a=4.000638 | -1853.46140244 eV/atom | 4 | 2026-06-09 12:58 | `bulk_batio3_report.txt` |
| 8 | `bulk_cao` | yes | a=4.810640 | -795.13715087 eV/atom | 4 | 2026-06-08 03:15 | `bulk_cao_report.txt` |
| 9 | `bulk_co2feal` | yes | a=5.500009 | -3281.54411333 eV/atom | 4 | 2026-06-09 13:33 | `bulk_co2feal_report.txt` |
| 10 | `bulk_cspbi3` | yes | a=6.380333 | -5634.74664933 eV/atom | 4 | 2026-06-09 13:03 | `bulk_cspbi3_report.txt` |
| 11 | `bulk_cu_4_qe_active_inverse` | no | - | 3.622902 A | - | 2026-06-07 22:13 | `bulk_cu_4_qe_active_inverse_report.txt` |
| 12 | `bulk_cu_generated` | yes | a=3.621795 | -2899.33060932 eV/atom | 6 | 2026-06-08 00:54 | `bulk_cu_generated_report.txt` |
| 13 | `bulk_fe` | yes | a=2.855777 | -4479.91006871 eV/atom | 6 | 2026-06-08 01:56 | `bulk_fe_report.txt` |
| 14 | `bulk_gaas` | yes | a=5.745379 | -2014.84657921 eV/atom | 6 | 2026-06-08 02:46 | `bulk_gaas_report.txt` |
| 15 | `bulk_ge` | yes | a=5.734928 | -2906.86968118 eV/atom | 4 | 2026-06-08 02:20 | `bulk_ge_report.txt` |
| 16 | `bulk_inp` | yes | a=5.939600 | -1081.12228971 eV/atom | 4 | 2026-06-08 03:05 | `bulk_inp_report.txt` |
| 17 | `bulk_licoo2_generated` | yes | a=2.700000  c_over_a=4.600000 | -1344.77219939 eV/atom | 6 | 2026-06-08 09:06 | `bulk_licoo2_generated_report.txt` |
| 18 | `bulk_lifepo4` | yes | a=4.654192 | -1019.92030530 eV/atom | 5 | 2026-06-14 23:36 | `bulk_lifepo4_report.txt` |
| 19 | `bulk_limn2o4` | yes | a=7.900003 | -1170.24562229 eV/atom | 4 | 2026-06-10 08:15 | `bulk_limn2o4_report.txt` |
| 20 | `bulk_limnpo4` | yes | b=5.900002 | -787.95560057 eV/atom | 4 | 2026-06-10 17:18 | `bulk_limnpo4_report.txt` |
| 21 | `bulk_litio2` | yes | a=4.046930 | -739.97298903 eV/atom | 4 | 2026-06-15 00:23 | `bulk_litio2_report.txt` |
| 22 | `bulk_mgo_generated` | yes | a=4.251955 | -513.87574682 eV/atom | 4 | 2026-06-08 03:10 | `bulk_mgo_generated_report.txt` |
| 23 | `bulk_mo` | yes | a=3.150000 | -1865.96306827 eV/atom | 6 | 2026-06-08 02:04 | `bulk_mo_report.txt` |
| 24 | `bulk_nacoo2` | yes | a=2.900000  c_over_a=5.400000 | -1623.38953775 eV/atom | 6 | 2026-06-14 20:57 | `bulk_nacoo2_report.txt` |
| 25 | `bulk_ni` | yes | a=3.520000 | -4670.57027851 eV/atom | 6 | 2026-06-08 01:16 | `bulk_ni_report.txt` |
| 26 | `bulk_nial` | yes | a=2.890000 | -2604.65306330 eV/atom | 6 | 2026-06-09 13:08 | `bulk_nial_report.txt` |
| 27 | `bulk_si_8_qe_active_inverse` | no | - | 5.465468 A | - | 2026-06-07 22:21 | `bulk_si_8_qe_active_inverse_report.txt` |
| 28 | `bulk_si_generated` | yes | a=5.481979 | -155.37818111 eV/atom | 4 | 2026-06-08 02:13 | `bulk_si_generated_report.txt` |
| 29 | `bulk_sic` | yes | a=4.383841 | -203.36005151 eV/atom | 5 | 2026-06-08 03:08 | `bulk_sic_report.txt` |
| 30 | `bulk_sio2` | yes | a=5.050000  c_over_a=1.150000 | -425.07754094 eV/atom | 8 | 2026-06-08 04:39 | `bulk_sio2_report.txt` |
| 31 | `bulk_srtio3` | yes | a=3.939457 | -857.49459192 eV/atom | 6 | 2026-06-09 12:55 | `bulk_srtio3_report.txt` |
| 32 | `bulk_tio2` | yes | a=4.590000  c_over_a=0.640000 | -920.48407242 eV/atom | 6 | 2026-06-08 03:28 | `bulk_tio2_report.txt` |
| 33 | `bulk_w` | yes | a=3.196028 | -2165.25263068 eV/atom | 6 | 2026-06-08 02:11 | `bulk_w_report.txt` |
| 34 | `bulk_zno` | yes | a=3.250000  c_over_a=1.600000 | -3423.78052531 eV/atom | 8 | 2026-06-08 03:21 | `bulk_zno_report.txt` |
| 35 | `ch4_generated` | yes | bond=1.090000 | -315.70514565 eV | 6 | 2026-06-08 06:52 | `ch4_generated_report.txt` |
| 36 | `ch4_qe_active_inverse` | no | - | 1.098086 A | - | 2026-06-07 21:34 | `ch4_qe_active_inverse_report.txt` |
| 37 | `co` | yes | bond=1.130000 | -816.54078629 eV | 6 | 2026-06-08 06:33 | `co_report.txt` |
| 38 | `co_on_cu111` | yes | height=1.800000  shift=0.500000 | -35605.13445507 eV | 8 | 2026-06-08 16:24 | `co_on_cu111_report.txt` |
| 39 | `co_on_ni111` | yes | height=1.375000  shift=0.875000 | -56858.98925829 eV | 17 | 2026-06-09 12:51 | `co_on_ni111_report.txt` |
| 40 | `co_on_pt111` | yes | height=1.200000  shift=0.875000 | -35212.58940664 eV | 8 | 2026-06-10 15:52 | `co_on_pt111_report.txt` |
| 41 | `cu2_run` | no | - | 2.171530 A | - | 2026-06-07 21:14 | `cu2_run_report.txt` |
| 42 | `graphene_generated` | yes | a=2.460000 | -250.93787420 eV/atom | 6 | 2026-06-08 04:41 | `graphene_generated_report.txt` |
| 43 | `h2_generated` | yes | bond=0.740000 | -31.74160104 eV | 6 | 2026-06-08 06:23 | `h2_generated_report.txt` |
| 44 | `h2_generated_qe_active_inverse` | no | bond=0.758202 | -15.87127046 eV/atom | - | 2026-06-07 22:23 | `h2_generated_qe_active_inverse_report.txt` |
| 45 | `h2_qe_active_inverse` | no | - | 0.900000 A | - | 2026-06-07 21:21 | `h2_qe_active_inverse_report.txt` |
| 46 | `h2_run` | no | - | 0.743909 A | - | 2026-06-07 21:14 | `h2_run_report.txt` |
| 47 | `h2o_generated` | yes | bond=0.960000  angle=104.500000 | -599.19409883 eV | 11 | 2026-06-08 06:41 | `h2o_generated_report.txt` |
| 48 | `h2o_qe_active_inverse` | no | - | 0.960000 A | - | 2026-06-07 21:42 | `h2o_qe_active_inverse_report.txt` |
| 49 | `h_on_cu111` | yes | height=0.900000  shift=0.860000 | -34804.27961767 eV | 6 | 2026-06-14 18:08 | `h_on_cu111_report.txt` |
| 50 | `h_on_ni111` | yes | height=1.293956  shift=1.000000 | -56056.67128234 eV | 8 | 2026-06-08 18:57 | `h_on_ni111_report.txt` |
| 51 | `h_on_pt111` | yes | height=0.980000  shift=0.860000 | -34411.45342313 eV | 6 | 2026-06-14 18:04 | `h_on_pt111_report.txt` |
| 52 | `hbn` | yes | a=2.500000 | -182.13324497 eV/atom | 6 | 2026-06-08 04:48 | `hbn_report.txt` |
| 53 | `mos2` | yes | a=3.198622  layer_half_thickness=1.589480 | -841.17631013 eV/atom | 8 | 2026-06-08 05:34 | `mos2_report.txt` |
| 54 | `n2` | yes | bond=1.100000 | -549.45559437 eV | 6 | 2026-06-08 06:27 | `n2_report.txt` |
| 55 | `nh3` | yes | bond=1.020000 | -323.37492087 eV | 6 | 2026-06-08 06:47 | `nh3_report.txt` |
| 56 | `o_on_cu111` | yes | height=0.950000  shift=0.850000 | -35354.22852436 eV | 6 | 2026-06-14 18:00 | `o_on_cu111_report.txt` |
| 57 | `o_on_ni111` | yes | height=1.300000  shift=0.500000 | -56607.32766201 eV | 7 | 2026-06-09 04:39 | `o_on_ni111_report.txt` |
| 58 | `silicene` | yes | a=3.860000  buckling=0.450000 | -154.73730297 eV/atom | 6 | 2026-06-08 04:58 | `silicene_report.txt` |
| 59 | `ws2` | yes | a=3.180000  layer_half_thickness=1.580000 | -940.85531087 eV/atom | 6 | 2026-06-08 06:15 | `ws2_report.txt` |

### References Used for Sanity Comparisons

- Standard tabulated lattice constants for common crystals: https://en.wikipedia.org/wiki/Lattice_constant
- LiFePO4 structural context and approximate lattice constants: https://en.wikipedia.org/wiki/Lithium_iron_phosphate
- Example QE/DFT+U LiFePO4 structural values: https://arxiv.org/abs/2305.11459
- User-supplied CIF-derived cells for NaCoO2, LiTiO2, and LiFePO4 were used as direct local references where applicable.
