# Changelog

All notable changes to ActiStruct are documented here.

## v2.0.0 - 2026-07-04

### Added

- **GNN encoder** (`actistruct/gnn/encoder.py`): SchNet-style geometry-aware
  message passing with neighbor list, Gaussian RBF expansion, and mean-pool
  aggregation. Produces distinct embeddings for identical-composition structures
  with different bond lengths (verified by test).
- **HybridGPSurrogate** (`actistruct/gnn/surrogate.py`): Frozen-embedding
  transfer learning. Pretrain encoder on LF energies, freeze weights, fit a
  GP (`ConstantKernel * RBF`, `alpha=1e-4`) on HF embeddings after
  `StandardScaler`. Drop-in for the existing `GPModel` interface.
- **Debug and recovery engine** (`actistruct/debug/`): `DFTFailureAnalyzer`
  (regex classifier, 4 failure types), `TroubleshootingStrategy` (4 cumulative
  escalation groups), `run_dft_with_recovery()` (wraps static SCF with
  automatic fault detection and ledger logging).
- **Append-only JSONL ledger** (`actistruct/core/ledger.py`): NTFS-safe
  atomic writes using `O_CREAT | O_EXCL`; one record per DFT attempt.
- **NTFS-safe atomic cache** (`actistruct/core/atomic_cache.py`).
- **Streamlit dashboard** (`actistruct/dashboard/`): 4-tab campaign monitor
  (scorecard, energy landscape, 3D structure viewer, full run log). Multi-ledger
  support; handles empty ledger gracefully.
- **Ti3C2-O HER oracle** (`examples/manual_qe/ti3c2_o_her_qe_active_inverse.py`):
  `DeltaG_H = E_slab+H - E_slab - 0.5*E_H2 + 0.04 eV`; `FIDELITY` env var
  switches LF (ecutwfc=40) vs HF (ecutwfc=60); full caching per fidelity level.
  SSSP 1.3.0 PBE efficiency pseudos. LF static verified: -25973.017 eV, JOB DONE.
- **Ti3C2-O demo** (`demo_ti3c2_o.py`): no-QE end-to-end demo exercising all
  4 phases on the real 28-atom slab geometry.
- **UV design variable sensitivity tests** (`tests/test_hybrid_surrogate.py`):
  3 new tests confirming (u,v) fractional-coordinate design variable produces
  distinct embeddings across atop/hollow/bridge adsorption sites.

### Changed

- `HybridGPSurrogate`: replaced `WhiteKernel` with fixed `alpha=1e-4`;
  added `StandardScaler` before GP fit to eliminate `ConvergenceWarning`.
- `GNNConfig`: added per-system cutoff guidance; Ti3C2-O default 5.0 A.
- `generated_models/bulk_lifepo4_qe_active_inverse.py`: updated pseudo-mixing
  comment to per-combination verification rule.
- Package version bumped from 0.7.2 to 2.0.0.

### Notes

- Test suite: **128 passed, 0 warnings** (Python 3.12, WSL2).
- HF ionic relaxation for Ti3C2-O slab deferred: OOM at ecutwfc=60 on WSL2
  default 3.7 GB RAM; requires `.wslconfig memory=6GB` or a compute cluster.
- All source files: ASCII-only (no Unicode in comments, docstrings, or output).

## v0.7.2 - 2026-06-27

### Added

- Added a QE-free dry-run candidate selector for future live QE/PBE
  validation planning.
- Generates schema-valid, review-only candidate rows in
  `data/dry_run_live_candidates_v072.csv`.
- Adds `reports/dry_run_live_candidate_selector_v072.md` and tests for
  no-QE/no-live-validation behavior.
- Marks prediction, uncertainty, failure-risk, and acquisition fields as
  `not_computed` where no validated model score is available.

### Notes

- Does not run QE/PBE, create executable QE inputs, reuse historical
  completed records, or claim live DFT savings. See
  `docs/releases/v0.7.2.md` for the full release note and safe claim.
- Test suite: `81 passed`.

## v0.5.1 - 2026-06-27

### Added

- Repeated-trial (50 trials) offline stress benchmark for failure-aware
  GP/LCB acquisition across four candidate-pool modes. No QE/DFT jobs were
  run. See `docs/releases/v0.5.1.md` for the full release note and
  `reports/actistruct_status_v051.md` for the broader project status.

### Notes

- Results support failure risk as a soft DFT triage signal, not a guarantee
  of live DFT savings. See the release note for the conservative safe claim
  and known limitations.

## 0.1.0 - 2026-06-15

### Added

- Initial ActiStruct repository packaging.
- Shared QE active-learning inverse-design engine.
- 50 generated benchmark workflows for solids, molecules, 2D materials, battery materials, and adsorption systems.
- Completed report archive under `outputs/reports/`.
- Completed plot archive under `outputs/plots/`.
- JCTC-style results draft summarizing benchmark outputs.
- CIF-derived NaCoO2, LiCoO2, and LiTiO2 structure builders.
- Professional repository metadata: README, pyproject, citation, security policy, gitattributes, and gitignore.

### Notes

- Raw Quantum ESPRESSO scratch directories are excluded from version control by default.
- Pseudopotential binaries are external assets and are not committed.