"""Active learning + inverse design for Spinel LiMn2O4 Model."""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qe_active_inverse_common import ActiveSystem, Variable, run_system
from generated_models.structure_builders import build_limn2o4


build_bulk_limn2o4 = build_limn2o4


SYSTEM = ActiveSystem(
    key='bulk_limn2o4',
    title='Spinel LiMn2O4 Model',
    builder=build_bulk_limn2o4,
    variables=(
        Variable("a", 7.9, 8.4, (8.0, 8.2, 8.35)),
    ),
    pseudopotentials={'Li': 'li_pbe_v1.4.uspp.F.UPF', 'Mn': 'mn_pbe_v1.5.uspp.F.UPF', 'O': 'O.pbe-n-kjpaw_psl.0.1.UPF'},
    ecutwfc=70.0,
    ecutrho=560.0,
    kpts=(4, 4, 4),
    smearing='mv',
    degauss=0.02,
    spin_polarized=True,
    energy_per_atom=True,
    result_quantity='Total energy per atom objective',
    result_units='eV/atom',
    n_candidates=61,
    random_state=136,
    category='Battery materials',
    notes="Total-energy-only objective for the generated 50-system benchmark.",
)


if __name__ == "__main__":
    run_system(SYSTEM)
