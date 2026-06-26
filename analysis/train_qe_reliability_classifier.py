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
from sklearn.impute import SimpleImputer


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "parsed_records" / "qe_reliability_records.csv"
DEFAULT_TABLE = ROOT / "data" / "qe_reliability_ml_table.csv"
DEFAULT_REPORT = ROOT / "reports" / "qe_reliability_classifier_v03_generalization.md"
DEFAULT_PREDICTIONS = ROOT / "data" / "qe_reliability_predictions_v03.csv"

LABEL_COLUMN = "success"
FAILURE_LABEL_COLUMN = "failure_label"
THRESHOLDS = [0.3, 0.4, 0.5, 0.6, 0.7]

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

ELEMENT_DATA = {
    "H": {"atomic_number": 1, "atomic_mass": 1.008, "electronegativity": 2.20},
    "Li": {"atomic_number": 3, "atomic_mass": 6.94, "electronegativity": 0.98},
    "C": {"atomic_number": 6, "atomic_mass": 12.011, "electronegativity": 2.55},
    "N": {"atomic_number": 7, "atomic_mass": 14.007, "electronegativity": 3.04},
    "O": {"atomic_number": 8, "atomic_mass": 15.999, "electronegativity": 3.44},
    "Na": {"atomic_number": 11, "atomic_mass": 22.990, "electronegativity": 0.93},
    "Mg": {"atomic_number": 12, "atomic_mass": 24.305, "electronegativity": 1.31},
    "Al": {"atomic_number": 13, "atomic_mass": 26.982, "electronegativity": 1.61},
    "Si": {"atomic_number": 14, "atomic_mass": 28.085, "electronegativity": 1.90},
    "P": {"atomic_number": 15, "atomic_mass": 30.974, "electronegativity": 2.19},
    "S": {"atomic_number": 16, "atomic_mass": 32.06, "electronegativity": 2.58},
    "K": {"atomic_number": 19, "atomic_mass": 39.098, "electronegativity": 0.82},
    "Ca": {"atomic_number": 20, "atomic_mass": 40.078, "electronegativity": 1.00},
    "Ti": {"atomic_number": 22, "atomic_mass": 47.867, "electronegativity": 1.54},
    "V": {"atomic_number": 23, "atomic_mass": 50.942, "electronegativity": 1.63},
    "Fe": {"atomic_number": 26, "atomic_mass": 55.845, "electronegativity": 1.83},
    "Co": {"atomic_number": 27, "atomic_mass": 58.933, "electronegativity": 1.88},
    "Ni": {"atomic_number": 28, "atomic_mass": 58.693, "electronegativity": 1.91},
    "Cu": {"atomic_number": 29, "atomic_mass": 63.546, "electronegativity": 1.90},
    "Zn": {"atomic_number": 30, "atomic_mass": 65.38, "electronegativity": 1.65},
    "As": {"atomic_number": 33, "atomic_mass": 74.922, "electronegativity": 2.18},
    "Sr": {"atomic_number": 38, "atomic_mass": 87.62, "electronegativity": 0.95},
    "Mo": {"atomic_number": 42, "atomic_mass": 95.95, "electronegativity": 2.16},
    "Ag": {"atomic_number": 47, "atomic_mass": 107.868, "electronegativity": 1.93},
    "I": {"atomic_number": 53, "atomic_mass": 126.904, "electronegativity": 2.66},
    "Ba": {"atomic_number": 56, "atomic_mass": 137.327, "electronegativity": 0.89},
    "W": {"atomic_number": 74, "atomic_mass": 183.84, "electronegativity": 2.36},
    "Pt": {"atomic_number": 78, "atomic_mass": 195.084, "electronegativity": 2.28},
    "Au": {"atomic_number": 79, "atomic_mass": 196.967, "electronegativity": 2.54},
    "Pb": {"atomic_number": 82, "atomic_mass": 207.2, "electronegativity": 2.33},
}

TRANSITION_METALS = {
    "Sc", "Ti", "V", "Cr", "Mn", "Fe", "Co", "Ni", "Cu", "Zn",
    "Y", "Zr", "Nb", "Mo", "Tc", "Ru", "Rh", "Pd", "Ag", "Cd",
    "Hf", "Ta", "W", "Re", "Os", "Ir", "Pt", "Au", "Hg",
}

ELEMENT_COUNT_COLUMNS = [f"element_count_{symbol}" for symbol in sorted(ELEMENT_DATA)]

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
    "n_atoms",
    "n_species",
    "elements",
    "atomic_number_mean",
    "atomic_number_min",
    "atomic_number_max",
    "atomic_mass_mean",
    "electronegativity_mean",
    "has_transition_metal",
    "has_oxygen",
    "has_hydrogen",
    "ecutrho_over_ecutwfc",
    "volume_per_atom",
    *ELEMENT_COUNT_COLUMNS,
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
class ThresholdResult:
    threshold: float
    precision: float
    recall: float
    failure_recall: float
    f1: float
    confusion: list[list[int]]


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
    threshold_metrics: list[ThresholdResult] | None = None


def read_records(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def build_ml_rows(records: Iterable[dict[str, str]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index, record in enumerate(records):
        failure_label = record.get("failure_reason") or "success"
        pseudos = _parse_pseudos(record.get("pseudopotentials", ""))
        elements = sorted(pseudos)
        k1, k2, k3 = _parse_kpoints(record.get("kpoints", ""))
        ecutwfc = _float_or_none(record.get("ecutwfc"))
        ecutrho = _float_or_none(record.get("ecutrho"))
        row = {
            "record_id": index,
            FAILURE_LABEL_COLUMN: failure_label,
            LABEL_COLUMN: 1 if failure_label == "success" else 0,
            "material_id": record.get("material_id") or "unknown",
            "ecutwfc": ecutwfc,
            "ecutrho": ecutrho,
            "k1": k1,
            "k2": k2,
            "k3": k3,
            "kpoint_product": k1 * k2 * k3,
            "smearing": record.get("smearing") or "unknown",
            "mixing_beta": _float_or_none(record.get("mixing_beta")),
            "pseudo_family": record.get("pseudo_family") or "unknown",
            "n_species": len(elements),
            "elements": " ".join(elements) or "unknown",
        }
        row.update(build_element_descriptors(elements, ecutwfc, ecutrho))
        rows.append(row)
    return rows


def build_element_descriptors(
    elements: Iterable[str],
    ecutwfc: float | None = None,
    ecutrho: float | None = None,
) -> dict[str, object]:
    symbols = sorted({symbol for symbol in elements if symbol})
    known = [ELEMENT_DATA[symbol] for symbol in symbols if symbol in ELEMENT_DATA]
    atomic_numbers = [float(item["atomic_number"]) for item in known]
    atomic_masses = [float(item["atomic_mass"]) for item in known]
    electronegativities = [
        float(item["electronegativity"])
        for item in known
        if item.get("electronegativity") is not None
    ]
    descriptors: dict[str, object] = {
        "n_atoms": None,
        "atomic_number_mean": _mean_or_none(atomic_numbers),
        "atomic_number_min": min(atomic_numbers) if atomic_numbers else None,
        "atomic_number_max": max(atomic_numbers) if atomic_numbers else None,
        "atomic_mass_mean": _mean_or_none(atomic_masses),
        "electronegativity_mean": _mean_or_none(electronegativities),
        "has_transition_metal": int(any(symbol in TRANSITION_METALS for symbol in symbols)),
        "has_oxygen": int("O" in symbols),
        "has_hydrogen": int("H" in symbols),
        "ecutrho_over_ecutwfc": (
            ecutrho / ecutwfc
            if ecutwfc is not None and ecutrho is not None and ecutwfc > 0
            else None
        ),
        "volume_per_atom": None,
    }
    for column in ELEMENT_COUNT_COLUMNS:
        symbol = column.removeprefix("element_count_")
        descriptors[column] = int(symbol in symbols)
    return descriptors


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
        "threshold",
        "record_id",
        "material_id",
        "failure_label",
        "true_success",
        "predicted_success",
        "success_probability",
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
        "# QE Reliability Classifier v0.3 Generalization",
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
        "## Descriptor Features",
        "",
        "v0.3 adds pre-run descriptors derived from setup metadata: species count, "
        "element presence/count indicators, atomic number/mass/electronegativity "
        "summaries, transition-metal/oxygen/hydrogen flags, `ecutrho/ecutwfc`, "
        "and k-point product.",
        "",
        "`n_atoms` and `volume_per_atom` are included as nullable columns because "
        "the current parsed reliability records do not carry trustworthy atom "
        "counts or cell volumes. Element counts are species-presence indicators "
        "from pseudopotential declarations, not stoichiometric atom counts.",
        "",
        "## Default Threshold Metrics",
        "",
        _metrics_table(results),
        "",
        "## Threshold Sweep",
        "",
        "Thresholds are applied to `success_probability`. Higher thresholds are "
        "more conservative: they classify more calculations as risky, which can "
        "improve failure recall at the cost of rejecting more potentially "
        "successful candidates.",
        "",
        _threshold_table(results),
        "",
        "## Generalization Readout",
        "",
        _generalization_summary(results),
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
        "- The random split measures in-domain interpolation over current records "
        "and can overestimate performance because related records can appear in "
        "both train and test sets.",
        "- The group split is the stricter held-out-material test and should guide "
        "deployment caution.",
        "- Missing atom counts and cell volumes limit descriptor strength. Current "
        "element indicators describe species presence, not full composition.",
        "- `material_id` is pre-run metadata, but it can encode local workflow "
        "history. The no-material ablation helps quantify that dependence.",
        "- The model does not inspect atomic geometry directly, so it should not "
        "replace the pre-QE overlap validator.",
        "- Metrics are v0.3 engineering evidence, not a publication-level claim.",
        "",
        "## Next Step",
        "",
        "Connect predicted failure risk to Bayesian acquisition, for example by "
        "using `score = acquisition_value - lambda_failure * failure_risk` for "
        "maximization or adding a failure penalty for minimization. Choose the "
        "operating threshold from the grouped split, where possible, because it "
        "is the more honest proxy for new-material behavior.",
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
        ("imputer", SimpleImputer(strategy="constant", fill_value=0.0, keep_empty_features=True)),
        ("model", estimator),
    ])
    pipeline.fit(X_train, y_train)
    prob = _positive_probabilities(pipeline, X_test)
    pred = (prob >= 0.5).astype(int) if prob is not None else pipeline.predict(X_test)
    threshold_metrics = _threshold_metrics(y_test, prob)
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
        threshold_metrics=threshold_metrics,
    )
    predictions: list[dict[str, object]] = []
    prediction_thresholds = THRESHOLDS if prob is not None else [0.5]
    success_probabilities = prob if prob is not None else np.asarray(pred, dtype=float)
    for threshold in prediction_thresholds:
        threshold_pred = (success_probabilities >= threshold).astype(int)
        for row, y_true, y_pred, p_success in zip(
            test_rows,
            y_test,
            threshold_pred,
            success_probabilities,
        ):
            predictions.append({
                "experiment": spec.name,
                "model": model_name,
                "threshold": threshold,
                "record_id": row["record_id"],
                "material_id": row["material_id"],
                "failure_label": row[FAILURE_LABEL_COLUMN],
                "true_success": int(y_true),
                "predicted_success": int(y_pred),
                "success_probability": float(p_success),
                "predicted_failure_risk": 1.0 - float(p_success),
                "split": "test",
            })
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


def _threshold_metrics(y_true: np.ndarray, probabilities: np.ndarray | None) -> list[ThresholdResult] | None:
    if probabilities is None:
        return None
    results: list[ThresholdResult] = []
    for threshold in THRESHOLDS:
        pred = (probabilities >= threshold).astype(int)
        results.append(ThresholdResult(
            threshold=threshold,
            precision=precision_score(y_true, pred, zero_division=0),
            recall=recall_score(y_true, pred, zero_division=0),
            failure_recall=recall_score(y_true, pred, pos_label=0, zero_division=0),
            f1=f1_score(y_true, pred, zero_division=0),
            confusion=confusion_matrix(y_true, pred).tolist(),
        ))
    return results


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


def _mean_or_none(values: list[float]) -> float | None:
    return float(np.mean(values)) if values else None


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


def _threshold_table(results: list[ModelResult]) -> str:
    lines = [
        "| Experiment | Model | Threshold | Precision | Recall | Failure Recall | F1 | Confusion [[TN, FP], [FN, TP]] |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for result in results:
        for item in result.threshold_metrics or []:
            lines.append(
                f"| {result.experiment} | {result.model} | {item.threshold:.1f} | "
                f"{_fmt(item.precision)} | {_fmt(item.recall)} | "
                f"{_fmt(item.failure_recall)} | {_fmt(item.f1)} | {item.confusion} |"
            )
    return "\n".join(lines)


def _generalization_summary(results: list[ModelResult]) -> str:
    random_rf = _result_by_name(results, "baseline_random_split", "RandomForestClassifier")
    group_rf = _result_by_name(results, "material_group_split", "RandomForestClassifier")
    lines = [
        "- In-domain performance is represented by `baseline_random_split`.",
        "- Out-of-domain performance is represented by `material_group_split`, "
        "where complete `material_id` groups are held out.",
    ]
    if random_rf and group_rf:
        random_best = _best_failure_recall(random_rf)
        group_best = _best_failure_recall(group_rf)
        lines.extend([
            f"- Random-split RandomForest default failure recall: {_fmt(random_rf.failure_recall)}.",
            f"- Group-split RandomForest default failure recall: {_fmt(group_rf.failure_recall)}.",
            f"- Best random-split threshold failure recall: {_fmt(random_best)}.",
            f"- Best group-split threshold failure recall: {_fmt(group_best)}.",
        ])
        if group_best is not None and group_rf.failure_recall is not None:
            verdict = "improves" if group_best > group_rf.failure_recall else "does not improve"
            lines.append(
                f"- Threshold tuning {verdict} group-split failure recall relative "
                "to the default 0.5 operating point."
            )
    return "\n".join(lines)


def _result_by_name(
    results: list[ModelResult],
    experiment: str,
    model: str,
) -> ModelResult | None:
    for result in results:
        if result.experiment == experiment and result.model == model and result.status == "trained":
            return result
    return None


def _best_failure_recall(result: ModelResult) -> float | None:
    values = [item.failure_recall for item in result.threshold_metrics or []]
    return max(values) if values else None


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
