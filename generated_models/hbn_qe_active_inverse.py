"""Active learning + inverse design for h-BN 2x2."""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qe_active_inverse_common import ActiveSystem, Variable, run_system
from generated_models.structure_builders import build_graphene_like


def build_hbn(a: float):
    return build_graphene_like("BN", a, vacuum=15.0)


SYSTEM = ActiveSystem(
    key='hbn',
    title='h-BN 2x2',
    builder=build_hbn,
    variables=(
        Variable("a", 2.35, 2.65, (2.4, 2.5, 2.6)),
    ),
    pseudopotentials={'B': 'b_pbe_v1.4.uspp.F.UPF', 'N': 'N.pbe-n-radius_5.UPF'},
    ecutwfc=60.0,
    ecutrho=480.0,
    kpts=(8, 8, 1),
    smearing='gaussian',
    degauss=0.01,
    spin_polarized=False,
    energy_per_atom=True,
    result_quantity='Total energy per atom objective',
    result_units='eV/atom',
    n_candidates=61,
    random_state=122,
    category='2D materials',
    notes="Total-energy-only objective for the generated 51-system benchmark.",
)


if __name__ == "__main__":
    run_system(SYSTEM)
