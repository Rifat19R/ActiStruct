"""Active learning + inverse design for H on Ni(111)."""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qe_active_inverse_common import ActiveSystem, Variable, run_system
from generated_models.structure_builders import build_adsorbate


def build_h_on_ni111(height: float, shift: float):
    return build_adsorbate('H', 'Ni', height, shift)


SYSTEM = ActiveSystem(
    key='h_on_ni111',
    title='H on Ni(111)',
    builder=build_h_on_ni111,
    variables=(
        Variable("height", 0.85, 1.15, (0.9, 1.0, 1.1, 0.95, 1.05)),
        Variable("shift", 0.85, 1.0, (0.86, 0.9, 0.95, 0.98, 1.0)),
    ),
    pseudopotentials={'H': 'H.pbe-rrkjus_psl.1.0.0.UPF', 'Ni': 'ni_pbe_v1.4.uspp.F.UPF'},
    ecutwfc=80.0,
    ecutrho=640.0,
    kpts=(6, 6, 1),
    smearing='mv',
    degauss=0.015,
    spin_polarized=True,
    energy_per_atom=False,
    result_quantity='Total energy objective',
    result_units='eV',
    n_candidates=81,
    random_state=141,
    category='Surface adsorption',
    notes="Total-energy-only objective for the generated 51-system benchmark.",
)


if __name__ == "__main__":
    run_system(SYSTEM)
