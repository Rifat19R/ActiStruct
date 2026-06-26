from __future__ import annotations

import csv

from analysis.summarize_qe_reliability_records import render_report, summarize_rows


FIELDS = [
    "material_id",
    "qe_input_path",
    "qe_output_path",
    "converged",
    "job_done",
    "scf_iterations",
    "final_energy_ry",
    "energy_ev",
    "max_force",
    "pressure_kbar",
    "wall_time",
    "failure_reason",
    "ecutwfc",
    "ecutrho",
    "kpoints",
    "smearing",
    "mixing_beta",
    "pseudo_family",
    "pseudopotentials",
    "calculation_hash",
]


def test_summarize_rows_counts_failures_and_metadata() -> None:
    rows = [
        _row("h2", "True", "True", "", '{"H":"H.UPF"}'),
        _row("mos2", "False", "True", "scf_not_converged", '{"Mo":"Mo.UPF","S":"S.UPF"}'),
        _row("mos2", "False", "False", "job_not_completed", '{"Mo":"Mo.UPF","S":"S.UPF"}'),
    ]

    summary = summarize_rows(rows)

    assert summary["total"] == 3
    assert summary["converged"] == 1
    assert summary["not_converged"] == 2
    assert summary["failure_reasons"]["success"] == 1
    assert summary["failure_reasons"]["scf_not_converged"] == 1
    assert summary["materials"]["mos2"] == 2
    assert summary["elements"]["S"] == 2
    assert summary["pseudo_families"]["PSLibrary"] == 3
    assert summary["missing"]["failure_reason"] == 1


def test_render_report_includes_counts_and_scientific_caveat(tmp_path) -> None:
    main_summary = summarize_rows([_row("h2", "True", "True", "", '{"H":"H.UPF"}')])
    quarantine_summary = summarize_rows([
        _row("bad", "False", "False", "geometry_overlap", '{"Li":"Li.UPF"}')
    ])

    report = render_report(
        main_summary,
        quarantine_summary,
        tmp_path / "main.csv",
        tmp_path / "bad.csv",
    )

    assert "Main records: **1**" in report
    assert "Invalid-geometry quarantine records: **1**" in report
    assert "not yet strong enough for a general DFT reliability claim" in report


def test_summary_rows_round_trip_from_csv(tmp_path) -> None:
    path = tmp_path / "records.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerow(_row("h2", "True", "True", "", '{"H":"H.UPF"}'))

    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert summarize_rows(rows)["total"] == 1


def _row(
    material_id: str,
    converged: str,
    job_done: str,
    failure_reason: str,
    pseudopotentials: str,
) -> dict[str, str]:
    row = {field: "" for field in FIELDS}
    row.update({
        "material_id": material_id,
        "converged": converged,
        "job_done": job_done,
        "failure_reason": failure_reason,
        "ecutwfc": "50.0",
        "ecutrho": "400.0",
        "kpoints": "1 1 1 0 0 0",
        "smearing": "gaussian",
        "pseudo_family": "PSLibrary",
        "pseudopotentials": pseudopotentials,
    })
    return row

