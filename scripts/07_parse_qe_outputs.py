"""Parse Quantum ESPRESSO relax outputs into a structured, traceable dataset.

Recursively scans a directory (default runs/initial_relax/) for files
containing a QE "Program PWSCF" banner, and extracts convergence/reliability
metadata plus final geometry for each. Never fabricates values: anything not
found in the output text is stored as null/None, and every record is
traceable back to its own input/output/error file paths.

Usage:
    python scripts/07_parse_qe_outputs.py
    python scripts/07_parse_qe_outputs.py --runs-dir runs/initial_relax
    python scripts/07_parse_qe_outputs.py --dry-run
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import PROJECT_ROOT, setup_logger  # noqa: E402

logger = setup_logger("parse_qe_outputs", "parser.log")

PARSER_VERSION = "0.1.0"
RY_TO_EV = 13.605693122994  # CODATA, matches ase.units.Ry

PWSCF_BANNER_RE = re.compile(r"Program PWSCF")
INPUT_FILE_RE = re.compile(r"Reading input from\s+(\S+)")
FINAL_ENERGY_BFGS_RE = re.compile(r"Final energy\s*=\s*([-\d.]+)\s*Ry")
FINAL_ENERGY_SCF_RE = re.compile(r"!\s*total energy\s*=\s*([-\d.]+)\s*Ry")
BFGS_CONVERGED_RE = re.compile(
    r"bfgs converged in\s+(\d+)\s+scf cycles and\s+(\d+)\s+bfgs steps")
BFGS_FAILED_RE = re.compile(
    r"bfgs failed after\s+(\d+)\s+scf cycles and\s+(\d+)\s+bfgs steps")
TOTAL_FORCE_RE = re.compile(r"Total force\s*=\s*([-\d.]+)\s*Total SCF correction")
ITERATION_RE = re.compile(r"^\s*iteration\s*#", re.MULTILINE)
WALLTIME_RE = re.compile(r"PWSCF\s*:\s*(.+?)CPU\s+(.+?)WALL")
ERROR_BANNER_RE = re.compile(r"%{10,}\n(.*?)%{10,}", re.DOTALL)
MESSAGE_FROM_ROUTINE_RE = re.compile(r"Message from routine\s+(\S+):\s*\n\s*(.+)")
DISCOURAGED_RE = re.compile(r"^.*DISCOURAGED.*$", re.MULTILINE)
NEGATIVE_RHO_RE = re.compile(r"negative rho \(up, down\):\s*([\d.eE+-]+)\s+([\d.eE+-]+)")


def _trace_path(path: Path) -> str:
    """Store paths reproducibly across Windows and WSL when they are in-repo."""
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path)


def _time_str_to_seconds(s: str) -> Optional[float]:
    s = s.strip()
    if not s:
        return None
    m = re.match(r"(?:(\d+)h)?\s*(?:(\d+)m)?\s*(?:([\d.]+)s)?", s)
    if not m or not any(m.groups()):
        return None
    h, mn, sec = m.groups()
    total = 0.0
    if h:
        total += int(h) * 3600
    if mn:
        total += int(mn) * 60
    if sec:
        total += float(sec)
    return total if total > 0 or s == "0s" else None


def find_qe_outputs(runs_dir: Path) -> list[Path]:
    found = []
    if not runs_dir.exists():
        return found
    for path in sorted(runs_dir.rglob("*")):
        if not path.is_file():
            continue
        try:
            head = path.read_text(encoding="utf-8", errors="ignore")[:2000]
        except (UnicodeDecodeError, OSError):
            continue
        if PWSCF_BANNER_RE.search(head):
            found.append(path)
    return found


def find_companion_err(out_path: Path) -> Optional[Path]:
    candidate = out_path.with_suffix(".err")
    if candidate.exists():
        return candidate
    candidate2 = out_path.parent / (out_path.stem + ".err")
    if candidate2.exists():
        return candidate2
    return None


def extract_failures_from_err(err_text: str) -> list[str]:
    failures = []
    if not err_text or not err_text.strip():
        return failures
    if "MPI_ABORT" in err_text:
        failures.append("mpi_abort: stderr reports MPI_ABORT was invoked")
    if "mkdir fail" in err_text:
        failures.append("mkdir_fail: stderr reports a failed mkdir")
    if not failures:
        snippet = err_text.strip().splitlines()[0][:200]
        failures.append(f"stderr_not_empty: {snippet}")
    return failures


def extract_error_banners(out_text: str) -> list[str]:
    banners = []
    for match in ERROR_BANNER_RE.finditer(out_text):
        lines = [ln.strip() for ln in match.group(1).strip().splitlines() if ln.strip()]
        if lines:
            banners.append(" ".join(lines))
    return banners


def extract_warnings(out_text: str) -> list[str]:
    warnings = []
    neg_rho_matches = NEGATIVE_RHO_RE.findall(out_text)
    if neg_rho_matches:
        max_up = max(float(m[0]) for m in neg_rho_matches)
        warnings.append(
            f"negative_rho observed ({len(neg_rho_matches)} occurrences, max up={max_up:.4g})")
    if DISCOURAGED_RE.search(out_text):
        warnings.append("QE emitted a DISCOURAGED setup warning (see output for detail)")
    for match in MESSAGE_FROM_ROUTINE_RE.finditer(out_text):
        routine, msg = match.group(1), match.group(2).strip()
        if "failed" not in msg and "stopping" not in msg.lower():
            warnings.append(f"message_from_routine[{routine}]: {msg}")
    return warnings


def parse_geometry(out_path: Path) -> tuple[Optional[list], Optional[list]]:
    try:
        from ase.io import read
    except ImportError:
        return None, None
    try:
        atoms = read(out_path, format="espresso-out", index=-1)
    except Exception as exc:  # pragma: no cover - defensive, ASE failure modes vary
        logger.warning("ASE could not parse geometry from %s: %s", out_path, exc)
        return None, None
    lattice = [[round(float(v), 8) for v in row] for row in atoms.get_cell()[:]]
    positions = [
        {"symbol": sym, "x": round(float(p[0]), 8), "y": round(float(p[1]), 8), "z": round(float(p[2]), 8)}
        for sym, p in zip(atoms.get_chemical_symbols(), atoms.get_positions())
    ]
    return lattice, positions


def parse_qe_output(out_path: Path) -> dict:
    out_text = out_path.read_text(encoding="utf-8", errors="ignore")
    err_path = find_companion_err(out_path)
    err_text = err_path.read_text(encoding="utf-8", errors="ignore") if err_path else ""

    system_id = out_path.parent.name

    input_match = INPUT_FILE_RE.search(out_text)
    input_filename = input_match.group(1) if input_match else None

    job_done = "JOB DONE" in out_text

    bfgs_converged = BFGS_CONVERGED_RE.search(out_text)
    bfgs_failed = BFGS_FAILED_RE.search(out_text)

    ionic_steps = None
    if bfgs_converged:
        ionic_steps = int(bfgs_converged.group(2))
        convergence_status = "converged"
    elif bfgs_failed:
        ionic_steps = int(bfgs_failed.group(2))
        convergence_status = "not_converged"
    elif job_done and "convergence has been achieved" in out_text:
        convergence_status = "converged"  # plain SCF (non-relax) run
    else:
        convergence_status = "unknown"

    final_energy_ry = None
    bfgs_energy_match = FINAL_ENERGY_BFGS_RE.search(out_text)
    if bfgs_energy_match:
        final_energy_ry = float(bfgs_energy_match.group(1))
    else:
        scf_energy_matches = FINAL_ENERGY_SCF_RE.findall(out_text)
        if scf_energy_matches:
            final_energy_ry = float(scf_energy_matches[-1])
    final_energy_ev = final_energy_ry * RY_TO_EV if final_energy_ry is not None else None

    force_matches = TOTAL_FORCE_RE.findall(out_text)
    max_force_ry_per_bohr = float(force_matches[-1]) if force_matches else None

    scf_iterations_total = len(ITERATION_RE.findall(out_text))

    walltime_match = WALLTIME_RE.search(out_text)
    wall_time_sec = _time_str_to_seconds(walltime_match.group(2)) if walltime_match else None

    final_lattice, final_positions = (None, None)
    if job_done:
        final_lattice, final_positions = parse_geometry(out_path)

    warnings = extract_warnings(out_text)
    failures = extract_error_banners(out_text) + extract_failures_from_err(err_text)
    if bfgs_failed:
        failures.append(
            f"bfgs_failed: {bfgs_failed.group(1)} scf cycles, {bfgs_failed.group(2)} bfgs steps, convergence not achieved")
    if not job_done and not failures:
        failures.append("job_did_not_complete: no JOB DONE marker and no recognized error banner")

    return {
        "parser_version": PARSER_VERSION,
        "system_id": system_id,
        "input_filename": input_filename,
        "output_filename": _trace_path(out_path),
        "error_filename": _trace_path(err_path) if err_path else None,
        "job_done": job_done,
        "convergence_status": convergence_status,
        "final_energy_ry": final_energy_ry,
        "final_energy_ev": final_energy_ev,
        "ionic_steps": ionic_steps,
        "scf_iterations_total": scf_iterations_total,
        "max_force_ry_per_bohr": max_force_ry_per_bohr,
        "wall_time_sec": wall_time_sec,
        "final_lattice_angstrom": final_lattice,
        "final_positions_angstrom": final_positions,
        "warnings": warnings,
        "failures": failures,
    }


def build_summary_report(records: list[dict], runs_dir: Path) -> str:
    n_total = len(records)
    converged = [r for r in records if r["convergence_status"] == "converged"]
    not_converged = [r for r in records if r["convergence_status"] == "not_converged"]
    unknown = [r for r in records if r["convergence_status"] == "unknown"]
    job_done_count = sum(1 for r in records if r["job_done"])

    energies = [r["final_energy_ry"] for r in records if r["final_energy_ry"] is not None]
    energy_range = (min(energies), max(energies)) if energies else None

    all_warnings = [f"[{r['system_id']}] {w}" for r in records for w in r["warnings"]]
    all_failures = [f"[{r['system_id']}] {f}" for r in records for f in r["failures"]]

    lines = []
    lines.append("# QE Output Parser Summary - v0.1")
    lines.append("")
    lines.append(f"Generated by `scripts/07_parse_qe_outputs.py` (parser_version {PARSER_VERSION}) "
                  f"scanning `{_trace_path(runs_dir)}`.")
    lines.append("")
    lines.append("## Job counts")
    lines.append("")
    lines.append(f"- Total QE outputs found: {n_total}")
    lines.append(f"- `JOB DONE` present: {job_done_count}")
    lines.append(f"- Converged: {len(converged)} ({', '.join(r['system_id'] for r in converged) or 'none'})")
    lines.append(f"- Not converged: {len(not_converged)} ({', '.join(r['system_id'] for r in not_converged) or 'none'})")
    lines.append(f"- Unknown/unparseable convergence: {len(unknown)} ({', '.join(r['system_id'] for r in unknown) or 'none'})")
    lines.append("")
    lines.append("## Energy range")
    lines.append("")
    if energy_range:
        lines.append(f"- Min: {energy_range[0]:.6f} Ry, Max: {energy_range[1]:.6f} Ry, "
                      f"across {len(energies)} job(s) with a parsed final energy.")
    else:
        lines.append("- No job had a parseable final energy.")
    lines.append("")
    lines.append("## Per-job detail")
    lines.append("")
    lines.append("| system_id | convergence | job_done | final_energy_ry | ionic_steps | scf_iterations_total | max_force_ry_per_bohr | wall_time_sec |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for r in records:
        lines.append(
            f"| {r['system_id']} | {r['convergence_status']} | {r['job_done']} | "
            f"{r['final_energy_ry']} | {r['ionic_steps']} | {r['scf_iterations_total']} | "
            f"{r['max_force_ry_per_bohr']} | {r['wall_time_sec']} |"
        )
    lines.append("")
    lines.append("## Parser warnings (collected from job outputs)")
    lines.append("")
    if all_warnings:
        for w in all_warnings:
            lines.append(f"- {w}")
    else:
        lines.append("- None.")
    lines.append("")
    lines.append("## Parser failures (collected from job outputs)")
    lines.append("")
    if all_failures:
        for f in all_failures:
            lines.append(f"- {f}")
    else:
        lines.append("- None.")
    lines.append("")
    lines.append("## Parser assumptions")
    lines.append("")
    lines.append("- A file is treated as a QE output if it contains a `Program PWSCF` banner "
                  "in its first ~2000 characters (content-based detection, not filename-based).")
    lines.append("- `final_energy_ry` prefers the BFGS `Final energy` summary line (printed once, "
                  "highest precision); falls back to the last `!  total energy` SCF line only when "
                  "no BFGS summary exists (e.g. failed/incomplete relax, or a plain SCF run).")
    lines.append("- `convergence_status` is `converged` only if QE itself printed `bfgs converged`, "
                  "or (for non-relax runs) printed `convergence has been achieved` with `JOB DONE`. "
                  "`not_converged` requires QE's own `bfgs failed` message. Anything else is `unknown` "
                  "- the parser never infers convergence from energy/force values alone.")
    lines.append("- `scf_iterations_total` is the count of all `iteration #` lines in the file "
                  "(total electronic iterations across every ionic step), not the `N scf cycles` "
                  "count QE prints in its own BFGS summary (which is closer to the ionic step count).")
    lines.append("- `max_force_ry_per_bohr` is the last `Total force` value printed before the job "
                  "ended, in QE's native Ry/au units - not converted, not re-derived.")
    lines.append("- Final geometry (`final_lattice_angstrom`, `final_positions_angstrom`) is parsed "
                  "via ASE's `espresso-out` reader, and only attempted when `JOB DONE` is present; "
                  "both are left `null` otherwise rather than guessing from a partial trajectory.")
    lines.append("- Every numeric/text field not found in the source text is stored as `null` - "
                  "nothing in this report or dataset is inferred, estimated, or fabricated.")
    lines.append("")
    return "\n".join(lines)


def to_csv_row(record: dict) -> dict:
    row = dict(record)
    for key in ("final_lattice_angstrom", "final_positions_angstrom", "warnings", "failures"):
        row[key] = json.dumps(row[key]) if row[key] is not None else ""
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-dir", default="runs/initial_relax",
                         help="Directory to recursively scan for QE outputs (default: runs/initial_relax)")
    parser.add_argument("--output-prefix", default="initial_relax_parsed_v0.1",
                         help="Stem for output files under data/processed/ "
                              "(default: initial_relax_parsed_v0.1 → "
                              "initial_relax_parsed_v0.1.csv/.json). "
                              "Use a different prefix to avoid overwriting Phase 1 output "
                              "when re-running for Phase 2B candidates.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    runs_dir = PROJECT_ROOT / args.runs_dir
    outputs = find_qe_outputs(runs_dir)
    logger.info("Found %d QE output file(s) under %s", len(outputs), runs_dir)

    if not outputs:
        logger.warning("No QE outputs found - nothing to parse")
        return 0

    records = []
    for out_path in outputs:
        logger.info("Parsing %s", out_path)
        record = parse_qe_output(out_path)
        records.append(record)
        logger.info("  system=%s convergence=%s job_done=%s energy_ry=%s",
                    record["system_id"], record["convergence_status"],
                    record["job_done"], record["final_energy_ry"])

    if args.dry_run:
        print(json.dumps(records, indent=2))
        logger.info("Dry run: not writing dataset files")
        return 0

    csv_path = PROJECT_ROOT / "data" / "processed" / f"{args.output_prefix}.csv"
    json_path = PROJECT_ROOT / "data" / "processed" / f"{args.output_prefix}.json"
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(to_csv_row(records[0]).keys()))
        writer.writeheader()
        for record in records:
            writer.writerow(to_csv_row(record))
    logger.info("Wrote %s", csv_path)

    json_path.write_text(json.dumps(records, indent=2), encoding="utf-8")
    logger.info("Wrote %s", json_path)

    report_path = PROJECT_ROOT / "reports" / "parser_summary_v0.1.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(build_summary_report(records, runs_dir), encoding="utf-8")
    logger.info("Wrote %s", report_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
