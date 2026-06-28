# Phase 1 Summary — ActiStruct-nebwalk TMC Reliability Benchmark

**Date:** 2026-06-29
**Repo:** `D:/Research/Dr.Kulik_MIT`
**Branch:** `feature/tmc-reliability-benchmark`
**Tests:** 23/23 passed (`pytest tests/ -v`)

## Environment corrections vs. the original plan

The plan in `CLAUDE_ACTISTRUCT_TMC_PLAN.md` was written before the environment was inspected and contained several incorrect assumptions. Phase 1 inspection corrected them:

| Item | Original assumption | Verified reality |
|---|---|---|
| ActiStruct location | Inside `D:/Research/Dr.Kulik_MIT` | Editable-installed from `D:/Rifat_kh/inverse_active` (v0.7.2) into the global Windows Python 3.14.4 environment |
| Import name | `actistruct` or `inverse_active` | `actistruct` is the real importable package |
| QE binary | Assumed on PATH | Not on Windows PATH, not on WSL default PATH. Exact path: `/home/duets/q-e-qe-7.4.1/bin/pw.x` (WSL Ubuntu, user `duets`) |
| Pseudopotential directory (for QE) | `D:\Rifat_kh\SSSP_1.3.0_PBE_efficiency` | Same directory, but `pw.x` only runs under WSL, so it must be addressed as `/mnt/d/Rifat_kh/SSSP_1.3.0_PBE_efficiency` |
| Ni/Cr pseudopotentials | Assumed consistent with Fe/C/H/O | Exist, but use a different naming convention (`ni_pbe_v1.4.uspp.F.UPF`, `cr_pbe_v1.5.uspp.F.UPF` vs. the `_psl.` SSSP-efficiency pattern) — flagged `needs_manual_review` |

## What was built (scripts 00–04, 06)

1. **`scripts/00_inspect_environment.py`** — confirms `actistruct` import, `pw.x` reachability via WSL, and pseudopotential coverage. Writes `reports/tables/environment_report.json`.
2. **`scripts/01_bootstrap_project.py`** — idempotent, backup-safe directory/README scaffold creation.
3. **`scripts/02_scan_pseudos.py`** — scans the pseudopotential directory, writes `configs/pseudo_manifest_required.yaml` (status: `ready`, with `naming_convention_warnings` for Ni/Cr).
4. **`scripts/03_collect_reference_stub.py`** — writes `references/reference_values_tmc_v0.yaml`, all 4 systems `status: needs_manual_review`, zero fabricated values, no web/API fetching performed.
5. **`scripts/04_build_initial_structures.py`** — builds 4 initial XYZ geometries (ferrocene D5h, Ni(CO)4 Td, Cr(CO)6 Oh, Fe(CO)5 D3h) from symmetry + literature-typical bond lengths, explicitly labeled as initial guesses, not reference geometries.
6. **`scripts/06_build_qe_inputs.py`** — builds QE relax `.in` files for all 4 systems directly from the initial structures, with Windows→WSL path translation for `pseudo_dir`/`outdir`. `ni_co4_initial.in` was smoke-tested against the real `pw.x` v7.4.1 binary: parsed cleanly, pseudopotentials loaded, SCF setup began with no errors (killed after 60s — input validity confirmed, not a full relax).

## Deliberately deferred

- **`scripts/05_generate_perturbation_candidates.py`** — perturbation/active-learning candidates around the initial guesses. Deferred until a first QE relax establishes a baseline PES point per system.
- **`scripts/07`–`15`** (parser, dataset validation, ML baseline, uncertainty, acquisition, reference comparison, report, nebwalk demo) — all require real QE relax outputs that don't exist yet.

## Next action

Rifat runs the 4 relax jobs via WSL `pw.x` using the inputs in `qe/inputs/relax/` (paths already WSL-translated). Once outputs land in `qe/outputs/relax/`, build `scripts/07_parse_qe_outputs.py` against real data — per the project's active-learning philosophy, ML/uncertainty/acquisition scaffolding should not be built ahead of having labeled QE rows to validate against.
