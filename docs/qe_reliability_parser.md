# QE Reliability Parser

ActiStruct includes a dependency-free parser for Quantum ESPRESSO `pw.x`
outputs:

```python
from actistruct.parsers.qe import parse_qe_output_file

record = parse_qe_output_file(
    "espresso.pwo",
    input_path="espresso.pwi",
    material_id="bulk_si",
)
print(record.to_dict())
```

The parser records both successful and failed calculations. This is important
for reliability-aware active learning: failed SCF jobs, malformed inputs, and
completed-but-unconverged runs are part of the scientific signal, not clutter.

## Parsed Fields

- convergence status,
- QE job completion status,
- SCF iterations,
- final energy in Ry and eV,
- total force,
- pressure,
- wall time,
- QE cutoffs and mixing settings,
- smearing,
- k-point grid,
- pseudopotential filenames,
- inferred pseudopotential family,
- failure reason,
- calculation hash.

## Scope

The parser is intended for metadata extraction and dataset-building. It does
not replace ASE, pymatgen, or domain-specific QE parsers for full trajectory,
wavefunction, or density analysis.

## Dataset Builder

The companion builder scans QE output files or directories and writes stable
CSV records:

```bash
python -m actistruct.datasets.qe_records \
  --base-path . \
  --output data/parsed_records/qe_reliability_records.csv \
  outputs/qe_runs/h2_r0p620000_pid237608_attempt1/espresso.pwo
```

The first committed CSV includes three successful H2 outputs and two failed
Li2NaV2(PO4)3 geometry-overlap outputs. Failed jobs are included by design.

The Li2NaV2(PO4)3 rows are legacy invalid-geometry scratch outputs. The shared
QE engine now validates minimum interatomic distance before launching QE, so
future exact-overlap candidates are rejected cheaply instead of consuming a QE
job.
