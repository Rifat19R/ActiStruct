# Reliability-Aware Quickstart for ActiStruct v0.6.3

## 1. What This Quickstart Does

Walks a new user through installing ActiStruct, running the test suite, and
reproducing the v0.5.1 repeated-trial offline stress benchmark for
failure-aware GP/LCB acquisition — entirely without Quantum ESPRESSO or any
other DFT code.

## 2. What This Quickstart Does Not Do

- This quickstart does not run QE/PBE.
- This quickstart does not validate new materials.
- This quickstart does not prove live DFT savings.
- The benchmark is offline and uses completed records.
- Failure-aware ranking is a soft penalty, not a hard rejection rule.

## 3. Installation Commands

```bash
cd <ACTISTRUCT_ROOT>
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e ".[test]"
```

## 4. Test Command

```bash
pytest -q
```

Expected: `74 passed` (see `docs/model_and_tests.md` for what each test file
covers, including `tests/test_reliability_aware_quickstart.py`). No QE/DFT
is launched by any test in the suite.

## 5. Run the v0.5.1 Stress Benchmark

```bash
python analysis/simulated_failure_aware_al_benchmark_v051.py
```

This is deterministic (fixed random seeds) and does not launch QE/DFT. It
(re)writes two files:

```text
data/simulated_failure_aware_al_benchmark_v051.csv
reports/simulated_failure_aware_al_benchmark_v051.md
```

Running it again produces byte-identical output. If you see only
line-ending (CRLF/LF) noise in `git diff` after running it — common on
Windows/WSL — see the Troubleshooting section before committing anything.

## 6. Files Generated or Read

| File | What it is |
| --- | --- |
| `analysis/simulated_failure_aware_al_benchmark_v051.py` | The script that builds candidate pools, ranks them under five policies, and writes the CSV/report below. Reads completed records via `analysis/simulated_failure_aware_al_benchmark_v05.py`'s loader; launches no QE/DFT. |
| `data/simulated_failure_aware_al_benchmark_v051.csv` | Per-trial, per-policy, per-pool-mode, per-top-k results (3,000 rows: 50 trials × 4 pool modes × 5 policies × 3 top-k values). |
| `reports/simulated_failure_aware_al_benchmark_v051.md` | Human-readable summary of the CSV: aggregate tables, interpretation, scientific caveats, and the safe-claim sentence. |
| `reports/actistruct_technical_report_v06.md` | The full v0.6 technical report consolidating evidence from v0.1 through v0.5.1, including the validated-vs-offline-only distinction. |
| `reports/actistruct_status_v051.md` | A concise post-v0.5.1 project-status handoff note. |
| `examples/reliability_aware_quickstart.py` | Optional helper: reads the CSV above (read-only, no QE/DFT) and prints the same kind of summary shown in Section 7, plus the safe-claim caveat. Run with `python examples/reliability_aware_quickstart.py`. |

## 7. How to Inspect the CSV

`pandas` is **not** a declared dependency of this repository, so this
quickstart uses the Python standard library only:

```bash
python - <<'PY'
import csv
from collections import defaultdict

path = "data/simulated_failure_aware_al_benchmark_v051.csv"
with open(path, newline="") as f:
    rows = list(csv.DictReader(f))

print("rows:", len(rows))
print("columns:", list(rows[0].keys()))
print("first row:", rows[0])

groups = defaultdict(list)
for r in rows:
    key = (r["pool_mode"], r["policy"], r["top_k"])
    groups[key].append(float(r["mean_failure_risk"]))

for key in sorted(groups)[:10]:
    vals = groups[key]
    print(key, "mean_risk=", sum(vals) / len(vals))
PY
```

This prints the row count, column names, one example row, and a mean
predicted-risk preview grouped by pool mode/policy/top-k. It only reads the
file — it never modifies it.

If you have `pandas` installed anyway and prefer it, the equivalent is:

```bash
python - <<'PY'
import pandas as pd
df = pd.read_csv("data/simulated_failure_aware_al_benchmark_v051.csv")
print(df.head())
print(df.groupby(["pool_mode", "policy", "top_k"])[["failures_selected", "mean_failure_risk"]].mean().head(20))
PY
```

— but treat this as optional; do not install `pandas` just for this
quickstart.

## 8. How to Interpret the Report

Open `reports/simulated_failure_aware_al_benchmark_v051.md`. It contains, in
order: the policies and pool modes tested, a results table per pool mode
(mean ± std failures/risk for each policy at each top-k), a comparison
against the single-trial v0.5.0 result, scientific caveats, and a
dynamically-computed "Safe Claims" section. The safe-claim sentence is
generated from the actual numbers in the CSV each time the script runs — it
is not hardcoded, and it will only call a pool mode's failure-count
reduction "clear" if the effect is larger than its own trial-to-trial noise.

## 9. Safe Claim Boundaries

> ActiStruct v0.5.1 extends the v0.5.0 offline benchmark into repeated
> stress tests. Across 50 trials, failure-aware LCB reduced the mean
> predicted failure risk in all tested pool modes. It also reduced known
> failed selections relative to LCB-only most clearly in normal and
> failure-enriched pools, while behavior was weaker in heldout-material
> pools and not universally better in high-uncertainty pools. These results
> support failure risk as a soft DFT triage signal, not a guarantee of live
> DFT savings.

The governing principle, repeated throughout ActiStruct's documentation:

```text
ML predicts. Uncertainty ranks. Failure risk warns. QE/PBE validates.
```

This quickstart does not run QE/PBE. This quickstart does not validate new
materials. This quickstart does not prove live DFT savings. This quickstart
does not prove universal generalization across all material classes. This
quickstart does not replace DFT.

## 10. Troubleshooting

**`pytest: command not found`** — you skipped `pip install -e ".[test]"`.
`pytest` is declared as the `test` optional-dependency in `pyproject.toml`,
not in `requirements.txt`; re-run the installation commands in Section 3.

**Missing `pandas`/`scikit-learn` dependency** — `scikit-learn` is a normal
dependency (`pip install -r requirements.txt` provides it); `pandas` is
intentionally **not** a dependency. Use the stdlib `csv` inspection snippet
in Section 7 instead of installing `pandas`.

**Line-ending warnings on Windows/WSL** — git may warn
`CRLF will be replaced by LF the next time Git touches it` after running
the benchmark script. This is usually cosmetic, not a content change.
Before committing anything, check whether the content actually changed:

```bash
git diff -- data/simulated_failure_aware_al_benchmark_v051.csv
git diff -- reports/simulated_failure_aware_al_benchmark_v051.md
```

If these come back empty (no real diff, only the CRLF warning), do not
commit them — restore them instead:

```bash
git checkout -- data/simulated_failure_aware_al_benchmark_v051.csv
git checkout -- reports/simulated_failure_aware_al_benchmark_v051.md
```

**Working tree changed after regenerating the CSV/report** — the benchmark
uses fixed random seeds and should reproduce byte-identical output. If
`git diff` shows a *real* content change after running it unmodified, that
is unexpected — do not commit it; open an issue describing what changed.

## 11. Next Step After This Quickstart

Read `reports/actistruct_technical_report_v06.md` Section 17 ("Recommended
Next Step: Live QE/PBE Validation Batch Design") for the proposed — not yet
executed — design for a small live QE/PBE validation batch. No live
validation has been performed as of v0.6.3; that remains future work.
