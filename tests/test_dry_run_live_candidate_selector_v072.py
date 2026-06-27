from __future__ import annotations

import csv

from analysis.dry_run_live_candidate_selector_v072 import (
    OUTPUT_COLUMNS,
    STATUS,
    build_rows,
    write_table,
)

FORBIDDEN_HISTORICAL_COLUMNS = {
    "true_failure",
    "true_success",
    "known_energy_ev",
    "failure_label",
    "converged",
    "final_energy_ry",
}


def test_builds_rows_without_qe() -> None:
    rows = build_rows()

    assert rows


def test_all_rows_have_required_columns() -> None:
    rows = build_rows()

    for row in rows:
        assert set(OUTPUT_COLUMNS) == set(row.keys())


def test_all_rows_are_dry_run_only_and_review_required() -> None:
    rows = build_rows()

    for row in rows:
        assert row["status"] == STATUS == "dry_run_only"
        assert "review" in row["notes"].lower() or "not selected" in row["notes"].lower()


def test_no_historical_outcome_columns_present() -> None:
    rows = build_rows()

    for row in rows:
        assert FORBIDDEN_HISTORICAL_COLUMNS.isdisjoint(row.keys())


def test_science_fields_are_explicitly_not_computed() -> None:
    rows = build_rows()

    for row in rows:
        assert row["predicted_value"] == "not_computed"
        assert row["uncertainty_lcb_score"] == "not_computed"
        assert row["failure_risk"] == "not_computed"
        assert row["acquisition_score"] == "not_computed"


def test_every_row_has_a_selection_reason() -> None:
    rows = build_rows()

    for row in rows:
        assert row["selection_reason"]
        assert row["selection_category"]


def test_write_table_creates_csv_with_required_columns(tmp_path) -> None:
    rows = build_rows()
    out = tmp_path / "dry_run.csv"

    write_table(rows, out)

    with out.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        assert set(OUTPUT_COLUMNS) <= set(reader.fieldnames or [])
        written_rows = list(reader)
    assert len(written_rows) == len(rows)
