# ActiStruct: Active-Learning Inverse Design for DFT Structure Optimization

ActiStruct is a research workflow for active-learning inverse design of atomistic structures with Quantum ESPRESSO, ASE, Gaussian-process surrogate models, and differential-evolution acquisition. It is designed to reduce the number of expensive DFT evaluations needed to locate low-energy structural parameters across molecules, bulk crystals, two-dimensional materials, battery materials, and surface adsorption systems.

## Topics

`inverse-design` `active-learning` `dft` `quantum-espresso` `ase` `gaussian-process` `bayesian-optimization` `materials-science` `atomistic-simulation` `structure-optimization`

## What Is Included

- Shared active-learning engine: `qe_active_inverse_common.py`
- 51 generated QE benchmark workflows: `generated_models/`
- Structure builders for molecules, crystals, 2D materials, cathode models, and adsorption systems
- Completed benchmark reports: `outputs/reports/`
- Convergence and surrogate plots: `outputs/plots/`
- JCTC-style results draft: `outputs/reports/NEBWALK_INVERSE_ACTIVE_JCTC_RESULTS_DRAFT.md`
- Supporting manuscript-style document: `inverse_active_supporting_results_Aplus.docx`

Raw Quantum ESPRESSO scratch directories are local reproducibility artifacts and are ignored by git by default. Final reports and plots are kept in the repository.

## Method Summary

ActiStruct uses a compact loop:

```text
initial structures -> QE labels -> Gaussian process -> active learning -> inverse proposal -> QE labels
```

For each system, a small set of initial structural parameters is evaluated with QE through ASE. A Gaussian-process model is trained on the labeled data, uncertain candidates are selected for active learning, and differential evolution proposes low-energy candidates through a lower-confidence-bound acquisition function. Caches prevent repeated QE calculations.

## Current Output Status

The local benchmark set contains 51 generated workflows with final reports. The report archive also includes several older legacy/demo reports for traceability.

Summary from the local reports:

- Generated benchmark scripts: 51
- Generated benchmark reports with `FINAL RESULT`: 51 / 51
- Total report files: 59
- Total final reports: 51 / 59
- Main scalar structural sanity checks: mean absolute percentage deviation about 0.68% across 24 reference checks

See:

- `outputs/reports/NEBWALK_INVERSE_ACTIVE_JCTC_RESULTS_DRAFT.md`
- `inverse_active_supporting_results_Aplus.docx`

## Repository Layout

```text
ActiStruct/
|-- qe_active_inverse_common.py          # shared active-learning QE engine
|-- generated_models/                    # generated benchmark scripts and runner
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
cd /mnt/d/Rifat_kh/inverse_active
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

ActiStruct expects `pw.x` in `PATH` or at one of the known local paths in `qe_active_inverse_common.py`.

Check:

```bash
which pw.x
```

The local benchmark configuration expects SSSP 1.3.0 PBE efficiency pseudopotentials at:

```text
/mnt/d/Rifat_kh/SSSP_1.3.0_PBE_efficiency
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

Logs are written to `run_logs/`. Final reports and plots are written to:

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

## License

MIT License. See `LICENSE`.