"""Phase 0 — concurrent ledger write/read integrity test.

Spawns 4 workers writing 5 records each (20 total) via multiprocessing.Pool.
Verifies:
  - Zero lost or corrupted lines
  - All 20 records survive
  - Every line is valid JSON
  - No interleaved partial writes (each line decodes cleanly)
"""
from __future__ import annotations

import json
import multiprocessing
import tempfile
from pathlib import Path

import pytest

from actistruct.core.ledger import append_record, make_record, read_records


# ── helpers ───────────────────────────────────────────────────────────────────

def _worker_write(args: tuple) -> None:
    """Write 5 records from one worker process to the shared ledger."""
    ledger_path, worker_id = args
    for i in range(5):
        rec = make_record(
            system="CaAlN2",
            fidelity="low",
            params={"worker": worker_id, "record": i, "ecutwfc": 30.0},
            energy=-(worker_id * 10 + i) * 1.23,
            converged=True,
        )
        append_record(rec, ledger_path=Path(ledger_path))


# ── tests ─────────────────────────────────────────────────────────────────────

def test_concurrent_writes_no_lost_records():
    """20 concurrent writes from 4 workers — all records must survive intact."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ledger_path = Path(tmpdir) / "run_ledger.jsonl"

        args = [(str(ledger_path), worker_id) for worker_id in range(4)]

        with multiprocessing.Pool(processes=4) as pool:
            pool.map(_worker_write, args)

        records = read_records(ledger_path)
        assert len(records) == 20, (
            f"Expected 20 records; got {len(records)}. "
            "Some writes were lost or lines merged."
        )


def test_all_lines_valid_json():
    """Every raw line in the ledger must be independently parseable."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ledger_path = Path(tmpdir) / "run_ledger.jsonl"

        args = [(str(ledger_path), worker_id) for worker_id in range(4)]
        with multiprocessing.Pool(processes=4) as pool:
            pool.map(_worker_write, args)

        with ledger_path.open("r", encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]

        assert len(lines) == 20
        for i, line in enumerate(lines):
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                pytest.fail(f"Line {i+1} is not valid JSON: {exc}\nContent: {line!r}")
            assert isinstance(obj, dict), f"Line {i+1} decoded to non-dict: {type(obj)}"


def test_record_schema_fields_present():
    """Each record must contain all mandatory ledger schema fields."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ledger_path = Path(tmpdir) / "run_ledger.jsonl"
        rec = make_record(
            system="CaAlN2",
            fidelity="high",
            params={"ecutwfc": 60.0, "kpts": [6, 6, 6]},
            energy=-134.5,
            converged=True,
            wall_time_s=42.7,
        )
        append_record(rec, ledger_path=ledger_path)

        records = read_records(ledger_path)
        assert len(records) == 1
        r = records[0]

        required = {
            "timestamp", "system", "candidate_id", "fidelity",
            "params", "energy", "converged", "failure_type",
            "actions_taken", "wall_time_s",
        }
        missing = required - set(r.keys())
        assert not missing, f"Missing ledger fields: {missing}"
        assert r["system"] == "CaAlN2"
        assert r["fidelity"] == "high"
        assert r["converged"] is True
        assert r["energy"] == pytest.approx(-134.5)


def test_empty_ledger_returns_empty_list():
    """read_records on a non-existent path must return [] not raise."""
    records = read_records(Path("/nonexistent/path/run_ledger.jsonl"))
    assert records == []


def test_failed_record_schema():
    """A failed (non-converged) record must store failure_type and empty energy."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ledger_path = Path(tmpdir) / "run_ledger.jsonl"
        rec = make_record(
            system="CaAlN2",
            fidelity="low",
            params={"ecutwfc": 30.0},
            energy=None,
            converged=False,
            failure_type="SCF_CONVERGENCE",
            actions_taken=["soften_mixing", "increase_degauss"],
        )
        append_record(rec, ledger_path=ledger_path)

        records = read_records(ledger_path)
        assert len(records) == 1
        r = records[0]
        assert r["converged"] is False
        assert r["energy"] is None
        assert r["failure_type"] == "SCF_CONVERGENCE"
        assert "soften_mixing" in r["actions_taken"]
