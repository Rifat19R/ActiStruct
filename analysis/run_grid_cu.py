from __future__ import annotations

"""Manual QE grid validation for FCC Cu."""

import csv
from pathlib import Path
import sys

sys.path.insert(0, "<ACTISTRUCT_ROOT>")

import numpy as np

from generated_models.bulk_cu_generated_qe_active_inverse import SYSTEM
from qe_active_inverse_common import _compute_energy, _get_reference_energies, _paths


RAW_DIR = Path("<ACTISTRUCT_ROOT>/analysis/outputs/raw")


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    paths = _paths(SYSTEM)
    refs = _get_reference_energies(SYSTEM, paths)
    rows = []
    for a in np.linspace(3.50, 3.80, 20):
        energy = _compute_energy(SYSTEM, (float(a),), refs, paths)
        rows.append({"a": float(a), "energy_eV_per_atom": energy})
        print(f"a={a:.4f} -> E={energy:.8f} eV")
    out = RAW_DIR / "grid_validation_cu.csv"
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["a", "energy_eV_per_atom"])
        writer.writeheader()
        writer.writerows(rows)
    best = min(rows, key=lambda row: row["energy_eV_per_atom"])
    (RAW_DIR / "grid_validation_cu_report.txt").write_text(f"Best: {best}\nTotal grid calls: {len(rows)}\n", encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
