from __future__ import annotations

"""Manual QE grid validation for layered LiCoO2.

This grid must match the active-learning wrapper variables:
    a in [2.70, 3.00] Angstrom
    c_over_a in [4.60, 5.10]

The CSV also stores c = a * c_over_a for readability.
"""

import csv
from pathlib import Path
import sys

sys.path.insert(0, "<ACTISTRUCT_ROOT>")

import numpy as np

from generated_models.bulk_licoo2_generated_qe_active_inverse import SYSTEM
from qe_active_inverse_common import _compute_energy, _get_reference_energies, _paths


RAW_DIR = Path("<ACTISTRUCT_ROOT>/analysis/outputs/raw")


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    paths = _paths(SYSTEM)
    refs = _get_reference_energies(SYSTEM, paths)
    rows = []
    a_min, a_max = SYSTEM.variables[0].lo, SYSTEM.variables[0].hi
    ratio_min, ratio_max = SYSTEM.variables[1].lo, SYSTEM.variables[1].hi
    for a in np.linspace(a_min, a_max, 7):
        for c_over_a in np.linspace(ratio_min, ratio_max, 7):
            c = float(a * c_over_a)
            energy = _compute_energy(SYSTEM, (float(a), c_over_a), refs, paths)
            rows.append({"a": float(a), "c": float(c), "c_over_a": c_over_a, "energy_eV_per_atom": energy})
            print(f"a={a:.4f}, c_over_a={c_over_a:.4f}, c={c:.4f} -> E={energy:.8f} eV")
    out = RAW_DIR / "grid_validation_licoo2.csv"
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["a", "c", "c_over_a", "energy_eV_per_atom"])
        writer.writeheader()
        writer.writerows(rows)
    best = min(rows, key=lambda row: row["energy_eV_per_atom"])
    (RAW_DIR / "grid_validation_licoo2_report.txt").write_text(f"Best: {best}\nTotal grid calls: {len(rows)}\n", encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
