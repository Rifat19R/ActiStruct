# HF Validation Status

Status: **attempted and deferred**, as of 2026-07-31. This is a
project-closure decision, not a completed scientific result.

## Summary

HF validation was deferred after a controlled partial run because its
computational cost was disproportionate to the closure objective and the
required clean-slab reference did not complete. No incomplete HF value is used
in the scientific conclusions.

## What was attempted

`examples/manual_qe/validate_lf_hf_ranking.py` was run under `FIDELITY=high`
(`ecutwfc=60`, `ecutrho=480`, `kpts=(6,6,1)`) to check whether HF preserves
the LF campaign ranking on three representative sites. The driver first
requires an HF clean-slab reference.

That reference did not complete in three attempts:

1. one attempt stopped before the first SCF iteration;
2. one reached SCF iteration 30 of 300 without convergence and then stopped;
3. one was deliberately interrupted with `SIGINT` during the closure
   decision.

Attempt-by-attempt curated metadata and a root-cause investigation that did
not identify a definitive single cause are committed at
`data/evidence/ti3c2_o_hf_ranking_validation_interrupted/`. Raw QE scratch
(`espresso.pwi`, `espresso.pwo`, and `espresso.err`) remains local-only under
the repository's established gitignore convention and is not claimed as
committed evidence.

## Why the work was deferred

- HF settings use larger cutoffs and a denser k-point grid than LF settings.
- The clean-slab reference alone exhausted the driver's three-attempt cap.
- The recorded WSL2 environment had a plausible but unconfirmed
  memory-reliability problem under long uptime.
- Further retries without resolving the infrastructure issue would spend
  substantial compute without a sound validation plan.

The completed LF campaign already supports a carefully scoped LF result. HF
validation would strengthen confidence in ranking transfer, but it is not
required to report what the LF campaign observed.

## Claim boundary

- No completed HF clean-slab or adsorption-site value exists.
- Partial/incomplete HF output must not be used in a scientific comparison.
- LF-to-HF rank correlation and ranking stability are unknown.
- `docs/claim_governance.md` therefore lists HF ranking transfer as
  unavailable.
- `docs/FEATURE_FREEZE.md` keeps the corresponding exit criterion open.

## Prerequisites before resuming

1. Resolve or avoid the recorded WSL2 reliability constraint, or move the
   work to suitable cluster hardware.
2. Review memory, MPI, scratch, QE, and pseudopotential configuration.
3. Run the clean-slab HF reference from a clean state.
4. Only after the reference completes, evaluate the pre-specified
   representative sites and report rank stability.

The future command would be:

```bash
FIDELITY=high python -m examples.manual_qe.validate_lf_hf_ranking
```

It is intentionally not part of installation, CI, or fast reproducibility
checks.
