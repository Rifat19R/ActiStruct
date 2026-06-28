"""Scan the SSSP pseudopotential directory for required elements and write a manifest.

Usage:
    python scripts/02_scan_pseudos.py
    python scripts/02_scan_pseudos.py --dry-run
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import PROJECT_ROOT, load_yaml, setup_logger  # noqa: E402

import yaml

logger = setup_logger("scan_pseudos", "bootstrap.log")

# Filenames not matching <Element>.<...>_psl.<ver>.UPF (the SSSP-efficiency
# naming convention used by Fe/C/H/O in this directory) are flagged: they may
# come from a different pseudopotential family/accuracy tier and should not
# be trusted to match SSSP-efficiency accuracy without manual confirmation.
SSSP_EFFICIENCY_PATTERN_HINT = "_psl."


def find_candidates(pseudo_dir: Path, element: str) -> list[str]:
    prefix = element.lower()
    matches = []
    for f in pseudo_dir.iterdir():
        if not f.is_file():
            continue
        low = f.name.lower()
        if low.startswith(prefix + ".") or low.startswith(prefix + "_"):
            matches.append(f.name)
    return matches


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    project_cfg = load_yaml("configs/project_config.yaml")
    qe_cfg = load_yaml("configs/qe_molecule_settings.yaml")

    pseudo_dir = Path(project_cfg["paths"]["pseudo_dir"])
    required_elements = qe_cfg["required_elements_phase1"]
    default_ecutwfc = qe_cfg["qe"]["ecutwfc_ry"]
    default_ecutrho = qe_cfg["qe"]["ecutrho_ry"]

    if not pseudo_dir.exists():
        logger.error("Pseudopotential directory does not exist: %s", pseudo_dir)
        return 1

    manifest = {
        "pseudo_family": project_cfg["project"]["name"] + "_SSSP_1.3.0_PBE_efficiency",
        "pseudo_dir": str(pseudo_dir),
        "elements": {},
        "status": "ready",
        "missing_elements": [],
        "naming_convention_warnings": [],
    }

    rows = []
    for element in required_elements:
        matches = find_candidates(pseudo_dir, element)
        exists = len(matches) > 0
        chosen = matches[0] if matches else None
        entry = {
            "filename": chosen,
            "path": str(pseudo_dir / chosen) if chosen else None,
            "exists": exists,
            "suggested_ecutwfc_ry": default_ecutwfc if exists else None,
            "suggested_ecutrho_ry": default_ecutrho if exists else None,
        }
        manifest["elements"][element] = entry
        if not exists:
            manifest["missing_elements"].append(element)
            logger.warning("No pseudopotential found for element: %s", element)
        elif chosen and SSSP_EFFICIENCY_PATTERN_HINT not in chosen.lower():
            warning = (
                f"{element}: '{chosen}' does not match the '_psl.' SSSP-efficiency "
                "naming convention seen for Fe/C/H/O in this directory. May be a "
                "different pseudopotential family/accuracy tier - verify before use."
            )
            manifest["naming_convention_warnings"].append(warning)
            logger.warning(warning)
        rows.append({
            "element": element,
            "filename": chosen or "",
            "exists": exists,
            "suggested_ecutwfc_ry": entry["suggested_ecutwfc_ry"] or "",
            "suggested_ecutrho_ry": entry["suggested_ecutrho_ry"] or "",
        })

    if manifest["missing_elements"]:
        manifest["status"] = "not_ready"

    logger.info("Pseudo scan status: %s", manifest["status"])

    if args.dry_run:
        logger.info("Dry run: not writing manifest/report files")
        print(yaml.safe_dump(manifest, sort_keys=False))
        return 0

    manifest_path = PROJECT_ROOT / "configs" / "pseudo_manifest_required.yaml"
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    logger.info("Wrote %s", manifest_path)

    report_path = PROJECT_ROOT / "reports" / "tables" / "pseudo_scan_report.csv"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["element", "filename", "exists",
                                                "suggested_ecutwfc_ry", "suggested_ecutrho_ry"])
        writer.writeheader()
        writer.writerows(rows)
    logger.info("Wrote %s", report_path)

    return 0 if manifest["status"] == "ready" else 2


if __name__ == "__main__":
    sys.exit(main())
