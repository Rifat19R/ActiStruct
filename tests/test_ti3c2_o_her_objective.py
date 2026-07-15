"""Guard tests for the Ti3C2-O HER campaign objective.

HER screening targets thermoneutral adsorption, so acquisition and best-site
selection must prefer DeltaG_H closest to zero rather than the most negative
adsorption free energy.
"""
from __future__ import annotations

import importlib
import json

import numpy as np
import pytest


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


def test_al_driver_uses_oracle_frozen_seed_points():
    driver = importlib.import_module("examples.manual_qe.run_ti3c2_o_al_loop")
    oracle = importlib.import_module("examples.manual_qe.ti3c2_o_her_qe_active_inverse")

    assert driver.SEED_POINTS == list(oracle.CONFIG.initial_points)
    assert len(driver.SEED_POINTS) == 6


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
        track_oracle_query=1,
        physical_new_dft_call=True,
        cache_hit=False,
        duplicate=False,
        delta_g_h=-0.03,
        best_delta_g_h=-0.03,
        n_points=7,
        wall_s=5300.0,
        cumulative_track_oracle_queries=1,
        cumulative_physical_new_dft_calls=1,
    )
    driver.append_campaign_record(log_path, row)

    loaded = json.loads(log_path.read_text(encoding="utf-8").strip())
    assert loaded["track"] == "plain-GP"
    assert loaded["status"] == "success"
    assert loaded["abs_delta_g_h"] == 0.03
    assert loaded["best_abs_delta_g_h"] == 0.03
    assert loaded["new_dft_call"] is True
    assert loaded["track_oracle_query"] == 1
    assert loaded["physical_new_dft_call"] is True
    assert loaded["cumulative_track_oracle_queries"] == 1
    assert loaded["cumulative_physical_new_dft_calls"] == 1
    assert loaded["cache_hit"] is False
    assert loaded["duplicate"] is False


def test_failed_campaign_record_preserves_current_best():
    driver = importlib.import_module("examples.manual_qe.run_ti3c2_o_al_loop")

    row = driver.build_campaign_record(
        iteration=2,
        track_name="GNN",
        u=0.5,
        v=0.5,
        pred_mean=0.2,
        pred_std=0.1,
        acquisition_score=0.1,
        status="failed",
        track_oracle_query=1,
        physical_new_dft_call=True,
        cache_hit=False,
        duplicate=False,
        delta_g_h=None,
        best_delta_g_h=-0.04,
        n_points=6,
        wall_s=120.0,
        cumulative_track_oracle_queries=2,
        cumulative_physical_new_dft_calls=2,
    )

    assert row["status"] == "failed"
    assert row["best_delta_g_h"] == -0.04
    assert row["best_abs_delta_g_h"] == 0.04


def test_duplicate_observation_is_not_trainable():
    driver = importlib.import_module("examples.manual_qe.run_ti3c2_o_al_loop")

    assert driver.should_add_observation(is_duplicate=True, delta_g_h=-0.02) is False
    assert driver.should_add_observation(is_duplicate=False, delta_g_h=None) is False
    assert driver.should_add_observation(is_duplicate=False, delta_g_h=-0.02) is True


def test_protocol_cache_file_and_key_are_fingerprinted():
    oracle = importlib.import_module("examples.manual_qe.ti3c2_o_her_qe_active_inverse")

    assert oracle.CACHE_FILE.name == "ti3c2_o_her_low_protocol_v1_amend1.pkl"
    key = oracle.delta_g_cache_key((0.0, 0.0))
    assert "campaign=ti3c2o-lf-v1-amend1" in key
    assert "constraint=fixedline-z" in key
    assert "relax_fmax=0.050000" in key
    assert "relax_steps=50" in key
    assert "degauss=0.02" in key
    assert "conv_thr=1e-8" in key


def test_run_energy_rejects_unconverged_bfgs(tmp_path, monkeypatch):
    oracle = importlib.import_module("examples.manual_qe.ti3c2_o_her_qe_active_inverse")

    class FakeAtoms:
        calc = None

        def get_forces(self):
            return np.array([[0.0, 0.0, 0.2]])

        def get_potential_energy(self):
            raise AssertionError("Unconverged relaxation must not read/cache energy")

    class FakeBFGS:
        nsteps = 50

        def __init__(self, atoms, logfile, trajectory):
            self.atoms = atoms

        def run(self, fmax, steps):
            return False

    monkeypatch.setattr(oracle, "get_calculator", lambda *args, **kwargs: object())
    monkeypatch.setattr(oracle, "BFGS", FakeBFGS)

    with pytest.raises(RuntimeError, match="BFGS did not reach"):
        oracle.run_energy(FakeAtoms(), tmp_path, "unconverged", (1, 1, 1), relax=True)

    metadata = json.loads((tmp_path / "run_metadata.json").read_text(encoding="utf-8"))
    assert metadata["converged"] is False
    assert metadata["bfgs_steps"] == 50
    assert metadata["final_max_force_ev_per_a"] == 0.2


def test_grid_campaign_uses_exact_seed_coordinates_only():
    from pathlib import Path

    source = Path("examples/manual_qe/run_ti3c2_o_grid_campaign.py").read_text(encoding="utf-8")
    assert "(0.02, 0.0)" not in source
    assert "not replacing it" in source
