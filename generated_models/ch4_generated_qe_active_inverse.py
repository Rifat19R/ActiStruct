"""Active learning + inverse design for CH4 Molecule."""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qe_active_inverse_common import ActiveSystem, Variable, run_system
from generated_models.structure_builders import build_scaled_molecule


def build_ch4_generated(bond: float):
    return build_scaled_molecule("CH4", bond, reference_bond=1.09)


SYSTEM = ActiveSystem(
    key='ch4_generated',
    title='CH4 Molecule',
    builder=build_ch4_generated,
    variables=(
        Variable("bond", 0.95, 1.22, (1.0, 1.09, 1.18)),
    ),
    pseudopotentials={'C': 'C.pbe-n-kjpaw_psl.1.0.0.UPF', 'H': 'H.pbe-rrkjus_psl.1.0.0.UPF'},
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
    random_state=132,
    category='Molecules',
    notes="Total-energy-only objective for the generated 51-system benchmark.",
)


if __name__ == "__main__":
    run_system(SYSTEM)
