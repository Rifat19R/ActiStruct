"""Active learning + inverse design for Silicene 2x2."""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qe_active_inverse_common import ActiveSystem, Variable, run_system
from generated_models.structure_builders import build_graphene_like


def build_silicene(a: float, buckling: float):
    return build_graphene_like("Si2", a, vacuum=16.0, buckling=buckling)


SYSTEM = ActiveSystem(
    key='silicene',
    title='Silicene 2x2',
    builder=build_silicene,
    variables=(
        Variable("a", 3.7, 4.05, (3.75, 3.86, 4.0, 3.82, 3.95)),
        Variable("buckling", 0.25, 0.65, (0.3, 0.45, 0.6, 0.38, 0.55)),
    ),
    pseudopotentials={'Si': 'Si.pbe-n-rrkjus_psl.1.0.0.UPF'},
    ecutwfc=50.0,
    ecutrho=400.0,
    kpts=(6, 6, 1),
    smearing='gaussian',
    degauss=0.01,
    spin_polarized=False,
    energy_per_atom=True,
    result_quantity='Total energy per atom objective',
    result_units='eV/atom',
    n_candidates=81,
    random_state=123,
    category='2D materials',
    notes="Total-energy-only objective for the generated 51-system benchmark.",
)


if __name__ == "__main__":
    run_system(SYSTEM)
