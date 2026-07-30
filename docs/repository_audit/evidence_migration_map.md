# Evidence migration map

Repository reorganization date: 2026-07-31.

No scientific evidence directory or evidence file was moved, renamed,
deleted, or rewritten for presentation. Therefore every evidence mapping is
identity-preserving:

| Old path | New path | Hash record | Reason |
|---|---|---|---|
| `outputs/campaigns/` | unchanged | `reproducibility/evidence_sha256.txt` | Preserve append-only Ti3C2-O campaign provenance. |
| `data/evidence/` | unchanged | `reproducibility/evidence_sha256.txt` | Preserve clean-slab audit and interrupted-HF process metadata. |
| `data/processed/` | unchanged | selected TMC dataset hash in manifest | Preserve tests, reports, and parser traceability. |
| `qe/` | unchanged | existing per-workflow metadata/tests | Preserve retained TMC inputs and outputs. |
| `runs/` | unchanged | existing per-workflow metadata/tests | Preserve calculation and failure records. |
| `structures/` | unchanged | existing manifests/tests | Preserve structure provenance and endpoint paths. |
| `reports/` | unchanged | selected TMC report hash in manifest | Preserve dated scientific interpretation. |

Documentation and public-entry files were moved according to
`maloq_vs_actistruct.md`; those moves do not relocate scientific evidence.
