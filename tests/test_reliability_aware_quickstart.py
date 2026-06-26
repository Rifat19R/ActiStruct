from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "examples" / "reliability_aware_quickstart.py"


def test_quickstart_script_runs_and_reports_safe_caveats() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        check=False,
        text=True,
        capture_output=True,
        cwd=ROOT,
    )

    assert result.returncode == 0
    output = result.stdout

    assert "offline simulation" in output
    assert "no live QE/PBE validation" in output
    assert "normal_pool" in output
    assert "failure_enriched_pool" in output
    assert "heldout_material_pool" in output
    assert "high_uncertainty_pool" in output
