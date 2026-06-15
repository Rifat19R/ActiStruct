"""Active learning + inverse design for H on Cu(111)."""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qe_active_inverse_common import ActiveSystem, Variable, run_system
from generated_models.structure_builders import build_adsorbate


def build_h_on_cu111(height: float, shift: float):
    return build_adsorbate('H', 'Cu', height, shift)


SYSTEM = ActiveSystem(
    key='h_on_cu111',
    title='H on Cu(111)',
    builder=build_h_on_cu111,
    variables=(
        Variable("height", 0.85, 1.15, (0.9, 1.0, 1.1, 0.95, 1.05)),
        Variable("shift", 0.85, 1.0, (0.86, 0.9, 0.95, 0.98, 1.0)),
    ),
    pseudopotentials={'H': 'H.pbe-rrkjus_psl.1.0.0.UPF', 'Cu': 'Cu.paw.z_11.ld1.psl.v1.0.0-low.upf'},
    ecutwfc=80.0,
    ecutrho=640.0,
    kpts=(6, 6, 1),
    smearing='mv',
    degauss=0.015,
    spin_polarized=False,
    energy_per_atom=False,
    result_quantity='Total energy objective',
    result_units='eV',
    n_candidates=81,
    random_state=138,
    category='Surface adsorption',
    notes="Total-energy-only objective for the generated 51-system benchmark.",
)


if __name__ == "__main__":
    run_system(SYSTEM)
