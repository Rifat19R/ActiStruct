"""Active learning + inverse design for Bulk SiO2 Model."""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qe_active_inverse_common import ActiveSystem, Variable, run_system
from generated_models.structure_builders import build_sio2_model


build_bulk_sio2 = build_sio2_model


SYSTEM = ActiveSystem(
    key='bulk_sio2',
    title='Bulk SiO2 Model',
    builder=build_bulk_sio2,
    variables=(
        Variable("a", 4.85, 5.15, (4.9, 5.025, 5.12, 4.96, 5.08)),
        Variable("c_over_a", 1.075, 1.125, (1.08, 1.1, 1.12, 1.09, 1.11)),
    ),
    pseudopotentials={'Si': 'Si.pbe-n-rrkjus_psl.1.0.0.UPF', 'O': 'O.pbe-n-kjpaw_psl.0.1.UPF'},
    ecutwfc=80.0,
    ecutrho=640.0,
    kpts=(8, 8, 8),
    smearing='gaussian',
    degauss=0.01,
    spin_polarized=False,
    energy_per_atom=True,
    result_quantity='Total energy per atom objective',
    result_units='eV/atom',
    n_candidates=81,
    random_state=120,
    category='Ionic oxides',
    notes="Total-energy-only objective for the generated 51-system benchmark.",
)


if __name__ == "__main__":
    run_system(SYSTEM)
