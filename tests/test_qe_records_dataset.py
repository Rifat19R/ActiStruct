from __future__ import annotations

import csv

from actistruct.datasets.qe_records import QE_RECORD_FIELDS, build_records, write_records_csv


SUCCESS_INPUT = """
&SYSTEM
  ecutwfc = 50.0
  ecutrho = 400.0
/
&ELECTRONS
  mixing_beta = 0.3
/
ATOMIC_SPECIES
H 1.0 H.pbe-rrkjus_psl.1.0.0.UPF
K_POINTS automatic
1 1 1 0 0 0
"""

SUCCESS_OUTPUT = """
     convergence has been achieved in   6 iterations
!    total energy              =      -2.31202217 Ry
     Total force =     0.000010
     PWSCF        :   1m 2.00s CPU   1m 3.00s WALL
   JOB DONE.
"""

FAILED_OUTPUT = """
     Program PWSCF v.7.4.1 starts
 %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
     Error in routine check_atoms (1):
     atoms #   1 and #   2 overlap!
 %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
     stopping ...
"""


def test_build_records_scans_success_and_failed_runs(tmp_path) -> None:
    success = tmp_path / "outputs" / "qe_runs" / "h2_r0p900000_pid1_attempt1"
    failed = tmp_path / "outputs" / "qe_runs_bulk_li2nav2po43" / "a8p1700_pid2_att1"
    success.mkdir(parents=True)
    failed.mkdir(parents=True)
    (success / "espresso.pwi").write_text(SUCCESS_INPUT, encoding="utf-8")
    (success / "espresso.pwo").write_text(SUCCESS_OUTPUT, encoding="utf-8")
    (failed / "espresso.pwi").write_text(SUCCESS_INPUT, encoding="utf-8")
    (failed / "espresso.pwo").write_text("Program PWSCF starts\n", encoding="utf-8")
    (failed / "CRASH").write_text(FAILED_OUTPUT, encoding="utf-8")

    records = build_records([tmp_path / "outputs"], base_path=tmp_path)

    assert len(records) == 2
    assert [record.material_id for record in records] == ["h2_r0p900000", "bulk_li2nav2po43"]
    assert records[0].converged is True
    assert records[0].failure_reason is None
    assert records[1].converged is False
    assert records[1].failure_reason == "geometry_overlap"
    assert records[1].final_energy_ry is None


def test_write_records_csv_uses_stable_columns_and_json_pseudos(tmp_path) -> None:
    run_dir = tmp_path / "outputs" / "qe_runs" / "h2_r0p900000_pid1_attempt1"
    run_dir.mkdir(parents=True)
    (run_dir / "espresso.pwi").write_text(SUCCESS_INPUT, encoding="utf-8")
    (run_dir / "espresso.pwo").write_text(SUCCESS_OUTPUT, encoding="utf-8")
    records = build_records([run_dir], base_path=tmp_path)
    out = tmp_path / "parsed_records.csv"

    write_records_csv(records, out)

    with out.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    assert reader.fieldnames == QE_RECORD_FIELDS
    assert len(rows) == 1
    assert rows[0]["material_id"] == "h2_r0p900000"
    assert rows[0]["qe_output_path"] == (
        "outputs/qe_runs/h2_r0p900000_pid1_attempt1/espresso.pwo"
    )
    assert rows[0]["pseudopotentials"] == '{"H":"H.pbe-rrkjus_psl.1.0.0.UPF"}'

