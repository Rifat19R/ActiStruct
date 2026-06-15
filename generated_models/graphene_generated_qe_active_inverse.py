"""Active learning + inverse design for Graphene 2x2."""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qe_active_inverse_common import ActiveSystem, Variable, run_system
from generated_models.structure_builders import build_graphene_like


def build_graphene_generated(a: float):
    return build_graphene_like("C2", a, vacuum=15.0)


SYSTEM = ActiveSystem(
    key='graphene_generated',
    title='Graphene 2x2',
    builder=build_graphene_generated,
    variables=(
        Variable("a", 2.3, 2.7, (2.34, 2.46, 2.64)),
    ),
    pseudopotentials={'C': 'C.pbe-n-kjpaw_psl.1.0.0.UPF'},
    ecutwfc=50.0,
    ecutrho=400.0,
    kpts=(8, 8, 1),
    smearing='gaussian',
    degauss=0.02,
    spin_polarized=False,
    energy_per_atom=True,
    result_quantity='Total energy per atom objective',
    result_units='eV/atom',
    n_candidates=61,
    random_state=121,
    category='2D materials',
    notes="Total-energy-only objective for the generated 50-system benchmark.",
)


if __name__ == "__main__":
    run_system(SYSTEM)
