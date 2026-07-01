"""Active-learning demonstration on the TMC benchmark dataset.

This script demonstrates three AL capabilities using the 12-candidate
perturbation dataset as a retrospective oracle:

1. SIMULATED AL LOOP — Starting from zero labelled candidates, an
   uncertainty-driven loop (LCB acquisition via actistruct) decides which
   of the 12 perturbation candidates to "query" (simulate a DFT run) next.
   A fixed 4-candidate holdout (1 per system) is used to measure the
   learning curve.  Compared against random selection (n=50 random trials).

2. UNCERTAINTY vs CONVERGENCE COST — After training the GP on all 12
   candidates, model uncertainty is compared to the number of SCF
   iterations each candidate required.  High SCF-iteration jobs are
   potential "expensive" or hard-to-converge calculations.  If uncertainty
   correlates with SCF cost, the model can flag them before running DFT.

3. RETROSPECTIVE EFFICIENCY — Given the AL selection order, how many of
   the "trivial" stretch perturbations (which all return to the same basin)
   would have been selected last?  This quantifies how many DFT runs AL
   can save by de-prioritising uninformative regions.

DISCLAIMER: All results use retrospective knowledge — true ΔE values are
already known for all 12 candidates.  This is a workflow demonstration,
not a predictive result.  With only 12 labelled structures the GP prior
dominates; AL is expected to give only marginal benefit over random
selection.  Genuine AL benefit requires ≥ 30–50 validated calculations
per system before the surrogate gains meaningful predictive power.

Reads:
  data/features/features_v0.1.csv       (via scripts/11_dataset_loader.py)

Writes:
  data/models/al_demo_v0.1.json
  reports/active_learning_demo_v0.1.md

Usage:
    python scripts/14_active_learning_demo.py
    python scripts/14_active_learning_demo.py --dry-run
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

import numpy as np
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, ConstantKernel, WhiteKernel
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import PROJECT_ROOT, setup_logger  # noqa: E402

import importlib.util as _ilu
_loader_path = Path(__file__).resolve().parent / "11_dataset_loader.py"
_spec = _ilu.spec_from_file_location("dataset_loader", _loader_path)
_loader_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_loader_mod)
load_dataset = _loader_mod.load_dataset

logger = setup_logger("al_demo", "al_demo.log")

AL_DEMO_VERSION = "0.1.0"

# Fixed holdout: 1 candidate per system, chosen to be representative of
# the "stretch" family (least informative, so the AL loop has the most
# freedom to choose among angle/rotation perturbations first).
FIXED_HOLDOUT_IDS = [
    "ferrocene__fe_cp_dist__-0.05",
    "ni_co4__co_dist__-0.04",
    "cr_co6__axial_stretch__-0.05",
    "fe_co5__eq_fe_c__+0.06",
]


def _make_gpr(random_state: int = 42) -> GaussianProcessRegressor:
    kernel = (
        ConstantKernel(1.0, constant_value_bounds=(1e-3, 1e3))
        * RBF(length_scale=1.0, length_scale_bounds=(1e-2, 1e3))
        + WhiteKernel(noise_level=1.0, noise_level_bounds=(1e-5, 1e2))
    )
    return GaussianProcessRegressor(
        kernel=kernel,
        n_restarts_optimizer=5,
        normalize_y=True,
        random_state=random_state,
    )


def _gp_predict_pool(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_pool: np.ndarray,
    random_state: int = 42,
) -> tuple[np.ndarray, np.ndarray]:
    """Fit GP on training data and predict mean/std for the pool.

    When training set is empty, returns zero mean and unit prior uncertainty.
    """
    if len(X_train) == 0:
        n = len(X_pool)
        return np.zeros(n), np.ones(n)
    scaler = StandardScaler()
    X_tr = scaler.fit_transform(X_train)
    X_po = scaler.transform(X_pool)
    gpr = _make_gpr(random_state=random_state)
    gpr.fit(X_tr, y_train)
    return gpr.predict(X_po, return_std=True)


def _lcb_score(pred: np.ndarray, std: np.ndarray, beta: float = 2.0) -> np.ndarray:
    """Lower-confidence-bound acquisition (minimisation).  Lower = higher priority."""
    return pred - beta * std


def simulate_al_loop(
    feature_set: str = "combined",
    target: str = "delta_e_meV",
    rng_seed: int = 0,
    beta: float = 2.0,
) -> list[dict]:
    """Simulate a full 12-step AL loop using LCB acquisition.

    The 4 FIXED_HOLDOUT_IDS are withheld from the pool for evaluation only.
    The remaining 8 candidates are available to the AL loop.
    At each step the pool candidate with the lowest LCB score (most
    informative / lowest predicted ΔE) is selected, its true label is
    revealed, and it is added to the training set.

    Returns a list of 8 step dicts (one per AL query).
    """
    from actistruct.acquisition.reliability import rank_candidates

    ds = load_dataset(
        feature_set=feature_set,
        target=target,
        candidates_only=True,
    )

    rng = np.random.default_rng(rng_seed)

    holdout_mask = np.array([sid in FIXED_HOLDOUT_IDS for sid in ds.system_ids])
    pool_mask = ~holdout_mask

    X_holdout = ds.X[holdout_mask]
    y_holdout = ds.y[holdout_mask]

    pool_indices = list(np.where(pool_mask)[0])
    train_indices: list[int] = []

    steps = []

    for step in range(len(pool_indices)):
        X_train = ds.X[train_indices] if train_indices else np.empty((0, ds.n_features))
        y_train = ds.y[train_indices] if train_indices else np.empty(0)
        X_pool_arr = ds.X[pool_indices]

        y_pred, y_std = _gp_predict_pool(
            X_train, y_train, X_pool_arr, random_state=int(rng.integers(1000))
        )

        candidates_for_acq = [
            {
                "system_id": ds.system_ids[pool_indices[i]],
                "predicted_value": float(y_pred[i]),
                "uncertainty": float(y_std[i]),
            }
            for i in range(len(pool_indices))
        ]
        ranked = rank_candidates(candidates_for_acq, objective="minimize", beta=beta)
        selected_id = ranked[0]["system_id"]

        # Find the index of the selected candidate in pool_indices
        sel_pos = next(
            i for i, idx in enumerate(pool_indices)
            if ds.system_ids[idx] == selected_id
        )
        sel_global_idx = pool_indices[sel_pos]

        pool_indices.pop(sel_pos)
        train_indices.append(sel_global_idx)

        # MAE on fixed holdout (requires at least 1 training point)
        if len(train_indices) >= 1:
            X_tr_now = ds.X[train_indices]
            y_tr_now = ds.y[train_indices]
            y_ho_pred, y_ho_std = _gp_predict_pool(
                X_tr_now, y_tr_now, X_holdout,
                random_state=42,
            )
            holdout_mae = float(np.mean(np.abs(y_ho_pred - y_holdout)))
            holdout_mean_std = float(np.mean(y_ho_std))
        else:
            holdout_mae = float("nan")
            holdout_mean_std = float("nan")

        pool_mean_uncertainty = float(np.mean(y_std))

        steps.append({
            "step": step + 1,
            "selected_id": selected_id,
            "y_true": float(ds.y[sel_global_idx]),
            "predicted_value": float(ranked[0]["predicted_value"]),
            "uncertainty_at_selection": float(ranked[0]["uncertainty"]),
            "pool_mean_uncertainty": pool_mean_uncertainty,
            "holdout_mae": holdout_mae,
            "holdout_mean_std": holdout_mean_std,
            "train_n": len(train_indices),
        })

        logger.info(
            "Step %02d: selected=%s  y_true=%.3f  holdout_MAE=%.3f  pool_σ=%.3f",
            step + 1, selected_id,
            float(ds.y[sel_global_idx]),
            holdout_mae, pool_mean_uncertainty,
        )

    return steps


def compare_al_vs_random(
    feature_set: str = "combined",
    target: str = "delta_e_meV",
    n_random_trials: int = 50,
    rng_seed: int = 0,
    beta: float = 2.0,
) -> dict:
    """Compare AL learning curve against random selection (n_random_trials trials).

    Returns dict with:
      al_steps: list of step dicts from simulate_al_loop
      random_mean_mae: mean holdout MAE per step across random trials
      random_std_mae: std of holdout MAE per step across random trials
    """
    al_steps = simulate_al_loop(
        feature_set=feature_set, target=target, rng_seed=rng_seed, beta=beta
    )

    ds = load_dataset(
        feature_set=feature_set,
        target=target,
        candidates_only=True,
    )
    holdout_mask = np.array([sid in FIXED_HOLDOUT_IDS for sid in ds.system_ids])
    pool_mask = ~holdout_mask
    pool_indices_full = list(np.where(pool_mask)[0])
    X_holdout = ds.X[holdout_mask]
    y_holdout = ds.y[holdout_mask]

    rng = np.random.default_rng(rng_seed + 1)
    n_steps = len(pool_indices_full)
    random_maes = np.zeros((n_random_trials, n_steps))

    for trial in range(n_random_trials):
        perm = rng.permutation(pool_indices_full).tolist()
        train_idx: list[int] = []
        for s in range(n_steps):
            train_idx.append(perm[s])
            X_tr = ds.X[train_idx]
            y_tr = ds.y[train_idx]
            y_pred, _ = _gp_predict_pool(X_tr, y_tr, X_holdout, random_state=42)
            random_maes[trial, s] = float(np.mean(np.abs(y_pred - y_holdout)))

    return {
        "al_steps": al_steps,
        "al_holdout_mae": [s["holdout_mae"] for s in al_steps],
        "random_mean_mae": random_maes.mean(axis=0).tolist(),
        "random_std_mae": random_maes.std(axis=0).tolist(),
        "n_random_trials": n_random_trials,
        "holdout_ids": FIXED_HOLDOUT_IDS,
    }


def analyze_convergence_correlation(
    feature_set: str = "combined",
    target: str = "delta_e_meV",
) -> dict:
    """Check whether model uncertainty correlates with SCF convergence cost.

    Fits the GP on all 12 candidates (target=delta_e_meV), then computes
    Pearson and Spearman correlations between the per-candidate GP uncertainty
    and the number of SCF iterations the candidate actually required.

    A positive correlation would mean: high-uncertainty structures → harder
    convergence → higher potential "failure" risk if launched without screening.
    """
    from scipy import stats as scipy_stats

    ds = load_dataset(
        feature_set=feature_set,
        target=target,
        candidates_only=True,
    )

    scaler = StandardScaler()
    X_all = scaler.fit_transform(ds.X)
    gpr = _make_gpr(random_state=42)
    gpr.fit(X_all, ds.y)
    _, y_std = gpr.predict(X_all, return_std=True)

    # Pull scf_iterations_total from the features CSV (bookkeeping column)
    feat_path = PROJECT_ROOT / "data" / "features" / "features_v0.1.csv"
    scf_by_id: dict[str, int] = {}
    with feat_path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("source") == "candidate":
                try:
                    scf_by_id[row["system_id"]] = int(float(row["scf_iterations_total"]))
                except (ValueError, KeyError):
                    pass

    scf_iters = np.array([scf_by_id.get(sid, 0) for sid in ds.system_ids], dtype=float)

    pearson_r, pearson_p = scipy_stats.pearsonr(y_std, scf_iters)
    spearman_r, spearman_p = scipy_stats.spearmanr(y_std, scf_iters)

    per_candidate = []
    for i, sid in enumerate(ds.system_ids):
        per_candidate.append({
            "system_id": sid,
            "uncertainty": float(y_std[i]),
            "scf_iterations": int(scf_iters[i]),
            "delta_e_meV": float(ds.y[i]),
        })

    logger.info(
        "Uncertainty vs SCF-iters: Pearson r=%.3f (p=%.3f), Spearman r=%.3f (p=%.3f)",
        pearson_r, pearson_p, spearman_r, spearman_p,
    )

    return {
        "pearson_r": float(pearson_r),
        "pearson_p": float(pearson_p),
        "spearman_r": float(spearman_r),
        "spearman_p": float(spearman_p),
        "per_candidate": per_candidate,
    }


def analyze_stretch_efficiency(al_steps: list[dict]) -> dict:
    """Retrospective: at what rank did AL select stretch vs angle/rotation perturbations?

    Stretch families: all perturbations NOT containing 'angle', 'rotation', 'distortion'.
    Angle/rotation families: those containing 'angle', 'rotation', 'tetra', 'ring'.
    """
    stretch_keywords = {"dist", "stretch", "bond"}
    angle_keywords = {"angle", "rotation", "tetra", "ring"}

    def classify(sid: str) -> str:
        lower = sid.lower()
        if any(kw in lower for kw in angle_keywords):
            return "angle_rotation"
        return "stretch"

    stretch_ranks = []
    angle_ranks = []
    for s in al_steps:
        kind = classify(s["selected_id"])
        if kind == "angle_rotation":
            angle_ranks.append(s["step"])
        else:
            stretch_ranks.append(s["step"])

    n_total = len(al_steps)
    return {
        "n_stretch": len(stretch_ranks),
        "n_angle_rotation": len(angle_ranks),
        "stretch_ranks": stretch_ranks,
        "angle_rotation_ranks": angle_ranks,
        "stretch_mean_rank": float(np.mean(stretch_ranks)) if stretch_ranks else float("nan"),
        "angle_mean_rank": float(np.mean(angle_ranks)) if angle_ranks else float("nan"),
        "n_total": n_total,
    }


def build_report(
    comparison: dict,
    convergence: dict,
    efficiency: dict,
    out_path: Path,
) -> None:
    al_steps = comparison["al_steps"]
    al_mae = comparison["al_holdout_mae"]
    rand_mean = comparison["random_mean_mae"]
    rand_std = comparison["random_std_mae"]

    lines = [
        "# Active-Learning Demonstration Report — TMC Benchmark v0.1",
        "",
        "*Generated by `scripts/14_active_learning_demo.py`. Do not edit by hand.*",
        "",
        "> **CRITICAL DISCLAIMER:** All results in this report use retrospective",
        "> knowledge — the true ΔE values for all 12 candidates are already known.",
        "> This is a workflow demonstration, not a predictive result.",
        "> With only 12 labelled structures the GP prior dominates any learned",
        "> function; AL is expected to give only marginal benefit over random",
        "> selection.  Genuine AL benefit requires ≥ 30–50 validated calculations",
        "> per system.",
        "",
        "---",
        "",
        "## 1. Simulated AL Loop",
        "",
        f"**Holdout set** (fixed, 4 candidates, 1 per system, for evaluation):**",
        "",
    ]
    for hid in comparison["holdout_ids"]:
        lines.append(f"- `{hid}`")

    lines += [
        "",
        "**AL pool** (8 candidates, queried one at a time by LCB acquisition, β=2).",
        "",
        "### 1.1 Step-by-step AL selection order",
        "",
        "| Step | Selected candidate | ΔE_true (meV) | Predicted ΔE (meV) | σ | Holdout MAE (meV) |",
        "|---|---|---|---|---|---|",
    ]
    for s in al_steps:
        lines.append(
            f"| {s['step']} | `{s['selected_id']}` | {s['y_true']:.3f} | "
            f"{s['predicted_value']:.3f} | {s['uncertainty_at_selection']:.3f} | "
            f"{s['holdout_mae']:.3f} |"
        )

    lines += [
        "",
        "### 1.2 AL vs random: learning curves",
        "",
        f"Random baseline: mean ± std over {comparison['n_random_trials']} random orderings.",
        "",
        "| Training size | AL MAE (meV) | Random mean MAE (meV) | Random std MAE (meV) |",
        "|---|---|---|---|",
    ]
    for i, s in enumerate(al_steps):
        lines.append(
            f"| {s['train_n']} | {al_mae[i]:.3f} | "
            f"{rand_mean[i]:.3f} | {rand_std[i]:.3f} |"
        )

    lines += [
        "",
        "> **Expected:** With only 8 pool candidates and a GP prior that",
        "> dominates the learned function, AL offers only marginal benefit over",
        "> random selection.  This is the correct result — not a failure.",
        "> The machinery is in place; it requires more data to show genuine benefit.",
        "",
        "---",
        "",
        "## 2. Uncertainty vs Convergence Cost",
        "",
        "GP trained on all 12 candidates (target = ΔE in meV).  Per-candidate",
        "uncertainty compared to actual SCF iteration count.",
        "",
        f"| Correlation | r | p-value | Interpretation |",
        f"|---|---|---|---|",
        f"| Pearson | {convergence['pearson_r']:.3f} | {convergence['pearson_p']:.3f} | "
        f"{'weak' if abs(convergence['pearson_r']) < 0.3 else 'moderate' if abs(convergence['pearson_r']) < 0.6 else 'strong'} |",
        f"| Spearman | {convergence['spearman_r']:.3f} | {convergence['spearman_p']:.3f} | "
        f"{'weak' if abs(convergence['spearman_r']) < 0.3 else 'moderate' if abs(convergence['spearman_r']) < 0.6 else 'strong'} |",
        "",
        "| Candidate | ΔE (meV) | GP σ (meV) | SCF iterations |",
        "|---|---|---|---|",
    ]
    for c in sorted(convergence["per_candidate"], key=lambda x: x["scf_iterations"], reverse=True):
        lines.append(
            f"| `{c['system_id']}` | {c['delta_e_meV']:.3f} | "
            f"{c['uncertainty']:.3f} | {c['scf_iterations']} |"
        )

    lines += [
        "",
        "> **Interpretation:** A statistically significant positive correlation would",
        "> mean the model can flag expensive-to-converge structures before launching",
        "> DFT.  With 12 points, any correlation is unreliable.  The table above",
        "> is included to establish the measurement protocol for the larger dataset.",
        "",
        "---",
        "",
        "## 3. Retrospective Efficiency: Stretch vs Angle/Rotation Selection Order",
        "",
        "**Scientific hypothesis:** AL (exploration) should de-prioritise stretch",
        "perturbations (which always return to the same basin) in favour of",
        "angle/rotation perturbations (which may find new conformers or require",
        "more SCF iterations).",
        "",
        f"- Stretch perturbations selected at ranks: {efficiency['stretch_ranks']}  "
        f"(mean rank: {efficiency['stretch_mean_rank']:.1f})",
        f"- Angle/rotation perturbations selected at ranks: {efficiency['angle_rotation_ranks']}  "
        f"(mean rank: {efficiency['angle_mean_rank']:.1f})",
        "",
    ]

    stretch_later = (
        efficiency["n_angle_rotation"] > 0
        and efficiency["n_stretch"] > 0
        and efficiency["stretch_mean_rank"] > efficiency["angle_mean_rank"]
    )
    stretch_earlier = (
        efficiency["n_angle_rotation"] > 0
        and efficiency["n_stretch"] > 0
        and efficiency["stretch_mean_rank"] < efficiency["angle_mean_rank"]
    )

    if stretch_later:
        lines.append(
            "> AL selected angle/rotation perturbations earlier on average — "
            "consistent with the hypothesis that the model assigns higher "
            "informativeness to non-stretch directions.  However, with 12 points "
            "this is not statistically significant."
        )
    elif stretch_earlier:
        lines.append(
            "> AL selected stretch perturbations earlier on average.  This is "
            "consistent with the GP prior dominating: with insufficient training "
            "data the model cannot distinguish stretch from angle/rotation directions, "
            "and LCB ordering is close to random.  Expected behaviour at this dataset size."
        )
    else:
        lines.append(
            "> Equal mean ranks — the GP prior dominates at this dataset size."
        )

    lines += [
        "",
        "---",
        "",
        "## 4. What comes next",
        "",
        "1. **Expand the dataset** to ≥ 30–50 validated DFT calculations per system.",
        "   Only then will the GP have enough data to show genuine AL benefit.",
        "2. **Prospective AL loop** — generate new candidate structures, rank by",
        "   acquisition score, run DFT on top-ranked, update model, repeat.",
        "3. **Failure prediction** — with a larger dataset, train a separate",
        "   classifier on SCF-iterations as the target to flag hard-to-converge",
        "   structures before launching expensive DFT jobs.",
        "4. **Dispersion correction (PBE-D3)** — add for ferrocene before any",
        "   publication-quality results; weak Cp–Fe bonding is poorly described by PBE.",
        "",
    ]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("Wrote %s", out_path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="Run setup checks without writing output files")
    parser.add_argument("--feature-set", default="combined",
                        choices=["coulomb", "geometric", "combined"])
    parser.add_argument("--n-random-trials", type=int, default=50)
    parser.add_argument("--beta", type=float, default=2.0,
                        help="LCB exploration parameter")
    args = parser.parse_args()

    if args.dry_run:
        ds = load_dataset(target="delta_e_meV", candidates_only=True)
        logger.info("Dry run: dataset loaded n=%d, n_features=%d", ds.n_samples, ds.n_features)
        holdout_mask = np.array([sid in FIXED_HOLDOUT_IDS for sid in ds.system_ids])
        logger.info("Dry run: holdout n=%d, pool n=%d",
                    holdout_mask.sum(), (~holdout_mask).sum())
        logger.info("Dry run complete — no files written")
        return

    logger.info("=== Phase 5: Active Learning Demonstration ===")

    logger.info("--- Analysis 1: Simulated AL loop vs random ---")
    comparison = compare_al_vs_random(
        feature_set=args.feature_set,
        n_random_trials=args.n_random_trials,
        beta=args.beta,
    )

    logger.info("--- Analysis 2: Uncertainty vs convergence cost ---")
    convergence = analyze_convergence_correlation(feature_set=args.feature_set)

    logger.info("--- Analysis 3: Stretch vs angle/rotation efficiency ---")
    efficiency = analyze_stretch_efficiency(comparison["al_steps"])

    # Save JSON
    models_dir = PROJECT_ROOT / "data" / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    results = {
        "al_demo_version": AL_DEMO_VERSION,
        "feature_set": args.feature_set,
        "disclaimer": (
            "Retrospective demonstration with 12 training points. "
            "No predictive or statistical conclusions should be drawn. "
            "AL benefit requires >= 30-50 validated calculations per system."
        ),
        "comparison": comparison,
        "convergence_correlation": convergence,
        "efficiency": efficiency,
    }
    json_path = models_dir / "al_demo_v0.1.json"
    json_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    logger.info("Wrote %s", json_path)

    report_path = PROJECT_ROOT / "reports" / "active_learning_demo_v0.1.md"
    build_report(comparison, convergence, efficiency, report_path)

    logger.info("=== Phase 5 complete ===")


if __name__ == "__main__":
    main()
