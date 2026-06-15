"""Active learning + inverse design for Heusler Co2FeAl."""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qe_active_inverse_common import ActiveSystem, Variable, run_system
from generated_models.structure_builders import build_co2feal


build_bulk_co2feal = build_co2feal


SYSTEM = ActiveSystem(
    key='bulk_co2feal',
    title='Heusler Co2FeAl',
    builder=build_bulk_co2feal,
    variables=(
        Variable("a", 5.5, 5.9, (5.55, 5.73, 5.85)),
    ),
    pseudopotentials={'Co': 'Co_pbe_v1.2.uspp.F.UPF', 'Fe': 'Fe.pbe-spn-kjpaw_psl.0.2.1.UPF', 'Al': 'Al.pbe-n-kjpaw_psl.1.0.0.UPF'},
    ecutwfc=70.0,
    ecutrho=560.0,
    kpts=(8, 8, 8),
    smearing='mv',
    degauss=0.02,
    spin_polarized=True,
    energy_per_atom=True,
    result_quantity='Total energy per atom objective',
    result_units='eV/atom',
    n_candidates=61,
    random_state=150,
    category='Complex structures',
    notes="Total-energy-only objective for the generated 51-system benchmark.",
)


if __name__ == "__main__":
    run_system(SYSTEM)
