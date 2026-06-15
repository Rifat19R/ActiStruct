"""Active learning + inverse design for Bulk Diamond Ge."""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qe_active_inverse_common import ActiveSystem, Variable, run_system
from generated_models.structure_builders import build_bulk_diamond


def build_bulk_ge(a: float):
    return build_bulk_diamond('Ge', a)


SYSTEM = ActiveSystem(
    key='bulk_ge',
    title='Bulk Diamond Ge',
    builder=build_bulk_ge,
    variables=(
        Variable("a", 5.45, 5.85, (5.5, 5.66, 5.8)),
    ),
    pseudopotentials={'Ge': 'ge_pbe_v1.4.uspp.F.UPF'},
    ecutwfc=50.0,
    ecutrho=400.0,
    kpts=(8, 8, 8),
    smearing='gaussian',
    degauss=0.01,
    spin_polarized=False,
    energy_per_atom=True,
    result_quantity='Total energy per atom objective',
    result_units='eV/atom',
    n_candidates=61,
    random_state=110,
    category='Semiconductors',
    notes="Total-energy-only objective for the generated 50-system benchmark.",
)


if __name__ == "__main__":
    run_system(SYSTEM)
