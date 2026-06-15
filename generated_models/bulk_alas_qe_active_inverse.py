"""Active learning + inverse design for Bulk Zincblende AlAs."""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qe_active_inverse_common import ActiveSystem, Variable, run_system
from generated_models.structure_builders import build_bulk_zincblende


def build_bulk_alas(a: float):
    return build_bulk_zincblende('AlAs', a)


SYSTEM = ActiveSystem(
    key='bulk_alas',
    title='Bulk Zincblende AlAs',
    builder=build_bulk_alas,
    variables=(
        Variable("a", 5.45, 5.85, (5.5, 5.66, 5.8)),
    ),
    pseudopotentials={'Al': 'Al.pbe-n-kjpaw_psl.1.0.0.UPF', 'As': 'As.pbe-n-rrkjus_psl.0.2.UPF'},
    ecutwfc=60.0,
    ecutrho=480.0,
    kpts=(8, 8, 8),
    smearing='gaussian',
    degauss=0.01,
    spin_polarized=False,
    energy_per_atom=True,
    result_quantity='Total energy per atom objective',
    result_units='eV/atom',
    n_candidates=61,
    random_state=112,
    category='Semiconductors',
    notes="Total-energy-only objective for the generated 51-system benchmark.",
)


if __name__ == "__main__":
    run_system(SYSTEM)
