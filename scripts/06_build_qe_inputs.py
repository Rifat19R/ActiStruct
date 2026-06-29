"""Build QE relax input files for the four primary TMC initial structures.

Builds one relax candidate per primary system directly from
structures/initial_xyz/ (perturbation candidates from script 05 are deferred
to phase 2, after a first relax establishes a baseline). pw.x runs under WSL,
so pseudo_dir is translated to /mnt/<drive>/... form (read-only access is
fine on the 9p-mounted Windows drive). outdir instead points to a native
WSL/ext4 path (configs/project_config.yaml qe.workdir_native_root) - a real
relax once crashed creating its .save/ checkpoint directory on the 9p mount
after a fully converged SCF, so write-heavy scratch/checkpoint I/O stays off
the Windows-mounted drive entirely.

Usage:
    python scripts/06_build_qe_inputs.py
    python scripts/06_build_qe_inputs.py --dry-run
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path, PureWindowsPath

from ase.data import atomic_masses, atomic_numbers
from ase.io import read

ANGSTROM_TO_BOHR = 1.0 / 0.529177210903

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import PROJECT_ROOT, load_yaml, setup_logger  # noqa: E402

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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--calculation", choices=["relax", "scf"], default="relax",
                         help="Which input type to build (default: relax)")
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

    primary_systems = project_cfg["systems"]["primary"]
    run_rows = []
    for complex_id in primary_systems:
        xyz_path = PROJECT_ROOT / "structures" / "initial_xyz" / f"{complex_id}_initial.xyz"
        if not xyz_path.exists():
            logger.error("Missing initial structure for %s: %s - run scripts/04_build_initial_structures.py first",
                         complex_id, xyz_path)
            return 1

        candidate_id = f"{complex_id}_initial"
        try:
            content = build_input_file(candidate_id, xyz_path, qe_cfg, pseudo_manifest, project_cfg)
        except ValueError as exc:
            logger.error("Failed to build input for %s: %s", candidate_id, exc)
            return 1

        out_path = PROJECT_ROOT / "qe" / "inputs" / args.calculation / f"{candidate_id}.in"
        run_rows.append({
            "candidate_id": candidate_id,
            "complex_id": complex_id,
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

    manifest_csv = PROJECT_ROOT / "qe" / "run_manifest_v0.csv"
    with manifest_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(run_rows[0].keys()))
        writer.writeheader()
        writer.writerows(run_rows)
    logger.info("Wrote %s", manifest_csv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
