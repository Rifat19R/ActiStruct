"""Phase 3 — Dashboard data loader and figure generation tests.

Tests
-----
1. Empty ledger → load_ledger returns empty DataFrame (correct columns, no crash).
2. Populated ledger → all required columns present, types correct.
3. get_summary_stats on empty DataFrame → returns zero-count dict (no crash).
4. get_summary_stats on populated DataFrame → correct totals.
5. Plotly figure generation succeeds on small synthetic ledger sample.
6. atoms_to_xyz_string produces parseable XYZ output.
"""
from __future__ import annotations

import json
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from actistruct.dashboard.data_loader import (
    REQUIRED_COLUMNS,
    atoms_to_xyz_string,
    get_summary_stats,
    load_ledger,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _write_ledger(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")


def _make_record(
    system: str = "CaAlN2",
    fidelity: str = "high",
    energy: float | None = -134.5,
    converged: bool = True,
    failure_type: str | None = None,
) -> dict:
    return {
        "timestamp":    datetime.now(timezone.utc).isoformat(),
        "system":       system,
        "candidate_id": str(uuid.uuid4()),
        "fidelity":     fidelity,
        "params":       {"ecutwfc": 60.0},
        "energy":       energy,
        "converged":    converged,
        "failure_type": failure_type,
        "actions_taken": [],
        "wall_time_s":  42.3,
    }


# ── Test 1: Empty ledger ──────────────────────────────────────────────────────

def test_load_empty_ledger_nonexistent_path():
    """Missing ledger path must return empty DataFrame, not raise."""
    df = load_ledger(Path("/nonexistent/path/run_ledger.jsonl"))
    assert isinstance(df, pd.DataFrame)
    assert df.empty
    # Correct schema columns must be present even in the empty case.
    for col in REQUIRED_COLUMNS:
        assert col in df.columns, f"Missing column in empty schema: {col}"


def test_load_empty_ledger_zero_byte_file():
    """Zero-byte ledger file must also return empty DataFrame."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "run_ledger.jsonl"
        path.touch()
        df = load_ledger(path)
        assert df.empty


# ── Test 2: Populated ledger ──────────────────────────────────────────────────

def test_load_populated_ledger_columns_correct():
    """Populated ledger must contain all required columns."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "run_ledger.jsonl"
        _write_ledger(path, [
            _make_record(converged=True,  energy=-134.5),
            _make_record(converged=False, energy=None, failure_type="SCF_CONVERGENCE"),
        ])
        df = load_ledger(path)
        assert len(df) == 2
        for col in REQUIRED_COLUMNS:
            assert col in df.columns, f"Required column missing: {col}"


def test_load_populated_ledger_types():
    """converged must be bool-compatible; energy must be float-compatible."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "run_ledger.jsonl"
        _write_ledger(path, [_make_record(converged=True, energy=-100.0)])
        df = load_ledger(path)
        assert bool(df.iloc[0]["converged"]) is True
        assert abs(float(df.iloc[0]["energy"]) - (-100.0)) < 1e-6


# ── Test 3: Summary stats on empty ───────────────────────────────────────────

def test_summary_stats_empty_df_no_crash():
    """get_summary_stats on empty DataFrame must return zero-count dict, not crash."""
    stats = get_summary_stats(pd.DataFrame(columns=sorted(REQUIRED_COLUMNS)))
    assert stats["total_runs"] == 0
    assert stats["converged"]  == 0
    assert stats["failed"]     == 0
    assert stats["convergence_rate_pct"] == 0.0
    assert stats["systems"] == []


# ── Test 4: Summary stats on populated data ───────────────────────────────────

def test_summary_stats_correct_totals():
    """Verify convergence rate and failure type counts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "run_ledger.jsonl"
        _write_ledger(path, [
            _make_record(converged=True),
            _make_record(converged=True),
            _make_record(converged=False, failure_type="SCF_CONVERGENCE"),
            _make_record(converged=False, failure_type="SCF_CONVERGENCE"),
            _make_record(converged=False, failure_type="GEOMETRY_CRASH"),
        ])
        df = load_ledger(path)
        stats = get_summary_stats(df)

        assert stats["total_runs"] == 5
        assert stats["converged"]  == 2
        assert stats["failed"]     == 3
        assert abs(stats["convergence_rate_pct"] - 40.0) < 0.1
        assert stats["failure_types"].get("SCF_CONVERGENCE") == 2
        assert stats["failure_types"].get("GEOMETRY_CRASH")  == 1


# ── Test 5: Plotly figure generation ─────────────────────────────────────────

def test_plotly_figure_on_synthetic_data():
    """Plotly energy scatter must build without error on small synthetic data."""
    import plotly.express as px

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "run_ledger.jsonl"
        records = [
            _make_record(energy=-130.0 + i * 0.5, converged=True, fidelity="low")
            for i in range(5)
        ]
        _write_ledger(path, records)
        df = load_ledger(path)
        converged_df = df[df["converged"]].copy()
        converged_df["run_index"] = range(1, len(converged_df) + 1)

        fig = px.scatter(
            converged_df,
            x="run_index",
            y="energy",
            color="fidelity",
            title="Test energy scatter",
        )
        assert fig is not None
        assert len(fig.data) > 0


# ── Test 6: XYZ string output ─────────────────────────────────────────────────

def test_atoms_to_xyz_string():
    """atoms_to_xyz_string must produce a parseable XYZ block."""
    from ase import Atoms

    atoms = Atoms(
        symbols=["Ca", "Al", "N", "N"],
        positions=[
            [0.0, 0.0, 0.0],
            [1.575, 1.575, 2.5],
            [0.0, 0.0, 1.875],
            [1.575, 1.575, 4.375],
        ],
        cell=[3.15, 3.15, 5.0],
        pbc=True,
    )
    xyz = atoms_to_xyz_string(atoms)
    lines = xyz.strip().splitlines()

    # First line: atom count.
    assert int(lines[0].strip()) == 4
    # Second line: comment (can be anything).
    assert len(lines[1]) > 0
    # Remaining lines: one per atom.
    assert len(lines) == 6   # 2 header + 4 atoms
    for atom_line in lines[2:]:
        parts = atom_line.split()
        assert len(parts) == 4, f"Expected 'Symbol x y z', got: {atom_line!r}"
        symbol = parts[0]
        x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
        assert symbol in {"Ca", "Al", "N"}
