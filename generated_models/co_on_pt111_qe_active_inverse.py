"""Active learning + inverse design for CO on Pt(111)."""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qe_active_inverse_common import ActiveSystem, Variable, run_system
from generated_models.structure_builders import build_adsorbate


def build_co_on_pt111(height: float, shift: float):
    return build_adsorbate('CO', 'Pt', height, shift)


SYSTEM = ActiveSystem(
    key='co_on_pt111',
    title='CO on Pt(111)',
    builder=build_co_on_pt111,
    variables=(
        Variable("height", 1.75, 1.95, (1.77, 1.85, 1.93, 1.81, 1.89)),
        Variable("shift", 0.0, 0.15, (0.0, 0.04, 0.08, 0.12, 0.15)),
    ),
    pseudopotentials={'C': 'C.pbe-n-kjpaw_psl.1.0.0.UPF', 'O': 'O.pbe-n-kjpaw_psl.0.1.UPF', 'Pt': 'pt_pbe_v1.4.uspp.F.UPF'},
    ecutwfc=80.0,
    ecutrho=640.0,
    kpts=(6, 6, 1),
    smearing='mv',
    degauss=0.015,
    spin_polarized=False,
    energy_per_atom=False,
    result_quantity='Structure-search QE objective',
    result_units='eV',
    n_candidates=81,
    random_state=145,
    category='Surface adsorption',
    notes="Total-energy-only objective for the generated 50-system benchmark.",
)


if __name__ == "__main__":
    run_system(SYSTEM)
