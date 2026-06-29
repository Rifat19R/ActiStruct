"""Compare relaxed QE geometries against literature/crystallographic reference values.

Produces the System | QE | Literature | Delta | %Error table the project
needs before any claim can be trusted. Bond lengths are measured purely from
the relaxed geometry's own internal angles/distances (e.g. axial vs
equatorial in Fe(CO)5 is determined from which Fe-C-C angle is closest to
180 degrees, not from a hardcoded atom index or coordinate axis) - never
assumed from how the structure happened to be built.

Usage:
    python scripts/13_compare_to_references.py
    python scripts/13_compare_to_references.py --dry-run
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import PROJECT_ROOT, load_yaml, setup_logger  # noqa: E402

logger = setup_logger("compare_to_references", "reference_validation.log")

VALIDATOR_VERSION = "0.1.0"
# This project's own working tolerance for calling a bond length "validated"
# against literature - not itself a literature-derived number, just a
# pragmatic threshold documented here so it can be challenged/changed.
TOLERANCE_ABSOLUTE_ANGSTROM = 0.03
TOLERANCE_RELATIVE_PERCENT = 3.0


def _dist(p1: dict, p2: dict) -> float:
    return math.sqrt((p1["x"] - p2["x"]) ** 2 + (p1["y"] - p2["y"]) ** 2 + (p1["z"] - p2["z"]) ** 2)


def _angle_deg(center: dict, a: dict, b: dict) -> float:
    v1 = (a["x"] - center["x"], a["y"] - center["y"], a["z"] - center["z"])
    v2 = (b["x"] - center["x"], b["y"] - center["y"], b["z"] - center["z"])
    dot = sum(x * y for x, y in zip(v1, v2))
    n1 = math.sqrt(sum(x * x for x in v1))
    n2 = math.sqrt(sum(x * x for x in v2))
    cos_theta = max(-1.0, min(1.0, dot / (n1 * n2)))
    return math.degrees(math.acos(cos_theta))


def _nearest(center: dict, candidates: list[dict], exclude_idx: set[int] = frozenset()) -> list[tuple[float, int]]:
    return sorted(
        ((_dist(center, c), i) for i, c in enumerate(candidates) if i not in exclude_idx),
    )


def measure_mean_nearest_neighbor(positions: list[dict], elem_a: str, elem_b: str) -> float:
    """Mean distance from each atom of elem_a to its nearest atom of elem_b
    (deduplicated so a mutual pair is only counted once)."""
    distances = []
    seen_pairs = set()
    for i, p in enumerate(positions):
        if p["symbol"] != elem_a:
            continue
        best = min(
            ((_dist(p, q), j) for j, q in enumerate(positions) if q["symbol"] == elem_b and j != i),
            default=None,
        )
        if best is None:
            continue
        d, j = best
        key = frozenset({i, j})
        if key in seen_pairs:
            continue
        seen_pairs.add(key)
        distances.append(d)
    if not distances:
        raise ValueError(f"no {elem_a}-{elem_b} pairs found")
    return sum(distances) / len(distances)


def classify_fe_co5_axial_equatorial(positions: list[dict]) -> tuple[list[int], list[int]]:
    """Determine which of the 5 carbonyl carbons are axial vs equatorial
    purely from the relaxed geometry: the two C-Fe-C angles closest to 180
    degrees identify the axial pair (trans to each other through the metal);
    the remaining three are equatorial. No coordinate-axis or atom-index
    assumption."""
    fe = next(p for p in positions if p["symbol"] == "Fe")
    carbons = [(i, p) for i, p in enumerate(positions) if p["symbol"] == "C"]
    if len(carbons) != 5:
        raise ValueError(f"expected 5 carbonyl carbons for Fe(CO)5, found {len(carbons)}")

    best_pair, best_angle = None, -1.0
    for (i1, c1), (i2, c2) in itertools.combinations(carbons, 2):
        angle = _angle_deg(fe, c1, c2)
        if angle > best_angle:
            best_angle, best_pair = angle, (i1, i2)

    axial_indices = list(best_pair)
    equatorial_indices = [i for i, _ in carbons if i not in axial_indices]
    return axial_indices, equatorial_indices


def carbon_to_its_oxygen(positions: list[dict], carbon_idx: int) -> int:
    c = positions[carbon_idx]
    return min(
        (i for i, p in enumerate(positions) if p["symbol"] == "O"),
        key=lambda i: _dist(c, positions[i]),
    )


# Per (system_id, reference_label) -> function(positions) -> measured value in Angstrom
def build_measurements(positions: list[dict]) -> dict:
    measurements = {}
    symbols_present = {p["symbol"] for p in positions}

    if "Fe" in symbols_present and "H" in symbols_present:  # ferrocene
        measurements["Fe-C"] = measure_mean_nearest_neighbor(positions, "Fe", "C")
        ring_cc = []
        carbons = [(i, p) for i, p in enumerate(positions) if p["symbol"] == "C"]
        seen = set()
        for i, p in carbons:
            best = min(
                ((_dist(p, q), j) for j, q in carbons if j != i),
                default=None,
            )
            if best is None:
                continue
            d, j = best
            key = frozenset({i, j})
            if key in seen:
                continue
            seen.add(key)
            ring_cc.append(d)
        measurements["C-C (Cp ring)"] = sum(ring_cc) / len(ring_cc)

    elif "Ni" in symbols_present:
        measurements["Ni-C"] = measure_mean_nearest_neighbor(positions, "Ni", "C")
        measurements["C-O"] = measure_mean_nearest_neighbor(positions, "C", "O")

    elif "Cr" in symbols_present:
        measurements["Cr-C"] = measure_mean_nearest_neighbor(positions, "Cr", "C")
        measurements["C-O"] = measure_mean_nearest_neighbor(positions, "C", "O")

    elif "Fe" in symbols_present:  # fe_co5 (no H present, unlike ferrocene)
        axial_idx, eq_idx = classify_fe_co5_axial_equatorial(positions)
        fe = next(p for p in positions if p["symbol"] == "Fe")
        measurements["Fe-C axial"] = sum(_dist(fe, positions[i]) for i in axial_idx) / len(axial_idx)
        measurements["Fe-C equatorial"] = sum(_dist(fe, positions[i]) for i in eq_idx) / len(eq_idx)
        axial_co = [_dist(positions[i], positions[carbon_to_its_oxygen(positions, i)]) for i in axial_idx]
        eq_co = [_dist(positions[i], positions[carbon_to_its_oxygen(positions, i)]) for i in eq_idx]
        measurements["C-O axial"] = sum(axial_co) / len(axial_co)
        measurements["C-O equatorial"] = sum(eq_co) / len(eq_co)

    return measurements


def is_source_documented(source: dict | None) -> bool:
    """A source is 'documented' if it has a traceable identifier (DOI or
    URL/accession) or, failing that, a complete print bibliographic entry
    (title + authors + year + journal/database) - e.g. a CRC Handbook
    citation has no DOI but is still a fully traceable reference."""
    if source is None:
        return False
    if source.get("doi") or source.get("url_or_accession"):
        return True
    return bool(source.get("title") and source.get("authors") and source.get("year")
                and source.get("journal_or_database"))


def compare_system(system_id: str, positions: list[dict], reference_entry: dict) -> list[dict]:
    measurements = build_measurements(positions)
    rows = []
    for bond in reference_entry["reference_values"]["bond_lengths"]:
        label = bond["label"]
        lit_value = bond["value_angstrom"]
        qe_value = measurements.get(label)
        row = {
            "system_id": system_id,
            "label": label,
            "qe_angstrom": qe_value,
            "literature_angstrom": lit_value,
            "delta_angstrom": None,
            "percent_error": None,
            "within_tolerance": None,
            "source_id": bond["source_id"],
        }
        if qe_value is not None and lit_value is not None:
            delta = qe_value - lit_value
            row["delta_angstrom"] = round(delta, 5)
            row["percent_error"] = round(100.0 * delta / lit_value, 4)
            row["within_tolerance"] = (
                abs(delta) <= TOLERANCE_ABSOLUTE_ANGSTROM
                or abs(row["percent_error"]) <= TOLERANCE_RELATIVE_PERCENT
            )
        rows.append(row)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    parsed_path = PROJECT_ROOT / "data" / "processed" / "initial_relax_parsed_v0.1.json"
    if not parsed_path.exists():
        logger.error("Parsed dataset not found at %s - run scripts/07_parse_qe_outputs.py first", parsed_path)
        return 1
    records = json.loads(parsed_path.read_text(encoding="utf-8"))

    reference_data = load_yaml("references/reference_values_tmc_v0.yaml")

    full_dataset_path = PROJECT_ROOT / "data" / "processed" / "full_dataset_v0.csv"
    dataset_labels = {}
    if full_dataset_path.exists():
        with full_dataset_path.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                dataset_labels[r["system_id"]] = r["label"]

    all_rows = []
    system_verdicts = {}
    for record in records:
        system_id = record["system_id"]
        if record["convergence_status"] != "converged" or not record["final_positions_angstrom"]:
            logger.warning("Skipping %s: not converged or no geometry available", system_id)
            continue
        reference_entry = reference_data.get(system_id)
        if reference_entry is None:
            logger.warning("Skipping %s: no reference entry found", system_id)
            continue

        rows = compare_system(system_id, record["final_positions_angstrom"], reference_entry)
        all_rows.extend(rows)

        comparable = [r for r in rows if r["within_tolerance"] is not None]
        all_within_tolerance = bool(comparable) and all(r["within_tolerance"] for r in comparable)
        all_sources_documented = all(
            is_source_documented(reference_entry["sources"].get(r["source_id"])) for r in rows
        )
        if all_within_tolerance and all_sources_documented and len(comparable) == len(rows):
            verdict = "validated"
        elif comparable:
            verdict = "deviates_from_literature"
        else:
            verdict = "insufficient_reference_data"
        system_verdicts[system_id] = verdict
        logger.info("system=%s verdict=%s (%d/%d bonds within tolerance)",
                    system_id, verdict, sum(1 for r in comparable if r["within_tolerance"]), len(rows))

    if args.dry_run:
        print(json.dumps(all_rows, indent=2))
        logger.info("Dry run: not writing comparison files")
        return 0

    comparison_path = PROJECT_ROOT / "reports" / "tables" / "reference_comparison_v0.csv"
    comparison_path.parent.mkdir(parents=True, exist_ok=True)
    with comparison_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(all_rows[0].keys()))
        writer.writeheader()
        writer.writerows(all_rows)
    logger.info("Wrote %s", comparison_path)

    report_path = PROJECT_ROOT / "reports" / "reference_validation_v0.1.md"
    report_path.write_text(build_report(all_rows, system_verdicts), encoding="utf-8")
    logger.info("Wrote %s", report_path)

    if dataset_labels:
        updated_path = PROJECT_ROOT / "data" / "processed" / "full_dataset_v0.1.csv"
        write_updated_dataset(full_dataset_path, updated_path, system_verdicts)
        logger.info("Wrote %s", updated_path)

    return 0


def write_updated_dataset(source_path: Path, dest_path: Path, system_verdicts: dict) -> None:
    with source_path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        fieldnames = list(rows[0].keys())
    for row in rows:
        if system_verdicts.get(row["system_id"]) == "validated":
            row["label"] = "validated"
    with dest_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_report(rows: list[dict], system_verdicts: dict) -> str:
    lines = []
    lines.append("# Reference Validation Report - v0.1")
    lines.append("")
    lines.append(f"Generated by `scripts/13_compare_to_references.py` (validator_version {VALIDATOR_VERSION}).")
    lines.append("")
    lines.append(f"**Tolerance for 'validated':** within {TOLERANCE_ABSOLUTE_ANGSTROM} A absolute OR "
                  f"{TOLERANCE_RELATIVE_PERCENT}% relative (whichever is looser) on every measured bond. "
                  "This is this project's own working threshold, not itself a literature value.")
    lines.append("")
    lines.append("## System | QE | Literature | Delta | %Error")
    lines.append("")
    lines.append("| System | Bond | QE (A) | Literature (A) | Delta (A) | % Error | Within tolerance |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in rows:
        qe = f"{r['qe_angstrom']:.4f}" if r["qe_angstrom"] is not None else "n/a"
        lit = f"{r['literature_angstrom']:.4f}" if r["literature_angstrom"] is not None else "n/a"
        delta = f"{r['delta_angstrom']:+.4f}" if r["delta_angstrom"] is not None else "n/a"
        pct = f"{r['percent_error']:+.2f}%" if r["percent_error"] is not None else "n/a"
        tol = "yes" if r["within_tolerance"] else ("no" if r["within_tolerance"] is False else "n/a")
        lines.append(f"| {r['system_id']} | {r['label']} | {qe} | {lit} | {delta} | {pct} | {tol} |")
    lines.append("")
    lines.append("## Per-system verdict")
    lines.append("")
    for system_id, verdict in system_verdicts.items():
        source_ids = {r["source_id"] for r in rows if r["system_id"] == system_id}
        sources_str = ", ".join(sorted(source_ids))
        lines.append(f"- **{system_id}**: `{verdict}` (compared against: {sources_str})")
    lines.append("")
    lines.append("## Important caveat")
    lines.append("")
    lines.append("Reference values were retrieved via AI web search/fetch on 2026-06-29 and "
                  "DOI-verified to exist, but primary-source PDFs were not independently opened "
                  "for most entries (publisher access-gated) - see "
                  "`references/reference_values_tmc_v0.yaml` notes per source. A `validated` "
                  "verdict here means \"this project's relaxed geometry agrees with the literature "
                  "value to within this project's stated tolerance\" - it does NOT mean the "
                  "literature value itself has been human-verified against the primary PDF. "
                  "Manual PDF confirmation is still recommended before any external scientific claim.")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
