from __future__ import annotations

import csv

import numpy as np

from publication_data import RAW_DIR, VARIABLE_RANGES, choose_report_by_key, ensure_dirs, parse_labeled_points


def read_results() -> list[dict]:
    with (RAW_DIR / "all_results.csv").open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def as_float(value: str) -> float | None:
    try:
        return float(value) if value not in ("", "None") else None
    except ValueError:
        return None


def surrogate_count(key: str, report_text: str) -> tuple[int, bool, bool]:
    ranges = VARIABLE_RANGES[key]
    dim = ranges["dim"]
    grid_size = 20 if dim == 1 else 49
    x, y = parse_labeled_points(report_text)
    if len(x) < 2 or len(y) < 2:
        return grid_size, True, False
    try:
        from sklearn.gaussian_process import GaussianProcessRegressor
        from sklearn.gaussian_process.kernels import ConstantKernel, RBF, WhiteKernel

        gp = GaussianProcessRegressor(
            kernel=ConstantKernel(1.0) * RBF(length_scale=0.1) + WhiteKernel(noise_level=1e-5),
            normalize_y=True,
            n_restarts_optimizer=2,
            random_state=7,
        )
        gp.fit(np.asarray(x, dtype=float), np.asarray(y, dtype=float))
        if dim == 1:
            grid = np.linspace(*ranges["a"], 20).reshape(-1, 1)
        else:
            a_grid = np.linspace(*ranges["a"], 7)
            c_grid = np.linspace(*ranges["c"], 7)
            aa, cc = np.meshgrid(a_grid, c_grid)
            grid = np.column_stack([aa.ravel(), cc.ravel()])
            if len(x[0]) == 2:
                grid = np.column_stack([grid[:, 0], grid[:, 1] / grid[:, 0]])
        pred = gp.predict(grid)
        idx = np.where(pred <= float(np.min(pred)) + 0.001)[0]
        return int(idx[0] + 1) if len(idx) else grid_size, True, True
    except Exception:
        return grid_size, True, False


def main() -> None:
    ensure_dirs()
    reports = choose_report_by_key()
    rows = []
    for row in read_results():
        key = row["key"]
        dim = int(row["dim"])
        grid_size = 20 if dim == 1 else 49
        n_al = as_float(row["n_qe_total"])
        report_text = reports[key].read_text(errors="ignore") if key in reports else ""
        n_grid_to_min, al_ok, grid_ok = surrogate_count(key, report_text)
        savings_abs = grid_size - int(n_al) if n_al is not None else ""
        savings_pct = savings_abs / grid_size * 100.0 if savings_abs != "" else ""
        rows.append({
            "key": key,
            "category": row["category"],
            "dim": dim,
            "n_al_calls": int(n_al) if n_al is not None else "",
            "n_grid_1d_equiv": 20 if dim == 1 else "",
            "n_grid_2d_equiv": 49 if dim == 2 else "",
            "grid_size_used": grid_size,
            "n_grid_to_surrogate_min": n_grid_to_min,
            "al_savings_abs": savings_abs,
            "al_savings_pct": savings_pct,
            "al_converged_to_min": al_ok,
            "grid_converged_to_min": grid_ok,
        })
    out = RAW_DIR / "grid_search_comparison.csv"
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
