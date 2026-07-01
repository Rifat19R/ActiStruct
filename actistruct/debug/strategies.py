"""Cumulative escalation strategy for QE SCF convergence failures.

Design decision (explicit):
  Actions are CUMULATIVE. Each retry keeps every previously applied fix and
  adds the next one on top. A system that needs softer mixing AND larger
  smearing to converge gets both by attempt 3, not just the smearing fix
  in isolation. This matches how an experienced QE user would manually
  escalate: each attempt starts from the best-known-so-far settings, not
  from scratch.

Physics constraints for CaAlN2 (hexagonal nitride):
  - Ca/Al/N are closed-shell → do NOT touch nspin unless the error is
    specifically an eigenvalue-occupation internal error.
  - Start with gaussian smearing (appropriate for a semiconductor/electride).
  - Escalate to methfessel-paxton with larger degauss if oscillation persists.
  - Soften mixing_beta first (most common fix for charge oscillation).
  - Never touch pseudopotentials or cell volume automatically.
"""
from __future__ import annotations

from typing import Any


class TroubleshootingStrategy:
    """Applies cumulative escalation actions to a QE input_data dict.

    Parameters
    ----------
    base_input_data:
        The QE input_data dict as used by ASE's Espresso calculator
        (nested: {"control": {...}, "system": {...}, "electrons": {...}}).

    Usage
    -----
    strategy = TroubleshootingStrategy(base_input_data)
    while True:
        next_params = strategy.next_input()
        if next_params is None:
            # exhausted — needs human review
            break
        # run QE with next_params, log actions via strategy.actions_applied
    """

    # Each tuple is (section, key, value) — applied cumulatively.
    # Order matters: soften electronics first, then smearing escalation.
    _ACTIONS: list[tuple[str, str, Any]] = [
        # Step 1: soften mixing to calm charge-density oscillations.
        ("electrons", "mixing_beta",      0.3),
        # Step 2: switch to gaussian with slightly larger degauss.
        ("system",    "smearing",         "gaussian"),
        ("system",    "degauss",          0.02),
        # Step 3: escalate to Methfessel-Paxton if gaussian still oscillates.
        ("system",    "smearing",         "methfessel-paxton"),
        ("system",    "degauss",          0.03),
        # Step 4: give the SCF more iterations before giving up.
        ("electrons", "electron_maxstep", 300),
    ]

    def __init__(self, base_input_data: dict[str, Any]) -> None:
        # Deep-copy to avoid mutating the caller's dict.
        self._base: dict[str, dict[str, Any]] = {
            section: dict(inner)
            for section, inner in base_input_data.items()
        }
        self._applied: dict[str, dict[str, Any]] = {}
        self._step = 0
        self.actions_applied: list[str] = []

    def next_input(self) -> dict[str, dict[str, Any]] | None:
        """Apply the next escalation action cumulatively and return the merged dict.

        Returns None when all actions are exhausted — caller should log the
        candidate as unrecoverable and move on.
        """
        if self._step >= len(self._ACTIONS):
            return None

        section, key, value = self._ACTIONS[self._step]
        self._step += 1

        if section not in self._applied:
            self._applied[section] = {}
        self._applied[section][key] = value

        action_label = f"{section}.{key}={value}"
        self.actions_applied.append(action_label)

        # Merge base + all accumulated changes.
        merged: dict[str, dict[str, Any]] = {}
        for sec, inner in self._base.items():
            merged[sec] = dict(inner)
        for sec, changes in self._applied.items():
            if sec not in merged:
                merged[sec] = {}
            merged[sec].update(changes)

        return merged

    @property
    def exhausted(self) -> bool:
        """True when no more escalation actions remain."""
        return self._step >= len(self._ACTIONS)

    @property
    def num_actions(self) -> int:
        """Total number of available escalation steps."""
        return len(self._ACTIONS)
