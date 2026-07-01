"""Build QE relax input files, either for the 4 primary systems or for the
audited+selected perturbation candidates from script 05b.

--source primary (default): one relax input per primary system, from
structures/initial_xyz/. --source candidates: one relax input per candidate
marked selected_as_representative=True in data/processed/candidate_audit_v0.csv
(from structures/generated_candidates/). pw.x runs under WSL, so pseudo_dir is
translated to /mnt/<drive>/... form (read-only access is fine on the
9p-mounted Windows drive). outdir instead points to a native WSL/ext4 path
(configs/project_config.yaml qe.workdir_native_root) - a real relax once
crashed creating its .save/ checkpoint directory on the 9p mount after a
fully converged SCF, so write-heavy scratch/checkpoint I/O stays off the
Windows-mounted drive entirely.

Usage:
    python scripts/06_build_qe_inputs.py
    python scripts/06_build_qe_inputs.py --source candidates
    python scripts/06_build_qe_inputs.py --dry-run
"""
from __future__ import annotations

import argparse
import csv
import math
import re
import sys
from pathlib import Path, PureWindowsPath

from ase.data import atomic_masses, atomic_numbers
from ase.io import read

ANGSTROM_TO_BOHR = 1.0 / 0.529177210903

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import PROJECT_ROOT, load_yaml, resolve_path, setup_logger  # noqa: E402

logger = setup_logger("build_qe_inputs", "bootstrap.log")


def windows_to_wsl_path(win_path: str) -> str:
    p = PureWindowsPath(win_path)
    drive = p.drive.rstrip(":").lower()
    rest = "/".join(p.parts[1:])
    return f"/mnt/{drive}/{rest}"


def build_input_file(candidate_id: str, xyz_path: Path, qe_cfg: dict,
                      pseudo_manifest: dict, project_cfg: dict) -> str:
    atoms = read(xyz_path)
    symbols = atoms.get_chemical_symbols()
    positions = atoms.get_positions()

    extent = positions.max(axis=0) - positions.min(axis=0)
    padding = qe_cfg["qe"]["vacuum_padding_angstrom"]
    cell_len = float(extent.max()) + 2 * padding
    centroid = positions.mean(axis=0)
    shifted = positions - centroid + cell_len / 2

    species = sorted(set(symbols))
    for el in species:
        entry = pseudo_manifest["elements"].get(el)
        if entry is None or not entry.get("exists"):
            raise ValueError(f"No pseudopotential available for element {el} (candidate {candidate_id})")

    pseudo_dir_wsl = windows_to_wsl_path(project_cfg["paths"]["pseudo_dir"])
    workdir_native_root = project_cfg["qe"]["workdir_native_root"]
    outdir_wsl = f"{workdir_native_root}/{candidate_id}"

    qe = qe_cfg["qe"]
    lines = []
    lines.append("&CONTROL")
    lines.append(f"  calculation = '{qe['calculation']}'")
    lines.append(f"  prefix = '{candidate_id}'")
    lines.append(f"  pseudo_dir = '{pseudo_dir_wsl}'")
    lines.append(f"  outdir = '{outdir_wsl}'")
    lines.append(f"  forc_conv_thr = {qe['forc_conv_thr']}")
    lines.append(f"  etot_conv_thr = {qe['etot_conv_thr']}")
    lines.append("  disk_io = '" + qe["disk_io"] + "'")
    lines.append("/")
    celldm1_bohr = cell_len * ANGSTROM_TO_BOHR
    lines.append("&SYSTEM")
    lines.append("  ibrav = 1")
    lines.append(f"  celldm(1) = {celldm1_bohr:.8f}")
    lines.append(f"  nat = {len(atoms)}")
    lines.append(f"  ntyp = {len(species)}")
    lines.append(f"  ecutwfc = {qe['ecutwfc_ry']}")
    lines.append(f"  ecutrho = {qe['ecutrho_ry']}")
    lines.append(f"  occupations = '{qe['occupations']}'")
    lines.append(f"  assume_isolated = '{qe['assume_isolated']}'")
    lines.append(f"  nspin = {qe_cfg['closed_shell_phase1']['nspin']}")
    lines.append("/")
    lines.append("&ELECTRONS")
    lines.append(f"  conv_thr = {qe['conv_thr']}")
    lines.append(f"  mixing_beta = {qe['mixing_beta']}")
    lines.append("/")
    if qe["calculation"] in ("relax", "vc-relax"):
        lines.append("&IONS")
        lines.append(f"  trust_radius_min = {qe['ion_trust_radius_min_bohr']}")
        lines.append("/")
    lines.append("ATOMIC_SPECIES")
    for el in species:
        pseudo_file = pseudo_manifest["elements"][el]["filename"]
        mass = atomic_masses[atomic_numbers[el]]
        lines.append(f"  {el}  {mass:.4f}  {pseudo_file}")
    lines.append("ATOMIC_POSITIONS (angstrom)")
    for sym, pos in zip(symbols, shifted):
        lines.append(f"  {sym}  {pos[0]:.8f}  {pos[1]:.8f}  {pos[2]:.8f}")
    if qe.get("gamma_only"):
        lines.append("K_POINTS gamma")
    else:
        kx, ky, kz = qe["kpoints"]
        lines.append("K_POINTS automatic")
        lines.append(f"  {kx} {ky} {kz}  0 0 0")
    lines.append("")
    return "\n".join(lines)


def validate_generated_input(in_path: Path, pseudo_dir: Path, overlap_threshold_angstrom: float = 0.5) -> list[str]:
    """Static, pre-execution sanity check on an already-written .in file -
    catches generation bugs before any CPU time is spent on pw.x."""
    pseudo_dir = resolve_path(str(pseudo_dir))
    text = in_path.read_text(encoding="utf-8")
    issues = []

    if "ibrav = 1" not in text:
        issues.append("missing or wrong ibrav (expected 'ibrav = 1')")
    if "celldm(1)" not in text:
        issues.append("missing celldm(1)")
    if "calculation = 'relax'" in text and "trust_radius_min" not in text:
        issues.append("relax calculation missing trust_radius_min in &IONS")
    if "outdir = '/mnt/" in text:
        issues.append("outdir points at the 9p-mounted drive (/mnt/...) instead of native WSL filesystem")

    species_block = re.search(r"ATOMIC_SPECIES\n(.*?)\nATOMIC_POSITIONS", text, re.DOTALL)
    if species_block:
        for line in species_block.group(1).strip().splitlines():
            parts = line.split()
            if len(parts) >= 3:
                pseudo_filename = parts[2]
                if not (pseudo_dir / pseudo_filename).exists():
                    issues.append(f"pseudopotential file not found on disk: {pseudo_filename}")

    positions_block = re.search(r"ATOMIC_POSITIONS \(angstrom\)\n(.*?)\n(?:K_POINTS|\Z)", text, re.DOTALL)
    if positions_block:
        atoms = []
        for line in positions_block.group(1).strip().splitlines():
            parts = line.split()
            if len(parts) == 4:
                atoms.append((parts[0], float(parts[1]), float(parts[2]), float(parts[3])))
        for i in range(len(atoms)):
            for j in range(i + 1, len(atoms)):
                d = math.sqrt(sum((atoms[i][k] - atoms[j][k]) ** 2 for k in (1, 2, 3)))
                if d < overlap_threshold_angstrom:
                    issues.append(f"atom overlap in ATOMIC_POSITIONS: atoms {i},{j} = {d:.4f} A")
    else:
        issues.append("could not locate ATOMIC_POSITIONS block")

    return issues


def load_primary_targets(project_cfg: dict) -> list[tuple[str, str, Path]]:
    targets = []
    for complex_id in project_cfg["systems"]["primary"]:
        xyz_path = PROJECT_ROOT / "structures" / "initial_xyz" / f"{complex_id}_initial.xyz"
        targets.append((f"{complex_id}_initial", complex_id, xyz_path))
    return targets


def load_selected_candidate_targets() -> list[tuple[str, str, Path]]:
    audit_path = PROJECT_ROOT / "data" / "processed" / "candidate_audit_v0.csv"
    if not audit_path.exists():
        raise FileNotFoundError(
            f"{audit_path} not found - run scripts/05b_audit_perturbation_candidates.py first")
    targets = []
    with audit_path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["selected_as_representative"] == "True":
                xyz_path = PROJECT_ROOT / "structures" / "generated_candidates" / f"{row['candidate_id']}.xyz"
                targets.append((row["candidate_id"], row["system_id"], xyz_path))
    return targets


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--calculation", choices=["relax", "scf"], default="relax",
                         help="Which input type to build (default: relax)")
    parser.add_argument("--source", choices=["primary", "candidates"], default="primary",
                         help="'primary' = the 4 baseline systems (default); "
                              "'candidates' = the audited+selected perturbation candidates from script 05b")
    args = parser.parse_args()

    project_cfg = load_yaml("configs/project_config.yaml")
    qe_cfg = load_yaml("configs/qe_molecule_settings.yaml")
    qe_cfg["qe"]["calculation"] = args.calculation

    manifest_path = PROJECT_ROOT / "configs" / "pseudo_manifest_required.yaml"
    if not manifest_path.exists():
        logger.error("Pseudo manifest not found - run scripts/02_scan_pseudos.py first")
        return 1
    pseudo_manifest = load_yaml("configs/pseudo_manifest_required.yaml")
    if pseudo_manifest["status"] != "ready":
        logger.error("Pseudo manifest status is '%s', not 'ready' - missing: %s",
                      pseudo_manifest["status"], pseudo_manifest["missing_elements"])
        return 1

    if args.source == "primary":
        targets = load_primary_targets(project_cfg)
    else:
        try:
            targets = load_selected_candidate_targets()
        except FileNotFoundError as exc:
            logger.error(str(exc))
            return 1
        if not targets:
            logger.error("No candidates marked selected_as_representative=True - nothing to build")
            return 1

    run_rows = []
    for candidate_id, system_id, xyz_path in targets:
        if not xyz_path.exists():
            logger.error("Missing structure for %s: %s", candidate_id, xyz_path)
            return 1

        try:
            content = build_input_file(candidate_id, xyz_path, qe_cfg, pseudo_manifest, project_cfg)
        except ValueError as exc:
            logger.error("Failed to build input for %s: %s", candidate_id, exc)
            return 1

        out_path = PROJECT_ROOT / "qe" / "inputs" / args.calculation / f"{candidate_id}.in"
        run_rows.append({
            "candidate_id": candidate_id,
            "system_id": system_id,
            "calculation": args.calculation,
            "input_path": str(out_path),
            "source_structure": str(xyz_path),
            "status": "generated",
        })

        if args.dry_run:
            logger.info("[dry-run] would write %s", out_path)
            continue
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")
        logger.info("Wrote %s", out_path)

    if args.dry_run:
        logger.info("Dry run: not writing run manifest")
        return 0

    manifest_filename = "run_manifest_v0.csv" if args.source == "primary" else "run_manifest_candidates_v0.csv"
    manifest_csv = PROJECT_ROOT / "qe" / manifest_filename
    with manifest_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(run_rows[0].keys()))
        writer.writeheader()
        writer.writerows(run_rows)
    logger.info("Wrote %s", manifest_csv)

    pseudo_dir = Path(project_cfg["paths"]["pseudo_dir"])
    any_invalid = False
    for row in run_rows:
        issues = validate_generated_input(Path(row["input_path"]), pseudo_dir)
        if issues:
            any_invalid = True
            logger.error("VALIDATION FAILED for %s: %s", row["candidate_id"], "; ".join(issues))
        else:
            logger.info("Validated %s: OK", row["candidate_id"])
    if any_invalid:
        logger.error("One or more generated inputs failed static validation - see errors above")
        return 1

    if args.source == "candidates":
        report_path = PROJECT_ROOT / "reports" / "pre_run_report_candidates_v0.md"
        report_path.write_text(build_pre_run_report(run_rows, qe_cfg), encoding="utf-8")
        logger.info("Wrote %s", report_path)

    return 0


def build_pre_run_report(run_rows: list[dict], qe_cfg: dict) -> str:
    audit_path = PROJECT_ROOT / "data" / "processed" / "candidate_audit_v0.csv"
    with audit_path.open(encoding="utf-8") as f:
        audit_by_id = {row["candidate_id"]: row for row in csv.DictReader(f)}

    qe = qe_cfg["qe"]
    lines = []
    lines.append("# Pre-Run Report - Perturbation Candidate QE Campaign v0")
    lines.append("")
    lines.append("Generated by `scripts/06_build_qe_inputs.py --source candidates` "
                  "before any of these jobs were executed.")
    lines.append("")
    lines.append("## QE settings (shared by all candidates below)")
    lines.append("")
    lines.append(f"- Functional: {qe['functional']}, ecutwfc={qe['ecutwfc_ry']} Ry, "
                  f"ecutrho={qe['ecutrho_ry']} Ry")
    lines.append(f"- `ibrav=1` (cubic), vacuum padding {qe['vacuum_padding_angstrom']} A/side, "
                  f"`assume_isolated='{qe['assume_isolated']}'`")
    lines.append(f"- `conv_thr={qe['conv_thr']}`, `forc_conv_thr={qe['forc_conv_thr']}`, "
                  f"`etot_conv_thr={qe['etot_conv_thr']}`, `trust_radius_min={qe['ion_trust_radius_min_bohr']}` bohr")
    lines.append(f"- `outdir` on native WSL ext4 (`{PROJECT_ROOT.name}` repo stays on the 9p-mounted "
                  "drive for inputs/outputs only, never for QE scratch/checkpoint I/O)")
    lines.append("")
    lines.append("## Candidates queued (all passed the script 05b chemical-reasonableness audit "
                  "and the static input validation above)")
    lines.append("")
    lines.append("| Candidate | System | Family | Direction | Magnitude | Expected effect | Selection reason |")
    lines.append("|---|---|---|---|---|---|---|")
    for row in run_rows:
        a = audit_by_id.get(row["candidate_id"], {})
        lines.append(f"| {row['candidate_id']} | {row['system_id']} | {a.get('perturbation_family', 'n/a')} | "
                      f"{a.get('perturbation_direction', 'n/a')} | {a.get('magnitude', 'n/a')} | "
                      f"{a.get('expected_physical_effect', 'n/a')} | {a.get('selection_reason', 'n/a')} |")
    lines.append("")
    lines.append(f"Total: {len(run_rows)} candidates, "
                  f"{len({r['system_id'] for r in run_rows})} systems.")
    lines.append("")
    lines.append("## Execution notes")
    lines.append("")
    lines.append("- Run sequentially, never in parallel - cr_co6 candidates alone need ~14GB/process "
                  "against this machine's 16GB WSL ceiling (see docs/PHASE1_SUMMARY.md for the OOM "
                  "history that makes this a hard constraint, not a suggestion).")
    lines.append("- Exit code 0 does NOT mean converged - QE prints `JOB DONE` even on a failed BFGS "
                  "run (this exact failure mode hit cr_co6 in the first campaign). Always grep each "
                  "output for `bfgs converged` vs `bfgs failed` before trusting a result.")
    lines.append("- Use `scripts/06b_run_qe_candidates_batch.sh` (idempotent - safe to re-run after a "
                  "partial failure, skips anything already converged).")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
