"""Active learning + inverse design for LiTiO2 from a CIF cell."""

from __future__ import annotations

from pathlib import Path
import sys

from ase import Atoms

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qe_active_inverse_common import ActiveSystem, Variable, run_system


# CIF reference supplied by the user:
# a=b=4.04607443, c=8.41536354, alpha=beta=gamma=90, Z=4.
# The optimization scales a while preserving the CIF c/a ratio and fixed
# fractional coordinates.
_CIF_A = 4.04607443
_CIF_C_OVER_A = 8.41536354 / _CIF_A
_LITIO2_SYMBOLS = ["Li"] * 4 + ["Ti"] * 4 + ["O"] * 8
_LITIO2_SCALED_POSITIONS = [
    (0.50000000, 0.50000000, 0.00000000),
    (0.50000000, 0.00000000, 0.25000000),
    (0.00000000, 0.00000000, 0.50000000),
    (0.00000000, 0.50000000, 0.75000000),
    (0.00000000, 0.00000000, 0.00000000),
    (0.00000000, 0.50000000, 0.25000000),
    (0.50000000, 0.50000000, 0.50000000),
    (0.50000000, 0.00000000, 0.75000000),
    (0.00000000, 0.00000000, 0.24982148),
    (0.00000000, 0.50000000, 0.00017852),
    (0.50000000, 0.00000000, 0.99982148),
    (0.00000000, 0.00000000, 0.75017852),
    (0.50000000, 0.50000000, 0.74982148),
    (0.50000000, 0.00000000, 0.50017852),
    (0.00000000, 0.50000000, 0.49982148),
    (0.50000000, 0.50000000, 0.25017852),
]


def build_bulk_litio2(a: float) -> Atoms:
    a = float(a)
    atoms = Atoms(
        _LITIO2_SYMBOLS,
        cell=[a, a, _CIF_C_OVER_A * a],
        pbc=True,
    )
    atoms.set_scaled_positions(_LITIO2_SCALED_POSITIONS)
    atoms.wrap()
    return atoms


SYSTEM = ActiveSystem(
    key='bulk_litio2',
    title='LiTiO2 Model',
    builder=build_bulk_litio2,
    variables=(
        Variable("a", 3.95, 4.15, (3.98, _CIF_A, 4.12)),
    ),
    pseudopotentials={
        'Li': 'li_pbe_v1.4.uspp.F.UPF',
        'Ti': 'ti_pbe_v1.4.uspp.F.UPF',
        'O': 'O.pbe-n-kjpaw_psl.0.1.UPF',
    },
    ecutwfc=80.0,
    ecutrho=640.0,
    kpts=(6, 6, 3),
    smearing='gaussian',
    degauss=0.01,
    spin_polarized=False,
    energy_per_atom=True,
    result_quantity='Total energy per atom objective',
    result_units='eV/atom',
    n_candidates=61,
    random_state=137,
    category='Battery materials',
    notes="CIF-derived Li4Ti4O8 tetragonal cell; fractional coordinates fixed while a scales c.",
)


if __name__ == "__main__":
    run_system(SYSTEM)