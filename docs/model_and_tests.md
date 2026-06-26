# Model and Test Documentation

## Project Summary

This repository implements active learning and inverse design for atomistic
systems. The central task is to discover a structural parameter that produces a
desired energy response while minimizing expensive oracle evaluations.

The design variables are deliberately small so each workflow can converge with
few expensive labels:

- Cu2: Cu-Cu bond distance.
- H2: H-H bond distance.
- CH4: C-H bond distance at fixed tetrahedral geometry.
- H2O: O-H bond distance and H-O-H angle.
- Graphene: in-plane lattice constant.
- Bulk Cu: FCC lattice constant.
- Bulk Si: diamond-cubic lattice constant.
- Bulk MgO: rocksalt lattice constant.
- H/Pt(111): H in-plane fractional surface coordinates `(u, v)`.
- Bulk LiCoO2: hexagonal lattice constants `(a, c)`.
- H/Cu(111): H in-plane fractional surface coordinates `(u, v)`.

The oracle changes by system:

- EMT for fast Cu2 demonstration.
- Lennard-Jones surrogate for H2 proof of concept.
- Quantum ESPRESSO through ASE for H2, H2O, CH4, graphene, bulk Cu, bulk Si, bulk MgO, H/Pt(111), bulk LiCoO2, and H/Cu(111).

## Gaussian-Process Model

Let `x` be the design variable and `E(x)` be the oracle energy. The surrogate
learns:

```text
x -> Gaussian process -> mean energy, uncertainty
```

The training set is:

```text
D = {(x_i, E_i)}
```

The model predicts:

```text
mu(x), sigma(x)
```

where `mu(x)` is predicted energy and `sigma(x)` is model uncertainty.

For 2D workflows, `x` is a vector. H2O uses `(bond length, angle)`. H/Pt(111)
uses fractional surface coordinates `(u, v)`. If explicit references are enabled, the referenced objective is:

```text
E_ads(u, v) = E(Pt slab + H) - E(Pt slab) - E(H atom)
```

Bulk LiCoO2 uses `(a, c)` for the R-3m hexagonal cell and minimizes QE total
energy per atom. H/Cu(111) uses a surface structure-search objective unless clean-slab and isolated-H references are explicitly enabled.

## Active Learning

At each iteration:

1. Predict uncertainty over a dense candidate grid.
2. Select candidates with `sigma(x)` above threshold.
3. Label the most uncertain points with the oracle.
4. Retrain the Gaussian process.

## Inverse Design

Target matching workflows use:

```text
score(x) = -abs(mu(x) - target) + kappa * sigma(x)
```

Energy minimization workflows use lower confidence bound:

```text
LCB(x) = mu(x) - kappa * sigma(x)
```

The first balances target closeness and exploration. The second balances low
predicted energy and exploration.

## Quantum ESPRESSO Integration

QE workflows use ASE's `Espresso` calculator. Each calculation:

1. Builds an ASE `Atoms` object.
2. Attaches a QE calculator.
3. Runs `pw.x` through MPI.
4. Extracts total energy.
5. Converts to energy per atom or binding energy.
6. Caches the result.

## Tests

The current test command for the full repository is:

```bash
pytest -q
```

This collects **73 tests** across `tests/`, none of which launch Quantum
ESPRESSO. The suite spans both the original GP/LCB engine described above
and the reliability-aware layer documented in
`reports/actistruct_technical_report_v06.md`:

- `tests/test_builders_and_config.py` — the original GP/LCB engine smoke
  test: structure builders return the right atom counts/geometry (H2, H2O,
  CH4, graphene, bulk Cu/Si/MgO, H/Pt(111), bulk LiCoO2, H/Cu(111)), and QE
  scripts point to existing SSSP pseudopotentials with a spin-correct H atom
  reference for H2.
- `tests/test_generated_workflows.py` — confirms all 50 generated benchmark
  workflows import and build without launching QE.
- `tests/test_qe_reliability_parser.py` — QE `pw.x` output parsing,
  including successful runs, namelist errors, and SCF-not-converged cases.
- `tests/test_qe_records_dataset.py` — dataset builder: scans success/failed
  runs, writes stable CSV columns, quarantines invalid-geometry records.
- `tests/test_qe_reliability_summary.py` — dataset summary counts/labels and
  report rendering.
- `tests/test_qe_reliability_classifier.py` — classifier training, the
  binary success label, and leakage-control checks (post-run fields are
  excluded from features).
- `tests/test_failure_aware_acquisition.py` — failure-aware GP/LCB scoring:
  soft-penalty behavior, NaN/negative-uncertainty rejection, malformed
  failure-risk handling, and exact LCB fallback when risk is absent or
  gamma = 0.
- `tests/test_simulated_failure_aware_al_benchmark.py` — the v0.5.0 offline
  benchmark (policy/top-k coverage, no hard deletion of candidates).
- `tests/test_simulated_failure_aware_al_benchmark_v051.py` — the v0.5.1
  repeated-trial stress benchmark (pool modes, delta-vs-LCB columns, report
  caveats and safe-claim wording).
- `tests/test_analysis_paths.py` — path-handling regressions for the
  original manuscript/benchmark-extraction scripts (OS-independent paths,
  preflight-check failure behavior).

Legacy direct-invocation smoke tests are also still runnable individually:

```bash
python tests/test_builders_and_config.py
python tests/test_generated_workflows.py
```

## Reproducibility Notes

For publication-quality results, record:

- QE version,
- pseudopotential filenames,
- cutoffs,
- k-point grids,
- smearing settings,
- convergence thresholds,
- MPI process count,
- report file for each run.

Each production script writes a report under:

```text
outputs/reports/
```

## Current Limitations

- Small low-dimensional design spaces only.
- No force training yet.
- No multi-objective optimization yet.
- No full DFT convergence study yet.
- Manuscript preparation should use the completed benchmark table and curated reference provenance.
