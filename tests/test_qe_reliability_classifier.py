from __future__ import annotations

import csv

from analysis.train_qe_reliability_classifier import (
    ExperimentSpec,
    FEATURE_COLUMNS,
    POST_RUN_EXCLUDED_COLUMNS,
    THRESHOLDS,
    _models,
    build_ml_rows,
    build_element_descriptors,
    experiment_specs,
    failure_taxonomy,
    make_split,
    train_experiments,
    write_ml_table,
)
from analysis.qe_reliability_generalization_fix import (
    FAILURE_RISK_THRESHOLDS,
    _diagnosis_prediction_rows,
    repeated_group_risk_experiment,
    run_v031_diagnosis,
)


def test_build_ml_rows_creates_binary_success_label() -> None:
    records = [
        _record("", "True", "-1.0", "12.0"),
        _record("scf_not_converged", "False", "-2.0", "99.0"),
    ]

    rows = build_ml_rows(records)

    assert rows[0]["failure_label"] == "success"
    assert rows[0]["failure_taxonomy"] == "success"
    assert rows[0]["success"] == 1
    assert rows[1]["failure_label"] == "scf_not_converged"
    assert rows[1]["failure_taxonomy"] == "scf_not_converged"
    assert rows[1]["success"] == 0


def test_ml_rows_exclude_post_run_leakage_fields() -> None:
    rows = build_ml_rows([_record("", "True", "-1.0", "12.0")])

    for field in POST_RUN_EXCLUDED_COLUMNS:
        assert field not in FEATURE_COLUMNS
        assert field not in rows[0]


def test_descriptor_generation_from_setup_metadata() -> None:
    rows = build_ml_rows([
        _record(
            "",
            "True",
            "-1.0",
            "12.0",
            material_id="ptoh",
            pseudopotentials='{"Pt":"Pt.UPF","O":"O.UPF","H":"H.UPF"}',
            ecutwfc="50.0",
            ecutrho="400.0",
        )
    ])
    row = rows[0]

    assert row["n_species"] == 3
    assert row["n_atoms"] is None
    assert row["volume_per_atom"] is None
    assert row["has_transition_metal"] == 1
    assert row["has_oxygen"] == 1
    assert row["has_hydrogen"] == 1
    assert row["atomic_number_min"] == 1.0
    assert row["atomic_number_max"] == 78.0
    assert row["atomic_number_std"] > 0.0
    assert row["atomic_radius_mean"] is not None
    assert row["transition_metal_fraction"] > 0.0
    assert row["ecutrho_over_ecutwfc"] == 8.0
    assert row["element_count_Pt"] == 1
    assert row["element_fraction_Pt"] > 0.0
    assert row["element_count_O"] == 1
    assert row["element_count_C"] == 0


def test_descriptor_helper_handles_unknown_elements() -> None:
    descriptors = build_element_descriptors(["Xx"], ecutwfc=0.0, ecutrho=400.0)

    assert descriptors["atomic_number_mean"] is None
    assert descriptors["ecutrho_over_ecutwfc"] is None
    assert descriptors["has_transition_metal"] == 0


def test_write_ml_table_has_expected_columns(tmp_path) -> None:
    rows = build_ml_rows([_record("", "True", "-1.0", "12.0")])
    out = tmp_path / "ml.csv"

    write_ml_table(rows, out)

    with out.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        saved = list(reader)

    assert reader.fieldnames == [
        "record_id",
        "failure_label",
        "failure_taxonomy",
        "success",
        *FEATURE_COLUMNS,
    ]
    assert saved[0]["success"] == "1"
    assert "final_energy_ry" not in reader.fieldnames


def test_failure_taxonomy_mapping() -> None:
    assert failure_taxonomy("success") == "success"
    assert failure_taxonomy("qe_error") == "setup_error"
    assert failure_taxonomy("scf_not_converged") == "scf_not_converged"
    assert failure_taxonomy("job_not_completed") == "runtime_incomplete"
    assert failure_taxonomy("invalid_geometry") == "invalid_geometry"
    assert failure_taxonomy("weird") == "unknown_failure"


def test_class_weight_model_setup() -> None:
    models = dict(_models(random_state=0))

    assert models["LogisticRegression"].class_weight == "balanced"
    assert models["RandomForestClassifier"].class_weight == "balanced"


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
    assert {"experiment", "model", "threshold", "predicted_failure_risk"} <= set(predictions[0])


def test_threshold_sweep_is_reported_for_trained_models() -> None:
    rows = _ml_fixture()

    results, _ = train_experiments(rows, random_state=0)

    trained = next(
        result for result in results
        if result.status == "trained" and result.model == "RandomForestClassifier"
    )
    assert trained.threshold_metrics is not None
    assert [item.threshold for item in trained.threshold_metrics] == THRESHOLDS
    assert all(item.confusion for item in trained.threshold_metrics)


def test_group_split_diagnosis_output_columns(tmp_path) -> None:
    rows = _ml_fixture()
    prediction_rows = _diagnosis_prediction_rows(
        rows[:2],
        y_test_success=[row["success"] for row in rows[:2]],
        success_prob=[0.95, 0.80],
        failure_risk=[0.05, 0.20],
    )

    assert {
        "material_id",
        "true_label",
        "failure_reason",
        "failure_taxonomy",
        "predicted_success_probability",
        "predicted_failure_risk",
        "predicted_label_t_0p05",
        "predicted_label_t_0p50",
    } <= set(prediction_rows[0])

    input_path = tmp_path / "records.csv"
    report_path = tmp_path / "diagnosis.md"
    predictions_path = tmp_path / "diagnosis.csv"
    _write_records_fixture(input_path)

    run_v031_diagnosis(input_path, report_path, predictions_path, random_state=0)

    assert report_path.exists()
    with predictions_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        assert "predicted_label_t_0p05" in (reader.fieldnames or [])


def test_repeated_group_risk_experiment_outputs_thresholds_and_ood() -> None:
    rows = _ml_fixture()

    metrics, predictions = repeated_group_risk_experiment(rows, random_state=0, n_splits=2)

    assert metrics
    assert {metric.threshold for metric in metrics} == set(FAILURE_RISK_THRESHOLDS)
    assert predictions
    assert {
        "setup_error_risk",
        "scf_failure_risk",
        "runtime_incomplete_risk",
        "total_failure_risk",
        "ood_distance",
        "ood_flag",
    } <= set(predictions[0])


def _record(
    failure_reason: str,
    converged: str,
    final_energy_ry: str,
    wall_time: str,
    *,
    material_id: str = "h2",
    pseudopotentials: str = '{"H":"H.UPF"}',
    ecutwfc: str = "50.0",
    ecutrho: str = "400.0",
) -> dict[str, str]:
    return {
        "material_id": material_id,
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
        "ecutwfc": ecutwfc,
        "ecutrho": ecutrho,
        "kpoints": "1 1 1 0 0 0",
        "smearing": "gaussian",
        "mixing_beta": "0.4",
        "pseudo_family": "PSLibrary",
        "pseudopotentials": pseudopotentials,
        "calculation_hash": "abc",
    }


def _ml_fixture() -> list[dict[str, object]]:
    records = []
    for idx in range(18):
        records.append(_record(
            "",
            "True",
            "-1.0",
            "12.0",
            material_id=f"ok_{idx % 6}",
            pseudopotentials='{"H":"H.UPF"}',
            ecutwfc="50.0",
            ecutrho="400.0",
        ))
        records.append(_record(
            "qe_error",
            "False",
            "",
            "99.0",
            material_id=f"bad_{idx % 6}",
            pseudopotentials='{"C":"C.UPF","O":"O.UPF","Pt":"Pt.UPF"}',
            ecutwfc="80.0",
            ecutrho="640.0",
        ))
    return build_ml_rows(records)


def _write_records_fixture(path) -> None:
    records = []
    for idx in range(12):
        records.append(_record(
            "",
            "True",
            "-1.0",
            "12.0",
            material_id=f"ok_{idx % 4}",
            pseudopotentials='{"H":"H.UPF"}',
        ))
        records.append(_record(
            "qe_error",
            "False",
            "",
            "99.0",
            material_id=f"bad_{idx % 4}",
            pseudopotentials='{"C":"C.UPF","O":"O.UPF","Pt":"Pt.UPF"}',
            ecutwfc="80.0",
            ecutrho="640.0",
        ))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
