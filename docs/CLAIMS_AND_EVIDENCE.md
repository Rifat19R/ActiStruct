# Claims And Evidence

This file is the claim-to-evidence index for reviewer-facing statements. A
claim is only safe when it has an evidence file, a reproduction command, and a
limitation.

## Current Claims

| Claim | Evidence | Reproduce command | Limitation |
|---|---|---|---|
| Geometry-sensitive embedding is implemented. | `tests/test_hybrid_surrogate.py`; `actistruct/gnn/encoder.py`; `actistruct/gnn/surrogate.py` | `pytest -q tests/test_hybrid_surrogate.py` | Proves representation sensitivity and API behavior, not predictive superiority. |
| Clean Ti3C2-O slab static SCF was historically reported once. | `data/evidence/ti3c2_o_clean_slab_lf/`; `data/structures/ti3c2_o/ti3c2_o_slab_relaxed.traj` | Regenerate with `FIDELITY=low python -m examples.manual_qe.ti3c2_o_her_qe_active_inverse` after QE and pseudopotentials are configured. | Raw clean-slab QE output is not retained in the repo/current scratch; treat as a historical report until regenerated with raw-output hash and parsed result. |
| GP/LCB direct-grid and failure-aware ranking have offline evidence. | `reports/simulated_failure_aware_al_benchmark_v051.md`; `data/simulated_failure_aware_al_benchmark_v051.csv`; `tests/test_simulated_failure_aware_al_benchmark_v051.py` | `pytest -q tests/test_simulated_failure_aware_al_benchmark_v051.py` | Offline replay/stress benchmark only; not live QE evidence. |
| Failure-aware acquisition is a soft ranking penalty and falls back to LCB when risk is unavailable or gamma is zero. | `actistruct/acquisition/reliability.py`; `tests/test_failure_aware_acquisition.py` | `pytest -q tests/test_failure_aware_acquisition.py` | Confirms scoring behavior, not live DFT savings. |
| TMC Benchmark v1.0 has 16 converged QE records passing internal checks. | `data/processed/full_dataset_v0.2.csv`; `reports/tmc_benchmark_v1.0.md`; parser/validation tests | `pytest -q tests/test_qe_parser.py tests/test_dataset_validation.py tests/test_convergence_and_consistency.py` | Internal QE/parser checks; three non-ferrocene primary PDF tables still need verification before citation-grade geometry claims. |
| Ferrocene D5h -> D5d optimized conformer energy difference is 41.68 meV. | `reports/tmc_benchmark_v1.0.md`; `reports/dataset_diagnostics_v0.1.md`; `data/features/features_v0.1.csv`; `structures/neb_endpoints/` | `pytest -q tests/test_convergence_and_consistency.py tests/test_neb_endpoints.py` | This is an optimized conformer energy difference, not a computed transition-state barrier. A barrier value requires constrained rotational scan or NEB. |
| GP baseline and one-step retrospective AL oracle loop run on the 16-row TMC dataset. | `reports/baseline_model_report_v0.1.md`; `reports/active_learning_demo_v0.1.md`; `data/models/baseline_gp_v0.1.json`; `data/models/al_demo_v0.1.json` | `python scripts/12_baseline_model.py` and `python scripts/14_active_learning_demo.py` | Retrospective workflow demonstration; no predictive claim from 16 rows. |
| Live AL reduces DFT evaluations. | Not available. | Not available. | Must not be claimed until a live campaign beats baselines under a frozen protocol. |
| LF ranking transfers reliably to HF. | Not available. | Not available. | Requires representative LF/HF comparison, rank correlation, and ranking-stability report. |
| DFT adsorption-energy rankings are converged. | Not available. | Not available. | Requires convergence checks on relative adsorption energies and candidate ranking, not only total energies. |

## Safe Language

Use:

- "converged QE records passing internal checks"
- "retrospective AL workflow demonstration"
- "optimized D5h -> D5d conformer energy difference"
- "same scale as the experimental rotational barrier"
- "offline failure-aware acquisition benchmark"
- "historically reported clean-slab SCF"

Avoid unless future evidence exists:

- "live AL reduces evaluations"
- "computed ferrocene barrier"
- "predictive model"
- "production-ready DFT automation"
- "validated DFT dataset" without specifying the validation standard
- "validated clean-slab SCF" until raw QE output and checksums are regenerated
