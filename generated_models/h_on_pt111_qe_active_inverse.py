"""Active learning + inverse design for H on Pt(111)."""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qe_active_inverse_common import ActiveSystem, Variable, run_system
from generated_models.structure_builders import build_adsorbate


def build_h_on_pt111(height: float, shift: float):
    return build_adsorbate('H', 'Pt', height, shift)


SYSTEM = ActiveSystem(
    key='h_on_pt111',
    title='H on Pt(111)',
    builder=build_h_on_pt111,
    variables=(
        Variable("height", 0.95, 1.2, (0.98, 1.1, 1.18, 1.04, 1.14)),
        Variable("shift", 0.85, 1.0, (0.86, 0.9, 0.95, 0.98, 1.0)),
    ),
    pseudopotentials={'H': 'H.pbe-rrkjus_psl.1.0.0.UPF', 'Pt': 'pt_pbe_v1.4.uspp.F.UPF'},
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
    random_state=144,
    category='Surface adsorption',
    notes="Total-energy-only objective for the generated 50-system benchmark.",
)


if __name__ == "__main__":
    run_system(SYSTEM)
