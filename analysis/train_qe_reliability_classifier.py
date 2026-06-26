from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import GroupShuffleSplit, train_test_split
from sklearn.pipeline import Pipeline


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "parsed_records" / "qe_reliability_records.csv"
DEFAULT_TABLE = ROOT / "data" / "qe_reliability_ml_table.csv"
DEFAULT_REPORT = ROOT / "reports" / "qe_reliability_classifier_v02_ablation.md"
DEFAULT_PREDICTIONS = ROOT / "data" / "qe_reliability_predictions_v02.csv"

LABEL_COLUMN = "success"
FAILURE_LABEL_COLUMN = "failure_label"

POST_RUN_EXCLUDED_COLUMNS = {
    "converged",
    "job_done",
    "scf_iterations",
    "final_energy_ry",
    "energy_ev",
    "max_force",
    "pressure_kbar",
    "wall_time",
    "failure_reason",
    "calculation_hash",
}

FEATURE_COLUMNS = [
    "material_id",
    "ecutwfc",
    "ecutrho",
    "k1",
    "k2",
    "k3",
    "kpoint_product",
    "smearing",
    "mixing_beta",
    "pseudo_family",
    "n_species",
    "elements",
]


@dataclass(frozen=True)
class ExperimentSpec:
    name: str
    split: str
    feature_columns: list[str]


@dataclass(frozen=True)
class SplitData:
    train_idx: np.ndarray
    test_idx: np.ndarray
    feature_columns: list[str]
    groups: np.ndarray


@dataclass(frozen=True)
class ModelResult:
    experiment: str
    model: str
    status: str
    feature_columns: list[str]
    n_train: int
    n_test: int
    train_success: int
    train_failure: int
    test_success: int
    test_failure: int
    accuracy: float | None = None
    precision: float | None = None
    recall: float | None = None
    failure_recall: float | None = None
    f1: float | None = None
    roc_auc: float | None = None
    confusion: list[list[int]] | None = None
    top_features: list[tuple[str, float]] | None = None


def read_records(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def build_ml_rows(records: Iterable[dict[str, str]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index, record in enumerate(records):
        failure_label = record.get("failure_reason") or "success"
        pseudos = _parse_pseudos(record.get("pseudopotentials", ""))
        k1, k2, k3 = _parse_kpoints(record.get("kpoints", ""))
        rows.append({
            "record_id": index,
            FAILURE_LABEL_COLUMN: failure_label,
            LABEL_COLUMN: 1 if failure_label == "success" else 0,
            "material_id": record.get("material_id") or "unknown",
            "ecutwfc": _float_or_none(record.get("ecutwfc")),
            "ecutrho": _float_or_none(record.get("ecutrho")),
            "k1": k1,
            "k2": k2,
            "k3": k3,
            "kpoint_product": k1 * k2 * k3,
            "smearing": record.get("smearing") or "unknown",
            "mixing_beta": _float_or_none(record.get("mixing_beta")),
            "pseudo_family": record.get("pseudo_family") or "unknown",
            "n_species": len(pseudos),
            "elements": " ".join(sorted(pseudos)) or "unknown",
        })
    return rows


def write_ml_table(rows: list[dict[str, object]], path: str | Path) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    columns = ["record_id", FAILURE_LABEL_COLUMN, LABEL_COLUMN, *FEATURE_COLUMNS]
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def experiment_specs() -> list[ExperimentSpec]:
    no_material = [col for col in FEATURE_COLUMNS if col != "material_id"]
    return [
        ExperimentSpec("baseline_random_split", "random", FEATURE_COLUMNS),
        ExperimentSpec("no_material_id_random_split", "random", no_material),
        ExperimentSpec("material_group_split", "group", FEATURE_COLUMNS),
    ]


def make_split(
    rows: list[dict[str, object]],
    spec: ExperimentSpec,
    random_state: int = 42,
) -> SplitData:
    y = np.array([int(row[LABEL_COLUMN]) for row in rows], dtype=int)
    groups = np.array([str(row["material_id"]) for row in rows])
    all_idx = np.arange(len(rows))
    if spec.split == "group":
        splitter = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=random_state)
        train_idx, test_idx = next(splitter.split(all_idx, y, groups))
    else:
        train_idx, test_idx = train_test_split(
            all_idx,
            test_size=0.2,
            random_state=random_state,
            stratify=y,
        )
    return SplitData(train_idx, test_idx, spec.feature_columns, groups)


def train_experiments(
    rows: list[dict[str, object]],
    random_state: int = 42,
) -> tuple[list[ModelResult], list[dict[str, object]]]:
    results: list[ModelResult] = []
    predictions: list[dict[str, object]] = []
    for spec in experiment_specs():
        split = make_split(rows, spec, random_state)
        experiment_results, experiment_predictions = _train_one_experiment(
            rows,
            spec,
            split,
            random_state,
        )
        results.extend(experiment_results)
        predictions.extend(experiment_predictions)
    return results, predictions


def write_predictions(rows: list[dict[str, object]], path: str | Path) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "experiment",
        "model",
        "record_id",
        "material_id",
        "failure_label",
        "true_success",
        "predicted_success",
        "predicted_failure_risk",
        "split",
    ]
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def render_report(
    results: list[ModelResult],
    table_path: str | Path,
    predictions_path: str | Path,
    input_path: str | Path,
) -> str:
    total_rows = max((r.n_train + r.n_test for r in results if r.status == "trained"), default=0)
    lines = [
        "# QE Reliability Classifier v0.2 Ablation",
        "",
        "## Purpose",
        "",
        "This model predicts whether a Quantum ESPRESSO calculation record is "
        "expected to be successful using setup metadata only. The binary label "
        "is `success=1` when `failure_label == \"success\"`; all other failure "
        "labels are `success=0`.",
        "",
        "The goal is not to reduce the failure count by relabeling data. The "
        "failure rows are the signal needed to learn failure risk. The right "
        "way to improve success rate is to use this model later as a penalty "
        "inside active acquisition.",
        "",
        "## Files",
        "",
        f"- Input records: `{_repo_path(input_path)}`",
        f"- ML table: `{_repo_path(table_path)}`",
        f"- Predictions: `{_repo_path(predictions_path)}`",
        f"- Rows modeled: **{total_rows}**",
        "",
        "## Experiments",
        "",
        "- `baseline_random_split`: current leakage-safe setup metadata.",
        "- `no_material_id_random_split`: removes `material_id` to test whether "
        "the model relies on local material/workflow identity.",
        "- `material_group_split`: holds out whole `material_id` groups to test "
        "cross-material generalization.",
        "",
        "## Leakage Controls",
        "",
        "Excluded post-run or result-derived fields:",
        "",
        ", ".join(f"`{col}`" for col in sorted(POST_RUN_EXCLUDED_COLUMNS)),
        "",
        "These excluded fields include energies, forces, wall time, SCF iteration "
        "count, convergence flags, and failure labels. They are outcomes or "
        "post-run diagnostics, not valid pre-run predictors.",
        "",
        "## Metrics",
        "",
        _metrics_table(results),
        "",
        "## Feature Sets",
        "",
        _feature_sets(results),
        "",
        "## Confusion Matrices",
        "",
        *[_confusion_block(result) for result in results if result.confusion],
        "## Top Features",
        "",
        *[_features_block(result) for result in results if result.top_features],
        "## Scientific Caveats",
        "",
        "- The observed failure fraction is not a target to hide. It is the "
        "training signal for failure-risk-aware acquisition.",
        "- The random split can overestimate performance because related records "
        "from the same material can appear in both train and test sets.",
        "- The group split is stricter and should be treated as the more honest "
        "generalization test.",
        "- `material_id` is pre-run metadata, but it can encode local workflow "
        "history. The no-material ablation helps quantify that dependence.",
        "- The model does not inspect atomic geometry directly, so it should not "
        "replace the pre-QE overlap validator.",
        "- Metrics are v0.2 engineering evidence, not a publication-level claim.",
        "",
        "## Next Step",
        "",
        "Connect predicted failure risk to Bayesian acquisition, for example by "
        "using `score = acquisition_value - lambda_failure * failure_risk` for "
        "maximization or adding a failure penalty for minimization.",
        "",
    ]
    return "\n".join(lines)


def write_report(text: str, path: str | Path) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--table", default=str(DEFAULT_TABLE))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--predictions", default=str(DEFAULT_PREDICTIONS))
    args = parser.parse_args(argv)

    records = read_records(args.input)
    rows = build_ml_rows(records)
    write_ml_table(rows, args.table)
    results, predictions = train_experiments(rows)
    write_predictions(predictions, args.predictions)
    write_report(
        render_report(results, args.table, args.predictions, args.input),
        args.report,
    )
    print(f"Wrote {args.table}")
    print(f"Wrote {args.predictions}")
    print(f"Wrote {args.report}")
    return 0


def _train_one_experiment(
    rows: list[dict[str, object]],
    spec: ExperimentSpec,
    split: SplitData,
    random_state: int,
) -> tuple[list[ModelResult], list[dict[str, object]]]:
    y = np.array([int(row[LABEL_COLUMN]) for row in rows], dtype=int)
    train_rows = [rows[int(i)] for i in split.train_idx]
    test_rows = [rows[int(i)] for i in split.test_idx]
    X_train = [_features(row, split.feature_columns) for row in train_rows]
    X_test = [_features(row, split.feature_columns) for row in test_rows]
    y_train = y[split.train_idx]
    y_test = y[split.test_idx]

    models = _models(random_state)
    results: list[ModelResult] = []
    predictions: list[dict[str, object]] = []
    for model_name, estimator in models:
        if estimator is None:
            results.append(_skipped_result(spec, model_name, split, y_train, y_test))
            continue
        result, model_predictions = _evaluate_model(
            spec,
            model_name,
            estimator,
            X_train,
            X_test,
            y_train,
            y_test,
            test_rows,
        )
        results.append(result)
        predictions.extend(model_predictions)
    return results, predictions


def _models(random_state: int) -> list[tuple[str, object | None]]:
    return [
        (
            "LogisticRegression",
            LogisticRegression(
                max_iter=5000,
                solver="liblinear",
                class_weight="balanced",
            ),
        ),
        (
            "RandomForestClassifier",
            RandomForestClassifier(
                n_estimators=300,
                random_state=random_state,
                class_weight="balanced",
                min_samples_leaf=2,
            ),
        ),
        ("CatBoostClassifier", _make_catboost(random_state)),
    ]


def _evaluate_model(
    spec: ExperimentSpec,
    model_name: str,
    estimator: object,
    X_train: list[dict[str, object]],
    X_test: list[dict[str, object]],
    y_train: np.ndarray,
    y_test: np.ndarray,
    test_rows: list[dict[str, object]],
) -> tuple[ModelResult, list[dict[str, object]]]:
    pipeline = Pipeline([
        ("vectorizer", DictVectorizer(sparse=False)),
        ("model", estimator),
    ])
    pipeline.fit(X_train, y_train)
    pred = pipeline.predict(X_test)
    prob = _positive_probabilities(pipeline, X_test)
    feature_names = list(pipeline.named_steps["vectorizer"].get_feature_names_out())
    model = pipeline.named_steps["model"]
    result = ModelResult(
        experiment=spec.name,
        model=model_name,
        status="trained",
        feature_columns=spec.feature_columns,
        n_train=len(y_train),
        n_test=len(y_test),
        train_success=int(np.sum(y_train)),
        train_failure=int(len(y_train) - np.sum(y_train)),
        test_success=int(np.sum(y_test)),
        test_failure=int(len(y_test) - np.sum(y_test)),
        accuracy=accuracy_score(y_test, pred),
        precision=precision_score(y_test, pred, zero_division=0),
        recall=recall_score(y_test, pred, zero_division=0),
        failure_recall=recall_score(y_test, pred, pos_label=0, zero_division=0),
        f1=f1_score(y_test, pred, zero_division=0),
        roc_auc=roc_auc_score(y_test, prob) if prob is not None and len(set(y_test)) > 1 else None,
        confusion=confusion_matrix(y_test, pred).tolist(),
        top_features=_top_features(model, feature_names),
    )
    predictions = [
        {
            "experiment": spec.name,
            "model": model_name,
            "record_id": row["record_id"],
            "material_id": row["material_id"],
            "failure_label": row[FAILURE_LABEL_COLUMN],
            "true_success": int(y_true),
            "predicted_success": int(y_pred),
            "predicted_failure_risk": "" if prob is None else 1.0 - float(p_success),
            "split": "test",
        }
        for row, y_true, y_pred, p_success in zip(
            test_rows,
            y_test,
            pred,
            prob if prob is not None else [np.nan] * len(pred),
        )
    ]
    return result, predictions


def _skipped_result(
    spec: ExperimentSpec,
    model_name: str,
    split: SplitData,
    y_train: np.ndarray,
    y_test: np.ndarray,
) -> ModelResult:
    return ModelResult(
        experiment=spec.name,
        model=model_name,
        status="skipped: dependency not installed",
        feature_columns=spec.feature_columns,
        n_train=len(y_train),
        n_test=len(y_test),
        train_success=int(np.sum(y_train)),
        train_failure=int(len(y_train) - np.sum(y_train)),
        test_success=int(np.sum(y_test)),
        test_failure=int(len(y_test) - np.sum(y_test)),
    )


def _features(row: dict[str, object], feature_columns: list[str]) -> dict[str, object]:
    return {col: row[col] for col in feature_columns}


def _positive_probabilities(pipeline: Pipeline, X_test: list[dict[str, object]]) -> np.ndarray | None:
    if hasattr(pipeline, "predict_proba"):
        return pipeline.predict_proba(X_test)[:, 1]
    if hasattr(pipeline, "decision_function"):
        scores = pipeline.decision_function(X_test)
        return 1.0 / (1.0 + np.exp(-scores))
    return None


def _top_features(model: object, feature_names: list[str], limit: int = 15) -> list[tuple[str, float]] | None:
    if hasattr(model, "feature_importances_"):
        values = getattr(model, "feature_importances_")
        pairs = sorted(zip(feature_names, values), key=lambda item: abs(item[1]), reverse=True)
        return [(name, float(value)) for name, value in pairs[:limit]]
    if hasattr(model, "coef_"):
        coef = np.ravel(getattr(model, "coef_"))
        pairs = sorted(zip(feature_names, coef), key=lambda item: abs(item[1]), reverse=True)
        return [(name, float(value)) for name, value in pairs[:limit]]
    return None


def _make_catboost(random_state: int) -> object | None:
    try:
        from catboost import CatBoostClassifier
    except ImportError:
        return None
    return CatBoostClassifier(
        iterations=200,
        depth=6,
        learning_rate=0.05,
        loss_function="Logloss",
        verbose=False,
        random_seed=random_state,
    )


def _parse_pseudos(raw: str) -> dict[str, str]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return {str(k): str(v) for k, v in data.items()}


def _parse_kpoints(raw: str) -> tuple[int, int, int]:
    parts = str(raw).split()
    values: list[int] = []
    for part in parts[:3]:
        try:
            values.append(int(part))
        except ValueError:
            values.append(0)
    while len(values) < 3:
        values.append(0)
    return values[0], values[1], values[2]


def _float_or_none(raw: str | None) -> float | None:
    if raw in ("", None):
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _metrics_table(results: list[ModelResult]) -> str:
    lines = [
        "| Experiment | Model | Status | Train | Test | Train S/F | Test S/F | Accuracy | Precision | Recall | Failure Recall | F1 | ROC-AUC |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for result in results:
        lines.append(
            f"| {result.experiment} | {result.model} | {result.status} | "
            f"{result.n_train} | {result.n_test} | "
            f"{result.train_success}/{result.train_failure} | "
            f"{result.test_success}/{result.test_failure} | "
            f"{_fmt(result.accuracy)} | {_fmt(result.precision)} | "
            f"{_fmt(result.recall)} | {_fmt(result.failure_recall)} | "
            f"{_fmt(result.f1)} | {_fmt(result.roc_auc)} |"
        )
    return "\n".join(lines)


def _feature_sets(results: list[ModelResult]) -> str:
    seen: dict[str, list[str]] = {}
    for result in results:
        seen.setdefault(result.experiment, result.feature_columns)
    lines = ["| Experiment | Features |", "| --- | --- |"]
    for name, columns in seen.items():
        lines.append(f"| {name} | {', '.join(f'`{col}`' for col in columns)} |")
    return "\n".join(lines)


def _confusion_block(result: ModelResult) -> str:
    tn, fp = result.confusion[0]
    fn, tp = result.confusion[1]
    return (
        f"### {result.experiment} / {result.model}\n\n"
        "|  | Predicted failure | Predicted success |\n"
        "| --- | ---: | ---: |\n"
        f"| Actual failure | {tn} | {fp} |\n"
        f"| Actual success | {fn} | {tp} |\n\n"
    )


def _features_block(result: ModelResult) -> str:
    lines = [
        f"### {result.experiment} / {result.model}",
        "",
        "| Feature | Weight/importances |",
        "| --- | ---: |",
    ]
    for name, value in result.top_features or []:
        lines.append(f"| `{name}` | {value:.6g} |")
    lines.append("")
    return "\n".join(lines)


def _fmt(value: float | None) -> str:
    return "NA" if value is None else f"{value:.3f}"


def _repo_path(path: str | Path) -> str:
    item = Path(path)
    try:
        return str(item.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(item)


if __name__ == "__main__":
    raise SystemExit(main())
