# Repository audit: MALOQ and ActiStruct

Audit date: 2026-07-31

## Verified starting point

- Cleanup base: `origin/main` at `60a570ef5999244d5ebed34e9c1d1c864a012019`.
- PR #25 was merged, so the cleanup branch starts from the completed LF
  campaign and deferred HF record rather than the older local checkout.
- Baseline: `433 passed` in 45.60 s under the configured warning policy.
- MALOQ inspected read-only at
  `408c57291fece330307e236b90718af7c9c4127b`.

## MALOQ patterns worth adapting

- A compact root with one obvious project identity.
- A short README with a logo, one-sentence purpose, supported applications,
  and citation information.
- Clear separation of package code, examples, scripts, tests, and images.
- Central package metadata and dependencies in `pyproject.toml`.
- A conventional `src/` package and a narrow, real CLI.
- Small, recognizable public entry points rather than development notes in
  the root.

## MALOQ patterns not worth copying

- Its README does not provide installation, first-run, limitations, or
  benchmark-provenance instructions.
- Its CI performs an import smoke test but does not run the repository tests.
- Its conda environment targets Python 3.12 while CI targets only 3.14, and
  CI reconstructs a large dependency set outside `pyproject.toml`.
- Dataset setup includes unresolved documentation caveats.
- Citation is embedded in README rather than accompanied by `CITATION.cff`.

ActiStruct should adopt MALOQ's visual and structural economy while retaining
its stronger tests, evidence mapping, failure records, reproducibility
metadata, and explicit limitations.

## Current ActiStruct organization problems

- The 532-line README mixes identity, API notes, benchmark reports, setup,
  roadmap, and historical release detail; it also contains a stale
  `424 passing` statement.
- Root-level demo, manual integration check, manuscript, bibliography, and
  launcher obscure the package and project metadata.
- Code, benchmark drivers, campaign evidence, historical analysis, and
  generated reports are recognizable only to an existing contributor.
- Documentation overlaps across the README, versioned quickstarts,
  `model_and_tests.md`, release reports, and phase summaries.
- `requirements.txt` duplicates `pyproject.toml` and adds dashboard packages
  without explaining its role; the NumPy constraint also disagrees.
- Scientific evidence is well preserved but lacks a short benchmark index and
  a machine-checkable public integrity manifest.
- The current package uses both `actistruct/` and an installed top-level
  `qe_active_inverse_common.py`; generated workflows depend on that layout.

## Target structure

```text
ActiStruct/
|-- .github/                 # CI and contributor templates
|-- assets/                  # restrained identity and workflow diagram
|-- actistruct/              # installed library (kept in place)
|-- benchmarks/              # TMC and Ti3C2-O reviewer entry points
|-- data/                    # immutable/reference/processed evidence
|-- docs/                    # one current document per public topic
|   |-- development/history/ # superseded plans and phase records
|   `-- repository_audit/
|-- examples/                # quickstart, integration, and live-QE workflows
|-- reproducibility/         # tiered reproduction guide and evidence manifest
|-- scripts/                 # benchmark, analysis, and maintenance drivers
|-- tests/                   # no-QE suite and repository-integrity checks
|-- qe/, runs/, structures/  # retained TMC inputs and evidence
|-- reports/, outputs/       # retained reports and curated campaign logs
|-- qe_active_inverse_common.py  # installed legacy engine; migration deferred
`-- standard project metadata
```

## File migration map

| Current path | Target path or action | Reason |
|---|---|---|
| `demo_ti3c2_o.py` | `examples/quickstart/no_qe_ti3c2o.py` | Public no-QE example, not root metadata. |
| `test_all_integrations.py` | `examples/integration/full_stack_check.py` | Manual check may invoke QE and must not look like a normal test. |
| `paper.md`, `paper.bib` | `docs/manuscript/` | Manuscript source belongs with documentation. |
| `run.sh` | `scripts/run_generated_models.sh` | Legacy live-QE suite launcher belongs with scripts. |
| `docs/PHASE1_SUMMARY.md` | `docs/development/history/tmc_phase1.md` | Dated implementation record. |
| `docs/PHASE2_SUMMARY.md` | `docs/development/history/tmc_phase2.md` | Dated implementation record. |
| `docs/model_and_tests.md` | `docs/development/history/model_and_tests_v0.md` | Superseded by current architecture and reproducibility docs. |
| `docs/repository_guide.md` | `docs/development/history/repository_guide_v0.md` | Contains obsolete first-commit and pre-arXiv instructions. |
| `docs/CLAIMS_AND_EVIDENCE.md` | `docs/claim_governance.md` | Canonical, consistently named claim index. |
| `docs/HF_VALIDATION_STATUS.md` | retain | Stable deferred-HF record referenced by preserved evidence. |
| `docs/BENCHMARK_PROTOCOL.md` | retain | Frozen, amended protocol; path churn offers no scientific benefit. |
| `docs/TI3C2O_LF_CAMPAIGN_RESULTS.md` | retain | Cited scientific record; benchmark index will point to it. |
| `qe_active_inverse_common.py` | retain at root | Installed module used by generated workflows and tests. |
| `generated_models/` | retain, document as legacy workflow collection | Moving 50 live-QE wrappers would create broad import/command churn. |
| `analysis/`, `reports/`, `outputs/` | retain, add indexes | Paths are embedded in reports, tests, and provenance records. |
| `data/evidence/`, `outputs/campaigns/`, `qe/`, `runs/` | retain exactly | Scientific evidence; no visual cleanup justifies moving it. |

## Scientific migration risks

| Area | Risk if moved | Decision |
|---|---|---|
| Campaign JSONL | Breaks append-only provenance, hashes, and citations. | Do not move or rename. |
| HF interruption metadata | Could imply incomplete output is a result or sever attempt context. | Do not move; describe as process evidence only. |
| TMC QE inputs/outputs and run trees | Breaks parser trace paths and validation tests. | Do not move. |
| Structures and pseudopotential manifest | Breaks checksums and reproduction commands. | Do not move. |
| Frozen protocol and amendments | Risks hiding post-result changes. | Retain one dated document at its current path. |
| Generated QE workflows | Root-relative import and launcher dependencies. | Retain; document separately from library code. |
| Package to `src/` | High import, editable-install, script, and package-data risk. | Defer to a dedicated refactor; no half-migration. |

No scientific evidence directory is scheduled to move. The cleanup will add
an evidence-path/hash manifest and tests without rewriting any evidence.
