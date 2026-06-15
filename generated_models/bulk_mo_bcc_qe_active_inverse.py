"""Active learning + inverse design for Bulk BCC Mo."""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qe_active_inverse_common import ActiveSystem, Variable, run_system
from generated_models.structure_builders import build_bulk_bcc


def build_bulk_mo(a: float):
    return build_bulk_bcc('Mo', a)


SYSTEM = ActiveSystem(
    key='bulk_mo',
    title='Bulk BCC Mo',
    builder=build_bulk_mo,
    variables=(
        Variable("a", 3.0, 3.3, (3.05, 3.15, 3.25)),
    ),
    pseudopotentials={'Mo': 'Mo_ONCV_PBE-1.0.oncvpsp.upf'},
    ecutwfc=70.0,
    ecutrho=560.0,
    kpts=(14, 14, 14),
    smearing='mv',
    degauss=0.02,
    spin_polarized=False,
    energy_per_atom=True,
    result_quantity='Total energy per atom objective',
    result_units='eV/atom',
    n_candidates=61,
    random_state=107,
    category='Simple metals (FCC, BCC)',
    notes="Total-energy-only objective for the generated 51-system benchmark.",
)


if __name__ == "__main__":
    run_system(SYSTEM)
