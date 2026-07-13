from pathlib import Path

from _load import load_script

parser_mod = load_script("07_parse_qe_outputs.py")

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "qe_outputs"

REAL_SYSTEMS = {
    "ferrocene": {"ionic_steps": 15, "energy_ry": -525.3618442398},
    "ni_co4": {"ionic_steps": 7, "energy_ry": -583.5691160575},
    "cr_co6": {"ionic_steps": 7, "energy_ry": -536.0152471419},
    "fe_co5": {"ionic_steps": 10, "energy_ry": -629.6772928617},
}


def test_find_qe_outputs_detects_all_real_fixtures():
    found = parser_mod.find_qe_outputs(FIXTURES_DIR)
    names = {p.parent.name for p in found if p.parent.name in REAL_SYSTEMS}
    assert names == set(REAL_SYSTEMS.keys())


def test_find_qe_outputs_ignores_non_qe_files(tmp_path):
    (tmp_path / "notes.txt").write_text("just a regular text file, not QE output")
    found = parser_mod.find_qe_outputs(tmp_path)
    assert found == []


def test_find_qe_outputs_returns_empty_for_missing_dir(tmp_path):
    missing = tmp_path / "does_not_exist"
    assert parser_mod.find_qe_outputs(missing) == []


def test_parse_time_str_handles_hours_minutes_seconds():
    assert parser_mod._time_str_to_seconds("1h23m") == 4980.0
    assert parser_mod._time_str_to_seconds("1h 1m") == 3660.0
    assert parser_mod._time_str_to_seconds("53m40.07s") == 3220.07
    assert parser_mod._time_str_to_seconds("31m37.18s") == 1897.18


def test_parse_time_str_handles_empty_or_garbage():
    assert parser_mod._time_str_to_seconds("") is None
    assert parser_mod._time_str_to_seconds("not a time") is None


def real_fixture_path(system_id: str) -> Path:
    return FIXTURES_DIR / system_id / f"{system_id}.relax.out"


def test_real_systems_parse_as_converged_with_correct_energy():
    for system_id, expected in REAL_SYSTEMS.items():
        record = parser_mod.parse_qe_output(real_fixture_path(system_id))
        assert record["system_id"] == system_id
        assert record["job_done"] is True
        assert record["convergence_status"] == "converged"
        assert record["ionic_steps"] == expected["ionic_steps"]
        assert record["final_energy_ry"] == expected["energy_ry"]
        assert record["final_energy_ev"] == expected["energy_ry"] * parser_mod.RY_TO_EV
        assert record["failures"] == []
        assert record["parser_version"] == parser_mod.PARSER_VERSION


def test_real_systems_have_geometry_and_no_missing_fields_silently_dropped():
    for system_id in REAL_SYSTEMS:
        record = parser_mod.parse_qe_output(real_fixture_path(system_id))
        assert record["final_lattice_angstrom"] is not None
        assert len(record["final_lattice_angstrom"]) == 3
        assert record["final_positions_angstrom"] is not None
        assert len(record["final_positions_angstrom"]) > 0
        assert record["max_force_ry_per_bohr"] is not None
        assert record["wall_time_sec"] is not None
        assert record["scf_iterations_total"] > 0
        assert record["input_filename"] is not None


def test_ni_co4_and_fe_co5_carry_ibrav0_discouraged_warning():
    for system_id in ("ni_co4", "fe_co5"):
        record = parser_mod.parse_qe_output(real_fixture_path(system_id))
        assert any("DISCOURAGED" in w for w in record["warnings"]), system_id


def test_synthetic_bfgs_failed_fixture_detected_as_not_converged():
    path = FIXTURES_DIR / "synthetic_failures" / "bfgs_failed.relax.out"
    record = parser_mod.parse_qe_output(path)
    assert record["convergence_status"] == "not_converged"
    assert record["job_done"] is True
    assert record["ionic_steps"] == 7
    assert any("bfgs_failed" in f for f in record["failures"])


def test_synthetic_mpi_crash_fixture_detected_as_failed_with_no_job_done():
    path = FIXTURES_DIR / "synthetic_failures" / "mpi_crash.relax.out"
    record = parser_mod.parse_qe_output(path)
    assert record["job_done"] is False
    assert record["convergence_status"] == "unknown"
    assert record["final_lattice_angstrom"] is None
    assert record["final_positions_angstrom"] is None
    assert len(record["failures"]) > 0
    joined_failures = " ".join(record["failures"])
    assert "create_directory" in joined_failures or "mpi_abort" in joined_failures


def test_missing_fields_are_null_not_fabricated(tmp_path):
    minimal = tmp_path / "minimal.out"
    minimal.write_text("     Program PWSCF v.7.4.1 starts on 29Jun2026\n\n     stopping ...\n")
    record = parser_mod.parse_qe_output(minimal)
    assert record["final_energy_ry"] is None
    assert record["final_energy_ev"] is None
    assert record["ionic_steps"] is None
    assert record["max_force_ry_per_bohr"] is None
    assert record["wall_time_sec"] is None
    assert record["final_lattice_angstrom"] is None
    assert record["final_positions_angstrom"] is None
    assert record["job_done"] is False
    assert record["convergence_status"] == "unknown"


def test_to_csv_row_json_encodes_nested_fields():
    record = parser_mod.parse_qe_output(real_fixture_path("ni_co4"))
    row = parser_mod.to_csv_row(record)
    assert isinstance(row["final_lattice_angstrom"], str)
    assert isinstance(row["warnings"], str)
    import json
    assert json.loads(row["warnings"]) == record["warnings"]


def test_build_summary_report_counts_match_records():
    records = [parser_mod.parse_qe_output(real_fixture_path(s)) for s in REAL_SYSTEMS]
    report = parser_mod.build_summary_report(records, FIXTURES_DIR)
    assert "Total QE outputs found: 4" in report
    assert "Converged: 4" in report
    assert "Not converged: 0" in report
