import json
from pathlib import Path

from _load import load_script

cmp_mod = load_script("13_compare_to_references.py")
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def square_planar_like_ni_co4_positions():
    import numpy as np
    directions = np.array([[1, 1, 1], [1, -1, -1], [-1, 1, -1], [-1, -1, 1]], dtype=float)
    positions = [{"symbol": "Ni", "x": 0.0, "y": 0.0, "z": 0.0}]
    for d in directions:
        unit = d / np.linalg.norm(d)
        c = unit * 1.838
        o = unit * (1.838 + 1.141)
        positions.append({"symbol": "C", "x": c[0], "y": c[1], "z": c[2]})
        positions.append({"symbol": "O", "x": o[0], "y": o[1], "z": o[2]})
    return positions


def fe_co5_positions(axial_fe_c=1.807, eq_fe_c=1.827, axial_co=1.143, eq_co=1.153):
    import numpy as np
    positions = [{"symbol": "Fe", "x": 0.0, "y": 0.0, "z": 0.0}]
    for sign in (+1, -1):
        c = [0.0, 0.0, sign * axial_fe_c]
        o = [0.0, 0.0, sign * (axial_fe_c + axial_co)]
        positions.append({"symbol": "C", "x": c[0], "y": c[1], "z": c[2]})
        positions.append({"symbol": "O", "x": o[0], "y": o[1], "z": o[2]})
    for k in range(3):
        angle = 2 * np.pi * k / 3
        ux, uy = np.cos(angle), np.sin(angle)
        c = [ux * eq_fe_c, uy * eq_fe_c, 0.0]
        o = [ux * (eq_fe_c + eq_co), uy * (eq_fe_c + eq_co), 0.0]
        positions.append({"symbol": "C", "x": c[0], "y": c[1], "z": c[2]})
        positions.append({"symbol": "O", "x": o[0], "y": o[1], "z": o[2]})
    return positions


def test_measure_mean_nearest_neighbor_ni_co4():
    positions = square_planar_like_ni_co4_positions()
    ni_c = cmp_mod.measure_mean_nearest_neighbor(positions, "Ni", "C")
    c_o = cmp_mod.measure_mean_nearest_neighbor(positions, "C", "O")
    assert abs(ni_c - 1.838) < 1e-6
    assert abs(c_o - 1.141) < 1e-6


def test_classify_fe_co5_axial_equatorial_is_rotation_invariant():
    """Axial/equatorial classification must come from the molecule's own
    internal angles, not coordinate-axis position - rotating the whole
    structure must not change which atoms are classified as axial."""
    import numpy as np
    positions = fe_co5_positions()

    def rotate(p, axis, theta):
        axis = axis / np.linalg.norm(axis)
        v = np.array([p["x"], p["y"], p["z"]])
        rotated = (v * np.cos(theta) + np.cross(axis, v) * np.sin(theta)
                   + axis * np.dot(axis, v) * (1 - np.cos(theta)))
        return {"symbol": p["symbol"], "x": rotated[0], "y": rotated[1], "z": rotated[2]}

    axial_before, eq_before = cmp_mod.classify_fe_co5_axial_equatorial(positions)
    rotated_positions = [rotate(p, np.array([0.3, 0.7, 0.1]), 1.234) for p in positions]
    axial_after, eq_after = cmp_mod.classify_fe_co5_axial_equatorial(rotated_positions)

    assert set(axial_before) == set(axial_after)
    assert set(eq_before) == set(eq_after)


def test_classify_fe_co5_identifies_correct_axial_carbons():
    positions = fe_co5_positions()
    axial_idx, eq_idx = cmp_mod.classify_fe_co5_axial_equatorial(positions)
    axial_symbols_z = sorted(abs(positions[i]["z"]) for i in axial_idx)
    eq_symbols_z = sorted(abs(positions[i]["z"]) for i in eq_idx)
    # axial carbons are the ones along z in this fixture; equatorial are in-plane
    assert all(z > 1.0 for z in axial_symbols_z)
    assert all(z < 1.0 for z in eq_symbols_z)


def test_build_measurements_fe_co5_matches_known_geometry():
    positions = fe_co5_positions(axial_fe_c=1.81, eq_fe_c=1.84, axial_co=1.14, eq_co=1.15)
    measurements = cmp_mod.build_measurements(positions)
    assert abs(measurements["Fe-C axial"] - 1.81) < 1e-6
    assert abs(measurements["Fe-C equatorial"] - 1.84) < 1e-6
    assert abs(measurements["C-O axial"] - 1.14) < 1e-6
    assert abs(measurements["C-O equatorial"] - 1.15) < 1e-6


def test_is_source_documented_accepts_doi_or_url_or_full_citation():
    assert cmp_mod.is_source_documented({"doi": "10.1234/x"})
    assert cmp_mod.is_source_documented({"url_or_accession": "https://example.com"})
    assert cmp_mod.is_source_documented(
        {"title": "T", "authors": "A", "year": 2020, "journal_or_database": "J"})
    assert not cmp_mod.is_source_documented({"title": "T"})
    assert not cmp_mod.is_source_documented(None)


def test_compare_system_flags_within_and_outside_tolerance():
    positions = square_planar_like_ni_co4_positions()
    reference_entry = {
        "reference_values": {
            "bond_lengths": [
                {"label": "Ni-C", "value_angstrom": 1.838, "source_id": "s1"},
                {"label": "C-O", "value_angstrom": 1.50, "source_id": "s1"},  # deliberately way off
            ]
        }
    }
    rows = cmp_mod.compare_system("ni_co4", positions, reference_entry)
    by_label = {r["label"]: r for r in rows}
    assert by_label["Ni-C"]["within_tolerance"] is True
    assert by_label["C-O"]["within_tolerance"] is False


def test_real_dataset_all_systems_validated():
    parsed_path = PROJECT_ROOT / "data" / "processed" / "initial_relax_parsed_v0.1.json"
    assert parsed_path.exists(), "run scripts/07_parse_qe_outputs.py first"
    records = json.loads(parsed_path.read_text(encoding="utf-8"))

    from _common import load_yaml
    reference_data = load_yaml("references/reference_values_tmc_v0.yaml")

    for record in records:
        rows = cmp_mod.compare_system(record["system_id"], record["final_positions_angstrom"],
                                       reference_data[record["system_id"]])
        for row in rows:
            assert row["qe_angstrom"] is not None, f"{record['system_id']}: {row['label']} not measured"
            assert row["within_tolerance"] is True, \
                f"{record['system_id']}: {row['label']} unexpectedly outside tolerance " \
                f"(delta={row['delta_angstrom']}, %={row['percent_error']})"


def test_comparison_report_and_csv_exist():
    report_path = PROJECT_ROOT / "reports" / "reference_validation_v0.1.md"
    csv_path = PROJECT_ROOT / "reports" / "tables" / "reference_comparison_v0.csv"
    assert report_path.exists(), "run scripts/13_compare_to_references.py first"
    assert csv_path.exists()
    report_text = report_path.read_text(encoding="utf-8")
    for system_id in ("ferrocene", "ni_co4", "cr_co6", "fe_co5"):
        assert f"`{system_id}`" in report_text or system_id in report_text


def test_updated_dataset_v01_has_validated_labels():
    updated_path = PROJECT_ROOT / "data" / "processed" / "full_dataset_v0.1.csv"
    assert updated_path.exists(), "run scripts/13_compare_to_references.py first"
    import csv
    with updated_path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 4
    assert all(r["label"] == "validated" for r in rows)
