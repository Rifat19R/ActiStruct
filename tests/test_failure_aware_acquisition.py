from __future__ import annotations

from actistruct.acquisition import (
    failure_aware_maximization_score,
    failure_aware_minimization_score,
    rank_candidates,
)
from analysis.failure_aware_acquisition_demo import build_demo_rows


def test_failure_penalty_increases_minimization_score() -> None:
    low_risk = failure_aware_minimization_score(0.0, 0.0, 0.1, failure_penalty=1.0)
    high_risk = failure_aware_minimization_score(0.0, 0.0, 0.9, failure_penalty=1.0)

    assert low_risk < high_risk


def test_failure_penalty_decreases_maximization_score() -> None:
    low_risk = failure_aware_maximization_score(1.0, 0.0, 0.1, failure_penalty=1.0)
    high_risk = failure_aware_maximization_score(1.0, 0.0, 0.9, failure_penalty=1.0)

    assert low_risk > high_risk


def test_rank_candidates_prefers_low_failure_risk_for_equal_value() -> None:
    candidates = [
        {"id": "bad", "predicted_value": 0.0, "uncertainty": 0.0, "failure_risk": 0.9},
        {"id": "good", "predicted_value": 0.0, "uncertainty": 0.0, "failure_risk": 0.1},
    ]

    ranked = rank_candidates(candidates, objective="minimize", failure_penalty=1.0)

    assert ranked[0]["id"] == "good"
    assert ranked[0]["failure_aware_score"] < ranked[1]["failure_aware_score"]


def test_demo_penalty_changes_top_ranked_risk() -> None:
    candidates = [
        {
            "record_id": "1",
            "material_id": "risky",
            "failure_label": "qe_error",
            "true_success": 0,
            "predicted_value": 0.0,
            "uncertainty": 0.0,
            "failure_risk": 0.9,
        },
        {
            "record_id": "2",
            "material_id": "safe",
            "failure_label": "success",
            "true_success": 1,
            "predicted_value": 0.0,
            "uncertainty": 0.0,
            "failure_risk": 0.1,
        },
    ]

    rows = build_demo_rows(candidates, failure_penalties=(0.0, 1.0))
    no_penalty_top = [row for row in rows if row["failure_penalty"] == 0.0 and row["rank"] == 1][0]
    penalty_top = [row for row in rows if row["failure_penalty"] == 1.0 and row["rank"] == 1][0]

    assert no_penalty_top["material_id"] == "risky"
    assert penalty_top["material_id"] == "safe"

