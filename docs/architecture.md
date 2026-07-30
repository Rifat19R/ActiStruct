# Architecture

ActiStruct separates reusable software from system-specific DFT workflows and
scientific evidence.

```text
candidate structures
        |
        v
acquisition + surrogate
        |
        v
QE oracle / cache ---> parser ---> failure classification / recovery
        ^                                  |
        |                                  v
        +--------- model update <----- append-only ledger
                                           |
                                           v
                               evidence, reports, and hashes
```

## Library

- `actistruct/acquisition/`: failure-aware LCB ranking.
- `actistruct/core/`: append-only ledger and atomic cache.
- `actistruct/datasets/`: normalized QE reliability records.
- `actistruct/debug/`: output classification and cumulative retry strategies.
- `actistruct/gnn/`: SchNet-style encoder and frozen-embedding GP surrogate.
- `actistruct/parsers/`: QE output parsing.
- `actistruct/dashboard/`: optional monitoring UI.

## Legacy active-learning engine

`qe_active_inverse_common.py` is an installed top-level module used by the
generated QE workflows. It remains at the repository root because moving it
would change installed imports, scripts, and test assumptions. A future
`src/` migration must move the package and this engine atomically, update every
workflow, declare package data, and pass clean-install tests.

## Workflows and benchmarks

- `examples/` contains user-facing examples and live-QE drivers.
- `generated_models/` contains the retained v0.x workflow collection.
- `scripts/` contains the numbered TMC data/analysis pipeline and launchers.
- `benchmarks/` explains protocols and points to evidence without duplicating
  immutable data.

## Evidence boundaries

- Raw/reference and processed datasets remain under `data/`.
- TMC QE inputs/outputs and run trees remain under `qe/` and `runs/`.
- Ti3C2-O append-only logs remain under `outputs/campaigns/`.
- Reports remain under `reports/`.
- Raw QE scratch is normally local-only and gitignored.

These paths are intentionally stable because tests, hashes, reports, and
provenance records refer to them.
