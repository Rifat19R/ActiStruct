"""Dashboard data loader — reads Phase 0/1/2 JSONL ledgers into a DataFrame.

Ledger architecture (per-system, not global)
--------------------------------------------
Each material campaign writes its own JSONL ledger:
  /home/alchemist/actistruct_data/<system>/recovery.jsonl   <- recovery-enabled runs
  /home/alchemist/actistruct_data/<system>/campaign.jsonl   <- full AL campaign

Use load_ledger() for a single file, load_multi_ledger() to aggregate across
all systems under a root directory. The 'system' field in every record
already tags which material it belongs to — the dashboard can filter by it.

Other design decisions
----------------------
- Reads JSONL directly via pandas.read_json(lines=True).
- Checks for required columns before using them; raises ValueError on schema
  mismatch rather than a bare KeyError.
- Returns an empty DataFrame (correct schema, zero rows) for missing/empty
  ledgers — the dashboard shows a friendly "no data yet" state.
- load_multi_ledger() skips corrupted files and adds 'source_file' provenance.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from actistruct.core.ledger import DEFAULT_LEDGER_PATH

# Default root for per-system ledgers on the native Linux FS.
MULTI_LEDGER_ROOT = Path("/home/alchemist/actistruct_data")

# Glob patterns searched inside MULTI_LEDGER_ROOT/<system>/.
MULTI_LEDGER_PATTERNS = ("*/recovery.jsonl", "*/campaign.jsonl")

# Minimal required columns — all written by make_record() in ledger.py.
REQUIRED_COLUMNS = {
    "timestamp",
    "system",
    "candidate_id",
    "fidelity",
    "params",
    "energy",
    "converged",
    "failure_type",
    "actions_taken",
    "wall_time_s",
}

# Empty DataFrame with the correct schema (shown when ledger has no data).
_EMPTY_DF = pd.DataFrame(columns=sorted(REQUIRED_COLUMNS))


def load_ledger(
    ledger_path: Path | str = DEFAULT_LEDGER_PATH,
) -> pd.DataFrame:
    """Load the JSONL run ledger into a pandas DataFrame.

    Returns an empty DataFrame (correct columns, zero rows) when the ledger
    does not exist or is empty — never raises on a missing/empty ledger.

    Raises
    ------
    ValueError
        If the ledger exists but is missing required columns (corrupted or
        produced by an incompatible version of the ledger schema).
    """
    path = Path(ledger_path)

    if not path.exists() or path.stat().st_size == 0:
        return _EMPTY_DF.copy()

    try:
        df = pd.read_json(path, lines=True)
    except ValueError as exc:
        raise ValueError(
            f"Could not parse ledger at {path}: {exc}\n"
            "The file may be corrupted. Check for partial/incomplete JSON lines."
        ) from exc

    if df.empty:
        return _EMPTY_DF.copy()

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(
            f"Ledger is missing required columns: {sorted(missing)}\n"
            f"Found columns: {sorted(df.columns)}\n"
            "Run Phase 1/2 to generate records, or check that the ledger was "
            "written by actistruct.core.ledger.make_record()."
        )

    # Parse timestamps.
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")

    return df


def load_multi_ledger(
    root_dir: Path | str = MULTI_LEDGER_ROOT,
    patterns: tuple[str, ...] = MULTI_LEDGER_PATTERNS,
) -> pd.DataFrame:
    """Load and concatenate ledgers from all systems under root_dir.

    Globs root_dir/<system>/recovery.jsonl and root_dir/<system>/campaign.jsonl.
    Skips missing, empty, or schema-incompatible files silently.

    The 'system' column already identifies the material for each record
    (written by make_record() at run time). The added 'source_file' column
    gives provenance for debugging.

    Returns an empty DataFrame (correct schema) if no ledger files are found.
    """
    root = Path(root_dir)
    frames: list[pd.DataFrame] = []

    for pattern in patterns:
        for ledger_path in sorted(root.glob(pattern)):
            try:
                df = load_ledger(ledger_path)
            except ValueError:
                continue
            if not df.empty:
                df = df.copy()
                df["source_file"] = str(ledger_path)
                frames.append(df)

    if not frames:
        empty = _EMPTY_DF.copy()
        empty["source_file"] = pd.Series(dtype="str")
        return empty

    combined = pd.concat(frames, ignore_index=True)
    if "timestamp" in combined.columns:
        combined = combined.sort_values("timestamp").reset_index(drop=True)
    return combined


def get_summary_stats(df: pd.DataFrame) -> dict[str, Any]:
    """Compute dashboard summary statistics from a loaded ledger DataFrame."""
    if df.empty:
        return {
            "total_runs": 0,
            "converged": 0,
            "failed": 0,
            "convergence_rate_pct": 0.0,
            "systems": [],
            "failure_types": {},
        }

    total       = len(df)
    converged   = int(df["converged"].sum())
    failed      = total - converged
    conv_rate   = 100.0 * converged / total if total > 0 else 0.0
    systems     = sorted(df["system"].dropna().unique().tolist())
    fail_counts = (
        df[~df["converged"]]["failure_type"]
        .value_counts()
        .to_dict()
    )

    return {
        "total_runs":           total,
        "converged":            converged,
        "failed":               failed,
        "convergence_rate_pct": conv_rate,
        "systems":              systems,
        "failure_types":        fail_counts,
    }


def atoms_to_xyz_string(atoms: Any) -> str:
    """Convert an ASE Atoms object to an XYZ format string for py3Dmol.

    The XYZ format: first line = number of atoms, second = comment, then
    one line per atom: symbol x y z (coordinates in Angstrom).
    """
    lines = [str(len(atoms)), f"ActiStruct structure - {atoms.get_chemical_formula()}"]
    for symbol, pos in zip(atoms.get_chemical_symbols(), atoms.get_positions()):
        lines.append(f"{symbol}  {pos[0]:.6f}  {pos[1]:.6f}  {pos[2]:.6f}")
    return "\n".join(lines)
