"""DFT recovery wrapper — classified, escalating, logged retries.

This replaces the blind try/except/sleep retry inside _run_one_qe() with:
  1. Parse the QE output text after each failure.
  2. Classify the failure (SCF, electronic instability, geometry crash).
  3. If not retryable (GEOMETRY_CRASH), log and discard immediately.
  4. If retryable, apply the next cumulative escalation action and retry.
  5. Log every attempt (params, failure_type, success) to the Phase 0 ledger.

Usage
-----
The hook point in qe_active_inverse_common.py is _run_one_qe() (lines 433-460).
Rather than modifying the shared engine (which would break the 50-workflow
benchmark suite), new v2 workflows (Ti3C2-O HER, etc.) call run_dft_with_recovery()
directly and pass their own QE runner callable.
"""
from __future__ import annotations

import time
import traceback
from pathlib import Path
from typing import Any, Callable

from actistruct.core.ledger import append_record, make_record
from actistruct.debug.classifier import DFTFailureAnalyzer
from actistruct.debug.strategies import TroubleshootingStrategy


def run_dft_with_recovery(
    qe_runner: Callable[[dict[str, Any]], tuple[float | None, str]],
    base_input_data: dict[str, Any],
    system_name: str,
    fidelity: str = "high",
    params: dict[str, Any] | None = None,
    candidate_id: str | None = None,
    ledger_path: Path | None = None,
    max_attempts: int = 5,
    retry_wait_s: int = 5,
) -> tuple[float | None, str | None, list[str]]:
    """Run a QE calculation with classified, cumulative-escalation retries.

    Parameters
    ----------
    qe_runner:
        Callable that accepts a QE input_data dict and returns
        (energy_ev_or_None, output_text_string). The caller is responsible
        for building the ASE Atoms object and passing it through a closure.

    base_input_data:
        Base QE input_data dict (the same nested dict ASE's Espresso takes).

    system_name:
        String identifier logged in the ledger (e.g. "Ti3C2_O").

    fidelity:
        "low" | "high" — logged in the ledger.

    params:
        Dict of structural parameters for the ledger record (e.g.
        {"a": 3.15, "c": 5.00}). Defaults to empty dict.

    candidate_id:
        Optional UUID string; auto-generated if omitted.

    ledger_path:
        Path to the JSONL ledger. Uses the package default if None.

    max_attempts:
        Hard cap on total QE attempts (including the initial unmodified run).
        Default 5 — covers the initial attempt plus 4 escalation steps.

    retry_wait_s:
        Seconds to sleep between retries.

    Returns
    -------
    (energy, final_failure_type, actions_applied)
        energy               — eV if any attempt converged, else None
        final_failure_type   — None on success, else last failure label
        actions_applied      — list of escalation action labels applied
    """
    analyzer  = DFTFailureAnalyzer()
    strategy  = TroubleshootingStrategy(base_input_data)
    params    = dict(params or {})
    ledger_kw = {} if ledger_path is None else {"ledger_path": ledger_path}

    current_input = base_input_data
    last_failure  = "UNKNOWN"

    for attempt in range(1, max_attempts + 1):
        t_start = time.time()
        energy: float | None = None
        output_text: str = ""

        try:
            energy, output_text = qe_runner(current_input)
        except Exception:
            output_text = traceback.format_exc()

        wall_time_s = time.time() - t_start
        failure_type = analyzer.classify(output_text)

        converged = (failure_type == "SUCCESS") and (energy is not None)

        rec = make_record(
            system=system_name,
            fidelity=fidelity,
            params=dict(params, attempt=attempt),
            energy=energy if converged else None,
            converged=converged,
            failure_type=None if converged else failure_type,
            actions_taken=list(strategy.actions_applied),
            wall_time_s=wall_time_s,
            candidate_id=candidate_id,
        )
        append_record(rec, **ledger_kw)

        if converged:
            return energy, None, list(strategy.actions_applied)

        last_failure = failure_type
        print(
            f"  [recovery] attempt {attempt}/{max_attempts} "
            f"-> {failure_type} | actions so far: {strategy.actions_applied}"
        )

        # GEOMETRY_CRASH cannot be fixed with electronic parameter changes.
        if not analyzer.is_retryable(failure_type):
            print(f"  [recovery] {failure_type} is not retryable — discarding candidate.")
            break

        next_input = strategy.next_input()
        if next_input is None:
            print("  [recovery] escalation steps exhausted — needs human review.")
            break

        current_input = next_input
        time.sleep(retry_wait_s)

    return None, last_failure, list(strategy.actions_applied)
