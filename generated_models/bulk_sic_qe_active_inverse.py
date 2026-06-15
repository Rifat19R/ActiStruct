"""Active learning + inverse design for Bulk Zincblende SiC."""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qe_active_inverse_common import ActiveSystem, Variable, run_system
from generated_models.structure_builders import build_bulk_zincblende


def build_bulk_sic(a: float):
    return build_bulk_zincblende('SiC', a)


SYSTEM = ActiveSystem(
    key='bulk_sic',
    title='Bulk Zincblende SiC',
    builder=build_bulk_sic,
    variables=(
        Variable("a", 4.2, 4.55, (4.25, 4.36, 4.5)),
    ),
    pseudopotentials={'Si': 'Si.pbe-n-rrkjus_psl.1.0.0.UPF', 'C': 'C.pbe-n-kjpaw_psl.1.0.0.UPF'},
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
    random_state=114,
    category='Semiconductors',
    notes="Total-energy-only objective for the generated 50-system benchmark.",
)


if __name__ == "__main__":
    run_system(SYSTEM)
