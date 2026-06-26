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

## QE Reliability Records - Expanded Evidence Set

The main parsed-record dataset is:

```text
data/parsed_records/qe_reliability_records.csv
```

It now contains 976 real local QE records:

- 589 converged records.
- 387 non-converged or non-completed records.
- Failure labels include `qe_error`, `job_not_completed`, and
  `scf_not_converged`.

The rows include energies where available, SCF iteration counts, forces,
pressure, wall time, cutoffs, k-points, smearing, mixing beta,
pseudopotential filenames, failure reasons, and calculation hashes.

Legacy invalid-geometry records are quarantined separately:

```text
data/parsed_records/qe_invalid_geometry_records.csv
```

That quarantine file contains 90 `geometry_overlap` records. Those records are
invalid structure-generation/scratch failures, not meaningful electronic-
structure failures. They cannot be converted into successful calculations after
the fact without rerunning from corrected crystallographic builders. The code
now includes a pre-QE minimum-distance validator in
`qe_active_inverse_common.py`, so exact or near-exact atomic overlaps are
skipped before launching Quantum ESPRESSO.

This is now a useful local evidence dataset for reliability-aware active
learning, but it still needs curation before manuscript-level modeling because
some records are local scratch attempts rather than planned benchmark cases.
