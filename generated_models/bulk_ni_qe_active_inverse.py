"""Active learning + inverse design for Bulk FCC Ni."""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qe_active_inverse_common import ActiveSystem, Variable, run_system
from generated_models.structure_builders import build_bulk_fcc


def build_bulk_ni(a: float):
    return build_bulk_fcc('Ni', a)


SYSTEM = ActiveSystem(
    key='bulk_ni',
    title='Bulk FCC Ni',
    builder=build_bulk_ni,
    variables=(
        Variable("a", 3.3, 3.7, (3.36, 3.52, 3.66)),
    ),
    pseudopotentials={'Ni': 'ni_pbe_v1.4.uspp.F.UPF'},
    ecutwfc=60.0,
    ecutrho=480.0,
    kpts=(12, 12, 12),
    smearing='mv',
    degauss=0.02,
    spin_polarized=False,
    energy_per_atom=True,
    result_quantity='Total energy per atom objective',
    result_units='eV/atom',
    n_candidates=61,
    random_state=103,
    category='Simple metals (FCC, BCC)',
    notes="Total-energy-only objective for the generated 50-system benchmark.",
)


if __name__ == "__main__":
    run_system(SYSTEM)
