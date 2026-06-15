"""Active learning + inverse design for LiFePO4 from a CIF cell."""

from __future__ import annotations

from pathlib import Path
import sys

from ase import Atoms

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qe_active_inverse_common import ActiveSystem, Variable, run_system


# CIF reference supplied by the user:
# a=4.65491719, b=5.97075510, c=10.23619605, alpha=beta=gamma=90, Z=4.
# The optimization scales a while preserving the CIF b/a and c/a ratios and
# fixed fractional coordinates.
_CIF_A = 4.65491719
_CIF_B_OVER_A = 5.97075510 / _CIF_A
_CIF_C_OVER_A = 10.23619605 / _CIF_A
_LIFEPO4_SYMBOLS = ["Li"] * 4 + ["Fe"] * 4 + ["P"] * 4 + ["O"] * 16
_LIFEPO4_SCALED_POSITIONS = [
    (0.00000000, 0.00000000, 0.00000000),
    (0.50000000, 0.50000000, 0.50000000),
    (0.50000000, 0.00000000, 0.50000000),
    (0.00000000, 0.50000000, 0.00000000),
    (0.52986573, 0.25000000, 0.78115127),
    (0.02986573, 0.75000000, 0.71884873),
    (0.97013427, 0.25000000, 0.28115127),
    (0.47013427, 0.75000000, 0.21884873),
    (0.41862257, 0.25000000, 0.09386630),
    (0.91862257, 0.75000000, 0.40613370),
    (0.08137743, 0.25000000, 0.59386630),
    (0.58137743, 0.75000000, 0.90613370),
    (0.74478656, 0.25000000, 0.09423067),
    (0.71373534, 0.54555803, 0.83415452),
    (0.71373534, 0.95444197, 0.83415452),
    (0.25521344, 0.75000000, 0.90576933),
    (0.70986445, 0.75000000, 0.04430856),
    (0.24478656, 0.75000000, 0.40576933),
    (0.28626466, 0.04555803, 0.16584548),
    (0.21373534, 0.45444197, 0.66584548),
    (0.78626466, 0.54555803, 0.33415452),
    (0.78626466, 0.95444197, 0.33415452),
    (0.29013555, 0.25000000, 0.95569144),
    (0.20986445, 0.25000000, 0.45569144),
    (0.79013555, 0.75000000, 0.54430856),
    (0.75521344, 0.25000000, 0.59423067),
    (0.21373534, 0.04555803, 0.66584548),
    (0.28626466, 0.45444197, 0.16584548),
]


def build_bulk_lifepo4(a: float) -> Atoms:
    a = float(a)
    atoms = Atoms(
        _LIFEPO4_SYMBOLS,
        cell=[a, _CIF_B_OVER_A * a, _CIF_C_OVER_A * a],
        pbc=True,
    )
    atoms.set_scaled_positions(_LIFEPO4_SCALED_POSITIONS)
    atoms.wrap()
    return atoms


SYSTEM = ActiveSystem(
    key='bulk_lifepo4',
    title='LiFePO4 Model',
    builder=build_bulk_lifepo4,
    variables=(
        Variable("a", 4.55, 4.75, (4.58, _CIF_A, 4.72)),
    ),
    pseudopotentials={
        'Li': 'li_pbe_v1.4.uspp.F.UPF',
        'Fe': 'Fe.pbe-spn-kjpaw_psl.0.2.1.UPF',
        'P': 'P.pbe-n-rrkjus_psl.1.0.0.UPF',
        'O': 'O.pbe-n-kjpaw_psl.0.1.UPF',
    },
    ecutwfc=70.0,
    ecutrho=560.0,
    kpts=(4, 3, 2),
    smearing='mv',
    degauss=0.02,
    spin_polarized=True,
    energy_per_atom=True,
    result_quantity='Total energy per atom objective',
    result_units='eV/atom',
    n_candidates=61,
    random_state=135,
    category='Battery materials',
    notes="CIF-derived Li4Fe4P4O16 orthorhombic cell; fractional coordinates fixed while a scales b and c.",
)


if __name__ == "__main__":
    run_system(SYSTEM)