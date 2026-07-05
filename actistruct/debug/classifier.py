"""QE DFT failure classifier.

Classifies a pw.x output string into one of four categories:
  SUCCESS              — JOB DONE, no SCF convergence failure
  SCF_CONVERGENCE      — SCF loop did not converge within electron_maxstep
  ELECTRONIC_INSTABILITY — charge density oscillation or ill-conditioned S matrix
  GEOMETRY_CRASH       — atoms too close, BFGS exhausted, or driver stopping
  UNKNOWN              — QE finished with an error we don't recognise yet

IMPORTANT false-positive guard
-------------------------------
QE writes "Broyden" and "linmin" into normal, successful BFGS relaxation logs
(these are line-minimisation sub-steps of the ionic optimizer, not error strings).
They are intentionally absent from the GEOMETRY_CRASH pattern — including them
would misclassify successful relaxation runs as failures.

Calibration note: patterns here have been verified against real QE 7.x pw.x
output strings. Before extending patterns, grep real .pwo files for the exact
failure string first. Never add a pattern that can appear in a successful run.
"""
from __future__ import annotations

import re


class DFTFailureAnalyzer:
    """Regex-based classifier for Quantum ESPRESSO pw.x output text."""

    # Ordered: most specific / most actionable first.
    _PATTERNS: dict[str, str] = {
        # SCF did not converge — trigger electronic-parameter escalation.
        "SCF_CONVERGENCE": (
            r"convergence NOT achieved after\s+\d+\s+iterations"
        ),
        # Oscillating charge density or ill-conditioned overlap matrix —
        # can be fixed by softer mixing or different smearing.
        "ELECTRONIC_INSTABILITY": (
            r"charge\s+density\s+(?:is\s+)?(?:not\s+normaliz|oscillat)"
            r"|S\s+matrix\s+not\s+positive\s+definite"
        ),
        # Geometry-level failure — electronic parameter changes won't help;
        # log and discard (needs human review of structure).
        # NOTE: "bfgs failed" = optimizer gave up; "Maximum number of
        # iterations reached" at the ionic level = geometry didn't relax.
        # "check_atoms" = QE 7.x's actual routine name when two atoms
        # overlap (real wording is "atoms # N and # M overlap!", not
        # "atoms too close" — verified against 180 real .pwo logs from
        # bulk_li2nav2po43, none of which co-occur with JOB DONE).
        # Do NOT add "Broyden" or "linmin" here — those appear in normal runs.
        "GEOMETRY_CRASH": (
            r"atoms\s+too\s+close"
            r"|check_atoms"
            r"|bfgs\s+failed"
            r"|Maximum\s+number\s+of\s+iterations\s+reached[^\n]*stopping"
        ),
    }

    def __init__(self) -> None:
        self._compiled = {
            label: re.compile(pattern, re.IGNORECASE | re.MULTILINE)
            for label, pattern in self._PATTERNS.items()
        }

    def classify(self, output_text: str) -> str:
        """Return the failure label for the given pw.x output text.

        Returns "SUCCESS" when JOB DONE is present and no failure pattern
        is matched. Returns "UNKNOWN" when the job did not finish and no
        specific pattern matches.
        """
        if "JOB DONE" in output_text and not self._compiled["SCF_CONVERGENCE"].search(output_text):
            return "SUCCESS"

        for label, pattern in self._compiled.items():
            if pattern.search(output_text):
                return label

        # Job didn't complete and no known pattern matched.
        return "UNKNOWN"

    def is_retryable(self, failure_type: str) -> bool:
        """True for failure types where electronic-parameter escalation may help.

        GEOMETRY_CRASH is not retryable with electronic changes — it needs a
        human to inspect the structure. SUCCESS is never retried.
        """
        return failure_type in {"SCF_CONVERGENCE", "ELECTRONIC_INSTABILITY", "UNKNOWN"}
