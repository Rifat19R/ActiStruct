from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from actistruct.acquisition import rank_candidates

DEFAULT_PREDICTIONS = ROOT / "data" / "qe_reliability_predictions_v02.csv"
DEFAULT_TABLE = ROOT / "data" / "failure_aware_acquisition_demo.csv"
DEFAULT_REPORT = ROOT / "reports" / "failure_aware_acquisition_demo.md"


def read_prediction_candidates(
    path: str | Path,
    experiment: str = "baseline_random_split",
    model: str = "RandomForestClassifier",
    limit: int = 50,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with Path(path).open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["experiment"] != experiment or row["model"] != model:
                continue
            risk = _float(row.get("predicted_failure_risk"))
            if risk is None:
                continue
            rows.append({
                "record_id": row["record_id"],
                "material_id": row["material_id"],
                "failure_label": row["failure_label"],
                "true_success": int(row["true_success"]),
                "predicted_value": 0.0,
                "uncertainty": 0.0,
                "failure_risk": risk,
            })
    return rows[:limit]


def build_demo_rows(
    candidates: list[dict[str, object]],
    failure_penalties: tuple[float, ...] = (0.0, 0.5, 1.0, 2.0),
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for penalty in failure_penalties:
        ranked = rank_candidates(
            candidates,
            objective="minimize",
            exploration_weight=1.0,
            failure_penalty=penalty,
        )
        for rank, item in enumerate(ranked, start=1):
            row = dict(item)
            row["failure_penalty"] = penalty
            row["rank"] = rank
            rows.append(row)
    return rows


def write_demo_table(rows: list[dict[str, object]], path: str | Path) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "failure_penalty",
        "rank",
        "record_id",
        "material_id",
        "failure_label",
        "true_success",
        "predicted_value",
        "uncertainty",
        "failure_risk",
        "failure_aware_score",
    ]
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def render_report(rows: list[dict[str, object]], table_path: str | Path) -> str:
    penalty_values = sorted({float(row["failure_penalty"]) for row in rows})
    lines = [
        "# Failure-Aware Acquisition Demo",
        "",
        "## Purpose",
        "",
        "This offline demo shows how predicted `failure_risk` can enter an "
        "active-learning acquisition score before launching new DFT jobs.",
        "",
        "No QE or DFT calculations are launched. The demo uses v0.2 classifier "
        "predictions as candidate metadata and applies the minimization score:",
        "",
        "```text",
        "score = predicted_value - exploration_weight * uncertainty + failure_penalty * failure_risk",
        "```",
        "",
        "Lower score is preferred for minimization.",
        "",
        "## Output",
        "",
        f"- Demo table: `{_repo_path(table_path)}`",
        "",
        "## Penalty Sweep",
        "",
    ]
    for penalty in penalty_values:
        subset = [row for row in rows if float(row["failure_penalty"]) == penalty]
        top = subset[:10]
        failure_count = sum(int(row["true_success"]) == 0 for row in top)
        avg_risk = sum(float(row["failure_risk"]) for row in top) / max(len(top), 1)
        lines.extend([
            f"### failure_penalty = {penalty:g}",
            "",
            f"- Top-10 known failures: **{failure_count}**",
            f"- Top-10 mean predicted failure risk: **{avg_risk:.3f}**",
            "",
            "| Rank | Material | Failure label | True success | Failure risk | Score |",
            "| ---: | --- | --- | ---: | ---: | ---: |",
        ])
        for row in top:
            lines.append(
                f"| {row['rank']} | `{row['material_id']}` | `{row['failure_label']}` | "
                f"{row['true_success']} | {float(row['failure_risk']):.3f} | "
                f"{float(row['failure_aware_score']):.3f} |"
            )
        lines.append("")

    lines.extend([
        "## Scientific Caveat",
        "",
        "This is a ranking-policy demonstration, not a final production "
        "acquisition loop. `predicted_value` and `uncertainty` are neutral "
        "placeholders here because the rows come from completed reliability "
        "records, not from a live GP candidate grid. The next production step "
        "is to compute these terms from the existing GP surrogate and apply the "
        "same failure penalty before choosing new DFT candidates.",
        "",
    ])
    return "\n".join(lines)


def write_report(text: str, path: str | Path) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", default=str(DEFAULT_PREDICTIONS))
    parser.add_argument("--table", default=str(DEFAULT_TABLE))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args(argv)

    candidates = read_prediction_candidates(args.predictions, limit=args.limit)
    rows = build_demo_rows(candidates)
    write_demo_table(rows, args.table)
    write_report(render_report(rows, args.table), args.report)
    print(f"Wrote {args.table}")
    print(f"Wrote {args.report}")
    return 0


def _float(raw: str | None) -> float | None:
    if raw in ("", None):
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _repo_path(path: str | Path) -> str:
    item = Path(path)
    try:
        return str(item.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(item)


if __name__ == "__main__":
    raise SystemExit(main())
