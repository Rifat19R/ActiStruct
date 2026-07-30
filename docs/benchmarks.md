# Benchmark index

## Transition-metal complexes

The [TMC reliability benchmark](../benchmarks/tmc/README.md) covers
ferrocene, Ni(CO)4, Cr(CO)6, and Fe(CO)5. It includes retained QE records,
parser and convergence checks, structure/features datasets, a GP baseline,
and a retrospective AL demonstration.

## Ti3C2-O hydrogen adsorption

The [Ti3C2-O benchmark](../benchmarks/ti3c2o/README.md) covers the completed
low-fidelity campaign with GNN-embedding GP, corrected periodic plain GP, and
random tracks. The original buggy plain-GP behavior and the corrected rerun
are both retained.

HF ranking validation did not complete and is not a benchmark result. See
[HF validation status](hf_validation_status.md).

## Evidence integrity

Selected reviewer-facing artifacts are listed with SHA-256 checksums in
`reproducibility/evidence_sha256.txt` and checked by the test suite. This
manifest complements, rather than replaces, the full Git history and
benchmark-specific metadata.
