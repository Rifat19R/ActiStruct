from __future__ import annotations

from actistruct.acquisition import (
    failure_aware_maximization_score,
    failure_aware_minimization_score,
    lcb_minimization_score,
    rank_candidates,
)
from analysis.failure_aware_acquisition_demo import build_demo_rows
from analysis.failure_aware_gp_acquisition_v04 import OUTPUT_COLUMNS, write_ranked_candidates
from qe_active_inverse_common import ActiveSystem, Variable, _rank_failure_aware_grid


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
    assert ranked[0]["acquisition_score"] == ranked[0]["failure_aware_score"]


def test_old_lcb_behavior_preserved_when_failure_risk_missing() -> None:
    candidates = [
        {"candidate_id": "a", "predicted_value": 1.0, "uncertainty": 0.05},
        {"candidate_id": "b", "predicted_value": 0.8, "uncertainty": 0.0},
    ]

    ranked = rank_candidates(candidates, objective="minimize", beta=2.0, gamma=1.0)

    assert [row["candidate_id"] for row in ranked] == ["b", "a"]
    assert ranked[0]["acquisition_score"] == lcb_minimization_score(0.8, 0.0, beta=2.0)
    assert ranked[0]["failure_risk"] == ""
    assert ranked[0]["risk_flag"] == "missing"
    assert ranked[0]["base_lcb_score"] == ranked[0]["acquisition_score"]
    assert "rank_shift" in ranked[0]


def test_gamma_zero_preserves_old_ranking() -> None:
    candidates = [
        {"candidate_id": "risky", "predicted_value": 0.0, "uncertainty": 0.0, "failure_risk": 1.0},
        {"candidate_id": "safe", "predicted_value": 0.1, "uncertainty": 0.0, "failure_risk": 0.0},
    ]

    ranked = rank_candidates(candidates, objective="minimize", beta=2.0, gamma=0.0)

    assert [row["candidate_id"] for row in ranked] == ["risky", "safe"]
    assert all(row["failure_penalty"] == 0.0 for row in ranked)


def test_gamma_penalizes_risky_candidates_without_rejecting() -> None:
    candidates = [
        {"candidate_id": "risky", "predicted_value": 0.0, "uncertainty": 0.0, "failure_risk": 1.0},
        {"candidate_id": "safe", "predicted_value": 0.1, "uncertainty": 0.0, "failure_risk": 0.0},
    ]

    ranked = rank_candidates(candidates, objective="minimize", beta=2.0, gamma=1.0)

    assert [row["candidate_id"] for row in ranked] == ["safe", "risky"]
    assert {row["candidate_id"] for row in ranked} == {"safe", "risky"}


def test_threshold_creates_correct_risk_flag() -> None:
    candidates = [
        {"candidate_id": "low", "predicted_value": 0.0, "uncertainty": 0.0, "failure_risk": 0.09},
        {"candidate_id": "elevated", "predicted_value": 1.0, "uncertainty": 0.0, "failure_risk": 0.10},
    ]

    ranked = rank_candidates(candidates, objective="minimize", failure_risk_threshold=0.10)
    flags = {row["candidate_id"]: row["risk_flag"] for row in ranked}

    assert flags == {"low": "low", "elevated": "elevated"}


def test_bad_failure_risk_does_not_crash_and_is_missing() -> None:
    candidates = [
        {"candidate_id": "bad", "predicted_value": 0.0, "uncertainty": 0.0, "failure_risk": "not-a-number"},
        {"candidate_id": "nan", "predicted_value": 1.0, "uncertainty": 0.0, "failure_risk": float("nan")},
        {"candidate_id": "clip", "predicted_value": 2.0, "uncertainty": 0.0, "failure_risk": 3.0},
    ]

    ranked = rank_candidates(candidates)
    by_id = {row["candidate_id"]: row for row in ranked}

    assert by_id["bad"]["risk_flag"] == "missing"
    assert by_id["nan"]["risk_flag"] == "missing"
    assert by_id["clip"]["failure_risk"] == 1.0


def test_negative_uncertainty_rejected() -> None:
    import pytest

    with pytest.raises(ValueError, match="uncertainty"):
        rank_candidates([
            {"candidate_id": "bad", "predicted_value": 0.0, "uncertainty": -0.1},
        ])


def test_output_csv_has_required_columns(tmp_path) -> None:
    rows = rank_candidates([
        {"candidate_id": "a", "predicted_value": 0.0, "uncertainty": 0.0, "failure_risk": 0.1},
    ])
    out = tmp_path / "ranked.csv"

    write_ranked_candidates(rows, out)

    import csv
    with out.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        assert set(OUTPUT_COLUMNS) <= set(reader.fieldnames or [])


def test_actual_gp_proposal_path_can_call_failure_aware_ranking() -> None:
    system = _system_with_risk(lambda params: 0.9 if params[0] < 0.5 else 0.0)

    ranked = _rank_failure_aware_grid(_FakeModel(), system, [[0.0], [1.0]])

    assert ranked
    assert ranked[0]["candidate_id"] == "1"
    assert ranked[0]["rank_without_failure_risk"] == 2
    assert ranked[0]["rank_shift"] > 0


def test_actual_gp_path_falls_back_when_failure_risk_missing() -> None:
    system = _system_with_risk(lambda params: None)

    ranked = _rank_failure_aware_grid(_FakeModel(), system, [[0.0], [1.0]])

    assert ranked == []


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


class _FakeModel:
    def predict(self, values):
        import numpy as np

        arr = np.atleast_2d(np.array(values, dtype=float))
        mean = arr[:, 0] * 0.2
        std = np.zeros(len(arr))
        return mean, std


def _system_with_risk(provider) -> ActiveSystem:
    return ActiveSystem(
        key="unit",
        title="unit",
        builder=lambda x: None,
        variables=(Variable("x", 0.0, 1.0, (0.0, 1.0)),),
        pseudopotentials={"H": "H.UPF"},
        ecutwfc=30.0,
        ecutrho=240.0,
        kpts=(1, 1, 1),
        failure_risk_provider=provider,
        failure_risk_gamma_mode="aggressive",
    )
