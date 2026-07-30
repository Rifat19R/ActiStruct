"""Repository presentation and scientific-evidence integrity checks.

These tests are offline and must never invoke Quantum ESPRESSO.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
HASH_MANIFEST = ROOT / "reproducibility" / "evidence_sha256.txt"

PUBLIC_MARKDOWN = [
    ROOT / "README.md",
    ROOT / "CONTRIBUTING.md",
    ROOT / "docs" / "index.md",
    ROOT / "docs" / "installation.md",
    ROOT / "docs" / "quickstart.md",
    ROOT / "docs" / "architecture.md",
    ROOT / "docs" / "scientific_scope.md",
    ROOT / "docs" / "benchmarks.md",
    ROOT / "docs" / "reproducibility.md",
    ROOT / "docs" / "limitations.md",
    ROOT / "docs" / "claim_governance.md",
    ROOT / "docs" / "hf_validation_status.md",
    ROOT / "benchmarks" / "README.md",
    ROOT / "benchmarks" / "tmc" / "README.md",
    ROOT / "benchmarks" / "ti3c2o" / "README.md",
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_entries() -> list[tuple[str, Path]]:
    entries: list[tuple[str, Path]] = []
    for raw_line in HASH_MANIFEST.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        digest, relative_path = line.split(maxsplit=1)
        entries.append((digest, ROOT / relative_path))
    return entries


def _local_markdown_targets(path: Path) -> list[Path]:
    text = path.read_text(encoding="utf-8")
    raw_targets = re.findall(r"\[[^\]]*\]\(([^)]+)\)", text)
    raw_targets += re.findall(r'(?:href|src)="([^"]+)"', text)
    targets: list[Path] = []
    for raw_target in raw_targets:
        target = raw_target.strip().split("#", 1)[0]
        if (
            not target
            or target.startswith(("#", "http://", "https://", "mailto:"))
        ):
            continue
        targets.append((path.parent / target).resolve())
    return targets


def test_public_entry_points_exist() -> None:
    required = [
        ROOT / "assets" / "logo" / "actistruct-wordmark.svg",
        ROOT / "assets" / "figures" / "workflow.svg",
        ROOT / "examples" / "quickstart" / "no_qe_ti3c2o.py",
        ROOT / "benchmarks" / "tmc" / "README.md",
        ROOT / "benchmarks" / "ti3c2o" / "README.md",
        ROOT / "docs" / "claim_governance.md",
        ROOT / "docs" / "hf_validation_status.md",
        HASH_MANIFEST,
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
    assert missing == []


def test_development_artifacts_are_not_at_repository_root() -> None:
    moved = [
        "demo_ti3c2_o.py",
        "test_all_integrations.py",
        "paper.md",
        "paper.bib",
        "run.sh",
    ]
    assert [name for name in moved if (ROOT / name).exists()] == []


@pytest.mark.parametrize("digest,path", _manifest_entries())
def test_evidence_manifest_digest(digest: str, path: Path) -> None:
    assert path.is_file(), f"Missing evidence file: {path.relative_to(ROOT)}"
    assert _sha256(path) == digest, f"Digest changed: {path.relative_to(ROOT)}"


def test_ti3c2o_campaign_summary_matches_append_only_logs() -> None:
    original_path = (
        ROOT / "outputs" / "campaigns" / "ti3c2_o_lf_campaign.jsonl"
    )
    rerun_path = (
        ROOT
        / "outputs"
        / "campaigns"
        / "ti3c2_o_lf_campaign_plain_gp_rerun_amend5.jsonl"
    )
    original = [
        json.loads(line)
        for line in original_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    rerun = [
        json.loads(line)
        for line in rerun_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert len(original) == 15
    assert len(rerun) == 5
    assert sum(bool(row["physical_new_dft_call"]) for row in original) == 9
    assert sum(bool(row["physical_new_dft_call"]) for row in rerun) == 5
    assert min(row["abs_delta_g_h"] for row in rerun) == pytest.approx(
        0.0019544716756589517
    )


@pytest.mark.parametrize("markdown_path", PUBLIC_MARKDOWN)
def test_public_markdown_local_links_exist(markdown_path: Path) -> None:
    assert markdown_path.is_file()
    broken = [
        str(target)
        for target in _local_markdown_targets(markdown_path)
        if not target.exists()
    ]
    assert broken == [], f"Broken links in {markdown_path.relative_to(ROOT)}: {broken}"


def test_readme_avoids_prohibited_claims() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8").lower()
    prohibited = [
        "autonomous materials discovery engine",
        "universally reduces dft cost",
        "experimentally validated catalyst",
        "hf-validated ranking",
        "hf validation succeeded",
    ]
    assert [claim for claim in prohibited if claim in text] == []
