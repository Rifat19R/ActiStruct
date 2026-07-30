# HF Validation Status

Status: **deferred**, as of 2026-07-31. This is a project-closure decision,
not a bug report -- it documents why HF validation (docs/FEATURE_FREEZE.md
Priority 5) is being closed out as future work rather than pursued further
right now.

## Summary

HF validation was deferred after a controlled partial run because its
computational cost was disproportionate to the current project-closure
objective. No incomplete HF result is used in the scientific conclusions.

## What was attempted

`examples/manual_qe/validate_lf_hf_ranking.py` was run under `FIDELITY=high`
(`ecutwfc=60, ecutrho=480, kpts=(6,6,1)`, vs LF's `ecutwfc=40, ecutrho=320,
kpts=(3,3,1)`) to check whether HF preserves the LF campaign's ranking on 3
representative sites. It requires the HF clean-slab reference energy first;
that alone was retried 3 times (the driver's configured retry cap) and did
not complete on any attempt -- 1 died before the first SCF iteration (~3 s),
1 reached SCF iteration 30 of 300 without converging (~28 min) then stopped,
and the 3rd was deliberately interrupted (`SIGINT`, clean exit, no
`SIGTERM`/`SIGKILL` needed) as part of this closure decision. Full
attempt-by-attempt evidence, including raw QE input/output and a root-cause
investigation that did **not** find a definitive single cause, is preserved
at `data/evidence/ti3c2_o_hf_ranking_validation_interrupted/` (see that
directory's `README.md` and `run_metadata.json`).

## Why this is being deferred, not retried again right now

- HF settings cost substantially more per calculation than LF (larger cutoffs,
  denser k-point grid), and the clean-slab reference alone did not complete
  in 3 attempts.
- A real, not-yet-fully-diagnosed reliability issue exists in this WSL2
  environment under long uptime (kernel `page allocation failure` events were
  observed on this same machine on 2026-07-25, 2026-07-26, and 2026-07-29,
  though none was captured correlated to this specific attempt window).
  Continuing to retry at HF cost without first resolving that infrastructure
  issue is not a good use of compute for a project-closure task.
- The completed LF campaign (`docs/TI3C2O_LF_CAMPAIGN_RESULTS.md`) already
  provides a real, fully-evidenced result. HF validation would strengthen
  confidence in the LF ranking but is not required to honestly report what
  the LF campaign found.

## What this means for claims

- **No completed HF scientific result exists.** No `DeltaG_H` value at HF
  settings, for the clean slab or any of the 3 target sites, was ever
  produced.
- **Partial HF data (the incomplete clean-slab attempts above) must not be
  used in any scientific claim or comparison.** They are preserved only as
  process evidence of what was attempted and why it was stopped.
- **HF validation remains future work.** `docs/FEATURE_FREEZE.md` Priority 5
  and its corresponding Exit Criterion stay unchecked; `docs/CLAIMS_AND_EVIDENCE.md`
  continues to list "LF ranking transfers reliably to HF" as "Not available."
- **The completed LF campaign is the validated result currently supported by
  evidence.** See `docs/TI3C2O_LF_CAMPAIGN_RESULTS.md` for the full,
  evidenced LF result and its own honestly-scoped limitations.

## Resuming this work later

Prerequisites before re-attempting HF validation:

1. Resolve or work around the WSL2 memory-fragmentation reliability issue
   (options: increase `.wslconfig` memory/reduce fragmentation via a fresh
   WSL restart before the run, or move HF calculations to a machine/cluster
   not subject to this constraint).
2. Re-run `FIDELITY=high python -m examples.manual_qe.validate_lf_hf_ranking`
   from a clean state (the 3 preserved attempts above do not need to be
   reproduced first; they document the interruption, not a required
   baseline).
