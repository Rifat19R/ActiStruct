import pytest

from _load import load_script

env_mod = load_script("00_inspect_environment.py")


def test_actistruct_import_check_returns_expected_keys():
    result = env_mod.check_actistruct_import()
    assert set(result.keys()) == {"package", "version", "location", "importable"}


def test_actistruct_is_importable_in_this_environment():
    result = env_mod.check_actistruct_import()
    assert result["importable"] is True
    assert result["package"] in ("actistruct", "inverse_active")


def test_check_pseudo_dir_handles_missing_directory(tmp_path):
    missing_dir = tmp_path / "does_not_exist"
    result = env_mod.check_pseudo_dir(str(missing_dir), ["Fe", "C"])
    assert result["exists"] is False
    assert result["elements_found"] == {}


def test_check_pseudo_dir_finds_known_elements():
    from _common import load_yaml
    project_cfg = load_yaml("configs/project_config.yaml")
    result = env_mod.check_pseudo_dir(project_cfg["paths"]["pseudo_dir"], ["Fe", "C", "H", "Ni", "O", "Cr"])
    if not result["exists"]:
        pytest.skip(
            f"SSSP pseudo dir not found at {project_cfg['paths']['pseudo_dir']} "
            "(local SSSP install required — skipped in CI)"
        )
    for element in ("Fe", "C", "H", "Ni", "O", "Cr"):
        assert result["elements_found"][element], f"no pseudopotential found for {element}"
