from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction import DictVectorizer
from sklearn.impute import SimpleImputer
from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.neighbors import NearestNeighbors
from sklearn.pipeline import Pipeline

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.train_qe_reliability_classifier import (
    DEFAULT_INPUT,
    FAILURE_LABEL_COLUMN,
    FAILURE_RISK_THRESHOLDS,
    FEATURE_COLUMNS,
    LABEL_COLUMN,
    build_ml_rows,
    failure_taxonomy,
    read_records,
)


DEFAULT_DIAGNOSIS_REPORT = ROOT / "reports" / "qe_reliability_group_split_diagnosis_v031.md"
DEFAULT_DIAGNOSIS_PREDICTIONS = ROOT / "data" / "qe_reliability_group_split_predictions_v031.csv"
DEFAULT_V032_REPORT = ROOT / "reports" / "qe_reliability_classifier_v032_group_generalization.md"
DEFAULT_V032_PREDICTIONS = ROOT / "data" / "qe_reliability_predictions_v032.csv"

RISK_TARGETS = {
    "setup_error_risk": "setup_error",
    "scf_failure_risk": "scf_not_converged",
    "runtime_incomplete_risk": "runtime_incomplete",
}


@dataclass(frozen=True)
class RiskMetrics:
    split_id: int
    threshold: float
    failure_recall: float
    failure_precision: float
    f1: float
    roc_auc: float | None
    confusion: list[list[int]]


def run_v031_diagnosis(
    input_path: str | Path = DEFAULT_INPUT,
    report_path: str | Path = DEFAULT_DIAGNOSIS_REPORT,
    predictions_path: str | Path = DEFAULT_DIAGNOSIS_PREDICTIONS,
    random_state: int = 42,
) -> None:
    rows = build_ml_rows(read_records(input_path))
    split = _group_split(rows, random_state)
    train_rows = [rows[int(idx)] for idx in split[0]]
    test_rows = [rows[int(idx)] for idx in split[1]]
    y_train = np.array([int(row[LABEL_COLUMN]) for row in train_rows], dtype=int)
    y_test = np.array([int(row[LABEL_COLUMN]) for row in test_rows], dtype=int)
    model = _fit_success_model(train_rows, y_train, random_state)
    success_prob = model.predict_proba(_feature_dicts(test_rows))[:, 1]
    failure_risk = 1.0 - success_prob

    prediction_rows = _diagnosis_prediction_rows(test_rows, y_test, success_prob, failure_risk)
    _write_csv(prediction_rows, predictions_path)
    report = render_v031_report(train_rows, test_rows, y_test, failure_risk, input_path, predictions_path)
    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
    Path(report_path).write_text(report, encoding="utf-8")


def render_v031_report(
    train_rows: list[dict[str, object]],
    test_rows: list[dict[str, object]],
    y_test_success: np.ndarray,
    failure_risk: np.ndarray,
    input_path: str | Path,
    predictions_path: str | Path,
) -> str:
    y_failure = 1 - y_test_success
    lines = [
        "# QE Reliability Group-Split Diagnosis v0.3.1",
        "",
        "## Purpose",
        "",
        "This report diagnoses why the material-group split in v0.3 failed to "
        "detect held-out failures. It does not run QE/DFT, change parser logic, "
        "delete records, or relabel failures.",
        "",
        "## Files",
        "",
        f"- Input records: `{_repo_path(input_path)}`",
        f"- Per-row predictions: `{_repo_path(predictions_path)}`",
        "",
        "## Failure Taxonomy",
        "",
        "- `success`: original success rows",
        "- `setup_error`: original `qe_error` rows",
        "- `scf_not_converged`: original `scf_not_converged` rows",
        "- `runtime_incomplete`: original `job_not_completed` rows",
        "- `invalid_geometry`: reserved for invalid geometry quarantine rows",
        "- `unknown_failure`: any unmapped non-success failure label",
        "",
        "## Held-Out Material Groups",
        "",
        _distribution_table(test_rows),
        "",
        "## Training Material Groups",
        "",
        _distribution_table(train_rows),
        "",
        "## Failure-Risk Threshold Sweep",
        "",
        _failure_threshold_table(y_failure, failure_risk),
        "",
        "## Diagnosis",
        "",
        _risk_diagnosis(y_failure, failure_risk),
        "",
    ]
    return "\n".join(lines)


def run_v032_generalization(
    input_path: str | Path = DEFAULT_INPUT,
    report_path: str | Path = DEFAULT_V032_REPORT,
    predictions_path: str | Path = DEFAULT_V032_PREDICTIONS,
    random_state: int = 42,
    n_splits: int = 20,
) -> None:
    rows = build_ml_rows(read_records(input_path))
    metrics, predictions = repeated_group_risk_experiment(rows, random_state, n_splits)
    _write_csv(predictions, predictions_path)
    report = render_v032_report(metrics, input_path, predictions_path, n_splits)
    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
    Path(report_path).write_text(report, encoding="utf-8")


def repeated_group_risk_experiment(
    rows: list[dict[str, object]],
    random_state: int = 42,
    n_splits: int = 20,
) -> tuple[list[RiskMetrics], list[dict[str, object]]]:
    groups = np.array([str(row["material_id"]) for row in rows])
    y_failure_all = np.array([0 if int(row[LABEL_COLUMN]) == 1 else 1 for row in rows], dtype=int)
    splitter = GroupShuffleSplit(n_splits=n_splits, test_size=0.2, random_state=random_state)
    metrics: list[RiskMetrics] = []
    predictions: list[dict[str, object]] = []
    for split_id, (train_idx, test_idx) in enumerate(splitter.split(np.arange(len(rows)), y_failure_all, groups)):
        train_rows = [rows[int(idx)] for idx in train_idx]
        test_rows = [rows[int(idx)] for idx in test_idx]
        risk_probs = _risk_probabilities(train_rows, test_rows, random_state + split_id)
        total_risk = _combine_risks(risk_probs)
        y_failure = np.array([0 if int(row[LABEL_COLUMN]) == 1 else 1 for row in test_rows], dtype=int)
        roc_auc = roc_auc_score(y_failure, total_risk) if len(set(y_failure)) > 1 else None
        ood_scores, ood_flags = _ood_scores(train_rows, test_rows)
        for threshold in FAILURE_RISK_THRESHOLDS:
            pred_failure = (total_risk >= threshold).astype(int)
            metrics.append(RiskMetrics(
                split_id=split_id,
                threshold=threshold,
                failure_recall=recall_score(y_failure, pred_failure, zero_division=0),
                failure_precision=precision_score(y_failure, pred_failure, zero_division=0),
                f1=f1_score(y_failure, pred_failure, zero_division=0),
                roc_auc=roc_auc,
                confusion=confusion_matrix(y_failure, pred_failure, labels=[0, 1]).tolist(),
            ))
            for row, true_failure, pred, setup, scf, runtime, total, ood_score, ood_flag in zip(
                test_rows,
                y_failure,
                pred_failure,
                risk_probs["setup_error_risk"],
                risk_probs["scf_failure_risk"],
                risk_probs["runtime_incomplete_risk"],
                total_risk,
                ood_scores,
                ood_flags,
            ):
                predictions.append({
                    "split_id": split_id,
                    "threshold": threshold,
                    "record_id": row["record_id"],
                    "material_id": row["material_id"],
                    "failure_label": row[FAILURE_LABEL_COLUMN],
                    "failure_taxonomy": row["failure_taxonomy"],
                    "true_failure": int(true_failure),
                    "setup_error_risk": float(setup),
                    "scf_failure_risk": float(scf),
                    "runtime_incomplete_risk": float(runtime),
                    "total_failure_risk": float(total),
                    "predicted_failure": int(pred),
                    "ood_distance": float(ood_score),
                    "ood_flag": int(ood_flag),
                })
    return metrics, predictions


def render_v032_report(
    metrics: list[RiskMetrics],
    input_path: str | Path,
    predictions_path: str | Path,
    n_splits: int,
) -> str:
    lines = [
        "# QE Reliability Classifier v0.3.2 Group Generalization",
        "",
        "## Purpose",
        "",
        "This experiment improves the v0.3 held-out-material analysis by using "
        "separate failure-risk targets, lower failure-risk thresholds, repeated "
        "group splits, and an OOD distance flag.",
        "",
        "## Files",
        "",
        f"- Input records: `{_repo_path(input_path)}`",
        f"- Predictions: `{_repo_path(predictions_path)}`",
        f"- Repeated group splits: **{n_splits}**",
        "",
        "## Model",
        "",
        "Separate balanced RandomForest risk models are trained for setup errors, "
        "SCF non-convergence, and runtime incompletion. Total failure risk is "
        "`1 - product(1 - component_risk)`.",
        "",
        "## Repeated Group-Split Metrics",
        "",
        _metric_summary_table(metrics),
        "",
        "## Scientific Caveats",
        "",
        "- The current records still lack trustworthy atom counts, cell volumes, "
        "and true stoichiometric fractions, so some requested descriptors remain "
        "nullable or species-presence approximations.",
        "- Runtime incompletion may reflect walltime or machine interruption rather "
        "than chemistry, so it is modeled separately.",
        "- Group-split metrics are the honest signal for new materials. If failure "
        "recall remains low, this model should be used only as an in-domain "
        "workflow triage aid.",
        "",
    ]
    return "\n".join(lines)


def _group_split(rows: list[dict[str, object]], random_state: int) -> tuple[np.ndarray, np.ndarray]:
    y = np.array([int(row[LABEL_COLUMN]) for row in rows], dtype=int)
    groups = np.array([str(row["material_id"]) for row in rows])
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=random_state)
    return next(splitter.split(np.arange(len(rows)), y, groups))


def _fit_success_model(
    train_rows: list[dict[str, object]],
    y_train: np.ndarray,
    random_state: int,
) -> Pipeline:
    model = Pipeline([
        ("vectorizer", DictVectorizer(sparse=False)),
        ("imputer", SimpleImputer(strategy="constant", fill_value=0.0, keep_empty_features=True)),
        ("model", RandomForestClassifier(
            n_estimators=300,
            random_state=random_state,
            class_weight="balanced",
            min_samples_leaf=2,
        )),
    ])
    model.fit(_feature_dicts(train_rows), y_train)
    return model


def _fit_binary_risk_model(
    train_rows: list[dict[str, object]],
    target_taxonomy: str,
    random_state: int,
) -> Pipeline | float:
    y = np.array([1 if row["failure_taxonomy"] == target_taxonomy else 0 for row in train_rows], dtype=int)
    if len(set(y)) < 2:
        return float(y[0]) if len(y) else 0.0
    model = Pipeline([
        ("vectorizer", DictVectorizer(sparse=False)),
        ("imputer", SimpleImputer(strategy="constant", fill_value=0.0, keep_empty_features=True)),
        ("model", RandomForestClassifier(
            n_estimators=300,
            random_state=random_state,
            class_weight="balanced",
            min_samples_leaf=2,
        )),
    ])
    model.fit(_feature_dicts(train_rows), y)
    return model


def _risk_probabilities(
    train_rows: list[dict[str, object]],
    test_rows: list[dict[str, object]],
    random_state: int,
) -> dict[str, np.ndarray]:
    output: dict[str, np.ndarray] = {}
    for offset, (risk_name, taxonomy) in enumerate(RISK_TARGETS.items()):
        model = _fit_binary_risk_model(train_rows, taxonomy, random_state + offset)
        if isinstance(model, float):
            output[risk_name] = np.full(len(test_rows), model)
        else:
            output[risk_name] = model.predict_proba(_feature_dicts(test_rows))[:, 1]
    return output


def _combine_risks(risks: dict[str, np.ndarray]) -> np.ndarray:
    safe_prob = np.ones(len(next(iter(risks.values()))))
    for values in risks.values():
        safe_prob *= 1.0 - values
    return 1.0 - safe_prob


def _feature_dicts(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return [{col: row[col] for col in FEATURE_COLUMNS} for row in rows]


def _ood_scores(train_rows: list[dict[str, object]], test_rows: list[dict[str, object]]) -> tuple[np.ndarray, np.ndarray]:
    vectorizer = DictVectorizer(sparse=False)
    imputer = SimpleImputer(strategy="constant", fill_value=0.0, keep_empty_features=True)
    x_train = imputer.fit_transform(vectorizer.fit_transform(_feature_dicts(train_rows)))
    x_test = imputer.transform(vectorizer.transform(_feature_dicts(test_rows)))
    if len(x_train) < 2:
        distances = np.zeros(len(x_test))
        return distances, np.zeros(len(x_test), dtype=int)
    train_nn = NearestNeighbors(n_neighbors=2).fit(x_train)
    train_distances = train_nn.kneighbors(x_train, return_distance=True)[0][:, 1]
    threshold = float(np.quantile(train_distances, 0.95))
    test_nn = NearestNeighbors(n_neighbors=1).fit(x_train)
    test_distances = test_nn.kneighbors(x_test, return_distance=True)[0][:, 0]
    return test_distances, (test_distances > threshold).astype(int)


def _diagnosis_prediction_rows(
    test_rows: list[dict[str, object]],
    y_test_success: np.ndarray,
    success_prob: np.ndarray,
    failure_risk: np.ndarray,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for row, true_success, p_success, risk in zip(test_rows, y_test_success, success_prob, failure_risk):
        item = {
            "material_id": row["material_id"],
            "true_label": "success" if int(true_success) == 1 else "failure",
            "failure_reason": row[FAILURE_LABEL_COLUMN],
            "failure_taxonomy": failure_taxonomy(str(row[FAILURE_LABEL_COLUMN])),
            "predicted_success_probability": float(p_success),
            "predicted_failure_risk": float(risk),
        }
        for threshold in FAILURE_RISK_THRESHOLDS:
            item[f"predicted_label_t_{threshold:.2f}".replace(".", "p")] = (
                "failure" if risk >= threshold else "success"
            )
        rows.append(item)
    return rows


def _failure_threshold_table(y_failure: np.ndarray, failure_risk: np.ndarray) -> str:
    lines = [
        "| Failure-risk threshold | Failure recall | Failure precision | F1 | Confusion [[TN, FP], [FN, TP]] |",
        "| ---: | ---: | ---: | ---: | --- |",
    ]
    for threshold in FAILURE_RISK_THRESHOLDS:
        pred_failure = (failure_risk >= threshold).astype(int)
        lines.append(
            f"| {threshold:.2f} | "
            f"{recall_score(y_failure, pred_failure, zero_division=0):.3f} | "
            f"{precision_score(y_failure, pred_failure, zero_division=0):.3f} | "
            f"{f1_score(y_failure, pred_failure, zero_division=0):.3f} | "
            f"{confusion_matrix(y_failure, pred_failure, labels=[0, 1]).tolist()} |"
        )
    return "\n".join(lines)


def _distribution_table(rows: list[dict[str, object]]) -> str:
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        counts[str(row["material_id"])][str(row["failure_taxonomy"])] += 1
    lines = ["| material_id | total | taxonomy distribution |", "| --- | ---: | --- |"]
    for material_id in sorted(counts):
        total = sum(counts[material_id].values())
        dist = ", ".join(f"{key}={value}" for key, value in sorted(counts[material_id].items()))
        lines.append(f"| `{material_id}` | {total} | {dist} |")
    return "\n".join(lines)


def _risk_diagnosis(y_failure: np.ndarray, failure_risk: np.ndarray) -> str:
    true_failure_risk = failure_risk[y_failure == 1]
    if len(true_failure_risk) == 0:
        return "- No true failures appeared in the held-out group split."
    median_risk = float(np.median(true_failure_risk))
    if median_risk < 0.05:
        reason = "feature/data problem: true failures receive near-zero risk."
    elif median_risk < 0.20:
        reason = "threshold problem mixed with weak calibration."
    else:
        reason = "threshold selection can recover some failures."
    return "\n".join([
        f"- True-failure median failure risk: {median_risk:.3f}.",
        f"- Diagnosis: {reason}",
    ])


def _metric_summary_table(metrics: list[RiskMetrics]) -> str:
    by_threshold: dict[float, list[RiskMetrics]] = defaultdict(list)
    for item in metrics:
        by_threshold[item.threshold].append(item)
    lines = [
        "| Threshold | Failure recall mean +/- std | Failure precision mean +/- std | F1 mean +/- std | ROC-AUC mean +/- std |",
        "| ---: | ---: | ---: | ---: | ---: |",
    ]
    for threshold in sorted(by_threshold):
        items = by_threshold[threshold]
        lines.append(
            f"| {threshold:.2f} | "
            f"{_mean_std([m.failure_recall for m in items])} | "
            f"{_mean_std([m.failure_precision for m in items])} | "
            f"{_mean_std([m.f1 for m in items])} | "
            f"{_mean_std([m.roc_auc for m in items if m.roc_auc is not None])} |"
        )
    return "\n".join(lines)


def _mean_std(values: list[float]) -> str:
    if not values:
        return "NA"
    return f"{float(np.mean(values)):.3f} +/- {float(np.std(values)):.3f}"


def _write_csv(rows: list[dict[str, object]], path: str | Path) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) if rows else []
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _repo_path(path: str | Path) -> str:
    item = Path(path)
    try:
        return str(item.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(item)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--diagnosis-report", default=str(DEFAULT_DIAGNOSIS_REPORT))
    parser.add_argument("--diagnosis-predictions", default=str(DEFAULT_DIAGNOSIS_PREDICTIONS))
    parser.add_argument("--v032-report", default=str(DEFAULT_V032_REPORT))
    parser.add_argument("--v032-predictions", default=str(DEFAULT_V032_PREDICTIONS))
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--n-splits", type=int, default=20)
    args = parser.parse_args(argv)

    run_v031_diagnosis(args.input, args.diagnosis_report, args.diagnosis_predictions, args.random_state)
    run_v032_generalization(
        args.input,
        args.v032_report,
        args.v032_predictions,
        args.random_state,
        args.n_splits,
    )
    print(f"Wrote {args.diagnosis_predictions}")
    print(f"Wrote {args.diagnosis_report}")
    print(f"Wrote {args.v032_predictions}")
    print(f"Wrote {args.v032_report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
