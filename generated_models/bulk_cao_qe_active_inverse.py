"""Active learning + inverse design for Bulk Rocksalt CaO."""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qe_active_inverse_common import ActiveSystem, Variable, run_system
from generated_models.structure_builders import build_bulk_rocksalt


def build_bulk_cao(a: float):
    return build_bulk_rocksalt('CaO', a)


SYSTEM = ActiveSystem(
    key='bulk_cao',
    title='Bulk Rocksalt CaO',
    builder=build_bulk_cao,
    variables=(
        Variable("a", 4.65, 5.05, (4.7, 4.81, 5.0)),
    ),
    pseudopotentials={'Ca': 'Ca_pbe_v1.uspp.F.UPF', 'O': 'O.pbe-n-kjpaw_psl.0.1.UPF'},
    ecutwfc=70.0,
    ecutrho=560.0,
    kpts=(8, 8, 8),
    smearing='gaussian',
    degauss=0.01,
    spin_polarized=False,
    energy_per_atom=True,
    result_quantity='Total energy per atom objective',
    result_units='eV/atom',
    n_candidates=61,
    random_state=116,
    category='Ionic oxides',
    notes="Total-energy-only objective for the generated 51-system benchmark.",
)


if __name__ == "__main__":
    run_system(SYSTEM)
