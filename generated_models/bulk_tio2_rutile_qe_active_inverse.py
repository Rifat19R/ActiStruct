"""Active learning + inverse design for Bulk Rutile TiO2."""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qe_active_inverse_common import ActiveSystem, Variable, run_system
from generated_models.structure_builders import build_tio2_rutile


build_bulk_tio2 = build_tio2_rutile


SYSTEM = ActiveSystem(
    key='bulk_tio2',
    title='Bulk Rutile TiO2',
    builder=build_bulk_tio2,
    variables=(
        Variable("a", 4.45, 4.75, (4.5, 4.59, 4.7, 4.55, 4.65)),
        Variable("c_over_a", 0.62, 0.67, (0.63, 0.64, 0.66, 0.625, 0.665)),
    ),
    pseudopotentials={'Ti': 'ti_pbe_v1.4.uspp.F.UPF', 'O': 'O.pbe-n-kjpaw_psl.0.1.UPF'},
    ecutwfc=70.0,
    ecutrho=560.0,
    kpts=(8, 8, 10),
    smearing='gaussian',
    degauss=0.01,
    spin_polarized=False,
    energy_per_atom=True,
    result_quantity='Total energy per atom objective',
    result_units='eV/atom',
    n_candidates=81,
    random_state=118,
    category='Ionic oxides',
    notes="Total-energy-only objective for the generated 50-system benchmark.",
)


if __name__ == "__main__":
    run_system(SYSTEM)
