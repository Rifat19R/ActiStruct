"""Reliability-aware quickstart example for ActiStruct.

Reads the already-committed v0.5.1 offline stress-benchmark CSV and prints a
short summary. This script does not run QE/DFT, does not modify any file,
and does not depend on pandas (stdlib `csv` only).

Usage:
    python examples/reliability_aware_quickstart.py
"""

from __future__ import annotations

import csv
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV = ROOT / "data" / "simulated_failure_aware_al_benchmark_v051.csv"

CAVEAT = "Caveat: offline simulation only; no live QE/PBE validation."


def load_rows(path: Path = DEFAULT_CSV) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def top10_summary(rows: list[dict[str, str]]) -> dict[str, dict[str, dict[str, float]]]:
    """Mean failures_selected/mean_failure_risk at top_k=10, grouped by
    pool_mode then policy."""
    grouped: dict[str, dict[str, list[dict[str, float]]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        if row["top_k"] != "10":
            continue
        grouped[row["pool_mode"]][row["policy"]].append(
            {
                "failures_selected": float(row["failures_selected"]),
                "mean_failure_risk": float(row["mean_failure_risk"]),
            }
        )

    summary: dict[str, dict[str, dict[str, float]]] = {}
    for pool_mode, by_policy in grouped.items():
        summary[pool_mode] = {}
        for policy, entries in by_policy.items():
            summary[pool_mode][policy] = {
                "mean_failures_selected": statistics.mean(e["failures_selected"] for e in entries),
                "mean_failure_risk": statistics.mean(e["mean_failure_risk"] for e in entries),
            }
    return summary


def main(csv_path: Path = DEFAULT_CSV) -> int:
    rows = load_rows(csv_path)

    print("ActiStruct reliability-aware quickstart")
    print(f"Rows: {len(rows)}")
    print(f"Policies: {sorted({row['policy'] for row in rows})}")
    print(f"Pool modes: {sorted({row['pool_mode'] for row in rows})}")
    print(f"Top-k values: {sorted({int(row['top_k']) for row in rows})}")

    summary = top10_summary(rows)
    print("\nTop-k=10 lcb_only vs failure_aware_aggressive summary:")
    for pool_mode in sorted(summary):
        by_policy = summary[pool_mode]
        lcb = by_policy.get("lcb_only")
        aggressive = by_policy.get("failure_aware_aggressive")
        if lcb is None or aggressive is None:
            continue
        print(
            f"  {pool_mode}: "
            f"lcb_only failures={lcb['mean_failures_selected']:.2f} risk={lcb['mean_failure_risk']:.3f} | "
            f"aggressive failures={aggressive['mean_failures_selected']:.2f} risk={aggressive['mean_failure_risk']:.3f}"
        )

    print(f"\n{CAVEAT}")
    print("This script does not run QE/PBE; no live QE/PBE validation has been performed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
