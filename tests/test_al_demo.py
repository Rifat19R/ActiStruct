"""Tests for scripts/14_active_learning_demo.py."""
from pathlib import Path

import numpy as np
import pytest

from _load import load_script

al_mod = load_script("14_active_learning_demo.py")
PROJECT_ROOT = Path(__file__).resolve().parent.parent

FIXED_HOLDOUT_IDS = al_mod.FIXED_HOLDOUT_IDS


# ──────────────────────────────────────────────
# Simulated AL loop
# ──────────────────────────────────────────────

def test_simulate_al_loop_returns_8_steps():
    """Pool has 12 - 4 holdout = 8 candidates so loop must produce exactly 8 steps."""
    steps = al_mod.simulate_al_loop(feature_set="geometric", rng_seed=0)
    assert len(steps) == 8


def test_simulate_al_loop_covers_all_pool_candidates():
    """Every non-holdout candidate must be selected exactly once."""
    from _load import load_script
    loader = load_script("11_dataset_loader.py")
    ds = loader.load_dataset(target="delta_e_meV", candidates_only=True)
    pool_ids = {sid for sid in ds.system_ids if sid not in FIXED_HOLDOUT_IDS}

    steps = al_mod.simulate_al_loop(feature_set="geometric", rng_seed=0)
    selected_ids = [s["selected_id"] for s in steps]
    assert set(selected_ids) == pool_ids, (
        f"Selected {set(selected_ids)} does not match expected pool {pool_ids}"
    )


def test_simulate_al_loop_step_keys():
    """Each step dict must have the required keys."""
    steps = al_mod.simulate_al_loop(feature_set="geometric", rng_seed=0)
    required = {
        "step", "selected_id", "y_true", "predicted_value",
        "uncertainty_at_selection", "pool_mean_uncertainty",
        "holdout_mae", "holdout_mean_std", "train_n",
    }
    for s in steps:
        assert required.issubset(s.keys()), f"Missing keys: {required - s.keys()}"


def test_simulate_al_loop_train_n_increments():
    """train_n must grow by 1 each step."""
    steps = al_mod.simulate_al_loop(feature_set="geometric", rng_seed=0)
    for i, s in enumerate(steps):
        assert s["train_n"] == i + 1


def test_simulate_al_loop_step_numbers_sequential():
    steps = al_mod.simulate_al_loop(feature_set="geometric", rng_seed=0)
    for i, s in enumerate(steps):
        assert s["step"] == i + 1


def test_simulate_al_loop_holdout_mae_nonnegative():
    steps = al_mod.simulate_al_loop(feature_set="geometric", rng_seed=0)
    for s in steps:
        assert s["holdout_mae"] >= 0.0


def test_simulate_al_loop_no_holdout_candidates_selected():
    """AL loop must never select a holdout candidate."""
    steps = al_mod.simulate_al_loop(feature_set="geometric", rng_seed=0)
    for s in steps:
        assert s["selected_id"] not in FIXED_HOLDOUT_IDS


def test_simulate_al_loop_deterministic_with_same_seed():
    """Same rng_seed must produce the same selection order."""
    steps_a = al_mod.simulate_al_loop(feature_set="geometric", rng_seed=7)
    steps_b = al_mod.simulate_al_loop(feature_set="geometric", rng_seed=7)
    for a, b in zip(steps_a, steps_b):
        assert a["selected_id"] == b["selected_id"]


def test_simulate_al_loop_y_true_matches_dataset():
    """Reported y_true values must match the real DFT data."""
    from _load import load_script
    loader = load_script("11_dataset_loader.py")
    ds = loader.load_dataset(target="delta_e_meV", candidates_only=True)
    y_by_id = dict(zip(ds.system_ids, ds.y))

    steps = al_mod.simulate_al_loop(feature_set="geometric", rng_seed=0)
    for s in steps:
        expected = y_by_id[s["selected_id"]]
        assert abs(s["y_true"] - expected) < 1e-6


# ──────────────────────────────────────────────
# AL vs random comparison
# ──────────────────────────────────────────────

def test_compare_al_vs_random_result_keys():
    result = al_mod.compare_al_vs_random(
        feature_set="geometric", n_random_trials=5, rng_seed=0
    )
    required = {
        "al_steps", "al_holdout_mae", "random_mean_mae",
        "random_std_mae", "n_random_trials", "holdout_ids",
    }
    assert required.issubset(result.keys())


def test_compare_al_vs_random_random_mae_length():
    result = al_mod.compare_al_vs_random(
        feature_set="geometric", n_random_trials=5, rng_seed=0
    )
    assert len(result["random_mean_mae"]) == 8
    assert len(result["random_std_mae"]) == 8


def test_compare_al_vs_random_mae_nonnegative():
    result = al_mod.compare_al_vs_random(
        feature_set="geometric", n_random_trials=5, rng_seed=0
    )
    assert all(v >= 0 for v in result["random_mean_mae"])
    assert all(v >= 0 for v in result["al_holdout_mae"])


# ──────────────────────────────────────────────
# Convergence correlation
# ──────────────────────────────────────────────

def test_convergence_correlation_keys():
    result = al_mod.analyze_convergence_correlation(feature_set="geometric")
    required = {"pearson_r", "pearson_p", "spearman_r", "spearman_p", "per_candidate"}
    assert required.issubset(result.keys())


def test_convergence_correlation_r_in_range():
    result = al_mod.analyze_convergence_correlation(feature_set="geometric")
    assert -1.0 <= result["pearson_r"] <= 1.0
    assert -1.0 <= result["spearman_r"] <= 1.0


def test_convergence_correlation_has_12_candidates():
    result = al_mod.analyze_convergence_correlation(feature_set="geometric")
    assert len(result["per_candidate"]) == 12


def test_convergence_correlation_scf_iters_positive():
    result = al_mod.analyze_convergence_correlation(feature_set="geometric")
    for c in result["per_candidate"]:
        assert c["scf_iterations"] > 0, f"{c['system_id']} has non-positive SCF iters"


# ──────────────────────────────────────────────
# Output files
# ──────────────────────────────────────────────

def test_outputs_exist_after_main_run():
    json_path = PROJECT_ROOT / "data" / "models" / "al_demo_v0.1.json"
    report_path = PROJECT_ROOT / "reports" / "active_learning_demo_v0.1.md"
    assert json_path.exists(), "run scripts/14_active_learning_demo.py first"
    assert report_path.exists(), "run scripts/14_active_learning_demo.py first"


def test_json_has_disclaimer():
    json_path = PROJECT_ROOT / "data" / "models" / "al_demo_v0.1.json"
    if not json_path.exists():
        pytest.skip("run scripts/14_active_learning_demo.py first")
    import json
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert "disclaimer" in data
    assert "12" in data["disclaimer"]


def test_report_contains_disclaimer():
    report_path = PROJECT_ROOT / "reports" / "active_learning_demo_v0.1.md"
    if not report_path.exists():
        pytest.skip("run scripts/14_active_learning_demo.py first")
    text = report_path.read_text(encoding="utf-8")
    assert "DISCLAIMER" in text or "disclaimer" in text.lower()
    assert "12" in text


def test_report_contains_al_loop_table():
    report_path = PROJECT_ROOT / "reports" / "active_learning_demo_v0.1.md"
    if not report_path.exists():
        pytest.skip("run scripts/14_active_learning_demo.py first")
    text = report_path.read_text(encoding="utf-8")
    assert "Step" in text
    assert "ferrocene" in text


def test_report_contains_convergence_section():
    report_path = PROJECT_ROOT / "reports" / "active_learning_demo_v0.1.md"
    if not report_path.exists():
        pytest.skip("run scripts/14_active_learning_demo.py first")
    text = report_path.read_text(encoding="utf-8")
    assert "Convergence" in text or "convergence" in text
    assert "Pearson" in text or "pearson" in text.lower()
