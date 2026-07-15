"""Guard tests for the Ti3C2-O HER campaign objective.

HER screening targets thermoneutral adsorption, so acquisition and best-site
selection must prefer DeltaG_H closest to zero rather than the most negative
adsorption free energy.
"""
from __future__ import annotations

import importlib
import json


def test_thermoneutral_lcb_prefers_near_zero_over_strong_binding():
    driver = importlib.import_module("examples.manual_qe.run_ti3c2_o_al_loop")

    strong_binding = driver.thermoneutral_lcb(mean_delta_g_h=-2.0, std=0.01)
    near_zero = driver.thermoneutral_lcb(mean_delta_g_h=-0.05, std=0.01)

    assert near_zero < strong_binding


def test_thermoneutral_lcb_still_rewards_uncertainty():
    driver = importlib.import_module("examples.manual_qe.run_ti3c2_o_al_loop")

    low_uncertainty = driver.thermoneutral_lcb(mean_delta_g_h=0.20, std=0.01)
    high_uncertainty = driver.thermoneutral_lcb(mean_delta_g_h=0.20, std=0.10)

    assert high_uncertainty < low_uncertainty


def test_best_thermoneutral_delta_uses_absolute_value():
    driver = importlib.import_module("examples.manual_qe.run_ti3c2_o_al_loop")

    assert driver.best_thermoneutral_delta([-2.0, -0.05, 0.08, 0.50]) == -0.05


def test_single_track_best_observed_uses_absolute_delta_g():
    oracle = importlib.import_module("examples.manual_qe.ti3c2_o_her_qe_active_inverse")

    point, value = oracle.best_observed(
        [(0.0, 0.0), (0.2, 0.2), (0.4, 0.4)],
        [-1.2, 0.04, -0.08],
    )

    assert point == (0.2, 0.2)
    assert value == 0.04


def test_random_track_is_deterministic_from_same_seed():
    driver = importlib.import_module("examples.manual_qe.run_ti3c2_o_al_loop")
    points = [(0.0, 0.0), (1.0 / 3.0, 1.0 / 6.0)]
    deltas = [-0.2, 0.1]

    first = driver.RandomTrack(points, deltas, random_state=42)
    second = driver.RandomTrack(points, deltas, random_state=42)

    assert first.propose() == second.propose()


def test_campaign_record_schema_and_jsonl_persistence(tmp_path):
    driver = importlib.import_module("examples.manual_qe.run_ti3c2_o_al_loop")
    log_path = tmp_path / "campaign.jsonl"

    row = driver.build_campaign_record(
        iteration=1,
        track_name="plain-GP",
        u=0.12,
        v=0.34,
        pred_mean=-0.08,
        pred_std=0.04,
        acquisition_score=0.04,
        status="success",
        new_dft_call=True,
        cache_hit=False,
        duplicate=False,
        delta_g_h=-0.03,
        best_delta_g_h=-0.03,
        n_points=7,
        wall_s=5300.0,
    )
    driver.append_campaign_record(log_path, row)

    loaded = json.loads(log_path.read_text(encoding="utf-8").strip())
    assert loaded["track"] == "plain-GP"
    assert loaded["status"] == "success"
    assert loaded["abs_delta_g_h"] == 0.03
    assert loaded["best_abs_delta_g_h"] == 0.03
    assert loaded["new_dft_call"] is True
    assert loaded["cache_hit"] is False
    assert loaded["duplicate"] is False
