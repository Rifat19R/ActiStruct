"""Create the reference values schema for the four primary TMC systems.

No web/API lookups are performed here - this writes an empty, source-tagged
schema with null values that must be filled in manually from verified
literature/database sources. Never fabricate values.

Usage:
    python scripts/03_collect_reference_stub.py
    python scripts/03_collect_reference_stub.py --dry-run
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import PROJECT_ROOT, setup_logger  # noqa: E402

import yaml

logger = setup_logger("collect_reference_stub", "bootstrap.log")

# Identity metadata only (formula, charge, geometry class) - not reference
# values. These are chemical facts, not measurements requiring a citation.
PRIMARY_SYSTEMS = {
    "ferrocene": {
        "name": "Ferrocene",
        "formula": "Fe(C5H5)2",
        "charge": 0,
        "spin_or_multiplicity": None,
        "geometry_class": "sandwich",
    },
    "ni_co4": {
        "name": "Nickel tetracarbonyl",
        "formula": "Ni(CO)4",
        "charge": 0,
        "spin_or_multiplicity": None,
        "geometry_class": "tetrahedral",
    },
    "cr_co6": {
        "name": "Chromium hexacarbonyl",
        "formula": "Cr(CO)6",
        "charge": 0,
        "spin_or_multiplicity": None,
        "geometry_class": "octahedral",
    },
    "fe_co5": {
        "name": "Iron pentacarbonyl",
        "formula": "Fe(CO)5",
        "charge": 0,
        "spin_or_multiplicity": None,
        "geometry_class": "trigonal_bipyramidal",
    },
}


def build_stub() -> dict:
    stub = {}
    for complex_id, meta in PRIMARY_SYSTEMS.items():
        stub[complex_id] = {
            **meta,
            "reference_values": {
                "bond_lengths": [],
                "angles": [],
                "relative_energies": [],
                "barriers": [],
            },
            "sources": {},
            "status": "needs_manual_review",
        }
    return stub


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    stub = build_stub()
    logger.info("Built reference stub for %d primary systems, all status=needs_manual_review",
                len(stub))

    if args.dry_run:
        print(yaml.safe_dump(stub, sort_keys=False))
        logger.info("Dry run: not writing reference files")
        return 0

    ref_path = PROJECT_ROOT / "references" / "reference_values_tmc_v0.yaml"
    if ref_path.exists():
        logger.info("Skipping existing %s (delete manually if a clean regenerate is intended)", ref_path)
    else:
        ref_path.write_text(yaml.safe_dump(stub, sort_keys=False), encoding="utf-8")
        logger.info("Wrote %s", ref_path)

    sources_csv = PROJECT_ROOT / "references" / "reference_sources_v0.csv"
    if not sources_csv.exists():
        with sources_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["source_id", "type", "title", "authors", "year",
                              "journal_or_database", "doi", "url_or_accession",
                              "access_date", "notes"])
        logger.info("Wrote %s", sources_csv)
    else:
        logger.info("Skipping existing %s", sources_csv)

    completeness_path = PROJECT_ROOT / "reports" / "tables" / "reference_completeness_report.csv"
    completeness_path.parent.mkdir(parents=True, exist_ok=True)
    with completeness_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["complex_id", "bond_lengths_count", "angles_count",
                          "relative_energies_count", "barriers_count", "status"])
        for complex_id, entry in stub.items():
            rv = entry["reference_values"]
            writer.writerow([complex_id, len(rv["bond_lengths"]), len(rv["angles"]),
                              len(rv["relative_energies"]), len(rv["barriers"]), entry["status"]])
    logger.info("Wrote %s", completeness_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
