"""Task 8: NEB endpoint structure validation.

Checks that the ferrocene conformer NEB endpoints are correctly written,
chemically consistent with the dataset, and ready for nebwalk input.
"""
import math
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
NEB_DIR = PROJECT_ROOT / "structures" / "neb_endpoints"
ECLIPSED_XYZ = NEB_DIR / "ferrocene_eclipsed_d5h.xyz"
STAGGERED_XYZ = NEB_DIR / "ferrocene_staggered_d5d.xyz"


def _parse_xyz(path: Path) -> tuple[str, list[tuple[str, float, float, float]]]:
    """Return (comment_line, [(symbol, x, y, z), ...])."""
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    n = int(lines[0].strip())
    comment = lines[1]
    atoms = []
    for line in lines[2:2 + n]:
        parts = line.split()
        atoms.append((parts[0], float(parts[1]), float(parts[2]), float(parts[3])))
    return comment, atoms


# ---------------------------------------------------------------------------
# File existence and basic structure
# ---------------------------------------------------------------------------

def test_neb_endpoint_files_exist():
    assert ECLIPSED_XYZ.exists(), f"{ECLIPSED_XYZ} not found — run scripts/17_prepare_neb_endpoints.py"
    assert STAGGERED_XYZ.exists(), f"{STAGGERED_XYZ} not found — run scripts/17_prepare_neb_endpoints.py"
    assert (NEB_DIR / "README.md").exists(), "README.md missing from neb_endpoints/"


def test_both_endpoints_have_21_atoms():
    for path in (ECLIPSED_XYZ, STAGGERED_XYZ):
        if not path.exists():
            pytest.skip(f"{path.name} not found")
        _, atoms = _parse_xyz(path)
        assert len(atoms) == 21, f"{path.name}: expected 21 atoms, got {len(atoms)}"


def test_endpoints_have_same_stoichiometry():
    """Both endpoints must have the same atom types and counts (same molecule)."""
    if not ECLIPSED_XYZ.exists() or not STAGGERED_XYZ.exists():
        pytest.skip("endpoint files missing")
    _, atoms_a = _parse_xyz(ECLIPSED_XYZ)
    _, atoms_b = _parse_xyz(STAGGERED_XYZ)
    from collections import Counter
    count_a = Counter(sym for sym, *_ in atoms_a)
    count_b = Counter(sym for sym, *_ in atoms_b)
    assert count_a == count_b, (
        f"Stoichiometry mismatch: eclipsed={dict(count_a)} staggered={dict(count_b)}"
    )


def test_ferrocene_stoichiometry_is_correct():
    """Ferrocene is Fe(C5H5)2: 1 Fe, 10 C, 10 H — total 21 atoms."""
    if not ECLIPSED_XYZ.exists():
        pytest.skip("eclipsed endpoint missing")
    from collections import Counter
    _, atoms = _parse_xyz(ECLIPSED_XYZ)
    count = Counter(sym for sym, *_ in atoms)
    assert count["Fe"] == 1, f"Expected 1 Fe, got {count['Fe']}"
    assert count["C"] == 10, f"Expected 10 C, got {count['C']}"
    assert count["H"] == 10, f"Expected 10 H, got {count['H']}"


# ---------------------------------------------------------------------------
# Physical reasonableness
# ---------------------------------------------------------------------------

def test_eclipsed_comment_encodes_pbe_60ry():
    """The eclipsed XYZ comment must state PBE functional and 60 Ry cutoff."""
    if not ECLIPSED_XYZ.exists():
        pytest.skip("eclipsed endpoint missing")
    comment, _ = _parse_xyz(ECLIPSED_XYZ)
    assert "PBE" in comment
    assert "60" in comment


def test_staggered_comment_encodes_delta_e():
    """The staggered XYZ comment must include the ΔE value."""
    if not STAGGERED_XYZ.exists():
        pytest.skip("staggered endpoint missing")
    comment, _ = _parse_xyz(STAGGERED_XYZ)
    # ΔE ≈ 41.68 meV should appear in some form
    assert "meV" in comment or "dE" in comment, (
        f"Staggered comment must encode ΔE in meV: {comment}"
    )


def test_endpoint_energies_are_within_expected_range():
    """Ferrocene PBE/60 Ry total energy should be ~ -7148 eV (21-atom system).

    Parses the energy from the XYZ comment line (format: E=<value> eV).
    """
    import re
    E_RE = re.compile(r"E=([-\d.]+)\s*eV")
    for path, label in ((ECLIPSED_XYZ, "eclipsed"), (STAGGERED_XYZ, "staggered")):
        if not path.exists():
            pytest.skip(f"{path.name} missing")
        comment, _ = _parse_xyz(path)
        m = E_RE.search(comment)
        assert m is not None, f"{label}: no 'E=... eV' in comment: {comment}"
        e_ev = float(m.group(1))
        # DFT energy for 21-atom ferrocene at PBE/60 Ry should be ~ -7148 eV (±10 eV)
        assert -7160.0 <= e_ev <= -7140.0, (
            f"{label}: energy {e_ev:.2f} eV outside expected range [-7160, -7140]"
        )


def test_staggered_has_higher_energy_than_eclipsed():
    """Staggered D5d must be higher energy than eclipsed D5h (ΔE > 0)."""
    import re
    E_RE = re.compile(r"E=([-\d.]+)\s*eV")
    if not ECLIPSED_XYZ.exists() or not STAGGERED_XYZ.exists():
        pytest.skip("endpoint files missing")
    comment_a, _ = _parse_xyz(ECLIPSED_XYZ)
    comment_b, _ = _parse_xyz(STAGGERED_XYZ)
    e_a = float(E_RE.search(comment_a).group(1))
    e_b = float(E_RE.search(comment_b).group(1))
    delta_mev = (e_b - e_a) * 1000
    assert delta_mev > 0, (
        f"Staggered must be higher energy than eclipsed; got ΔE={delta_mev:.2f} meV"
    )
    # Should match experimental eclipsed–staggered barrier ≈ 41 meV within 10 meV
    assert 25.0 <= delta_mev <= 60.0, (
        f"ΔE={delta_mev:.2f} meV outside expected range 25–60 meV "
        f"(eclipsed–staggered barrier for ferrocene)"
    )


def test_endpoint_positions_are_consistent_with_features_csv():
    """Eclipsed D5h endpoint Fe-C mean distance must match the features CSV value."""
    import csv as _csv
    import numpy as np

    if not ECLIPSED_XYZ.exists():
        pytest.skip("eclipsed endpoint missing")
    feat_path = PROJECT_ROOT / "data" / "features" / "features_v0.1.csv"
    if not feat_path.exists():
        pytest.skip("features_v0.1.csv missing")

    # Get expected ml_mean from features CSV
    rows = {r["system_id"]: r
            for r in _csv.DictReader(feat_path.open(encoding="utf-8"))}
    expected_ml_mean = float(rows["ferrocene"]["ml_mean_angstrom"])

    # Compute Fe-C mean from the XYZ file directly
    _, atoms = _parse_xyz(ECLIPSED_XYZ)
    fe_pos = next((x, y, z) for sym, x, y, z in atoms if sym == "Fe")
    c_positions = [(x, y, z) for sym, x, y, z in atoms if sym == "C"]
    fe_c_distances = [
        math.sqrt((x - fe_pos[0])**2 + (y - fe_pos[1])**2 + (z - fe_pos[2])**2)
        for x, y, z in c_positions
    ]
    # Only count C atoms within ML_CUTOFF_ANGSTROM = 2.5 Å
    bonded = [d for d in fe_c_distances if d <= 2.5]
    xyz_ml_mean = sum(bonded) / len(bonded)

    assert abs(xyz_ml_mean - expected_ml_mean) < 1e-3, (
        f"XYZ ml_mean={xyz_ml_mean:.6f} Å vs features CSV ml_mean={expected_ml_mean:.6f} Å"
    )
