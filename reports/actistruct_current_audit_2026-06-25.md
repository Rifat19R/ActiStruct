# ActiStruct Current Audit - 2026-06-25

## Status

ActiStruct is currently best described as a reproducible active-learning
workflow benchmark for Quantum ESPRESSO structure-search objectives. It is not
yet a fully validated materials-discovery framework.

## Verification

- ActiStruct preflight: passed.
- ActiStruct tests: 14 passed.
- Public/local GitHub comparison before this audit: local `HEAD` matched
  GitHub `main`; the analysis cleanup was committed afterward.
- Main generated benchmark set: 50 workflows, 50 parsed reports.
- Mean successful QE calls across the parsed benchmark: about 6.0.

## Current Evidence

- Conventional validation categories have low primary-parameter error:
  FCC metals, BCC metals, semiconductors, simple ionic oxides, 2D materials,
  molecules, and intermetallics are suitable for cautious workflow claims.
- Overall primary-parameter MAE vs encoded PBE references is about 3.58%.
- Four direct-grid validations pass the 1 meV/atom criterion: Cu FCC, MoS2,
  MgO, and Si.
- Active-learning/grid comparison currently supports a data-efficiency claim
  for the implemented search ranges, not a universal discovery claim.

## Scientific Caveats

- Surface adsorption rows are prototype structure-search models. They optimize
  simplified height/site variables using total-energy objectives and should not
  be presented as adsorption-energy benchmarks.
- Battery/perovskite structures need stricter crystallographic degrees of
  freedom and reference curation before quantitative claims.
- Literature references encoded in `analysis/publication_data.py` still need
  manuscript-level verification against primary papers or curated databases.
- QE version, SSSP version, pseudopotential filenames, cutoffs, smearing,
  spin state, and Hubbard corrections must be documented before outreach or
  preprint claims.

## Kulik-Aligned Positioning

The strongest alignment is not "new materials discovered." The credible angle
is:

```text
ActiStruct reduces wasteful electronic-structure evaluations by combining
Quantum ESPRESSO calculations, Gaussian-process uncertainty, reproducible
metadata, and active selection for atomistic structure-search workflows.
```

This connects to electronic-structure reliability, ML-guided simulation,
uncertainty-aware active learning, and computational materials/catalysis
workflows.

## Next Implementation Priority

The QE reliability parser now extracts completed and failed calculation
metadata into a structured schema:

- convergence status,
- SCF iteration count,
- final energy,
- total force,
- pressure,
- wall time,
- QE cutoffs and mixing settings,
- pseudopotential filenames,
- k-point grid,
- failure reason,
- calculation hash.

This parser should support both successful and failed QE outputs, because
failed calculations are part of the scientific reliability signal.

## QE Reliability Records - First Evidence Set

The first real parsed-record dataset is:

```text
data/parsed_records/qe_reliability_records.csv
```

It contains five real local QE calculations:

- 3 successful H2 single-point outputs from `outputs/qe_runs/`.
- 2 failed Li2NaV2(PO4)3 outputs from `outputs/qe_runs_bulk_li2nav2po43/`.

The successful rows include energies, SCF iteration counts, forces, pressure,
wall time, cutoffs, k-points, smearing, mixing beta, pseudopotential filenames,
and calculation hashes. The failed rows are intentionally included and labeled
with `failure_reason=geometry_overlap`.

The Li2NaV2(PO4)3 overlap rows are legacy local QE scratch outputs from an
invalid geometry, not a valid failed chemistry result. They cannot be converted
into successful calculations after the fact without rerunning from a corrected
crystallographic builder. The code now includes a pre-QE minimum-distance
validator in `qe_active_inverse_common.py`, so exact or near-exact atomic
overlaps are skipped before launching Quantum ESPRESSO.

This is an evidence seed for reliability-aware active learning, not yet a full
benchmark dataset. The next step is to scale the same builder over a curated
set of successful, unconverged, and failed QE runs while preserving provenance.
