"""Tests for scripts/11_dataset_loader.py."""
import math
from pathlib import Path

import numpy as np
import pytest

from _load import load_script

loader = load_script("11_dataset_loader.py")
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_load_dataset_candidates_only_has_12_rows():
    ds = loader.load_dataset(target="delta_e_meV", candidates_only=True)
    assert ds.n_samples == 12


def test_load_dataset_all_rows_with_energy_target():
    ds = loader.load_dataset(target="final_energy_ry", candidates_only=False)
    assert ds.n_samples == 16


def test_load_dataset_combined_feature_count():
    ds = loader.load_dataset(feature_set="combined", target="final_energy_ry")
    # 10 geometric + 21 Coulomb = 31
    assert ds.n_features == 31


def test_load_dataset_coulomb_only():
    ds = loader.load_dataset(feature_set="coulomb", target="final_energy_ry")
    assert ds.n_features == 21
    assert all(n.startswith("cm_eig_") for n in ds.feature_names)


def test_load_dataset_geometric_only():
    ds = loader.load_dataset(feature_set="geometric", target="final_energy_ry")
    assert ds.n_features == 10
    assert all(n in loader.GEO_FEATURES for n in ds.feature_names)


def test_no_nan_in_X_after_loading():
    """After imputation all feature values must be finite."""
    ds = loader.load_dataset(target="final_energy_ry")
    assert np.all(np.isfinite(ds.X)), "X contains NaN or Inf after imputation"


def test_no_nan_in_y_after_loading_delta_e():
    """Candidates-only delta_e must have no NaN targets."""
    ds = loader.load_dataset(target="delta_e_meV", candidates_only=True)
    assert np.all(np.isfinite(ds.y)), "y contains NaN for delta_e_meV target"


def test_ferrocene_co_features_imputed():
    """Ferrocene has no C-O bonds: co_mean and co_std must be imputed (not NaN)."""
    ds = loader.load_dataset(feature_set="geometric", target="final_energy_ry")
    idx = ds.system_ids.index("ferrocene")
    co_mean_idx = ds.feature_names.index("co_mean_angstrom")
    co_std_idx = ds.feature_names.index("co_std_angstrom")
    assert math.isfinite(ds.X[idx, co_mean_idx]), "co_mean should be imputed for ferrocene"
    assert math.isfinite(ds.X[idx, co_std_idx]), "co_std should be imputed for ferrocene"
    assert "co_mean_angstrom" in ds.imputed_cols
    assert "co_std_angstrom" in ds.imputed_cols


def test_train_test_split_sizes():
    ds = loader.load_dataset(target="delta_e_meV", candidates_only=True)
    train, test = loader.train_test_split_by_system(ds, ["ferrocene"])
    assert train.n_samples + test.n_samples == ds.n_samples
    assert test.n_samples == 3   # 3 ferrocene candidates
    assert train.n_samples == 9  # remaining 9


def test_train_test_split_no_leakage():
    """No system should appear in both train and test."""
    ds = loader.load_dataset(target="delta_e_meV", candidates_only=True)
    for held_out in ["ferrocene", "ni_co4", "cr_co6", "fe_co5"]:
        train, test = loader.train_test_split_by_system(ds, [held_out])
        train_systems = {sid.split("__")[0] for sid in train.system_ids}
        test_systems = {sid.split("__")[0] for sid in test.system_ids}
        assert train_systems.isdisjoint(test_systems), (
            f"Data leakage for held_out={held_out}: "
            f"overlap={train_systems & test_systems}"
        )


def test_leave_one_out_splits_cover_all_rows_once():
    ds = loader.load_dataset(feature_set="coulomb", target="final_energy_ev")
    splits = loader.leave_one_out_splits(ds)
    assert len(splits) == ds.n_samples == 16
    held_out = []
    for train, test in splits:
        assert train.n_samples == 15
        assert test.n_samples == 1
        assert set(train.system_ids).isdisjoint(test.system_ids)
        held_out.extend(test.system_ids)
    assert sorted(held_out) == sorted(ds.system_ids)


def test_invalid_target_raises():
    with pytest.raises(ValueError, match="target must be one of"):
        loader.load_dataset(target="not_a_real_target")


def test_invalid_feature_set_raises():
    with pytest.raises(ValueError, match="feature_set must be"):
        loader.load_dataset(feature_set="rac_descriptors")


def test_feature_names_match_X_columns():
    ds = loader.load_dataset(target="final_energy_ry")
    assert len(ds.feature_names) == ds.X.shape[1]


def test_system_ids_match_X_rows():
    ds = loader.load_dataset(target="final_energy_ry")
    assert len(ds.system_ids) == ds.X.shape[0]
