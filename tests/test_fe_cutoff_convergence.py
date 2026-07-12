"""Tests for the Fe(CO)5 ecutwfc cutoff convergence analysis — Task 1.5.

These tests verify:
1. The convergence CSV exists and has the expected schema.
2. All 3 ecutwfc runs converged (failed runs are a hard stop).
3. Convergence criteria were applied correctly.
4. The recommended cutoff is a member of {60, 75, 90} Ry.
5. The delta columns are computed correctly vs the 90 Ry reference.
6. The report and figure files were written.
7. The qe_molecule_settings.yaml was updated consistently.
8. The dataset fe_cutoff_flag columns are populated.

Slow tests (those that re-run the analysis) are marked with @pytest.mark.slow.
Run with:  pytest tests/test_fe_cutoff_convergence.py -v
Skip slow: pytest tests/test_fe_cutoff_convergence.py -v -m "not slow"
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

CONV_CSV = PROJECT_ROOT / "data" / "processed" / "fe_cutoff_convergence.csv"
REPORT = PROJECT_ROOT / "reports" / "fe_cutoff_convergence_v0.1.md"
FIGURE = PROJECT_ROOT / "reports" / "figures" / "fe_cutoff_convergence.png"
QE_SETTINGS = PROJECT_ROOT / "configs" / "qe_molecule_settings.yaml"
DATASET_CSV = PROJECT_ROOT / "data" / "processed" / "full_dataset_v0.2.csv"
OUTPUT_DIR = PROJECT_ROOT / "qe" / "outputs" / "cutoff_test"

EXPECTED_CUTOFFS = [60, 75, 90]
ENERGY_THRESHOLD_MEV = 1.0
BOND_THRESHOLD_MANG = 5.0

EXPECTED_CSV_COLS = {
    "ecutwfc_ry", "ecutrho_ry",
    "total_energy_ev", "energy_per_atom_ev",
    "fe_c_axial_ang", "fe_c_equatorial_ang",
    "max_force_ev_ang", "n_scf_steps", "n_bfgs_steps",
    "walltime_sec", "converged",
    "delta_energy_per_atom_mev", "delta_fe_c_axial_mang", "delta_fe_c_equatorial_mang",
    "passes_energy_threshold", "passes_bond_threshold", "passes_both",
}


def _load_conv_csv() -> list[dict]:
    return list(csv.DictReader(CONV_CSV.open(encoding="utf-8")))


# ──────────────────────────────────────────────
# Output file existence
# ──────────────────────────────────────────────

@pytest.mark.parametrize("ec", EXPECTED_CUTOFFS)
def test_qe_output_file_exists(ec):
    f = OUTPUT_DIR / f"fe_co5_cutoff_{ec}.out"
    assert f.exists(), (
        f"QE output for ecutwfc={ec} Ry not found: {f}. "
        "Run scripts/run_fe_cutoff_batch.sh first."
    )


@pytest.mark.parametrize("ec", EXPECTED_CUTOFFS)
def test_qe_output_is_non_empty(ec):
    f = OUTPUT_DIR / f"fe_co5_cutoff_{ec}.out"
    if not f.exists():
        pytest.skip(f"Output not yet generated: {f}")
    assert f.stat().st_size > 0, (
        f"QE output for ecutwfc={ec} Ry is empty. pw.x may have failed — "
        f"check {OUTPUT_DIR / f'fe_co5_cutoff_{ec}.err'}"
    )


@pytest.mark.parametrize("ec", EXPECTED_CUTOFFS)
def test_qe_run_converged(ec):
    f = OUTPUT_DIR / f"fe_co5_cutoff_{ec}.out"
    if not f.exists() or f.stat().st_size == 0:
        pytest.skip(f"Output not yet generated or empty: {f}")
    text = f.read_text(encoding="utf-8", errors="replace")
    assert "bfgs converged" in text.lower(), (
        f"BFGS geometry optimization did NOT converge for ecutwfc={ec} Ry. "
        "Do NOT update settings or proceed to Task 2 until all 3 runs converge."
    )


# ──────────────────────────────────────────────
# Convergence CSV
# ──────────────────────────────────────────────

def test_conv_csv_exists():
    assert CONV_CSV.exists(), (
        f"Convergence CSV not found: {CONV_CSV}. "
        "Run scripts/15_fe_cutoff_convergence.py first."
    )


def test_conv_csv_has_expected_columns():
    if not CONV_CSV.exists():
        pytest.skip("CSV not generated yet")
    rows = _load_conv_csv()
    assert rows, "CSV is empty"
    missing = EXPECTED_CSV_COLS - set(rows[0].keys())
    assert not missing, f"CSV missing columns: {missing}"


def test_conv_csv_has_three_rows():
    if not CONV_CSV.exists():
        pytest.skip("CSV not generated yet")
    rows = _load_conv_csv()
    assert len(rows) == 3, f"Expected 3 rows (one per ecutwfc), got {len(rows)}"


def test_conv_csv_ecutwfc_values():
    if not CONV_CSV.exists():
        pytest.skip("CSV not generated yet")
    rows = _load_conv_csv()
    actual = sorted(int(r["ecutwfc_ry"]) for r in rows)
    assert actual == EXPECTED_CUTOFFS, (
        f"Expected ecutwfc values {EXPECTED_CUTOFFS}, got {actual}"
    )


def test_conv_csv_ecutrho_is_8x_ecutwfc():
    if not CONV_CSV.exists():
        pytest.skip("CSV not generated yet")
    for row in _load_conv_csv():
        ec = int(row["ecutwfc_ry"])
        er = int(row["ecutrho_ry"])
        assert er == ec * 8, (
            f"ecutwfc={ec} should have ecutrho={ec * 8}, got {er}"
        )


def test_conv_csv_all_runs_converged():
    if not CONV_CSV.exists():
        pytest.skip("CSV not generated yet")
    not_converged = [
        r["ecutwfc_ry"]
        for r in _load_conv_csv()
        if r.get("converged", "").lower() != "true"
    ]
    assert not not_converged, (
        f"Runs that did NOT converge: ecutwfc={not_converged} Ry. "
        "Task 1.5 cannot be completed until all 3 runs converge."
    )


def test_conv_csv_ref_row_has_no_deltas():
    """The 90 Ry reference row should have None/empty deltas (it is the reference)."""
    if not CONV_CSV.exists():
        pytest.skip("CSV not generated yet")
    ref_rows = [r for r in _load_conv_csv() if int(r["ecutwfc_ry"]) == 90]
    assert ref_rows, "No 90 Ry row in CSV"
    ref = ref_rows[0]
    # Delta vs itself must be 0 or empty
    delta = ref.get("delta_energy_per_atom_mev", "")
    if delta not in ("", "None", "nan", None):
        assert abs(float(delta)) < 1e-6, (
            f"90 Ry delta should be ~0 or empty; got {delta}"
        )


def test_conv_csv_delta_energy_threshold():
    """For any passing row: |ΔE/atom| < 1 meV/atom."""
    if not CONV_CSV.exists():
        pytest.skip("CSV not generated yet")
    for row in _load_conv_csv():
        if row.get("passes_energy_threshold", "").lower() == "true":
            delta = row.get("delta_energy_per_atom_mev")
            if delta not in ("", "None", "nan", None):
                assert abs(float(delta)) < ENERGY_THRESHOLD_MEV, (
                    f"ecutwfc={row['ecutwfc_ry']}: passes_energy_threshold=True "
                    f"but |ΔE/atom|={abs(float(delta)):.3f} ≥ {ENERGY_THRESHOLD_MEV} meV/atom"
                )


def test_conv_csv_delta_bond_threshold():
    """For any passing row: |Δd(Fe-C)| < 5 mÅ for both axial and equatorial."""
    if not CONV_CSV.exists():
        pytest.skip("CSV not generated yet")
    for row in _load_conv_csv():
        if row.get("passes_bond_threshold", "").lower() == "true":
            for col in ("delta_fe_c_axial_mang", "delta_fe_c_equatorial_mang"):
                val = row.get(col)
                if val not in ("", "None", "nan", None):
                    assert abs(float(val)) < BOND_THRESHOLD_MANG, (
                        f"ecutwfc={row['ecutwfc_ry']}: passes_bond_threshold=True "
                        f"but |{col}|={abs(float(val)):.2f} ≥ {BOND_THRESHOLD_MANG} mÅ"
                    )


def test_conv_csv_passes_both_consistency():
    """passes_both == passes_energy_threshold AND passes_bond_threshold."""
    if not CONV_CSV.exists():
        pytest.skip("CSV not generated yet")
    for row in _load_conv_csv():
        both = row.get("passes_both", "").lower() == "true"
        energy = row.get("passes_energy_threshold", "").lower() == "true"
        bond = row.get("passes_bond_threshold", "").lower() == "true"
        assert both == (energy and bond), (
            f"ecutwfc={row['ecutwfc_ry']}: passes_both={both} but "
            f"passes_energy={energy}, passes_bond={bond} — inconsistent"
        )


def test_conv_csv_energies_decrease_with_cutoff():
    """Total energy should decrease (become more negative) as ecutwfc increases."""
    if not CONV_CSV.exists():
        pytest.skip("CSV not generated yet")
    rows = sorted(_load_conv_csv(), key=lambda r: int(r["ecutwfc_ry"]))
    energies = []
    for r in rows:
        e = r.get("total_energy_ev")
        if e in ("", "None", "nan", None):
            pytest.skip("Some energies missing; cannot verify monotonicity")
        energies.append(float(e))
    for i in range(1, len(energies)):
        assert energies[i] <= energies[i - 1] + 0.1, (
            f"Energy should decrease with ecutwfc: "
            f"ec={EXPECTED_CUTOFFS[i-1]}→{EXPECTED_CUTOFFS[i]}: "
            f"{energies[i-1]:.4f}→{energies[i]:.4f} eV (not monotone within 0.1 eV tolerance)"
        )


# ──────────────────────────────────────────────
# Report and figure
# ──────────────────────────────────────────────

def test_report_file_exists():
    assert REPORT.exists(), (
        f"Report not found: {REPORT}. "
        "Run scripts/15_fe_cutoff_convergence.py first."
    )


def test_report_contains_recommended_cutoff_section():
    if not REPORT.exists():
        pytest.skip("Report not generated yet")
    text = REPORT.read_text(encoding="utf-8")
    assert "## 4. Recommendation" in text, (
        "Report is missing the '## 4. Recommendation' section"
    )


def test_report_contains_convergence_table():
    if not REPORT.exists():
        pytest.skip("Report not generated yet")
    text = REPORT.read_text(encoding="utf-8")
    assert "### 3.1 Convergence table" in text, (
        "Report is missing the convergence table section"
    )
    # Should have rows for all 4 cutoffs
    for ec in EXPECTED_CUTOFFS:
        assert str(ec) in text, f"ecutwfc={ec} Ry not found in report text"


def test_figure_file_exists():
    assert FIGURE.exists(), (
        f"Convergence figure not found: {FIGURE}. "
        "Run scripts/15_fe_cutoff_convergence.py (requires matplotlib) first."
    )


# ──────────────────────────────────────────────
# QE settings update
# ──────────────────────────────────────────────

def test_qe_settings_has_cutoff_history_or_verification_comment():
    """After Task 1.5, qe_molecule_settings.yaml must document the cutoff decision."""
    if not QE_SETTINGS.exists():
        pytest.skip("qe_molecule_settings.yaml not found")
    text = QE_SETTINGS.read_text(encoding="utf-8")
    has_history = "cutoff_history" in text
    has_comment = "fe_cutoff_convergence" in text
    assert has_history or has_comment, (
        "qe_molecule_settings.yaml was not updated by Task 1.5 — "
        "should contain 'cutoff_history' or 'fe_cutoff_convergence' comment"
    )


def test_qe_settings_ecutwfc_matches_recommendation():
    """The ecutwfc_ry in settings must match the recommended cutoff from the CSV."""
    if not CONV_CSV.exists() or not QE_SETTINGS.exists():
        pytest.skip("CSV or settings not available")
    rows = _load_conv_csv()
    passing = [
        int(r["ecutwfc_ry"])
        for r in rows
        if r.get("passes_both", "").lower() == "true" and int(r["ecutwfc_ry"]) != 90
    ]
    recommended = min(passing) if passing else 90

    cfg = yaml.safe_load(QE_SETTINGS.read_text(encoding="utf-8"))
    # Navigate to ecutwfc_ry — it could be at top level or under a 'defaults' key
    ecutwfc = None
    for section in cfg.values():
        if isinstance(section, dict) and "ecutwfc_ry" in section:
            ecutwfc = section["ecutwfc_ry"]
            break
    if ecutwfc is None and "ecutwfc_ry" in cfg:
        ecutwfc = cfg["ecutwfc_ry"]

    if ecutwfc is not None:
        assert int(ecutwfc) == recommended, (
            f"qe_molecule_settings.yaml has ecutwfc_ry={ecutwfc} but "
            f"recommended cutoff from CSV is {recommended} Ry"
        )


# ──────────────────────────────────────────────
# Dataset update
# ──────────────────────────────────────────────

def test_dataset_fe_cutoff_flag_updated_after_task15():
    """After Task 1.5, Fe row cutoff flags should NOT say 'cutoff convergence test NOT performed'."""
    if not DATASET_CSV.exists():
        pytest.skip("Dataset CSV not found")
    rows = list(csv.DictReader(DATASET_CSV.open(encoding="utf-8")))
    fe_systems = {"ferrocene", "fe_co5"}
    for row in rows:
        sid = row["system_id"]
        is_fe = any(sid == s or sid.startswith(s + "__") for s in fe_systems)
        if not is_fe:
            continue
        flag = row.get("fe_cutoff_flag", "")
        assert "has NOT been performed" not in flag and "NOT been performed" not in flag, (
            f"Row {sid} still has pre-Task-1.5 placeholder flag: {flag!r}. "
            "Run scripts/15_fe_cutoff_convergence.py to update the dataset."
        )


def test_dataset_fe_cutoff_flag_present_after_task15():
    """All Fe rows must have non-empty cutoff flag after Task 1.5."""
    if not DATASET_CSV.exists():
        pytest.skip("Dataset CSV not found")
    rows = list(csv.DictReader(DATASET_CSV.open(encoding="utf-8")))
    fe_systems = {"ferrocene", "fe_co5"}
    for row in rows:
        sid = row["system_id"]
        is_fe = any(sid == s or sid.startswith(s + "__") for s in fe_systems)
        if is_fe:
            flag = row.get("fe_cutoff_flag", "")
            assert flag.strip(), f"Row {sid} has empty fe_cutoff_flag after Task 1.5"


# ──────────────────────────────────────────────
# Slow: re-run analysis from scratch
# ──────────────────────────────────────────────

@pytest.mark.slow
def test_analysis_script_runs_dry_run():
    """Smoke test: the analysis script runs without errors in --dry-run mode."""
    import subprocess
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "15_fe_cutoff_convergence.py"), "--dry-run"],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT)
    )
    assert result.returncode == 0, (
        f"15_fe_cutoff_convergence.py --dry-run failed:\n{result.stderr}"
    )
