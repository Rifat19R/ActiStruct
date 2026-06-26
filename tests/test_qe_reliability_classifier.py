from __future__ import annotations

import csv

from analysis.train_qe_reliability_classifier import (
    FEATURE_COLUMNS,
    POST_RUN_EXCLUDED_COLUMNS,
    build_ml_rows,
    train_models,
    write_ml_table,
)


def test_build_ml_rows_creates_binary_success_label() -> None:
    records = [
        _record("", "True", "-1.0", "12.0"),
        _record("scf_not_converged", "False", "-2.0", "99.0"),
    ]

    rows = build_ml_rows(records)

    assert rows[0]["failure_label"] == "success"
    assert rows[0]["success"] == 1
    assert rows[1]["failure_label"] == "scf_not_converged"
    assert rows[1]["success"] == 0


def test_ml_rows_exclude_post_run_leakage_fields() -> None:
    rows = build_ml_rows([_record("", "True", "-1.0", "12.0")])

    for field in POST_RUN_EXCLUDED_COLUMNS:
        assert field not in FEATURE_COLUMNS
        assert field not in rows[0]


def test_write_ml_table_has_expected_columns(tmp_path) -> None:
    rows = build_ml_rows([_record("", "True", "-1.0", "12.0")])
    out = tmp_path / "ml.csv"

    write_ml_table(rows, out)

    with out.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        saved = list(reader)

    assert reader.fieldnames == ["failure_label", "success", *FEATURE_COLUMNS]
    assert saved[0]["success"] == "1"
    assert "final_energy_ry" not in reader.fieldnames


def test_train_models_returns_baselines_on_separable_fixture() -> None:
    rows = []
    for idx in range(12):
        rows.append({
            "failure_label": "success",
            "success": 1,
            "material_id": f"ok_{idx % 3}",
            "ecutwfc": 50.0,
            "ecutrho": 400.0,
            "k1": 1,
            "k2": 1,
            "k3": 1,
            "kpoint_product": 1,
            "smearing": "gaussian",
            "mixing_beta": 0.4,
            "pseudo_family": "PSLibrary",
            "n_species": 1,
            "elements": "H",
        })
        rows.append({
            "failure_label": "qe_error",
            "success": 0,
            "material_id": f"bad_{idx % 3}",
            "ecutwfc": 80.0,
            "ecutrho": 640.0,
            "k1": 6,
            "k2": 6,
            "k3": 1,
            "kpoint_product": 36,
            "smearing": "mv",
            "mixing_beta": 0.2,
            "pseudo_family": "ONCV",
            "n_species": 3,
            "elements": "C O Pt",
        })

    results, split = train_models(rows, random_state=0)

    trained = {result.name: result for result in results if result.status == "trained"}
    assert split["n_total"] == 24
    assert split["n_train"] == 19
    assert split["n_test"] == 5
    assert "LogisticRegression" in trained
    assert "RandomForestClassifier" in trained
    assert trained["RandomForestClassifier"].confusion is not None


def _record(
    failure_reason: str,
    converged: str,
    final_energy_ry: str,
    wall_time: str,
) -> dict[str, str]:
    return {
        "material_id": "h2",
        "qe_input_path": "in",
        "qe_output_path": "out",
        "converged": converged,
        "job_done": converged,
        "scf_iterations": "7",
        "final_energy_ry": final_energy_ry,
        "energy_ev": "-13.0",
        "max_force": "0.1",
        "pressure_kbar": "1.0",
        "wall_time": wall_time,
        "failure_reason": failure_reason,
        "ecutwfc": "50.0",
        "ecutrho": "400.0",
        "kpoints": "1 1 1 0 0 0",
        "smearing": "gaussian",
        "mixing_beta": "0.4",
        "pseudo_family": "PSLibrary",
        "pseudopotentials": '{"H":"H.UPF"}',
        "calculation_hash": "abc",
    }

