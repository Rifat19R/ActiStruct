"""Active learning + inverse design for O on Ni(111)."""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qe_active_inverse_common import ActiveSystem, Variable, run_system
from generated_models.structure_builders import build_adsorbate


def build_o_on_ni111(height: float, shift: float):
    return build_adsorbate('O', 'Ni', height, shift)


SYSTEM = ActiveSystem(
    key='o_on_ni111',
    title='O on Ni(111)',
    builder=build_o_on_ni111,
    variables=(
        Variable("height", 1.0, 1.2, (1.02, 1.1, 1.18, 1.06, 1.14)),
        Variable("shift", 0.85, 1.0, (0.86, 0.9, 0.95, 0.98, 1.0)),
    ),
    pseudopotentials={'O': 'O.pbe-n-kjpaw_psl.0.1.UPF', 'Ni': 'ni_pbe_v1.4.uspp.F.UPF'},
    ecutwfc=80.0,
    ecutrho=640.0,
    kpts=(6, 6, 1),
    smearing='mv',
    degauss=0.015,
    spin_polarized=True,
    energy_per_atom=False,
    result_quantity='Structure-search QE objective',
    result_units='eV',
    n_candidates=81,
    random_state=142,
    category='Surface adsorption',
    notes="Total-energy-only objective for the generated 50-system benchmark.",
)


if __name__ == "__main__":
    run_system(SYSTEM)
