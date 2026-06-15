"""Active learning + inverse design for B2 NiAl."""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qe_active_inverse_common import ActiveSystem, Variable, run_system
from generated_models.structure_builders import build_nial


build_bulk_nial = build_nial


SYSTEM = ActiveSystem(
    key='bulk_nial',
    title='B2 NiAl',
    builder=build_bulk_nial,
    variables=(
        Variable("a", 2.75, 3.05, (2.8, 2.89, 3.0)),
    ),
    pseudopotentials={'Ni': 'ni_pbe_v1.4.uspp.F.UPF', 'Al': 'Al.pbe-n-kjpaw_psl.1.0.0.UPF'},
    ecutwfc=70.0,
    ecutrho=560.0,
    kpts=(10, 10, 10),
    smearing='mv',
    degauss=0.02,
    spin_polarized=True,
    energy_per_atom=True,
    result_quantity='Total energy per atom objective',
    result_units='eV/atom',
    n_candidates=61,
    random_state=149,
    category='Complex structures',
    notes="Total-energy-only objective for the generated 51-system benchmark.",
)


if __name__ == "__main__":
    run_system(SYSTEM)
