# Feature Freeze

Status: active as of 2026-07-16. Updated 2026-07-31: the live LF campaign
(Priority 3) and baseline comparison (Priority 4) below are now complete --
see `docs/TI3C2O_LF_CAMPAIGN_RESULTS.md`. Priority 5 (HF validation) was
attempted and then deliberately **deferred** as a project-closure decision --
see `docs/hf_validation_status.md` for what was attempted and why. The freeze
itself is **not** lifted: the Exit Criteria below are not all satisfied, and
Priority 7 (outreach) remains explicitly out of scope. See "Declaration of
Done" below for the current honest status.

## Rule

ActiStruct is in a scientific-evidence freeze. Do not add major new features,
dashboards, model families, or broad UI/API surfaces until the live low-fidelity
campaign evidence exists.

Allowed work during the freeze:

- campaign reliability fixes
- reproducibility fixes
- missing tests for existing behavior
- documentation corrections
- scientific wording corrections
- benchmark protocol and evidence documentation
- bug fixes needed to run the live LF campaign

Not allowed during the freeze:

- new model architectures beyond the existing direct GP, descriptor GP, and
  frozen SchNet + GP comparisons
- new dashboard sections unrelated to campaign evidence
- new public claims not tied to an evidence file and reproduction command
- rewriting benchmark protocol after seeing live results without an explicit
  dated amendment

## Current Priority Order

1. Correct scientific wording.
2. Freeze new feature development.
3. ~~Run the live LF campaign.~~ **Done** -- `docs/TI3C2O_LF_CAMPAIGN_RESULTS.md`.
4. ~~Compare against simple baselines.~~ **Done** -- random baseline and plain GP both compared under the same 5-iteration budget as the GNN track.
5. Validate LF against HF on representative sites. **Deferred** -- attempted and stopped after a controlled partial run; see `docs/hf_validation_status.md`.
6. Release the reproducibility package.
7. Contact Prof. Kulik with the reviewer-safe package.

## Exit Criteria

The freeze can be relaxed only after the repository contains:

- [x] a frozen benchmark protocol (`docs/BENCHMARK_PROTOCOL.md`)
- [x] a completed live LF campaign ledger (`outputs/campaigns/ti3c2_o_lf_campaign.jsonl`, `outputs/campaigns/ti3c2_o_lf_campaign_plain_gp_rerun_amend5.jsonl`)
- [x] baseline comparisons under the same data budget (`docs/TI3C2O_LF_CAMPAIGN_RESULTS.md`)
- [ ] LF/HF ranking validation on representative sites -- **not done, deferred, see `docs/hf_validation_status.md`**
- [x] raw data hashes or stable output references (`campaign_fingerprint()`: slab sha256, pseudopotential sha256, commit)
- [ ] a public technical report linking every major claim to evidence -- `docs/claim_governance.md` covers this internally; no separate public-facing report has been drafted

Not all criteria are met. **Do not treat the freeze as lifted or the
Ti3C2-O work as ready for outreach (Priority 7) until Priority 5 and the
two open Exit Criteria above are resolved.**

## Declaration of Done (2026-07-31 project closure)

Honest status at project closure, stated plainly:

- **Done, with evidence:** the LF active-learning campaign for H adsorption
  on Ti3C2-O -- structure regeneration and relaxation, the full 3-track
  campaign, the plain-GP kernel bug found and fixed with a verified re-run,
  and all of it written up in `docs/TI3C2O_LF_CAMPAIGN_RESULTS.md` with raw
  evidence committed, not just summarized.
- **Deferred, not done:** HF validation (Priority 5). Attempted, did not
  complete even the clean-slab reference in 3 attempts, deliberately stopped
  rather than continuing to spend compute against an unresolved WSL2
  reliability issue. See `docs/hf_validation_status.md`. No HF result exists
  and none is used in any claim.
- **Explicitly not in scope for this closure:** Priority 6 (reproducibility
  package release) and Priority 7 (contacting Prof. Kulik) are **not**
  attempted here. Priority 7 in particular remains blocked on Priority 5 per
  this document's own rule above, and outreach preparation was intentionally
  excluded from this closure's scope.
- **Net effect:** this closure finalizes and documents the LF result as the
  validated, evidenced result of this project phase. It does not lift the
  freeze, does not claim HF validation, and does not prepare or imply
  readiness for outreach.
