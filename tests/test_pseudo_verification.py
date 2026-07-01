"""Tests for pseudopotential verification against official SSSP checksums.

These tests read the verification block from configs/pseudo_manifest_required.yaml
and confirm that the local UPF files still match the recorded official MD5 checksums.
They FAIL loudly if any file is missing or corrupted — that is the intended behaviour.

Run after any change to the pseudopotential directory.
"""
from __future__ import annotations

import csv
import hashlib
from pathlib import Path

import sys
import pytest
import yaml

PROJECT_ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from _common import resolve_path  # noqa: E402

MANIFEST_PATH = PROJECT_ROOT / "configs" / "pseudo_manifest_required.yaml"
DATASET_PATH = PROJECT_ROOT / "data" / "processed" / "full_dataset_v0.2.csv"

# Official SSSP 1.3.0 PBE efficiency MD5 checksums, as stored in the manifest.
# These are the ground-truth values; local files must match.
REQUIRED_ELEMENTS = ["Fe", "C", "H", "Ni", "O", "Cr"]


# ──────────────────────────────────────────────
# Manifest structure
# ──────────────────────────────────────────────

def _load_manifest() -> dict:
    return yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_manifest_exists():
    assert MANIFEST_PATH.exists(), f"Missing manifest: {MANIFEST_PATH}"


def test_manifest_has_all_required_elements():
    m = _load_manifest()
    for el in REQUIRED_ELEMENTS:
        assert el in m["elements"], f"Element {el} missing from manifest"


def test_manifest_has_verification_block_for_all_elements():
    m = _load_manifest()
    for el in REQUIRED_ELEMENTS:
        elem_data = m["elements"][el]
        assert "verification" in elem_data, (
            f"Element {el} missing 'verification' block in manifest"
        )


def test_manifest_verification_block_has_required_fields():
    m = _load_manifest()
    required_fields = {
        "official_filename", "official_source_url", "official_checksum_md5",
        "local_filename", "local_checksum_md5", "match_status",
        "verification_date", "source_library",
    }
    for el in REQUIRED_ELEMENTS:
        v = m["elements"][el]["verification"]
        missing = required_fields - set(v.keys())
        assert not missing, (
            f"Element {el} verification block missing fields: {missing}"
        )


def test_manifest_all_match_status_are_match():
    """Every element must have match_status='match'. Fail loudly if any do not."""
    m = _load_manifest()
    for el in REQUIRED_ELEMENTS:
        status = m["elements"][el]["verification"]["match_status"]
        assert status == "match", (
            f"Element {el} has match_status='{status}'. "
            "The local pseudopotential file does not match the official SSSP checksum. "
            "Do NOT proceed with DFT until this is resolved."
        )


def test_manifest_ni_cr_source_library_is_gbrv():
    """Ni and Cr must be documented as GBRV, explaining the naming convention difference."""
    m = _load_manifest()
    for el in ("Ni", "Cr"):
        lib = m["elements"][el]["verification"]["source_library"]
        assert "GBRV" in lib, (
            f"Element {el} source_library should say GBRV; got: {lib!r}"
        )


def test_manifest_has_fe_cutoff_flag():
    """The Fe verification block must document the cutoff concern."""
    m = _load_manifest()
    fe_v = m["elements"]["Fe"]["verification"]
    assert "cutoff_flag" in fe_v or "cutoff_above_sssp_recommendation" in fe_v, (
        "Fe verification block must flag the ecutwfc=60 vs SSSP-recommended 90 Ry concern"
    )
    assert fe_v.get("cutoff_above_sssp_recommendation") is False, (
        "Fe: cutoff_above_sssp_recommendation should be False (60 Ry < 90 Ry)"
    )


# ──────────────────────────────────────────────
# Local file checksum verification
# ──────────────────────────────────────────────

def _compute_md5(path: Path, chunk_size: int = 1 << 20) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def _resolve_pseudo_path(manifest_path_str: str) -> Path:
    """Delegate to resolve_path from _common.py for cross-platform path translation."""
    return resolve_path(str(manifest_path_str))


@pytest.mark.parametrize("element", REQUIRED_ELEMENTS)
def test_local_file_md5_matches_official(element):
    """Local UPF file MD5 must match the official SSSP checksum in the manifest."""
    m = _load_manifest()
    v = m["elements"][element]["verification"]
    local_path = _resolve_pseudo_path(m["elements"][element]["path"])

    assert local_path.exists(), (
        f"Pseudopotential file for {element} not found at {local_path}. "
        "Check that the SSSP directory is mounted and accessible."
    )

    local_md5 = _compute_md5(local_path)
    official_md5 = v["local_checksum_md5"]

    assert local_md5 == official_md5, (
        f"CHECKSUM MISMATCH for {element}:\n"
        f"  file:     {local_path}\n"
        f"  computed: {local_md5}\n"
        f"  expected: {official_md5}\n"
        "The local file does not match the verified SSSP checksum. "
        "Do NOT run DFT until this is investigated."
    )


@pytest.mark.parametrize("element", REQUIRED_ELEMENTS)
def test_official_checksum_matches_manifest_local(element):
    """official_checksum_md5 and local_checksum_md5 in manifest must agree."""
    m = _load_manifest()
    v = m["elements"][element]["verification"]
    assert v["official_checksum_md5"] == v["local_checksum_md5"], (
        f"Element {element}: official_checksum_md5 and local_checksum_md5 "
        "disagree in the manifest — the manifest itself is inconsistent."
    )


# ──────────────────────────────────────────────
# Dataset CSV
# ──────────────────────────────────────────────

def test_dataset_has_pseudo_verified_column():
    assert DATASET_PATH.exists(), f"Dataset not found: {DATASET_PATH}"
    with DATASET_PATH.open(encoding="utf-8") as f:
        header = next(csv.reader(f))
    assert "pseudo_verified" in header, (
        "full_dataset_v0.2.csv is missing 'pseudo_verified' column — "
        "run Task 1 pseudopotential verification first."
    )


def test_dataset_pseudo_verified_all_true():
    """All 16 rows must have pseudo_verified=True after Task 1 completion."""
    rows = list(csv.DictReader(DATASET_PATH.open(encoding="utf-8")))
    not_verified = [r["system_id"] for r in rows if r.get("pseudo_verified") != "True"]
    assert not not_verified, (
        f"Rows with pseudo_verified != True: {not_verified}"
    )


def test_dataset_fe_cutoff_flag_present_for_fe_systems():
    """Fe-containing rows must have a non-empty fe_cutoff_flag."""
    rows = list(csv.DictReader(DATASET_PATH.open(encoding="utf-8")))
    fe_systems = {"ferrocene", "fe_co5"}
    for row in rows:
        sid = row["system_id"]
        is_fe = any(sid == s or sid.startswith(s + "__") for s in fe_systems)
        if is_fe:
            flag = row.get("fe_cutoff_flag", "")
            assert flag.strip(), (
                f"Row {sid} is Fe-containing but has empty fe_cutoff_flag — "
                "the ecutwfc concern is not documented in the dataset."
            )
