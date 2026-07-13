"""Tests for scripts/10_build_features.py.

Run before executing the main script to confirm descriptor logic is
scientifically correct (rotation/translation invariance, correct geometry
extraction, Coulomb matrix properties).
"""
import json
import math
from pathlib import Path

import numpy as np
import pytest

from _load import load_script

feat_mod = load_script("10_build_features.py")
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Minimal toy molecules for unit tests
# ---------------------------------------------------------------------------

def _linear_co2_atoms():
    """Simple 3-atom CO2 for Coulomb matrix tests (known geometry)."""
    from ase import Atoms
    return Atoms(
        symbols=["O", "C", "O"],
        positions=[[-1.16, 0, 0], [0.0, 0, 0], [1.16, 0, 0]],
    )


def _ni_co4_minimal():
    """Minimal Ni(CO)4 mock: Ni at origin, 4 C at 1.84 Å, 4 O at 3.0 Å."""
    from ase import Atoms
    d_ni_c = 1.84
    d_c_o = 1.16
    pos = [
        [0, 0, 0],                       # Ni
        [d_ni_c, 0, 0],                   # C1
        [-(d_ni_c), 0, 0],               # C2
        [0, d_ni_c, 0],                   # C3
        [0, -(d_ni_c), 0],               # C4
        [d_ni_c + d_c_o, 0, 0],           # O1
        [-(d_ni_c + d_c_o), 0, 0],       # O2
        [0, d_ni_c + d_c_o, 0],           # O3
        [0, -(d_ni_c + d_c_o), 0],       # O4
    ]
    return Atoms(symbols=["Ni", "C", "C", "C", "C", "O", "O", "O", "O"], positions=pos)


# ---------------------------------------------------------------------------
# Coulomb matrix tests
# ---------------------------------------------------------------------------

def test_coulomb_matrix_is_symmetric():
    atoms = _linear_co2_atoms()
    cm = feat_mod.coulomb_matrix(atoms)
    assert cm.shape == (3, 3)
    np.testing.assert_allclose(cm, cm.T, atol=1e-12)


def test_coulomb_matrix_diagonal():
    """Diagonal must be 0.5 * Z^2.4 (Rupp 2012 convention)."""
    atoms = _linear_co2_atoms()
    cm = feat_mod.coulomb_matrix(atoms)
    z_c, z_o = 6, 8
    assert pytest.approx(cm[1, 1], rel=1e-8) == 0.5 * z_c ** 2.4
    assert pytest.approx(cm[0, 0], rel=1e-8) == 0.5 * z_o ** 2.4


def test_coulomb_matrix_offdiagonal_symmetry():
    """M_ij = Z_i*Z_j / r_ij; the two O's in CO2 are at equal distance from C."""
    atoms = _linear_co2_atoms()
    cm = feat_mod.coulomb_matrix(atoms)
    # Both O-C entries should be equal
    assert pytest.approx(cm[0, 1], rel=1e-8) == cm[2, 1]


def test_sorted_coulomb_eigenvalues_length():
    atoms = _linear_co2_atoms()
    eigs = feat_mod.sorted_coulomb_eigenvalues(atoms, n_max=5)
    assert len(eigs) == 5


def test_sorted_coulomb_eigenvalues_descending_order():
    atoms = _linear_co2_atoms()
    eigs = feat_mod.sorted_coulomb_eigenvalues(atoms, n_max=5)
    for i in range(len(eigs) - 1):
        assert abs(eigs[i]) >= abs(eigs[i + 1]) - 1e-12


def test_sorted_coulomb_eigenvalues_padded_with_zeros():
    atoms = _linear_co2_atoms()  # 3 atoms
    eigs = feat_mod.sorted_coulomb_eigenvalues(atoms, n_max=10)
    # Last 7 entries must be zero (padding)
    np.testing.assert_array_equal(eigs[3:], 0.0)


def test_coulomb_eigenvalues_rotation_invariant():
    """Rotating a molecule must not change its sorted Coulomb eigenvalues."""
    from ase import Atoms
    import numpy as np
    atoms = _ni_co4_minimal()
    eigs_orig = feat_mod.sorted_coulomb_eigenvalues(atoms, n_max=20)

    # 45-degree rotation around z-axis
    theta = math.radians(45)
    rot = np.array([
        [math.cos(theta), -math.sin(theta), 0],
        [math.sin(theta),  math.cos(theta), 0],
        [0,                0,               1],
    ])
    rotated_pos = atoms.positions @ rot.T
    atoms_rot = Atoms(symbols=atoms.symbols, positions=rotated_pos)
    eigs_rot = feat_mod.sorted_coulomb_eigenvalues(atoms_rot, n_max=20)

    np.testing.assert_allclose(eigs_orig, eigs_rot, atol=1e-8)


def test_coulomb_eigenvalues_translation_invariant():
    """Translating a molecule must not change its sorted Coulomb eigenvalues."""
    from ase import Atoms
    atoms = _ni_co4_minimal()
    eigs_orig = feat_mod.sorted_coulomb_eigenvalues(atoms, n_max=20)

    shifted_pos = atoms.positions + np.array([5.0, -3.0, 2.5])
    atoms_shifted = Atoms(symbols=atoms.symbols, positions=shifted_pos)
    eigs_shifted = feat_mod.sorted_coulomb_eigenvalues(atoms_shifted, n_max=20)

    np.testing.assert_allclose(eigs_orig, eigs_shifted, atol=1e-8)


# ---------------------------------------------------------------------------
# Metal identification
# ---------------------------------------------------------------------------

def test_find_metal_index_ni_co4():
    atoms = _ni_co4_minimal()
    idx = feat_mod.find_metal_index(atoms)
    assert atoms.symbols[idx] == "Ni"


def test_find_metal_index_no_metal_raises():
    from ase import Atoms
    atoms = Atoms(symbols=["C", "O"], positions=[[0, 0, 0], [1.16, 0, 0]])
    with pytest.raises(ValueError, match="metal"):
        feat_mod.find_metal_index(atoms)


# ---------------------------------------------------------------------------
# Local geometric features
# ---------------------------------------------------------------------------

def test_local_features_ni_co4_coordination_number():
    atoms = _ni_co4_minimal()
    feats = feat_mod.local_geometric_features(atoms)
    assert feats["n_ligands"] == 4


def test_local_features_ni_co4_ml_distance():
    atoms = _ni_co4_minimal()
    feats = feat_mod.local_geometric_features(atoms)
    assert pytest.approx(feats["ml_mean_angstrom"], abs=1e-6) == 1.84
    assert pytest.approx(feats["ml_std_angstrom"], abs=1e-6) == 0.0  # perfect Td


def test_local_features_ni_co4_co_distance():
    atoms = _ni_co4_minimal()
    feats = feat_mod.local_geometric_features(atoms)
    assert pytest.approx(feats["co_mean_angstrom"], abs=1e-6) == 1.16
    assert pytest.approx(feats["co_std_angstrom"], abs=1e-6) == 0.0


def test_local_features_no_oxygen_gives_nan_co():
    """Ferrocene-like system: no O atoms → C-O features must be NaN."""
    from ase import Atoms
    # Minimal Fe + 2 C (no O)
    atoms = Atoms(
        symbols=["Fe", "C", "C"],
        positions=[[0, 0, 0], [2.0, 0, 0], [-2.0, 0, 0]],
    )
    feats = feat_mod.local_geometric_features(atoms)
    assert math.isnan(feats["co_mean_angstrom"])
    assert math.isnan(feats["co_std_angstrom"])


def test_local_features_lml_angle_ni_co4():
    """Square-planar mock (±x, ±y): 4 pairs at 90°, 2 pairs at 180°.
    Mean = (4×90 + 2×180) / 6 = 120°; std = 0 is wrong, but mean is correct.
    This tests the angle-calculation logic, not a real Td geometry.
    """
    atoms = _ni_co4_minimal()
    feats = feat_mod.local_geometric_features(atoms)
    # 4 adjacent pairs at 90°, 2 trans pairs at 180° → mean = 120°
    assert pytest.approx(feats["lml_angle_mean_deg"], abs=0.1) == 120.0


def test_local_features_z_metal():
    atoms = _ni_co4_minimal()
    feats = feat_mod.local_geometric_features(atoms)
    assert feats["z_metal"] == 28  # Ni


# ---------------------------------------------------------------------------
# Integration test: run the full pipeline on real data
# ---------------------------------------------------------------------------

def test_feature_csv_exists_and_has_16_rows():
    feat_path = PROJECT_ROOT / "data" / "features" / "features_v0.1.csv"
    assert feat_path.exists(), "run scripts/10_build_features.py first"
    import csv
    with feat_path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 16


def test_feature_metadata_json_exists_and_documents_all_columns():
    meta_path = PROJECT_ROOT / "data" / "features" / "feature_metadata_v0.1.json"
    assert meta_path.exists(), "run scripts/10_build_features.py first"
    feat_path = PROJECT_ROOT / "data" / "features" / "features_v0.1.csv"
    assert feat_path.exists(), "run scripts/10_build_features.py first"

    import csv
    with feat_path.open(encoding="utf-8") as f:
        headers = list(csv.DictReader(f))[0].keys()
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    # Every data column (excluding bookkeeping) must appear in metadata
    bookkeeping = {"system_id", "parent_system_id", "source", "label",
                   "feature_version"}
    for col in headers:
        if col in bookkeeping:
            continue
        assert col in meta, f"Column '{col}' missing from feature_metadata_v0.1.json"


def test_coulomb_eigenvalues_in_csv_are_rotation_invariant_for_same_parent():
    """Two candidates of the same parent that relax back to the same basin
    should have very similar Coulomb eigenvalues (within numerical noise)."""
    feat_path = PROJECT_ROOT / "data" / "features" / "features_v0.1.csv"
    if not feat_path.exists():
        pytest.skip("run scripts/10_build_features.py first")

    import csv
    with feat_path.open(encoding="utf-8") as f:
        rows = {r["system_id"]: r for r in csv.DictReader(f)}

    # ferrocene__fe_cp_dist__-0.05 and parent ferrocene both returned to the
    # same basin (ΔE = 0 meV, RMS = 0 Å) — their Coulomb eigenvalues should
    # differ by less than 1% for the dominant (large) ones
    parent = rows.get("ferrocene")
    cand = rows.get("ferrocene__fe_cp_dist__-0.05")
    if parent is None or cand is None:
        pytest.skip("parent or candidate row missing")

    # Compare the first (largest) Coulomb eigenvalue
    e0_parent = float(parent["cm_eig_00"])
    e0_cand = float(cand["cm_eig_00"])
    assert abs(e0_parent - e0_cand) / abs(e0_parent) < 0.01, (
        f"Dominant Coulomb eigenvalue differs by >1% for same-basin candidate: "
        f"parent={e0_parent:.4f}, candidate={e0_cand:.4f}"
    )


# ---------------------------------------------------------------------------
# Task 5 validation: reproducibility, DFT-vs-reference, descriptor labeling
# ---------------------------------------------------------------------------

def test_feature_matrix_is_reproducible_from_raw_positions():
    """Re-running compute_all_features() must reproduce stored features_v0.1.csv.

    Validates that stored values are stable across runs and that the positions
    in full_dataset_v0.2.csv faithfully encode the QE-relaxed geometries.
    Tolerance 1e-4 (in Å or eigenvalue units) accommodates CSV float formatting.
    """
    import csv as _csv
    merged_path = PROJECT_ROOT / "data" / "processed" / "full_dataset_v0.2.csv"
    feat_path = PROJECT_ROOT / "data" / "features" / "features_v0.1.csv"
    if not merged_path.exists() or not feat_path.exists():
        pytest.skip("dataset or feature CSV missing — run build_features first")

    all_rows = list(_csv.DictReader(merged_path.open(encoding="utf-8")))
    primary_lookup = {r["system_id"]: r for r in all_rows if "__" not in r["system_id"]}
    recomputed = feat_mod.compute_all_features(all_rows, primary_lookup)
    recomputed_map = {r["system_id"]: r for r in recomputed}

    stored = list(_csv.DictReader(feat_path.open(encoding="utf-8")))
    bookkeeping = {"system_id", "parent_system_id", "source", "label",
                   "feature_version", "ionic_steps", "scf_iterations_total",
                   "max_force_ry_per_bohr"}

    failures = []
    for row in stored:
        sid = row["system_id"]
        if sid not in recomputed_map:
            failures.append(f"{sid}: missing from recomputed output")
            continue
        rec = recomputed_map[sid]
        for col, stored_val in row.items():
            if col in bookkeeping:
                continue
            rec_val = rec.get(col, "")
            if stored_val == "" and rec_val == "":
                continue
            if stored_val == "" or rec_val == "":
                failures.append(
                    f"{sid}[{col}]: NaN/empty mismatch "
                    f"(stored={stored_val!r}, recomputed={rec_val!r})"
                )
                continue
            try:
                s_f, r_f = float(stored_val), float(rec_val)
            except ValueError:
                if stored_val != rec_val:
                    failures.append(f"{sid}[{col}]: string mismatch")
                continue
            if abs(s_f - r_f) > 1e-4:
                failures.append(
                    f"{sid}[{col}]: stored={s_f:.6f} recomputed={r_f:.6f} "
                    f"diff={abs(s_f - r_f):.2e}"
                )

    assert not failures, "Feature matrix not reproducible:\n" + "\n".join(failures)


@pytest.mark.parametrize("system_id,ref_ml_mean_angstrom,tol,note", [
    # Whitaker & Jeffery 1967 (Cr-C = 1.916 Å, crystal X-ray)
    ("cr_co6", 1.916, 0.05, "Whitaker 1967 Cr-C"),
    # Hedberg et al. 1979 (Ni-C = 1.838 Å, gas-phase ED)
    ("ni_co4", 1.838, 0.05, "Hedberg 1979 Ni-C"),
    # McClelland et al. 2001: 2 ax (1.810) + 3 eq (1.842) → weighted mean 1.829 Å
    ("fe_co5", 1.829, 0.05, "McClelland 2001 weighted mean"),
    # Haaland & Nilsson 1968 (Fe-C = 2.064 Å, all 10 bonds equal in D5h)
    ("ferrocene", 2.064, 0.05, "Haaland 1968 Fe-C"),
])
def test_primary_dft_ml_mean_within_dft_error_of_reference(
        system_id, ref_ml_mean_angstrom, tol, note):
    """DFT (PBE/90 Ry) M-L mean bond lengths must be within ±0.05 Å of experiment.

    PBE systematically underestimates TM-C bonds by 0.01–0.04 Å; a ±0.05 Å
    window passes expected DFT error while catching calculation errors.
    """
    import csv as _csv
    feat_path = PROJECT_ROOT / "data" / "features" / "features_v0.1.csv"
    if not feat_path.exists():
        pytest.skip("features_v0.1.csv missing")
    rows = {r["system_id"]: r
            for r in _csv.DictReader(feat_path.open(encoding="utf-8"))}
    row = rows.get(system_id)
    assert row is not None, f"{system_id} not found in features CSV"
    dft_ml = float(row["ml_mean_angstrom"])
    diff = abs(dft_ml - ref_ml_mean_angstrom)
    assert diff <= tol, (
        f"{system_id}: DFT ml_mean={dft_ml:.4f} Å, ref={ref_ml_mean_angstrom:.3f} Å "
        f"({note}), diff={diff:.4f} Å > tolerance {tol} Å"
    )


def test_feature_report_documents_coulomb_not_rac():
    """feature_report_v0.1.md must identify descriptors as Coulomb matrix eigenvalues.

    These are NOT RAC (Revised Autocorrelation) descriptors — a common TMC
    descriptor family. The report must be unambiguous to avoid misrepresentation.
    """
    report_path = PROJECT_ROOT / "reports" / "feature_report_v0.1.md"
    if not report_path.exists():
        pytest.skip("feature_report_v0.1.md missing")
    text = report_path.read_text(encoding="utf-8")
    assert "Coulomb matrix" in text, "Feature report must mention 'Coulomb matrix'"
    assert "RAC" not in text, (
        "Feature report must not claim RAC descriptors — "
        "these are Coulomb matrix eigenvalues (Rupp 2012), not RACs"
    )


def test_ferrocene_n_ligands_counts_metal_carbon_bonds():
    """ferrocene n_ligands=10 counts all 10 Fe-C bonds (5 per Cp ring).

    This is the correct M-C atom count for the Coulomb/geometric feature set,
    though chemically ferrocene has 2 ligands (two Cp rings).
    """
    import csv as _csv
    feat_path = PROJECT_ROOT / "data" / "features" / "features_v0.1.csv"
    if not feat_path.exists():
        pytest.skip("features_v0.1.csv missing")
    rows = {r["system_id"]: r
            for r in _csv.DictReader(feat_path.open(encoding="utf-8"))}
    row = rows.get("ferrocene")
    assert row is not None
    assert int(float(row["n_ligands"])) == 10, (
        "ferrocene must have n_ligands=10 (counts M-C bonds, not Cp rings)"
    )
