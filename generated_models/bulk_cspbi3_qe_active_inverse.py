"""Active learning + inverse design for Perovskite CsPbI3."""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qe_active_inverse_common import ActiveSystem, Variable, run_system
from generated_models.structure_builders import build_perovskite


def build_bulk_cspbi3(a: float):
    return build_perovskite('Cs', 'Pb', 'I', a)


SYSTEM = ActiveSystem(
    key='bulk_cspbi3',
    title='Perovskite CsPbI3',
    builder=build_bulk_cspbi3,
    variables=(
        Variable("a", 6.0, 6.5, (6.1, 6.3, 6.45)),
    ),
    pseudopotentials={'Cs': 'Cs_pbe_v1.uspp.F.UPF', 'Pb': 'Pb.pbe-dn-kjpaw_psl.0.2.2.UPF', 'I': 'I.pbe-n-kjpaw_psl.0.2.UPF'},
    ecutwfc=70.0,
    ecutrho=560.0,
    kpts=(4, 4, 4),
    smearing='gaussian',
    degauss=0.01,
    spin_polarized=False,
    energy_per_atom=True,
    result_quantity='Total energy per atom objective',
    result_units='eV/atom',
    n_candidates=61,
    random_state=148,
    category='Complex structures',
    notes="Total-energy-only objective for the generated 51-system benchmark.",
)


if __name__ == "__main__":
    run_system(SYSTEM)
