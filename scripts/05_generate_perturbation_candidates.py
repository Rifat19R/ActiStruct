"""Generate local geometry perturbation candidates around the initial guesses.

Per CLAUDE_ACTISTRUCT_TMC_PLAN.md Sec 7.6: one-at-a-time local perturbations
of each complex's defining geometric variables, 10-20 candidates per complex
(not hundreds). Each candidate varies exactly one variable away from its
phase-1 initial-guess value (see scripts/04_build_initial_structures.py),
holding the others fixed, so individual perturbation effects stay
interpretable for the first active-learning batch.

Usage:
    python scripts/05_generate_perturbation_candidates.py
    python scripts/05_generate_perturbation_candidates.py --dry-run
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from ase.io import write

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import PROJECT_ROOT, setup_logger  # noqa: E402

import importlib.util

_spec = importlib.util.spec_from_file_location(
    "build_initial_structures", Path(__file__).resolve().parent / "04_build_initial_structures.py")
build_initial_structures = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_initial_structures)

logger = setup_logger("generate_perturbation_candidates", "bootstrap.log")

# Each entry: (variable_name, builder_kwarg, nominal_value, [delta steps])
FERROCENE_VARIABLES = [
    ("fe_cp_centroid_distance_angstrom", "fe_cp_dist", 1.66, [-0.05, -0.02, 0.02, 0.05]),
    ("cp_ring_rotation_angle_degree", "ring2_rotation_deg", 0.0, [9.0, 18.0, 27.0, 36.0]),
    ("cp_ring_radius_perturbation_angstrom", "cc_bond", 1.40, [-0.03, -0.015, 0.015, 0.03]),
]

NI_CO4_VARIABLES = [
    ("ni_c_distance_angstrom", "mc_dist", 1.838, [-0.06, -0.03, 0.03, 0.06]),
    ("c_o_distance_angstrom", "co_dist", 1.127, [-0.04, -0.02, 0.02, 0.04]),
    ("tetrahedral_angle_perturbation_degree", "tetra_angle_perturb_deg", 0.0, [-6.0, -3.0, 3.0, 6.0]),
]

CR_CO6_VARIABLES = [
    ("cr_c_distance_angstrom", "mc_dist", 1.918, [-0.06, -0.03, 0.03, 0.06]),
    ("c_o_distance_angstrom", "co_dist", 1.171, [-0.04, -0.02, 0.02, 0.04]),
    ("axial_equatorial_distortion_angstrom", "axial_stretch", 0.0, [-0.05, -0.02, 0.02, 0.05]),
]

FE_CO5_VARIABLES = [
    ("axial_fe_c_distance_angstrom", "axial_fe_c", 1.807, [-0.06, -0.03, 0.03, 0.06]),
    ("equatorial_fe_c_distance_angstrom", "eq_fe_c", 1.827, [-0.06, -0.03, 0.03, 0.06]),
    ("equatorial_angle_perturbation_degree", "eq_angle_perturb_deg", 0.0, [-6.0, -3.0, 3.0, 6.0]),
    ("berry_like_distortion_coordinate_degree", "berry_tilt_deg", 0.0, [-20.0, -10.0, 10.0, 20.0]),
]

COMPLEXES = {
    "ferrocene": (build_initial_structures.build_ferrocene, "Fe(C5H5)2", FERROCENE_VARIABLES),
    "ni_co4": (build_initial_structures.build_ni_co4, "Ni(CO)4", NI_CO4_VARIABLES),
    "cr_co6": (build_initial_structures.build_cr_co6, "Cr(CO)6", CR_CO6_VARIABLES),
    "fe_co5": (build_initial_structures.build_fe_co5, "Fe(CO)5", FE_CO5_VARIABLES),
}


def generate_candidates(complex_id: str, builder, formula: str, variables: list) -> list[dict]:
    candidates = []
    for var_label, kwarg, nominal, deltas in variables:
        for delta in deltas:
            value = nominal + delta
            kwargs = {kwarg: value}
            atoms = builder(**kwargs)
            candidate_id = f"{complex_id}__{kwarg}__{'+' if delta >= 0 else ''}{delta:g}"
            candidates.append({
                "candidate_id": candidate_id,
                "complex_id": complex_id,
                "formula": formula,
                "charge": 0,
                "spin_setting": "closed_shell_phase1",
                "atoms": atoms,
                "generation_method": f"one_at_a_time_perturbation:{var_label}",
                "variables_json": json.dumps({var_label: value, "delta_from_nominal": delta}),
                "notes": "AL exploration candidate, not relaxed - structure quality unknown until QE relax",
            })
    return candidates


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    all_rows = []
    for complex_id, (builder, formula, variables) in COMPLEXES.items():
        candidates = generate_candidates(complex_id, builder, formula, variables)
        logger.info("Generated %d perturbation candidates for %s", len(candidates), complex_id)
        if not (10 <= len(candidates) <= 20):
            logger.warning("%s has %d candidates, outside the 10-20 phase-1 range",
                            complex_id, len(candidates))

        for cand in candidates:
            out_path = PROJECT_ROOT / "structures" / "generated_candidates" / f"{cand['candidate_id']}.xyz"
            row = {
                "candidate_id": cand["candidate_id"],
                "complex_id": cand["complex_id"],
                "formula": cand["formula"],
                "charge": cand["charge"],
                "spin_setting": cand["spin_setting"],
                "structure_path": str(out_path),
                "generation_method": cand["generation_method"],
                "variables_json": cand["variables_json"],
                "notes": cand["notes"],
            }
            all_rows.append(row)

            if args.dry_run:
                logger.info("[dry-run] would write %s", out_path)
                continue
            out_path.parent.mkdir(parents=True, exist_ok=True)
            write(out_path, cand["atoms"], format="xyz",
                  comment=f"{cand['candidate_id']} AL perturbation candidate - not relaxed")
            logger.info("Wrote %s", out_path)

    if args.dry_run:
        logger.info("Dry run: not writing candidate manifest")
        return 0

    manifest_path = PROJECT_ROOT / "data" / "raw" / "candidate_manifest_v0.csv"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(all_rows[0].keys()))
        writer.writeheader()
        writer.writerows(all_rows)
    logger.info("Wrote %s (%d candidates total)", manifest_path, len(all_rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
