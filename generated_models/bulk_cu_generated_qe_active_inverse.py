"""Active learning + inverse design for Bulk FCC Cu."""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qe_active_inverse_common import ActiveSystem, Variable, run_system
from generated_models.structure_builders import build_bulk_fcc


def build_bulk_cu_generated(a: float):
    return build_bulk_fcc('Cu', a)


SYSTEM = ActiveSystem(
    key='bulk_cu_generated',
    title='Bulk FCC Cu',
    builder=build_bulk_cu_generated,
    variables=(
        Variable("a", 3.4, 3.8, (3.45, 3.61, 3.75)),
    ),
    pseudopotentials={'Cu': 'Cu.paw.z_11.ld1.psl.v1.0.0-low.upf'},
    ecutwfc=70.0,
    ecutrho=560.0,
    kpts=(12, 12, 12),
    smearing='mv',
    degauss=0.02,
    spin_polarized=False,
    energy_per_atom=True,
    result_quantity='Total energy per atom objective',
    result_units='eV/atom',
    n_candidates=61,
    random_state=102,
    category='Simple metals (FCC, BCC)',
    notes="Total-energy-only objective for the generated 51-system benchmark.",
)


if __name__ == "__main__":
    run_system(SYSTEM)
