"""Active learning + inverse design for H2O Molecule."""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qe_active_inverse_common import ActiveSystem, Variable, run_system
from generated_models.structure_builders import build_h2o


build_h2o_generated = build_h2o


SYSTEM = ActiveSystem(
    key='h2o_generated',
    title='H2O Molecule',
    builder=build_h2o_generated,
    variables=(
        Variable("bond", 0.85, 1.08, (0.88, 0.96, 1.05, 0.92, 1.02)),
        Variable("angle", 95.0, 115.0, (98.0, 104.5, 112.0, 101.0, 109.0)),
    ),
    pseudopotentials={'H': 'H.pbe-rrkjus_psl.1.0.0.UPF', 'O': 'O.pbe-n-kjpaw_psl.0.1.UPF'},
    ecutwfc=60.0,
    ecutrho=480.0,
    kpts=(1, 1, 1),
    smearing='gaussian',
    degauss=0.01,
    spin_polarized=False,
    energy_per_atom=False,
    result_quantity='Structure-search QE objective',
    result_units='eV',
    n_candidates=81,
    random_state=130,
    category='Molecules',
    notes="Total-energy-only objective for the generated 50-system benchmark.",
)


if __name__ == "__main__":
    run_system(SYSTEM)
