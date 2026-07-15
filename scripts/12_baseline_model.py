"""Baseline surrogate model with uncertainty for the TMC benchmark dataset.

MODEL CHOICE: Gaussian Process Regression (GPR) with an RBF kernel.
GPR is a useful tiny-data baseline because it returns predictive uncertainty
natively and optimises kernel hyperparameters by marginal likelihood.

CRITICAL DISCLAIMER:
16 data points across 4 systems. This is a workflow demonstration. No
predictive claim is made. Minimum ~30-50 points per system needed for
statistically meaningful uncertainty estimates.

The default run fits Coulomb matrix features against total DFT energy with
leave-one-out (LOO) cross-validation. The older 12-candidate delta-E
leave-one-system-out (LOSO) demo remains available via ``--mode loso-delta``.

Reads:
  data/features/features_v0.1.csv  (via scripts/11_dataset_loader.py)

Writes:
  data/models/baseline_gp_v0.1.json   (CV results + model metadata)
  reports/baseline_model_report_v0.1.md

Usage:
    python scripts/12_baseline_model.py              # 16-row LOO GP + report
    python scripts/12_baseline_model.py --mode loso-delta
    python scripts/12_baseline_model.py --dry-run    # verify setup only
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import warnings
from pathlib import Path

import numpy as np
from sklearn.exceptions import ConvergenceWarning
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, ConstantKernel, WhiteKernel
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import PROJECT_ROOT, setup_logger  # noqa: E402

# Import the loader functions directly so this script is self-contained when
# run from the project root.
import importlib.util as _ilu
_loader_path = Path(__file__).resolve().parent / "11_dataset_loader.py"
_spec = _ilu.spec_from_file_location("dataset_loader", _loader_path)
_loader_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_loader_mod)
load_dataset = _loader_mod.load_dataset
train_test_split_by_system = _loader_mod.train_test_split_by_system
leave_one_out_splits = _loader_mod.leave_one_out_splits

logger = setup_logger("baseline_model", "baseline_model.log")
warnings.filterwarnings("ignore", category=ConvergenceWarning)

MODEL_VERSION = "0.1.0"
SYSTEMS = ["ferrocene", "ni_co4", "cr_co6", "fe_co5"]
LOO_TOTAL_ENERGY_DISCLAIMER = (
    "16 data points across 4 systems. This is a workflow demonstration. "
    "No predictive claim is made. Minimum ~30-50 points per system needed "
    "for statistically meaningful uncertainty estimates."
)

# Kernel: constant amplitude × RBF (length scale) + white noise.
# All hyperparameters are optimised per fold via log-marginal-likelihood.
# Bounds prevent degenerate solutions on small datasets.
def make_kernel():
    return (
        ConstantKernel(1.0, constant_value_bounds=(1e-3, 1e3))
        * RBF(length_scale=1.0, length_scale_bounds=(1e-2, 1e3))
        + WhiteKernel(noise_level=1.0, noise_level_bounds=(1e-5, 1e2))
    )


def make_gpr(random_state: int = 42) -> GaussianProcessRegressor:
    return GaussianProcessRegressor(
        kernel=make_kernel(),
        n_restarts_optimizer=5,
        normalize_y=True,
        random_state=random_state,
    )


def evaluate_loso(
    feature_set: str = "combined",
    target: str = "delta_e_meV",
) -> list[dict]:
    """Leave-one-system-out cross-validation.

    For each of the 4 systems: train on the other 3 (9 candidates), predict
    on the held-out 3. Returns per-fold and per-sample results.
    """
    full_ds = load_dataset(
        feature_set=feature_set,
        target=target,
        candidates_only=True,
    )
    logger.info("Full dataset: n=%d, n_features=%d, target=%s",
                full_ds.n_samples, full_ds.n_features, target)

    fold_results = []

    for held_out in SYSTEMS:
        train_ds, test_ds = train_test_split_by_system(full_ds, [held_out])

        if train_ds.n_samples == 0 or test_ds.n_samples == 0:
            logger.warning("Skipping fold %s: empty split", held_out)
            continue

        # Scale features to zero mean, unit variance on training data
        scaler = StandardScaler()
        X_train = scaler.fit_transform(train_ds.X)
        X_test = scaler.transform(test_ds.X)
        y_train = train_ds.y
        y_test = test_ds.y

        gpr = make_gpr()
        gpr.fit(X_train, y_train)

        y_pred, y_std = gpr.predict(X_test, return_std=True)

        mae = float(np.mean(np.abs(y_pred - y_test)))
        rmse = float(np.sqrt(np.mean((y_pred - y_test) ** 2)))
        mean_uncertainty = float(np.mean(y_std))

        logger.info(
            "LOSO fold held_out=%s: train_n=%d, test_n=%d, "
            "MAE=%.3f %s, RMSE=%.3f %s, mean_std=%.3f %s",
            held_out, train_ds.n_samples, test_ds.n_samples,
            mae, target, rmse, target, mean_uncertainty, target,
        )

        per_sample = []
        for i, sid in enumerate(test_ds.system_ids):
            per_sample.append({
                "system_id": sid,
                "y_true": float(y_test[i]),
                "y_pred": float(y_pred[i]),
                "y_std": float(y_std[i]),
                "error": float(y_pred[i] - y_test[i]),
                "abs_error": float(abs(y_pred[i] - y_test[i])),
            })
            logger.info("  %s: true=%.3f, pred=%.3f±%.3f, err=%.3f",
                        sid, y_test[i], y_pred[i], y_std[i],
                        y_pred[i] - y_test[i])

        fold_results.append({
            "held_out_system": held_out,
            "train_n": int(train_ds.n_samples),
            "test_n": int(test_ds.n_samples),
            "mae": mae,
            "rmse": rmse,
            "mean_uncertainty": mean_uncertainty,
            "kernel_str": str(gpr.kernel_),
            "per_sample": per_sample,
        })

    return fold_results


def evaluate_loo_total_energy(
    feature_set: str = "coulomb",
    target: str = "final_energy_ev",
) -> list[dict]:
    """Leave-one-out GP baseline over all 16 structures.

    Uses all primary + perturbation rows, Coulomb matrix features by default,
    and total DFT energy as the target. This is the software baseline requested
    for the Kulik technical section; the numbers are workflow diagnostics, not
    scientific performance claims.
    """
    full_ds = load_dataset(
        feature_set=feature_set,
        target=target,
        candidates_only=False,
    )
    logger.info("LOO dataset: n=%d, n_features=%d, target=%s",
                full_ds.n_samples, full_ds.n_features, target)

    fold_results = []
    for fold_i, (train_ds, test_ds) in enumerate(leave_one_out_splits(full_ds), start=1):
        scaler = StandardScaler()
        X_train = scaler.fit_transform(train_ds.X)
        X_test = scaler.transform(test_ds.X)

        gpr = make_gpr()
        gpr.fit(X_train, train_ds.y)
        y_pred, y_std = gpr.predict(X_test, return_std=True)

        y_true = float(test_ds.y[0])
        pred = float(y_pred[0])
        std = float(y_std[0])
        err = pred - y_true

        fold_results.append({
            "fold": fold_i,
            "held_out_system_id": test_ds.system_ids[0],
            "train_n": int(train_ds.n_samples),
            "test_n": int(test_ds.n_samples),
            "y_true": y_true,
            "y_pred": pred,
            "y_std": std,
            "error": float(err),
            "abs_error": float(abs(err)),
            "kernel_str": str(gpr.kernel_),
        })
        logger.info("LOO %02d/%02d held_out=%s: true=%.6f, pred=%.6f±%.6f, err=%+.6f %s",
                    fold_i, full_ds.n_samples, test_ds.system_ids[0],
                    y_true, pred, std, err, target)

    return fold_results


def rank_candidates_by_acquisition(
    full_ds,
    feature_set: str = "combined",
) -> list[dict]:
    """Train on ALL 12 candidates and compute acquisition scores for ranking.

    Since we don't have new unlabelled candidates in this dataset, this
    demonstrates the acquisition interface using the training data itself
    (in-sample uncertainty). In a real AL loop, X_new would be unlabelled
    candidate structures.

    Uses actistruct's acquisition functions (LCB for minimisation).
    """
    from actistruct.acquisition.reliability import rank_candidates

    scaler = StandardScaler()
    X_all = scaler.fit_transform(full_ds.X)

    gpr = make_gpr()
    gpr.fit(X_all, full_ds.y)
    y_pred, y_std = gpr.predict(X_all, return_std=True)

    candidates = [
        {
            "system_id": full_ds.system_ids[i],
            "predicted_value": float(y_pred[i]),
            "uncertainty": float(y_std[i]),
        }
        for i in range(full_ds.n_samples)
    ]

    ranked = rank_candidates(candidates, objective="minimize", beta=2.0)
    logger.info("Acquisition ranking (LCB, beta=2, minimise delta_e):")
    for rank_i, c in enumerate(ranked):
        logger.info("  #%d  %s  pred=%.3f, std=%.3f, lcb_score=%.3f",
                    rank_i + 1, c["system_id"],
                    c["predicted_value"], c["uncertainty"],
                    c.get("acquisition_score", float("nan")))
    return ranked


def build_report(
    fold_results: list[dict],
    ranked: list[dict],
    target: str,
    out_path: Path,
) -> None:
    lines = [
        "# Baseline Surrogate Model Report — TMC Benchmark v0.1",
        "",
        "*Generated by `scripts/12_baseline_model.py`. Do not edit by hand.*",
        "",
        "> **CRITICAL DISCLAIMER:** This model is trained on 12 DFT calculations "
        "across 4 systems (3 per system). No performance metric reported here is "
        "statistically meaningful. Results are presented solely to demonstrate the "
        "end-to-end workflow (descriptor → model → uncertainty → acquisition). "
        "Do not use these numbers to make scientific claims.",
        "",
        "## Model",
        "",
        "- **Type:** Gaussian Process Regression (scikit-learn)",
        "- **Kernel:** ConstantKernel × RBF + WhiteKernel (hyperparameters "
        "optimised per fold via log-marginal-likelihood)",
        "- **Features:** Sorted Coulomb matrix eigenvalues (21) + local geometric "
        "features (10) = 31 total; StandardScaler applied per fold",
        f"- **Target:** `{target}` (meV relative to parent primary structure)",
        "- **Evaluation:** Leave-one-system-out (LOSO) cross-validation",
        "  (the only defensible split with 3 samples per system — random splits "
        "would mix parent/candidate rows from the same PES, which is data leakage)",
        "",
        "## LOSO Cross-Validation Results",
        "",
        "| Held-out system | Train n | Test n | MAE (meV) | RMSE (meV) | Mean σ (meV) |",
        "|---|---|---|---|---|---|",
    ]
    for f in fold_results:
        lines.append(
            f"| {f['held_out_system']} | {f['train_n']} | {f['test_n']} | "
            f"{f['mae']:.2f} | {f['rmse']:.2f} | {f['mean_uncertainty']:.2f} |"
        )

    overall_mae = np.mean([f["mae"] for f in fold_results]) if fold_results else float("nan")
    overall_rmse = np.mean([f["rmse"] for f in fold_results]) if fold_results else float("nan")
    lines += [
        "",
        f"Mean LOSO MAE: **{overall_mae:.2f} meV** | Mean LOSO RMSE: **{overall_rmse:.2f} meV**",
        "",
        "> With 3 test points per fold, these metrics have very high variance. "
        "They are reported for reproducibility, not interpretation.",
        "",
        "## Per-Sample Predictions",
        "",
        "| Fold | System | y_true (meV) | y_pred (meV) | σ (meV) | error (meV) |",
        "|---|---|---|---|---|---|",
    ]
    for f in fold_results:
        for s in f["per_sample"]:
            lines.append(
                f"| {f['held_out_system']} | {s['system_id']} | "
                f"{s['y_true']:.3f} | {s['y_pred']:.3f} | "
                f"{s['y_std']:.3f} | {s['error']:+.3f} |"
            )

    lines += [
        "",
        "## Acquisition Ranking (in-sample, for interface demonstration)",
        "",
        "Trained on all 12 candidates; uses actistruct `rank_candidates` with "
        "LCB score (β=2, minimisation). In a real AL loop the candidates would "
        "be unlabelled new structures, not training points.",
        "",
        "| Rank | System | Predicted ΔE (meV) | σ (meV) |",
        "|---|---|---|---|",
    ]
    for i, c in enumerate(ranked[:12]):
        lines.append(
            f"| {i+1} | {c['system_id']} | "
            f"{c['predicted_value']:.3f} | {c['uncertainty']:.3f} |"
        )

    lines += [
        "",
        "## What comes next",
        "",
        "Before any AL loop can meaningfully prioritise DFT calculations:",
        "",
        "1. **Expand the dataset** to ≥30–50 validated calculations per system.",
        "2. **Validate descriptor quality** on the expanded set (learning curves, "
        "correlation of uncertainty with actual error).",
        "3. **Run a prospective AL loop**: generate new candidate structures, rank "
        "by acquisition score, run DFT on top-ranked, update the model, repeat.",
        "",
    ]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("Wrote %s", out_path)


def build_loo_total_energy_report(
    fold_results: list[dict],
    feature_set: str,
    target: str,
    out_path: Path,
) -> None:
    """Write the 16-row LOO GP report."""
    mae = float(np.mean([f["abs_error"] for f in fold_results])) if fold_results else math.nan
    rmse = (
        float(np.sqrt(np.mean([f["error"] ** 2 for f in fold_results])))
        if fold_results else math.nan
    )
    mean_unc = float(np.mean([f["y_std"] for f in fold_results])) if fold_results else math.nan

    lines = [
        "# Baseline Surrogate Model Report — TMC Benchmark v0.1",
        "",
        "*Generated by `scripts/12_baseline_model.py`. Do not edit by hand.*",
        "",
        f"> **CRITICAL DISCLAIMER:** {LOO_TOTAL_ENERGY_DISCLAIMER}",
        "",
        "## Model",
        "",
        "- **Type:** Gaussian Process Regression (scikit-learn)",
        "- **Kernel:** ConstantKernel × RBF + WhiteKernel (hyperparameters "
        "optimised per fold via log-marginal-likelihood)",
        f"- **Features:** `{feature_set}`",
        f"- **Target:** `{target}` (total DFT energy)",
        "- **Evaluation:** Leave-one-out cross-validation over all 16 structures",
        "",
        "Total energies across different stoichiometries are dominated by system "
        "identity and atom count. This baseline exists to validate the descriptor, "
        "loader, uncertainty, and reporting path; it is not a chemistry claim.",
        "",
        "## LOO Cross-Validation Results",
        "",
        "| Held-out row | Train n | y_true | y_pred | σ | error |",
        "|---|---|---|---|---|---|",
    ]
    for f in fold_results:
        lines.append(
            f"| {f['held_out_system_id']} | {f['train_n']} | "
            f"{f['y_true']:.6f} | {f['y_pred']:.6f} | "
            f"{f['y_std']:.6f} | {f['error']:+.6f} |"
        )

    lines += [
        "",
        f"Mean LOO MAE: **{mae:.6f}** | RMSE: **{rmse:.6f}** | "
        f"Mean σ: **{mean_unc:.6f}**",
        "",
        "## Interpretation",
        "",
        "The useful result here is the software path: features load correctly, "
        "all 16 rows receive an out-of-sample prediction, and the GP produces "
        "uncertainty estimates. The dataset is too small and chemically mixed "
        "for predictive conclusions.",
        "",
    ]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("Wrote %s", out_path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="Verify setup (load data, fit one fold) without writing outputs")
    parser.add_argument("--mode", default="loo-total",
                        choices=["loo-total", "loso-delta"],
                        help="Baseline workflow to run")
    parser.add_argument("--feature-set", default=None,
                        choices=["coulomb", "geometric", "combined"])
    parser.add_argument("--target", default=None)
    args = parser.parse_args()

    feature_set = args.feature_set or ("coulomb" if args.mode == "loo-total" else "combined")
    target = args.target or ("final_energy_ev" if args.mode == "loo-total" else "delta_e_meV")

    if args.dry_run:
        ds = load_dataset(
            feature_set=feature_set,
            target=target,
            candidates_only=(args.mode == "loso-delta"),
        )
        logger.info("Dry run: loaded dataset n=%d, n_features=%d", ds.n_samples, ds.n_features)
        # Fit one GP fold to verify no errors
        from sklearn.preprocessing import StandardScaler
        X = StandardScaler().fit_transform(ds.X)
        gpr = make_gpr()
        gpr.fit(X[:9], ds.y[:9])
        y_pred, y_std = gpr.predict(X[9:], return_std=True)
        logger.info("Dry run: GP fit OK, sample preds=%s", y_pred.round(2))
        logger.info("Dry run complete — no files written")
        return

    models_dir = PROJECT_ROOT / "data" / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    json_path = models_dir / "baseline_gp_v0.1.json"
    report_path = PROJECT_ROOT / "reports" / "baseline_model_report_v0.1.md"

    if args.mode == "loo-total":
        fold_results = evaluate_loo_total_energy(
            feature_set=feature_set,
            target=target,
        )
        results = {
            "model_version": MODEL_VERSION,
            "mode": args.mode,
            "feature_set": feature_set,
            "target": target,
            "disclaimer": LOO_TOTAL_ENERGY_DISCLAIMER,
            "loo_folds": fold_results,
        }
        json_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
        logger.info("Wrote %s", json_path)
        build_loo_total_energy_report(fold_results, feature_set, target, report_path)
        return

    fold_results = evaluate_loso(
        feature_set=feature_set,
        target=target,
    )

    full_ds = load_dataset(
        feature_set=feature_set,
        target=target,
        candidates_only=True,
    )
    ranked = rank_candidates_by_acquisition(full_ds, feature_set)

    results = {
        "model_version": MODEL_VERSION,
        "mode": args.mode,
        "feature_set": feature_set,
        "target": target,
        "disclaimer": (
            "12 training points — no statistical conclusions should be drawn. "
            "Workflow demonstration only."
        ),
        "loso_folds": fold_results,
        "acquisition_ranking": ranked,
    }
    json_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    logger.info("Wrote %s", json_path)

    build_report(fold_results, ranked, target, report_path)


if __name__ == "__main__":
    main()
