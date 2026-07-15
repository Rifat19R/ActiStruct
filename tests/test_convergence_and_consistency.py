"""Task 6: Scientific convergence and self-consistency checks on the dataset.

Key distinction: 'max_force_ry_per_bohr' in the dataset is QE's "Total force"
= sqrt(sum_i sum_{alpha in xyz} |F_{i,alpha}|^2), NOT the per-atom maximum force.
QE's forc_conv_thr applies to the largest per-atom force component, which is a
different quantity. Trust 'convergence_status' (set from "bfgs converged" in the
QE output) as the authoritative convergence flag.
"""
import csv
import math
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FULL_DS_PATH = PROJECT_ROOT / "data" / "processed" / "full_dataset_v0.2.csv"
FEAT_PATH = PROJECT_ROOT / "data" / "features" / "features_v0.1.csv"

PRIMARY_IDS = {"cr_co6", "fe_co5", "ferrocene", "ni_co4"}
PRIMARY_ATOM_COUNTS = {
    "cr_co6": 13,    # Cr + 6(CO)
    "fe_co5": 11,    # Fe + 5(CO)
    "ferrocene": 21,  # Fe + 2×C5H5
    "ni_co4": 9,     # Ni + 4(CO)
}


def _load_full_dataset() -> list[dict]:
    if not FULL_DS_PATH.exists():
        pytest.skip("full_dataset_v0.2.csv missing")
    with FULL_DS_PATH.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _load_features() -> dict[str, dict]:
    if not FEAT_PATH.exists():
        pytest.skip("features_v0.1.csv missing")
    with FEAT_PATH.open(encoding="utf-8") as f:
        return {r["system_id"]: r for r in csv.DictReader(f)}


# ---------------------------------------------------------------------------
# BFGS convergence
# ---------------------------------------------------------------------------

def test_all_primary_systems_bfgs_converged():
    """All 4 primary systems must have convergence_status='converged'."""
    rows = {r["system_id"]: r for r in _load_full_dataset()
            if r["system_id"] in PRIMARY_IDS}
    assert len(rows) == 4, f"Expected 4 primary systems, got {len(rows)}"
    for sid, r in rows.items():
        assert r["convergence_status"] == "converged", (
            f"{sid}: convergence_status='{r['convergence_status']}' — BFGS did not converge"
        )


def test_all_candidate_systems_bfgs_converged():
    """All 12 candidate (perturbed) systems must have convergence_status='converged'."""
    all_rows = _load_full_dataset()
    candidates = [r for r in all_rows if "__" in r["system_id"]]
    assert len(candidates) == 12, f"Expected 12 candidates, got {len(candidates)}"
    failed = [r["system_id"] for r in candidates if r["convergence_status"] != "converged"]
    assert not failed, f"Candidates not converged: {failed}"


# ---------------------------------------------------------------------------
# Force sanity (total RMS force, not per-atom max)
# ---------------------------------------------------------------------------

def test_total_rms_force_within_sanity_bounds_for_all_systems():
    """QE 'Total force' (= sqrt(sum|F_i|^2)) must be < 0.001 Ry/bohr for all 16.

    This is NOT the same as forc_conv_thr=0.0001; see module docstring.
    The 0.001 bound is 10× larger than forc_conv_thr and flags only pathological
    non-convergence or parsing errors, not force-threshold policy.
    """
    rows = _load_full_dataset()
    violations = []
    for r in rows:
        mf = r.get("max_force_ry_per_bohr", "")
        if not mf:
            continue
        try:
            f = float(mf)
        except ValueError:
            continue
        if f >= 0.001:
            violations.append(f"{r['system_id']}: total_force={f:.4e} >= 0.001 Ry/bohr")
    assert not violations, "\n".join(violations)


def test_max_force_column_parsed_from_qe_total_force_keyword():
    """'max_force_ry_per_bohr' is extracted from QE's 'Total force' keyword.

    Documents the naming caveat: this is RMS, not per-atom maximum. The test
    checks the parser's regex so future edits cannot silently break this invariant.
    """
    from _load import load_script
    parser = load_script("07_parse_qe_outputs.py")
    pattern = parser.TOTAL_FORCE_RE.pattern
    assert "Total force" in pattern, (
        f"max_force_ry_per_bohr must be parsed from QE 'Total force'; got: {pattern}"
    )


# ---------------------------------------------------------------------------
# Atom counts and stoichiometry
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("system_id,expected_n", sorted(PRIMARY_ATOM_COUNTS.items()))
def test_primary_atom_counts_match_stoichiometry(system_id, expected_n):
    """Atom count for each primary system must match the expected stoichiometry."""
    import json
    rows = {r["system_id"]: r for r in _load_full_dataset()}
    row = rows.get(system_id)
    assert row is not None, f"{system_id} not found in full_dataset"
    pos = json.loads(row["final_positions_angstrom"])
    assert len(pos) == expected_n, (
        f"{system_id}: expected {expected_n} atoms, got {len(pos)}"
    )


# ---------------------------------------------------------------------------
# Energy sanity
# ---------------------------------------------------------------------------

def test_all_final_energies_are_negative_ry():
    """DFT total energies must be negative for all 16 relaxed structures."""
    rows = _load_full_dataset()
    bad = []
    for r in rows:
        e_str = r.get("final_energy_ry", "")
        if not e_str:
            bad.append(f"{r['system_id']}: missing energy")
            continue
        e = float(e_str)
        if e >= 0:
            bad.append(f"{r['system_id']}: final_energy_ry={e:.4f} (expected < 0)")
    assert not bad, "\n".join(bad)


# ---------------------------------------------------------------------------
# Candidate ΔE physical ordering
# ---------------------------------------------------------------------------

def test_ring_rotation_is_largest_delta_e_in_ferrocene_family():
    """ferrocene ring rotation by +36° (toward staggered D5d) must cost the most energy
    among the 3 ferrocene candidates. The optimized D5h-D5d conformer energy
    difference should be on the same scale as ferrocene's experimental rotational
    barrier (~4 kJ/mol, ~41 meV), but is not itself a computed barrier.
    """
    feats = _load_features()
    ring_rot = feats.get("ferrocene__ring2_rotation_deg__+36")
    others = [
        ("ferrocene__cc_bond__-0.03", feats.get("ferrocene__cc_bond__-0.03")),
        ("ferrocene__fe_cp_dist__-0.05", feats.get("ferrocene__fe_cp_dist__-0.05")),
    ]
    assert ring_rot is not None, "ferrocene__ring2_rotation_deg__+36 missing from features"
    ring_de = float(ring_rot["delta_e_meV"])

    for sid, row in others:
        if row is None or not row.get("delta_e_meV"):
            pytest.skip(f"{sid} missing delta_e_meV")
        other_de = float(row["delta_e_meV"])
        assert ring_de > other_de, (
            f"ring rotation ΔE={ring_de:.2f} meV not > {sid} ΔE={other_de:.2f} meV"
        )

    # Sanity range: same scale as experimental eclipsed-staggered rotation
    # (~4-9 kJ/mol -> 41-93 meV), without claiming a computed barrier.
    assert 20.0 <= ring_de <= 150.0, (
        f"ring rotation ΔE={ring_de:.2f} meV outside expected range 20–150 meV "
        f"(expected ferrocene conformer energy scale)"
    )


def test_same_basin_candidates_have_near_zero_delta_e():
    """Candidates that relax back to the primary basin must have |ΔE| < 1 meV.

    Both ferrocene__fe_cp_dist__-0.05 and cr_co6__axial_stretch__-0.05 returned
    to the same energy minimum, confirmed by ΔE ≈ 0 in prior analysis.
    """
    feats = _load_features()
    same_basin = ["ferrocene__fe_cp_dist__-0.05", "cr_co6__axial_stretch__-0.05"]
    for sid in same_basin:
        row = feats.get(sid)
        if row is None or not row.get("delta_e_meV"):
            pytest.skip(f"{sid} missing delta_e_meV")
        de = abs(float(row["delta_e_meV"]))
        assert de < 1.0, (
            f"{sid}: |ΔE|={de:.4f} meV — expected < 1 meV for a same-basin candidate"
        )


def test_no_candidate_has_unphysically_large_delta_e():
    """No candidate should deviate from its parent by more than 500 meV.

    All 12 perturbations are small structural tweaks; energies > 500 meV
    would indicate a calculation error, a wrong parent reference, or a
    dramatically different bonding topology.
    """
    feats = _load_features()
    violations = []
    for sid, row in feats.items():
        if "__" not in sid:
            continue
        de_str = row.get("delta_e_meV", "")
        if not de_str:
            continue
        de = abs(float(de_str))
        if de > 500.0:
            violations.append(f"{sid}: |ΔE|={de:.1f} meV")
    assert not violations, "Unphysically large ΔE:\n" + "\n".join(violations)
