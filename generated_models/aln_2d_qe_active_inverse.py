"""Active learning + inverse design for 2D AlN 2x2."""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qe_active_inverse_common import ActiveSystem, Variable, run_system
from generated_models.structure_builders import build_graphene_like


def build_aln_2d(a: float):
    return build_graphene_like("AlN", a, vacuum=16.0)


SYSTEM = ActiveSystem(
    key='aln_2d',
    title='2D AlN 2x2',
    builder=build_aln_2d,
    variables=(
        Variable("a", 3.0, 3.25, (3.05, 3.13, 3.22)),
    ),
    pseudopotentials={'Al': 'Al.pbe-n-kjpaw_psl.1.0.0.UPF', 'N': 'N.pbe-n-radius_5.UPF'},
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
    random_state=126,
    category='2D materials',
    notes="Total-energy-only objective for the generated 51-system benchmark.",
)


if __name__ == "__main__":
    run_system(SYSTEM)
