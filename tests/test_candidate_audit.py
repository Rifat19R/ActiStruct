import csv
import json
from pathlib import Path

from _load import load_script

audit_mod = load_script("05b_audit_perturbation_candidates.py")
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_classify_candidate_matches_real_variable_labels():
    result = audit_mod.classify_candidate({"fe_cp_centroid_distance_angstrom": 1.71, "delta_from_nominal": 0.05})
    assert result["perturbation_family"] == "Fe-Cp stretch"
    assert result["magnitude"] == 0.05
    assert result["magnitude_bucket"] == "large"


def test_classify_candidate_angle_vs_distance_bucket_thresholds():
    angle = audit_mod.classify_candidate({"cp_ring_rotation_angle_degree": 9.0, "delta_from_nominal": 9.0})
    distance = audit_mod.classify_candidate({"cp_ring_radius_perturbation_angstrom": 1.43, "delta_from_nominal": 0.03})
    assert angle["magnitude_bucket"] == "small"  # 9 deg < 10 deg threshold
    assert distance["magnitude_bucket"] == "small"  # 0.03 A == threshold


def test_classify_candidate_unknown_label_falls_back_gracefully():
    result = audit_mod.classify_candidate({"some_future_variable": 1.0, "delta_from_nominal": 0.01})
    assert result["perturbation_family"] == "some_future_variable"
    assert "Unclassified" in result["expected_physical_effect"]


def test_check_overlaps_detects_clashing_atoms():
    positions = [
        {"symbol": "C", "x": 0.0, "y": 0.0, "z": 0.0},
        {"symbol": "C", "x": 0.1, "y": 0.0, "z": 0.0},  # 0.1 A apart - clearly overlapping
    ]
    issues = audit_mod.check_overlaps(positions)
    assert len(issues) == 1
    assert "atom_overlap" in issues[0]


def test_check_overlaps_passes_normal_geometry():
    positions = [
        {"symbol": "C", "x": 0.0, "y": 0.0, "z": 0.0},
        {"symbol": "O", "x": 1.15, "y": 0.0, "z": 0.0},
    ]
    assert audit_mod.check_overlaps(positions) == []


def test_check_bond_sanity_rejects_dissociated_bond():
    import numpy as np
    directions = np.array([[1, 1, 1], [1, -1, -1], [-1, 1, -1], [-1, -1, 1]], dtype=float)
    positions = [{"symbol": "Ni", "x": 0.0, "y": 0.0, "z": 0.0}]
    for d in directions:
        unit = d / np.linalg.norm(d)
        c = unit * 1.838
        o = unit * (1.838 + 1.141)
        positions.append({"symbol": "C", "x": c[0], "y": c[1], "z": c[2]})
        positions.append({"symbol": "O", "x": o[0], "y": o[1], "z": o[2]})
    # dissociate the first Ni-C bond
    positions[1]["x"] *= 3
    positions[1]["y"] *= 3
    positions[1]["z"] *= 3
    issues = audit_mod.check_bond_sanity(positions, "ni_co4")
    assert any("unrealistic_bond_length_after_perturbation" in i for i in issues)


def test_check_bond_sanity_passes_unperturbed_geometry():
    import numpy as np
    directions = np.array([[1, 1, 1], [1, -1, -1], [-1, 1, -1], [-1, -1, 1]], dtype=float)
    positions = [{"symbol": "Ni", "x": 0.0, "y": 0.0, "z": 0.0}]
    for d in directions:
        unit = d / np.linalg.norm(d)
        c = unit * 1.838
        o = unit * (1.838 + 1.141)
        positions.append({"symbol": "C", "x": c[0], "y": c[1], "z": c[2]})
        positions.append({"symbol": "O", "x": o[0], "y": o[1], "z": o[2]})
    assert audit_mod.check_bond_sanity(positions, "ni_co4") == []


def test_find_duplicates_detects_identical_structures():
    positions = [{"symbol": "Fe", "x": 0.0, "y": 0.0, "z": 0.0}, {"symbol": "C", "x": 2.0, "y": 0.0, "z": 0.0}]
    candidates = [
        {"candidate_id": "a", "system_id": "sys1", "positions": positions},
        {"candidate_id": "b", "system_id": "sys1", "positions": positions},
        {"candidate_id": "c", "system_id": "sys1", "positions": [{"symbol": "Fe", "x": 0.0, "y": 0.0, "z": 0.0}, {"symbol": "C", "x": 2.5, "y": 0.0, "z": 0.0}]},
    ]
    duplicate_map = audit_mod.find_duplicates(candidates)
    assert duplicate_map == {"b": "a"}


def test_find_duplicates_does_not_cross_systems():
    positions = [{"symbol": "Fe", "x": 0.0, "y": 0.0, "z": 0.0}]
    candidates = [
        {"candidate_id": "a", "system_id": "sys1", "positions": positions},
        {"candidate_id": "b", "system_id": "sys2", "positions": positions},
    ]
    assert audit_mod.find_duplicates(candidates) == {}


def test_select_representatives_alternates_sign_within_a_system():
    rows = [
        {"candidate_id": "x1", "system_id": "s", "perturbation_family": "A", "var_label": "a", "magnitude": -0.06, "audit_status": "accepted"},
        {"candidate_id": "x2", "system_id": "s", "perturbation_family": "A", "var_label": "a", "magnitude": 0.06, "audit_status": "accepted"},
        {"candidate_id": "y1", "system_id": "s", "perturbation_family": "B", "var_label": "b", "magnitude": -0.06, "audit_status": "accepted"},
        {"candidate_id": "y2", "system_id": "s", "perturbation_family": "B", "var_label": "b", "magnitude": 0.06, "audit_status": "accepted"},
    ]
    selected = audit_mod.select_representatives(rows)
    # family A (alphabetically first) should prefer negative, family B should prefer positive
    assert "x1" in selected
    assert "y2" in selected


def test_select_representatives_excludes_berry_family():
    rows = [
        {"candidate_id": "z1", "system_id": "fe_co5", "perturbation_family": "Berry-pseudorotation-like tilt",
         "var_label": "berry_like_distortion_coordinate_degree", "magnitude": 20.0, "audit_status": "accepted"},
    ]
    assert audit_mod.select_representatives(rows) == set()


def test_select_representatives_skips_rejected_candidates():
    rows = [
        {"candidate_id": "good", "system_id": "s", "perturbation_family": "A", "var_label": "a", "magnitude": 0.02, "audit_status": "accepted"},
        {"candidate_id": "bad", "system_id": "s", "perturbation_family": "A", "var_label": "a", "magnitude": 0.06, "audit_status": "rejected"},
    ]
    assert audit_mod.select_representatives(rows) == {"good"}


def test_real_audit_all_52_candidates_classified_and_exactly_12_selected():
    audit_path = PROJECT_ROOT / "data" / "processed" / "candidate_audit_v0.csv"
    assert audit_path.exists(), "run scripts/05b_audit_perturbation_candidates.py first"
    with audit_path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 52
    for row in rows:
        assert row["perturbation_family"], f"{row['candidate_id']} has no family classification"
        assert "Unclassified" not in row["expected_physical_effect"], \
            f"{row['candidate_id']} ({row['var_label']}) was not recognized - update PERTURBATION_FAMILIES"
    selected = [r for r in rows if r["selected_as_representative"] == "True"]
    assert len(selected) == 12
    per_system = {}
    for r in selected:
        per_system.setdefault(r["system_id"], 0)
        per_system[r["system_id"]] += 1
    assert per_system == {"ferrocene": 3, "ni_co4": 3, "cr_co6": 3, "fe_co5": 3}


def test_real_audit_selected_set_spans_both_signs_per_system():
    audit_path = PROJECT_ROOT / "data" / "processed" / "candidate_audit_v0.csv"
    with audit_path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    selected = [r for r in rows if r["selected_as_representative"] == "True"]
    by_system: dict[str, list[float]] = {}
    for r in selected:
        by_system.setdefault(r["system_id"], []).append(float(r["magnitude"]))
    for system_id, magnitudes in by_system.items():
        signs = {m >= 0 for m in magnitudes}
        assert len(signs) == 2, f"{system_id}: all selected representatives have the same sign {magnitudes}"


def test_real_audit_no_duplicates_among_52():
    audit_path = PROJECT_ROOT / "data" / "processed" / "candidate_audit_v0.csv"
    with audit_path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    duplicates = [r for r in rows if r["is_duplicate_of"]]
    assert duplicates == [], f"unexpected duplicates found: {duplicates}"
