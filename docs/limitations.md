# Limitations

- The Ti3C2-O comparison covers one system, one seed set, and one five-query
  budget per track. It cannot establish general GP, GNN, or random-search
  superiority.
- Ti3C2-O results are low-fidelity screening values. HF ranking validation was
  attempted and deferred; no HF scientific result exists.
- The `+0.04 eV` HER correction is approximate rather than a full vibrational
  free-energy treatment.
- The TMC dataset has 16 converged records. The GP/AL work is a retrospective
  demonstration, not a general predictive validation.
- Some non-ferrocene TMC reference geometry checks still require
  primary-source verification before citation-grade geometry claims.
- The v0.x reliability classifier has large split-to-split variance and is a
  soft triage signal, not a hard accept/reject rule.
- Failure-aware acquisition has offline evidence but no completed live-QE
  campaign demonstrating reduced failed-job cost.
- `run_dft_with_recovery()` covers static SCF retries; ionic-relaxation restart
  still requires explicit workflow handling.
- Raw QE scratch is usually local-only. Committed metadata and hashes must not
  be described as if all raw outputs were stored in Git.
- Pseudopotential binaries are external assets and must be verified locally.
- No experimental validation is included.

See [claim governance](claim_governance.md) for the wording permitted by
current evidence.
