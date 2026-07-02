"""Cumulative escalation strategy for QE SCF convergence failures.

Design decision (explicit):
  Actions are applied in GROUPS, cumulatively. All parameters within a group
  change in the same retry because they are physically coupled:
    - switching smearing method and updating degauss must happen together
      (applying methfessel-paxton with gaussian degauss=0.02 is wrong)
    - each group keeps every previously applied group's changes on top

  This matches how an experienced QE user escalates manually: each retry
  starts from the best-known-so-far settings, not from scratch.

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
    """Applies cumulative escalation action groups to a QE input_data dict.

    Each call to ``next_input()`` applies one full group and returns the
    merged dict. Groups are cumulative: group 3 always includes all changes
    from groups 1 and 2 as well.

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
            break  # exhausted — needs human review
        # run QE with next_params
        # log actions via strategy.actions_applied
    """

    # Each group is applied atomically in one retry.
    # Smearing method and degauss always change together — they are
    # physically coupled (M-P smearing needs higher degauss than gaussian).
    _GROUPS: list[list[tuple[str, str, Any]]] = [
        # Group 1: soften mixing to calm charge-density oscillations
        [("electrons", "mixing_beta", 0.3)],
        # Group 2: gaussian smearing + matched degauss (both at once)
        [("system",    "smearing",    "gaussian"),
         ("system",    "degauss",     0.02)],
        # Group 3: Methfessel-Paxton + larger degauss (both at once —
        #          M-P requires larger degauss than gaussian for metals)
        [("system",    "smearing",    "methfessel-paxton"),
         ("system",    "degauss",     0.03)],
        # Group 4: more SCF iterations as final resort before human review
        [("electrons", "electron_maxstep", 300)],
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
        """Apply the next escalation group cumulatively and return the merged dict.

        All parameters within a group are applied in the same retry.
        Returns None when all groups are exhausted — caller should log the
        candidate as unrecoverable and seek human review.
        """
        if self._step >= len(self._GROUPS):
            return None

        group = self._GROUPS[self._step]
        self._step += 1

        for section, key, value in group:
            if section not in self._applied:
                self._applied[section] = {}
            self._applied[section][key] = value
            self.actions_applied.append(f"{section}.{key}={value}")

        # Merge base + all accumulated group changes.
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
        """True when no more escalation groups remain."""
        return self._step >= len(self._GROUPS)

    @property
    def num_actions(self) -> int:
        """Number of escalation groups (= maximum retries before exhaustion)."""
        return len(self._GROUPS)
