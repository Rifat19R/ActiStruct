from __future__ import annotations

import csv
import statistics
from collections import defaultdict

from publication_data import RAW_DIR, TABLE_DIR, ensure_dirs


FIELDS = [
    "category", "n_systems", "mean_abs_error_pbe", "std_abs_error_pbe", "max_abs_error_pbe",
    "mean_abs_error_exp", "std_abs_error_exp", "mean_n_qe", "std_n_qe", "min_n_qe",
    "max_n_qe", "pct_converged", "mean_gp_uncertainty",
]


def f(value: str) -> float | None:
    try:
        return float(value) if value not in ("", "None") else None
    except ValueError:
        return None


def mean(values: list[float]) -> float | None:
    return statistics.mean(values) if values else None


def stdev(values: list[float]) -> float | None:
    return statistics.stdev(values) if len(values) > 1 else 0.0 if values else None


def summarize(rows: list[dict], name: str) -> dict:
    pbe = [v for row in rows if (v := f(row["pct_error_param1"])) is not None]
    exp = []
    for row in rows:
        best = f(row["best_param1"])
        ref = f(row["exp_param1"])
        if best is not None and ref not in (None, 0):
            exp.append(abs(best - ref) / abs(ref) * 100.0)
    calls = [v for row in rows if (v := f(row["n_qe_total"])) is not None]
    gp = [v for row in rows if (v := f(row["gp_uncertainty_eV"])) is not None]
    conv = [str(row["converged"]).lower() == "true" for row in rows]
    return {
        "category": name,
        "n_systems": len(rows),
        "mean_abs_error_pbe": mean(pbe),
        "std_abs_error_pbe": stdev(pbe),
        "max_abs_error_pbe": max(pbe) if pbe else None,
        "mean_abs_error_exp": mean(exp),
        "std_abs_error_exp": stdev(exp),
        "mean_n_qe": mean(calls),
        "std_n_qe": stdev(calls),
        "min_n_qe": int(min(calls)) if calls else None,
        "max_n_qe": int(max(calls)) if calls else None,
        "pct_converged": sum(conv) / len(conv) * 100.0 if conv else 0.0,
        "mean_gp_uncertainty": mean(gp),
    }


def fmt(value: object) -> str:
    return "" if value is None else f"{value:.6g}" if isinstance(value, float) else str(value)


def main() -> None:
    ensure_dirs()
    with (RAW_DIR / "all_results.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[row["category"]].append(row)
    out_rows = [summarize(grouped[name], name) for name in grouped]
    out_rows.append(summarize(rows, "Overall"))
    out_rows.append(summarize([r for r in rows if r["dim"] == "1"], "Overall 1D"))
    out_rows.append(summarize([r for r in rows if r["dim"] == "2"], "Overall 2D"))
    out = TABLE_DIR / "statistics_summary.csv"
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(out_rows)
    print("Category statistics")
    for row in out_rows:
        print(" | ".join(fmt(row[field]) for field in FIELDS[:6]))
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
