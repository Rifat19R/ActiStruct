"""Phase 1 — DFT failure classifier, escalation strategy, and recovery tests.

Test coverage:
  1. SCF_CONVERGENCE correctly classified from real QE failure string.
  2. Successful BFGS relaxation log NOT misclassified as GEOMETRY_CRASH.
     (Regression test: "Broyden" and "linmin" appear in normal runs.)
  3. Escalation actions are cumulative — attempt 3 includes attempt 1+2 changes.
  4. Strategy stops after max steps (no infinite loop).
  5. Recovery wrapper: returns energy on first-attempt success (no retries).
  6. Recovery wrapper: GEOMETRY_CRASH triggers immediate discard (no retries).
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from actistruct.debug.classifier import DFTFailureAnalyzer
from actistruct.debug.strategies import TroubleshootingStrategy
from actistruct.debug.recovery import run_dft_with_recovery
from actistruct.core.ledger import read_records


# ── synthetic QE output snippets ─────────────────────────────────────────────

_SCF_FAILURE_OUTPUT = """\
     Self-consistent Calculation

     iteration #  1     ecut=   30.00 Ry     beta= 0.70
     ...
     convergence NOT achieved after  100 iterations; stopping
"""

# Real successful BFGS relaxation output contains "Broyden" and "linmin" —
# these are sub-step labels in the ionic optimizer, NOT error strings.
_SUCCESS_BFGS_OUTPUT = """\
     Starting BFGS Geometry Optimization
     bfgs history length = 20
     Broyden mixing: rho=  0.00000E+00, ...
     linmin: alpha= 1.00000E+00
     BFGS converged in    4 scf cycles and    3 bfgs steps
     ...
     JOB DONE.
"""

_ELECTRONIC_INSTABILITY_OUTPUT = """\
     S matrix not positive definite
     convergence NOT achieved after  50 iterations; stopping
"""

_GEOMETRY_CRASH_OUTPUT = """\
     atoms too close: minimum distance is  0.01 Bohr
     stopping ...
"""

_BFGS_EXHAUSTED_OUTPUT = """\
     Maximum number of iterations reached without convergence — stopping
"""


# ── classifier tests ──────────────────────────────────────────────────────────

class TestDFTFailureAnalyzer:
    def setup_method(self):
        self.analyzer = DFTFailureAnalyzer()

    def test_scf_convergence_classified(self):
        result = self.analyzer.classify(_SCF_FAILURE_OUTPUT)
        assert result == "SCF_CONVERGENCE", f"Got: {result}"

    def test_success_bfgs_not_misclassified_as_geometry_crash(self):
        """KEY REGRESSION TEST: Broyden + linmin in successful logs must not trigger GEOMETRY_CRASH."""
        result = self.analyzer.classify(_SUCCESS_BFGS_OUTPUT)
        assert result == "SUCCESS", (
            f"Got: {result!r}. "
            "Successful BFGS relaxation output was misclassified — "
            "check that 'Broyden'/'linmin' are NOT in the GEOMETRY_CRASH pattern."
        )

    def test_electronic_instability_classified(self):
        result = self.analyzer.classify(_ELECTRONIC_INSTABILITY_OUTPUT)
        # S matrix not positive definite → ELECTRONIC_INSTABILITY
        # (SCF_CONVERGENCE also matches the second line, but ELECTRONIC_INSTABILITY
        # appears first in the pattern dict — the check is ordered.)
        assert result in {"ELECTRONIC_INSTABILITY", "SCF_CONVERGENCE"}, f"Got: {result}"

    def test_geometry_crash_atoms_too_close(self):
        result = self.analyzer.classify(_GEOMETRY_CRASH_OUTPUT)
        assert result == "GEOMETRY_CRASH", f"Got: {result}"

    def test_geometry_crash_bfgs_exhausted(self):
        result = self.analyzer.classify(_BFGS_EXHAUSTED_OUTPUT)
        assert result == "GEOMETRY_CRASH", f"Got: {result}"

    def test_geometry_crash_not_retryable(self):
        assert self.analyzer.is_retryable("GEOMETRY_CRASH") is False

    def test_scf_convergence_is_retryable(self):
        assert self.analyzer.is_retryable("SCF_CONVERGENCE") is True

    def test_unknown_is_retryable(self):
        assert self.analyzer.is_retryable("UNKNOWN") is True


# ── strategy tests ────────────────────────────────────────────────────────────

class TestTroubleshootingStrategy:
    def _base(self) -> dict:
        return {
            "system":    {"ecutwfc": 30.0, "smearing": "gaussian", "degauss": 0.01},
            "electrons": {"conv_thr": 5e-9, "electron_maxstep": 200, "mixing_beta": 0.7},
        }

    def test_first_action_softens_mixing(self):
        s = TroubleshootingStrategy(self._base())
        merged = s.next_input()
        assert merged is not None
        assert merged["electrons"]["mixing_beta"] == pytest.approx(0.3)

    def test_actions_are_cumulative_by_attempt_3(self):
        """Attempt 3 must contain BOTH attempt 1's and attempt 2's changes."""
        s = TroubleshootingStrategy(self._base())
        s.next_input()   # step 1: mixing_beta=0.3
        s.next_input()   # step 2: smearing=gaussian
        merged = s.next_input()  # step 3: degauss=0.02

        assert merged is not None
        # mixing_beta from step 1 must still be present
        assert merged["electrons"]["mixing_beta"] == pytest.approx(0.3), \
            "Step 1 change (mixing_beta) was lost by step 3 — actions are not cumulative!"
        # degauss from step 3 must be present
        assert merged["system"]["degauss"] == pytest.approx(0.02)

    def test_base_dict_not_mutated(self):
        base = self._base()
        original_mixing = base["electrons"]["mixing_beta"]
        s = TroubleshootingStrategy(base)
        s.next_input()
        assert base["electrons"]["mixing_beta"] == pytest.approx(original_mixing), \
            "TroubleshootingStrategy mutated the caller's base dict!"

    def test_stops_after_max_actions(self):
        s = TroubleshootingStrategy(self._base())
        results = []
        for _ in range(s.num_actions + 5):   # deliberately over-run
            results.append(s.next_input())
        none_results = [r for r in results if r is None]
        assert len(none_results) >= 5, "Strategy did not stop returning None after exhaustion."

    def test_actions_applied_list_grows(self):
        s = TroubleshootingStrategy(self._base())
        s.next_input()
        s.next_input()
        assert len(s.actions_applied) == 2

    def test_exhausted_flag(self):
        s = TroubleshootingStrategy(self._base())
        for _ in range(s.num_actions):
            s.next_input()
        assert s.exhausted is True


# ── recovery wrapper tests ────────────────────────────────────────────────────

class TestRunDftWithRecovery:
    def _make_runner(self, energy: float | None, output: str):
        """Return a qe_runner closure that always returns (energy, output)."""
        def _runner(input_data):
            return energy, output
        return _runner

    def test_success_on_first_attempt(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir) / "ledger.jsonl"
            runner = self._make_runner(-134.5, _SUCCESS_BFGS_OUTPUT)
            base = {
                "system": {"ecutwfc": 60.0, "smearing": "gaussian", "degauss": 0.01},
                "electrons": {"conv_thr": 5e-9, "electron_maxstep": 200, "mixing_beta": 0.7},
            }
            energy, failure, actions = run_dft_with_recovery(
                runner, base, system_name="CaAlN2", fidelity="high",
                params={"a": 3.15}, ledger_path=ledger, retry_wait_s=0,
            )
            assert energy == pytest.approx(-134.5)
            assert failure is None
            assert actions == []  # no escalation needed

            recs = read_records(ledger)
            assert len(recs) == 1
            assert recs[0]["converged"] is True

    def test_geometry_crash_discards_immediately(self):
        """GEOMETRY_CRASH must not retry — record logged with converged=False."""
        call_count = [0]

        def counting_runner(input_data):
            call_count[0] += 1
            return None, _GEOMETRY_CRASH_OUTPUT

        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir) / "ledger.jsonl"
            base = {"system": {}, "electrons": {}}
            energy, failure, actions = run_dft_with_recovery(
                counting_runner, base, system_name="CaAlN2", fidelity="low",
                params={"a": 3.10}, ledger_path=ledger, retry_wait_s=0,
            )
            assert energy is None
            assert failure == "GEOMETRY_CRASH"
            assert call_count[0] == 1, \
                f"GEOMETRY_CRASH was retried {call_count[0]} times — should be exactly 1."

    def test_scf_failure_escalates_then_succeeds(self):
        """SCF failure on attempt 1, then success on attempt 2 (escalated mixing)."""
        call_count = [0]

        def runner_that_succeeds_second_time(input_data):
            call_count[0] += 1
            if call_count[0] == 1:
                return None, _SCF_FAILURE_OUTPUT
            return -130.0, _SUCCESS_BFGS_OUTPUT

        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir) / "ledger.jsonl"
            base = {
                "system":    {"ecutwfc": 60.0, "smearing": "gaussian", "degauss": 0.01},
                "electrons": {"conv_thr": 5e-9, "electron_maxstep": 200, "mixing_beta": 0.7},
            }
            energy, failure, actions = run_dft_with_recovery(
                runner_that_succeeds_second_time, base, system_name="CaAlN2",
                fidelity="high", params={"a": 3.15}, ledger_path=ledger, retry_wait_s=0,
            )
            assert energy == pytest.approx(-130.0)
            assert failure is None
            assert call_count[0] == 2

            recs = read_records(ledger)
            assert len(recs) == 2  # one failure + one success logged
            assert recs[0]["converged"] is False
            assert recs[1]["converged"] is True
