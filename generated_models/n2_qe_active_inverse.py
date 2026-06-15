"""Active learning + inverse design for N2 Molecule."""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qe_active_inverse_common import ActiveSystem, Variable, run_system
from generated_models.structure_builders import build_linear_molecule


def build_n2(bond: float):
    return build_linear_molecule("N2", bond)


SYSTEM = ActiveSystem(
    key='n2',
    title='N2 Molecule',
    builder=build_n2,
    variables=(
        Variable("bond", 0.9, 1.35, (0.95, 1.1, 1.28)),
    ),
    pseudopotentials={'N': 'N.pbe-n-radius_5.UPF'},
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
    random_state=128,
    category='Molecules',
    notes="Total-energy-only objective for the generated 51-system benchmark.",
)


if __name__ == "__main__":
    run_system(SYSTEM)
