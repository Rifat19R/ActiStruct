"""Regression tests for analysis path handling."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_DIR = PROJECT_ROOT / "analysis"
if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))


def test_publication_data_uses_checkout_root() -> None:
    import publication_data

    assert publication_data.ROOT == PROJECT_ROOT
    assert publication_data.REPORT_DIR == PROJECT_ROOT / "outputs" / "reports"
    assert publication_data.RAW_DIR == PROJECT_ROOT / "analysis" / "outputs" / "raw"


def test_preflight_returns_nonzero_on_failure(tmp_path) -> None:
    script = (
        "from pathlib import Path\n"
        "import sys\n"
        f"sys.path.insert(0, {str(ANALYSIS_DIR)!r})\n"
        "import preflight_check\n"
        f"preflight_check.RAW_DIR = Path({str(tmp_path)!r})\n"
        f"preflight_check.FIGURE_DIR = Path({str(tmp_path)!r})\n"
        f"preflight_check.ROOT = Path({str(tmp_path)!r})\n"
        "preflight_check.main()\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "PREFLIGHT FAILED" in result.stdout


def test_report_paths_are_repo_relative() -> None:
    import extract_all_results

    report = PROJECT_ROOT / "outputs" / "reports" / "bulk_al_report.txt"

    assert extract_all_results.report_path_for_csv(report) == "outputs/reports/bulk_al_report.txt"
