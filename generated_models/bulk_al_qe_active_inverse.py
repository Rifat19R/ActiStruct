"""Active learning + inverse design for Bulk FCC Al."""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qe_active_inverse_common import ActiveSystem, Variable, run_system
from generated_models.structure_builders import build_bulk_fcc


def build_bulk_al(a: float):
    return build_bulk_fcc('Al', a)


SYSTEM = ActiveSystem(
    key='bulk_al',
    title='Bulk FCC Al',
    builder=build_bulk_al,
    variables=(
        Variable("a", 3.8, 4.3, (3.9, 4.05, 4.2)),
    ),
    pseudopotentials={'Al': 'Al.pbe-n-kjpaw_psl.1.0.0.UPF'},
    ecutwfc=50.0,
    ecutrho=400.0,
    kpts=(12, 12, 12),
    smearing='mv',
    degauss=0.02,
    spin_polarized=False,
    energy_per_atom=True,
    result_quantity='Total energy per atom objective',
    result_units='eV/atom',
    n_candidates=61,
    random_state=101,
    category='Simple metals (FCC, BCC)',
    notes="Total-energy-only objective for the generated 50-system benchmark.",
)


if __name__ == "__main__":
    run_system(SYSTEM)
