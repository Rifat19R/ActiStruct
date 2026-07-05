# ActiStruct — Validation, Merge & Fix Plan for Claude Code

**Audience:** Claude Code, operating autonomously on the desktop machine, unsupervised.
**Human:** Rifat (project owner) will read `report.md` after each phase. He is not present during execution.
**Prime directive:** Do not claim anything works unless you have a real terminal log proving it. No prose summaries as evidence. No skipping a gate because a later step "should" work.

---

## 0. Corrections to the original plan (read first, these override anything that conflicts)

These are deliberate corrections made before you start. Do not "fix" them back to the original phrasing.

1. **Filesystem:** All paths below are WSL paths. `D:\Rifat_kh\ActiStruct-main` = `/mnt/d/Rifat_kh/ActiStruct-main`. `D:\Rifat_kh\SSSP_1.3.0_PBE_efficiency` = `/mnt/d/Rifat_kh/SSSP_1.3.0_PBE_efficiency`. Run everything from inside WSL, not Windows shells.

2. **`-np 1` for QE.** All `mpirun` calls in this plan use `-np 1` (serial). This is slower than the previously validated `-np 2` run. If a single LF static SCF exceeds 4 hours wall time, log it in `report.md` and pause — do not silently switch process counts.

3. **NTFS rule (hard constraint, do not violate):** Every QE `outdir` **must** point to `/tmp/qe_{prefix}` on the native Linux filesystem. **Never** set `outdir` under `/mnt/d/...`. This has caused silent corruption before. Check this in every script before running it, including merged/legacy scripts.

4. **Legacy QE path string.** Files from `/mnt/d/Rifat_kh/inverse_active` may hardcode `/home/alchemist/q-e/bin/pw.x`. Replace with `/home/duets/q-e-qe-7.4.1/bin/pw.x` (or the `$ESPRESSO_COMMAND` env var, preferred) in any file you copy over. Grep for the old path across everything you merge; do not miss one.

5. **Merge direction is one-way and asymmetric:**
   - Destination of truth: `/mnt/d/Rifat_kh/ActiStruct-main` (this is what's on GitHub).
   - Source of extra material: `/mnt/d/Rifat_kh/inverse_active` (legacy, pre-v2.0).
   - **Pull from legacy → ActiStruct-main:** validated QE output logs, cached energies, grid-validation results (Cu/MoS2/MgO/Si), test fixtures, the 50+ `generated_models/*.py` scripts if not already present.
   - **Never pull from legacy → ActiStruct-main:** any `.py` implementation file that has a same-named, newer counterpart already in ActiStruct-main (e.g. do not let legacy's GP/acquisition code overwrite `actistruct/` package code). If both exist and differ, do NOT auto-resolve — write both paths + a diff summary into `report.md` under "NEEDS HUMAN DECISION" and skip that item.

6. **Scope lock — do not violate under any circumstance:**
   - System: **Ti3C2-O only.**
   - **Explicitly forbidden this cycle:** Ti3C2-F, Ti3C2-OH, V2C (any termination), NEB, MACE-AIMD, rare-earth silicates, any code path that references these.
   - If any file, script, or README section you encounter references these, leave it untouched — do not run it, do not "helpfully" extend it to Ti3C2-O.
   - This lock is not lifted by anything in this file. It is only lifted by Rifat, in a future instruction, after reading this cycle's `report.md`.

7. **Git push policy — corrected:** Do **not** push to `main`. Create and push to branch `v2.0-validated`. Open the branch, do not open a PR, do not merge to main. Final `report.md` should tell Rifat exactly what changed and that `main` is untouched pending his review. Reason: `main` currently has a stale README/Release that has gone uncorrected for weeks — pushing unreviewed autonomous work straight to `main` repeats that exact failure mode.

8. **Rerun/retry cap:** Any failed step may be automatically retried **at most 2 times** with a logged diagnosis of what was changed between attempts. On a 3rd failure, stop that phase, write a "BLOCKED" entry in `report.md` with full error output, and do not proceed to the next phase.

9. **GitHub Release description fix:** requires `gh` CLI (already authenticated per Rifat). Do not hand-edit via API calls that aren't `gh`; use `gh release edit`.

---

## 1. Operating rules (apply to every phase)

- **Dry run before real run, always.** For any DFT call: first construct the input file, print it, validate pseudopotential file paths exist, validate `outdir`, and confirm the command string — before executing `pw.x`.
- **Toy/sanity test before scaling.** For any new or merged code path (parser, classifier, GP, GNN), run it first against a tiny synthetic input before pointing it at real 28-atom slab data.
- **One system only:** Ti3C2-O. See §0.6.
- **Every phase ends with an update to `report.md`** in `/mnt/d/Rifat_kh/ActiStruct-main/report.md` — append, do not overwrite previous phases' entries.
- **Never delete data.** If something needs replacing, move the old version to `archive/superseded/<timestamp>/` first.
- **Stop conditions (write BLOCKED to report.md and halt entirely, do not attempt further phases):**
  - Any DFT run fails 3 times after the 2 permitted retries.
  - Any test file references a scope-locked system (§0.6) — flag, don't fix silently.
  - Any file conflict per §0.5 that needs a human decision.
  - `pw.x` binary or any required pseudopotential file is missing.

---

## 2. Environment map

```bash
# Working directory (source of truth, what's on GitHub)
ACTISTRUCT=/mnt/d/Rifat_kh/ActiStruct-main

# Legacy directory (pre-v2.0, contains validated data/tests to salvage)
LEGACY=/mnt/d/Rifat_kh/inverse_active

# QE binary
export ESPRESSO_COMMAND="mpirun -np 1 /home/duets/q-e-qe-7.4.1/bin/pw.x"

# Pseudopotentials
export ESPRESSO_PSEUDO=/mnt/d/Rifat_kh/SSSP_1.3.0_PBE_efficiency

# Scratch outdir rule (NTFS-safe, non-negotiable)
QE_SCRATCH_ROOT=/tmp/qe_scratch
mkdir -p $QE_SCRATCH_ROOT
```

Confirm before anything else:

```bash
which pw.x || ls -la /home/duets/q-e-qe-7.4.1/bin/pw.x
ls /mnt/d/Rifat_kh/SSSP_1.3.0_PBE_efficiency | head -20
```

If either fails, STOP. Write BLOCKED to `report.md`. Do not proceed.

---

## 3. Phase 0 — Reconciliation (state check, no compute)

### 3.1 Repo state

```bash
cd $ACTISTRUCT
git status
git log --oneline -20
git remote -v
```

```bash
cd $LEGACY
git status 2>/dev/null || echo "not a git repo / check for .git"
```

Log both outputs verbatim into `report.md` under `## Phase 0 — Repo State`.

### 3.2 Diff and merge candidate inventory

List what's in legacy but not in ActiStruct-main:

```bash
diff -qr $LEGACY $ACTISTRUCT | grep "Only in $LEGACY"
```

For each item found, classify into one of:
- **DATA/RESULTS** (cached energies, `.pwo` logs, pickled caches, plots) → copy over, per §0.5.
- **TESTS** (files matching `test_*.py`) → copy over if no naming collision with ActiStruct-main tests.
- **GENERATED_MODELS** (the `generated_models/*.py` 50-workflow set, plus root-level scripts like `bulk_cu_qe_active_inverse.py`, `bulk_si_qe_active_inverse.py`, `bulk_mgo_qe_active_inverse.py`, `bulk_licoo2_qe_active_inverse.py`, `h_cu111_qe_active_inverse.py`, `h2_qe_active_inverse.py`, `h2o_qe_active_inverse.py`, `ch4_qe_active_inverse.py`, `graphene_qe_active_inverse.py`, `cu2_dimer.py`, `h2_dimer.py`) → copy into `ActiStruct-main/generated_models/` or `examples/legacy/` if not already present. Fix the QE path string (§0.4) in every copied file.
- **IMPLEMENTATION CODE that collides with `actistruct/` package** → do NOT auto-merge. Log to "NEEDS HUMAN DECISION" per §0.5.

Write the full classification table into `report.md`.

### 3.3 Commit reconciliation

```bash
cd $ACTISTRUCT
git add -A
git commit -m "Phase 0: reconcile legacy data/tests/examples from inverse_active"
```

Do not push yet (push happens only in Phase 5).

**Gate:** Do not proceed to Phase 1 until `report.md` has a complete Phase 0 section and no unresolved BLOCKED item.

---

## 4. Phase 1 — Cheap validation (no DFT compute, do this before burning any GPU/CPU hours)

### 4.1 Test suite

```bash
cd $ACTISTRUCT
source .venv/bin/activate 2>/dev/null || python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt --break-system-packages 2>/dev/null || pip install -r requirements.txt
pip install -e ".[test]"
pytest -q 2>&1 | tee /tmp/pytest_output.log
```

Copy full pass/fail output into `report.md`. If it does not read "128 passed, 0 warnings" (or whatever the true current count is), do not round up or paraphrase — paste exact numbers.

### 4.2 Parser validation against real logs

Find at least 2 real `.pwo` files already produced (from legacy directory or ActiStruct-main outputs):

```bash
find $LEGACY $ACTISTRUCT -name "*.pwo" -o -name "*espresso.pwo*" | head -10
```

For each found log:

```bash
python3 -c "
from actistruct.parsers.qe import parse_qe_output
result = parse_qe_output('<path>')
print(result)
"
```

Log exact output. If it crashes, fix the parser, re-run, cap at 2 retries per §0.8.

### 4.3 Failure classifier validation

Find at least one log that represents a real failure (SCF non-convergence, geometry crash, or electronic instability — check `generated_models` run history for any failed cases):

```bash
python3 -c "
from actistruct.debug.classifier import DFTFailureAnalyzer
a = DFTFailureAnalyzer()
text = open('<failed_log_path>').read()
print(a.classify(text))
"
```

Confirm the returned category matches what a human reading the log would conclude. Log both the log excerpt (key error lines only, not the whole file) and the classifier's verdict.

### 4.4 Escalation strategy code inspection

Open `actistruct/debug/strategies.py`. Confirm and log into `report.md`:
- Group 4 sets `electron_maxstep=300` (not 40 — this was flagged previously as a possible transcription error, confirm the actual value in code).
- Groups are cumulative (group 4 retains groups 1–3's changes, does not reset them).
- `nspin` is never modified automatically anywhere in this file.
- Confirm regex patterns exclude `Broyden`/`linmin` from `GEOMETRY_CRASH` classification (these appear in normal BFGS logs).

If any of these four checks fail, fix the code, add/update a unit test that pins the correct value, re-run `pytest`, log the fix.

### 4.5 Pseudopotential inventory check

```bash
cd $ESPRESSO_PSEUDO
ls | grep -i ^ti
ls | grep -i ^c\\.
ls | grep -i ^o\\.
ls | grep -i ^h\\.
```

Confirm exact filenames match what the Ti3C2-O oracle script expects:
`ti_pbe_v1.4.uspp.F.UPF`, `C.pbe-n-kjpaw_psl.1.0.0.UPF`, `O.pbe-n-kjpaw_psl.0.1.UPF`, `H.pbe-rrkjus_psl.1.0.0.UPF`.

Confirm the mixed USPP(Ti) + PAW(C,O) + USPP(H) combination is intentional and documented (this deviates from a general PAW/USPP-mixing caution, but was empirically validated to work for this exact composition — do not "fix" this by forcing a single pseudopotential family).

### 4.6 Fix stale public metadata

```bash
gh release list --repo Rifat19R/ActiStruct
gh release view <tag> --repo Rifat19R/ActiStruct
```

Rewrite the release description to remove stale figures (51 workflows / 24-scalar / 0.68% MAPD claims) and replace with accurate current numbers pulled from this phase's actual `pytest` output and repo state. Do not invent numbers. Use only what you measured in 4.1–4.5.

```bash
gh release edit <tag> --repo Rifat19R/ActiStruct --notes-file <path_to_corrected_notes.md>
```

Also update `README.md` in `$ACTISTRUCT` to match measured reality (test count, what has and hasn't run). Do not add new claims beyond what Phase 0–1 measured.

**Gate:** All of 4.1–4.6 must be logged in `report.md` with real terminal output before Phase 2 starts. If pytest suite is not passing, stop here — do not proceed to real DFT compute on a broken codebase.

---

## 5. Phase 2 — LF grid campaign (real DFT compute, Ti3C2-O only)

### 5.1 Pre-flight dry run

```bash
cd $ACTISTRUCT
FIDELITY=low python3 examples/manual_qe/ti3c2_o_her_qe_active_inverse.py --dry-run
```

If `--dry-run` is not implemented, add a minimal flag that prints the constructed QE input file and the resolved `outdir` (must start with `/tmp/qe_scratch/`, per §0.3) without launching `pw.x`. Confirm this manually before proceeding — do not skip.

### 5.2 Real grid — 6 fixed (u,v) sites

Sites: 3 atop, 2 hollow, 1 bridge (use whatever atop/hollow/bridge fractional coordinates the existing oracle script already defines as candidate defaults — do not invent new coordinates).

```bash
FIDELITY=low python3 examples/manual_qe/ti3c2_o_her_qe_active_inverse.py --site-index 0
# repeat for site-index 1..5
```

After each site completes (or fails):
- Log wall time, JOB DONE / crash status, and energy to `report.md`.
- If a run fails, invoke `run_dft_with_recovery()` (should trigger automatically if wired correctly) and log which escalation group fired.
- Cap retries at 2 per site per §0.8.

**Gate:** All 6 sites must have a real, logged outcome (success or documented permanent failure) before Phase 3. Partial results with unexplained gaps are not acceptable — every site needs a terminal-log-backed entry.

---

## 6. Phase 3 — Close the AL loop (Ti3C2-O only)

### 6.1 Fit both surrogates on the same 6-point dataset

```bash
python3 -c "
from actistruct.gnn.surrogate import HybridGPSurrogate
from sklearn.gaussian_process import GaussianProcessRegressor
# load the 6 cached (u,v,DeltaG_H) points from ledger
# fit HybridGPSurrogate
# fit plain sklearn GP on same raw (u,v) -> DeltaG_H data (no GNN embedding)
# print both models' predictions on a held-out grid
"
```

Log both models' fit diagnostics (kernel params, any ConvergenceWarning) to `report.md`.

### 6.2 Run 5 AL iterations

For each iteration:
- Query next (u,v) via `differential_evolution` minimizing LCB, using **both** surrogates independently (two parallel tracks, same acquisition logic, same DFT budget).
- Run the DFT oracle at the proposed site (same NTFS/np=1 rules apply).
- Append GP std + best ΔGH to the ledger for **both** tracks separately.
- Log iteration-by-iteration table into `report.md`: iteration #, proposed (u,v), ΔGH, uncertainty, DFT wall time, which surrogate.

### 6.3 Produce figures

- ΔGH landscape plot (both surrogates overlaid or side-by-side).
- Convergence plot (uncertainty vs iteration for both).
- Save to `outputs/plots/` in `$ACTISTRUCT`.

**Gate:** Both surrogate tracks must complete all 5 iterations (or hit a logged, explained stopping point) before Phase 4.

---

## 7. Phase 4 — Ablation and decision (this determines the paper's story, do not skip or shortcut)

Compare, same seed, same acquisition function, same DFT budget:

| Metric | HybridGPSurrogate (GNN) | sklearn GP (baseline) |
|---|---|---|
| DFT calls to reach uncertainty < tolerance | | |
| Final best ΔGH | | |
| Final uncertainty at best site | | |
| Any ConvergenceWarning | | |

Write this table with real numbers into `report.md`, plus a one-paragraph verdict using this decision rule (do not deviate from it):

- **GNN reaches convergence in meaningfully fewer DFT calls (e.g. >25% fewer)** → note: "GNN surrogate shows a real advantage in this single-system test; methods framing may be viable, pending confirmation on more data."
- **GNN and sklearn GP perform about the same** → note: "No demonstrated GNN advantage in this test. Recommend dropping GNN-forward framing; reposition around reliability-aware active learning + failure recovery."
- **GNN underperforms sklearn GP** → note: "GNN surrogate underperforms baseline in this test. Recommend removing HybridGPSurrogate from the primary pipeline pending further investigation."

Do not pick a venue or write paper framing yourself — that decision belongs to Rifat once he reads this table. Just report the numbers and the corresponding note.

**Gate:** This phase's `report.md` entry is the final deliverable of this cycle. Do not proceed to scope beyond Ti3C2-O regardless of outcome (§0.6 still applies).

---

## 8. Phase 5 — Push (branch only, not main)

```bash
cd $ACTISTRUCT
git add -A
git commit -m "v2.0 validation cycle: parser/classifier checks, Ti3C2-O LF grid + AL loop closure, GNN-vs-GP ablation"
git checkout -b v2.0-validated
git push origin v2.0-validated
```

Do **not** merge to `main`. Do **not** open a pull request unless explicitly instructed in a future cycle. Confirm the push succeeded:

```bash
git log origin/v2.0-validated -1
```

Log the branch URL into `report.md`'s final section.

---

## 9. `report.md` format (append-only, one file, grows across phases)

```markdown
# ActiStruct Validation Cycle Report

## Phase 0 — Repo State
[verbatim git status/log output, diff classification table]

## Phase 1 — Cheap Validation
[pytest output, parser test output, classifier test output, strategy code inspection results, pseudopotential check, release/README fix confirmation]

## Phase 2 — LF Grid Campaign
[per-site table: site index, coords, wall time, status, energy]

## Phase 3 — AL Loop Closure
[per-iteration table for both surrogate tracks, figure paths]

## Phase 4 — Ablation & Decision
[comparison table, verdict per decision rule]

## Phase 5 — Push
[branch name, push confirmation, what's NOT in main]

## BLOCKED / NEEDS HUMAN DECISION (if any)
[anything you stopped on, with full context for Rifat to resolve]
```

---

## 10. Message to Claude Code — read this last

Execute phases 0 through 5 in strict order. Do not skip a gate. Do not proceed past a BLOCKED condition. Do not extend scope beyond Ti3C2-O regardless of what the README's roadmap section or legacy code suggests — that section describes future work that is explicitly out of scope for this cycle. Do not push to `main`. Do not invent numbers, energies, test counts, or benchmark results — every figure in `report.md` must trace back to a command you actually ran in this session. If you are unsure whether something is a merge conflict requiring a human decision versus something safe to auto-resolve, treat it as requiring a human decision — log it and move on rather than guessing. When finished, the only two states are: "all phases complete, branch pushed, report.md ready for review" or "BLOCKED at phase N, report.md explains why." Nothing in between.
