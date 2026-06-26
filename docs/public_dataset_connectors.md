# Public Dataset Connectors

## Goal

Scale ActiStruct from local Quantum ESPRESSO records toward larger
electronic-structure reliability datasets without running new DFT on the local
machine.

The first connector target should be NOMAD because it emphasizes calculation
metadata, provenance, workflow context, and multiple electronic-structure
codes.

## First Connector: NOMAD Metadata

NOMAD should initially be used as a metadata source, not as a drop-in
replacement for QE `.pwo` parsing.

Target fields to map into ActiStruct:

| ActiStruct field | NOMAD-style source concept |
| --- | --- |
| `material_id` | formula, material id, upload/entry id |
| `qe_output_path` | external entry URL or archive id |
| `converged` | calculation/workflow convergence flag if available |
| `job_done` | successful parser/workflow completion flag |
| `failure_reason` | parser error, convergence failure, missing metadata |
| `energy_ev` | final total energy |
| `energy_per_atom_ev` | total energy normalized by atom count |
| `ecutwfc` / `ecutrho` | basis-set cutoff metadata when available |
| `kpoints` | k-point mesh or density metadata |
| `smearing` | occupation/smearing metadata |
| `pseudo_family` | pseudopotential or code basis metadata |
| `calculation_hash` | stable external id plus metadata hash |

## Scientific Rules

- Do not label non-QE records as QE `.pwo` records.
- Keep source code/package provenance in the record.
- Separate VASP, QE, GPAW, FHI-aims, and other-code records where possible.
- Treat missing convergence metadata as unknown, not failed.
- Do not mix invalid structure-generation failures with SCF/convergence
  failures.
- Do not compare energies across codes or pseudopotentials unless reference
  conventions are explicitly controlled.

## Scaling Path

1. Current local ActiStruct CSVs: about 1k parsed local records.
2. Add NOMAD metadata sampling: target 10k records.
3. Add additional public sources only after schema checks:
   Materials Project, OQMD, AFLOW, JARVIS, Materials Cloud.
4. Move toward 100k-1M records by storing source-specific normalized metadata,
   not by pretending all records are identical QE outputs.

## Minimum Viable NOMAD Connector

The first connector should:

- query a small public sample,
- save raw JSON metadata snapshots under an ignored cache directory,
- write a normalized CSV under `data/public_records/`,
- include source fields such as `source_database`, `source_entry_id`, and
  `source_code`,
- include tests using small static JSON fixtures.

No large download should run by default. The connector must require an explicit
command-line argument such as `--limit 1000`.

