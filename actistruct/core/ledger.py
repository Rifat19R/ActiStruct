"""Append-only JSONL run ledger for v2 active learning experiments.

One JSON object per line, one line per DFT attempt (converged or failed).
Uses the same O_CREAT | O_EXCL atomic-lock pattern as atomic_cache.py so
concurrent Pool workers never interleave partial writes.

NTFS/SQLite warning: do not move this to SQLite under /mnt/d/ with concurrent
writers — that reproduces a known NTFS locking bug. Only the JSONL file is
written concurrently; if SQL queries are needed for the dashboard (Phase 3),
use compile_db.py to build a read-only SQLite mirror under the native Linux
home directory.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Default ledger lives inside the package data directory.
_HERE = Path(__file__).resolve().parent.parent   # actistruct/
DEFAULT_LEDGER_PATH = _HERE / "data" / "run_ledger.jsonl"


def _acquire_lock(lock_path: Path, timeout: float = 60.0, poll: float = 0.05) -> int:
    start = time.time()
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_RDWR)
            os.write(fd, str(os.getpid()).encode())
            return fd
        except FileExistsError:
            if time.time() - start > timeout:
                raise TimeoutError(f"Ledger lock timeout: {lock_path}")
            time.sleep(poll)


def _release_lock(fd: int, lock_path: Path) -> None:
    try:
        os.close(fd)
    finally:
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def append_record(
    record: dict[str, Any],
    ledger_path: Path = DEFAULT_LEDGER_PATH,
    lock_path: Path | None = None,
) -> None:
    """Atomically append one record as a JSON line to the ledger.

    Safe to call from multiple concurrent processes — each write is protected
    by the O_CREAT|O_EXCL lock and a single f.write() call so lines are never
    interleaved.
    """
    if lock_path is None:
        lock_path = ledger_path.with_suffix(".lock")

    ledger_path.parent.mkdir(parents=True, exist_ok=True)

    # Ensure mandatory fields are present.
    record = dict(record)
    if "timestamp" not in record:
        record["timestamp"] = datetime.now(timezone.utc).isoformat()
    if "candidate_id" not in record:
        record["candidate_id"] = str(uuid.uuid4())

    line = json.dumps(record, ensure_ascii=False) + "\n"

    fd_lock = _acquire_lock(lock_path)
    try:
        with ledger_path.open("a", encoding="utf-8") as f:
            f.write(line)
    finally:
        _release_lock(fd_lock, lock_path)


def read_records(
    ledger_path: Path = DEFAULT_LEDGER_PATH,
) -> list[dict[str, Any]]:
    """Read all records from the ledger.

    Returns an empty list if the ledger file does not exist yet (normal at
    the start of a campaign). Raises ValueError on a corrupted line so the
    caller knows the file needs repair rather than silently skipping data.
    """
    if not ledger_path.exists():
        return []
    records: list[dict[str, Any]] = []
    with ledger_path.open("r", encoding="utf-8") as f:
        for lineno, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Corrupted ledger at line {lineno} in {ledger_path}: {exc}"
                ) from exc
    return records


def make_record(
    system: str,
    fidelity: str,
    params: dict[str, Any],
    energy: float | None,
    converged: bool,
    failure_type: str | None = None,
    actions_taken: list[str] | None = None,
    wall_time_s: float | None = None,
    candidate_id: str | None = None,
) -> dict[str, Any]:
    """Build a well-formed ledger record dict matching the v2 schema.

    Schema
    ------
    timestamp       ISO 8601 UTC
    system          e.g. "Ti3C2_O"
    candidate_id    UUID string
    fidelity        "low" | "high"
    params          {"ecutwfc": 30.0, "kpts": [2,2,2], ...}
    energy          total energy in eV (None if calculation failed)
    converged       True if QE reached JOB DONE without SCF failure
    failure_type    None | "SCF_CONVERGENCE" | "ELECTRONIC_INSTABILITY" |
                    "GEOMETRY_CRASH" | "UNKNOWN"
    actions_taken   list of escalation actions applied, e.g. ["soften_mixing"]
    wall_time_s     wall clock seconds for the QE run
    """
    return {
        "timestamp":    datetime.now(timezone.utc).isoformat(),
        "system":       system,
        "candidate_id": candidate_id or str(uuid.uuid4()),
        "fidelity":     fidelity,
        "params":       dict(params),
        "energy":       energy,
        "converged":    converged,
        "failure_type": failure_type,
        "actions_taken": list(actions_taken) if actions_taken else [],
        "wall_time_s":  wall_time_s,
    }
