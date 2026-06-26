"""Build CSV datasets from Quantum ESPRESSO reliability records."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Iterable

from actistruct.parsers.qe import QEReliabilityRecord, parse_qe_output_text

QE_RECORD_FIELDS = [
    "material_id",
    "qe_input_path",
    "qe_output_path",
    "converged",
    "job_done",
    "scf_iterations",
    "final_energy_ry",
    "energy_ev",
    "max_force",
    "pressure_kbar",
    "wall_time",
    "failure_reason",
    "ecutwfc",
    "ecutrho",
    "kpoints",
    "smearing",
    "mixing_beta",
    "pseudo_family",
    "pseudopotentials",
    "calculation_hash",
]

DIAGNOSTIC_FILENAMES = ("espresso.err", "CRASH")


def build_records(
    roots: Iterable[str | Path],
    base_path: str | Path | None = None,
) -> list[QEReliabilityRecord]:
    """Scan roots for QE outputs and return one record per ``espresso.pwo`` file."""

    base = Path(base_path).resolve() if base_path is not None else None
    output_paths: list[Path] = []
    for root in roots:
        root_path = Path(root)
        if root_path.is_file():
            output_paths.append(root_path)
        elif root_path.is_dir():
            output_paths.extend(sorted(root_path.rglob("espresso.pwo")))
    return [_record_from_output(path, base) for path in sorted(set(output_paths))]


def write_records_csv(
    records: Iterable[QEReliabilityRecord],
    output_path: str | Path,
) -> None:
    """Write records to a stable-column CSV file."""

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=QE_RECORD_FIELDS)
        writer.writeheader()
        for record in records:
            writer.writerow(_csv_row(record))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("roots", nargs="+", help="QE output files or directories to scan")
    parser.add_argument(
        "--output",
        default="data/parsed_records/qe_reliability_records.csv",
        help="CSV output path",
    )
    parser.add_argument(
        "--base-path",
        default=".",
        help="Base path used to make input/output paths repo-relative",
    )
    args = parser.parse_args(argv)

    records = build_records(args.roots, base_path=args.base_path)
    write_records_csv(records, args.output)
    print(f"Wrote {len(records)} QE reliability records to {args.output}")
    return 0


def _record_from_output(path: Path, base: Path | None) -> QEReliabilityRecord:
    input_path = path.with_suffix(".pwi")
    input_text = _read_optional(input_path)
    output_text = path.read_text(encoding="utf-8", errors="replace")
    diagnostic_text = "\n".join(
        text for name in DIAGNOSTIC_FILENAMES if (text := _read_optional(path.parent / name))
    )
    combined_output = "\n".join(part for part in (output_text, diagnostic_text) if part)

    return parse_qe_output_text(
        combined_output,
        input_text=input_text,
        material_id=_material_id_from_path(path),
        qe_output_path=_display_path(path, base),
        qe_input_path=_display_path(input_path, base) if input_path.exists() else None,
    )


def _read_optional(path: Path) -> str | None:
    if not path.exists() or path.is_dir():
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    return text if text else None


def _display_path(path: Path, base: Path | None) -> str:
    if base is None:
        return str(path)
    try:
        return str(path.resolve().relative_to(base)).replace("\\", "/")
    except ValueError:
        return str(path)


def _csv_row(record: QEReliabilityRecord) -> dict[str, object]:
    row = record.to_dict()
    row["pseudopotentials"] = json.dumps(
        row["pseudopotentials"],
        sort_keys=True,
        separators=(",", ":"),
    )
    return {field: row.get(field) for field in QE_RECORD_FIELDS}


def _material_id_from_path(path: Path) -> str:
    run_dir = path.parent.name
    parent = path.parent.parent.name
    if parent.startswith("qe_runs_"):
        return parent.removeprefix("qe_runs_")
    if parent == "qe_runs":
        return run_dir.split("_pid", 1)[0].split("_attempt", 1)[0]
    return parent or run_dir


if __name__ == "__main__":
    raise SystemExit(main())

