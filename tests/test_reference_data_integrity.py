"""Sanity checks on the populated references/reference_values_tmc_v0.yaml.

These guard against exactly the failure modes the project forbids:
fabricated DOIs, bond-length values with no traceable source, and silently
upgrading a system's status without an actual human review.
"""
import re
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REFERENCE_PATH = PROJECT_ROOT / "references" / "reference_values_tmc_v0.yaml"
SOURCES_CSV_PATH = PROJECT_ROOT / "references" / "reference_sources_v0.csv"

DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$")


def load_reference_data() -> dict:
    return yaml.safe_load(REFERENCE_PATH.read_text(encoding="utf-8"))


def test_all_four_systems_present():
    data = load_reference_data()
    assert set(data.keys()) == {"ferrocene", "ni_co4", "cr_co6", "fe_co5"}


def test_every_bond_length_has_a_value_and_a_valid_source_reference():
    data = load_reference_data()
    for system_id, entry in data.items():
        sources = entry.get("sources", {})
        for bond in entry["reference_values"]["bond_lengths"]:
            assert bond["value_angstrom"] is not None, f"{system_id}: {bond['label']} has no value"
            assert bond["source_id"] in sources, \
                f"{system_id}: {bond['label']} references unknown source_id '{bond['source_id']}'"


def test_every_doi_present_is_syntactically_valid_and_not_a_placeholder():
    data = load_reference_data()
    seen_dois = set()
    for system_id, entry in data.items():
        for source_id, src in entry.get("sources", {}).items():
            doi = src.get("doi")
            if doi is None:
                continue
            assert DOI_RE.match(doi), f"{system_id}/{source_id}: malformed DOI '{doi}'"
            assert doi not in ("10.0000/example", "10.1234/fake"), \
                f"{system_id}/{source_id}: looks like a placeholder DOI"
            seen_dois.add(doi)
    assert len(seen_dois) >= 4, "expected at least one distinct real DOI per system"


def test_no_system_claims_full_pdf_verification_without_access():
    """No system may use a status that implies primary-PDF verification.

    Task 4 (2026-07-14) legitimately elevated statuses to:
      - 'cross_verified_secondary': values confirmed via secondary sources
        (Wikipedia, HandWiki) that explicitly cite the primary paper.
      - 'confirmed_from_primary_abstract': values confirmed character-by-character
        from a publicly accessible primary abstract (PubMed).
    All four publisher PDFs remain access-gated (HTTP 403). Any status implying
    full primary-PDF verification is prohibited until Rifat reviews the PDFs
    with institutional access.
    """
    ALLOWED = {
        "needs_manual_review",
        "cross_verified_secondary",
        "confirmed_from_primary_abstract",
    }
    data = load_reference_data()
    for system_id, entry in data.items():
        status = entry["status"]
        assert status in ALLOWED, (
            f"{system_id}: status='{status}' is not an allowed verification level. "
            f"Allowed post-Task-4 values: {sorted(ALLOWED)}"
        )


def test_uncertainty_values_are_plausible_diffraction_precision():
    """Populated uncertainties should be small (diffraction-precision
    residuals, e.g. +-0.002-0.02 A), not an order-of-magnitude guess."""
    data = load_reference_data()
    for system_id, entry in data.items():
        for bond in entry["reference_values"]["bond_lengths"]:
            unc = bond["uncertainty_angstrom"]
            if unc is not None:
                assert 0 < unc < 0.1, \
                    f"{system_id}: {bond['label']} uncertainty {unc} A looks implausible for diffraction data"


def test_reference_sources_csv_matches_yaml_source_ids():
    import csv
    data = load_reference_data()
    yaml_source_ids = {sid for entry in data.values() for sid in entry.get("sources", {})}
    with SOURCES_CSV_PATH.open(encoding="utf-8") as f:
        csv_source_ids = {row["source_id"] for row in csv.DictReader(f)}
    assert yaml_source_ids == csv_source_ids


def test_ferrocene_bond_lengths_within_generic_sanity_range():
    """Cross-check against scripts/08_validate_dataset.py's own generic
    bonding sanity ranges - the reference values themselves should obviously
    pass the same gross-error bounds applied to QE results."""
    from _load import load_script
    val_mod = load_script("08_validate_dataset.py")
    data = load_reference_data()
    for system_id in ("ferrocene", "ni_co4", "cr_co6", "fe_co5"):
        for bond in data[system_id]["reference_values"]["bond_lengths"]:
            label = bond["label"]
            elements = [e for e in ("Fe", "Ni", "Cr", "C", "O", "H") if e in label]
            if len(elements) != 2:
                continue
            bounds = val_mod.BOND_RANGES_ANGSTROM.get(frozenset(elements))
            if bounds is None:
                continue
            lo, hi = bounds
            assert lo <= bond["value_angstrom"] <= hi, \
                f"{system_id}: literature {label}={bond['value_angstrom']} outside sanity range [{lo},{hi}]"
