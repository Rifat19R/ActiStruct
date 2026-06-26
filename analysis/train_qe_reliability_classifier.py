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
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "parsed_records" / "qe_reliability_records.csv"
DEFAULT_TABLE = ROOT / "data" / "qe_reliability_ml_table.csv"
DEFAULT_REPORT = ROOT / "reports" / "qe_reliability_classifier_v0.md"

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
class ModelResult:
    name: str
    status: str
    accuracy: float | None = None
    precision: float | None = None
    recall: float | None = None
    f1: float | None = None
    roc_auc: float | None = None
    confusion: list[list[int]] | None = None
    top_features: list[tuple[str, float]] | None = None


def read_records(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def build_ml_rows(records: Iterable[dict[str, str]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for record in records:
        failure_label = record.get("failure_reason") or "success"
        pseudos = _parse_pseudos(record.get("pseudopotentials", ""))
        k1, k2, k3 = _parse_kpoints(record.get("kpoints", ""))
        rows.append({
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
    columns = [FAILURE_LABEL_COLUMN, LABEL_COLUMN, *FEATURE_COLUMNS]
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def train_models(
    rows: list[dict[str, object]],
    random_state: int = 42,
) -> tuple[list[ModelResult], dict[str, object]]:
    X_rows = [{col: row[col] for col in FEATURE_COLUMNS} for row in rows]
    y = np.array([int(row[LABEL_COLUMN]) for row in rows], dtype=int)
    X_train, X_test, y_train, y_test = train_test_split(
        X_rows,
        y,
        test_size=0.2,
        random_state=random_state,
        stratify=y,
    )
    split_info = {
        "n_total": len(rows),
        "n_train": len(X_train),
        "n_test": len(X_test),
        "n_success": int(np.sum(y)),
        "n_failure": int(len(y) - np.sum(y)),
    }

    models: list[tuple[str, object]] = [
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
    ]
    catboost_result = _make_catboost(random_state)
    if catboost_result is not None:
        models.append(("CatBoostClassifier", catboost_result))

    results = [
        _evaluate_model(name, estimator, X_train, X_test, y_train, y_test)
        for name, estimator in models
    ]
    if catboost_result is None:
        results.append(ModelResult("CatBoostClassifier", "skipped: dependency not installed"))
    return results, split_info


def render_report(
    results: list[ModelResult],
    split_info: dict[str, object],
    table_path: str | Path,
    input_path: str | Path,
) -> str:
    lines = [
        "# QE Reliability Classifier v0.1",
        "",
        "## Purpose",
        "",
        "This model predicts whether a Quantum ESPRESSO calculation record is "
        "expected to be successful using setup metadata only. The binary label "
        "is `success=1` when `failure_label == \"success\"`; all other failure "
        "labels are `success=0`.",
        "",
        "## Data",
        "",
        f"- Input records: `{_repo_path(input_path)}`",
        f"- ML table: `{_repo_path(table_path)}`",
        f"- Total rows: **{split_info['n_total']}**",
        f"- Train rows: **{split_info['n_train']}**",
        f"- Test rows: **{split_info['n_test']}**",
        f"- Success rows: **{split_info['n_success']}**",
        f"- Failure rows: **{split_info['n_failure']}**",
        "",
        "## Features Used",
        "",
        ", ".join(f"`{col}`" for col in FEATURE_COLUMNS),
        "",
        "## Leakage Controls",
        "",
        "The classifier excludes post-run or result-derived fields:",
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
        "## Confusion Matrices",
        "",
        *[_confusion_block(result) for result in results if result.confusion],
        "## Top Features",
        "",
        *[_features_block(result) for result in results if result.top_features],
        "## Scientific Caveats",
        "",
        "- The current dataset is local and scratch-heavy, so the model may learn "
        "project-specific workflow patterns rather than general DFT reliability.",
        "- `material_id` is a pre-run metadata field, but it can encode local "
        "workflow history and should be ablated in the next version.",
        "- The model does not inspect atomic geometry directly, so it should not "
        "replace the pre-QE overlap validator.",
        "- Metrics are a v0.1 baseline on one train/test split, not a publication "
        "claim.",
        "- Records from other electronic-structure codes must be modeled with "
        "source-code provenance preserved.",
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
    args = parser.parse_args(argv)

    records = read_records(args.input)
    rows = build_ml_rows(records)
    write_ml_table(rows, args.table)
    results, split_info = train_models(rows)
    write_report(render_report(results, split_info, args.table, args.input), args.report)
    print(f"Wrote {args.table}")
    print(f"Wrote {args.report}")
    return 0


def _evaluate_model(
    name: str,
    estimator: object,
    X_train: list[dict[str, object]],
    X_test: list[dict[str, object]],
    y_train: np.ndarray,
    y_test: np.ndarray,
) -> ModelResult:
    pipeline = Pipeline([
        ("vectorizer", DictVectorizer(sparse=False)),
        ("model", estimator),
    ])
    pipeline.fit(X_train, y_train)
    pred = pipeline.predict(X_test)
    prob = _positive_probabilities(pipeline, X_test)
    feature_names = list(pipeline.named_steps["vectorizer"].get_feature_names_out())
    model = pipeline.named_steps["model"]
    return ModelResult(
        name=name,
        status="trained",
        accuracy=accuracy_score(y_test, pred),
        precision=precision_score(y_test, pred, zero_division=0),
        recall=recall_score(y_test, pred, zero_division=0),
        f1=f1_score(y_test, pred, zero_division=0),
        roc_auc=roc_auc_score(y_test, prob) if prob is not None and len(set(y_test)) > 1 else None,
        confusion=confusion_matrix(y_test, pred).tolist(),
        top_features=_top_features(model, feature_names),
    )


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
        "| Model | Status | Accuracy | Precision | Recall | F1 | ROC-AUC |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for result in results:
        lines.append(
            f"| {result.name} | {result.status} | {_fmt(result.accuracy)} | "
            f"{_fmt(result.precision)} | {_fmt(result.recall)} | "
            f"{_fmt(result.f1)} | {_fmt(result.roc_auc)} |"
        )
    return "\n".join(lines)


def _confusion_block(result: ModelResult) -> str:
    tn, fp = result.confusion[0]
    fn, tp = result.confusion[1]
    return (
        f"### {result.name}\n\n"
        "|  | Predicted failure | Predicted success |\n"
        "| --- | ---: | ---: |\n"
        f"| Actual failure | {tn} | {fp} |\n"
        f"| Actual success | {fn} | {tp} |\n\n"
    )


def _features_block(result: ModelResult) -> str:
    lines = [f"### {result.name}", "", "| Feature | Weight/importances |", "| --- | ---: |"]
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
