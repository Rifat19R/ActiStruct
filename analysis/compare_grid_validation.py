from __future__ import annotations

import csv

from publication_data import RAW_DIR


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    all_results = {row["key"]: row for row in read_csv(RAW_DIR / "all_results.csv")}
    rows = []
    for key, short in {"bulk_cu": "cu", "bulk_licoo2": "licoo2", "mos2": "mos2"}.items():
        path = RAW_DIR / f"grid_validation_{short}.csv"
        if not path.exists() or key not in all_results:
            rows.append({"key": key, "status": "missing grid validation", "energy_diff_eV": "", "grid_calls": "", "al_calls": ""})
            continue
        grid = read_csv(path)
        grid_min = min(float(row["energy_eV_per_atom"]) for row in grid)
        al_energy = float(all_results[key]["best_energy_eV_per_atom"])
        diff = abs(grid_min - al_energy)
        rows.append({"key": key, "status": "PASS" if diff <= 0.001 else "FAIL", "energy_diff_eV": diff, "grid_calls": len(grid), "al_calls": all_results[key]["n_qe_total"]})
    out = RAW_DIR / "grid_validation_comparison.csv"
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["key", "status", "energy_diff_eV", "grid_calls", "al_calls"])
        writer.writeheader()
        writer.writerows(rows)
    for row in rows:
        print(row)


if __name__ == "__main__":
    main()
