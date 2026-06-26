from __future__ import annotations

import argparse
import csv
import math
import random
import sys
from pathlib import Path
from statistics import mean


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from actistruct.acquisition import GAMMA_MODES, rank_candidates  # noqa: E402


DEFAULT_PREDICTIONS = ROOT / "data" / "qe_reliability_predictions_v032.csv"
DEFAULT_RECORDS = ROOT / "data" / "parsed_records" / "qe_reliability_records.csv"
DEFAULT_TABLE = ROOT / "data" / "simulated_failure_aware_al_benchmark_v05.csv"
DEFAULT_REPORT = ROOT / "reports" / "simulated_failure_aware_al_benchmark_v05.md"

TOP_K_VALUES = (5, 10, 20)
POLICIES = {
    "random_selection": None,
    "lcb_only": 0.0,
    "failure_aware_lcb_mild": GAMMA_MODES["mild"],
    "failure_aware_lcb_balanced": GAMMA_MODES["balanced"],
    "failure_aware_lcb_aggressive": GAMMA_MODES["aggressive"],
}

OUTPUT_COLUMNS = [
    "policy",
    "top_k",
    "known_failures_selected",
    "known_successes_selected",
    "failure_avoidance_rate",
    "mean_failure_risk",
    "mean_acquisition_score",
    "top_k_overlap_with_lcb",
    "mean_rank_shift",
    "best_candidate_id",
    "best_candidate_material_id",
    "best_candidate_energy_ev",
]


def load_candidates(
    predictions_path: str | Path = DEFAULT_PREDICTIONS,
    records_path: str | Path = DEFAULT_RECORDS,
    threshold: float = 0.10,
) -> list[dict[str, object]]:
    energies = _record_energies(records_path)
    candidates: list[dict[str, object]] = []
    seen: set[str] = set()
    with Path(predictions_path).open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            row_threshold = _float(row.get("threshold"))
            if row_threshold is None or abs(row_threshold - threshold) > 1e-12:
                continue
            candidate_id = str(row["record_id"])
            if candidate_id in seen:
                continue
            seen.add(candidate_id)
            failure_risk = _float(row.get("total_failure_risk")) or 0.0
            ood_distance = _float(row.get("ood_distance")) or 0.0
            candidates.append({
                "candidate_id": candidate_id,
                "material_id": row.get("material_id", ""),
                "failure_label": row.get("failure_label", ""),
                "true_failure": int(row.get("true_failure", "0")),
                "failure_risk": failure_risk,
                "predicted_value": 0.0,
                "uncertainty": ood_distance,
                "known_energy_ev": energies.get(candidate_id),
            })
    _normalize_uncertainty(candidates)
    return candidates


def run_benchmark(
    candidates: list[dict[str, object]],
    top_k_values: tuple[int, ...] = TOP_K_VALUES,
    random_seed: int = 42,
) -> list[dict[str, object]]:
    ranked_by_policy = rank_all_policies(candidates, random_seed)
    lcb_top_by_k = {
        top_k: {str(row["candidate_id"]) for row in ranked_by_policy["lcb_only"][:top_k]}
        for top_k in top_k_values
    }
    rows: list[dict[str, object]] = []
    for policy, ranked in ranked_by_policy.items():
        for top_k in top_k_values:
            selected = ranked[:top_k]
            rows.append(_summary_row(policy, top_k, selected, lcb_top_by_k[top_k]))
    return rows


def rank_all_policies(
    candidates: list[dict[str, object]],
    random_seed: int = 42,
) -> dict[str, list[dict[str, object]]]:
    ranked: dict[str, list[dict[str, object]]] = {}
    for policy, gamma in POLICIES.items():
        if policy == "random_selection":
            shuffled = [dict(item) for item in candidates]
            random.Random(random_seed).shuffle(shuffled)
            for rank, item in enumerate(shuffled, start=1):
                item["rank"] = rank
                item["base_lcb_score"] = float(item["predicted_value"]) - 2.0 * float(item["uncertainty"])
                item["failure_penalty"] = 0.0
                item["acquisition_score"] = item["base_lcb_score"]
                item["rank_without_failure_risk"] = rank
                item["rank_with_failure_risk"] = rank
                item["rank_shift"] = 0
            ranked[policy] = shuffled
        else:
            ranked[policy] = rank_candidates(candidates, objective="minimize", beta=2.0, gamma=float(gamma))
    return ranked


def write_table(rows: list[dict[str, object]], path: str | Path) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def render_report(rows: list[dict[str, object]], table_path: str | Path, n_candidates: int) -> str:
    lines = [
        "# Simulated Failure-Aware Active-Learning Benchmark v0.5",
        "",
        "## Purpose",
        "",
        "This offline benchmark compares candidate-selection policies using "
        "existing completed QE reliability records and v0.3.2 failure-risk "
        "predictions. It does not run QE/DFT and does not modify parser logic "
        "or labels.",
        "",
        "## Policies",
        "",
        "- `random_selection`",
        "- `lcb_only`",
        "- `failure_aware_lcb_mild`: gamma = 0.1",
        "- `failure_aware_lcb_balanced`: gamma = 0.3",
        "- `failure_aware_lcb_aggressive`: gamma = 1.0",
        "",
        "## Output",
        "",
        f"- Benchmark table: `{_repo_path(table_path)}`",
        f"- Candidate pool: **{n_candidates}** records",
        "",
        "## Results",
        "",
        "| Policy | Top-k | Failures | Successes | Avoidance | Mean risk | Mean score | LCB overlap | Mean shift | Best candidate | Best energy eV |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row['policy']} | {row['top_k']} | "
            f"{row['known_failures_selected']} | {row['known_successes_selected']} | "
            f"{float(row['failure_avoidance_rate']):.3f} | "
            f"{float(row['mean_failure_risk']):.3f} | "
            f"{float(row['mean_acquisition_score']):.3f} | "
            f"{float(row['top_k_overlap_with_lcb']):.3f} | "
            f"{float(row['mean_rank_shift']):.3f} | "
            f"`{row['best_candidate_id']}` | {_fmt_float(row['best_candidate_energy_ev'])} |"
        )
    lines.extend([
        "",
        "## Interpretation",
        "",
        _gamma_interpretation(rows),
        "",
        "## Scientific Caveats",
        "",
        "- This is a simulated policy benchmark, not a live GP retraining study.",
        "- The LCB uncertainty proxy uses existing v0.3.2 OOD distances because no "
        "new GP/QE jobs are launched here.",
        "- Failure-risk generalization still has high split-to-split variance, so "
        "failure risk should remain a soft penalty for DFT triage, not a hard "
        "rejection rule.",
        "- Known failures/successes are evaluated from completed records after "
        "selection; failed records are not deleted or relabeled.",
        "",
    ])
    return "\n".join(lines)


def write_report(text: str, path: str | Path) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")


def _summary_row(
    policy: str,
    top_k: int,
    selected: list[dict[str, object]],
    lcb_top_ids: set[str],
) -> dict[str, object]:
    failures = sum(int(row["true_failure"]) for row in selected)
    successes = len(selected) - failures
    selected_ids = {str(row["candidate_id"]) for row in selected}
    best = _best_success(selected)
    return {
        "policy": policy,
        "top_k": top_k,
        "known_failures_selected": failures,
        "known_successes_selected": successes,
        "failure_avoidance_rate": successes / max(len(selected), 1),
        "mean_failure_risk": _safe_mean([float(row["failure_risk"]) for row in selected]),
        "mean_acquisition_score": _safe_mean([float(row["acquisition_score"]) for row in selected]),
        "top_k_overlap_with_lcb": len(selected_ids & lcb_top_ids) / max(top_k, 1),
        "mean_rank_shift": _safe_mean([abs(float(row.get("rank_shift", 0.0))) for row in selected]),
        "best_candidate_id": best.get("candidate_id", "NA"),
        "best_candidate_material_id": best.get("material_id", "NA"),
        "best_candidate_energy_ev": best.get("known_energy_ev", ""),
    }


def _best_success(selected: list[dict[str, object]]) -> dict[str, object]:
    successes = [
        row for row in selected
        if int(row["true_failure"]) == 0 and row.get("known_energy_ev") not in (None, "")
    ]
    if not successes:
        return {}
    return min(successes, key=lambda row: float(row["known_energy_ev"]))


def _record_energies(records_path: str | Path) -> dict[str, float]:
    energies: dict[str, float] = {}
    with Path(records_path).open(newline="", encoding="utf-8") as handle:
        for idx, row in enumerate(csv.DictReader(handle)):
            energy = _float(row.get("energy_ev")) or _float(row.get("final_energy_ry"))
            if energy is not None:
                energies[str(idx)] = energy
    return energies


def _normalize_uncertainty(candidates: list[dict[str, object]]) -> None:
    values = [float(row["uncertainty"]) for row in candidates]
    if not values:
        return
    lo, hi = min(values), max(values)
    span = hi - lo
    for row in candidates:
        row["uncertainty"] = 0.0 if span == 0 else (float(row["uncertainty"]) - lo) / span


def _gamma_interpretation(rows: list[dict[str, object]]) -> str:
    top10 = {row["policy"]: row for row in rows if int(row["top_k"]) == 10}
    parts = []
    for policy in ("lcb_only", "failure_aware_lcb_mild", "failure_aware_lcb_balanced", "failure_aware_lcb_aggressive"):
        if policy in top10:
            row = top10[policy]
            parts.append(
                f"- `{policy}` selected {row['known_failures_selected']} known failures "
                f"at top-10 with mean risk {float(row['mean_failure_risk']):.3f}."
            )
    return "\n".join(parts)


def _float(raw: str | None) -> float | None:
    if raw in ("", None):
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    if math.isnan(value):
        return None
    return value


def _safe_mean(values: list[float]) -> float:
    return mean(values) if values else 0.0


def _fmt_float(value: object) -> str:
    if value in ("", None):
        return "NA"
    return f"{float(value):.3f}"


def _repo_path(path: str | Path) -> str:
    item = Path(path)
    try:
        return str(item.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(item)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", default=str(DEFAULT_PREDICTIONS))
    parser.add_argument("--records", default=str(DEFAULT_RECORDS))
    parser.add_argument("--table", default=str(DEFAULT_TABLE))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--random-seed", type=int, default=42)
    args = parser.parse_args(argv)

    candidates = load_candidates(args.predictions, args.records)
    rows = run_benchmark(candidates, random_seed=args.random_seed)
    write_table(rows, args.table)
    write_report(render_report(rows, args.table, len(candidates)), args.report)
    print(f"Wrote {args.table}")
    print(f"Wrote {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
