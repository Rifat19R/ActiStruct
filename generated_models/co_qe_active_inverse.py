"""Active learning + inverse design for CO Molecule."""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qe_active_inverse_common import ActiveSystem, Variable, run_system
from generated_models.structure_builders import build_linear_molecule


def build_co(bond: float):
    return build_linear_molecule("CO", bond)


SYSTEM = ActiveSystem(
    key='co',
    title='CO Molecule',
    builder=build_co,
    variables=(
        Variable("bond", 0.95, 1.35, (1.0, 1.13, 1.28)),
    ),
    pseudopotentials={'C': 'C.pbe-n-kjpaw_psl.1.0.0.UPF', 'O': 'O.pbe-n-kjpaw_psl.0.1.UPF'},
    ecutwfc=60.0,
    ecutrho=480.0,
    kpts=(1, 1, 1),
    smearing='gaussian',
    degauss=0.01,
    spin_polarized=False,
    energy_per_atom=False,
    result_quantity='Structure-search QE objective',
    result_units='eV',
    n_candidates=61,
    random_state=129,
    category='Molecules',
    notes="Total-energy-only objective for the generated 51-system benchmark.",
)


if __name__ == "__main__":
    run_system(SYSTEM)
