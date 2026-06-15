"""Active learning + inverse design for layered LiCoO2 from a CIF cell."""

from __future__ import annotations

from math import sqrt
from pathlib import Path
import sys

from ase import Atoms

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qe_active_inverse_common import ActiveSystem, Variable, run_system


# CIF reference supplied by the user:
# a=b=2.88136916, c=15.43996543, alpha=beta=90, gamma=120, Z=3.
# The optimization keeps the CIF fractional coordinates fixed and varies a and c/a.
_CIF_C_OVER_A = 15.43996543 / 2.88136916
_LICOO2_SYMBOLS = ["Li"] * 3 + ["Co"] * 3 + ["O"] * 6
_LICOO2_SCALED_POSITIONS = [
    (0.00000000, 0.00000000, 0.00000000),
    (0.66666667, 0.33333333, 0.33333333),
    (0.33333333, 0.66666667, 0.66666667),
    (0.66666667, 0.33333333, 0.83333333),
    (0.33333333, 0.66666667, 0.16666667),
    (1.00000000, 1.00000000, 0.50000000),
    (0.33333333, 0.66666667, 0.89725961),
    (0.00000000, 0.00000000, 0.76940706),
    (0.00000000, 0.00000000, 0.23059294),
    (0.66666667, 0.33333333, 0.10274039),
    (0.66666667, 0.33333333, 0.56392627),
    (0.33333333, 0.66666667, 0.43607373),
]


def build_bulk_licoo2_generated(a: float, c_over_a: float) -> Atoms:
    a = float(a)
    c = float(c_over_a) * a
    cell = [
        (a, 0.0, 0.0),
        (-0.5 * a, 0.5 * sqrt(3.0) * a, 0.0),
        (0.0, 0.0, c),
    ]
    atoms = Atoms(_LICOO2_SYMBOLS, cell=cell, pbc=True)
    atoms.set_scaled_positions(_LICOO2_SCALED_POSITIONS)
    atoms.wrap()
    return atoms


SYSTEM = ActiveSystem(
    key='bulk_licoo2_generated',
    title='Layered LiCoO2 Model',
    builder=build_bulk_licoo2_generated,
    variables=(
        Variable("a", 2.82, 2.94, (2.84, 2.88136916, 2.92, 2.86, 2.90)),
        Variable("c_over_a", 5.20, 5.50, (5.25, _CIF_C_OVER_A, 5.45, 5.30, 5.40)),
    ),
    pseudopotentials={
        'Li': 'li_pbe_v1.4.uspp.F.UPF',
        'Co': 'Co_pbe_v1.2.uspp.F.UPF',
        'O': 'O.pbe-n-kjpaw_psl.0.1.UPF',
    },
    ecutwfc=80.0,
    ecutrho=640.0,
    kpts=(6, 6, 2),
    smearing='mv',
    degauss=0.02,
    spin_polarized=True,
    energy_per_atom=True,
    result_quantity='Total energy per atom objective',
    result_units='eV/atom',
    n_candidates=81,
    random_state=134,
    category='Battery materials',
    notes="CIF-derived Li3Co3O6 hexagonal cell; fractional coordinates fixed while a and c/a vary.",
)


if __name__ == "__main__":
    run_system(SYSTEM)