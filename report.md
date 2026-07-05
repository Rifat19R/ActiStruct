# ActiStruct Validation Cycle Report

## Phase 0 — Repo State

### Pre-flight (§2 of plan)
```
$ wsl.exe -- bash -lc 'which pw.x || ls -la /home/duets/q-e-qe-7.4.1/bin/pw.x'
lrwxrwxrwx 1 duets duets 14 Apr 24 06:35 /home/duets/q-e-qe-7.4.1/bin/pw.x -> ../PW/src/pw.x
```
Binary present (symlink resolves into the QE 7.4.1 build tree). Required pseudopotentials for Ti3C2-O confirmed present in `/mnt/d/Rifat_kh/SSSP_1.3.0_PBE_efficiency`:
- `ti_pbe_v1.4.uspp.F.UPF` — present
- `C.pbe-n-kjpaw_psl.1.0.0.UPF` — present
- `O.pbe-n-kjpaw_psl.0.1.UPF` — present
- `H.pbe-rrkjus_psl.1.0.0.UPF` — present

No STOP condition triggered here.

### 3.1 `git status` / `git log` / `git remote -v`

**ActiStruct-main** (`/mnt/d/Rifat_kh/ActiStruct-main`):
```
On branch main
Your branch is up to date with 'origin/main'.

Untracked files:
  (use "git add <file>..." to include in what will be committed)
	ACTISTRUCT_FIX_PLAN_FOR_CLAUDE_CODE.md
	examples/manual_qe/bulk_lifepo4_qe_active_inverse_LEGACY.py

nothing added to commit but untracked files present (use "git add" to track)

origin	https://github.com/Rifat19R/ActiStruct.git (fetch)
origin	https://github.com/Rifat19R/ActiStruct.git (push)

71c285a Merge branch 'v2-dev'
7ae889a docs: clean README, pyproject, CITATION for v2.0.0
e37c9fb Merge pull request #13 from Rifat19R/v2-dev
9ca34c4 docs: update README, CHANGELOG, and version for v2.0.0
74eca07 feat: add Ti3C2-O demo script (no QE required)
710fc8a Merge pull request #12 from Rifat19R/v2-dev
157d9be feat: add Ti3C2-O HER oracle, UV sensitivity tests, GP StandardScaler fix
7a7cc17 chore: drop CaAlN2 as Phase 2 target, archive CaAlN2-specific files
1f80eeb fix: disqualify LiFePO4, add BCC Fe as recovery hook target
3f7fba0 feat: per-system multi-ledger support in dashboard + 4 new tests
```

**inverse_active (legacy)** (`/mnt/d/Rifat_kh/inverse_active`):
```
On branch main
Your branch is up to date with 'origin/main'.
nothing to commit, working tree clean

origin	git@github.com:Rifat19R/ActiStruct.git (fetch)
origin	git@github.com:Rifat19R/ActiStruct.git (push)

710fc8a Merge pull request #12 from Rifat19R/v2-dev
157d9be feat: add Ti3C2-O HER oracle, UV sensitivity tests, GP StandardScaler fix
...
```

**Correction to a stale prior assumption:** an earlier working note (9 days old) had `ActiStruct-main` flagged as a stale, non-git duplicate. That is no longer true — `ActiStruct-main` is now a real, live clone tracking `origin/main` on the same GitHub remote as `inverse_active`, and it is **ahead** of `inverse_active` (has commits `71c285a`/`7ae889a`/`e37c9fb`/`9ca34c4` — the v2.0.0 release merge — that legacy doesn't). `inverse_active`'s HEAD (`710fc8a`) is an ancestor commit of `ActiStruct-main`. So per §0.5 of the plan, `ActiStruct-main` is correctly the destination of truth; `inverse_active` is a not-yet-updated clone of the same repo, not a separate pre-v2.0 codebase.

### 3.2 Diff / merge-candidate inventory

`diff -qr` (excluding `.git`, `.venv`, `__pycache__`) between `inverse_active` and `ActiStruct-main`:

- **Files that "differ" (24 total):** all are data/config artifacts (`README.md`, `CHANGELOG.md`, `CITATION.cff`, `pyproject.toml`, `*.egg-info/*`, various `analysis/outputs/raw/*.csv`, `data/*.csv`). In every case the ActiStruct-main version is the newer one (post v2.0.0 merge) — expected, not a conflict. **Zero `actistruct/` package implementation files differ** — no same-named code collisions requiring a human decision per §0.5.
- **Files/dirs only in ActiStruct-main (2):** `ACTISTRUCT_FIX_PLAN_FOR_CLAUDE_CODE.md` (this plan doc), `demo_ti3c2_o.py` (already committed in `74eca07`). Nothing to reconcile.
- **Files/dirs only in `inverse_active` (237 raw diff lines):** classified below.

#### Classification table (§3.2 buckets)

| Category | Item(s) | Decision |
|---|---|---|
| GENERATED_MODELS | `generated_models/` dir | Present **identically named** in both repos, no diff flagged inside it → already merged, nothing to copy. |
| TESTS | — | Zero `test_*.py` files found only in legacy. Nothing to copy. |
| DATA/RESULTS — QE scratch | `outputs/qe_runs/`, `outputs/qe_runs_*` (49 subdirs, **723 MB total**, e.g. `outputs/qe_runs_h2o` alone = 341 MB, `qe_runs_ch4` = 186 MB) | **NOT copied.** Inspected a sample run dir (`outputs/qe_runs/h2_r0p620000_pid237608_attempt1`): each contains `espresso.pwi/.pwo/.err` (small, KB-scale) **plus** a `tmp/<prefix>.save/` directory with binary `wfc*.dat` / `charge-density.dat` (tens of MB per run). `ActiStruct-main/.gitignore` already has explicit rules excluding exactly this: `outputs/qe_runs*/`, `outputs/qe_runs/`, `*.pwi`, `*.pwo`, `*.err`, `*.save/`, `tmp/`. Copying this in would (a) get silently gitignored anyway, or (b) if force-added, bloat the repo with 723 MB of binary DFT scratch permanently into git history — exactly the failure mode the plan's own NTFS/scratch rule (§0.3) and "keep final reports and plots only" gitignore policy are designed to prevent. Treated as **NEEDS HUMAN DECISION**, but resolved conservatively by *not* copying, consistent with the repo's own existing `.gitignore` policy — logged here rather than silently actioned. |
| DATA/RESULTS — pickled caches | `outputs/cache/*.pkl` (36 files, 208 KB total) | **NOT copied.** `.gitignore` explicitly excludes `outputs/cache/` and `*.pkl` — these are QE energy caches the repo owner has already decided are local-only, not versioned artifacts. |
| DATA/RESULTS — local-only bookkeeping CSVs | `analysis/outputs/raw/direct_grid_validations_internal.csv`, `analysis/outputs/raw/direct_grid/bulk_fe_spin_grid.csv` | **NOT copied.** `.gitignore` names these two exact paths verbatim under "Local-only direct-grid bookkeeping" — an explicit, deliberate prior exclusion decision, not something this cycle should override. |
| Misc scratch | `notebooks/` (empty), `run_logs/` (empty), `local_artifacts/` (1.8 MB: logs, an `.xlsx`, a `.png`, two `*_supporting_results*.docx`), `ActiStruct_supporting_results.docx` (2.3 MB, repo root) | **NOT copied.** All match existing `.gitignore` patterns (`local_artifacts/`, `run_logs/`, `*.xlsx`, `*supporting_results*.docx`, `md to code.txt`, `Target mateirals for testing.png`). |
| Pseudopotential | `pseudo/H_ONCV_PBE-1.2.upf` (64 KB) | **NOT copied.** `.gitignore` excludes `pseudo/*.upf`/`pseudo/*.UPF` — pseudopotentials are treated as external assets (matches the SSSP-directory pattern used everywhere else), and this ONCV variant isn't part of the Ti3C2-O pseudopotential set (§4.5) anyway — out of scope regardless. |

**Net finding: nothing from `inverse_active` needs to be pulled into `ActiStruct-main`.** The legacy directory is a not-yet-updated clone of the same repo; every path present there and absent in ActiStruct-main is scratch/cache data that ActiStruct-main's own `.gitignore` already, deliberately, excludes. No implementation-code conflicts exist (§0.5's "never pull" case doesn't arise because nothing collides). No BLOCKED condition, no unresolved NEEDS HUMAN DECISION requiring Rifat's input before proceeding — the ambiguous cases above were resolved by deferring to the destination repo's own existing, explicit `.gitignore` policy rather than guessing.

### 3.3 Commit reconciliation

Two untracked files already physically present in `ActiStruct-main` (not from legacy — pre-existing local work) were staged and committed:
- `ACTISTRUCT_FIX_PLAN_FOR_CLAUDE_CODE.md`
- `examples/manual_qe/bulk_lifepo4_qe_active_inverse_LEGACY.py`

(commit hash logged below once created.)

Commit `54bdce9` — "Phase 0: reconcile legacy data/tests/examples from inverse_active". Local `main` is now 1 commit ahead of `origin/main`; **not pushed** (push happens only in Phase 5, to a new branch, per §7/§8).

**Gate status: PASS.** Proceeding to Phase 1.

## Phase 1 — Cheap Validation

### 4.1 Test suite

```
$ python3 -m venv .venv && source .venv/bin/activate
$ pip install -r requirements.txt -q
$ pip install -e ".[test]" -q
$ python3 -c "import actistruct; print(actistruct.__file__)"
/mnt/d/Rifat_kh/ActiStruct-main/actistruct/__init__.py

$ pytest -q
........................................................................ [ 56%]
........................................................                 [100%]
128 passed in 64.63s (0:01:04)
```
128 passed, 0 warnings — exact match to the number already claimed in README.md before this cycle.

### 4.2 Parser validation against real logs

Used the real function name found in `actistruct/parsers/qe.py` — `parse_qe_output_file(output_path, input_path=None, material_id=None)` (the plan's guessed name `parse_qe_output` doesn't exist; this is the actual API).

Ran against 2 real `.pwo` files from `inverse_active/outputs/qe_runs/`:

```
>>> parse_qe_output_file(".../h2_r0p620000_pid237608_attempt1/espresso.pwo")
QEReliabilityRecord(converged=True, job_done=True, scf_iterations=7,
  final_energy_ry=-2.30394668, energy_ev=-31.34679149982086, max_force=0.38896,
  pressure_kbar=2.31, wall_time='6.65s WALL', failure_reason=None,
  pseudo_family='PSLibrary', pseudopotentials={'H': 'H.pbe-rrkjus_psl.1.0.0.UPF'}, ...)

>>> parse_qe_output_file(".../h2_r0p774544_pid237717_attempt3/espresso.pwo")
QEReliabilityRecord(converged=False, job_done=False, scf_iterations=None,
  final_energy_ry=None, failure_reason='job_not_completed', ...)
```
Both parse correctly — no crash, no fix needed. (Note: the second log's underlying failure is an Open MPI "not enough slots" infrastructure error — `pw.x` never started — not a DFT failure; correctly reported as an incomplete job.)

### 4.3 Failure classifier validation — BUG FOUND AND FIXED

Searched for a genuine DFT-level failure (not infra) log: `grep -rl "Error in routine\|convergence NOT achieved" outputs/qe_runs*` found 180 real logs under `inverse_active/outputs/qe_runs_bulk_li2nav2po43/*` with:
```
 %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
     Error in routine check_atoms (1):
     atoms #   1 and #   2 overlap!
 %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
     stopping ...
```
A human reading this log concludes GEOMETRY_CRASH (two atoms overlapping is a structure problem, not an electronic-parameter one). `DFTFailureAnalyzer().classify(text)` returned **`UNKNOWN`** instead — the existing `GEOMETRY_CRASH` pattern only matched the string `"atoms too close"`, but real QE 7.4.1 output for this failure mode is `"atoms # N and # M overlap!"` via the `check_atoms` routine, which never occurred in the codebase's test fixtures.

Verified before fixing: `check_atoms` appears in 180 `.pwo`/`CRASH` files, none of which contain `JOB DONE` — safe to add without risking a false positive on successful runs (per the module's own calibration-note discipline).

**Fix applied** (`actistruct/debug/classifier.py`): added `check_atoms` to the `GEOMETRY_CRASH` regex alternation. Re-classified the same log → now correctly returns `GEOMETRY_CRASH`.

**Test added** (`tests/test_debugging.py`): `test_geometry_crash_atoms_overlap_check_atoms_routine`, using a fixture built from the real log text above, pinning the fix.

Re-ran full suite after the fix:
```
$ pytest -q
........................................................................ [ 55%]
.........................................................                [100%]
129 passed in 61.94s (0:01:01)
```
129 passed, 0 warnings (128 + 1 new test, no regressions).

### 4.4 Escalation strategy code inspection (`actistruct/debug/strategies.py`)

All four checks confirmed directly from source, no fix needed:
1. **Group 4 sets `electron_maxstep=300`** (line 69) — confirmed, and the code comment explicitly documents this is deliberately 300, not the 40 mentioned in an early blueprint draft (40 would be below QE's own default of 100 and make convergence *harder*).
2. **Groups are cumulative** — confirmed by code (`self._applied` dict accumulates across all `next_input()` calls; each call re-merges `base + all applied groups so far`), and by the passing `test_actions_are_cumulative_by_attempt_3` test.
3. **`nspin` is never modified anywhere in this file** — confirmed; no reference to `nspin` exists in `_GROUPS`, and the module docstring explicitly states "Do NOT touch nspin automatically."
4. **`Broyden`/`linmin` excluded from `GEOMETRY_CRASH`** — confirmed in `classifier.py`; the pattern has no such terms, and `test_success_bfgs_not_misclassified_as_geometry_crash` passes.

### 4.5 Pseudopotential inventory check

```
$ ls $ESPRESSO_PSEUDO | grep -i "^ti_\|^c\.\|^o\.\|^h\."
ti_pbe_v1.4.uspp.F.UPF
C.pbe-n-kjpaw_psl.1.0.0.UPF
O.pbe-n-kjpaw_psl.0.1.UPF
H.pbe-rrkjus_psl.1.0.0.UPF
```
Exact filenames match what the Ti3C2-O oracle script expects. Mixed USPP(Ti)+PAW(C,O)+USPP(H) family confirmed present as-is; not "fixed" to a single family, per the plan's explicit instruction not to.

### 4.6 Fix stale public metadata

**BLOCKED (partial, narrow — not a full-pipeline stop):** `gh` CLI is **not installed** in this environment (checked WSL PATH, Git Bash PATH, and Windows PATH — not found anywhere), contrary to the plan's assumption that it was "already authenticated." Per the plan's own instruction ("Do not hand-edit via API calls that aren't `gh`"), I did **not** attempt a workaround via raw GitHub API calls. **The GitHub Release description was not touched.** This needs either `gh` installed + authenticated, or Rifat editing the release manually.

README.md **was** updated (git-tracked file, doesn't need `gh`) — it turned out to already be accurate (a prior commit, `7ae889a "docs: clean README, pyproject, CITATION for v2.0.0"`, had already removed the stale 51-workflow/24-scalar/0.68% MAPD figures the plan warned about). The only stale number left was the test count, now corrected in 4 places (128 → 129) to match the measured count after the classifier fix. Added a matching `## Unreleased` entry to `CHANGELOG.md` documenting the fix.

Committed as: `fix: GEOMETRY_CRASH misclassifies real check_atoms overlap crash as UNKNOWN` (files: `actistruct/debug/classifier.py`, `tests/test_debugging.py`, `README.md`, `CHANGELOG.md`).

**Gate status: PASS, with one open item for Rifat** — GitHub Release description still needs `gh`-based editing (§0.9/§4.6), not done this cycle. Everything else in Phase 1 is complete with real, measured, passing output. Proceeding to Phase 2.
