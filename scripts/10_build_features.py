"""Compute molecular descriptors for all 16 relaxed TMC structures.

Two complementary descriptor sets, both rotation/translation invariant and
computable from atomic positions + numbers alone (no additional calculations):

1. Sorted Coulomb matrix eigenvalues (Rupp et al. 2012, JCTC 8:1513)
   - M_ii = 0.5 * Z_i^2.4 (atomic energy baseline)
   - M_ij = Z_i * Z_j / r_ij  (nuclear repulsion; r_ij in Angstrom)
   - Eigenvalues sorted by descending absolute value, padded to n_max=20
   - Rotation/translation invariant by construction

2. Local metal-center geometric features (physically interpretable)
   - Metal identity, coordination number, M-L distances, L-M-L angles,
     C-O bond lengths (carbonyl systems), energy-per-atom, convergence cost

Reads:
  data/processed/full_dataset_v0.2.csv       (16-row merged validated dataset)
  data/processed/candidate_audit_v0.csv      (perturbation family metadata)

Writes:
  data/features/features_v0.1.csv            (16 rows × all features)
  data/features/feature_metadata_v0.1.json   (column names, units, descriptions)
  reports/feature_report_v0.1.md             (programmatic summary)

Usage:
    python scripts/10_build_features.py
    python scripts/10_build_features.py --dry-run
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path
import numpy as np
from ase import Atoms

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import PROJECT_ROOT, setup_logger  # noqa: E402

logger = setup_logger("build_features", "features.log")

FEATURE_VERSION = "0.1.0"

# Atoms whose Z values indicate a 3d/4d/5d transition metal (simplified set
# covering the 4 systems in this benchmark).
TM_Z = {21, 22, 23, 24, 25, 26, 27, 28, 29, 30,  # 3d TM (Sc-Zn)
        39, 40, 41, 42, 43, 44, 45, 46, 47, 48}   # 4d TM (Y-Cd)

# Maximum atom count across all 16 structures.
# ferrocene Fe(C5H5)2 = 1 Fe + 10 C + 10 H = 21 atoms (the largest system).
# Used as the fixed Coulomb eigenvalue vector length so no eigenvalue is dropped.
COULOMB_N_MAX = 21

# Distance cutoff to identify M-L bonds (Å). Generous enough to catch all
# M-C bonds across the 4 systems (shortest: ~1.84 Å for Ni(CO)4) without
# picking up any M...O through-space contacts (~3.0 Å for Ni(CO)4).
ML_CUTOFF_ANGSTROM = 2.5

# C-O bond detection cutoff (Å). Standard C-O bond ~1.15 Å.
CO_CUTOFF_ANGSTROM = 1.35

RY_TO_EV = 13.605693122994


# ---------------------------------------------------------------------------
# Coulomb matrix descriptors
# ---------------------------------------------------------------------------

def coulomb_matrix(atoms: Atoms) -> np.ndarray:
    """Compute the N×N Coulomb matrix for an ASE Atoms object.

    Diagonal: 0.5 * Z_i^2.4  (atomic energy baseline, Rupp 2012)
    Off-diagonal: Z_i * Z_j / r_ij  (nuclear repulsion in Angstrom units)
    """
    n = len(atoms)
    z = atoms.numbers.astype(float)
    pos = atoms.positions  # (N, 3) Angstrom

    cm = np.zeros((n, n), dtype=float)
    for i in range(n):
        cm[i, i] = 0.5 * z[i] ** 2.4
        for j in range(i + 1, n):
            r_ij = np.linalg.norm(pos[i] - pos[j])
            if r_ij < 1e-10:
                raise ValueError(
                    f"Atoms {i} and {j} are effectively co-located "
                    f"(r={r_ij:.2e} Å) — cannot compute Coulomb matrix"
                )
            val = z[i] * z[j] / r_ij
            cm[i, j] = val
            cm[j, i] = val
    return cm


def sorted_coulomb_eigenvalues(atoms: Atoms, n_max: int = COULOMB_N_MAX) -> np.ndarray:
    """Return sorted Coulomb matrix eigenvalues, padded to length n_max.

    Eigenvalues are sorted by descending absolute value (so the most
    chemically-informative, largest-magnitude eigenvalues come first).
    Padding uses zeros — physically equivalent to adding ghost atoms with Z=0.
    """
    cm = coulomb_matrix(atoms)
    eigs = np.linalg.eigvalsh(cm)  # real because cm is symmetric
    eigs_sorted = sorted(eigs, key=abs, reverse=True)
    result = np.zeros(n_max)
    n_eigs = min(len(eigs_sorted), n_max)
    result[:n_eigs] = eigs_sorted[:n_eigs]
    return result


# ---------------------------------------------------------------------------
# Local geometric features
# ---------------------------------------------------------------------------

def find_metal_index(atoms: Atoms) -> int:
    """Return the index of the transition metal atom.

    Raises ValueError if none is found (catches wrong-system or parsing error).
    """
    for i, z in enumerate(atoms.numbers):
        if z in TM_Z:
            return i
    raise ValueError(
        f"No transition metal atom found among Z={list(atoms.numbers)}. "
        "Check that the structure is a TMC."
    )


def local_geometric_features(atoms: Atoms) -> dict[str, float]:
    """Compute metal-center geometric features.

    Returns a dict with float values (math.nan where feature is not
    applicable, e.g. C-O distance for ferrocene which has no O atoms).
    """
    metal_idx = find_metal_index(atoms)
    metal_pos = atoms.positions[metal_idx]
    z_metal = int(atoms.numbers[metal_idx])

    # M-L bonds: all atoms within ML_CUTOFF of the metal (excluding metal itself)
    ligand_indices = []
    for i, pos in enumerate(atoms.positions):
        if i == metal_idx:
            continue
        d = np.linalg.norm(pos - metal_pos)
        if d <= ML_CUTOFF_ANGSTROM:
            ligand_indices.append(i)

    n_ligands = len(ligand_indices)
    if n_ligands == 0:
        raise ValueError(
            f"No atoms within {ML_CUTOFF_ANGSTROM} Å of metal (Z={z_metal}). "
            "Check ML_CUTOFF_ANGSTROM or that positions are correct."
        )

    ml_distances = [
        float(np.linalg.norm(atoms.positions[i] - metal_pos))
        for i in ligand_indices
    ]
    ml_mean = float(np.mean(ml_distances))
    ml_std = float(np.std(ml_distances, ddof=0))
    ml_min = float(min(ml_distances))
    ml_max = float(max(ml_distances))

    # L-M-L angles: all pairs of ligand atoms, angle at metal center
    lml_angles = []
    if n_ligands >= 2:
        for ii in range(n_ligands):
            for jj in range(ii + 1, n_ligands):
                v1 = atoms.positions[ligand_indices[ii]] - metal_pos
                v2 = atoms.positions[ligand_indices[jj]] - metal_pos
                cos_theta = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
                cos_theta = float(np.clip(cos_theta, -1.0, 1.0))
                angle_deg = math.degrees(math.acos(cos_theta))
                lml_angles.append(angle_deg)

    lml_mean = float(np.mean(lml_angles)) if lml_angles else math.nan
    lml_std = float(np.std(lml_angles, ddof=0)) if len(lml_angles) >= 2 else math.nan

    # C-O distances: for each ligand C, find nearest O within CO_CUTOFF_ANGSTROM.
    # NaN if no O atoms (ferrocene, which has no carbonyl ligands).
    o_indices = [i for i, z in enumerate(atoms.numbers) if z == 8]  # O = Z=8
    co_distances: list[float] = []
    if o_indices:
        for li in ligand_indices:
            if atoms.numbers[li] != 6:   # only C ligands have a C-O bond
                continue
            li_pos = atoms.positions[li]
            near_o = [
                float(np.linalg.norm(atoms.positions[oi] - li_pos))
                for oi in o_indices
            ]
            d_co_min = min(near_o)
            if d_co_min <= CO_CUTOFF_ANGSTROM:
                co_distances.append(d_co_min)

    co_mean = float(np.mean(co_distances)) if co_distances else math.nan
    co_std = float(np.std(co_distances, ddof=0)) if len(co_distances) >= 2 else math.nan

    return {
        "z_metal": float(z_metal),
        "n_ligands": float(n_ligands),
        "ml_mean_angstrom": ml_mean,
        "ml_std_angstrom": ml_std,
        "ml_min_angstrom": ml_min,
        "ml_max_angstrom": ml_max,
        "lml_angle_mean_deg": lml_mean,
        "lml_angle_std_deg": lml_std,
        "co_mean_angstrom": co_mean,
        "co_std_angstrom": co_std,
    }


# ---------------------------------------------------------------------------
# ASE Atoms reconstruction from CSV position string
# ---------------------------------------------------------------------------

def atoms_from_position_list(position_list: list[dict]) -> Atoms:
    """Build an ASE Atoms object from a parsed positions list.

    position_list: [{"symbol": "Fe", "x": 9.089, "y": 9.089, "z": 9.089}, ...]
    """
    symbols = [p["symbol"] for p in position_list]
    positions = [[p["x"], p["y"], p["z"]] for p in position_list]
    return Atoms(symbols=symbols, positions=positions)


def parse_positions(pos_str: str | None) -> list[dict] | None:
    if not pos_str:
        return None
    try:
        return json.loads(pos_str)
    except (json.JSONDecodeError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Feature metadata
# ---------------------------------------------------------------------------

def build_feature_metadata() -> dict:
    """Build the feature column metadata dict (column → description)."""
    meta = {}

    # Energy and convergence (not descriptors, but ML targets/meta)
    meta["final_energy_ry"] = {
        "unit": "Ry", "type": "target",
        "description": "DFT total energy from QE BFGS relaxation.",
    }
    meta["final_energy_ev"] = {
        "unit": "eV", "type": "target",
        "description": "DFT total energy in eV (= final_energy_ry × 13.6057).",
    }
    meta["delta_e_ry"] = {
        "unit": "Ry", "type": "target",
        "description": "Energy relative to parent primary structure (NaN for primary rows).",
    }
    meta["delta_e_ev"] = {
        "unit": "eV", "type": "target",
        "description": "delta_e_ry in eV (NaN for primary rows).",
    }
    meta["delta_e_meV"] = {
        "unit": "meV", "type": "target",
        "description": "delta_e_ry in meV (NaN for primary rows).",
    }
    meta["energy_per_atom_ry"] = {
        "unit": "Ry/atom", "type": "feature",
        "description": "Total energy divided by number of atoms. Partially normalises "
                       "for system size, but cross-system comparison is still not "
                       "physically meaningful (different stoichiometries).",
    }
    meta["n_atoms"] = {
        "unit": "count", "type": "feature",
        "description": "Total number of atoms in the relaxed structure.",
    }
    meta["ionic_steps"] = {
        "unit": "steps", "type": "meta",
        "description": "BFGS geometry optimization steps to convergence. "
                       "Proxy for relaxation difficulty.",
    }
    meta["scf_iterations_total"] = {
        "unit": "iterations", "type": "meta",
        "description": "Total SCF electronic iterations across all ionic steps.",
    }
    meta["max_force_ry_per_bohr"] = {
        "unit": "Ry/bohr", "type": "meta",
        "description": "Maximum residual force at end of relaxation (QE-reported).",
    }

    # Local geometric features
    meta["z_metal"] = {
        "unit": "Z", "type": "feature",
        "description": "Atomic number of the central transition metal (24=Cr, 26=Fe, 28=Ni).",
    }
    meta["n_ligands"] = {
        "unit": "count", "type": "feature",
        "description": f"Number of atoms within {ML_CUTOFF_ANGSTROM} Å of the metal center.",
    }
    meta["ml_mean_angstrom"] = {
        "unit": "Å", "type": "feature",
        "description": "Mean metal–ligand bond length (direct M-C or M-ring bond).",
    }
    meta["ml_std_angstrom"] = {
        "unit": "Å", "type": "feature",
        "description": "Standard deviation of M-L bond lengths. 0 for perfect symmetry.",
    }
    meta["ml_min_angstrom"] = {
        "unit": "Å", "type": "feature",
        "description": "Shortest M-L bond length.",
    }
    meta["ml_max_angstrom"] = {
        "unit": "Å", "type": "feature",
        "description": "Longest M-L bond length.",
    }
    meta["lml_angle_mean_deg"] = {
        "unit": "degrees", "type": "feature",
        "description": "Mean L-M-L angle over all ligand pairs. 90° for perfect Oh/Td; "
                       "varies for perturbed geometries.",
    }
    meta["lml_angle_std_deg"] = {
        "unit": "degrees", "type": "feature",
        "description": "Standard deviation of L-M-L angles. 0 for perfect symmetry.",
    }
    meta["co_mean_angstrom"] = {
        "unit": "Å", "type": "feature",
        "description": "Mean C–O bond length for carbonyl ligands. NaN for ferrocene.",
    }
    meta["co_std_angstrom"] = {
        "unit": "Å", "type": "feature",
        "description": "Standard deviation of C-O bond lengths. NaN for ferrocene.",
    }

    # Coulomb matrix eigenvalues
    for i in range(COULOMB_N_MAX):
        meta[f"cm_eig_{i:02d}"] = {
            "unit": "dimensionless", "type": "feature",
            "description": f"Coulomb matrix eigenvalue {i} (sorted by descending |value|). "
                           f"Zero-padded for structures with fewer than {COULOMB_N_MAX} atoms.",
        }

    return meta


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def _read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _safe_float(s: str | None) -> float | None:
    if s is None or s.strip() in ("", "None"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def compute_all_features(dataset_rows: list[dict], primary_lookup: dict[str, dict]) -> list[dict]:
    rows_out = []
    for row in dataset_rows:
        sys_id = row["system_id"]
        is_candidate = "__" in sys_id
        parent_id = sys_id.split("__")[0] if is_candidate else sys_id
        source = "candidate" if is_candidate else "primary"

        pos_list = parse_positions(row.get("final_positions_angstrom"))
        if pos_list is None:
            logger.warning("No positions for %s — skipping", sys_id)
            continue

        atoms = atoms_from_position_list(pos_list)
        n_atoms = len(atoms)

        # Coulomb eigenvalues
        try:
            cm_eigs = sorted_coulomb_eigenvalues(atoms, n_max=COULOMB_N_MAX)
        except ValueError as e:
            logger.error("Coulomb matrix failed for %s: %s", sys_id, e)
            continue

        # Local geometric features
        try:
            geo = local_geometric_features(atoms)
        except ValueError as e:
            logger.error("Geometric features failed for %s: %s", sys_id, e)
            continue

        # Energy targets
        e_ry = _safe_float(row.get("final_energy_ry"))
        e_ev = _safe_float(row.get("final_energy_ev"))
        e_per_atom = e_ry / n_atoms if e_ry is not None else math.nan

        # ΔE relative to parent (candidates only)
        delta_e_ry = math.nan
        delta_e_ev = math.nan
        delta_e_meV = math.nan
        if is_candidate:
            parent = primary_lookup.get(parent_id)
            if parent:
                p_pos = parse_positions(parent.get("final_positions_angstrom"))
                if p_pos:
                    p_e = _safe_float(parent.get("final_energy_ry"))
                    if e_ry is not None and p_e is not None:
                        delta_e_ry = e_ry - p_e
                        delta_e_ev = delta_e_ry * RY_TO_EV
                        delta_e_meV = delta_e_ev * 1000

        out = {
            "system_id": sys_id,
            "parent_system_id": parent_id,
            "source": source,
            "label": row.get("label", ""),
            "feature_version": FEATURE_VERSION,
            "final_energy_ry": e_ry if e_ry is not None else "",
            "final_energy_ev": e_ev if e_ev is not None else "",
            "delta_e_ry": "" if math.isnan(delta_e_ry) else f"{delta_e_ry:.10f}",
            "delta_e_ev": "" if math.isnan(delta_e_ev) else f"{delta_e_ev:.8f}",
            "delta_e_meV": "" if math.isnan(delta_e_meV) else f"{delta_e_meV:.4f}",
            "energy_per_atom_ry": "" if math.isnan(e_per_atom) else f"{e_per_atom:.8f}",
            "n_atoms": n_atoms,
            "ionic_steps": row.get("ionic_steps", ""),
            "scf_iterations_total": row.get("scf_iterations_total", ""),
            "max_force_ry_per_bohr": row.get("max_force_ry_per_bohr", ""),
        }

        # Local geometric features
        for k, v in geo.items():
            out[k] = "" if math.isnan(v) else f"{v:.6f}"

        # Coulomb eigenvalues
        for i, eig_val in enumerate(cm_eigs):
            out[f"cm_eig_{i:02d}"] = f"{eig_val:.6f}"

        rows_out.append(out)
        logger.info("  %s: n_atoms=%d, z_metal=%.0f, n_lig=%.0f, ml_mean=%.4f Å, "
                    "delta_e_meV=%s",
                    sys_id, n_atoms, geo["z_metal"], geo["n_ligands"],
                    geo["ml_mean_angstrom"],
                    "primary" if math.isnan(delta_e_meV) else f"{delta_e_meV:.2f}")

    return rows_out


def build_report(rows: list[dict], out_path: Path) -> None:
    lines = ["# Feature Report — TMC Benchmark v0.1",
             "",
             "*Generated by `scripts/10_build_features.py`. Do not edit by hand.*",
             "",
             "## Descriptor design",
             "",
             "Two complementary descriptor sets, both rotation/translation invariant:",
             "",
             "1. **Sorted Coulomb matrix eigenvalues** (Rupp et al. 2012, JCTC 8:1513): "
             f"{COULOMB_N_MAX} values, zero-padded for structures with fewer than "
             f"{COULOMB_N_MAX} atoms.",
             "2. **Local metal-center geometric features**: 10 values — metal identity, "
             "coordination number, M-L distances (mean/std/min/max), L-M-L angles "
             "(mean/std), C-O bond lengths (mean/std; NaN for ferrocene).",
             "",
             "## Feature completeness",
             "",
             f"| # rows | n_atoms range | Coulomb dim | Local geo dim |",
             f"|---|---|---|---|",
             f"| {len(rows)} | "
             f"{min(int(r['n_atoms']) for r in rows)}–{max(int(r['n_atoms']) for r in rows)} "
             f"| {COULOMB_N_MAX} | 10 |",
             "",
             "## Per-structure summary",
             "",
             "| system_id | source | n_atoms | z_metal | n_ligands | ml_mean (Å) | co_mean (Å) | ΔE (meV) |",
             "|---|---|---|---|---|---|---|---|",
             ]
    for r in sorted(rows, key=lambda x: (x["parent_system_id"], x["system_id"])):
        co = r.get("co_mean_angstrom", "")
        de = r.get("delta_e_meV", "")
        lines.append(
            f"| {r['system_id']} | {r['source']} | {r['n_atoms']} | "
            f"{r.get('z_metal', '')} | {r.get('n_ligands', '')} | "
            f"{r.get('ml_mean_angstrom', '')} | {co if co else 'NaN'} | "
            f"{de if de else '—'} |"
        )
    lines += [
        "",
        "## Dataset size disclaimer",
        "",
        "> This dataset contains **16 DFT calculations across 4 systems** (4 points per "
        "system after the perturbation campaign). This is sufficient for workflow "
        "demonstration and descriptor validation, but **not sufficient for statistically "
        "robust ML training or predictive claims**. Descriptors are provided as "
        "infrastructure for future expansion. No ML performance claims should be made "
        "until ≥30–50 validated calculations per system are available.",
        "",
    ]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("Wrote %s", out_path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="Compute features but do not write output files.")
    args = parser.parse_args()

    merged_path = PROJECT_ROOT / "data" / "processed" / "full_dataset_v0.2.csv"
    if not merged_path.exists():
        logger.error("Merged dataset not found: %s — run scripts/09_dataset_diagnostics.py first",
                     merged_path)
        sys.exit(1)

    all_rows = _read_csv(merged_path)
    primary_rows = [r for r in all_rows if "__" not in r["system_id"]]
    primary_lookup = {r["system_id"]: r for r in primary_rows}

    logger.info("Computing features for %d structures (%d primary, %d candidates)",
                len(all_rows), len(primary_rows), len(all_rows) - len(primary_rows))

    feature_rows = compute_all_features(all_rows, primary_lookup)

    if not feature_rows:
        logger.error("No feature rows produced — check position parsing")
        sys.exit(1)

    logger.info("Successfully computed features for %d/%d structures",
                len(feature_rows), len(all_rows))

    if args.dry_run:
        logger.info("Dry run: skipping file writes")
        for r in feature_rows[:3]:
            logger.info("  sample row keys: %s", list(r.keys()))
        return

    feat_dir = PROJECT_ROOT / "data" / "features"
    feat_dir.mkdir(parents=True, exist_ok=True)

    feat_path = feat_dir / "features_v0.1.csv"
    fieldnames = list(feature_rows[0].keys())
    with feat_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(feature_rows)
    logger.info("Wrote %s (%d rows, %d columns)", feat_path, len(feature_rows), len(fieldnames))

    meta = build_feature_metadata()
    meta_path = feat_dir / "feature_metadata_v0.1.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    logger.info("Wrote %s (%d entries)", meta_path, len(meta))

    report_path = PROJECT_ROOT / "reports" / "feature_report_v0.1.md"
    build_report(feature_rows, report_path)


if __name__ == "__main__":
    main()
