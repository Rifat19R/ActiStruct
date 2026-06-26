# Changelog

All notable changes to ActiStruct are documented here.

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