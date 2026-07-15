"""Dataset loader for the TMC benchmark feature dataset.

Provides a clean, typed interface for loading the feature CSV into numpy
arrays ready for ML experiments. Handles:
- Leave-one-out and leave-one-system-out splitting
- NaN imputation for the two features that don't apply to ferrocene (C-O
  bond lengths), using column mean over the non-NaN rows
- Feature subsetting: Coulomb-only, geometric-only, or combined
- Reproducible random splits via explicit random_state

Reads:
  data/features/features_v0.1.csv
  data/features/feature_metadata_v0.1.json

Usage:
    python scripts/11_dataset_loader.py           # prints a dataset summary
    python scripts/11_dataset_loader.py --split   # prints a train/test split
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import NamedTuple

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import PROJECT_ROOT, setup_logger  # noqa: E402

logger = setup_logger("dataset_loader", "dataset_loader.log")

# Feature subsets available via load_dataset(feature_set=...)
COULOMB_PREFIX = "cm_eig_"
GEO_FEATURES = [
    "z_metal", "n_ligands",
    "ml_mean_angstrom", "ml_std_angstrom", "ml_min_angstrom", "ml_max_angstrom",
    "lml_angle_mean_deg", "lml_angle_std_deg",
    "co_mean_angstrom", "co_std_angstrom",
]

# ML target columns
TARGET_COLS = {
    "delta_e_ry": "Ry",
    "delta_e_ev": "eV",
    "delta_e_meV": "meV",
    "final_energy_ry": "Ry",
    "final_energy_ev": "eV",
    "energy_per_atom_ry": "Ry/atom",
}

BOOKKEEPING_COLS = {
    "system_id", "parent_system_id", "source", "label",
    "feature_version", "ionic_steps", "scf_iterations_total",
    "max_force_ry_per_bohr", "n_atoms",
}


class TMCDataset(NamedTuple):
    """Loaded TMC benchmark dataset ready for ML experiments.

    All arrays are float64, NaNs resolved, rows consistently ordered.

    Attributes
    ----------
    X : ndarray (n_samples, n_features)
        Feature matrix, NaN-imputed.
    y : ndarray (n_samples,)
        Target vector.
    system_ids : list[str]
        Row identifiers (one per sample).
    feature_names : list[str]
        Column names corresponding to X.
    target_name : str
        Which target column was used.
    imputed_cols : list[str]
        Feature columns that contained NaN and were imputed with column mean.
    source : list[str]
        "primary" or "candidate" per row.
    label : list[str]
        Validation label per row ("validated" / "usable_with_caution").
    n_samples : int
        Total number of rows.
    n_features : int
        Total number of feature columns.
    """
    X: np.ndarray
    y: np.ndarray
    system_ids: list
    feature_names: list
    target_name: str
    imputed_cols: list
    source: list
    label: list
    n_samples: int
    n_features: int


def load_dataset(
    feature_set: str = "combined",
    target: str = "delta_e_meV",
    candidates_only: bool = False,
    feat_path: Path | None = None,
) -> TMCDataset:
    """Load the feature CSV and return a ready-to-use TMCDataset.

    Parameters
    ----------
    feature_set : "coulomb" | "geometric" | "combined"
        Which descriptor columns to include.
    target : str
        Which target column to use (must be in TARGET_COLS).
    candidates_only : bool
        If True, include only perturbation candidates (12 rows) and exclude
        primary structures. Useful when target=delta_e_* (which is NaN for
        primary structures).
    feat_path : Path, optional
        Override default path to features_v0.1.csv.
    """
    if target not in TARGET_COLS:
        raise ValueError(f"target must be one of {list(TARGET_COLS)}; got '{target}'")
    if feature_set not in ("coulomb", "geometric", "combined"):
        raise ValueError("feature_set must be 'coulomb', 'geometric', or 'combined'")

    csv_path = feat_path or PROJECT_ROOT / "data" / "features" / "features_v0.1.csv"
    if not csv_path.exists():
        raise FileNotFoundError(
            f"Features not found at {csv_path} — run scripts/10_build_features.py first"
        )

    with csv_path.open(encoding="utf-8") as f:
        all_rows = list(csv.DictReader(f))

    if candidates_only:
        rows = [r for r in all_rows if r["source"] == "candidate"]
    else:
        rows = all_rows

    if not rows:
        raise ValueError("No rows matched the filter criteria")

    # Determine feature columns
    sample = rows[0]
    all_cols = list(sample.keys())
    if feature_set == "coulomb":
        feat_cols = [c for c in all_cols if c.startswith(COULOMB_PREFIX)]
    elif feature_set == "geometric":
        feat_cols = [c for c in all_cols if c in GEO_FEATURES]
    else:  # combined
        feat_cols = [c for c in all_cols
                     if c.startswith(COULOMB_PREFIX) or c in GEO_FEATURES]

    if not feat_cols:
        raise ValueError(f"No feature columns found for feature_set='{feature_set}'")

    # Build raw X and y arrays
    def _parse(val: str) -> float:
        if val in ("", "None", "nan"):
            return float("nan")
        return float(val)

    X_raw = np.array([[_parse(r[c]) for c in feat_cols] for r in rows], dtype=np.float64)
    y_raw = np.array([_parse(r[target]) for r in rows], dtype=np.float64)

    # Drop rows where target is NaN (primary structures have no delta_e)
    valid_mask = np.isfinite(y_raw)
    if not np.all(valid_mask):
        n_dropped = (~valid_mask).sum()
        logger.info("Dropping %d rows with NaN target '%s'", n_dropped, target)
        X_raw = X_raw[valid_mask]
        y_raw = y_raw[valid_mask]
        rows = [r for r, v in zip(rows, valid_mask) if v]

    # Impute NaN features with column mean (only co_mean/co_std are NaN for ferrocene)
    imputed_cols = []
    for j, col in enumerate(feat_cols):
        col_vals = X_raw[:, j]
        nan_mask = ~np.isfinite(col_vals)
        if nan_mask.any():
            col_mean = float(np.nanmean(col_vals))
            X_raw[nan_mask, j] = col_mean
            imputed_cols.append(col)
            logger.info("Imputed %d NaN(s) in '%s' with column mean %.4f",
                        nan_mask.sum(), col, col_mean)

    n_samples, n_features = X_raw.shape
    return TMCDataset(
        X=X_raw,
        y=y_raw,
        system_ids=[r["system_id"] for r in rows],
        feature_names=feat_cols,
        target_name=target,
        imputed_cols=imputed_cols,
        source=[r["source"] for r in rows],
        label=[r["label"] for r in rows],
        n_samples=n_samples,
        n_features=n_features,
    )


def train_test_split_by_system(
    dataset: TMCDataset,
    test_systems: list[str],
) -> tuple[TMCDataset, TMCDataset]:
    """Hold out all structures belonging to `test_systems`.

    This is a leave-one-system-out split: train on 3 systems, test on 1.
    With only 16 data points this is the only scientifically defensible
    split (random splits would mix parent and children from the same PES,
    which is data leakage for generalization claims).
    """
    test_set = set(test_systems)
    train_mask = np.array([
        not any(sid.startswith(s) for s in test_set)
        for sid in dataset.system_ids
    ])
    test_mask = ~train_mask

    def _subset(ds: TMCDataset, mask: np.ndarray) -> TMCDataset:
        idx = np.where(mask)[0]
        return TMCDataset(
            X=ds.X[idx],
            y=ds.y[idx],
            system_ids=[ds.system_ids[i] for i in idx],
            feature_names=ds.feature_names,
            target_name=ds.target_name,
            imputed_cols=ds.imputed_cols,
            source=[ds.source[i] for i in idx],
            label=[ds.label[i] for i in idx],
            n_samples=int(mask.sum()),
            n_features=ds.n_features,
        )

    return _subset(dataset, train_mask), _subset(dataset, test_mask)


def subset_dataset(dataset: TMCDataset, indices: np.ndarray | list[int]) -> TMCDataset:
    """Return a row subset while preserving feature metadata.

    This helper keeps split implementations small and avoids ad hoc tuple
    rebuilding in model scripts.
    """
    idx = np.asarray(indices, dtype=int)
    return TMCDataset(
        X=dataset.X[idx],
        y=dataset.y[idx],
        system_ids=[dataset.system_ids[i] for i in idx],
        feature_names=dataset.feature_names,
        target_name=dataset.target_name,
        imputed_cols=dataset.imputed_cols,
        source=[dataset.source[i] for i in idx],
        label=[dataset.label[i] for i in idx],
        n_samples=int(len(idx)),
        n_features=dataset.n_features,
    )


def leave_one_out_splits(dataset: TMCDataset) -> list[tuple[TMCDataset, TMCDataset]]:
    """Build deterministic leave-one-out train/test splits.

    With 16 total structures, random train/test partitions are too small and
    unstable. LOO gives every row exactly one out-of-sample prediction while
    keeping 15 rows for fitting in each fold.
    """
    splits = []
    all_idx = np.arange(dataset.n_samples)
    for test_i in range(dataset.n_samples):
        train_idx = all_idx[all_idx != test_i]
        test_idx = np.array([test_i])
        splits.append((subset_dataset(dataset, train_idx), subset_dataset(dataset, test_idx)))
    return splits


def print_summary(ds: TMCDataset) -> None:
    logger.info("Dataset summary:")
    logger.info("  n_samples=%d, n_features=%d, target=%s",
                ds.n_samples, ds.n_features, ds.target_name)
    logger.info("  sources: %s", dict(zip(*np.unique(ds.source, return_counts=True))))
    logger.info("  labels:  %s", dict(zip(*np.unique(ds.label, return_counts=True))))
    if ds.imputed_cols:
        logger.info("  NaN-imputed cols: %s", ds.imputed_cols)
    if ds.n_samples > 0:
        logger.info("  y stats: min=%.4f, max=%.4f, mean=%.4f, std=%.4f",
                    ds.y.min(), ds.y.max(), ds.y.mean(), ds.y.std())
        logger.info("  X finite: %d/%d cells",
                    int(np.isfinite(ds.X).sum()), ds.X.size)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", action="store_true",
                        help="Show a leave-one-system-out train/test split")
    parser.add_argument("--feature-set", default="combined",
                        choices=["coulomb", "geometric", "combined"])
    parser.add_argument("--target", default="delta_e_meV",
                        choices=list(TARGET_COLS))
    args = parser.parse_args()

    ds = load_dataset(
        feature_set=args.feature_set,
        target=args.target,
        candidates_only=(args.target.startswith("delta_e")),
    )
    print_summary(ds)

    if args.split:
        for held_out in ["ferrocene", "ni_co4", "cr_co6", "fe_co5"]:
            train, test = train_test_split_by_system(ds, [held_out])
            logger.info("Hold-out=%s: train n=%d, test n=%d",
                        held_out, train.n_samples, test.n_samples)
        logger.info("LOO folds: %d", len(leave_one_out_splits(ds)))

    logger.info("")
    logger.info("DATASET SIZE DISCLAIMER: %d samples across 4 systems is insufficient",
                ds.n_samples)
    logger.info("for statistically robust ML. Use for workflow demonstration only.")
    logger.info("No predictive claims until >= 30-50 validated calculations per system.")


if __name__ == "__main__":
    main()
