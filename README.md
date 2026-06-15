# ActiStruct: Active-Learning Inverse Design for DFT Structure Optimization

ActiStruct is a research workflow for active-learning inverse design of atomistic structures with Quantum ESPRESSO, ASE, Gaussian-process surrogate models, and differential-evolution acquisition. It is designed to reduce the number of expensive DFT evaluations needed to locate low-energy structural parameters across molecules, bulk crystals, two-dimensional materials, battery materials, and surface adsorption systems.

## Topics

`inverse-design` `active-learning` `dft` `quantum-espresso` `ase` `gaussian-process` `bayesian-optimization` `materials-science` `atomistic-simulation` `structure-optimization`

## What Is Included

- Shared active-learning engine: `qe_active_inverse_common.py`
- 51 generated QE benchmark workflows: `generated_models/`
- Standalone manual QE examples: `examples/manual_qe/`
- Structure builders for molecules, crystals, 2D materials, cathode models, and adsorption systems
- Completed benchmark reports: `outputs/reports/`
- Convergence and surrogate plots: `outputs/plots/`
- JCTC-style results draft: `outputs/reports/NEBWALK_INVERSE_ACTIVE_JCTC_RESULTS_DRAFT.md`
- Supporting manuscript-style document: `ActiStruct_supporting_results.docx`

Raw Quantum ESPRESSO scratch directories are local reproducibility artifacts and are ignored by git by default. Final reports and plots are kept in the repository.

## Method Summary

ActiStruct uses a compact loop:

```text
initial structures -> QE labels -> Gaussian process -> active learning -> inverse proposal -> QE labels
```

For each system, a small set of initial structural parameters is evaluated with QE through ASE. A Gaussian-process model is trained on the labeled data, uncertain candidates are selected for active learning, and differential evolution proposes low-energy candidates through a lower-confidence-bound acquisition function. Caches prevent repeated QE calculations.

## Current Output Status

The local benchmark set contains 51 generated workflows, and the repository keeps only those 51 final benchmark reports.

Summary from the local reports:

- Generated benchmark scripts: 51
- Generated benchmark reports with `FINAL RESULT`: 51 / 51
- Total final report files: 51
- Total final reports: 51 / 51
- Main scalar structural sanity checks: mean absolute percentage deviation about 0.68% across 24 reference checks

See:

- `outputs/reports/NEBWALK_INVERSE_ACTIVE_JCTC_RESULTS_DRAFT.md`
- `ActiStruct_supporting_results.docx`

## Repository Layout

```text
ActiStruct/
|-- qe_active_inverse_common.py          # shared active-learning QE engine
|-- generated_models/                    # generated benchmark scripts and runner
|-- examples/manual_qe/                  # standalone manual QE examples
|-- analysis/                            # result extraction and manuscript helpers
|-- docs/                                # setup notes and original specifications
|-- outputs/
|   |-- reports/                         # final report text and JCTC draft
|   `-- plots/                           # convergence and model plots
|-- tests/                               # smoke tests that avoid launching QE
|-- pseudo/README.md                     # pseudopotential notes only
|-- run.sh                               # top-level runner wrapper
|-- requirements.txt
|-- pyproject.toml
|-- CITATION.cff
|-- CHANGELOG.md
|-- SECURITY.md
|-- LICENSE
`-- README.md
```

## Installation

Use WSL/Linux for Quantum ESPRESSO runs.

```bash
cd <ACTISTRUCT_ROOT>
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Required Python packages:

- numpy
- scipy
- matplotlib
- scikit-learn
- ase

## Quantum ESPRESSO Setup

ActiStruct expects Quantum ESPRESSO to be configured through environment variables or available in `PATH`.

Example setup:

```bash
export ESPRESSO_PSEUDO=/path/to/SSSP_1.3.0_PBE_efficiency
export ESPRESSO_COMMAND="mpirun -np 2 pw.x"
```

Check that QE is available:

```bash
which pw.x
```

Pseudopotential binaries are not committed. See `pseudo/README.md` and `docs/qe_setup.md`.

## Running Benchmarks

Run the validated generated benchmark set:

```bash
bash run.sh all
```

Run one group:

```bash
bash run.sh battery
bash run.sh adsorption
bash run.sh molecules
bash run.sh solids
bash run.sh two-d
```

Run one script directly:

```bash
bash run.sh one generated_models/bulk_litio2_qe_active_inverse.py
```

Logs are written to `run_logs/`. Runtime caches are written to `outputs/cache/`. Final reports and plots are written to:

```text
outputs/reports/
outputs/plots/
```

## Tests

Smoke tests do not launch QE:

```bash
source .venv/bin/activate
python tests/test_builders_and_config.py
```

## Results Interpretation

The final QE objectives are useful for ranking candidates within each system. Absolute total energies should not be compared directly to literature unless pseudopotentials, cutoffs, spin state, DFT+U treatment, smearing, and reference-energy conventions match. The strongest validation signal in this repository is structural parameter recovery and successful convergence across a chemically diverse benchmark set.

## Citation

If ActiStruct supports your work, please cite the repository metadata in `CITATION.cff`. Update the DOI after archival release.

## Acknowledgments
ActiStruct was developed with selective AI-assisted support for code review, debugging guidance, documentation refinement, and release-workflow cleanup. Scientific direction, algorithmic design, implementation decisions, validation strategy, benchmark interpretation, and release responsibility remain with the project maintainer.

## License

MIT License. See `LICENSE`.
