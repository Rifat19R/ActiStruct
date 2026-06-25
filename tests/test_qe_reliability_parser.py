from __future__ import annotations

import pytest

from actistruct.parsers.qe import RY_TO_EV, parse_qe_output_text


QE_INPUT = """
&CONTROL
  calculation = 'scf'
/
&SYSTEM
  ecutwfc = 50.0
  ecutrho = 400.0
  smearing = 'marzari-vanderbilt'
/
&ELECTRONS
  mixing_beta = 0.3
/
ATOMIC_SPECIES
Si 28.0855 Si.pbe-n-rrkjus_psl.1.0.0.UPF
O  15.9994 O.pbe-n-kjpaw_psl.1.0.0.UPF
K_POINTS automatic
4 4 4 0 0 0
"""


def test_parse_successful_qe_output_with_input_metadata() -> None:
    output = """
     iteration #  1
     iteration #  2
     convergence has been achieved in   2 iterations
!    total energy              =     -42.50000000 Ry
     Total force =     0.000123     Total SCF correction =     0.000001
     total   stress  (Ry/bohr**3)                   (kbar)     P=    1.23
     PWSCF        :   1m 2.00s CPU   1m 3.00s WALL
   JOB DONE.
"""

    record = parse_qe_output_text(
        output,
        input_text=QE_INPUT,
        material_id="si_o_test",
        qe_output_path="espresso.pwo",
        qe_input_path="espresso.pwi",
    )

    assert record.material_id == "si_o_test"
    assert record.converged is True
    assert record.job_done is True
    assert record.scf_iterations == 2
    assert record.final_energy_ry == pytest.approx(-42.5)
    assert record.energy_ev == pytest.approx(-42.5 * RY_TO_EV)
    assert record.max_force == pytest.approx(0.000123)
    assert record.pressure_kbar == pytest.approx(1.23)
    assert record.wall_time == "1m 3.00s WALL"
    assert record.failure_reason is None
    assert record.ecutwfc == pytest.approx(50.0)
    assert record.ecutrho == pytest.approx(400.0)
    assert record.mixing_beta == pytest.approx(0.3)
    assert record.smearing == "marzari-vanderbilt"
    assert record.kpoints == "4 4 4 0 0 0"
    assert record.pseudopotentials == {
        "Si": "Si.pbe-n-rrkjus_psl.1.0.0.UPF",
        "O": "O.pbe-n-kjpaw_psl.1.0.0.UPF",
    }
    assert record.pseudo_family == "PSLibrary"
    assert len(record.calculation_hash or "") == 64


def test_parse_failed_qe_namelist_error() -> None:
    output = """
 %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
     from  read_namelists : error #         2
      could not find namelist &control
 %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
"""

    record = parse_qe_output_text(output, material_id="bad_input")

    assert record.material_id == "bad_input"
    assert record.converged is False
    assert record.job_done is False
    assert record.failure_reason == "invalid_input_namelist"
    assert record.final_energy_ry is None
    assert record.energy_ev is None


def test_parse_scf_not_converged_but_energy_present() -> None:
    output = """
     iteration #  1
     iteration #  80
     convergence NOT achieved after 80 iterations: stopping
!    total energy              =      -9.25000000 Ry
   JOB DONE.
"""

    record = parse_qe_output_text(output)

    assert record.converged is False
    assert record.job_done is True
    assert record.scf_iterations == 80
    assert record.failure_reason == "scf_not_converged"
    assert record.energy_ev == pytest.approx(-9.25 * RY_TO_EV)

