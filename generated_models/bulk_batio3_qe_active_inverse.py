"""Active learning + inverse design for Perovskite BaTiO3."""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qe_active_inverse_common import ActiveSystem, Variable, run_system
from generated_models.structure_builders import build_perovskite


def build_bulk_batio3(a: float):
    return build_perovskite('Ba', 'Ti', 'O', a)


SYSTEM = ActiveSystem(
    key='bulk_batio3',
    title='Perovskite BaTiO3',
    builder=build_bulk_batio3,
    variables=(
        Variable("a", 3.9, 4.15, (3.95, 4.0, 4.1)),
    ),
    pseudopotentials={'Ba': 'Ba.pbe-spn-kjpaw_psl.1.0.0.UPF', 'Ti': 'ti_pbe_v1.4.uspp.F.UPF', 'O': 'O.pbe-n-kjpaw_psl.0.1.UPF'},
    ecutwfc=70.0,
    ecutrho=560.0,
    kpts=(6, 6, 6),
    smearing='gaussian',
    degauss=0.01,
    spin_polarized=False,
    energy_per_atom=True,
    result_quantity='Total energy per atom objective',
    result_units='eV/atom',
    n_candidates=61,
    random_state=147,
    category='Complex structures',
    notes="Total-energy-only objective for the generated 50-system benchmark.",
)


if __name__ == "__main__":
    run_system(SYSTEM)
