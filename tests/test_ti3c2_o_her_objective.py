"""Guard tests for the Ti3C2-O HER campaign objective.

HER screening targets thermoneutral adsorption, so acquisition and best-site
selection must prefer DeltaG_H closest to zero rather than the most negative
adsorption free energy.
"""
from __future__ import annotations

import importlib


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
