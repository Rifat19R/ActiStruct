# Reproducibility

ActiStruct separates fast software verification, cached analysis, and live
Quantum ESPRESSO reproduction. Do not describe these tiers as equivalent.

## Fast local checks

These commands launch no QE calculation:

```bash
python -m pip install -e ".[test]"
python -c "import actistruct; print(actistruct.__version__)"
python examples/reliability_aware_quickstart.py
python -m pytest -q
```

The pre-change baseline was `433 passed`; after repository-integrity tests were
added, the verified result was `467 passed` with no warnings.

## Cached benchmark reproduction

TMC reports can be regenerated from committed parsed/processed records:

```bash
python scripts/12_baseline_model.py
python scripts/14_active_learning_demo.py
python -m pytest -q tests/test_dataset_validation.py tests/test_baseline_model.py tests/test_al_demo.py
```

The Ti3C2-O result report should be checked against the append-only JSONL
files rather than rerunning DFT:

```bash
python -m pytest -q tests/test_repository_integrity.py
```

## Live QE reproduction

Live commands are expensive and require the exact environment,
pseudopotentials, runtime paths, and hardware review described by each
benchmark.

```bash
FIDELITY=low python -m examples.manual_qe.run_ti3c2_o_grid_campaign
FIDELITY=low python -m examples.manual_qe.run_ti3c2_o_al_loop
```

The first uncached Ti3C2-O evaluations can take hours. Do not launch these
commands merely to verify installation. The legacy 50-workflow collection is
launched with `bash scripts/run_generated_models.sh`, and also requires QE.

## Seeds and protocol

- Ti3C2-O seed sites, acquisition settings, stopping rule, duplicate
  handling, and dated amendments are in `docs/BENCHMARK_PROTOCOL.md`.
- Campaign records are in `outputs/campaigns/`.
- Random-state behavior is regression-tested.
- The TMC pipeline configuration is under `configs/`.

## Pseudopotentials

Pseudopotential binaries are external and gitignored. Required filenames,
sources, and recorded checksums are in
`configs/pseudo_manifest_required.yaml`; setup guidance is in
`pseudo/README.md`. Users must verify local files before live reproduction.

## Figures

The SVG files in `assets/` are identity/software diagrams, not scientific
plots. Existing scientific figures under `analysis/outputs/` and `reports/`
must be regenerated only through their corresponding analysis scripts and
committed data.

## Hardware limitations and HF status

The LF Ti3C2-O campaign required long live-QE runs. The attempted HF clean-slab
calculation did not complete in three attempts on the recorded WSL2
environment. No HF result exists. Read
`docs/hf_validation_status.md` before considering another HF run.

## Integrity manifest

Verify selected evidence:

```bash
python -m pytest -q tests/test_repository_integrity.py
```

The manifest is `reproducibility/evidence_sha256.txt`. Evidence paths were not
moved during the repository reorganization.
