from __future__ import annotations

import csv
from pathlib import Path


RAW_DIR = Path(__file__).resolve().parent / "outputs" / "raw"


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    path = RAW_DIR / "direct_grid_validations.csv"
    rows = read_csv(path)
    if not rows:
        raise SystemExit(f"No direct validation rows found in {path}")

    for row in rows:
        if row["pass_fail"] != "pass":
            raise SystemExit(f"Non-pass validation row found in public summary: {row}")
        print(
            f"{row['system']}: {row['completed_grid_points']}/{row['grid_points']} "
            f"pass delta={row['delta_eV_per_atom']} {row['energy_units']}"
        )


if __name__ == "__main__":
    main()
