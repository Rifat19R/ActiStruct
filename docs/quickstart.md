# Quickstart

## 1. Install the offline stack

```bash
python -m pip install -e ".[test]"
```

## 2. Run the no-QE Ti3C2-O example

```bash
python examples/quickstart/no_qe_ti3c2o.py
```

This example uses the committed structure and synthetic training targets to
exercise structure generation, GNN embeddings, GP prediction, and the ledger.
It demonstrates the software path; it is not benchmark evidence and does not
reproduce a DFT result.

## 3. Run the reliability-aware acquisition example

```bash
python examples/reliability_aware_quickstart.py
```

This uses committed offline data to compare standard and failure-aware
candidate ranking. It launches no DFT calculation.

## 4. Run the tests

```bash
python -m pytest -q
```

Verified after reorganization: `467 passed` with no warnings. Exact counts may
increase as tests are added; any reduction requires review.

## Next steps

- Read [architecture](architecture.md) to find the relevant module.
- Use [benchmarks](benchmarks.md) to inspect existing evidence.
- Use [reproducibility](reproducibility.md) to distinguish cached analysis
  from expensive live-QE work.
