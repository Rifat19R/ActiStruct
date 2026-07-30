# Reproducibility package

The authoritative guide is `docs/reproducibility.md`.

- `evidence_sha256.txt` pins selected reviewer-facing evidence at its stable
  path.
- The test suite verifies every listed file and digest.
- Live QE scratch and pseudopotential binaries are intentionally not bundled.

Use the fast checks before considering cached analysis or live QE reproduction.
