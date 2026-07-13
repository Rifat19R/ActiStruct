"""Task 9: Guard tests for honest ML/AL framing in reports.

These tests lock in the disclaimer language and guard against over-claim
phrases being introduced (e.g. by re-running report-generation scripts).
They are deliberately strict: if a script regenerates a report with
inflated claims, these tests must fail loudly.

What this guards against:
- Reports losing their CRITICAL DISCLAIMER blocks
- Language claiming statistical significance with 12–16 data points
- Claims of generalization, deployment-readiness, or production accuracy
- Descriptors being mislabeled as RAC when they are Coulomb matrix
"""
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = PROJECT_ROOT / "reports"

# Report paths we audit for honest framing
BASELINE_REPORT = REPORTS_DIR / "baseline_model_report_v0.1.md"
AL_REPORT = REPORTS_DIR / "active_learning_demo_v0.1.md"
FEATURE_REPORT = REPORTS_DIR / "feature_report_v0.1.md"


# ---------------------------------------------------------------------------
# Required disclaimer text (must be present)
# ---------------------------------------------------------------------------

def test_baseline_model_report_has_critical_disclaimer():
    """Baseline model report must contain its CRITICAL DISCLAIMER block."""
    if not BASELINE_REPORT.exists():
        pytest.skip("baseline_model_report_v0.1.md not found")
    text = BASELINE_REPORT.read_text(encoding="utf-8")
    assert "CRITICAL DISCLAIMER" in text, (
        "baseline_model_report_v0.1.md missing CRITICAL DISCLAIMER — "
        "re-run scripts/12_baseline_model.py may have overwritten it"
    )
    assert "statistically meaningful" in text or "statistically" in text, (
        "Baseline report must explicitly say metrics are not statistically meaningful"
    )


def test_al_demo_report_has_critical_disclaimer():
    """AL demo report must contain its CRITICAL DISCLAIMER block."""
    if not AL_REPORT.exists():
        pytest.skip("active_learning_demo_v0.1.md not found")
    text = AL_REPORT.read_text(encoding="utf-8")
    assert "CRITICAL DISCLAIMER" in text, (
        "active_learning_demo_v0.1.md missing CRITICAL DISCLAIMER — "
        "re-run scripts/14_active_learning_demo.py may have overwritten it"
    )
    assert "retrospective" in text.lower() or "workflow demonstration" in text.lower(), (
        "AL report must state results are retrospective / workflow demonstration only"
    )


def test_feature_report_has_dataset_size_disclaimer():
    """Feature report must state the 16-structure dataset limitation."""
    if not FEATURE_REPORT.exists():
        pytest.skip("feature_report_v0.1.md not found")
    text = FEATURE_REPORT.read_text(encoding="utf-8")
    # Must mention the dataset size and ML limitation
    assert "16 DFT" in text or "16 calculations" in text or "16 rows" in text or "16 structures" in text, (
        "Feature report must state the 16-structure dataset size"
    )
    assert "not sufficient" in text.lower() or "insufficient" in text.lower(), (
        "Feature report must state that 16 structures are not sufficient for ML claims"
    )


# ---------------------------------------------------------------------------
# Prohibited over-claim phrases (must NOT be present in ML/AL reports)
# ---------------------------------------------------------------------------

PROHIBITED_PHRASES = [
    # Claims of statistical validity with tiny dataset
    # NOTE: "statistically significant" is NOT prohibited — the AL demo correctly
    # uses it as a hypothetical ("A statistically significant correlation WOULD mean...")
    # to contrast with the actual result ("With 12 points, any correlation is unreliable").
    # We prohibit "is statistically significant" and "shows statistically significant"
    # as phrases that would claim significance rather than discuss the concept.
    ("is statistically significant", "baseline", BASELINE_REPORT),
    ("is statistically significant", "al_demo", AL_REPORT),
    ("shows statistically significant", "baseline", BASELINE_REPORT),
    ("shows statistically significant", "al_demo", AL_REPORT),
    # Claims of generalization / transfer
    ("generalizes to", "baseline", BASELINE_REPORT),
    ("generalizes to", "al_demo", AL_REPORT),
    ("generalises to", "baseline", BASELINE_REPORT),
    ("generalises to", "al_demo", AL_REPORT),
    # Claims of production readiness
    ("ready for deployment", "baseline", BASELINE_REPORT),
    ("ready for deployment", "al_demo", AL_REPORT),
    ("suitable for production", "baseline", BASELINE_REPORT),
    ("suitable for production", "al_demo", AL_REPORT),
    # Strong prediction claims without caveat
    ("our model predicts accurately", "baseline", BASELINE_REPORT),
    ("our model predicts accurately", "al_demo", AL_REPORT),
    ("state of the art", "baseline", BASELINE_REPORT),
    ("state of the art", "al_demo", AL_REPORT),
    ("state-of-the-art", "baseline", BASELINE_REPORT),
    ("state-of-the-art", "al_demo", AL_REPORT),
    # Mislabeling descriptors
    ("RAC descriptor", "baseline", BASELINE_REPORT),
    ("RAC descriptor", "al_demo", AL_REPORT),
    ("RAC descriptor", "feature", FEATURE_REPORT),
    ("Revised Autocorrelation", "baseline", BASELINE_REPORT),
    ("Revised Autocorrelation", "al_demo", AL_REPORT),
    ("Revised Autocorrelation", "feature", FEATURE_REPORT),
]


@pytest.mark.parametrize("phrase,report_label,report_path",
                         PROHIBITED_PHRASES,
                         ids=[f"{label}:{phrase[:30]}" for phrase, label, _ in PROHIBITED_PHRASES])
def test_no_prohibited_phrase_in_report(phrase, report_label, report_path):
    """Prohibited over-claim phrase must not appear in the report."""
    if not report_path.exists():
        pytest.skip(f"{report_path.name} not found")
    text = report_path.read_text(encoding="utf-8").lower()
    assert phrase.lower() not in text, (
        f"Prohibited phrase '{phrase}' found in {report_path.name} — "
        "this may indicate ML/AL over-claiming language"
    )


# ---------------------------------------------------------------------------
# Dataset size honesty checks
# ---------------------------------------------------------------------------

def test_baseline_report_does_not_claim_30_or_more_training_structures():
    """The baseline model is trained on 12 structures. Any claim of ≥30
    training samples would indicate a fabricated or inflated result.
    """
    if not BASELINE_REPORT.exists():
        pytest.skip("baseline_model_report_v0.1.md not found")
    text = BASELINE_REPORT.read_text(encoding="utf-8")
    # Check the training size stated in the disclaimer matches reality
    assert "12 DFT" in text or "12 candidates" in text or "12 labelled" in text or "12 labeled" in text, (
        "Baseline report must state it was trained on 12 candidates — "
        "check that re-generation hasn't silently changed the training size"
    )


def test_al_demo_pool_size_is_honest():
    """AL demo pool must be 8 candidates (12 total minus 4 holdout)."""
    if not AL_REPORT.exists():
        pytest.skip("active_learning_demo_v0.1.md not found")
    text = AL_REPORT.read_text(encoding="utf-8")
    # The report mentions 8 pool candidates in the step table
    assert "8 candidates" in text or "pool (8" in text or "(8 candidates" in text, (
        "AL demo report must state pool size of 8 candidates"
    )


# ---------------------------------------------------------------------------
# Script-level framing audit (catches re-generation that strips disclaimers)
# ---------------------------------------------------------------------------

def test_baseline_model_script_writes_disclaimer():
    """scripts/12_baseline_model.py must write a CRITICAL DISCLAIMER to the report.

    If the script is updated and the disclaimer-writing code is removed,
    re-generation would silently drop the safeguard.
    """
    script_path = PROJECT_ROOT / "scripts" / "12_baseline_model.py"
    if not script_path.exists():
        pytest.skip("scripts/12_baseline_model.py not found")
    text = script_path.read_text(encoding="utf-8")
    assert "CRITICAL DISCLAIMER" in text, (
        "scripts/12_baseline_model.py must write CRITICAL DISCLAIMER to its report"
    )


def test_al_demo_script_writes_disclaimer():
    """scripts/14_active_learning_demo.py must write a CRITICAL DISCLAIMER."""
    script_path = PROJECT_ROOT / "scripts" / "14_active_learning_demo.py"
    if not script_path.exists():
        pytest.skip("scripts/14_active_learning_demo.py not found")
    text = script_path.read_text(encoding="utf-8")
    assert "CRITICAL DISCLAIMER" in text, (
        "scripts/14_active_learning_demo.py must write CRITICAL DISCLAIMER to its report"
    )
