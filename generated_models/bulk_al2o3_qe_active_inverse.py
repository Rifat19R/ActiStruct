"""Active learning + inverse design for Bulk Al2O3 Model."""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qe_active_inverse_common import ActiveSystem, Variable, run_system
from generated_models.structure_builders import build_al2o3_model


build_bulk_al2o3 = build_al2o3_model


SYSTEM = ActiveSystem(
    key='bulk_al2o3',
    title='Bulk Al2O3 Model',
    builder=build_bulk_al2o3,
    variables=(
        Variable("a", 4.65, 4.9, (4.7, 4.76, 4.85, 4.72, 4.88)),
        Variable("c_over_a", 2.65, 2.8, (2.68, 2.73, 2.78, 2.7, 2.76)),
    ),
    pseudopotentials={'Al': 'Al.pbe-n-kjpaw_psl.1.0.0.UPF', 'O': 'O.pbe-n-kjpaw_psl.0.1.UPF'},
    ecutwfc=70.0,
    ecutrho=560.0,
    kpts=(6, 6, 4),
    smearing='gaussian',
    degauss=0.01,
    spin_polarized=False,
    energy_per_atom=True,
    result_quantity='Total energy per atom objective',
    result_units='eV/atom',
    n_candidates=81,
    random_state=119,
    category='Ionic oxides',
    notes="Total-energy-only objective for the generated 51-system benchmark.",
)


if __name__ == "__main__":
    run_system(SYSTEM)
