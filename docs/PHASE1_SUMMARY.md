# Phase 1 Summary — ActiStruct-nebwalk TMC Reliability Benchmark

**Date:** 2026-06-29
**Repo:** `D:/Research/Dr.Kulik_MIT`
**Branch:** `feature/tmc-reliability-benchmark`
**Tests:** 28/28 passed (`pytest tests/ -v`)
**Real QE run status:** ferrocene relax confirmed running cleanly (several SCF iterations, energy converging) after fixing an OOM caused by oversized vacuum padding — see "First real relax attempt" below.

## Environment corrections vs. the original plan

The plan in `CLAUDE_ACTISTRUCT_TMC_PLAN.md` was written before the environment was inspected and contained several incorrect assumptions. Phase 1 inspection corrected them:

| Item | Original assumption | Verified reality |
|---|---|---|
| ActiStruct location | Inside `D:/Research/Dr.Kulik_MIT` | Editable-installed from `D:/Rifat_kh/inverse_active` (v0.7.2) into the global Windows Python 3.14.4 environment |
| Import name | `actistruct` or `inverse_active` | `actistruct` is the real importable package |
| QE binary | Assumed on PATH | Not on Windows PATH, not on WSL default PATH. Exact path: `/home/duets/q-e-qe-7.4.1/bin/pw.x` (WSL Ubuntu, user `duets`) |
| Pseudopotential directory (for QE) | `D:\Rifat_kh\SSSP_1.3.0_PBE_efficiency` | Same directory, but `pw.x` only runs under WSL, so it must be addressed as `/mnt/d/Rifat_kh/SSSP_1.3.0_PBE_efficiency` |
| Ni/Cr pseudopotentials | Assumed consistent with Fe/C/H/O | Exist, but use a different naming convention (`ni_pbe_v1.4.uspp.F.UPF`, `cr_pbe_v1.5.uspp.F.UPF` vs. the `_psl.` SSSP-efficiency pattern) — flagged `needs_manual_review` |

## What was built (scripts 00–06)

1. **`scripts/00_inspect_environment.py`** — confirms `actistruct` import, `pw.x` reachability via WSL, and pseudopotential coverage. Writes `reports/tables/environment_report.json`.
2. **`scripts/01_bootstrap_project.py`** — idempotent, backup-safe directory/README scaffold creation.
3. **`scripts/02_scan_pseudos.py`** — scans the pseudopotential directory, writes `configs/pseudo_manifest_required.yaml` (status: `ready`, with `naming_convention_warnings` for Ni/Cr).
4. **`scripts/03_collect_reference_stub.py`** — writes `references/reference_values_tmc_v0.yaml`, all 4 systems `status: needs_manual_review`, zero fabricated values, no web/API fetching performed.
5. **`scripts/04_build_initial_structures.py`** — builds 4 initial XYZ geometries (ferrocene D5h, Ni(CO)4 Td, Cr(CO)6 Oh, Fe(CO)5 D3h) from symmetry + literature-typical bond lengths, explicitly labeled as initial guesses, not reference geometries.
5. **`scripts/05_generate_perturbation_candidates.py`** — one-at-a-time local perturbations of each complex's defining geometric variables (e.g. ferrocene's Fe-Cp distance, Cp ring rotation, ring radius; Fe(CO)5's axial/equatorial Fe-C distances, equatorial angle, and a heuristic Berry-pseudorotation-like tilt coordinate — explicitly labeled as a simplified local coordinate, not a validated reaction path). 12–16 candidates per complex (52 total), written to `structures/generated_candidates/` with `data/raw/candidate_manifest_v0.csv`. Reuses the parameterized builders from script 04 (refactored to accept optional perturbation kwargs, defaults unchanged from phase 1 baseline — confirmed byte-identical initial-structure output before/after the refactor).
6. **`scripts/06_build_qe_inputs.py`** — builds QE relax `.in` files for all 4 primary systems directly from the initial structures, with Windows→WSL path translation for `pseudo_dir`/`outdir`. `ni_co4_initial.in` was smoke-tested against the real `pw.x` v7.4.1 binary: parsed cleanly, pseudopotentials loaded, SCF setup began with no errors (killed after 60s — input validity confirmed, not a full relax).

## Deliberately deferred

- **`scripts/07`–`15`** (parser, dataset validation, ML baseline, uncertainty, acquisition, reference comparison, report, nebwalk demo) — all require real QE relax outputs that don't exist yet.

## First real relax attempt (2026-06-29)

Rifat ran `pw.x` on `ferrocene_initial.in` via WSL and hit `MPI_ABORT` (rank 1, errorcode 1). Two separate issues found and fixed in sequence:

1. **Wrong input path used initially** (`qe_inputs/initial_relax/ferrocene.in`, which never existed) - the actual generated path is `qe/inputs/relax/ferrocene_initial.in`. Confirmed via the `CRASH` file QE wrote: `from read_input : error #1, opening input file`.
2. **After fixing the path, the job ran but got OOM-killed** (and briefly destabilized the WSL VM). QE's own estimate: `Estimated total dynamical RAM > 54.79 GB` for a 2-process run, against 16 GB WSL RAM + 20 GB swap on a 32 GB host. Root cause: `vacuum_padding_angstrom: 12.0` (per side) inflated the cubic cell to ~28.3 A/side for a ~4.5 A molecule, driving a 375^3 dense FFT grid. Fixed by reducing to `6.0` (still standard for the `assume_isolated='mt'` correction) - new cell ~16.3 A/side, re-verified with a real `pw.x` run that reached `Estimated max dynamical RAM per process > 10.50 GB` and progressed cleanly through several SCF iterations (energy -525.36 -> -524.93 Ry, estimated accuracy 2.04 -> 0.88 Ry) with no memory error.

All 4 `qe/inputs/relax/*.in` files were regenerated with the corrected padding.

## Next action

Rifat runs the 4 relax jobs via WSL `pw.x` using the inputs in `qe/inputs/relax/` (paths already WSL-translated). Once outputs land in `qe/outputs/relax/`, build `scripts/07_parse_qe_outputs.py` against real data — per the project's active-learning philosophy, ML/uncertainty/acquisition scaffolding should not be built ahead of having labeled QE rows to validate against.
