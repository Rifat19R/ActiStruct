from __future__ import annotations

import csv

from actistruct.acquisition import rank_candidates
from analysis.simulated_failure_aware_al_benchmark_v051 import (
    OUTPUT_COLUMNS,
    POLICIES,
    POOL_MODES,
    TOP_K_VALUES,
    aggregate_rows,
    gamma_zero_matches_lcb_only,
    render_report,
    run_stress_benchmark,
    write_table,
)


def test_benchmark_runs_without_qe() -> None:
    rows = run_stress_benchmark(_candidates(), n_trials=3)

    assert rows


def test_all_policies_appear() -> None:
    rows = run_stress_benchmark(_candidates(), n_trials=3)

    assert {row["policy"] for row in rows} == set(POLICIES)


def test_top_k_values_appear() -> None:
    rows = run_stress_benchmark(_candidates(), n_trials=3)

    assert {int(row["top_k"]) for row in rows} == set(TOP_K_VALUES)


def test_all_pool_modes_appear() -> None:
    rows = run_stress_benchmark(_candidates(), n_trials=3)

    assert {row["pool_mode"] for row in rows} == set(POOL_MODES)


def test_required_output_columns_present(tmp_path) -> None:
    rows = run_stress_benchmark(_candidates(), n_trials=3)
    out = tmp_path / "benchmark.csv"

    write_table(rows, out)

    with out.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        assert set(OUTPUT_COLUMNS) <= set(reader.fieldnames or [])


def test_delta_columns_present_and_zero_for_lcb_only() -> None:
    rows = run_stress_benchmark(_candidates(), n_trials=3)

    assert all("delta_failures_vs_lcb" in row and "delta_mean_risk_vs_lcb" in row for row in rows)
    lcb_rows = [row for row in rows if row["policy"] == "lcb_only"]
    assert lcb_rows
    assert all(row["delta_failures_vs_lcb"] == 0 for row in lcb_rows)
    assert all(row["delta_mean_risk_vs_lcb"] == 0.0 for row in lcb_rows)


def test_gamma_zero_matches_lcb_only_behavior() -> None:
    """The acquisition function at gamma=0 must reduce exactly to lcb_only
    ranking, independent of the failure_risk values present."""
    candidates = _candidates()
    assert gamma_zero_matches_lcb_only(candidates)

    high_risk_variant = [dict(c, failure_risk=1.0) for c in candidates]
    assert gamma_zero_matches_lcb_only(high_risk_variant)


def test_failure_aware_selection_does_not_hard_reject() -> None:
    candidates = _candidates()

    ranked = rank_candidates(candidates, objective="minimize", beta=2.0, gamma=1.0)

    assert len(ranked) == len(candidates)
    assert {row["candidate_id"] for row in ranked} == {row["candidate_id"] for row in candidates}


def test_csv_and_report_are_generated(tmp_path) -> None:
    rows = run_stress_benchmark(_candidates(), n_trials=3)
    summary = aggregate_rows(rows)
    table_path = tmp_path / "v051.csv"
    write_table(rows, table_path)

    report_text = render_report(rows, summary, table_path, n_base_candidates=len(_candidates()), n_trials=3)

    assert table_path.exists()
    assert report_text


def test_report_includes_required_caveats() -> None:
    rows = run_stress_benchmark(_candidates(), n_trials=3)
    summary = aggregate_rows(rows)

    report_text = render_report(rows, summary, "unused.csv", n_base_candidates=len(_candidates()), n_trials=3)

    assert "offline simulation" in report_text
    assert "no new QE/PBE validation was performed" in report_text
    assert "does not prove live DFT savings" in report_text
    assert "triage evidence, not a" in report_text


def test_report_includes_safe_claim_wording() -> None:
    rows = run_stress_benchmark(_candidates(), n_trials=3)
    summary = aggregate_rows(rows)

    report_text = render_report(rows, summary, "unused.csv", n_base_candidates=len(_candidates()), n_trials=3)

    assert "## Safe Claims" in report_text
    assert "reduced the mean predicted failure risk" in report_text
    safe_phrases = (
        "most clearly in",
        "did not consistently reduce known failed selections",
    )
    assert any(phrase in report_text for phrase in safe_phrases)
    assert "soft DFT triage signal, not a guarantee of live DFT savings" in report_text
    assert "ActiStruct guarantees fewer failed DFT jobs" not in report_text
    assert "always outperforms" not in report_text
    assert "proves live DFT savings" not in report_text


def test_reproducible_with_fixed_seed() -> None:
    candidates = _candidates()

    rows_a = run_stress_benchmark(candidates, n_trials=5, base_seed=7)
    rows_b = run_stress_benchmark(candidates, n_trials=5, base_seed=7)

    assert rows_a == rows_b


def _candidates() -> list[dict[str, object]]:
    """Synthetic candidate pool with enough size/material diversity/
    uncertainty spread for all four pool modes to build a non-trivial pool
    without depending on the real, large v0.5.0 data files."""
    materials = [f"mat{i}" for i in range(6)]
    rows: list[dict[str, object]] = []
    idx = 0
    for m_idx, material in enumerate(materials):
        for j in range(8):
            true_failure = 1 if (j % 4 == 0) else 0
            rows.append({
                "candidate_id": f"c{idx}",
                "material_id": material,
                "failure_label": "qe_error" if true_failure else "success",
                "true_failure": true_failure,
                "failure_risk": 0.05 + 0.1 * (j % 5),
                "predicted_value": 0.0,
                "uncertainty": (idx % 10) / 10.0,
                "known_energy_ev": None if true_failure else -float(idx),
            })
            idx += 1
    return rows
