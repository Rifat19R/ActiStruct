# TMC reliability benchmark

## Scientific purpose

Evaluate ActiStruct's QE parsing, reliability metadata, feature construction,
small-data GP baseline, and retrospective active-learning workflow on real
transition-metal-complex calculations.

## Systems

Ferrocene, Ni(CO)4, Cr(CO)6, and Fe(CO)5; 16 converged QE records passing the
documented internal checks.

## Protocol and evidence

- Main report: `reports/tmc_benchmark_v1.0.md`
- Processed dataset: `data/processed/full_dataset_v0.2.csv`
- QE inputs/outputs: `qe/`
- Run records: `runs/`
- Structures: `structures/`
- Literature references: `references/reference_values_tmc_v0.yaml`
- Historical phase record: `docs/development/history/tmc_phase1.md` and
  `docs/development/history/tmc_phase2.md`

## Reproduce from committed data

```bash
python scripts/12_baseline_model.py
python scripts/14_active_learning_demo.py
python -m pytest -q tests/test_qe_parser.py tests/test_dataset_validation.py tests/test_convergence_and_consistency.py
```

Expected outputs include the baseline and AL JSON/report artifacts already
committed under `data/models/` and `reports/`. The commands above use retained
records and do not launch QE.

## Limitations

The dataset is small. The AL demonstration is retrospective. The ferrocene
D5h-to-D5d value is an optimized conformer energy difference, not a computed
transition-state barrier. Some non-ferrocene primary literature geometry
checks remain incomplete.
