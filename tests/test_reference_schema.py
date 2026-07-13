from pathlib import Path

from _load import load_script

ref_mod = load_script("03_collect_reference_stub.py")
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_stub_has_four_primary_systems():
    stub = ref_mod.build_stub()
    assert set(stub.keys()) == {"ferrocene", "ni_co4", "cr_co6", "fe_co5"}


def test_stub_values_are_unverified_with_no_fabricated_numbers():
    stub = ref_mod.build_stub()
    for complex_id, entry in stub.items():
        assert entry["status"] == "needs_manual_review", complex_id
        rv = entry["reference_values"]
        assert rv["bond_lengths"] == []
        assert rv["angles"] == []
        assert rv["relative_energies"] == []
        assert rv["barriers"] == []
        assert entry["sources"] == {}


def test_stub_identity_metadata_matches_plan_systems():
    stub = ref_mod.build_stub()
    assert stub["ferrocene"]["formula"] == "Fe(C5H5)2"
    assert stub["ni_co4"]["formula"] == "Ni(CO)4"
    assert stub["cr_co6"]["formula"] == "Cr(CO)6"
    assert stub["fe_co5"]["formula"] == "Fe(CO)5"
    for entry in stub.values():
        assert entry["charge"] == 0


def test_reference_yaml_file_exists_on_disk():
    ref_path = PROJECT_ROOT / "references" / "reference_values_tmc_v0.yaml"
    assert ref_path.exists(), "run scripts/03_collect_reference_stub.py before this test"
