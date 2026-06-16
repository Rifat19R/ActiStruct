"""Active learning + inverse design for H2 Molecule."""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qe_active_inverse_common import ActiveSystem, Variable, run_system
from generated_models.structure_builders import build_linear_molecule


def build_h2_generated(bond: float):
    return build_linear_molecule("H2", bond)


SYSTEM = ActiveSystem(
    key='h2_generated',
    title='H2 Molecule',
    builder=build_h2_generated,
    variables=(
        Variable("bond", 0.55, 1.2, (0.6, 0.74, 1.05)),
    ),
    pseudopotentials={'H': 'H.pbe-rrkjus_psl.1.0.0.UPF'},
    ecutwfc=50.0,
    ecutrho=400.0,
    kpts=(1, 1, 1),
    smearing='gaussian',
    degauss=0.01,
    spin_polarized=False,
    energy_per_atom=False,
    result_quantity='Structure-search QE objective',
    result_units='eV',
    n_candidates=61,
    random_state=127,
    category='Molecules',
    notes="Total-energy-only objective for the generated 50-system benchmark.",
)


if __name__ == "__main__":
    run_system(SYSTEM)
