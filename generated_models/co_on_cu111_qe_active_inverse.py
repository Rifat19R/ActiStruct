"""Active learning + inverse design for CO on Cu(111)."""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qe_active_inverse_common import ActiveSystem, Variable, run_system
from generated_models.structure_builders import build_adsorbate


def build_co_on_cu111(height: float, shift: float):
    return build_adsorbate('CO', 'Cu', height, shift)


SYSTEM = ActiveSystem(
    key='co_on_cu111',
    title='CO on Cu(111)',
    builder=build_co_on_cu111,
    variables=(
        Variable("height", 1.8, 2.0, (1.82, 1.9, 1.98, 1.86, 1.94)),
        Variable("shift", 0.0, 0.15, (0.0, 0.04, 0.08, 0.12, 0.15)),
    ),
    pseudopotentials={'C': 'C.pbe-n-kjpaw_psl.1.0.0.UPF', 'O': 'O.pbe-n-kjpaw_psl.0.1.UPF', 'Cu': 'Cu.paw.z_11.ld1.psl.v1.0.0-low.upf'},
    ecutwfc=80.0,
    ecutrho=640.0,
    kpts=(6, 6, 1),
    smearing='mv',
    degauss=0.015,
    spin_polarized=False,
    energy_per_atom=False,
    result_quantity='Structure-search QE objective',
    result_units='eV',
    n_candidates=81,
    random_state=140,
    category='Surface adsorption',
    notes="Total-energy-only objective for the generated 51-system benchmark.",
)


if __name__ == "__main__":
    run_system(SYSTEM)
