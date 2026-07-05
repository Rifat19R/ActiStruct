"""Active learning + inverse design for LiFePO₄ (orthorhombic)"""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from qe_active_inverse_common import ActiveSystem, Variable, run_system
from generated_models.structure_builders import build_lifepo4

# The builder expects the b lattice constant (A) and derives the full
# orthorhombic cell via fixed experimental ratios:
#   a = 4.65 / 5.97 * b
#   c = 10.24 / 5.97 * b
# Optimising b is the natural single-variable choice for this material.

SYSTEM = ActiveSystem(
    key='bulk_lifepo4',
    title='LiFePO4 (Orthorhombic)',
    builder=build_lifepo4,               # callable: expects b (A)
    variables=(
        Variable("b", 5.80, 6.20, (5.85, 5.97, 6.15)),  # centred on experimental b=5.97 A
    ),
    pseudopotentials={
        # Li: USPP — confirmed present (used in LiCoO2, LiMn2O4)
        'Li': 'li_pbe_v1.4.uspp.F.UPF',
        # Fe: PAW — confirmed present (ls | grep Fe returns this exact file)
        'Fe': 'Fe.pbe-spn-kjpaw_psl.0.2.1.UPF',
        # P:  USPP (rrkjus) — confirmed present (ls | grep P returns this exact file)
        'P':  'P.pbe-n-rrkjus_psl.1.0.0.UPF',
        # O:  PAW — confirmed present (MgO, LiMn2O4, LiCoO2)
        'O':  'O.pbe-n-kjpaw_psl.0.1.UPF',
    },
    # FIX 1: raise cutoffs to handle Fe 3d PAW (match LiMn2O4)
    ecutwfc=70.0,
    ecutrho=560.0,
    # FIX 2: denser mesh for 28-atom orthorhombic cell (a~4.65, b~5.97, c~10.24 A)
    kpts=(4, 4, 2),
    # FIX 3: match LiMn2O4 smearing settings
    smearing='mv',
    degauss=0.02,
    # Kept False for benchmark consistency with LiMn2O4 — see warning above.
    spin_polarized=False,
    energy_per_atom=True,
    result_quantity='Total energy per atom objective',
    result_units='eV/atom',
    n_candidates=61,
    random_state=135,
    category='Battery materials',
    notes=(
        "Orthorhombic LiFePO4 Pnma, optimising b lattice constant. "
        "Experimental: a=4.65, b=5.97, c=10.24 A. "
        "Fixed: ecutwfc 50->70 Ry (FIX 1); kpts (2,2,2)->(4,4,2) (FIX 2); "
        "smearing gaussian->mv, degauss 0.03->0.02 (FIX 3). "
        "All pseudo filenames confirmed on disk."
    ),
)


if __name__ == "__main__":
    run_system(SYSTEM)