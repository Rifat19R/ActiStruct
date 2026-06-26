from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from actistruct.acquisition import (  # noqa: E402
    DEFAULT_BETA,
    DEFAULT_FAILURE_RISK_THRESHOLD,
    DEFAULT_GAMMA,
    GAMMA_MODES,
    rank_candidates,
)


DEFAULT_INPUT = ROOT / "data" / "qe_reliability_predictions_v032.csv"
DEFAULT_TABLE = ROOT / "data" / "failure_aware_gp_acquisition_v041.csv"
DEFAULT_REPORT = ROOT / "reports" / "failure_aware_gp_acquisition_v041.md"

OUTPUT_COLUMNS = [
    "rank",
    "candidate_id",
    "predicted_value",
    "uncertainty",
    "failure_risk",
    "base_lcb_score",
    "failure_penalty",
    "acquisition_score",
    "rank_without_failure_risk",
    "rank_with_failure_risk",
    "rank_shift",
    "risk_flag",
    "selection_reason",
]


def read_v032_candidates(path: str | Path, limit: int = 50) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    seen: set[str] = set()
    with Path(path).open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            threshold = _float(row.get("threshold"))
            if threshold is None or abs(threshold - DEFAULT_FAILURE_RISK_THRESHOLD) > 1e-12:
                continue
            candidate_id = str(row["record_id"])
            if candidate_id in seen:
                continue
            seen.add(candidate_id)
            candidates.append({
                "candidate_id": candidate_id,
                "predicted_value": 0.0,
                "uncertainty": 0.0,
                "failure_risk": _float(row.get("total_failure_risk")),
                "material_id": row.get("material_id", ""),
                "failure_label": row.get("failure_label", ""),
            })
            if len(candidates) >= limit:
                break
    return candidates


def rank_failure_aware_candidates(
    candidates: list[dict[str, object]],
    beta: float = DEFAULT_BETA,
    gamma: float = DEFAULT_GAMMA,
    failure_risk_threshold: float = DEFAULT_FAILURE_RISK_THRESHOLD,
) -> list[dict[str, object]]:
    return rank_candidates(
        candidates,
        objective="minimize",
        beta=beta,
        gamma=gamma,
        failure_risk_threshold=failure_risk_threshold,
    )


def rank_gamma_modes(
    candidates: list[dict[str, object]],
    beta: float = DEFAULT_BETA,
    failure_risk_threshold: float = DEFAULT_FAILURE_RISK_THRESHOLD,
) -> dict[str, list[dict[str, object]]]:
    return {
        mode: rank_failure_aware_candidates(candidates, beta, gamma, failure_risk_threshold)
        for mode, gamma in GAMMA_MODES.items()
    }


def write_ranked_candidates(rows: list[dict[str, object]], path: str | Path) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        *OUTPUT_COLUMNS,
        "material_id",
        "failure_label",
    ]
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def render_report(
    rows: list[dict[str, object]],
    table_path: str | Path,
    mode_rows: dict[str, list[dict[str, object]]] | None = None,
) -> str:
    elevated = sum(row["risk_flag"] == "elevated" for row in rows)
    modes_text = ", ".join(f"`{name}={value}`" for name, value in GAMMA_MODES.items())
    lines = [
        "# Failure-Aware GP Acquisition v0.4.1",
        "",
        "## Purpose",
        "",
        "This integrates v0.3.2 failure-risk predictions into the live GP/LCB "
        "candidate ranking path as a soft penalty. No QE/DFT jobs are launched.",
        "",
        "## Formula",
        "",
        "For minimization:",
        "",
        "```text",
        "score = predicted_value - beta * uncertainty + gamma * failure_risk",
        "```",
        "",
        f"Defaults: `beta={DEFAULT_BETA}`, `gamma={DEFAULT_GAMMA}`, "
        f"`failure_risk_threshold={DEFAULT_FAILURE_RISK_THRESHOLD}`.",
        f"Gamma modes: {modes_text}.",
        "",
        "Candidates are never hard rejected by failure risk. Elevated-risk "
        "candidates are only penalized in the acquisition score.",
        "",
        "## Output",
        "",
        f"- Ranked table: `{_repo_path(table_path)}`",
        f"- Ranked candidates: **{len(rows)}**",
        f"- Elevated-risk candidates: **{elevated}**",
        "",
        "## Default Top Candidates",
        "",
        "| Rank | Candidate | Base LCB | Failure risk | Penalty | Score | Base rank | Risk rank | Shift | Risk flag |",
        "| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows[:10]:
        risk = row["failure_risk"]
        risk_text = "NA" if risk == "" else f"{float(risk):.3f}"
        lines.append(
            f"| {row['rank']} | `{row['candidate_id']}` | "
            f"{float(row['base_lcb_score']):.3f} | {risk_text} | "
            f"{float(row['failure_penalty']):.3f} | "
            f"{float(row['acquisition_score']):.3f} | "
            f"{row['rank_without_failure_risk']} | "
            f"{row['rank_with_failure_risk']} | {row['rank_shift']} | "
            f"{row['risk_flag']} |"
        )
    if mode_rows:
        lines.extend(["", "## Gamma Mode Top-10 Changes", ""])
        for mode, ranked in mode_rows.items():
            top = ranked[:10]
            avg_risk = sum(_risk_or_zero(row["failure_risk"]) for row in top) / max(len(top), 1)
            shifted = sum(1 for row in top if int(row["rank_shift"]) != 0)
            lines.extend([
                f"### {mode} gamma = {GAMMA_MODES[mode]}",
                "",
                f"- Top-10 mean failure risk: **{avg_risk:.3f}**",
                f"- Top-10 candidates shifted by risk penalty: **{shifted}**",
                "",
                "| Rank | Candidate | Failure risk | Score | Base rank | Shift |",
                "| ---: | --- | ---: | ---: | ---: | ---: |",
            ])
            for row in top:
                risk = row["failure_risk"]
                risk_text = "NA" if risk == "" else f"{float(risk):.3f}"
                lines.append(
                    f"| {row['rank']} | `{row['candidate_id']}` | {risk_text} | "
                    f"{float(row['acquisition_score']):.3f} | "
                    f"{row['rank_without_failure_risk']} | {row['rank_shift']} |"
                )
            lines.append("")
    lines.extend([
        "",
        "## Scientific Caveat",
        "",
        "The included CSV is an offline integration artifact. The production "
        "engine now exposes an optional `failure_risk_provider` on `ActiveSystem`; "
        "when it is absent, the original DE LCB path is preserved.",
        "",
    ])
    return "\n".join(lines)


def write_report(text: str, path: str | Path) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--table", default=str(DEFAULT_TABLE))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--beta", type=float, default=DEFAULT_BETA)
    parser.add_argument("--gamma", type=float, default=DEFAULT_GAMMA)
    parser.add_argument("--failure-risk-threshold", type=float, default=DEFAULT_FAILURE_RISK_THRESHOLD)
    args = parser.parse_args(argv)

    candidates = read_v032_candidates(args.input, args.limit)
    ranked = rank_failure_aware_candidates(candidates, args.beta, args.gamma, args.failure_risk_threshold)
    mode_rows = rank_gamma_modes(candidates, args.beta, args.failure_risk_threshold)
    write_ranked_candidates(ranked, args.table)
    write_report(render_report(ranked, args.table, mode_rows), args.report)
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


def _risk_or_zero(value: object) -> float:
    if value == "":
        return 0.0
    return float(value)


def _repo_path(path: str | Path) -> str:
    item = Path(path)
    try:
        return str(item.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(item)


if __name__ == "__main__":
    raise SystemExit(main())
