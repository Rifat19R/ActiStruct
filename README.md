# ActiStruct

ActiStruct is an **experimental reliability-aware active-learning workflow
for DFT-guided materials discovery**. It does not replace Quantum ESPRESSO
(QE)/PBE calculations. It learns from *completed* QE/PBE calculations,
including failures and uncertainty, to help triage which candidate
calculations are worth running next.

## Topics

`inverse-design` `active-learning` `dft` `quantum-espresso` `ase`
`gaussian-process` `bayesian-optimization` `materials-science`
`atomistic-simulation` `structure-optimization` `reliability-aware-al`

## Project Overview

ActiStruct grew out of a GP/LCB active-learning engine for DFT structure
optimization (`qe_active_inverse_common.py`, the 50-workflow benchmark in
`generated_models/`). On top of that engine, ActiStruct now adds a
**reliability-aware** layer: a parser and dataset builder that record QE
failures as first-class data, a failure-risk classifier trained on those
records, and a soft failure-risk penalty wired into the GP/LCB acquisition
score. The goal is to reduce wasted DFT time by down-ranking candidates that
look likely to fail, without ever hard-rejecting them.

## Current Workflow

```text
DFT/QE outputs
    -> reliability parsing
    -> ML failure-risk prediction
    -> GP/LCB candidate proposal
    -> failure-aware Bayesian acquisition
    -> safer next DFT candidate selection
```

The scientific identity is intentionally conservative:

```text
ML predicts.
Uncertainty ranks.
Failure-risk penalizes risky candidates.
QE/PBE validates final claims.
```

## Implemented Components

- **Shared GP/LCB active-learning engine** — `qe_active_inverse_common.py`,
  with 50 generated QE benchmark workflows in `generated_models/`.
- **QE reliability parser and dataset builder** — `actistruct/parsers/qe.py`,
  `actistruct/datasets/qe_records.py` (see `docs/qe_reliability_parser.md`).
  Records both successful and failed QE runs; failures are never discarded.
- **Reliability classifier (v0.1-v0.3.2)** — `analysis/train_qe_reliability_classifier.py`,
  `analysis/qe_reliability_generalization_fix.py`. Predicts pre-run failure
  risk from setup-time features only (cutoffs, k-points, smearing, pseudopotential
  family, composition) — never from post-run fields such as convergence flags,
  final energy, or wall time.
- **Failure-aware acquisition** — `actistruct/acquisition/reliability.py`,
  wired into the live GP/LCB proposal path in `qe_active_inverse_common.py`
  (`failure_risk_provider`, gamma modes `mild`/`balanced`/`aggressive`). Old
  LCB behavior is preserved exactly when no failure-risk estimate is
  available, or when gamma = 0.
- **Offline benchmarks (v0.5.0, v0.5.1)** — `analysis/simulated_failure_aware_al_benchmark_v05.py`
  and `analysis/simulated_failure_aware_al_benchmark_v051.py`. Simulated,
  reproducible comparisons of candidate-selection policies using completed
  records; no new QE/DFT jobs are launched by these scripts.
- **Original 50-workflow QE/PBE benchmark** — generated structure-optimization
  workflows across bulk solids, 2D materials, molecules, battery/perovskite
  systems, and surfaces (see `PROJECT_OVERVIEW.md` for that benchmark's own
  scope and validation status).

## Current Benchmark Status

**Reliability classifier (v0.3.2, repeated group splits, 20 splits):**

```text
threshold 0.05 -> failure recall 0.776 +/- 0.344
threshold 0.10 -> failure recall 0.725 +/- 0.377
threshold 0.30 -> failure recall 0.300 +/- 0.359
```

The standard deviation is large across held-out-material splits. This is a
soft DFT-triage signal, not a hard rejection rule (see
`reports/qe_reliability_classifier_v032_group_generalization.md`).

**v0.5.0 offline benchmark (single trial, full candidate pool):**
`lcb_only` already selected 0 known failures at top-10, so v0.5.0 could not
show a failure-count improvement over LCB-only. The aggressive failure-aware
penalty reduced mean predicted failure risk of the top-10 set from 0.152 to
0.066 while preserving 0 known failures (see
`reports/simulated_failure_aware_al_benchmark_v05.md`).

**v0.5.1 offline stress benchmark (50 repeated trials, 4 candidate-pool
modes):** with smaller, harder candidate pools, `lcb_only` no longer always
avoids every known failure, which lets failure-aware re-ranking show a real
effect:

| Pool mode | Risk vs LCB-only (aggressive) | Failure-count vs LCB-only (aggressive) |
| --- | --- | --- |
| `normal_pool` | reduced | reduced, clearly |
| `failure_enriched_pool` | reduced | reduced, clearly |
| `heldout_material_pool` | reduced | reduced, but small/noisy |
| `high_uncertainty_pool` | reduced | not universally better |

See `reports/simulated_failure_aware_al_benchmark_v051.md` and
`reports/actistruct_status_v051.md` for the full numbers and caveats.

## Safe Claims

- ActiStruct learns from completed QE/PBE calculations, including failures
  and uncertainty, to help triage candidate calculations.
- Current reliability/acquisition results are **offline benchmarks and
  simulations using completed records** — no new QE/DFT jobs were run to
  produce them.
- Failure-aware acquisition acts as a **soft triage signal, not a hard
  guarantee**: candidates are re-ranked by predicted risk, never rejected
  outright, and old LCB behavior is preserved when risk is unavailable or
  gamma = 0.
- In repeated offline stress tests (v0.5.1), failure-aware LCB reduced mean
  predicted failure risk across all tested pool modes, and reduced known
  failed selections relative to LCB-only most clearly in normal and
  failure-enriched pools — behavior was weaker in held-out-material pools and
  not universally better in high-uncertainty pools.

ActiStruct does **not** claim:

- a universal materials-discovery engine,
- guaranteed reduction of failed DFT jobs,
- that failure-aware LCB always outperforms LCB-only,
- live DFT savings (no live GP/QE active-learning run with failure-aware
  acquisition has been performed yet),
- that it replaces QE/PBE validation.

## Limitations

- Failure-risk recall has large split-to-split variance on held-out
  materials; it should not be used as a hard accept/reject filter.
- The v0.5.x benchmarks use a constant `predicted_value = 0.0` placeholder
  (no live GP energy model queried), so policy differences come from the
  uncertainty proxy and the failure-risk penalty, not a predicted-energy
  signal.
- Each v0.5.0/v0.5.1 candidate's failure risk is drawn from a single v0.3.2
  held-out group split, not averaged across the 20 repeated splits.
- `heldout_material_pool` and `high_uncertainty_pool` stress conditions in
  v0.5.1 did not show a clear failure-count improvement; only the risk
  reduction is consistent across all four pool modes.
- No live QE/DFT active-learning run with failure-aware acquisition has been
  performed yet; all reliability/acquisition evidence so far is offline.

## Repository Structure

```text
ActiStruct/
|-- qe_active_inverse_common.py          # shared GP/LCB active-learning QE engine
|-- actistruct/
|   |-- parsers/qe.py                    # QE output parser (records failures too)
|   |-- datasets/qe_records.py           # dataset builder for parsed QE records
|   `-- acquisition/reliability.py       # failure-aware LCB acquisition scoring
|-- analysis/                            # classifier training, generalization tests,
|   |                                    # offline v0.5.0/v0.5.1 benchmarks, manuscript helpers
|-- generated_models/                    # 50 generated benchmark scripts and canonical runner
|-- examples/manual_qe/                  # standalone manual QE examples
|-- data/                                # parsed records, predictions, benchmark CSVs
|-- docs/                                # setup notes and parser/spec documentation
|-- reports/                             # reliability/acquisition/benchmark markdown reports
|-- outputs/
|   |-- reports/                         # 50-workflow final report text and JCTC draft
|   `-- plots/                           # convergence and model plots
|-- tests/                               # pytest suite (no QE/DFT launched)
|-- pseudo/README.md                     # pseudopotential notes only
|-- run.sh                               # top-level runner wrapper
|-- requirements.txt
|-- pyproject.toml
|-- CITATION.cff
|-- CODE_OF_CONDUCT.md
|-- CHANGELOG.md
|-- SECURITY.md
|-- LICENSE
`-- README.md
```

## Getting Started / Tests

```bash
cd <ACTISTRUCT_ROOT>
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e ".[test]"
```

Required Python packages: numpy, scipy, matplotlib, scikit-learn, ase.
`pip install -e ".[test]"` additionally installs `pytest` (declared as the
`test` optional-dependency in `pyproject.toml`) — `pytest -q` will fail with
"command not found" if this step is skipped and `pytest` isn't already
available globally.

Run the full test suite (no QE/DFT is launched by any test):

```bash
pytest -q
```

This currently passes with **73 tests** covering the reliability parser,
dataset builder, classifier, failure-aware acquisition scoring, and the
v0.5.0/v0.5.1 offline benchmarks, plus the original generated-workflow smoke
tests.

Legacy direct-invocation smoke tests are also still available:

```bash
python tests/test_builders_and_config.py
python tests/test_generated_workflows.py
```

To regenerate the offline reliability/acquisition benchmarks (deterministic,
no QE/DFT):

```bash
python analysis/simulated_failure_aware_al_benchmark_v05.py
python analysis/simulated_failure_aware_al_benchmark_v051.py
```

For a no-DFT walkthrough of the reliability-aware benchmark track, see
[`docs/reliability_aware_quickstart_v063.md`](docs/reliability_aware_quickstart_v063.md).

## Quantum ESPRESSO Setup (for the underlying GP/LCB engine)

ActiStruct expects Quantum ESPRESSO to be configured through environment
variables or available in `PATH`. Use WSL/Linux for QE runs.

```bash
export ESPRESSO_PSEUDO=/path/to/SSSP_1.3.0_PBE_efficiency
export ESPRESSO_COMMAND="mpirun -np 2 pw.x"
which pw.x
```

Pseudopotential binaries are not committed. See `pseudo/README.md` and
`docs/qe_setup.md`.

## Running the 50-Workflow QE Benchmark

```bash
bash run.sh all
bash run.sh battery
bash run.sh adsorption
bash run.sh molecules
bash run.sh solids
bash run.sh two-d
bash run.sh one generated_models/bulk_litio2_qe_active_inverse.py
```

Logs are written to `run_logs/`. Runtime caches are written to
`outputs/cache/`. Final reports and plots are written to `outputs/reports/`
and `outputs/plots/`.

Direct QE/PBE grid validations:

```bash
python analysis/direct_grid_validation.py dry-run
python analysis/direct_grid_validation.py summarize
```

| System | Grid | Status | Delta vs AL |
| --- | ---: | --- | ---: |
| Cu FCC | 20/20 | pass | 0.000198 eV/atom |
| MoS2 monolayer | 49/49 | pass | 0.000916 eV/atom |
| Rocksalt MgO | 20/20 | pass | 0.000157 eV/atom |
| Diamond Si | 20/20 | pass | 0.000233 eV/atom |

See `analysis/DIRECT_GRID_VALIDATION.md` for details. This validates the
underlying GP/LCB structure-optimization engine, not the reliability/
failure-aware acquisition layer.

## Results Interpretation

Absolute total energies should not be compared directly to literature unless
pseudopotentials, cutoffs, spin state, DFT+U treatment, smearing, Hubbard
corrections, and reference-energy conventions match. Surface entries are
structure-search objective energies, not quantitative adsorption energies,
unless an explicit clean-slab plus adsorbate reference calculation is
enabled. The strongest validation signal for the underlying engine is
structural parameter recovery for a documented 23-check subset; the
strongest evidence for the reliability/acquisition layer so far is the
offline v0.5.0/v0.5.1 benchmarks described above.

## Near-Term Roadmap

- Validate failure-aware acquisition against a live GP/QE active-learning
  run (not yet performed) before claiming any live DFT savings.
- Investigate why `heldout_material_pool` and `high_uncertainty_pool` show
  weaker/non-universal failure-count improvement in v0.5.1.
- Continue treating failure-risk as a soft triage signal given the large
  split-to-split variance documented in v0.3.2.
- No GNN-based surrogate or v0.6 feature work is planned until the offline
  failure-aware acquisition path is validated live.

The future live QE/PBE validation-batch design is documented in
[`reports/live_qe_validation_batch_design_v070.md`](reports/live_qe_validation_batch_design_v070.md).
No DFT has been run for this design; it is a design-only document.

## Citation

If ActiStruct supports your work, please cite the repository metadata in
`CITATION.cff`. Update the DOI after archival release.

## Acknowledgments

ActiStruct was developed with selective AI-assisted support for code review,
debugging guidance, documentation refinement, and release-workflow cleanup.
Scientific direction, algorithmic design, implementation decisions, validation
strategy, benchmark interpretation, and release responsibility remain with the
project maintainer.

## License

MIT License. See `LICENSE`.
