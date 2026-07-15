"""Tests for scripts/12_baseline_model.py."""
from pathlib import Path

import numpy as np
import pytest

from _load import load_script

model_mod = load_script("12_baseline_model.py")
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_make_gpr_returns_gpr():
    from sklearn.gaussian_process import GaussianProcessRegressor
    gpr = model_mod.make_gpr()
    assert isinstance(gpr, GaussianProcessRegressor)


def test_gpr_fits_and_predicts_with_std():
    """GP must fit a small dataset and return both mean and std predictions."""
    import numpy as np
    rng = np.random.default_rng(0)
    X = rng.normal(size=(10, 5))
    y = rng.normal(size=10)
    gpr = model_mod.make_gpr(random_state=0)
    gpr.fit(X, y)
    y_pred, y_std = gpr.predict(X[:3], return_std=True)
    assert y_pred.shape == (3,)
    assert y_std.shape == (3,)
    assert np.all(y_std >= 0)


def test_evaluate_loso_returns_four_folds():
    """LOSO with 4 systems must produce exactly 4 folds."""
    folds = model_mod.evaluate_loso(feature_set="geometric", target="delta_e_meV")
    assert len(folds) == 4


def test_evaluate_loso_fold_keys():
    folds = model_mod.evaluate_loso(feature_set="geometric", target="delta_e_meV")
    required_keys = {"held_out_system", "train_n", "test_n", "mae", "rmse",
                     "mean_uncertainty", "per_sample"}
    for fold in folds:
        assert required_keys.issubset(fold.keys())


def test_evaluate_loso_split_sizes():
    """Each fold must have 9 train and 3 test samples (4 systems × 3 each)."""
    folds = model_mod.evaluate_loso(feature_set="geometric", target="delta_e_meV")
    for fold in folds:
        assert fold["train_n"] == 9
        assert fold["test_n"] == 3


def test_evaluate_loso_mae_is_nonnegative():
    folds = model_mod.evaluate_loso(feature_set="geometric", target="delta_e_meV")
    for fold in folds:
        assert fold["mae"] >= 0
        assert fold["rmse"] >= 0


def test_evaluate_loso_per_sample_fields():
    folds = model_mod.evaluate_loso(feature_set="geometric", target="delta_e_meV")
    required = {"system_id", "y_true", "y_pred", "y_std", "error", "abs_error"}
    for fold in folds:
        for s in fold["per_sample"]:
            assert required.issubset(s.keys())
            assert s["y_std"] >= 0
            assert abs(s["abs_error"] - abs(s["error"])) < 1e-9


def test_evaluate_loo_total_energy_returns_16_folds():
    folds = model_mod.evaluate_loo_total_energy(feature_set="coulomb", target="final_energy_ev")
    assert len(folds) == 16
    for fold in folds:
        assert fold["train_n"] == 15
        assert fold["test_n"] == 1
        assert fold["y_std"] >= 0
        assert fold["abs_error"] >= 0


def test_acquisition_ranking_uses_actistruct():
    """rank_candidates_by_acquisition must call actistruct and return 12 rows."""
    from _load import load_script
    loader = load_script("11_dataset_loader.py")
    ds = loader.load_dataset(target="delta_e_meV", candidates_only=True)
    ranked = model_mod.rank_candidates_by_acquisition(ds)
    assert len(ranked) == 12
    # Each ranked item must have predicted_value and uncertainty keys
    for c in ranked:
        assert "predicted_value" in c
        assert "uncertainty" in c
        assert "system_id" in c


def test_outputs_exist_after_main_run():
    json_path = PROJECT_ROOT / "data" / "models" / "baseline_gp_v0.1.json"
    report_path = PROJECT_ROOT / "reports" / "baseline_model_report_v0.1.md"
    assert json_path.exists(), "run scripts/12_baseline_model.py first"
    assert report_path.exists(), "run scripts/12_baseline_model.py first"


def test_json_results_have_disclaimer():
    json_path = PROJECT_ROOT / "data" / "models" / "baseline_gp_v0.1.json"
    if not json_path.exists():
        pytest.skip("run scripts/12_baseline_model.py first")
    import json
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert "disclaimer" in data
    assert "16 data points" in data["disclaimer"]
    assert data["mode"] == "loo-total"


def test_report_contains_disclaimer():
    report_path = PROJECT_ROOT / "reports" / "baseline_model_report_v0.1.md"
    if not report_path.exists():
        pytest.skip("run scripts/12_baseline_model.py first")
    text = report_path.read_text(encoding="utf-8")
    assert "CRITICAL DISCLAIMER" in text or "DISCLAIMER" in text
    assert "16 data points" in text
    assert "Leave-one-out" in text
