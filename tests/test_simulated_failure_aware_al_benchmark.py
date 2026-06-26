from __future__ import annotations

import csv

from actistruct.acquisition import rank_candidates
from analysis.simulated_failure_aware_al_benchmark_v05 import (
    OUTPUT_COLUMNS,
    POLICIES,
    TOP_K_VALUES,
    _record_energies,
    load_candidates,
    run_benchmark,
    write_table,
)


def test_benchmark_runs_without_qe() -> None:
    rows = run_benchmark(_candidates())

    assert rows


def test_all_policies_appear() -> None:
    rows = run_benchmark(_candidates())

    assert {row["policy"] for row in rows} == set(POLICIES)


def test_top_k_outputs_correct_row_counts() -> None:
    rows = run_benchmark(_candidates())

    assert len(rows) == len(POLICIES) * len(TOP_K_VALUES)
    assert {int(row["top_k"]) for row in rows} == set(TOP_K_VALUES)


def test_failure_aware_policy_does_not_hard_delete_candidates() -> None:
    candidates = _candidates()

    ranked = rank_candidates(candidates, gamma=1.0)

    assert len(ranked) == len(candidates)
    assert {row["candidate_id"] for row in ranked} == {row["candidate_id"] for row in candidates}


def test_gamma_zero_matches_lcb_only_behavior() -> None:
    """gamma=0 (the lcb_only policy) must rank purely by predicted_value/uncertainty,
    independent of failure_risk — i.e. it must not act as a hidden, hard-coded
    failure-risk penalty."""
    candidates = _candidates()
    high_risk_variant = [dict(c, failure_risk=1.0) for c in candidates]

    lcb_baseline = rank_candidates(candidates, gamma=0.0)
    lcb_with_high_risk = rank_candidates(high_risk_variant, gamma=0.0)

    assert [row["candidate_id"] for row in lcb_with_high_risk] == [
        row["candidate_id"] for row in lcb_baseline
    ]
    assert all(row["failure_penalty"] == 0.0 for row in lcb_with_high_risk)


def test_output_columns_are_present(tmp_path) -> None:
    rows = run_benchmark(_candidates())
    out = tmp_path / "benchmark.csv"

    write_table(rows, out)

    with out.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        assert set(OUTPUT_COLUMNS) <= set(reader.fieldnames or [])


def test_load_candidates_from_real_artifacts() -> None:
    candidates = load_candidates()

    assert candidates
    assert {"candidate_id", "true_failure", "failure_risk", "predicted_value", "uncertainty"} <= set(candidates[0])


def test_record_energies_never_substitutes_rydberg_for_ev(tmp_path) -> None:
    """energy_ev and final_energy_ry are different units. A row missing
    energy_ev must be skipped, not silently filled in with the Ry value."""
    records = tmp_path / "records.csv"
    with records.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["energy_ev", "final_energy_ry"])
        writer.writeheader()
        writer.writerow({"energy_ev": "-100.0", "final_energy_ry": "-7.35"})
        writer.writerow({"energy_ev": "", "final_energy_ry": "-7.35"})

    energies = _record_energies(records)

    assert energies == {"0": -100.0}


def _candidates() -> list[dict[str, object]]:
    base = [
        ("fail_low_lcb", 1, 0.9, 0.0, 0.5, None),
        ("safe_good", 0, 0.05, 0.1, 0.4, -2.0),
        ("safe_ok", 0, 0.1, 0.2, 0.1, -1.0),
        ("fail_high", 1, 0.8, 0.3, 0.2, None),
        ("safe_mid", 0, 0.2, 0.4, 0.3, -0.5),
    ]
    rows = []
    for repeat in range(4):
        for name, true_failure, risk, value, uncertainty, energy in base:
            rows.append({
                "candidate_id": f"{name}_{repeat}",
                "material_id": f"m{repeat}",
                "true_failure": true_failure,
                "failure_risk": risk,
                "predicted_value": value,
                "uncertainty": uncertainty,
                "known_energy_ev": energy,
            })
    return rows
