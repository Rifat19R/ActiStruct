# Feature Freeze

Status: active as of 2026-07-16.

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
3. Run the live LF campaign.
4. Compare against simple baselines.
5. Validate LF against HF on representative sites.
6. Release the reproducibility package.
7. Contact Prof. Kulik with the reviewer-safe package.

## Exit Criteria

The freeze can be relaxed only after the repository contains:

- a frozen benchmark protocol
- a completed live LF campaign ledger
- baseline comparisons under the same data budget
- LF/HF ranking validation on representative sites
- raw data hashes or stable output references
- a public technical report linking every major claim to evidence
