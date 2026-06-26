"""v0.5.1 repeated-trial stress benchmark for failure-aware GP/LCB acquisition.

This is an offline simulation only. It reuses the completed QE reliability
records and v0.3.2 failure-risk predictions already loaded by v0.5.0
(`simulated_failure_aware_al_benchmark_v05.load_candidates`). No QE/DFT jobs
are launched here, no parser logic is touched, and no failed records are
deleted or relabeled.

v0.5.0 ran a single offline trial on the full, naturally-occurring candidate
pool. Because `lcb_only` already avoided all known failures at top-10 in that
single sample, v0.5.0 could not show whether failure-aware re-ranking
actually helps when LCB-only is not already perfect. v0.5.1 stress-tests this
by repeating the comparison across many random sub-pools (`n_trials`) and
under harder candidate-pool conditions (failure-enriched, held-out-material,
high-uncertainty), so that a genuine LCB-only failure case can occur and the
failure-aware policies can be judged against it.
"""

from __future__ import annotations

import argparse
import csv
import random
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from actistruct.acquisition import GAMMA_MODES, rank_candidates  # noqa: E402
from analysis.simulated_failure_aware_al_benchmark_v05 import (  # noqa: E402
    load_candidates,
)

DEFAULT_TABLE = ROOT / "data" / "simulated_failure_aware_al_benchmark_v051.csv"
DEFAULT_REPORT = ROOT / "reports" / "simulated_failure_aware_al_benchmark_v051.md"
DEFAULT_V050_TABLE = ROOT / "data" / "simulated_failure_aware_al_benchmark_v05.csv"

TOP_K_VALUES = (5, 10, 20)
N_TRIALS = 50
BASE_SEED = 42

# Target candidate-pool size per trial for the modes that sub-sample records
# directly (normal/failure_enriched/high_uncertainty). heldout_material_pool
# accumulates whole materials until it reaches at least this many records, so
# its actual pool size varies trial to trial by construction.
POOL_SIZE = 150
FAILURE_ENRICHED_TARGET_FRACTION = 0.60
HELDOUT_MATERIAL_TARGET_SIZE = 150
HIGH_UNCERTAINTY_TOP_FRACTION = 0.5

POLICIES = {
    "random_selection": None,
    "lcb_only": 0.0,
    "failure_aware_mild": GAMMA_MODES["mild"],
    "failure_aware_balanced": GAMMA_MODES["balanced"],
    "failure_aware_aggressive": GAMMA_MODES["aggressive"],
}

POOL_MODES = (
    "normal_pool",
    "failure_enriched_pool",
    "heldout_material_pool",
    "high_uncertainty_pool",
)

# Disjoint seed ranges so each pool mode's per-trial randomness is independent
# but still fully reproducible from BASE_SEED.
POOL_MODE_SEED_OFFSET = {
    "normal_pool": 0,
    "failure_enriched_pool": 10_000,
    "heldout_material_pool": 20_000,
    "high_uncertainty_pool": 30_000,
}

OUTPUT_COLUMNS = [
    "policy",
    "pool_mode",
    "trial_id",
    "seed",
    "top_k",
    "failures_selected",
    "successes_selected",
    "failure_fraction",
    "mean_failure_risk",
    "mean_acquisition_score",
    "best_known_candidate_found",
    "top_k_overlap_with_lcb",
    "mean_rank_shift",
    "delta_failures_vs_lcb",
    "delta_mean_risk_vs_lcb",
]


# ── Pool construction ─────────────────────────────────────────────────────

def _sample(rng: random.Random, pool: list[dict], k: int) -> list[dict]:
    if not pool or k <= 0:
        return []
    if k <= len(pool):
        return rng.sample(pool, k)
    # Should not happen with current data volumes; sampling with replacement
    # keeps the function defined instead of crashing on a too-small pool.
    return rng.choices(pool, k=k)


def build_normal_pool(base: list[dict], rng: random.Random) -> list[dict]:
    """Plain random sub-sample of the full v0.5.0 candidate pool."""
    size = min(POOL_SIZE, len(base))
    return [dict(row) for row in _sample(rng, base, size)]


def build_failure_enriched_pool(base: list[dict], rng: random.Random) -> list[dict]:
    """Over-represent known failures relative to their natural base rate, to
    test whether failure-aware ranking avoids risky candidates when failures
    are closer to the selectable region."""
    failures = [row for row in base if int(row["true_failure"]) == 1]
    successes = [row for row in base if int(row["true_failure"]) == 0]
    n_fail = min(round(POOL_SIZE * FAILURE_ENRICHED_TARGET_FRACTION), len(failures))
    n_succ = min(POOL_SIZE - n_fail, len(successes))
    chosen = _sample(rng, failures, n_fail) + _sample(rng, successes, n_succ)
    rng.shuffle(chosen)
    return [dict(row) for row in chosen]


def build_heldout_material_pool(base: list[dict], rng: random.Random) -> list[dict]:
    """Sample whole materials (not individual records) until the pool reaches
    the target size, so failures/successes cluster by material the way they
    would if entire materials were held out together, rather than being
    i.i.d. across records."""
    by_material: dict[str, list[dict]] = defaultdict(list)
    for row in base:
        by_material[str(row["material_id"])].append(row)
    materials = list(by_material)
    rng.shuffle(materials)
    pool: list[dict] = []
    for material_id in materials:
        pool.extend(by_material[material_id])
        if len(pool) >= HELDOUT_MATERIAL_TARGET_SIZE:
            break
    return [dict(row) for row in pool]


def build_high_uncertainty_pool(base: list[dict], rng: random.Random) -> list[dict]:
    """Sample from the highest-uncertainty half of the pool (by the existing
    normalized OOD-distance proxy), to stress exploration vs. failure-risk
    competition under low GP confidence."""
    ordered = sorted(base, key=lambda row: float(row["uncertainty"]), reverse=True)
    top_n = max(1, int(len(ordered) * HIGH_UNCERTAINTY_TOP_FRACTION))
    subset = ordered[:top_n]
    size = min(POOL_SIZE, len(subset))
    return [dict(row) for row in _sample(rng, subset, size)]


POOL_BUILDERS = {
    "normal_pool": build_normal_pool,
    "failure_enriched_pool": build_failure_enriched_pool,
    "heldout_material_pool": build_heldout_material_pool,
    "high_uncertainty_pool": build_high_uncertainty_pool,
}


def build_pool(base: list[dict], pool_mode: str, rng: random.Random) -> list[dict]:
    return POOL_BUILDERS[pool_mode](base, rng)


# ── Ranking ────────────────────────────────────────────────────────────────

def rank_all_policies(pool: list[dict], trial_seed: int) -> dict[str, list[dict]]:
    ranked: dict[str, list[dict]] = {}
    for policy, gamma in POLICIES.items():
        if policy == "random_selection":
            shuffled = [dict(item) for item in pool]
            random.Random(trial_seed).shuffle(shuffled)
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
            ranked[policy] = rank_candidates(pool, objective="minimize", beta=2.0, gamma=float(gamma))
    return ranked


def gamma_zero_matches_lcb_only(pool: list[dict]) -> bool:
    """Sanity check: gamma=0 acquisition ranking must be identical to the
    lcb_only policy, with no hidden failure-risk influence, even when
    failure_risk values differ across candidates."""
    gamma_zero_ranked = rank_candidates(pool, objective="minimize", beta=2.0, gamma=0.0)
    lcb_only_ranked = rank_candidates(pool, objective="minimize", beta=2.0, gamma=float(POLICIES["lcb_only"]))
    same_order = [r["candidate_id"] for r in gamma_zero_ranked] == [r["candidate_id"] for r in lcb_only_ranked]
    no_penalty = all(r["failure_penalty"] == 0.0 for r in gamma_zero_ranked)
    return same_order and no_penalty


# ── Per-trial metrics ──────────────────────────────────────────────────────

def _best_known_candidate(pool: list[dict]) -> dict | None:
    successes = [
        row for row in pool
        if int(row["true_failure"]) == 0 and row.get("known_energy_ev") not in (None, "")
    ]
    if not successes:
        return None
    return min(successes, key=lambda row: float(row["known_energy_ev"]))


def _selection_metrics(
    selected: list[dict],
    top_k: int,
    lcb_top_ids: set[str],
    best_candidate_id: str | None,
) -> dict[str, object]:
    failures = sum(int(row["true_failure"]) for row in selected)
    successes = len(selected) - failures
    selected_ids = {str(row["candidate_id"]) for row in selected}
    best_found = "" if best_candidate_id is None else int(best_candidate_id in selected_ids)
    return {
        "failures_selected": failures,
        "successes_selected": successes,
        "failure_fraction": failures / max(top_k, 1),
        "mean_failure_risk": _safe_mean([float(row["failure_risk"]) for row in selected]),
        "mean_acquisition_score": _safe_mean([float(row["acquisition_score"]) for row in selected]),
        "best_known_candidate_found": best_found,
        "top_k_overlap_with_lcb": len(selected_ids & lcb_top_ids) / max(top_k, 1),
        "mean_rank_shift": _safe_mean([abs(float(row.get("rank_shift", 0.0))) for row in selected]),
    }


def _trial_rows(trial_id: int, seed: int, pool_mode: str, pool: list[dict]) -> list[dict[str, object]]:
    ranked_by_policy = rank_all_policies(pool, seed)
    best_candidate = _best_known_candidate(pool)
    best_candidate_id = str(best_candidate["candidate_id"]) if best_candidate else None

    lcb_top_by_k = {
        top_k: {str(row["candidate_id"]) for row in ranked_by_policy["lcb_only"][:top_k]}
        for top_k in TOP_K_VALUES
    }
    lcb_metrics_by_k = {
        top_k: _selection_metrics(
            ranked_by_policy["lcb_only"][:top_k], top_k, lcb_top_by_k[top_k], best_candidate_id
        )
        for top_k in TOP_K_VALUES
    }

    rows: list[dict[str, object]] = []
    for policy in POLICIES:
        ranked = ranked_by_policy[policy]
        for top_k in TOP_K_VALUES:
            selected = ranked[:top_k]
            metrics = _selection_metrics(selected, top_k, lcb_top_by_k[top_k], best_candidate_id)
            lcb_ref = lcb_metrics_by_k[top_k]
            rows.append({
                "policy": policy,
                "pool_mode": pool_mode,
                "trial_id": trial_id,
                "seed": seed,
                "top_k": top_k,
                "failures_selected": metrics["failures_selected"],
                "successes_selected": metrics["successes_selected"],
                "failure_fraction": metrics["failure_fraction"],
                "mean_failure_risk": metrics["mean_failure_risk"],
                "mean_acquisition_score": metrics["mean_acquisition_score"],
                "best_known_candidate_found": metrics["best_known_candidate_found"],
                "top_k_overlap_with_lcb": metrics["top_k_overlap_with_lcb"],
                "mean_rank_shift": metrics["mean_rank_shift"],
                "delta_failures_vs_lcb": metrics["failures_selected"] - lcb_ref["failures_selected"],
                "delta_mean_risk_vs_lcb": metrics["mean_failure_risk"] - lcb_ref["mean_failure_risk"],
            })
    return rows


# ── Top-level run ───────────────────────────────────────────────────────────

def run_stress_benchmark(
    base_candidates: list[dict],
    n_trials: int = N_TRIALS,
    base_seed: int = BASE_SEED,
    pool_modes: tuple[str, ...] = POOL_MODES,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    min_pool_size = max(TOP_K_VALUES)
    for trial_id in range(n_trials):
        for pool_mode in pool_modes:
            seed = base_seed + POOL_MODE_SEED_OFFSET[pool_mode] + trial_id
            pool = build_pool(base_candidates, pool_mode, random.Random(seed))
            if len(pool) < min_pool_size:
                # Not enough candidates to fill the largest top_k; skip this
                # trial/pool_mode combination rather than fabricate a result.
                continue
            rows.extend(_trial_rows(trial_id, seed, pool_mode, pool))
    return rows


# ── Aggregation ─────────────────────────────────────────────────────────────

def aggregate_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    groups: dict[tuple[str, int, str], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        key = (str(row["pool_mode"]), int(row["top_k"]), str(row["policy"]))
        groups[key].append(row)

    summary: list[dict[str, object]] = []
    for (pool_mode, top_k, policy), group in groups.items():
        failures = [float(r["failures_selected"]) for r in group]
        risks = [float(r["mean_failure_risk"]) for r in group]
        delta_failures = [float(r["delta_failures_vs_lcb"]) for r in group]
        delta_risks = [float(r["delta_mean_risk_vs_lcb"]) for r in group]
        found_flags = [r["best_known_candidate_found"] for r in group if r["best_known_candidate_found"] != ""]

        fail_mean, fail_std = _mean_std(failures)
        risk_mean, risk_std = _mean_std(risks)
        dfail_mean, dfail_std = _mean_std(delta_failures)
        drisk_mean, drisk_std = _mean_std(delta_risks)
        found_rate = (sum(int(v) for v in found_flags) / len(found_flags)) if found_flags else None

        summary.append({
            "pool_mode": pool_mode,
            "top_k": top_k,
            "policy": policy,
            "n_trials": len(group),
            "mean_failures_selected": fail_mean,
            "std_failures_selected": fail_std,
            "mean_failure_risk": risk_mean,
            "std_failure_risk": risk_std,
            "best_known_candidate_found_rate": found_rate,
            "mean_delta_failures_vs_lcb": dfail_mean,
            "std_delta_failures_vs_lcb": dfail_std,
            "mean_delta_risk_vs_lcb": drisk_mean,
            "std_delta_risk_vs_lcb": drisk_std,
        })

    summary.sort(key=lambda r: (r["pool_mode"], r["top_k"], list(POLICIES).index(r["policy"])))
    return summary


def _mean_std(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    if len(values) == 1:
        return values[0], 0.0
    return statistics.mean(values), statistics.stdev(values)


def _safe_mean(values: list[float]) -> float:
    return statistics.mean(values) if values else 0.0


# ── Report ──────────────────────────────────────────────────────────────────

def render_report(
    rows: list[dict[str, object]],
    summary: list[dict[str, object]],
    table_path: str | Path,
    n_base_candidates: int,
    n_trials: int,
    v050_table_path: str | Path = DEFAULT_V050_TABLE,
) -> str:
    lines = [
        "# Simulated Failure-Aware Active-Learning Stress Benchmark v0.5.1",
        "",
        "## Objective",
        "",
        "Stress-test whether failure-aware GP/LCB candidate re-ranking helps "
        "under harder, repeated candidate-pool conditions, instead of relying "
        "on a single offline sample as v0.5.0 did.",
        "",
        "## Why v0.5.1 is needed",
        "",
        "v0.5.0 ran one offline trial on the naturally-occurring candidate "
        "pool. `lcb_only` already selected zero known failures at top-10 in "
        "that single sample, so v0.5.0 could not show whether failure-aware "
        "re-ranking reduces failed selections relative to LCB-only - only "
        "that it can lower mean predicted failure risk without increasing "
        "failures. v0.5.1 repeats the comparison across "
        f"**{n_trials}** trials and four candidate-pool conditions so that "
        "genuine LCB-only failures can occur and be compared against.",
        "",
        "## Data source",
        "",
        "Same offline data as v0.5.0: completed QE reliability records "
        "(`data/parsed_records/qe_reliability_records.csv`) and v0.3.2 "
        "failure-risk predictions (`data/qe_reliability_predictions_v032.csv`), "
        "loaded via "
        "`analysis.simulated_failure_aware_al_benchmark_v05.load_candidates`. "
        f"Base candidate pool: **{n_base_candidates}** records. No new QE/DFT "
        "jobs were run and no records were deleted or relabeled.",
        "",
        "## Policies",
        "",
        "- `random_selection`",
        "- `lcb_only` (gamma = 0.0)",
        "- `failure_aware_mild` (gamma = 0.1)",
        "- `failure_aware_balanced` (gamma = 0.3)",
        "- `failure_aware_aggressive` (gamma = 1.0)",
        "",
        "A `gamma=0` check is run separately to confirm the failure-aware "
        "ranking function reduces exactly to `lcb_only` ranking (no hidden "
        "risk influence) when gamma is zero; see "
        "`gamma_zero_matches_lcb_only()` and its test.",
        "",
        "## Pool modes",
        "",
        f"- `normal_pool`: random sub-sample of {POOL_SIZE} candidates from "
        "the full v0.5.0 pool, at the pool's natural failure rate.",
        "- `failure_enriched_pool`: random sub-sample re-weighted to "
        f"~{int(FAILURE_ENRICHED_TARGET_FRACTION * 100)}% known failures "
        "(sampled without replacement from real failure/success records; no "
        "labels are fabricated).",
        "- `heldout_material_pool`: whole materials (not individual records) "
        f"are sampled until the pool reaches at least {HELDOUT_MATERIAL_TARGET_SIZE} "
        "records, so failures/successes cluster by material the way they "
        "would if entire materials were held out together, rather than being "
        "i.i.d. across records. Implemented because `material_id` is present "
        "in the v0.3.2 prediction data.",
        "- `high_uncertainty_pool`: sub-sample drawn from the highest-"
        f"uncertainty {int(HIGH_UNCERTAINTY_TOP_FRACTION * 100)}% of candidates "
        "(by the existing normalized OOD-distance proxy used in v0.5.0), to "
        "test exploration vs. failure-risk competition. Implemented because "
        "an uncertainty proxy (`ood_distance`) is present.",
        "",
        "All four requested pool modes were implemented; none were skipped, "
        "since both `material_id` and an uncertainty proxy are present in "
        "the existing v0.3.2 prediction data.",
        "",
        "## Metrics",
        "",
        "Per trial/policy/pool_mode/top_k: `failures_selected`, "
        "`successes_selected`, `failure_fraction`, `mean_failure_risk`, "
        "`mean_acquisition_score`, `best_known_candidate_found`, "
        "`top_k_overlap_with_lcb`, `mean_rank_shift`, "
        "`delta_failures_vs_lcb`, `delta_mean_risk_vs_lcb`. Full per-trial "
        f"data: `{_repo_path(table_path)}`.",
        "",
        "## Results",
        "",
    ]

    for pool_mode in POOL_MODES:
        lines.append(f"### {pool_mode}")
        lines.append("")
        lines.append(
            "| Policy | Top-k | Mean failures ± std | Mean risk ± std | "
            "Best-known found rate | Δ failures vs LCB ± std | Δ risk vs LCB ± std |"
        )
        lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
        for row in summary:
            if row["pool_mode"] != pool_mode:
                continue
            found_rate = row["best_known_candidate_found_rate"]
            found_str = "NA" if found_rate is None else f"{found_rate:.3f}"
            lines.append(
                f"| {row['policy']} | {row['top_k']} | "
                f"{row['mean_failures_selected']:.2f} ± {row['std_failures_selected']:.2f} | "
                f"{row['mean_failure_risk']:.3f} ± {row['std_failure_risk']:.3f} | "
                f"{found_str} | "
                f"{row['mean_delta_failures_vs_lcb']:+.2f} ± {row['std_delta_failures_vs_lcb']:.2f} | "
                f"{row['mean_delta_risk_vs_lcb']:+.3f} ± {row['std_delta_risk_vs_lcb']:.3f} |"
            )
        lines.append("")

    lines.extend([
        "## Comparison vs v0.5.0",
        "",
        _v050_comparison(summary, v050_table_path),
        "",
        "## Scientific Caveats",
        "",
        "1. This is an offline simulation using completed records; no new "
        "QE/PBE validation was performed.",
        "2. Failure-risk estimates are inherited from earlier reliability "
        "modeling (v0.3.2) and may have split-to-split variance, as "
        "documented in the v0.5.0 report.",
        "3. v0.5.1 stress-tests selection policy; it does not prove live DFT "
        "savings.",
        "4. `predicted_value` remains a constant 0.0 placeholder, as in "
        "v0.5.0; policy differences come from the uncertainty proxy and the "
        "failure-risk penalty, not a live energy prediction.",
        "5. `failure_enriched_pool` and `high_uncertainty_pool` resample "
        "existing real records (with replacement only if a target exceeds "
        "availability, which did not occur in this run); they do not "
        "fabricate new candidates or labels.",
        "6. Because ranking has no live predicted-energy signal (caveat 4), "
        "`best_known_candidate_found_rate` mainly reflects incidental "
        "overlap between the uncertainty/risk-based ranking and the single "
        "lowest-known-energy success in each trial's pool. It is not a "
        "measure of optimization quality and is expected to be low.",
        "7. Results should be interpreted as triage evidence, not a "
        "guarantee.",
        "",
        "## Safe Claims",
        "",
        _safe_claim(summary),
        "",
        "## Next Steps",
        "",
        "If failure-aware re-ranking shows a consistent advantage under "
        "stressed pools, the next step would be validating that advantage "
        "against a live GP/QE active-learning run (not yet performed here). "
        "v0.6 GNN-based surrogate modeling is out of scope until the offline "
        "failure-aware acquisition path itself is validated live.",
        "",
    ])
    return "\n".join(lines)


def _v050_comparison(summary: list[dict[str, object]], v050_table_path: str | Path) -> str:
    v050_rows = _read_v050_top10(v050_table_path)
    if not v050_rows:
        return (
            "v0.5.0 results file not found or unreadable; skipping numeric "
            "comparison. (Run `analysis/simulated_failure_aware_al_benchmark_v05.py` first.)"
        )
    normal_top10 = {
        row["policy"]: row for row in summary
        if row["pool_mode"] == "normal_pool" and row["top_k"] == 10
    }
    name_map = {
        "lcb_only": "lcb_only",
        "failure_aware_lcb_aggressive": "failure_aware_aggressive",
    }
    parts = [
        "v0.5.0 ran a single offline trial on the full natural candidate "
        "pool (no repeated trials). v0.5.1's `normal_pool` mode is the "
        "closest equivalent here, repeated over "
        f"{N_TRIALS} random sub-samples of that same pool:",
        "",
    ]
    for v050_name, v051_name in name_map.items():
        v050_row = v050_rows.get(v050_name)
        v051_row = normal_top10.get(v051_name)
        if v050_row is None or v051_row is None:
            continue
        parts.append(
            f"- `{v050_name}` (v0.5.0, single trial): "
            f"{v050_row['known_failures_selected']} known failures, "
            f"mean risk {float(v050_row['mean_failure_risk']):.3f}. "
            f"`{v051_name}` (v0.5.1, `normal_pool`, mean over {N_TRIALS} trials): "
            f"{v051_row['mean_failures_selected']:.2f} ± {v051_row['std_failures_selected']:.2f} "
            "known failures, "
            f"mean risk {v051_row['mean_failure_risk']:.3f} ± {v051_row['std_failure_risk']:.3f}."
        )
    return "\n".join(parts)


def _read_v050_top10(v050_table_path: str | Path) -> dict[str, dict[str, str]]:
    path = Path(v050_table_path)
    if not path.exists():
        return {}
    rows: dict[str, dict[str, str]] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row.get("top_k") == "10":
                rows[row["policy"]] = row
    return rows


def _safe_claim(summary: list[dict[str, object]]) -> str:
    """Decide, from the aggregate numbers themselves, which pre-approved
    sentence is supported. Never force a positive result."""
    top10 = [row for row in summary if row["top_k"] == 10]
    improved_pool_modes = []
    for pool_mode in POOL_MODES:
        aggressive = next(
            (r for r in top10 if r["pool_mode"] == pool_mode and r["policy"] == "failure_aware_aggressive"),
            None,
        )
        if aggressive is None:
            continue
        if aggressive["mean_delta_failures_vs_lcb"] < 0:
            improved_pool_modes.append(pool_mode)

    risk_reduced = all(
        r["mean_delta_risk_vs_lcb"] <= 0
        for r in top10
        if r["policy"] == "failure_aware_aggressive"
    )

    if improved_pool_modes:
        pools_str = ", ".join(f"`{p}`" for p in improved_pool_modes)
        claim = (
            "In repeated offline stress tests, failure-aware LCB reduced mean "
            f"predicted failure risk and, under {pools_str}, reduced known "
            "failed selections (mean delta vs. LCB-only < 0 at top-10) "
            "relative to LCB-only."
        )
    else:
        claim = (
            "Failure-aware LCB reduced predicted risk but did not "
            "consistently reduce known failed selections across stress-test "
            "pools."
        )
    if not risk_reduced:
        claim += (
            " Mean predicted risk reduction under the aggressive penalty was "
            "not consistent across every pool mode at top-10; see the "
            "per-pool tables above."
        )
    return claim


def _repo_path(path: str | Path) -> str:
    item = Path(path)
    try:
        return item.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(item)


# ── I/O ──────────────────────────────────────────────────────────────────────

def write_table(rows: list[dict[str, object]], path: str | Path) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def write_report(text: str, path: str | Path) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--table", default=str(DEFAULT_TABLE))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--n-trials", type=int, default=N_TRIALS)
    parser.add_argument("--base-seed", type=int, default=BASE_SEED)
    args = parser.parse_args(argv)

    base_candidates = load_candidates()
    rows = run_stress_benchmark(base_candidates, n_trials=args.n_trials, base_seed=args.base_seed)
    summary = aggregate_rows(rows)
    write_table(rows, args.table)
    write_report(
        render_report(rows, summary, args.table, len(base_candidates), args.n_trials),
        args.report,
    )
    print(f"Wrote {args.table}")
    print(f"Wrote {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
