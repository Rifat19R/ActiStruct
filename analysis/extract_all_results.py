from __future__ import annotations

import csv

from publication_data import (
    MATERIALS,
    RAW_DIR,
    ROOT,
    choose_report_by_key,
    ensure_dirs,
    parse_best_params,
    parse_converged,
    parse_energy,
    parse_gp_std,
    parse_iterations,
    parse_n_qe,
    params_to_material_values,
    pct_error,
)


FIELDS = [
    "key", "category", "material_name", "dim", "best_param1", "best_param2",
    "best_energy_eV_per_atom", "gp_uncertainty_eV", "n_qe_total",
    "n_iterations", "converged", "lit_pbe_param1", "lit_pbe_param2",
    "exp_param1", "exp_param2", "abs_error_param1", "pct_error_param1",
    "abs_error_param2", "pct_error_param2", "report_file",
]


def report_path_for_csv(path):
    return path.relative_to(ROOT).as_posix()


def main() -> None:
    ensure_dirs()
    reports = choose_report_by_key()
    rows: list[dict] = []
    missing: list[str] = []
    for key, meta in MATERIALS.items():
        path = reports.get(key)
        row = {
            "key": key,
            "category": meta.category,
            "material_name": meta.material_name,
            "dim": meta.dim,
            "lit_pbe_param1": meta.lit_pbe_param1,
            "lit_pbe_param2": meta.lit_pbe_param2,
            "exp_param1": meta.exp_param1,
            "exp_param2": meta.exp_param2,
        }
        if path is None:
            missing.append(key)
            row.update({
                "best_param1": "", "best_param2": "", "best_energy_eV_per_atom": "",
                "gp_uncertainty_eV": "", "n_qe_total": "", "n_iterations": 0,
                "converged": False, "abs_error_param1": "", "pct_error_param1": "",
                "abs_error_param2": "", "pct_error_param2": "", "report_file": "",
            })
            rows.append(row)
            continue

        text = path.read_text(errors="ignore")
        best1, best2 = params_to_material_values(key, parse_best_params(text))
        err1 = abs(best1 - meta.lit_pbe_param1) if best1 is not None and meta.lit_pbe_param1 is not None else None
        err2 = abs(best2 - meta.lit_pbe_param2) if best2 is not None and meta.lit_pbe_param2 is not None else None
        row.update({
            "best_param1": best1,
            "best_param2": best2,
            "best_energy_eV_per_atom": parse_energy(text),
            "gp_uncertainty_eV": parse_gp_std(text),
            "n_qe_total": parse_n_qe(text),
            "n_iterations": parse_iterations(text),
            "converged": parse_converged(text),
            "abs_error_param1": err1,
            "pct_error_param1": pct_error(best1, meta.lit_pbe_param1),
            "abs_error_param2": err2,
            "pct_error_param2": pct_error(best2, meta.lit_pbe_param2),
            "report_file": report_path_for_csv(path),
        })
        rows.append(row)

    out = RAW_DIR / "all_results.csv"
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    parsed = sum(1 for row in rows if row.get("best_param1") not in ("", None))
    total = len(MATERIALS)
    print(f"Reports found for {total - len(missing)}/{total} workflows; parsed best parameter for {parsed}/{total}.")
    if missing:
        print("Missing reports:", ", ".join(missing))
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
