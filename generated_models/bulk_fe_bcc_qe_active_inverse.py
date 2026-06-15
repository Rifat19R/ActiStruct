"""Active learning + inverse design for Bulk BCC Fe."""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qe_active_inverse_common import ActiveSystem, Variable, run_system
from generated_models.structure_builders import build_bulk_bcc


def build_bulk_fe(a: float):
    return build_bulk_bcc('Fe', a)


SYSTEM = ActiveSystem(
    key='bulk_fe',
    title='Bulk BCC Fe',
    builder=build_bulk_fe,
    variables=(
        Variable("a", 2.65, 3.05, (2.7, 2.87, 3.0)),
    ),
    pseudopotentials={'Fe': 'Fe.pbe-spn-kjpaw_psl.0.2.1.UPF'},
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
    random_state=106,
    category='Simple metals (FCC, BCC)',
    notes="Total-energy-only objective for the generated 50-system benchmark.",
)


if __name__ == "__main__":
    run_system(SYSTEM)
