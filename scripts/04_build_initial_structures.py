"""Generate initial molecular geometries for the four primary TMC systems.

Geometries are built from symmetry (D5h/Td/Oh/D3h) plus approximate
literature-typical organometallic bond lengths (Fe-Cp ~1.66 A, M-C/C-O in the
1.8-1.95/1.12-1.17 A range). These are INITIAL GUESSES for a subsequent QE
relax, not verified reference values - see references/reference_values_tmc_v0.yaml
for the (separately tracked, source-cited) reference schema.

Usage:
    python scripts/04_build_initial_structures.py
    python scripts/04_build_initial_structures.py --dry-run
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import numpy as np
from ase import Atoms
from ase.io import write

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import PROJECT_ROOT, setup_logger  # noqa: E402

logger = setup_logger("build_initial_structures", "bootstrap.log")


def build_ferrocene() -> Atoms:
    fe_cp_dist = 1.66
    cc_bond = 1.40
    ch_bond = 1.09
    ring_radius = cc_bond / (2 * np.sin(np.pi / 5))

    symbols = ["Fe"]
    positions = [[0.0, 0.0, 0.0]]
    for sign in (+1, -1):
        z = sign * fe_cp_dist
        for k in range(5):
            angle = 2 * np.pi * k / 5
            cx, cy = ring_radius * np.cos(angle), ring_radius * np.sin(angle)
            symbols.append("C")
            positions.append([cx, cy, z])
        for k in range(5):
            angle = 2 * np.pi * k / 5
            hr = ring_radius + ch_bond
            hx, hy = hr * np.cos(angle), hr * np.sin(angle)
            symbols.append("H")
            positions.append([hx, hy, z])
    return Atoms(symbols=symbols, positions=positions)


def build_mco_n(metal: str, mc_dist: float, co_dist: float, directions: np.ndarray) -> Atoms:
    symbols = [metal]
    positions = [[0.0, 0.0, 0.0]]
    for d in directions:
        unit = d / np.linalg.norm(d)
        c_pos = unit * mc_dist
        o_pos = unit * (mc_dist + co_dist)
        symbols.append("C")
        positions.append(c_pos.tolist())
        symbols.append("O")
        positions.append(o_pos.tolist())
    return Atoms(symbols=symbols, positions=positions)


def build_ni_co4() -> Atoms:
    directions = np.array([
        [1, 1, 1], [1, -1, -1], [-1, 1, -1], [-1, -1, 1],
    ], dtype=float)
    return build_mco_n("Ni", mc_dist=1.838, co_dist=1.127, directions=directions)


def build_cr_co6() -> Atoms:
    directions = np.array([
        [1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1],
    ], dtype=float)
    return build_mco_n("Cr", mc_dist=1.918, co_dist=1.171, directions=directions)


def build_fe_co5() -> Atoms:
    axial_fe_c, axial_co = 1.807, 1.143
    eq_fe_c, eq_co = 1.827, 1.153

    symbols = ["Fe"]
    positions = [[0.0, 0.0, 0.0]]
    for sign in (+1, -1):
        c_pos = [0.0, 0.0, sign * axial_fe_c]
        o_pos = [0.0, 0.0, sign * (axial_fe_c + axial_co)]
        symbols += ["C", "O"]
        positions += [c_pos, o_pos]
    for k in range(3):
        angle = 2 * np.pi * k / 3
        ux, uy = np.cos(angle), np.sin(angle)
        c_pos = [ux * eq_fe_c, uy * eq_fe_c, 0.0]
        o_pos = [ux * (eq_fe_c + eq_co), uy * (eq_fe_c + eq_co), 0.0]
        symbols += ["C", "O"]
        positions += [c_pos, o_pos]
    return Atoms(symbols=symbols, positions=positions)


BUILDERS = {
    "ferrocene": (build_ferrocene, "Fe(C5H5)2", "D5h sandwich from Fe-Cp/C-C/C-H literature-typical bond lengths"),
    "ni_co4": (build_ni_co4, "Ni(CO)4", "Td tetrahedral from literature-typical Ni-C/C-O bond lengths"),
    "cr_co6": (build_cr_co6, "Cr(CO)6", "Oh octahedral from literature-typical Cr-C/C-O bond lengths"),
    "fe_co5": (build_fe_co5, "Fe(CO)5", "D3h trigonal bipyramidal from literature-typical axial/equatorial Fe-C/C-O bond lengths"),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    rows = []
    for complex_id, (builder, formula, method) in BUILDERS.items():
        atoms = builder()
        n_atoms = len(atoms)
        logger.info("Built %s: %s, %d atoms", complex_id, formula, n_atoms)
        out_path = PROJECT_ROOT / "structures" / "initial_xyz" / f"{complex_id}_initial.xyz"
        rows.append({
            "complex_id": complex_id,
            "formula": formula,
            "charge": 0,
            "spin_setting": "closed_shell_phase1",
            "n_atoms": n_atoms,
            "structure_path": str(out_path),
            "generation_method": method,
            "notes": "INITIAL GUESS geometry from symmetry + literature-typical bond lengths - not a verified reference value",
        })
        if args.dry_run:
            logger.info("[dry-run] would write %s", out_path)
            continue
        out_path.parent.mkdir(parents=True, exist_ok=True)
        write(out_path, atoms, format="xyz", comment=f"{complex_id} {formula} INITIAL GUESS - not relaxed, not a reference geometry")
        logger.info("Wrote %s", out_path)

    if args.dry_run:
        logger.info("Dry run: not writing summary CSV")
        return 0

    summary_path = PROJECT_ROOT / "reports" / "tables" / "initial_structure_summary.csv"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with summary_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    logger.info("Wrote %s", summary_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
