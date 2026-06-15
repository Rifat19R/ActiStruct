"""Active learning + inverse design for Bulk Wurtzite ZnO."""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qe_active_inverse_common import ActiveSystem, Variable, run_system
from generated_models.structure_builders import build_zno_wurtzite


build_bulk_zno = build_zno_wurtzite


SYSTEM = ActiveSystem(
    key='bulk_zno',
    title='Bulk Wurtzite ZnO',
    builder=build_bulk_zno,
    variables=(
        Variable("a", 3.1, 3.4, (3.15, 3.25, 3.35, 3.22, 3.3)),
        Variable("c_over_a", 1.55, 1.7, (1.58, 1.6, 1.66, 1.63, 1.68)),
    ),
    pseudopotentials={'Zn': 'Zn_pbe_v1.uspp.F.UPF', 'O': 'O.pbe-n-kjpaw_psl.0.1.UPF'},
    ecutwfc=70.0,
    ecutrho=560.0,
    kpts=(8, 8, 6),
    smearing='gaussian',
    degauss=0.01,
    spin_polarized=False,
    energy_per_atom=True,
    result_quantity='Total energy per atom objective',
    result_units='eV/atom',
    n_candidates=81,
    random_state=117,
    category='Ionic oxides',
    notes="Total-energy-only objective for the generated 50-system benchmark.",
)


if __name__ == "__main__":
    run_system(SYSTEM)
