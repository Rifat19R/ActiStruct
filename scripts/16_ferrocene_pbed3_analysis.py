"""Task 2: Ferrocene PBE-D3 analysis.

Parses the PBE-D3 relax output, compares geometry and energy to the plain-PBE
baseline, checks Cp-ring conformer ordering (eclipsed vs staggered dihedral),
updates the dataset, and writes a short report.

Reads:
  qe/outputs/relax/ferrocene_pbed3.out

Writes:
  data/processed/ferrocene_pbed3_vs_pbe.csv
  reports/ferrocene_pbed3_v0.1.md
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import PROJECT_ROOT, setup_logger  # noqa: E402

logger = setup_logger("ferrocene_pbed3", "ferrocene_pbed3.log")

RY_TO_EV = 13.605693122994
N_ATOMS = 21  # Fe(C5H5)2

# PBE baseline from initial_relax_parsed_v0.1.csv (already in the repo)
PBE_ENERGY_RY = -525.3618442398
PBE_ENERGY_EV = PBE_ENERGY_RY * RY_TO_EV


# ─── Parser ──────────────────────────────────────────────────────────────────

def parse_qe_output(path: Path) -> dict:
    if not path.exists():
        return {"converged": False, "error": f"file not found: {path}"}
    text = path.read_text(encoding="utf-8", errors="replace")
    r: dict = {"path": str(path)}

    r["converged"] = "bfgs converged" in text.lower()
    r["job_done"] = "JOB DONE" in text

    # Total energy
    em = re.findall(r"!\s+total energy\s+=\s+([-\d.]+)\s+Ry", text)
    if em:
        r["total_energy_ry"] = float(em[-1])
        r["total_energy_ev"] = r["total_energy_ry"] * RY_TO_EV
        r["energy_per_atom_ev"] = r["total_energy_ev"] / N_ATOMS
    else:
        r["total_energy_ry"] = r["total_energy_ev"] = r["energy_per_atom_ev"] = None

    # Ionic / SCF steps
    r["n_bfgs_steps"] = len(re.findall(r"number of scf cycles\s*=\s*\d+", text))
    scf = re.findall(r"convergence has been achieved in\s+(\d+)\s+iterations", text)
    r["n_scf_steps"] = sum(int(x) for x in scf) if scf else None

    # Walltime
    wt = re.search(r"PWSCF\s+:\s+([\d.hms ]+?)CPU", text)
    if wt:
        r["walltime_str"] = wt.group(1).strip()
        r["walltime_sec"] = _parse_walltime(r["walltime_str"])
    else:
        r["walltime_str"] = r["walltime_sec"] = None

    # Final positions
    r["positions"] = _parse_positions(text)
    return r


def _parse_walltime(s: str) -> float | None:
    total = 0.0
    for num, unit in re.findall(r"([\d.]+)\s*([hms])", s):
        total += float(num) * {"h": 3600, "m": 60, "s": 1}[unit]
    return total if total > 0 else None


def _parse_positions(text: str) -> list[dict] | None:
    block = re.search(
        r"Begin final coordinates.*?ATOMIC_POSITIONS \(angstrom\)\n(.*?)End final coordinates",
        text, re.DOTALL
    )
    if not block:
        all_blocks = re.findall(
            r"ATOMIC_POSITIONS \(angstrom\)\n((?:[ \t]+\S+[ \t]+[-\d.]+[ \t]+[-\d.]+[ \t]+[-\d.]+\n)+)",
            text
        )
        if not all_blocks:
            return None
        raw = all_blocks[-1]
    else:
        raw = block.group(1)

    positions = []
    for line in raw.strip().splitlines():
        parts = line.split()
        if len(parts) >= 4:
            try:
                positions.append({"symbol": parts[0],
                                   "x": float(parts[1]),
                                   "y": float(parts[2]),
                                   "z": float(parts[3])})
            except ValueError:
                pass
    return positions or None


# ─── Geometry analysis ───────────────────────────────────────────────────────

def _fe_cp_distance(positions: list[dict]) -> float | None:
    """Mean distance from Fe to each Cp ring centroid."""
    fe = next((p for p in positions if p["symbol"] == "Fe"), None)
    if fe is None:
        return None
    fe_xyz = np.array([fe["x"], fe["y"], fe["z"]])

    # Split C atoms into two Cp rings by z-coordinate relative to Fe
    c_atoms = [p for p in positions if p["symbol"] == "C"]
    above = [p for p in c_atoms if p["z"] > fe["z"]]
    below = [p for p in c_atoms if p["z"] <= fe["z"]]
    if len(above) != 5 or len(below) != 5:
        return None

    def centroid(atoms):
        return np.mean([[a["x"], a["y"], a["z"]] for a in atoms], axis=0)

    d_above = float(np.linalg.norm(centroid(above) - fe_xyz))
    d_below = float(np.linalg.norm(centroid(below) - fe_xyz))
    return round((d_above + d_below) / 2, 4)


def _cp_dihedral_deg(positions: list[dict]) -> float | None:
    """Dihedral between the two Cp rings (0° = eclipsed, 36° = staggered).

    Strategy: find the C atom in the upper ring closest to the x-axis
    (max x coordinate), do the same for the lower ring, compute the
    angle between the two vectors projected onto the xy-plane.
    """
    fe = next((p for p in positions if p["symbol"] == "Fe"), None)
    if fe is None:
        return None

    c_atoms = [p for p in positions if p["symbol"] == "C"]
    above = sorted([p for p in c_atoms if p["z"] > fe["z"]], key=lambda p: -p["x"])
    below = sorted([p for p in c_atoms if p["z"] <= fe["z"]], key=lambda p: -p["x"])
    if not above or not below:
        return None

    # Vector from Fe to the "reference" C in each ring, in the xy-plane
    va = np.array([above[0]["x"] - fe["x"], above[0]["y"] - fe["y"]])
    vb = np.array([below[0]["x"] - fe["x"], below[0]["y"] - fe["y"]])
    if np.linalg.norm(va) < 1e-6 or np.linalg.norm(vb) < 1e-6:
        return None
    cos_theta = np.clip(np.dot(va, vb) / (np.linalg.norm(va) * np.linalg.norm(vb)), -1, 1)
    return round(float(np.degrees(np.arccos(cos_theta))), 2)


def _fe_c_distance(positions: list[dict]) -> float | None:
    """Mean Fe–C bond length (all 10 Cp carbons)."""
    fe = next((p for p in positions if p["symbol"] == "Fe"), None)
    if fe is None:
        return None
    fe_xyz = np.array([fe["x"], fe["y"], fe["z"]])
    dists = []
    for p in positions:
        if p["symbol"] == "C":
            d = np.linalg.norm(np.array([p["x"], p["y"], p["z"]]) - fe_xyz)
            if d < 3.0:
                dists.append(d)
    return round(float(np.mean(dists)), 4) if dists else None


# ─── Main ────────────────────────────────────────────────────────────────────

def main() -> None:
    out_path = PROJECT_ROOT / "qe" / "outputs" / "relax" / "ferrocene_pbed3.out"
    if not out_path.exists():
        logger.error("Output not found: %s — run scripts/run_ferrocene_pbed3.sh first.", out_path)
        sys.exit(1)

    r = parse_qe_output(out_path)

    if not r.get("converged"):
        logger.error("ferrocene_pbed3 did NOT converge — do NOT update dataset.")
        sys.exit(1)

    logger.info("converged=True, E=%.6f eV, walltime=%s", r["total_energy_ev"], r["walltime_str"])

    # Geometry
    pos = r["positions"]
    fe_cp = _fe_cp_distance(pos) if pos else None
    fe_c = _fe_c_distance(pos) if pos else None
    dihedral = _cp_dihedral_deg(pos) if pos else None

    logger.info("Fe–Cp centroid dist = %.4f Å", fe_cp if fe_cp is not None else float("nan"))
    logger.info("Mean Fe–C bond      = %.4f Å", fe_c if fe_c is not None else float("nan"))
    logger.info("Cp–Cp dihedral      = %.2f °  (0=eclipsed, 36=staggered)", dihedral if dihedral is not None else float("nan"))

    # PBE comparison
    delta_e_ev = (r["total_energy_ev"] or 0.0) - PBE_ENERGY_EV
    delta_e_mev_atom = delta_e_ev * 1000 / N_ATOMS
    logger.info("ΔE(PBE-D3 − PBE) = %.4f eV  (%.2f meV/atom)", delta_e_ev, delta_e_mev_atom)
    logger.info("  Dispersion lowers energy by %.4f eV (expected: negative for D3)", delta_e_ev)

    # Conformer check
    if dihedral is not None:
        if dihedral < 10:
            conformer = "eclipsed (D5h)"
        elif dihedral > 26:
            conformer = "staggered (D5d)"
        else:
            conformer = f"intermediate ({dihedral:.1f}°)"
        logger.info("Conformer: %s", conformer)
    else:
        conformer = "unknown"

    # Write comparison CSV
    csv_path = PROJECT_ROOT / "data" / "processed" / "ferrocene_pbed3_vs_pbe.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "system", "functional", "ecutwfc_ry", "vdw_corr",
            "total_energy_ev", "energy_per_atom_ev",
            "fe_cp_centroid_ang", "fe_c_mean_ang", "cp_dihedral_deg",
            "conformer", "n_bfgs_steps", "n_scf_steps", "walltime_sec",
            "delta_e_vs_pbe_ev", "delta_e_vs_pbe_mev_atom",
        ])
        writer.writeheader()
        writer.writerow({
            # Distinct system label: functional + cutoff disambiguate from PBE-D3 row
            "system": "ferrocene_pbe_60ry", "functional": "PBE",
            "ecutwfc_ry": 60, "vdw_corr": "none",
            "total_energy_ev": round(PBE_ENERGY_EV, 6),
            "energy_per_atom_ev": round(PBE_ENERGY_EV / N_ATOMS, 6),
            "fe_cp_centroid_ang": "", "fe_c_mean_ang": "", "cp_dihedral_deg": "",
            "conformer": "eclipsed (D5h)",  # from prior run; Cp rings eclipsed at PBE
            "n_bfgs_steps": 15, "n_scf_steps": 319, "walltime_sec": 4980,
            "delta_e_vs_pbe_ev": 0.0, "delta_e_vs_pbe_mev_atom": 0.0,
        })
        writer.writerow({
            # Distinct system label: PBE-D3/90 Ry conformer check (Task 2)
            "system": "ferrocene_pbed3_90ry", "functional": "PBE-D3",
            "ecutwfc_ry": 90, "vdw_corr": "grimme-d3",
            "total_energy_ev": round(r["total_energy_ev"], 6),
            "energy_per_atom_ev": round(r["energy_per_atom_ev"], 6),
            "fe_cp_centroid_ang": fe_cp, "fe_c_mean_ang": fe_c, "cp_dihedral_deg": dihedral,
            "conformer": conformer,
            "n_bfgs_steps": r["n_bfgs_steps"], "n_scf_steps": r["n_scf_steps"],
            "walltime_sec": r["walltime_sec"],
            "delta_e_vs_pbe_ev": round(delta_e_ev, 6),
            "delta_e_vs_pbe_mev_atom": round(delta_e_mev_atom, 2),
        })
    logger.info("Wrote %s", csv_path)

    # Write report
    report_path = PROJECT_ROOT / "reports" / "ferrocene_pbed3_v0.1.md"
    _write_report(report_path, r, fe_cp, fe_c, dihedral, conformer, delta_e_ev, delta_e_mev_atom)
    logger.info("Wrote %s", report_path)
    logger.info("=== Task 2 complete ===")


def _write_report(path, r, fe_cp, fe_c, dihedral, conformer, delta_e_ev, delta_e_mev_atom):
    lines = [
        "# Ferrocene PBE-D3 Relax — Task 2 Report (v0.1)",
        "",
        "*Generated by `scripts/16_ferrocene_pbed3_analysis.py`. Do not edit by hand.*",
        "",
        "## 1. Motivation",
        "",
        "Ferrocene (Fe(C5H5)2) has a sandwich geometry where the Cp rings interact",
        "with each other and with the Fe centre via π-electron density. The Cp–Fe–Cp",
        "dispersion contribution is non-negligible and can affect the Fe–Cp distance",
        "and the conformer preference (eclipsed D5h vs staggered D5d).",
        "The Task 1 baseline used plain PBE at 60 Ry. Task 2 re-runs with PBE-D3",
        "(Grimme DFT-D3, zero-damping) at 90 Ry (adopted cutoff from Task 1.5).",
        "",
        "## 2. Computational details",
        "",
        "| Parameter | Value |",
        "|---|---|",
        "| functional | PBE + DFT-D3 (`vdw_corr = 'grimme-d3'`) |",
        "| ecutwfc | 90 Ry (adopted from Task 1.5 Fe cutoff convergence test) |",
        "| ecutrho | 720 Ry |",
        "| assume_isolated | mt (Martyna-Tuckerman) |",
        "| Starting geometry | PBE-relaxed positions from Task 1 baseline |",
        "| disk_io | medium (checkpoint after every BFGS step) |",
        "",
        "## 3. Results",
        "",
        "### 3.1 Convergence",
        f"- Converged: {'Yes' if r.get('converged') else 'NO'}",
        f"- BFGS steps: {r.get('n_bfgs_steps', 'N/A')}",
        f"- SCF iterations: {r.get('n_scf_steps', 'N/A')}",
        f"- Walltime: {r.get('walltime_str', 'N/A')}",
        "",
        "### 3.2 Energy comparison",
        "",
        "| Functional | ecutwfc (Ry) | E_total (eV) | E/atom (eV) | ΔE vs PBE (eV) | ΔE/atom (meV) |",
        "|---|---|---|---|---|---|",
        f"| PBE | 60 | {PBE_ENERGY_EV:.4f} | {PBE_ENERGY_EV/N_ATOMS:.4f} | — | — |",
        f"| PBE-D3 | 90 | {r.get('total_energy_ev', 0):.4f} | {r.get('energy_per_atom_ev', 0):.4f} | {delta_e_ev:+.4f} | {delta_e_mev_atom:+.2f} |",
        "",
        "> Note: the ΔE includes both the dispersion correction and the ecutwfc change",
        "> (60→90 Ry). These are not separated here. The Fe(CO)5 cutoff test showed",
        "> ~18.6 meV/atom energy shift from 60→90 Ry for Fe PAW-031, so a similar",
        "> offset is expected for ferrocene independent of dispersion.",
        "",
        "### 3.3 Geometry",
        "",
        f"| Quantity | PBE-D3 | Notes |",
        "|---|---|---|",
        f"| Fe–Cp centroid distance | {fe_cp or 'N/A'} Å | mean of two rings |",
        f"| Mean Fe–C bond | {fe_c or 'N/A'} Å | all 10 Cp carbons |",
        f"| Cp–Cp dihedral | {dihedral or 'N/A'} ° | 0°=eclipsed, 36°=staggered |",
        f"| Conformer | {conformer} | |",
        "",
        "### 3.4 Conformer check (Task 3 blocker)",
        "",
        "The experimentally known ground state of ferrocene in the gas phase is",
        "**eclipsed (D5h)** with an extremely small eclipsed–staggered barrier",
        "(< 1 kcal/mol, ~40 meV). PBE-D3 should reproduce eclipsed or near-eclipsed.",
    ]

    if dihedral is not None:
        if dihedral < 10:
            verdict = f"✓ Dihedral = {dihedral}° — correctly eclipsed (D5h). Task 3 conformer check PASSED."
        elif dihedral > 26:
            verdict = (f"⚠ Dihedral = {dihedral}° — staggered geometry obtained. "
                       "This may indicate the starting geometry or DFT settings favour D5d. "
                       "Investigate before proceeding to v1.0.")
        else:
            verdict = (f"⚠ Dihedral = {dihedral}° — intermediate. "
                       "The Cp rings are partially rotated. Check starting geometry and convergence.")
        lines.append("")
        lines.append(verdict)

    lines += [
        "",
        "## 4. Known limitations",
        "",
        "- ΔE(PBE-D3 − PBE) conflates dispersion and cutoff effects (60→90 Ry).",
        "  A fair dispersion-only comparison would require re-running PBE at 90 Ry.",
        "- D3 zero-damping used (`vdw_corr = 'grimme-d3'`). Becke-Johnson damping",
        "  (`grimme-d3bj`) is often preferred but is not available in all QE builds.",
        "- Cp–Cp dihedral is computed from the highest-x C atom in each ring, which",
        "  is a proxy. A full symmetry analysis would be more rigorous.",
        "",
        "## 5. Next steps",
        "",
        "- Task 3: confirm conformer ordering is correct.",
        "- Task 4: PDF-verify all literature references.",
    ]

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
