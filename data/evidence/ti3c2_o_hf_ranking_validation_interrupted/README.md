# HF Ranking Validation — Interrupted Run Evidence

Audit date: 2026-07-31.

`examples/manual_qe/validate_lf_hf_ranking.py` (docs/FEATURE_FREEZE.md Priority 5)
was started under `FIDELITY=high` to check whether the LF campaign's ranking of
three representative Ti3C2-O sites survives at HF settings
(`ecutwfc=60, ecutrho=480, kpts=(6,6,1)` vs LF's `ecutwfc=40, ecutrho=320,
kpts=(3,3,1)`). It did not complete even the first required calculation (the
clean-slab reference energy) and was deliberately stopped. **No HF scientific
result exists.** See `docs/hf_validation_status.md` for the full closure
decision and rationale.

## What is preserved here

Raw QE input/output for all 3 clean-slab attempts (`espresso.pwi`/`.pwo`/`.err`
+ `run_metadata.json` per attempt, copied verbatim from
`/tmp/qe_scratch/ti3c2_o_her/high/clean_slab_pid120527_attempt{1,2,3}/`), plus
`driver_stdout.log` (the driver's own console output, ending in the uncaught
`RuntimeError` that terminated the process). These raw files are **not**
git-tracked (`.gitignore` excludes `*.pwi`/`*.pwo`/`*.err`/`*.log` repo-wide,
consistent with how live QE scratch is handled elsewhere in this repo) — they
remain on disk here for local inspection. This README and
`run_metadata.json` (the curated summary, not raw QE dumps) are git-tracked.

## Attempt-by-attempt facts (from the raw files, not narrative)

All 3 attempts used **identical** QE input (`espresso.pwi` is byte-identical
across all 3, sha256 `ecdd5696768eb2996d25ae8c9a4c59b021c934311a452c0d305e2e3477e59015`);
the retry loop reused the same input, not a modified one.

| Attempt | Input written | Output last written | Wall time | Progress reached | Outcome |
|---|---|---|---|---|---|
| 1 | 2026-07-31 02:36:10 | 02:36:13 | ~3 s | Died during initial charge-density setup, before SCF iteration #1 | Incomplete (no `JOB DONE`) |
| 2 | 2026-07-31 02:36:22 | 03:04:35 | ~28 min | Reached SCF iteration #30 (of `electron_maxstep=300`, `conv_thr=1e-8`); last recorded total energy `-1914.03173471 Ry`, estimated accuracy `1.61e-6 Ry` (not yet converged) | Incomplete (no `JOB DONE`) |
| 3 | 2026-07-31 03:04:46 | 03:05:13 | ~27 s | Reached SCF iteration #1 | Deliberately stopped via `SIGINT` (operator-issued, per the HF-closure/deferral decision) |

`espresso.err` is empty (0 bytes) for all 3 attempts. No `OOM-killer` or
`page allocation failure` kernel message was found in `dmesg` correlated to
this specific run window (2026-07-31 02:36-03:05); earlier `dmesg` entries
from this same WSL2 session (2026-07-25, 2026-07-26, 2026-07-29) do show
repeated `pw.x: page allocation failure: order:4, mode:GFP_NOFS` events under
long uptime / memory fragmentation, which is a plausible contributing factor
given HF's much larger per-iteration memory footprint (`~4.14 GB` estimated
per MPI rank vs LF), but this is not confirmed as the specific cause of
attempts 1-2 — reported here as an open, not a resolved, question.

After attempt 3's `SIGINT`, the driver (`get_clean_slab_energy`, 3 retries
configured) raised an uncaught `RuntimeError` and exited; no HF value for the
clean-slab reference, nor for any of the 3 target sites, was ever produced.

## Regeneration command (not run as part of this closure)

```bash
cd /mnt/d/Rifat_kh/ActiStruct-main
source .venv/bin/activate
FIDELITY=high python -m examples.manual_qe.validate_lf_hf_ranking
```
