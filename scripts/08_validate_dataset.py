"""Validate parsed QE results before any ML/dataset use.

Reads data/processed/initial_relax_parsed_v0.1.json (script 07's output) and
labels every row reliable / usable_with_caution / failed / needs_rerun /
outlier. Rows are never deleted - only labeled, with the specific reasons
recorded, so nothing is silently hidden.

Usage:
    python scripts/08_validate_dataset.py
    python scripts/08_validate_dataset.py --dry-run
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import PROJECT_ROOT, load_yaml, setup_logger  # noqa: E402

logger = setup_logger("validate_dataset", "dataset_validation.log")

VALIDATOR_VERSION = "0.1.0"

# Generic chemical-bonding sanity ranges (gross-error detection only - not
# literature reference values, see references/reference_values_tmc_v0.yaml
# for the separately-tracked, source-cited reference comparison).
BOND_RANGES_ANGSTROM = {
    frozenset({"Fe", "C"}): (1.6, 2.3),
    frozenset({"Ni", "C"}): (1.6, 2.1),
    frozenset({"Cr", "C"}): (1.6, 2.2),
    frozenset({"C", "O"}): (1.05, 1.30),
    frozenset({"C", "C"}): (1.30, 1.55),
    frozenset({"C", "H"}): (0.95, 1.20),
}
MIN_PLAUSIBLE_ABS_ENERGY_EV = 50.0  # catches parser/calc catastrophes, not precision errors

# Which element pairs are actually bonded in each system's known topology
# (from how scripts/04_build_initial_structures.py built them) - e.g. CO
# ligand carbons are bonded to the metal and their own O, never to each
# other, so a generic "any C-C pair" check would flag non-bonded inter-
# ligand C...C distances as false positives.
EXPECTED_BOND_PAIRS = {
    "ferrocene": {frozenset({"Fe", "C"}), frozenset({"C", "C"}), frozenset({"C", "H"})},
    "ni_co4": {frozenset({"Ni", "C"}), frozenset({"C", "O"})},
    "cr_co6": {frozenset({"Cr", "C"}), frozenset({"C", "O"})},
    "fe_co5": {frozenset({"Fe", "C"}), frozenset({"C", "O"})},
}


def _dist(p1: dict, p2: dict) -> float:
    return math.sqrt((p1["x"] - p2["x"]) ** 2 + (p1["y"] - p2["y"]) ** 2 + (p1["z"] - p2["z"]) ** 2)


def check_bond_lengths(positions: list[dict], system_id: str) -> list[str]:
    """For each atom, check the distance to its NEAREST neighbor of each
    element it's actually expected to bond to in this system's known
    topology - not all element pairs with a defined range, and not all
    pairwise distances. Either of those would also catch non-bonded
    through-space pairs (e.g. 1,3-carbons across a Cp ring, ~2.3 A; or
    inter-ligand C...C distances in M(CO)n complexes, ~2.5-3.0 A) as false
    positives."""
    issues = []
    if not positions:
        return issues

    expected_pairs = EXPECTED_BOND_PAIRS.get(system_id)
    if expected_pairs is None:
        return issues  # unknown system topology - don't guess at bonding

    by_element: dict[str, list[int]] = {}
    for idx, p in enumerate(positions):
        by_element.setdefault(p["symbol"], []).append(idx)

    checked_pairs = set()
    for i, p_i in enumerate(positions):
        for elem_j, indices_j in by_element.items():
            pair_key = frozenset({p_i["symbol"], elem_j})
            if pair_key not in expected_pairs:
                continue
            bounds = BOND_RANGES_ANGSTROM.get(pair_key)
            if bounds is None:
                continue
            nearest = min(
                ((_dist(p_i, positions[j]), j) for j in indices_j if j != i),
                default=None,
            )
            if nearest is None:
                continue
            d, j = nearest
            dedup_key = frozenset({i, j})
            if dedup_key in checked_pairs:
                continue
            checked_pairs.add(dedup_key)
            lo, hi = bounds
            if not (lo <= d <= hi):
                issues.append(
                    f"unrealistic_bond_length: {p_i['symbol']}{i}-{positions[j]['symbol']}{j} "
                    f"= {d:.4f} A, outside sanity range [{lo}, {hi}] A")
    return issues


def check_reference_availability(system_id: str, reference_data: dict) -> list[str]:
    entry = reference_data.get(system_id)
    if entry is None:
        return [f"missing_reference_source: '{system_id}' not present in reference_values_tmc_v0.yaml"]
    if entry.get("status") != "verified":
        return [f"missing_reference_source: reference status is '{entry.get('status')}', not 'verified'"]
    return []


def check_pseudopotentials(pseudo_manifest: dict, elements_used: set[str]) -> list[str]:
    issues = []
    if pseudo_manifest.get("status") != "ready":
        issues.append(f"missing_pseudopotentials: manifest status is '{pseudo_manifest.get('status')}'")
    for el in elements_used:
        entry = pseudo_manifest.get("elements", {}).get(el)
        if entry is None or not entry.get("exists"):
            issues.append(f"missing_pseudopotentials: no pseudopotential recorded for element {el}")
    for warning in pseudo_manifest.get("naming_convention_warnings", []):
        el = warning.split(":")[0].strip()
        if el in elements_used:
            issues.append(f"pseudopotential_naming_caution: {warning}")
    return issues


def elements_from_positions(positions: Optional[list]) -> set:
    if not positions:
        return set()
    return {p["symbol"] for p in positions}


def validate_record(record: dict, reference_data: dict, pseudo_manifest: dict) -> dict:
    issues = []

    if not record["job_done"]:
        issues.append("job_did_not_complete")
    if record["convergence_status"] != "converged":
        issues.append(f"non_converged: convergence_status='{record['convergence_status']}'")
    if record["final_energy_ry"] is None:
        issues.append("missing_energy")
    elif abs(record["final_energy_ev"]) < MIN_PLAUSIBLE_ABS_ENERGY_EV:
        issues.append(f"extreme_energy: |{record['final_energy_ev']:.4f} eV| implausibly small")
    if record["final_positions_angstrom"] is None:
        issues.append("missing_final_geometry")

    bond_issues = check_bond_lengths(record["final_positions_angstrom"] or [], record["system_id"])
    issues.extend(bond_issues)

    elements_used = elements_from_positions(record["final_positions_angstrom"])
    issues.extend(check_pseudopotentials(pseudo_manifest, elements_used))
    issues.extend(check_reference_availability(record["system_id"], reference_data))

    if record["warnings"]:
        issues.extend(f"parser_warning: {w}" for w in record["warnings"])
    if record["failures"]:
        issues.extend(f"parser_failure: {f}" for f in record["failures"])

    label = classify(record, issues)
    return {"label": label, "validation_issues": issues}


def classify(record: dict, issues: list[str]) -> str:
    if not record["job_done"] or record["convergence_status"] == "not_converged":
        return "failed"
    if record["convergence_status"] == "unknown":
        return "needs_rerun"
    if record["final_energy_ry"] is None or record["final_positions_angstrom"] is None:
        return "needs_rerun"
    if any(i.startswith("unrealistic_bond_length") or i.startswith("extreme_energy") for i in issues):
        return "outlier"
    if any(i.startswith("missing_reference_source") or i.startswith("pseudopotential_naming_caution")
           or i.startswith("parser_warning") for i in issues):
        return "usable_with_caution"
    return "reliable"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--input", default="data/processed/initial_relax_parsed_v0.1.json",
                         help="Parsed JSON input (default: data/processed/initial_relax_parsed_v0.1.json). "
                              "Pass a different path to validate a separate batch without overwriting "
                              "Phase 1 output (e.g. data/processed/candidates_relax_parsed_v0.1.json).")
    parser.add_argument("--output", default="data/processed/full_dataset_v0.csv",
                         help="Validated CSV output (default: data/processed/full_dataset_v0.csv).")
    args = parser.parse_args()

    parsed_path = PROJECT_ROOT / args.input
    if not parsed_path.exists():
        logger.error("Parsed dataset not found at %s - run scripts/07_parse_qe_outputs.py first", parsed_path)
        return 1
    records = json.loads(parsed_path.read_text(encoding="utf-8"))

    reference_path = PROJECT_ROOT / "references" / "reference_values_tmc_v0.yaml"
    reference_data = load_yaml(str(reference_path.relative_to(PROJECT_ROOT))) if reference_path.exists() else {}

    manifest_path = PROJECT_ROOT / "configs" / "pseudo_manifest_required.yaml"
    pseudo_manifest = load_yaml("configs/pseudo_manifest_required.yaml") if manifest_path.exists() else {}

    system_ids = [r["system_id"] for r in records]
    duplicate_ids = {sid for sid, count in Counter(system_ids).items() if count > 1}

    full_rows = []
    for record in records:
        validation = validate_record(record, reference_data, pseudo_manifest)
        if record["system_id"] in duplicate_ids:
            validation["validation_issues"].append("duplicate_system_id")
            validation["label"] = "needs_rerun"
        row = dict(record)
        row["validator_version"] = VALIDATOR_VERSION
        row["label"] = validation["label"]
        row["validation_issues"] = validation["validation_issues"]
        full_rows.append(row)
        logger.info("system=%s label=%s issues=%d", row["system_id"], row["label"], len(row["validation_issues"]))

    label_counts = Counter(r["label"] for r in full_rows)
    logger.info("Label counts: %s", dict(label_counts))

    if args.dry_run:
        print(json.dumps(full_rows, indent=2))
        logger.info("Dry run: not writing dataset files")
        return 0

    def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
        json_cols = ("final_lattice_angstrom", "final_positions_angstrom", "warnings",
                     "failures", "validation_issues")
        flat_rows = []
        for r in rows:
            flat = dict(r)
            for col in json_cols:
                flat[col] = json.dumps(flat[col]) if flat.get(col) is not None else ""
            flat_rows.append(flat)
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(flat_rows)
        logger.info("Wrote %s (%d data row(s))", path, len(rows))

    fieldnames = list(full_rows[0].keys())

    full_path = PROJECT_ROOT / args.output
    write_csv(full_path, full_rows, fieldnames)

    output_stem = Path(args.output).stem  # e.g. "full_dataset_v0" or "full_dataset_candidates_v0"
    reliable_rows = [r for r in full_rows if r["label"] == "reliable"]
    reliable_stem = output_stem.replace("full_dataset", "reliable_subset")
    reliable_path = PROJECT_ROOT / "data" / "processed" / f"{reliable_stem}.csv"
    write_csv(reliable_path, reliable_rows, fieldnames)
    if not reliable_rows:
        logger.warning("No rows labeled 'reliable' yet - %s has headers only, no data rows", reliable_path.name)

    report_name = output_stem.replace("full_dataset", "dataset_validation_report") + ".md"
    report_path = PROJECT_ROOT / "reports" / report_name
    report_path.parent.mkdir(parents=True, exist_ok=True)
    input_label = parsed_path.relative_to(PROJECT_ROOT).as_posix()
    report_path.write_text(build_report(full_rows, label_counts, input_label), encoding="utf-8")
    logger.info("Wrote %s", report_path)

    return 0


def build_report(rows: list[dict], label_counts: Counter, input_label: str) -> str:
    lines = []
    lines.append("# Dataset Validation Report - v0")
    lines.append("")
    lines.append(f"Generated by `scripts/08_validate_dataset.py` (validator_version {VALIDATOR_VERSION}) "
                  f"from `{input_label}`.")
    lines.append("")
    lines.append("## Label counts")
    lines.append("")
    for label in ("reliable", "usable_with_caution", "needs_rerun", "outlier", "failed"):
        lines.append(f"- {label}: {label_counts.get(label, 0)}")
    lines.append("")
    lines.append("## Per-system detail")
    lines.append("")
    lines.append("| system_id | label | issue count | issues |")
    lines.append("|---|---|---|---|")
    for r in rows:
        issues_str = "; ".join(r["validation_issues"]) if r["validation_issues"] else "none"
        lines.append(f"| {r['system_id']} | {r['label']} | {len(r['validation_issues'])} | {issues_str} |")
    lines.append("")
    lines.append("## Why nothing is labeled fully 'reliable' yet")
    lines.append("")
    lines.append("Every system currently lacks a `verified` entry in "
                  "`references/reference_values_tmc_v0.yaml` (all are still `needs_manual_review`), "
                  "and `policy.require_reference_verification: true` in `configs/project_config.yaml` "
                  "means missing reference comparison caps a row at `usable_with_caution`, never "
                  "`reliable`, even when the QE relax itself converged cleanly. This is intentional - "
                  "see CLAUDE_ACTISTRUCT_TMC_PLAN.md Sec 4 and Sec 13 (no claims beyond the data).")
    lines.append("")
    lines.append("## Validator assumptions")
    lines.append("")
    lines.append("- Bond-length sanity ranges (e.g. M-C, C-O, C-C, C-H) are generic chemical-bonding "
                  "gross-error bounds, not literature reference values - they catch dissociation/collapse/"
                  "unit errors, not precision deviations.")
    lines.append("- `extreme_energy` only flags implausibly small total energies (|E| < "
                  f"{MIN_PLAUSIBLE_ABS_ENERGY_EV} eV) as a parser/calculation-catastrophe check - it is "
                  "not a per-atom DFT-accuracy claim.")
    lines.append("- Rows are never deleted or modified; only `label` and `validation_issues` are added "
                  "on top of the parser's original record.")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
