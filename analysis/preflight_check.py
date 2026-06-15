from __future__ import annotations

import csv
import shutil

from PIL import Image

from publication_data import FIGURE_DIR, RAW_DIR, ROOT


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def f(value):
    try:
        return float(value) if value not in ("", None, "None") else None
    except ValueError:
        return None


def main() -> None:
    failures: list[str] = []
    rows = read_csv(RAW_DIR / "all_results.csv")
    if len(rows) != 50:
        failures.append(f"all_results.csv has {len(rows)} rows, expected 50")
    for col in ["key", "category", "material_name", "dim"]:
        if any(not row.get(col) for row in rows):
            failures.append(f"missing values in required column {col}")
    figure_names = [
        "fig1_pipeline_schematic.png", "fig2_gp_convergence_panel.png", "fig3_parity_plot.png",
        "fig4_dft_savings.png", "fig5_category_errors.png", "fig6_grid_validation.png",
    ]
    for name in figure_names:
        path = FIGURE_DIR / name
        if not path.exists():
            failures.append(f"missing figure {name}")
            continue
        with Image.open(path) as img:
            dpi = img.info.get("dpi", (0, 0))[0]
            if dpi and dpi < 299:
                failures.append(f"{name} dpi={dpi}, expected >=300")
    grid_path = RAW_DIR / "grid_search_comparison.csv"
    if grid_path.exists():
        grid = read_csv(grid_path)
        two_d = [row for row in grid if row["dim"] == "2" and f(row["al_savings_abs"]) is not None]
        if two_d and sum(1 for row in two_d if f(row["al_savings_abs"]) > 0) / len(two_d) < 0.80:
            failures.append("AL uses fewer calls for <80% of 2D systems")
    pbe = [f(row["pct_error_param1"]) for row in rows if f(row["pct_error_param1"]) is not None]
    if pbe and sum(pbe) / len(pbe) > 5:
        failures.append("overall mean absolute error vs PBE literature exceeds 5%")
    if not (ROOT / "CITATION.cff").exists():
        failures.append("CITATION.cff missing")
    if not ((ROOT / "requirements.txt").exists() or (ROOT / "pyproject.toml").exists()):
        failures.append("requirements.txt or pyproject.toml missing")
    if not shutil.which("pdflatex"):
        failures.append("pdflatex not available; LaTeX table compile check not run")
    if failures:
        print("PREFLIGHT FAILED")
        for item in failures:
            print(f"- {item}")
    else:
        print("PREFLIGHT PASSED")


if __name__ == "__main__":
    main()
