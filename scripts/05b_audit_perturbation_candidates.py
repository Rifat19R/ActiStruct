"""Audit the 52 perturbation candidates from script 05 before spending QE time on them.

Per Rifat's Phase 2B.0 quality gate: classify every candidate (perturbation
family, magnitude, expected physical effect), reject anything chemically
unreasonable (overlaps, unrealistic bonds, duplicates), then select a small,
family-diverse representative subset (~3 per system) for the next QE
campaign - rather than running all 52 blindly.

Usage:
    python scripts/05b_audit_perturbation_candidates.py
    python scripts/05b_audit_perturbation_candidates.py --dry-run
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import PROJECT_ROOT, setup_logger  # noqa: E402

logger = setup_logger("audit_perturbation_candidates", "bootstrap.log")

AUDITOR_VERSION = "0.1.0"
OVERLAP_THRESHOLD_ANGSTROM = 0.5
DUPLICATE_RMSD_THRESHOLD_ANGSTROM = 0.01

_spec = importlib.util.spec_from_file_location(
    "validate_dataset", Path(__file__).resolve().parent / "08_validate_dataset.py")
validate_dataset = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(validate_dataset)

# Maps the EXACT variable label used in script 05's variables_json (the
# var_label field, not the short builder kwarg) to a human-readable
# perturbation family and a short, generic (not numerically-specific)
# description of the expected physical effect. Generic chemistry reasoning
# only - not a literature claim.
PERTURBATION_FAMILIES = {
    "fe_cp_centroid_distance_angstrom": ("Fe-Cp stretch", "Changes Fe-ring distance; weakens/strengthens overall Fe-Cp bonding."),
    "cp_ring_rotation_angle_degree": ("Cp ring rotation", "Rotates one Cp ring toward staggered conformation; tests rotational/conformational flexibility."),
    "cp_ring_radius_perturbation_angstrom": ("Cp ring radius (C-C stretch)", "Expands/contracts the ring; probes ring strain and aromaticity-adjacent bonding."),
    "ni_c_distance_angstrom": ("Metal-ligand stretch", "Direct Ni-C bond stretch/compression; probes the primary bonding interaction."),
    "cr_c_distance_angstrom": ("Metal-ligand stretch", "Direct Cr-C bond stretch/compression; probes the primary bonding interaction."),
    "c_o_distance_angstrom": ("Carbonyl C-O stretch", "Stretches/compresses C-O; probes M->CO pi-backdonation strength indirectly."),
    "tetrahedral_angle_perturbation_degree": ("Tetrahedral angle distortion", "Breaks ideal Td angle locally; probes angular bending stiffness."),
    "axial_equatorial_distortion_angstrom": ("Octahedral axial/equatorial distortion", "Tetragonal (Jahn-Teller-like) distortion; probes Oh angular/axial stiffness."),
    "axial_fe_c_distance_angstrom": ("Axial Fe-C stretch", "Stretches/compresses the two axial Fe-C bonds; probes TBP axial bonding."),
    "equatorial_fe_c_distance_angstrom": ("Equatorial Fe-C stretch", "Stretches/compresses the three equatorial Fe-C bonds; probes TBP equatorial bonding."),
    "equatorial_angle_perturbation_degree": ("Equatorial angle distortion", "Breaks ideal 120-degree equatorial spacing; probes in-plane angular stiffness."),
    "berry_like_distortion_coordinate_degree": ("Berry-pseudorotation-like tilt", "Heuristic local coordinate toward TBP<->square-pyramidal interconversion - NOT a validated reaction path, exploratory only."),
}

# Variable labels excluded from representative selection for the FIRST
# follow-up QE campaign, with an explicit reason - not silently dropped.
EXCLUDED_FROM_SELECTION = {
    "berry_like_distortion_coordinate_degree": "heuristic/non-validated coordinate (see script 05 docstring) - "
                                                "deprioritized in favor of the 3 more standard stretch/angle families for fe_co5",
}


def read_xyz(path: Path) -> list[dict]:
    lines = path.read_text(encoding="utf-8").splitlines()
    n_atoms = int(lines[0].strip())
    positions = []
    for line in lines[2:2 + n_atoms]:
        parts = line.split()
        positions.append({"symbol": parts[0], "x": float(parts[1]), "y": float(parts[2]), "z": float(parts[3])})
    return positions


def _dist(p1: dict, p2: dict) -> float:
    return math.sqrt((p1["x"] - p2["x"]) ** 2 + (p1["y"] - p2["y"]) ** 2 + (p1["z"] - p2["z"]) ** 2)


def classify_candidate(variables_json: dict) -> dict:
    # variables_json has exactly one variable key + "delta_from_nominal" -
    # that key is the exact var_label string from script 05.
    var_label = next(k for k in variables_json if k != "delta_from_nominal")
    delta = variables_json["delta_from_nominal"]
    is_angle = var_label.endswith("_degree")

    family_label, expected_effect = PERTURBATION_FAMILIES.get(
        var_label, (var_label, "Unclassified perturbation - add to PERTURBATION_FAMILIES."))

    # Buckets are family-relative, not a single cross-unit threshold: small
    # angle steps are ~3-10 degrees, small distance steps are ~0.015-0.03 A
    # in this project's script-05 step design.
    small_threshold = 10.0 if is_angle else 0.03
    magnitude_bucket = "small" if abs(delta) <= small_threshold else "large"
    return {
        "var_label": var_label,
        "perturbation_family": family_label,
        "expected_physical_effect": expected_effect,
        "magnitude": delta,
        "magnitude_bucket": magnitude_bucket,
    }


def check_overlaps(positions: list[dict]) -> list[str]:
    issues = []
    n = len(positions)
    for i in range(n):
        for j in range(i + 1, n):
            d = _dist(positions[i], positions[j])
            if d < OVERLAP_THRESHOLD_ANGSTROM:
                issues.append(f"atom_overlap: {positions[i]['symbol']}{i}-{positions[j]['symbol']}{j} = {d:.4f} A")
    return issues


def check_bond_sanity(positions: list[dict], system_id: str) -> list[str]:
    raw_issues = validate_dataset.check_bond_lengths(positions, system_id)
    return [issue.replace("unrealistic_bond_length", "unrealistic_bond_length_after_perturbation")
            for issue in raw_issues]


def rmsd(positions_a: list[dict], positions_b: list[dict]) -> float:
    sq = sum((a[c] - b[c]) ** 2 for a, b in zip(positions_a, positions_b) for c in ("x", "y", "z"))
    return math.sqrt(sq / len(positions_a))


def find_duplicates(candidates: list[dict]) -> dict:
    """candidates: list of dicts with 'candidate_id', 'system_id', 'positions'.
    Returns {candidate_id: duplicate_of_candidate_id} for later (not earlier) duplicates."""
    duplicate_of = {}
    by_system: dict[str, list[dict]] = {}
    for c in candidates:
        by_system.setdefault(c["system_id"], []).append(c)
    for system_id, group in by_system.items():
        for i in range(len(group)):
            if group[i]["candidate_id"] in duplicate_of:
                continue
            for j in range(i + 1, len(group)):
                if group[j]["candidate_id"] in duplicate_of:
                    continue
                d = rmsd(group[i]["positions"], group[j]["positions"])
                if d < DUPLICATE_RMSD_THRESHOLD_ANGSTROM:
                    duplicate_of[group[j]["candidate_id"]] = group[i]["candidate_id"]
    return duplicate_of


def select_representatives(audited_rows: list[dict]) -> set:
    """Pick one representative per (system, family): the largest-magnitude
    accepted candidate, alternating which sign is preferred across a
    system's families so the selected set covers BOTH compression and
    elongation directions overall - always tie-breaking toward the same
    sign would explore only one side of the PES, defeating the point of
    selecting a diverse subset."""
    selected = set()
    by_system: dict[str, dict] = {}
    for row in audited_rows:
        if row["audit_status"] != "accepted":
            continue
        if row["var_label"] in EXCLUDED_FROM_SELECTION:
            continue
        by_system.setdefault(row["system_id"], {}).setdefault(row["perturbation_family"], []).append(row)

    for system_id, families in by_system.items():
        for family_index, family in enumerate(sorted(families)):
            rows = families[family]
            preferred_sign = -1 if family_index % 2 == 0 else 1
            same_sign_candidates = [r for r in rows if (r["magnitude"] >= 0) == (preferred_sign > 0)]
            pool = same_sign_candidates or rows
            best = max(pool, key=lambda r: abs(r["magnitude"]))
            selected.add(best["candidate_id"])
    return selected


def build_selection_reason(row: dict, was_selected: bool) -> str:
    if row["audit_status"] == "rejected":
        return f"not eligible: rejected by audit ({'; '.join(row['rejection_reasons'])})"
    if row["var_label"] in EXCLUDED_FROM_SELECTION:
        return f"excluded by design: {EXCLUDED_FROM_SELECTION[row['var_label']]}"
    if was_selected:
        return (f"representative of {row['perturbation_family']} family "
                f"({row['perturbation_direction']} direction, largest accepted magnitude in this slot)")
    return f"not selected: another candidate in {row['perturbation_family']} was preferred for this system/sign slot"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    manifest_path = PROJECT_ROOT / "data" / "raw" / "candidate_manifest_v0.csv"
    if not manifest_path.exists():
        logger.error("Candidate manifest not found at %s - run scripts/05_generate_perturbation_candidates.py first",
                      manifest_path)
        return 1

    with manifest_path.open(encoding="utf-8") as f:
        manifest_rows = list(csv.DictReader(f))

    candidates_with_positions = []
    audited_rows = []
    for row in manifest_rows:
        candidate_id = row["candidate_id"]
        system_id = row["complex_id"]
        xyz_path = Path(row["structure_path"])
        if not xyz_path.exists():
            logger.error("Missing structure file for %s: %s", candidate_id, xyz_path)
            return 1
        positions = read_xyz(xyz_path)
        variables = json.loads(row["variables_json"])

        classification = classify_candidate(variables)
        issues = check_overlaps(positions) + check_bond_sanity(positions, system_id)
        var_label = classification["var_label"]

        audited_rows.append({
            "candidate_id": candidate_id,
            "system_id": system_id,
            "parent_structure": f"{system_id}_initial",  # the validated relaxed QE result this perturbs from
            "perturbation_parameter": var_label,
            "perturbation_direction": "positive" if classification["magnitude"] >= 0 else "negative",
            **classification,
            "audit_status": "rejected" if issues else "accepted",
            "rejection_reasons": issues,
            "is_duplicate_of": None,
        })
        candidates_with_positions.append({"candidate_id": candidate_id, "system_id": system_id, "positions": positions})

    duplicate_map = find_duplicates(candidates_with_positions)
    for row in audited_rows:
        dup_of = duplicate_map.get(row["candidate_id"])
        if dup_of:
            row["is_duplicate_of"] = dup_of
            row["audit_status"] = "rejected"
            row["rejection_reasons"].append(f"duplicate_of: {dup_of}")

    selected_ids = select_representatives(audited_rows)
    for row in audited_rows:
        row["selected_as_representative"] = row["candidate_id"] in selected_ids
        row["selection_reason"] = build_selection_reason(row, row["candidate_id"] in selected_ids)

    n_accepted = sum(1 for r in audited_rows if r["audit_status"] == "accepted")
    n_rejected = len(audited_rows) - n_accepted
    n_selected = len(selected_ids)
    logger.info("Audited %d candidates: %d accepted, %d rejected, %d selected as representatives",
                len(audited_rows), n_accepted, n_rejected, n_selected)

    if args.dry_run:
        print(json.dumps(audited_rows, indent=2))
        logger.info("Dry run: not writing audit files")
        return 0

    audit_csv_path = PROJECT_ROOT / "data" / "processed" / "candidate_audit_v0.csv"
    audit_csv_path.parent.mkdir(parents=True, exist_ok=True)
    with audit_csv_path.open("w", newline="", encoding="utf-8") as f:
        flat_rows = []
        for r in audited_rows:
            flat = dict(r)
            flat["rejection_reasons"] = json.dumps(flat["rejection_reasons"])
            flat_rows.append(flat)
        writer = csv.DictWriter(f, fieldnames=list(flat_rows[0].keys()))
        writer.writeheader()
        writer.writerows(flat_rows)
    logger.info("Wrote %s", audit_csv_path)

    report_path = PROJECT_ROOT / "reports" / "candidate_audit_report_v0.md"
    report_path.write_text(build_report(audited_rows), encoding="utf-8")
    logger.info("Wrote %s", report_path)

    return 0


def build_report(rows: list[dict]) -> str:
    lines = []
    lines.append("# Perturbation Candidate Audit Report - v0")
    lines.append("")
    lines.append(f"Generated by `scripts/05b_audit_perturbation_candidates.py` (auditor_version {AUDITOR_VERSION}).")
    lines.append("")
    n_total = len(rows)
    n_accepted = sum(1 for r in rows if r["audit_status"] == "accepted")
    n_rejected = n_total - n_accepted
    n_selected = sum(1 for r in rows if r["selected_as_representative"])
    lines.append(f"- Total candidates audited: {n_total}")
    lines.append(f"- Accepted: {n_accepted}")
    lines.append(f"- Rejected: {n_rejected}")
    lines.append(f"- Selected as representatives for the next QE campaign: {n_selected}")
    lines.append("")

    lines.append("## Classification (all candidates)")
    lines.append("")
    lines.append("| Candidate | Parent | Family | Parameter | Direction | Magnitude | Expected effect |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in sorted(rows, key=lambda r: (r["system_id"], r["perturbation_family"])):
        lines.append(f"| {r['candidate_id']} | {r['parent_structure']} | {r['perturbation_family']} | "
                      f"{r['perturbation_parameter']} | {r['perturbation_direction']} | "
                      f"{r['magnitude']} | {r['expected_physical_effect']} |")
    lines.append("")

    rejected = [r for r in rows if r["audit_status"] == "rejected"]
    lines.append("## Rejected candidates")
    lines.append("")
    if rejected:
        lines.append("| Candidate | Reasons |")
        lines.append("|---|---|")
        for r in rejected:
            lines.append(f"| {r['candidate_id']} | {'; '.join(r['rejection_reasons'])} |")
    else:
        lines.append("None - all 52 candidates passed the overlap/bond-sanity/duplicate checks.")
    lines.append("")

    lines.append("## Selected representatives")
    lines.append("")
    lines.append("| Candidate | System | Family | Magnitude | Selection reason |")
    lines.append("|---|---|---|---|---|")
    for r in rows:
        if r["selected_as_representative"]:
            lines.append(f"| {r['candidate_id']} | {r['system_id']} | {r['perturbation_family']} | "
                          f"{r['magnitude']} | {r['selection_reason']} |")
    lines.append("")
    excluded_note = "; ".join(f"{k}: {v}" for k, v in EXCLUDED_FROM_SELECTION.items())
    lines.append(f"**Excluded from selection (by design, not by audit failure):** {excluded_note}")
    lines.append("")

    lines.append("## Auditor assumptions")
    lines.append("")
    lines.append(f"- Atom-overlap threshold: {OVERLAP_THRESHOLD_ANGSTROM} A (any pair closer than this is rejected outright).")
    lines.append("- Bond-sanity check reuses scripts/08_validate_dataset.py's system-topology-aware "
                  "EXPECTED_BOND_PAIRS logic (the same generic chemical-bonding gross-error ranges "
                  "applied to relaxed QE results, applied here to unrelaxed perturbed structures).")
    lines.append(f"- Duplicate detection: pairwise coordinate RMSD < {DUPLICATE_RMSD_THRESHOLD_ANGSTROM} A "
                  "within the same system (no alignment needed - all candidates share the same atom "
                  "ordering/frame from the builder functions).")
    lines.append("- Representative selection picks the largest-magnitude ACCEPTED candidate per "
                  "(system, perturbation family) - maximizes distance from equilibrium (more informative "
                  "for a future surrogate model) while still passing every chemical-reasonableness check.")
    lines.append("- Sign (compression vs. elongation/positive-angle vs. negative-angle) alternates across "
                  "a system's families rather than always tie-breaking the same direction - otherwise all "
                  "selected candidates would explore only one side of the PES, defeating the point of a "
                  "diverse subset.")
    lines.append("- `parent_structure` (e.g. `ferrocene_initial`) refers to this project's validated, "
                  "QE-relaxed reference structure for that system (status `validated` in "
                  "`data/processed/full_dataset_v0.1.csv`) - the `_initial` suffix is a pre-existing "
                  "candidate_id naming artifact from script 06, not an indication the parent is unrelaxed. "
                  "Note the perturbation itself was applied to script 04's nominal (literature-typical) "
                  "bond-length parameterization, not literally to the relaxed atom coordinates - the "
                  "relaxed structure is the correct scientific reference point for interpreting/comparing "
                  "results, even though it isn't the literal geometric starting point each candidate's "
                  "internal coordinates were perturbed from.")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
