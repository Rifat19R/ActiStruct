from __future__ import annotations

"""Manual QE grid validation for monolayer MoS2.

This grid must match the active-learning wrapper variables:
    a in [3.05, 3.30] Angstrom
    layer_half_thickness in [1.45, 1.70] Angstrom
"""

import csv
from pathlib import Path
import sys

sys.path.insert(0, "/mnt/d/Rifat_kh/inverse_active")

import numpy as np

from generated_models.mos2_qe_active_inverse import SYSTEM
from qe_active_inverse_common import _compute_energy, _get_reference_energies, _paths


RAW_DIR = Path("/mnt/d/Rifat_kh/inverse_active/analysis/outputs/raw")


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    paths = _paths(SYSTEM)
    refs = _get_reference_energies(SYSTEM, paths)
    rows = []
    a_min, a_max = SYSTEM.variables[0].lo, SYSTEM.variables[0].hi
    t_min, t_max = SYSTEM.variables[1].lo, SYSTEM.variables[1].hi
    for a in np.linspace(a_min, a_max, 7):
        for thickness in np.linspace(t_min, t_max, 7):
            energy = _compute_energy(SYSTEM, (float(a), float(thickness)), refs, paths)
            rows.append({"a": float(a), "layer_half_thickness": float(thickness), "energy_eV_per_atom": energy})
            print(f"a={a:.4f}, t={thickness:.4f} -> E={energy:.8f} eV")
    out = RAW_DIR / "grid_validation_mos2.csv"
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["a", "layer_half_thickness", "energy_eV_per_atom"])
        writer.writeheader()
        writer.writerows(rows)
    best = min(rows, key=lambda row: row["energy_eV_per_atom"])
    (RAW_DIR / "grid_validation_mos2_report.txt").write_text(f"Best: {best}\nTotal grid calls: {len(rows)}\n", encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
