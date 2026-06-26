from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MAIN = ROOT / "data" / "parsed_records" / "qe_reliability_records.csv"
DEFAULT_QUARANTINE = ROOT / "data" / "parsed_records" / "qe_invalid_geometry_records.csv"
DEFAULT_REPORT = ROOT / "reports" / "qe_reliability_dataset_summary.md"


def read_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def summarize_rows(rows: list[dict[str, str]]) -> dict[str, object]:
    total = len(rows)
    converged = sum(_is_true(row.get("converged")) for row in rows)
    job_done = sum(_is_true(row.get("job_done")) for row in rows)
    failure_reasons = Counter(row.get("failure_reason") or "success" for row in rows)
    materials = Counter(row.get("material_id") or "unknown" for row in rows)
    pseudo_families = Counter(row.get("pseudo_family") or "unknown" for row in rows)
    smearing = Counter(row.get("smearing") or "unknown" for row in rows)
    ecutwfc = Counter(_bucket_numeric(row.get("ecutwfc")) for row in rows)
    kpoints = Counter(row.get("kpoints") or "unknown" for row in rows)
    missing = {
        field: sum(1 for row in rows if row.get(field) in ("", None))
        for field in rows[0]
    } if rows else {}
    element_counts = Counter()
    for row in rows:
        element_counts.update(_pseudo_elements(row.get("pseudopotentials", "")))

    return {
        "total": total,
        "converged": converged,
        "not_converged": total - converged,
        "job_done": job_done,
        "job_not_done": total - job_done,
        "failure_reasons": failure_reasons,
        "materials": materials,
        "pseudo_families": pseudo_families,
        "smearing": smearing,
        "ecutwfc": ecutwfc,
        "kpoints": kpoints,
        "missing": missing,
        "elements": element_counts,
    }


def render_report(
    main_summary: dict[str, object],
    quarantine_summary: dict[str, object],
    main_path: str | Path,
    quarantine_path: str | Path,
) -> str:
    main_total = int(main_summary["total"])
    quarantine_total = int(quarantine_summary["total"])
    main_converged = int(main_summary["converged"])
    main_failed = int(main_summary["not_converged"])
    lines = [
        "# QE Reliability Dataset Summary",
        "",
        "## Files",
        "",
        f"- Main dataset: `{_repo_path(main_path)}`",
        f"- Invalid-geometry quarantine: `{_repo_path(quarantine_path)}`",
        "",
        "## Record Counts",
        "",
        f"- Main records: **{main_total}**",
        f"- Converged records: **{main_converged}**",
        f"- Non-converged, failed, or incomplete records: **{main_failed}**",
        f"- Invalid-geometry quarantine records: **{quarantine_total}**",
        f"- Total parsed local records: **{main_total + quarantine_total}**",
        "",
        "## Main Failure Labels",
        "",
        _markdown_counter(main_summary["failure_reasons"]),
        "",
        "## Top Materials In Main Dataset",
        "",
        _markdown_counter(main_summary["materials"], limit=20),
        "",
        "## Pseudopotential Families",
        "",
        _markdown_counter(main_summary["pseudo_families"]),
        "",
        "## Element Coverage",
        "",
        _markdown_counter(main_summary["elements"], limit=20),
        "",
        "## Smearing Settings",
        "",
        _markdown_counter(main_summary["smearing"]),
        "",
        "## ecutwfc Values",
        "",
        _markdown_counter(main_summary["ecutwfc"]),
        "",
        "## K-Point Settings",
        "",
        _markdown_counter(main_summary["kpoints"], limit=20),
        "",
        "## Missing Metadata In Main Dataset",
        "",
        _markdown_counter(main_summary["missing"], limit=30),
        "",
        "## Scientific Interpretation",
        "",
        "This dataset is strong enough for reliability parsing, descriptive "
        "statistics, failure-mode accounting, and an initial baseline classifier "
        "for calculation completion/convergence. It is not yet strong enough for "
        "a general DFT reliability claim because the records are local, "
        "scratch-heavy, and unevenly distributed across materials.",
        "",
        "The quarantine file separates invalid structure-generation failures from "
        "electronic-structure workflow failures. Those records are useful for "
        "builder validation, but they should not be mixed into a model that is "
        "intended to learn SCF or QE reliability.",
        "",
        "## Next Data Scaling Step",
        "",
        "The next scalable source should be public calculation metadata, starting "
        "with a lightweight NOMAD connector. Public metadata must be mapped into "
        "ActiStruct fields without pretending that VASP/other-code records are "
        "Quantum ESPRESSO `.pwo` records.",
        "",
    ]
    return "\n".join(lines)


def write_report(
    main_path: str | Path = DEFAULT_MAIN,
    quarantine_path: str | Path = DEFAULT_QUARANTINE,
    report_path: str | Path = DEFAULT_REPORT,
) -> None:
    main_rows = read_rows(main_path)
    quarantine_rows = read_rows(quarantine_path)
    report = render_report(
        summarize_rows(main_rows),
        summarize_rows(quarantine_rows),
        main_path,
        quarantine_path,
    )
    out = Path(report_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--main", default=str(DEFAULT_MAIN))
    parser.add_argument("--quarantine", default=str(DEFAULT_QUARANTINE))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    args = parser.parse_args(argv)
    write_report(args.main, args.quarantine, args.report)
    print(f"Wrote {args.report}")
    return 0


def _is_true(value: str | None) -> bool:
    return str(value).lower() == "true"


def _bucket_numeric(value: str | None) -> str:
    if value in ("", None):
        return "unknown"
    try:
        number = float(value)
    except ValueError:
        return "unknown"
    return f"{number:g}"


def _pseudo_elements(raw: str) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return sorted(str(key) for key in data)


def _markdown_counter(counter: object, limit: int | None = None) -> str:
    items = counter.items() if hasattr(counter, "items") else []
    sorted_items = sorted(items, key=lambda item: (-int(item[1]), str(item[0])))
    if limit is not None:
        sorted_items = sorted_items[:limit]
    if not sorted_items:
        return "_None._"
    lines = ["| Value | Count |", "| --- | ---: |"]
    for value, count in sorted_items:
        label = str(value) if str(value) else "blank"
        lines.append(f"| `{label}` | {int(count)} |")
    return "\n".join(lines)


def _repo_path(path: str | Path) -> str:
    item = Path(path)
    try:
        return str(item.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(item)


if __name__ == "__main__":
    raise SystemExit(main())

