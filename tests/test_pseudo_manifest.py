from pathlib import Path

from _load import load_script

scan_mod = load_script("02_scan_pseudos.py")
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_find_candidates_matches_case_insensitive_prefix(tmp_path):
    (tmp_path / "Fe.pbe-spn-kjpaw_psl.0.2.1.UPF").write_text("dummy")
    (tmp_path / "ni_pbe_v1.4.uspp.F.UPF").write_text("dummy")
    (tmp_path / "Fermium_unrelated.UPF").write_text("dummy")

    fe_matches = scan_mod.find_candidates(tmp_path, "Fe")
    assert "Fe.pbe-spn-kjpaw_psl.0.2.1.UPF" in fe_matches
    assert "Fermium_unrelated.UPF" not in fe_matches

    ni_matches = scan_mod.find_candidates(tmp_path, "Ni")
    assert "ni_pbe_v1.4.uspp.F.UPF" in ni_matches


def test_manifest_file_exists_and_is_ready():
    manifest_path = PROJECT_ROOT / "configs" / "pseudo_manifest_required.yaml"
    assert manifest_path.exists(), "run scripts/02_scan_pseudos.py before this test"
    import yaml
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "ready"
    assert manifest["missing_elements"] == []
    for element in ("Fe", "C", "H", "Ni", "O", "Cr"):
        assert manifest["elements"][element]["exists"] is True
