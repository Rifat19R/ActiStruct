# ActiStruct Project Overview

## Current State

ActiStruct is a research codebase for active-learning inverse design of atomistic structures with Python, ASE, Gaussian-process surrogate modeling, differential-evolution acquisition, and Quantum ESPRESSO. The repository currently contains 51 generated workflow scripts and 51 final text reports. The public repository lists only the completed 51-workflow report set.

The project should be presented as a completed software benchmark and reproducible workflow demonstration, not as a claim that every one of the 51 systems is fully literature-validated. The strongest quantitative validation currently reported is a 24-system scalar structural sanity subset with about 0.68% mean absolute percentage deviation against documented structural references.

## Workflow

```text
structure variables -> ASE builder -> QE labels -> Gaussian process -> active query -> inverse proposal -> final report
```

Each generated workflow defines a module-level ASE structure builder, one or two physically meaningful variables, Quantum ESPRESSO pseudopotential names and numerical settings, active-learning settings, and a system-level `SYSTEM` object consumed by the shared engine.

The shared engine is `qe_active_inverse_common.py`. Generated workflows live in `generated_models/`. Manual standalone examples live in `examples/manual_qe/` and are not part of the 51-report generated benchmark.

## Benchmark Scope

| Category | Count |
| --- | ---: |
| Bulk solids and common crystals | 20 |
| Two-dimensional materials | 6 |
| Molecules | 6 |
| Battery/perovskite/intermetallic systems | 11 |
| Surface structure-search models | 8 |
| **Total generated workflows** | **51** |

Run the generated benchmark through the top-level wrapper:

```bash
bash run.sh all
```

The canonical generated-suite runner is:

```bash
bash generated_models/run_all_generated_models.sh all
```

## Results Language

The reported scalar objective is the QE optimization objective used by the workflow. For bulk and 2D periodic systems this is usually a total energy per atom. For molecules and surface models it is a total-energy-based structure-search objective.

Surface rows must not be described as quantitative adsorption energies unless the workflow explicitly computes:

```text
E_ads = E_slab+adsorbate - E_clean_slab - E_adsorbate_reference
```

The current public tables should therefore use careful labels such as `QE objective energy`, `relative optimization objective`, or `structure-search energy`.

## Validation Position

The repository supports these claims:

1. The 51 generated workflows import and define valid `SYSTEM` objects.
2. The 51 final reports contain completed `FINAL RESULT` sections.
3. The 24 scalar structural sanity checks show close agreement with documented references.
4. The framework records QE settings, pseudopotential filenames, variables, convergence metadata, plots, and reports in a reproducible layout.

The repository does not claim that all 51 systems are fully literature-validated. Literature-quality validation requires primary-paper or curated-database references, consistent pseudopotentials and cutoffs, and clearly defined reference-energy conventions.

## Reference Policy

Manuscript-level references should come from primary literature or curated crystallographic/scientific databases, for example Materials Project, COD, ICSD, NIST Chemistry WebBook/CCCBDB, or peer-reviewed papers. Non-curated public encyclopedia pages, local scratch notes, and private structure snippets are not acceptable as manuscript-level validation references.

## Reproducibility

Use `environment.yml` for a reproducible Python environment. Quantum ESPRESSO and SSSP pseudopotentials remain external requirements and are configured through environment variables:

```bash
export ESPRESSO_PSEUDO=/path/to/SSSP_1.3.0_PBE_efficiency
export ESPRESSO_COMMAND="mpirun -np 2 pw.x"
```

Public reports intentionally avoid local machine paths. Runtime caches and QE scratch files are ignored by git.

## Important Files

| Path | Purpose |
| --- | --- |
| `qe_active_inverse_common.py` | Shared active-learning and inverse-design engine |
| `generated_models/` | 51 generated benchmark workflows |
| `generated_models/run_all_generated_models.sh` | Canonical generated-suite runner |
| `run.sh` | Top-level wrapper around the generated-suite runner |
| `tests/test_generated_workflows.py` | Automatic import/build/config checks for every generated workflow |
| `outputs/reports/` | Final text reports and ActiStruct results draft |
| `outputs/plots/` | Convergence and surrogate plots |
| `docs/qe_setup.md` | QE setup notes |
| `environment.yml` | Reproducible Python environment specification |

## Near-Term Extension

The next planned benchmark extension is a separate set of MAX phase and MXene workflows. Those results should be added only after the calculations finish and their reports are produced.
