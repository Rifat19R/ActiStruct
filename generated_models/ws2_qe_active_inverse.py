"""Active learning + inverse design for WS2 Monolayer 2x2."""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qe_active_inverse_common import ActiveSystem, Variable, run_system
from generated_models.structure_builders import build_mx2


def build_ws2(a: float, layer_half_thickness: float):
    return build_mx2("W", "S", a, layer_half_thickness)


SYSTEM = ActiveSystem(
    key='ws2',
    title='WS2 Monolayer 2x2',
    builder=build_ws2,
    variables=(
        Variable("a", 3.05, 3.3, (3.1, 3.18, 3.26, 3.14, 3.22)),
        Variable("layer_half_thickness", 1.45, 1.75, (1.5, 1.58, 1.7, 1.54, 1.66)),
    ),
    pseudopotentials={'W': 'W_pbe_v1.2.uspp.F.UPF', 'S': 's_pbe_v1.4.uspp.F.UPF'},
    ecutwfc=70.0,
    ecutrho=560.0,
    kpts=(6, 6, 1),
    smearing='gaussian',
    degauss=0.01,
    spin_polarized=False,
    energy_per_atom=True,
    result_quantity='Total energy per atom objective',
    result_units='eV/atom',
    n_candidates=81,
    random_state=125,
    category='2D materials',
    notes="Total-energy-only objective for the generated 50-system benchmark.",
)


if __name__ == "__main__":
    run_system(SYSTEM)
