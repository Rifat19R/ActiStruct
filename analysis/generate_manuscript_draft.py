from __future__ import annotations

import csv

from publication_data import OUTPUT_DIR, RAW_DIR, TABLE_DIR


def rows(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def first_row(path, category):
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["category"] == category:
                return row
    return {}


def f(row, key, default=0.0):
    try:
        return float(row.get(key) or default)
    except ValueError:
        return default


def category_summary(stats_rows):
    lines = []
    for row in stats_rows:
        if row["category"].startswith("Overall"):
            continue
        lines.append(
            f"- {row['category']}: N={row['n_systems']}, "
            f"MAE vs PBE={f(row, 'mean_abs_error_pbe'):.2f}%, "
            f"mean QE calls={f(row, 'mean_n_qe'):.1f}, "
            f"converged={f(row, 'pct_converged'):.0f}%."
        )
    return "\n".join(lines)


def main() -> None:
    results = rows(RAW_DIR / "all_results.csv")
    stats_rows = rows(TABLE_DIR / "statistics_summary.csv")
    grid_rows = rows(RAW_DIR / "grid_search_comparison.csv")
    overall = first_row(TABLE_DIR / "statistics_summary.csv", "Overall")
    one_d = first_row(TABLE_DIR / "statistics_summary.csv", "Overall 1D")
    two_d = first_row(TABLE_DIR / "statistics_summary.csv", "Overall 2D")
    report_count = sum(1 for row in results if row["report_file"])
    mean_saving = sum(f(row, "al_savings_pct") for row in grid_rows) / max(len(grid_rows), 1)
    mean_calls = f(overall, "mean_n_qe")
    max_error = max((f(row, "pct_error_param1") for row in results), default=0.0)
    high_error = [row for row in results if f(row, "pct_error_param1") > 3.0]
    high_error_text = ", ".join(row["key"] for row in high_error[:18])
    if len(high_error) > 18:
        high_error_text += f", and {len(high_error) - 18} others"
    text = f"""# Active Learning Inverse Design Benchmark for Quantum ESPRESSO Total-Energy Optimization

## Abstract

We present an automated active-learning workflow for total-energy optimization across a 50-system benchmark spanning simple metals, semiconductors, ionic oxides, two-dimensional materials, molecules, battery-relevant crystals, adsorbate/surface geometries, and intermetallics. The workflow couples ASE structure generation, Quantum ESPRESSO single-point calculations with SSSP 1.3.0 PBE efficiency pseudopotentials, Gaussian-process surrogate modeling, and lower-confidence-bound acquisition optimized with differential evolution. Parsed reports are available for {report_count} of 50 systems. Across the current report set, all systems reached the implemented convergence criterion, requiring {mean_calls:.1f} QE evaluations on average. The primary optimized structural parameter has an overall mean absolute deviation of {f(overall, 'mean_abs_error_pbe'):.2f}% from the PBE literature references, with substantially lower errors for the conventional bulk and molecular subsets and larger deviations for prototype battery and surface-height models. The present draft is therefore positioned as a reproducible workflow and data-efficiency benchmark, with the outlier categories identified as targets for further physical-model refinement before final journal submission.

## 1. Introduction

Efficient exploration of atomistic structure spaces remains a central problem in computational materials chemistry. Standard grid scans are reliable but quickly become expensive when the search space contains more than one structural degree of freedom. Gaussian-process Bayesian optimization provides a natural alternative: a probabilistic surrogate is trained on a small number of first-principles calculations, uncertainty is propagated to the acquisition function, and the next calculation is selected where improvement is most likely.

This work benchmarks a compact active-learning and inverse-design loop for Quantum ESPRESSO calculations. The goal is not to introduce a new electronic-structure method, but to quantify how far a lightweight, reproducible Python workflow can reduce the number of DFT calls needed to locate low-energy structural parameters across a chemically diverse set of systems. The study is motivated by prior Bayesian optimization and surrogate-driven materials studies, including BOSS-style atomistic optimization, Gaussian-process Bayesian optimization, and reproducibility benchmarks for DFT workflows.

## 2. Computational Methods

### 2.1 DFT Setup

All calculations are configured through ASE and Quantum ESPRESSO. The project uses the SSSP 1.3.0 PBE efficiency pseudopotential library. The generated wrappers define the structure builder, pseudopotentials, kinetic-energy cutoffs, charge-density cutoffs, k-point meshes, smearing choice, and the optimized structural variables. Energies are cached by system and parameter tuple so repeated analysis does not rerun previously completed QE points.

### 2.2 Active-Learning Loop

The shared engine constructs an `Atoms` object, attaches an ASE `Espresso` calculator, evaluates the QE single-point energy, trains a Gaussian-process surrogate using an RBF kernel, and proposes the next geometry by minimizing a lower-confidence-bound acquisition function. The acquisition search uses scipy differential evolution rather than exhaustive enumeration, which avoids exponential grid growth for the 2D systems.

### 2.3 Objective Definition

The cleaned benchmark uses total-energy or total-energy-per-atom objectives only. Binding, cohesive, formation, and adsorption reference-energy subtractions were intentionally removed from this analysis pass because they require additional reference calculations, consistent spin handling, and category-specific thermodynamic conventions. Structural comparisons remain meaningful because the optimized variables are lattice constants, bond lengths, layer parameters, or adsorption heights.

## 3. Benchmark Set

The benchmark contains 50 target systems grouped into metals, semiconductors, ionic oxides, two-dimensional materials, molecules, battery materials, surface adsorption geometries, and intermetallics. The material list and literature references are encoded in `analysis/publication_data.py`, and the raw extracted values are written to `analysis/outputs/raw/all_results.csv`.

{category_summary(stats_rows)}

## 4. Results and Discussion

### 4.1 Workflow and Convergence

Figure 1 summarizes the closed-loop workflow from structure construction to QE evaluation, GP fitting, acquisition optimization, and convergence. Figure 2 shows representative convergence histories parsed directly from the run reports. The full benchmark converged according to the implemented criterion for {f(overall, 'pct_converged'):.0f}% of systems. The average number of successful QE evaluations was {mean_calls:.1f}, with category means ranging from {min(f(row, 'mean_n_qe') for row in stats_rows if not row['category'].startswith('Overall')):.1f} to {max(f(row, 'mean_n_qe') for row in stats_rows if not row['category'].startswith('Overall')):.1f}.

### 4.2 Structural Accuracy

Figure 3 compares the optimized primary structural parameter against the PBE literature values listed in the benchmark specification. The overall mean absolute deviation is {f(overall, 'mean_abs_error_pbe'):.2f}% for the primary parameter. For one-dimensional systems the mean deviation is {f(one_d, 'mean_abs_error_pbe'):.2f}%, while the currently parsed two-dimensional subset gives {f(two_d, 'mean_abs_error_pbe'):.2f}%. Conventional FCC metals, BCC metals, semiconductors, 2D materials, molecules, and most simple oxides remain near the expected PBE ranges. The largest deviations are concentrated in prototype battery structures and surface-height-only models. Systems exceeding 3% primary-parameter error include: {high_error_text or 'none'}.

### 4.3 Data Efficiency

Figure 4 compares the active-learning call counts with an exhaustive post-hoc grid baseline of 20 points for 1D systems and 49 points for 2D systems. The mean call saving over the benchmark is {mean_saving:.1f}%. This figure should be interpreted as a computational-cost comparison for the implemented search ranges rather than a replacement for the three real QE grid validations. The generated validation scripts for Cu, LiCoO2, and MoS2 are located in `analysis/run_grid_cu.py`, `analysis/run_grid_licoo2.py`, and `analysis/run_grid_mos2.py`; those jobs require manual execution because they launch QE.

### 4.4 Category-Level Error Patterns

Figure 5 summarizes errors by category. The high surface-adsorption errors arise because the current simplified models optimize adsorption height using total energy without reporting true adsorption energies or fully relaxed site-specific geometries. The battery-material deviations are dominated by prototype cells that do not yet reproduce the full crystallographic degrees of freedom of the cited structures. These limitations do not invalidate the pipeline demonstration, but they should be addressed before claiming quantitative structural benchmarking for those categories.

### 4.5 Real Grid Validation Status

Figure 6 is a placeholder until the three manual QE grid validation jobs are run. After those CSV files are generated, `analysis/compare_grid_validation.py` will compare the grid minima against the active-learning minima and report whether they agree within 1 meV/atom.

## 5. Conclusions

The generated analysis package converts the existing run reports into CSV files, publication-style figures, LaTeX tables, SI figures, and preflight checks. The active-learning workflow consistently converges with a small number of QE calls for the current 50-system set. The cleaned total-energy-only objective is robust and suitable for testing the software pipeline. Final submission to JCTC will require completing the three manual QE grid-validation runs, installing a LaTeX toolchain for table compilation checks, and resolving or explicitly reframing the high-error prototype categories.

## 6. Current Preflight Status

The current preflight check reports two blockers:

1. The overall mean absolute error vs PBE literature exceeds the strict 5% threshold because of battery and surface prototype outliers.
2. `pdflatex` is not available in the current environment, so LaTeX table compilation could not be tested.

All required CSV files, the six main figures, the three LaTeX table files, the 50 SI figures, `CITATION.cff`, and `requirements.txt` are present.

## Associated Content

Supporting Information figures are generated in `analysis/outputs/si_figures/`. Reproducibility scripts are in `analysis/`.

## Data and Code Availability

The codebase contains `CITATION.cff`, `requirements.txt`, generated wrappers, analysis scripts, and the output tables/figures used in this draft. Before submission, the repository should be made public and archived with Zenodo to obtain a DOI.

## References To Add

Todorovic2019; Shahriari2016; Snoek2012; Giannozzi2017; Lejaeghere2016; Haas2009; Serrano2004; Labat2007; Digne2004; Demuth1999; Cahangirov2009; Mak2010; Zhao2013; Tsipas2013; Wolverton1998; Meng2004; Kim2008; Benedek2011; Perez2012; Bousquet2010; Bilc2008; Brivio2015; Michaelides2003; Grabow2010; Hammer1999; Gajdos2004; Zou2012; Picozzi2002; NIST.
"""
    out = OUTPUT_DIR / "manuscript_draft.md"
    out.write_text(text, encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
