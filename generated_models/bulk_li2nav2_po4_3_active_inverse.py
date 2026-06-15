#!/usr/bin/env python3
"""Active learning + inverse design for Li2NaV2(PO4)3 (NASICON-type, R-3c).

Optimises hexagonal lattice parameters a and c.
Formula per model cell: Li2NaV2(PO4)3 = 20 atoms (1 formula unit, Z=1 approx).

BUGS FIXED vs. original Codex-generated script
================================================
FIX 1 [FATAL]   Li and Na stacked at (0,0,0):
    Na occupies the M1 site (6b Wyckoff): (0, 0, 0).
    Li occupies the M2 site (18e Wyckoff): ~(0.636, 0, 0.25).
    These are DIFFERENT crystallographic sites. The original code placed all
    three atoms (Na + Li + Li) at the same fractional coordinate, which causes
    an immediate QE crash (atoms too close / overlapping).

FIX 2 [FATAL]   kpts=(1,1,1) — Gamma-only for a 20-atom hexagonal cell:
    With only 1 k-point the BZ sampling is completely inadequate. Changed to
    (2,2,1), which is the minimal sensible mesh for a hexagonal cell where the
    c-axis (~22 A) is much longer than a (~8.3 A).

FIX 3 [SERIOUS] ecutwfc=50 / ecutrho=400 too low for V 3d USPP:
    Vanadium with a uspp.F PP needs at least 60-70 Ry. Raised to match
    LiMn2O4 reference: ecutwfc=70, ecutrho=560.

FIX 4 [SERIOUS] spin_polarized=True but no initial magnetic moments:
    V3+ is d2 (S=1, ~2 muB). Without set_initial_magnetic_moments() the SCF
    starts in an undefined magnetic state and typically fails to converge.
    Moments are now set inside the builder.

FIX 5 [MINOR]   Missing result_quantity / result_units fields (added).

FIX 6 [MINOR]   Comment claimed "28 atoms per primitive cell" — corrected to 20.

NOTE: The negative V z-coordinate (-0.1465) is now explicitly wrapped to
      0.8535 to stay in [0, 1) and avoid any ambiguity with ASE's wrapping.

CRYSTALLOGRAPHIC CAVEAT: A true R-3c hexagonal cell has 6 formula units
(120 atoms). The primitive rhombohedral cell has 2 formula units (40 atoms).
This 20-atom model is a single-formula-unit approximation that does NOT
satisfy the R-centering conditions. It is retained as a lightweight benchmark
cell; do not compare absolute energies to literature without re-doing with
the proper 40-atom primitive cell.
"""

from __future__ import annotations

from pathlib import Path
import sys
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qe_active_inverse_common import ActiveSystem, Variable, run_system
from ase import Atoms


def build_li2nav2po43(a: float, c: float) -> Atoms:
    """
    Build Li2NaV2(PO4)3 NASICON-type cell with given a and c (Angstrom).

    Atomic sites (R-3c hexagonal, literature values):
      Na : M1 site (6b Wyckoff)  at (0,        0,      0    )
      Li : M2 site (18e Wyckoff) at ~(0.636,   0,      0.25 )
      V  : 12c Wyckoff           at (0,        0,      0.1465) and symmetry equiv.
      P  : 18e Wyckoff           at (0.2875,   0,      0.25 ) and symmetry equiv.
      O  : 36f Wyckoff           at (0.175,   ~0,     ~0.087) and symmetry equiv.

    Total atoms: 20 (1 formula unit approximation).
    """
    a = float(a)
    c = float(c)

    cell = np.array([
        [ a,             0.0,          0.0],
        [-a / 2.0,  np.sqrt(3) / 2.0 * a,  0.0],
        [ 0.0,           0.0,           c ],
    ])

    # All coordinates in [0, 1) to avoid wrapping ambiguity.
    # FIX 1: Na stays at M1 (0,0,0); Li moves to M2 (~0.636, 0, 0.25).
    frac = [
        # --- alkali metals ---
        ('Na', (0.0000, 0.0000, 0.0000)),   # M1 / 6b
        ('Li', (0.6360, 0.0000, 0.2500)),   # M2 / 18e  (first Li)
        ('Li', (0.0000, 0.6360, 0.2500)),   # M2 / 18e  (second Li, sym. equiv.)
        # --- vanadium (12c), z wrapped from -0.1465 to 0.8535 ---
        ('V',  (0.0000, 0.0000, 0.1465)),
        ('V',  (0.0000, 0.0000, 0.8535)),   # FIX (note): was -0.1465 in original
        # --- phosphorus (18e) ---
        ('P',  (0.2875, 0.0000, 0.2500)),
        ('P',  (0.0000, 0.2875, 0.2500)),
        ('P',  (0.2875, 0.2875, 0.7500)),
        # --- oxygen (36f, 12 atoms) ---
        ('O',  (0.1750, 0.0000, 0.0870)),
        ('O',  (0.0000, 0.1750, 0.0870)),
        ('O',  (0.1750, 0.1750, 0.9130)),
        ('O',  (0.1900, 0.3450, 0.0740)),
        ('O',  (0.3450, 0.1900, 0.0740)),
        ('O',  (0.1900, 0.1900, 0.9260)),
        ('O',  (0.1750, 0.0000, 0.9130)),
        ('O',  (0.0000, 0.1750, 0.9130)),
        ('O',  (0.1750, 0.1750, 0.0870)),
        ('O',  (0.1900, 0.3450, 0.9260)),
        ('O',  (0.3450, 0.1900, 0.9260)),
        ('O',  (0.1900, 0.1900, 0.0740)),
    ]

    symbols      = [s for s, _ in frac]
    scaled_pos   = [p for _, p in frac]

    atoms = Atoms(symbols=symbols, scaled_positions=scaled_pos, cell=cell, pbc=True)

    if len(atoms) != 20:
        raise RuntimeError(f"Expected 20 atoms, got {len(atoms)}")

    # FIX 4: set initial magnetic moments for spin-polarised run.
    # V3+ (d2, S=1) -> 2 muB; all other elements non-magnetic.
    moment_map = {'Li': 0.0, 'Na': 0.0, 'V': 2.0, 'P': 0.0, 'O': 0.0}
    atoms.set_initial_magnetic_moments([moment_map[s] for s in symbols])

    return atoms


# VERIFY before running:
#   ls "$ESPRESSO_PSEUDO" | grep -iE "^na_|^v_"
# Expected output should include:
#   na_pbe_v1.5.uspp.F.UPF
#   v_pbe_v1.4.uspp.F.UPF

SYSTEM = ActiveSystem(
    key='bulk_li2nav2po43',
    title='Li2NaV2(PO4)3 (NASICON, R-3c)',
    builder=build_li2nav2po43,
    variables=(
        Variable("a", 8.0, 8.6, (8.2, 8.325, 8.5)),
        Variable("c", 21.0, 24.0, (21.5, 22.49, 23.5)),
    ),
    pseudopotentials={
        'Li': 'li_pbe_v1.4.uspp.F.UPF',       # USPP — confirmed present
        'Na': 'na_pbe_v1.5.uspp.F.UPF',       # USPP — verify with ls | grep na_
        'V':  'v_pbe_v1.4.uspp.F.UPF',        # USPP — verify with ls | grep v_
        'P':  'P.pbe-n-rrkjus_psl.1.0.0.UPF', # USPP — confirmed present
        'O':  'O.pbe-n-kjpaw_psl.0.1.UPF',    # PAW  — confirmed present
    },
    ecutwfc=70.0,       # FIX 3: raised from 50 (V 3d USPP needs >=70 Ry)
    ecutrho=560.0,      # FIX 3: raised from 400 (8x ecutwfc, match LiMn2O4)
    kpts=(2, 2, 1),     # FIX 2: raised from (1,1,1); minimal sensible mesh for hexagonal cell
    smearing='mv',      # Methfessel-Paxton; more stable than gaussian for d-metal oxides
    degauss=0.02,
    spin_polarized=True,   # V3+ (d2) is magnetic — keep True; moments now set in builder
    energy_per_atom=True,
    result_quantity='Total energy per atom objective',   # FIX 5: added
    result_units='eV/atom',                              # FIX 5: added
    n_candidates=61,
    random_state=135,
    category='Battery materials',
    notes=(
        "NASICON Li2NaV2(PO4)3 (R-3c hexagonal), optimising a and c. "
        "20-atom single-formula-unit approx. (see crystallographic caveat in docstring). "
        "Experimental: a~8.3 A, c~22.5 A. "
        "Six bugs fixed: Li/Na site collision (FIX 1), kpts (FIX 2), "
        "ecutwfc/ecutrho (FIX 3), missing V moments (FIX 4), "
        "result fields (FIX 5), atom count comment (FIX 6)."
    ),
)


if __name__ == "__main__":
    run_system(SYSTEM)