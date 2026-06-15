from __future__ import annotations

"""Direct QE/PBE grid validation for selected ActiStruct workflows.

This script is intentionally separate from the active-learning runner. It
evaluates fixed uniform grids with the same structure builders and QE settings
used by the generated workflows, then compares the grid minimum with the
active-learning minimum recorded in the final report.

The expensive commands are explicit:

    python analysis/direct_grid_validation.py dry-run
    python analysis/direct_grid_validation.py run --system bulk_mgo
    python analysis/direct_grid_validation.py summarize
"""

import argparse
import csv
import importlib
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
for path in (PROJECT_ROOT / "generated_models", PROJECT_ROOT):
    path_text = str(path)
    if path_text in sys.path:
        sys.path.remove(path_text)
    sys.path.insert(0, path_text)

from qe_active_inverse_common import _compute_energy, _get_reference_energies, _paths


RAW_DIR = PROJECT_ROOT / "analysis" / "outputs" / "raw"
GRID_DIR = RAW_DIR / "direct_grid"
SUMMARY_CSV = RAW_DIR / "direct_grid_validations.csv"
INTERNAL_SUMMARY_CSV = RAW_DIR / "direct_grid_validations_internal.csv"
REPORT_DIR = PROJECT_ROOT / "outputs" / "reports"


@dataclass(frozen=True)
class GridCase:
    """One direct-grid validation case."""

    case_id: str
    module: str
    label: str
    scan_variables: tuple[str, ...]
    points_per_variable: int
    priority: str
    notes: str = ""
    force_spin: bool | None = None

    @property
    def grid_points(self) -> int:
        return self.points_per_variable ** len(self.scan_variables)

    @property
    def dim(self) -> int:
        return len(self.scan_variables)


GRID_CASES: tuple[GridCase, ...] = (
    # Already completed in the earlier validation set; kept for one combined
    # summary when the corresponding CSVs exist.
    GridCase(
        "bulk_cu",
        "generated_models.bulk_cu_generated_qe_active_inverse",
        "Cu FCC",
        ("a",),
        20,
        "completed-baseline",
    ),
    GridCase(
        "mos2",
        "generated_models.mos2_qe_active_inverse",
        "MoS2 monolayer",
        ("a", "layer_half_thickness"),
        7,
        "completed-baseline",
    ),
    # Exploratory validation cases. These are not part of the public pass-only
    # summary unless explicitly selected or included locally.
    GridCase(
        "bulk_licoo2_matched",
        "generated_models.bulk_licoo2_generated_qe_active_inverse",
        "Layered LiCoO2, production settings",
        ("a", "c_over_a"),
        7,
        "critical",
    ),
    GridCase(
        "bulk_fe_spin",
        "generated_models.bulk_fe_bcc_qe_active_inverse",
        "BCC Fe, spin-polarized validation",
        ("a",),
        20,
        "high",
        notes="Overrides spin_polarized=True for magnetic Fe validation.",
        force_spin=True,
    ),
    GridCase(
        "o_on_ni111_height",
        "generated_models.o_on_ni111_qe_active_inverse",
        "O/Ni(111), height projection",
        ("height",),
        20,
        "high",
        notes="Scans height; fixes shift at AL best only when the report is compatible with current bounds, otherwise uses the current-bound midpoint.",
        force_spin=True,
    ),
    GridCase(
        "co_on_pt111_height",
        "generated_models.co_on_pt111_qe_active_inverse",
        "CO/Pt(111), height projection",
        ("height",),
        20,
        "high",
        notes="Scans height; fixes shift at AL best only when the report is compatible with current bounds, otherwise uses the current-bound midpoint.",
    ),
    GridCase(
        "bulk_mgo",
        "generated_models.bulk_mgo_generated_qe_active_inverse",
        "Rocksalt MgO",
        ("a",),
        20,
        "high",
    ),
    GridCase(
        "bulk_si_optional",
        "generated_models.bulk_si_generated_qe_active_inverse",
        "Diamond Si",
        ("a",),
        20,
        "optional",
    ),
)


PUBLIC_CASE_IDS = {
    "bulk_cu",
    "mos2",
    "bulk_mgo",
    "bulk_si_optional",
}


LEGACY_GRID_FILES = {
    "bulk_cu": RAW_DIR / "grid_validation_cu.csv",
    "mos2": RAW_DIR / "grid_validation_mos2.csv",
}


RESULT_KEY_BY_CASE = {
    "bulk_cu": "bulk_cu",
    "mos2": "mos2",
    "bulk_licoo2_matched": "bulk_licoo2",
    "bulk_fe_spin": "bulk_fe_bcc",
    "o_on_ni111_height": "o_on_ni111",
    "co_on_pt111_height": "co_on_pt111",
    "bulk_mgo": "bulk_mgo",
    "bulk_si_optional": "bulk_si",
}


def load_system(case: GridCase):
    module = importlib.import_module(case.module)
    system = module.SYSTEM
    if case.force_spin is not None:
        system.spin_polarized = case.force_spin
    return system


def report_path_for_key(key: str) -> Path:
    direct = REPORT_DIR / f"{key}_report.txt"
    if direct.exists():
        return direct
    matches = sorted(REPORT_DIR.glob(f"{key}*_report.txt"))
    if matches:
        return matches[0]
    raise FileNotFoundError(f"No final report found for key: {key}")


def parse_al_reference(system) -> tuple[dict[str, float], float | None, int | None, bool | None]:
    """Return best params, best energy, QE-call count, and report spin flag."""
    path = report_path_for_key(system.key)
    text = path.read_text(errors="ignore")
    params: dict[str, float] = {}

    match = re.search(r"Best parameters\s*:\s*([^\n]+)", text)
    if match:
        for name, value in re.findall(
            r"([A-Za-z_][A-Za-z0-9_]*)=([-+]?\d+(?:\.\d+)?)",
            match.group(1),
        ):
            params[name] = float(value)

    energy = None
    energy_matches = re.findall(
        r"Best .*?objective:\s*([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)",
        text,
    )
    if energy_matches:
        energy = float(energy_matches[-1])

    calls = None
    calls_match = re.search(r"Total QE calls\s*:\s*(\d+)", text)
    if calls_match:
        calls = int(calls_match.group(1))

    spin = None
    spin_match = re.search(r"spin_polarized:\s*(True|False)", text)
    if spin_match:
        spin = spin_match.group(1) == "True"

    return params, energy, calls, spin


def variable_map(system) -> dict[str, object]:
    return {variable.name: variable for variable in system.variables}


def al_reference_is_compatible(
    system,
    al_params: dict[str, float],
    report_spin: bool | None,
) -> bool:
    """True when parsed AL best parameters are inside current wrapper bounds."""
    if report_spin is not None and bool(system.spin_polarized) != bool(report_spin):
        return False
    if not al_params:
        return False
    for variable in system.variables:
        if variable.name not in al_params:
            return False
        value = al_params[variable.name]
        if not (variable.lo <= value <= variable.hi):
            return False
    return True


def midpoint(variable) -> float:
    return 0.5 * (float(variable.lo) + float(variable.hi))


def grid_points_for_case(case: GridCase, system) -> list[dict[str, float]]:
    variables = variable_map(system)
    al_params, _al_energy, _al_calls, report_spin = parse_al_reference(system)
    compatible_al = al_reference_is_compatible(system, al_params, report_spin)

    fixed: dict[str, float] = {}
    for variable in system.variables:
        if variable.name in case.scan_variables:
            continue
        if compatible_al and variable.name in al_params:
            fixed[variable.name] = al_params[variable.name]
        else:
            fixed[variable.name] = midpoint(variable)

    axes = []
    for name in case.scan_variables:
        variable = variables[name]
        axes.append((name, np.linspace(variable.lo, variable.hi, case.points_per_variable)))

    rows: list[dict[str, float]] = []
    for values in np.array(np.meshgrid(*[axis for _name, axis in axes], indexing="ij")).T.reshape(-1, len(axes)):
        row = dict(fixed)
        for (name, _axis), value in zip(axes, values):
            row[name] = float(value)
        rows.append(row)
    return rows


def params_tuple(system, row: dict[str, float]) -> tuple[float, ...]:
    return tuple(float(row[variable.name]) for variable in system.variables)


def output_csv(case: GridCase) -> Path:
    return GRID_DIR / f"{case.case_id}_grid.csv"


def read_existing_rows(path: Path) -> dict[tuple[tuple[str, float], ...], dict[str, str]]:
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = {}
        for row in reader:
            key_items = []
            for name, value in row.items():
                if name in {"energy", "status"}:
                    continue
                try:
                    key_items.append((name, round(float(value), 10)))
                except (TypeError, ValueError):
                    pass
            rows[tuple(sorted(key_items))] = row
    return rows


def row_key(row: dict[str, float]) -> tuple[tuple[str, float], ...]:
    return tuple(sorted((name, round(float(value), 10)) for name, value in row.items()))


def write_grid_rows(path: Path, variable_names: Iterable[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(variable_names) + ["energy", "status"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def run_case(case: GridCase, max_points: int | None = None) -> None:
    system = load_system(case)
    paths = _paths(system)
    refs = _get_reference_energies(system, paths)
    grid = grid_points_for_case(case, system)
    out = output_csv(case)
    existing = read_existing_rows(out)

    completed_rows: list[dict[str, object]] = []
    for row in grid:
        key = row_key(row)
        if key in existing and existing[key].get("status") == "ok":
            completed_rows.append(existing[key])
            continue
        if max_points is not None and max_points <= 0:
            completed_rows.append({**row, "energy": "", "status": "not_run"})
            continue
        energy = _compute_energy(system, params_tuple(system, row), refs, paths)
        status = "ok" if energy is not None else "failed"
        completed_rows.append({**row, "energy": "" if energy is None else f"{energy:.12f}", "status": status})
        print(f"{case.case_id}: {row} -> {energy} [{status}]")
        if max_points is not None:
            max_points -= 1

    write_grid_rows(out, [variable.name for variable in system.variables], completed_rows)
    print(f"Wrote {out}")


def read_grid_rows(case: GridCase) -> list[dict[str, str]]:
    path = output_csv(case)
    if not path.exists() and case.case_id in LEGACY_GRID_FILES:
        path = LEGACY_GRID_FILES[case.case_id]
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def summarize_case(case: GridCase) -> dict[str, object]:
    system = load_system(case)
    rows = read_grid_rows(case)
    ok_rows = []
    for row in rows:
        status = row.get("status", "ok")
        energy_text = row.get("energy") or row.get("energy_eV_per_atom")
        if status == "ok" and energy_text not in {None, ""}:
            row = dict(row)
            row["energy_float"] = float(energy_text)
            ok_rows.append(row)

    al_params, al_energy, al_calls, report_spin = parse_al_reference(system)
    compatible_al = al_reference_is_compatible(system, al_params, report_spin)
    result: dict[str, object] = {
        "system": case.case_id,
        "label": case.label,
        "dim": case.dim,
        "grid_points": case.grid_points,
        "completed_grid_points": len(ok_rows),
        "AL_calls": "" if al_calls is None else al_calls,
        "grid_min_energy": "",
        "AL_min_energy": "" if al_energy is None or not compatible_al else f"{al_energy:.12f}",
        "delta_eV_per_atom": "",
        "pass_fail": "not_run",
        "grid_min_params": "",
        "AL_min_params": " ".join(f"{k}={v:.6f}" for k, v in al_params.items()) if compatible_al else "",
        "energy_units": system.result_units,
        "notes": case.notes,
    }
    if not ok_rows:
        if not compatible_al:
            result["pass_fail"] = "no_compatible_al_reference"
        return result

    best = min(ok_rows, key=lambda row: row["energy_float"])
    delta = None if al_energy is None or not compatible_al else abs(best["energy_float"] - al_energy)
    result["grid_min_energy"] = f"{best['energy_float']:.12f}"
    result["grid_min_params"] = " ".join(
        f"{variable.name}={float(best[variable.name]):.6f}" for variable in system.variables if variable.name in best
    )
    if delta is not None:
        result["delta_eV_per_atom"] = f"{delta:.12f}"
        result["pass_fail"] = "pass" if delta < 0.001 else "review"
    else:
        result["pass_fail"] = "no_compatible_al_reference"
    if len(ok_rows) < case.grid_points:
        result["pass_fail"] = "incomplete"
    return result


def write_summary(cases: Iterable[GridCase]) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    rows = [summarize_case(case) for case in cases]
    public_rows = [
        row for row in rows
        if row["pass_fail"] == "pass"
        and str(row["completed_grid_points"]) == str(row["grid_points"])
    ]
    fieldnames = [
        "system",
        "label",
        "dim",
        "grid_points",
        "completed_grid_points",
        "AL_calls",
        "grid_min_energy",
        "AL_min_energy",
        "delta_eV_per_atom",
        "pass_fail",
        "grid_min_params",
        "AL_min_params",
        "energy_units",
        "notes",
    ]
    with SUMMARY_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(public_rows)
    with INTERNAL_SUMMARY_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {SUMMARY_CSV}")
    print(f"Wrote local-only {INTERNAL_SUMMARY_CSV}")
    for row in rows:
        print(
            f"{row['system']:24s} {row['completed_grid_points']:>3}/{row['grid_points']:<3} "
            f"{row['pass_fail']:>12s} delta={row['delta_eV_per_atom']}"
        )
    sync_all_results_clean(rows)


def sync_all_results_clean(summary_rows: list[dict[str, object]]) -> None:
    """Add direct-grid validation columns to all_results_clean.csv."""
    path = RAW_DIR / "all_results_clean.csv"
    if not path.exists():
        return

    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])

    extra_fields = [
        "direct_grid_status",
        "direct_grid_points",
        "direct_grid_completed_points",
        "direct_grid_min_energy",
        "direct_grid_min_params",
        "direct_grid_delta_eV_per_atom",
    ]
    for field in extra_fields:
        if field not in fieldnames:
            fieldnames.append(field)

    public_by_key = {
        RESULT_KEY_BY_CASE.get(str(row["system"]), str(row["system"])): row
        for row in summary_rows
        if row["pass_fail"] == "pass"
        and str(row["completed_grid_points"]) == str(row["grid_points"])
    }
    for row in rows:
        summary = public_by_key.get(row.get("key", ""))
        if not summary:
            for field in extra_fields:
                row[field] = ""
            continue
        row["direct_grid_status"] = str(summary["pass_fail"])
        row["direct_grid_points"] = str(summary["grid_points"])
        row["direct_grid_completed_points"] = str(summary["completed_grid_points"])
        row["direct_grid_min_energy"] = str(summary["grid_min_energy"])
        row["direct_grid_min_params"] = str(summary["grid_min_params"])
        row["direct_grid_delta_eV_per_atom"] = str(summary["delta_eV_per_atom"])

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def selected_cases(names: list[str] | None, include_optional: bool) -> list[GridCase]:
    if names:
        by_name = {case.case_id: case for case in GRID_CASES}
        missing = sorted(set(names) - set(by_name))
        if missing:
            raise SystemExit(f"Unknown system(s): {', '.join(missing)}")
        return [by_name[name] for name in names]
    if include_optional:
        return list(GRID_CASES)
    return [case for case in GRID_CASES if case.case_id in PUBLIC_CASE_IDS]


def dry_run(cases: Iterable[GridCase]) -> None:
    print("Direct QE/PBE grid validation plan")
    print("=" * 72)
    for case in cases:
        system = load_system(case)
        grid = grid_points_for_case(case, system)
        al_params, al_energy, al_calls, report_spin = parse_al_reference(system)
        print(f"{case.case_id}: {case.label}")
        print(f"  module        : {case.module}")
        print(f"  scan variables: {', '.join(case.scan_variables)}")
        print(f"  grid points   : {case.grid_points}")
        print(f"  QE settings   : ecut={system.ecutwfc}/{system.ecutrho} Ry, kpts={system.kpts}, "
              f"smearing={system.smearing}, degauss={system.degauss}, spin={system.spin_polarized}")
        print(f"  AL calls      : {al_calls}")
        compatible = al_reference_is_compatible(system, al_params, report_spin)
        print(f"  AL best       : {al_params}, energy={al_energy}")
        print(f"  AL report spin: {report_spin}")
        print(f"  AL compatible : {compatible}")
        print(f"  first point   : {grid[0]}")
        print(f"  last point    : {grid[-1]}")
        if case.notes:
            print(f"  note          : {case.notes}")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("dry-run", "summarize"):
        p = sub.add_parser(name)
        p.add_argument("--system", action="append", dest="systems")
        p.add_argument("--include-optional", action="store_true")

    run = sub.add_parser("run")
    run.add_argument("--system", action="append", dest="systems", required=True)
    run.add_argument("--max-points", type=int, default=None, help="Debug/resume aid; run at most N missing points.")

    args = parser.parse_args()
    cases = selected_cases(getattr(args, "systems", None), getattr(args, "include_optional", False))

    if args.command == "dry-run":
        dry_run(cases)
    elif args.command == "run":
        for case in cases:
            run_case(case, max_points=args.max_points)
        write_summary(cases)
    elif args.command == "summarize":
        write_summary(cases)


if __name__ == "__main__":
    main()
