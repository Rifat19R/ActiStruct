"""Phase 1 — Active troubleshooting engine for QE DFT failures.

Provides:
  DFTFailureAnalyzer  — regex-based failure classifier
  TroubleshootingStrategy — cumulative parameter-escalation strategy
  run_dft_with_recovery   — drop-in wrapper around a single QE call
"""

from .classifier import DFTFailureAnalyzer
from .strategies import TroubleshootingStrategy
from .recovery import run_dft_with_recovery

__all__ = [
    "DFTFailureAnalyzer",
    "TroubleshootingStrategy",
    "run_dft_with_recovery",
]
