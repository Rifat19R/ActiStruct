"""Active learning + inverse design for NH3 Molecule."""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qe_active_inverse_common import ActiveSystem, Variable, run_system
from generated_models.structure_builders import build_scaled_molecule


def build_nh3(bond: float):
    return build_scaled_molecule("NH3", bond, reference_bond=1.02)


SYSTEM = ActiveSystem(
    key='nh3',
    title='NH3 Molecule',
    builder=build_nh3,
    variables=(
        Variable("bond", 0.92, 1.15, (0.95, 1.02, 1.12)),
    ),
    pseudopotentials={'N': 'N.pbe-n-radius_5.UPF', 'H': 'H.pbe-rrkjus_psl.1.0.0.UPF'},
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
    random_state=131,
    category='Molecules',
    notes="Total-energy-only objective for the generated 50-system benchmark.",
)


if __name__ == "__main__":
    run_system(SYSTEM)
