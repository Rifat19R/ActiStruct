from __future__ import annotations

import csv

from analysis.train_qe_reliability_classifier import (
    ExperimentSpec,
    FEATURE_COLUMNS,
    POST_RUN_EXCLUDED_COLUMNS,
    build_ml_rows,
    experiment_specs,
    make_split,
    train_experiments,
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

    assert reader.fieldnames == ["record_id", "failure_label", "success", *FEATURE_COLUMNS]
    assert saved[0]["success"] == "1"
    assert "final_energy_ry" not in reader.fieldnames


def test_no_material_id_ablation_removes_material_feature() -> None:
    specs = {spec.name: spec for spec in experiment_specs()}

    assert "material_id" in specs["baseline_random_split"].feature_columns
    assert "material_id" not in specs["no_material_id_random_split"].feature_columns


def test_group_split_holds_out_material_groups() -> None:
    rows = _ml_fixture()
    spec = ExperimentSpec("material_group_split", "group", FEATURE_COLUMNS)

    split = make_split(rows, spec, random_state=0)

    train_groups = {rows[int(idx)]["material_id"] for idx in split.train_idx}
    test_groups = {rows[int(idx)]["material_id"] for idx in split.test_idx}
    assert train_groups
    assert test_groups
    assert train_groups.isdisjoint(test_groups)


def test_train_experiments_returns_ablation_results_and_predictions() -> None:
    rows = _ml_fixture()

    results, predictions = train_experiments(rows, random_state=0)

    trained = {
        (result.experiment, result.model): result
        for result in results
        if result.status == "trained"
    }
    experiments = {result.experiment for result in results}
    assert {
        "baseline_random_split",
        "no_material_id_random_split",
        "material_group_split",
    } <= experiments
    assert ("baseline_random_split", "LogisticRegression") in trained
    assert ("baseline_random_split", "RandomForestClassifier") in trained
    assert trained[("baseline_random_split", "RandomForestClassifier")].failure_recall is not None
    assert predictions
    assert {"experiment", "model", "predicted_failure_risk"} <= set(predictions[0])


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


def _ml_fixture() -> list[dict[str, object]]:
    rows = []
    for idx in range(18):
        rows.append({
            "record_id": len(rows),
            "failure_label": "success",
            "success": 1,
            "material_id": f"ok_{idx % 6}",
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
            "record_id": len(rows),
            "failure_label": "qe_error",
            "success": 0,
            "material_id": f"bad_{idx % 6}",
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
    return rows
