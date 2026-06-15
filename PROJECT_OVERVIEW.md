# Inverse Active: Active-Learning Inverse Design for Atomistic Structures

## Executive Summary

`inverse_active` is a research codebase for active-learning inverse design of atomistic structures using Python, ASE, Gaussian-process surrogate modeling, and Quantum ESPRESSO. The central idea is simple but powerful: instead of scanning a large number of structural parameters with expensive DFT calculations, the model learns from a small number of DFT evaluations, estimates uncertainty, and chooses the next most informative structure to calculate.

The project has already been demonstrated on a 51-system benchmark spanning metals, semiconductors, ionic oxides, 2D materials, molecules, battery materials, surface adsorption systems, and intermetallics. This makes it more than a single-case demonstration. It is a general workflow for testing whether active learning can guide DFT-based structural optimization across chemically different material classes.

In its current state, the full 50-structure benchmark has been run once and analyzed. The first validation pass identified 12 structures with more than 5% mismatch against literature structural values. Those 12 input definitions were then corrected using literature-aligned structural ranges and stricter Quantum ESPRESSO settings. Three corrected reruns are confirmed in the current report directory; the remaining nine corrected reruns still need to be completed before the final updated statistics are regenerated.

## What This Project Builds

The project builds a closed-loop inverse-design engine for materials and molecular structures:

```text
structure parameters
        |
        v
ASE structure builder
        |
        v
Quantum ESPRESSO DFT evaluation
        |
        v
Gaussian-process surrogate model
        |
        v
active-learning query + inverse proposal
        |
        v
new structure to evaluate
```

Each material system is defined by a small number of physically meaningful design variables, such as a lattice constant, bond length, c/a ratio, adsorption height, or surface-site descriptor. The model then searches this design space with far fewer DFT calls than a conventional dense grid scan.

## Why It Matters

DFT calculations are accurate but expensive. A brute-force parameter scan can quickly become costly, especially when each point requires a full Quantum ESPRESSO calculation. This project demonstrates that a Gaussian-process active-learning loop can locate useful structural parameters with only a small number of DFT evaluations.

The impact is threefold:

1. It reduces computational cost by learning from sparse DFT data.
2. It provides uncertainty-aware optimization, not blind parameter scanning.
3. It is general enough to run across many classes of atomistic systems.

This is important for computational materials discovery because many promising materials problems involve expensive calculations over structural, chemical, or adsorption-coordinate spaces. `inverse_active` is a proof-of-concept toward a more autonomous DFT workflow.

## Core Technical Components

The main shared engine is:

```text
qe_active_inverse_common.py
```

It implements:

- `Variable`: a design-variable definition with lower bound, upper bound, and initial samples.
- `ActiveSystem`: the full configuration for one atomistic optimization problem.
- ASE structure construction.
- Quantum ESPRESSO execution through ASE's `Espresso` calculator.
- File-based caching to avoid repeating the same expensive QE calculation.
- Gaussian-process regression with an RBF kernel.
- Active learning based on model uncertainty.
- Inverse proposal by lower-confidence-bound optimization using differential evolution.
- Automatic plots and text reports for each system.

The current global QE settings include:

```text
N_PROCS = 2
PARALLEL_WORKERS = 2
QE_CONV_THR = 5e-9
QE_MIXING_BETA = 0.3
PSEUDO_DIR = <PSEUDO_DIR>
```

For the corrected outlier systems, the input ranges and numerical settings were tightened, including higher cutoffs such as `ecutwfc = 80 Ry`, `ecutrho = 640 Ry`, denser k-point meshes, and smaller metallic smearing where appropriate.

## Benchmark Scope

The generated benchmark contains 51 systems in the following categories:

| Category | Systems |
| --- | ---: |
| FCC metals | 5 |
| BCC metals | 3 |
| Semiconductors | 6 |
| Ionic oxides | 6 |
| 2D materials | 6 |
| Molecules | 6 |
| Battery materials | 8 |
| Surface adsorption | 8 |
| Heusler/intermetallic systems | 2 |
| **Total** | **50** |

The generated model wrappers are located in:

```text
generated_models/
```

The reusable generated structure builders are in:

```text
generated_models/structure_builders.py
```

The analysis and publication-style postprocessing scripts are in:

```text
analysis/
```

The output reports, figures, tables, and supporting-information plots are in:

```text
outputs/reports/
analysis/outputs/
```

## First 50-System Validation Pass

The first full benchmark pass produced report files for all 51 systems. The analysis scripts parsed those reports and generated summary tables and figures.

From the current analysis outputs for the initial 51-system pass:

- Reports parsed: 50/51 systems.
- Convergence rate: 100% according to the implemented convergence criterion.
- Mean number of QE calls: about 6.3 per system.
- Initial overall mean absolute error vs PBE structural references: 6.36%.
- Initial major outlier categories: surface adsorption and some battery-material prototype cells.

The strongest initial performance was observed for conventional structural problems:

- FCC metals: about 0.28% mean error vs PBE.
- BCC metals: about 0.58% mean error vs PBE.
- Semiconductors: about 0.24% mean error vs PBE.
- Ionic oxides: about 1.07% mean error vs PBE.
- 2D materials: about 0.28% mean error vs PBE.
- Molecules: about 0.80% mean error vs PBE.

This is an important result: the active-learning workflow is already accurate for many conventional systems using only a small number of DFT evaluations.

## Outlier Diagnosis and Correction

After the initial 51-system pass, 12 systems were identified with more than 5% mismatch against the literature structural references:

```text
o_on_cu111
h_on_pt111
h_on_cu111
bulk_nacoo2
co_on_pt111
bulk_litio2
h_on_ni111
co_on_ni111
o_on_ni111
bulk_licoo2_generated
co_on_cu111
bulk_sio2
```

The diagnosis was that these errors were not simply failures of the active-learning loop. In several cases, the allowed input ranges or prototype structure definitions did not properly match the literature validation target. For example:

- Some adsorption systems used broad top/bridge/hollow site sweeps when the literature comparison expected a specific site family and adsorption-height range.
- `bulk_litio2` was originally treated as a layered `a, c/a` structure, while the validation reference was a cubic/rocksalt-style lattice parameter.
- `bulk_nacoo2` and `bulk_licoo2` had c/a ranges that did not properly admit the literature c-axis values.
- `bulk_sio2` needed a tighter quartz-like structural range.

The input definitions were corrected so that the model is now testing the right physical domain. This is a good scientific move because it separates two questions:

1. Can the active-learning model optimize inside a physically meaningful domain?
2. Were the original DFT input definitions consistent with the literature validation target?

The corrections address the second issue and make the validation test more rigorous.

## Current Rerun Status

The corrected 12-system rerun is partially complete in the current report directory.

Confirmed corrected reports:

| System | Corrected report confirmed | Notes |
| --- | --- | --- |
| `o_on_cu111` | Yes | Uses corrected height/site range and stricter QE settings. |
| `h_on_pt111` | Yes | Uses corrected height/site range and stricter QE settings. |
| `h_on_cu111` | Yes | Uses corrected height/site range and stricter QE settings. |

The following nine systems still show old report settings and need to be rerun with the corrected wrappers:

```text
bulk_nacoo2
co_on_pt111
bulk_litio2
h_on_ni111
co_on_ni111
o_on_ni111
bulk_licoo2_generated
co_on_cu111
bulk_sio2
```

The rerun script is:

```text
run.sh
```

Run it from WSL:

```bash
cd <ACTISTRUCT_ROOT>
bash run.sh
```

After that, the analysis tables and figures should be regenerated so the final statistics reflect the corrected 12-system pass.

## How Powerful Is the Model Right Now?

The model is powerful as a proof-of-concept because it has already shown four important capabilities:

1. **Generality**  
   It is not limited to one molecule or one crystal. It has been applied to 51 systems across many material classes.

2. **Data efficiency**  
   The initial benchmark converged with about 6.3 QE calls per system on average. That is far smaller than a dense brute-force grid for each structure.

3. **Uncertainty-aware optimization**  
   The Gaussian process does not only predict an energy. It also estimates uncertainty, which allows the model to choose new calculations intelligently.

4. **Failure diagnosis**  
   The 12 outliers were identified systematically. This is valuable because it showed where the physical input definitions needed correction, rather than treating every mismatch as a model failure.

At the same time, the project should be presented honestly. The current model is a strong active-learning DFT workflow, but it is not yet a fully general autonomous materials-discovery platform. It currently works on low-dimensional structural spaces and uses total-energy-based objectives. Future versions can expand toward force-aware relaxation, adsorption-energy reference handling, multi-objective optimization, and higher-dimensional chemical design.

## What Is Scientifically Strong About This Project?

This project is scientifically strong because it combines:

- A real DFT backend rather than only a toy surrogate.
- A reproducible active-learning loop.
- A chemically diverse 51-system benchmark.
- Automatic reporting, plotting, and analysis.
- Literature-based validation targets.
- A clear correction pathway for outliers.

The strongest claim is not that every initial number was perfect. The strongest claim is that the workflow can:

1. run across many systems,
2. learn with few expensive calculations,
3. identify structural optima,
4. quantify uncertainty,
5. expose when the physical input model needs refinement.

That is exactly what a useful scientific machine-learning workflow should do.

## Current Limitations

The current version has several important limitations:

- Most generated benchmark systems use one or two design variables.
- `relax=False` is used in the current generated wrappers unless explicitly changed.
- With `relax=True`, each proposed structure is relaxed before energy evaluation, which can improve DFT energy quality but also changes the interpretation of the original input parameter.
- Current structural validation compares optimized input parameters to literature values; if relaxation is enabled, final relaxed geometries should also be extracted and compared.
- Some adsorption models use simplified site/height parameterizations.
- Formation, cohesive, and adsorption-energy comparisons need consistent reference calculations before being claimed quantitatively.
- The corrected 12-system rerun is not yet fully reflected in the final analysis outputs.

These limitations are normal for a proof-of-concept, and they define a clear path for the next research stage.

## Recommended Next Steps

1. Finish the remaining nine corrected reruns:

```bash
cd <ACTISTRUCT_ROOT>
bash run.sh
```

2. Regenerate extracted results, tables, and figures:

```bash
cd <ACTISTRUCT_ROOT>
python analysis/extract_all_results.py
python analysis/generate_tables.py
python analysis/generate_figures.py
python analysis/generate_si.py
python analysis/preflight_check.py
```

3. Review the updated mismatch table and confirm whether the 12 corrected systems are now within the desired validation threshold.

4. Commit the clean code and corrected input definitions to GitHub.

5. Commit updated reports and figures separately after the corrected rerun is complete.

6. For a publication-grade next version, add optional relaxed-geometry extraction so the model can report final relaxed lattice constants, bond lengths, and adsorption heights directly.

## Suggested Message to a Professor

This project implements an active-learning inverse-design workflow for DFT-based atomistic structure optimization. It combines ASE, Quantum ESPRESSO, Gaussian-process regression, uncertainty-guided sampling, and differential-evolution inverse proposals. The workflow has been demonstrated on a 51-system benchmark covering metals, semiconductors, oxides, 2D materials, molecules, battery materials, surface adsorption systems, and intermetallics. The first full pass converged for all 51 systems with a small average number of QE calculations, and the analysis identified 12 outliers where the input domains did not fully match literature validation targets. Those 12 systems have now been corrected with literature-aligned parameter ranges and stricter QE settings, and the corrected reruns are in progress. The project is therefore a strong proof-of-concept for data-efficient, uncertainty-aware DFT structural optimization, with a clear path toward publication-quality validation after the corrected reruns and final analysis refresh.

## Key Files

| File or directory | Purpose |
| --- | --- |
| `qe_active_inverse_common.py` | Shared active-learning and inverse-design engine. |
| `generated_models/` | 51 generated benchmark wrappers. |
| `generated_models/structure_builders.py` | Reusable ASE builders for generated systems. |
| `analysis/publication_data.py` | Literature references, parser logic, and validation metadata. |
| `analysis/` | Result extraction, tables, figures, SI generation, and preflight checks. |
| `outputs/reports/` | Per-system run reports. |
| `analysis/outputs/figures/` | Main manuscript-style figures. |
| `analysis/outputs/tables/` | LaTeX and CSV summary tables. |
| `tests/test_builders_and_config.py` | Smoke tests for builders and configuration. |
| `run.sh` | Runs the 12 corrected outlier systems one by one. |

## Bottom Line

`inverse_active` is now a substantial working research prototype. It has moved from single-example active learning to a broad 51-system DFT benchmark. The model has proven that it can run, learn, converge, and diagnose errors across diverse atomistic systems. The remaining task is to finish the corrected 12-system rerun and regenerate the final analysis outputs. Once that is done, the project will be much stronger as a GitHub repository, professor-facing research demonstration, and foundation for a manuscript.
