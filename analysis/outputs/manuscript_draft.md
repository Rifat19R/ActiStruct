# Active Learning Inverse Design Benchmark for Quantum ESPRESSO Total-Energy Optimization

## Abstract

We present an automated active-learning workflow for total-energy optimization across a 51-workflow benchmark spanning simple metals, semiconductors, ionic oxides, two-dimensional materials, molecules, battery-relevant crystals, surface structure-search geometries, and intermetallics. The workflow couples ASE structure generation, Quantum ESPRESSO single-point calculations with SSSP 1.3.0 PBE efficiency pseudopotentials, Gaussian-process surrogate modeling, and lower-confidence-bound acquisition optimized with differential evolution. Parsed reports are available for 51 of 51 workflows. Across the current report set, all systems reached the implemented convergence criterion, requiring 6.3 QE evaluations on average. The primary optimized structural parameter has an overall mean absolute deviation of 6.36% from the PBE literature references, with substantially lower errors for the conventional bulk and molecular subsets and larger deviations for prototype battery and surface-height models. The present draft is therefore positioned as a reproducible workflow and data-efficiency benchmark, with the prototype categories identified as requiring careful reference conventions before manuscript-level quantitative claims.

## 1. Introduction

Efficient exploration of atomistic structure spaces remains a central problem in computational materials chemistry. Standard grid scans are reliable but quickly become expensive when the search space contains more than one structural degree of freedom. Gaussian-process Bayesian optimization provides a natural alternative: a probabilistic surrogate is trained on a small number of first-principles calculations, uncertainty is propagated to the acquisition function, and the next calculation is selected where improvement is most likely.

This work benchmarks a compact active-learning and inverse-design loop for Quantum ESPRESSO calculations. The goal is not to introduce a new electronic-structure method, but to quantify how far a lightweight, reproducible Python workflow can reduce the number of DFT calls needed to locate low-energy structural parameters across a chemically diverse set of systems. The study is motivated by prior Bayesian optimization and surrogate-driven materials studies, including BOSS-style atomistic optimization, Gaussian-process Bayesian optimization, and reproducibility benchmarks for DFT workflows.

## 2. Computational Methods

### 2.1 DFT Setup

All calculations are configured through ASE and Quantum ESPRESSO. The project uses the SSSP 1.3.0 PBE efficiency pseudopotential library. The generated wrappers define the structure builder, pseudopotentials, kinetic-energy cutoffs, charge-density cutoffs, k-point meshes, smearing choice, and the optimized structural variables. Energies are cached by system and parameter tuple so repeated analysis reuses previously completed QE points.

### 2.2 Active-Learning Loop

The shared engine constructs an `Atoms` object, attaches an ASE `Espresso` calculator, evaluates the QE single-point energy, trains a Gaussian-process surrogate using an RBF kernel, and proposes the next geometry by minimizing a lower-confidence-bound acquisition function. The acquisition search uses scipy differential evolution rather than exhaustive enumeration, which avoids exponential grid growth for the 2D systems.

### 2.3 Objective Definition

The cleaned benchmark uses total-energy or total-energy-per-atom objectives only. Binding, cohesive, formation, and adsorption reference-energy subtractions were intentionally removed from this analysis pass because they require additional reference calculations, consistent spin handling, and category-specific thermodynamic conventions. Structural comparisons remain meaningful because the optimized variables are lattice constants, bond lengths, layer parameters, or adsorption heights.

## 3. Benchmark Set

The benchmark contains 51 target workflows grouped into metals, semiconductors, ionic oxides, two-dimensional materials, molecules, battery materials, surface structure-search geometries, and intermetallics. The material list and literature references are encoded in `analysis/publication_data.py`, and the raw extracted values are written to `analysis/outputs/raw/all_results.csv`.

- FCC metals: N=5, MAE vs PBE=0.28%, mean QE calls=5.6, converged=100%.
- BCC metals: N=3, MAE vs PBE=0.58%, mean QE calls=6.0, converged=100%.
- Semiconductors: N=6, MAE vs PBE=0.24%, mean QE calls=4.8, converged=100%.
- Ionic oxides: N=6, MAE vs PBE=1.07%, mean QE calls=6.0, converged=100%.
- 2D materials: N=6, MAE vs PBE=0.28%, mean QE calls=6.0, converged=100%.
- Molecules: N=6, MAE vs PBE=0.80%, mean QE calls=6.8, converged=100%.
- Battery materials: N=8, MAE vs PBE=6.15%, mean QE calls=5.4, converged=100%.
- Surface adsorption: N=8, MAE vs PBE=30.91%, mean QE calls=9.0, converged=100%.
- Heusler/intermetallic: N=2, MAE vs PBE=2.09%, mean QE calls=5.0, converged=100%.

## 4. Results and Discussion

### 4.1 Workflow and Convergence

Figure 1 summarizes the closed-loop workflow from structure construction to QE evaluation, GP fitting, acquisition optimization, and convergence. Figure 2 shows representative convergence histories parsed directly from the run reports. The full benchmark converged according to the implemented criterion for 100% of systems. The average number of successful QE evaluations was 6.3, with category means ranging from 4.8 to 9.0.

### 4.2 Structural Accuracy

Figure 3 compares the optimized primary structural parameter against the PBE literature values listed in the benchmark specification. The overall mean absolute deviation is 6.36% for the primary parameter. For one-dimensional systems the mean deviation is 6.84%, while the currently parsed two-dimensional subset gives 2.08%. Conventional FCC metals, BCC metals, semiconductors, 2D materials, molecules, and most simple oxides remain near the expected PBE ranges. The largest deviations are concentrated in prototype battery structures and surface-height-only models. Systems exceeding 3% primary-parameter error include: bulk_al2o3, bulk_licoo2, bulk_nacoo2, bulk_limn2o4, bulk_litio2, h_on_cu111, o_on_cu111, co_on_cu111, h_on_ni111, o_on_ni111, co_on_ni111, h_on_pt111, co_on_pt111, bulk_co2feal.

### 4.3 Data Efficiency

Figure 4 compares the active-learning call counts with an exhaustive post-hoc grid baseline of 20 points for 1D systems and 49 points for 2D systems. The mean call saving over the benchmark is 70.8%. This figure should be interpreted as a computational-cost comparison for the implemented search ranges. Direct QE/PBE grid validations are handled by `analysis/direct_grid_validation.py`, which reuses the production wrappers and writes `analysis/outputs/raw/direct_grid_validations.csv`.

### 4.4 Category-Level Error Patterns

Figure 5 summarizes errors by category. The high surface-adsorption errors arise because the current simplified models optimize adsorption height using total energy without reporting true adsorption energies or fully relaxed site-specific geometries. The battery-material deviations are dominated by prototype cells that do not yet reproduce the full crystallographic degrees of freedom of the cited structures. These limitations do not invalidate the pipeline demonstration, but they should be addressed before claiming quantitative structural benchmarking for those categories.

### 4.5 Direct QE/PBE Grid Validation Status

Direct grid validations compare active-learning minima with uniform QE/PBE grid minima using 20 points for 1D systems and 49 points for 2D systems. Four validations are completed and pass the 1 meV/atom criterion: Cu FCC, MoS2 monolayer, rocksalt MgO, and diamond Si. The completed deltas are 0.000198 eV/atom for Cu, 0.000916 eV/atom for MoS2, 0.000157 eV/atom for MgO, and 0.000233 eV/atom for Si. The spin-polarized Fe grid is also complete, but it is not compared against the existing non-spin AL report because the spin treatment differs. Production-matched LiCoO2, O/Ni(111), and CO/Pt(111) grids are configured in the same runner for longer QE jobs. O/Ni(111) and CO/Pt(111) require compatible active-learning reference reports before a pass/fail comparison is meaningful, because their older report minima are outside the current production wrapper bounds.

## 5. Conclusions

The generated analysis package converts the existing run reports into CSV files, publication-style figures, LaTeX tables, SI figures, and preflight checks. The active-learning workflow consistently converges with a small number of QE calls for the current 51-workflow set. The cleaned structure-search QE objective is robust and suitable for testing the software pipeline. Manuscript preparation should verify each structural reference against primary papers or curated databases, document QE and SSSP versions, and avoid quantitative referenced-surface-energy claims unless explicit reference energies are computed.

## 6. Current Preflight Status

The current preflight check reports two blockers:

1. The 24-reference scalar subset is useful for sanity checking, but the full 51-workflow set should not be described as fully literature-validated without additional reference curation.
2. `pdflatex` is not available in the current environment, so LaTeX table compilation could not be tested.

All required CSV files, the six main figures, the three LaTeX table files, the SI figures, `CITATION.cff`, `requirements.txt`, and `environment.yml` are present.

## Associated Content

Supporting Information figures are generated in `analysis/outputs/si_figures/`. Reproducibility scripts are in `analysis/`.

## Data and Code Availability

The codebase contains `CITATION.cff`, `requirements.txt`, generated wrappers, analysis scripts, and the output tables/figures used in this draft. Before submission, the repository should be made public and archived with Zenodo to obtain a DOI.

## References To Add

Todorovic2019; Shahriari2016; Snoek2012; Giannozzi2017; Lejaeghere2016; Haas2009; Serrano2004; Labat2007; Digne2004; Demuth1999; Cahangirov2009; Mak2010; Zhao2013; Tsipas2013; Wolverton1998; Meng2004; Kim2008; Benedek2011; Perez2012; Bousquet2010; Bilc2008; Brivio2015; Michaelides2003; Grabow2010; Hammer1999; Gajdos2004; Zou2012; Picozzi2002; NIST.
