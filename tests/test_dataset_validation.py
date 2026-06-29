import json
from pathlib import Path

from _load import load_script

val_mod = load_script("08_validate_dataset.py")
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def ferrocene_ring_positions():
    """Real Cp-ring topology: C-C ring neighbors ~1.40 A apart, but 1,3
    transannular C-C pairs sit at ~2.3 A and must NOT be flagged as bonds."""
    import numpy as np
    cc_bond = 1.40
    ch_bond = 1.09
    radius = cc_bond / (2 * np.sin(np.pi / 5))
    positions = [{"symbol": "Fe", "x": 0.0, "y": 0.0, "z": 0.0}]
    for k in range(5):
        angle = 2 * np.pi * k / 5
        positions.append({"symbol": "C", "x": radius * np.cos(angle), "y": radius * np.sin(angle), "z": 1.66})
    for k in range(5):
        angle = 2 * np.pi * k / 5
        hr = radius + ch_bond
        positions.append({"symbol": "H", "x": hr * np.cos(angle), "y": hr * np.sin(angle), "z": 1.66})
    return positions


def carbonyl_positions_no_cc_bonds():
    """Ni(CO)4-like topology: carbons bonded only to the metal/their own O,
    never to each other. Inter-ligand C...C distances (~2.5-3.0 A) must NOT
    be flagged as bonds for this system."""
    import numpy as np
    directions = np.array([[1, 1, 1], [1, -1, -1], [-1, 1, -1], [-1, -1, 1]], dtype=float)
    positions = [{"symbol": "Ni", "x": 0.0, "y": 0.0, "z": 0.0}]
    for d in directions:
        unit = d / np.linalg.norm(d)
        c = unit * 1.838
        o = unit * (1.838 + 1.127)
        positions.append({"symbol": "C", "x": c[0], "y": c[1], "z": c[2]})
        positions.append({"symbol": "O", "x": o[0], "y": o[1], "z": o[2]})
    return positions


def test_ferrocene_ring_has_no_false_positive_transannular_bonds():
    issues = val_mod.check_bond_lengths(ferrocene_ring_positions(), "ferrocene")
    assert issues == []


def test_carbonyl_complex_has_no_false_positive_inter_ligand_cc_bonds():
    issues = val_mod.check_bond_lengths(carbonyl_positions_no_cc_bonds(), "ni_co4")
    assert issues == []


def test_unknown_system_topology_skips_bond_check_rather_than_guessing():
    issues = val_mod.check_bond_lengths(ferrocene_ring_positions(), "totally_unknown_system")
    assert issues == []


def test_genuinely_dissociated_bond_is_flagged():
    positions = carbonyl_positions_no_cc_bonds()
    # stretch the first Ni-C bond way out, simulating a dissociated ligand
    positions[1]["x"] *= 3.0
    positions[1]["y"] *= 3.0
    positions[1]["z"] *= 3.0
    issues = val_mod.check_bond_lengths(positions, "ni_co4")
    assert any("unrealistic_bond_length" in i and "Ni" in i for i in issues)


def test_check_reference_availability_flags_unverified_status():
    issues = val_mod.check_reference_availability("ferrocene", {"ferrocene": {"status": "needs_manual_review"}})
    assert len(issues) == 1
    assert "missing_reference_source" in issues[0]


def test_check_reference_availability_passes_when_verified():
    issues = val_mod.check_reference_availability("ferrocene", {"ferrocene": {"status": "verified"}})
    assert issues == []


def test_check_reference_availability_flags_missing_entry():
    issues = val_mod.check_reference_availability("ferrocene", {})
    assert len(issues) == 1


def test_check_pseudopotentials_flags_not_ready_manifest():
    manifest = {"status": "not_ready", "elements": {}, "naming_convention_warnings": []}
    issues = val_mod.check_pseudopotentials(manifest, {"Fe"})
    assert any("missing_pseudopotentials" in i for i in issues)


def test_check_pseudopotentials_flags_naming_caution_only_for_used_elements():
    manifest = {
        "status": "ready",
        "elements": {"Ni": {"exists": True}, "Cr": {"exists": True}},
        "naming_convention_warnings": ["Ni: bad name", "Cr: bad name"],
    }
    issues = val_mod.check_pseudopotentials(manifest, {"Ni"})
    assert len(issues) == 1
    assert "Ni" in issues[0]


RY_TO_EV = 13.605693122994


def make_record(**overrides):
    base = {
        "system_id": "ferrocene",
        "job_done": True,
        "convergence_status": "converged",
        "final_energy_ry": -525.36,
        "final_energy_ev": -525.36 * RY_TO_EV,
        "final_positions_angstrom": ferrocene_ring_positions(),
        "warnings": [],
        "failures": [],
    }
    base.update(overrides)
    return base


def test_classify_failed_job_not_done():
    record = make_record(job_done=False)
    assert val_mod.classify(record, []) == "failed"


def test_classify_failed_not_converged():
    record = make_record(convergence_status="not_converged")
    assert val_mod.classify(record, []) == "failed"


def test_classify_needs_rerun_unknown_convergence():
    record = make_record(convergence_status="unknown")
    assert val_mod.classify(record, []) == "needs_rerun"


def test_classify_needs_rerun_missing_energy():
    record = make_record(final_energy_ry=None)
    assert val_mod.classify(record, []) == "needs_rerun"


def test_classify_outlier_on_bad_bond_length():
    record = make_record()
    issues = ["unrealistic_bond_length: foo"]
    assert val_mod.classify(record, issues) == "outlier"


def test_classify_usable_with_caution_on_missing_reference():
    record = make_record()
    issues = ["missing_reference_source: not verified"]
    assert val_mod.classify(record, issues) == "usable_with_caution"


def test_classify_reliable_with_no_issues():
    record = make_record()
    assert val_mod.classify(record, []) == "reliable"


def test_real_dataset_all_four_systems_land_in_usable_with_caution():
    parsed_path = PROJECT_ROOT / "data" / "processed" / "initial_relax_parsed_v0.1.json"
    assert parsed_path.exists(), "run scripts/07_parse_qe_outputs.py first"
    records = json.loads(parsed_path.read_text(encoding="utf-8"))
    reference_data = {}
    pseudo_manifest = {"status": "ready", "elements": {}, "naming_convention_warnings": []}
    for record in records:
        result = val_mod.validate_record(record, reference_data, pseudo_manifest)
        assert result["label"] == "usable_with_caution", (record["system_id"], result)
        assert not any(i.startswith("unrealistic_bond_length") for i in result["validation_issues"]), \
            f"false-positive bond-length flag for {record['system_id']}"


def test_full_dataset_csv_and_report_exist_and_are_consistent():
    full_path = PROJECT_ROOT / "data" / "processed" / "full_dataset_v0.csv"
    report_path = PROJECT_ROOT / "reports" / "dataset_validation_report_v0.md"
    assert full_path.exists(), "run scripts/08_validate_dataset.py first"
    assert report_path.exists()
    report_text = report_path.read_text(encoding="utf-8")
    assert "usable_with_caution: 4" in report_text
