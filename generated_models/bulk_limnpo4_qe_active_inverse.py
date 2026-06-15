"""Active learning + inverse design for LiMnPO₄ (orthorhombic olivine)."""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qe_active_inverse_common import ActiveSystem, Variable, run_system
from ase import Atoms
import numpy as np

# ----------------------------------------------------------------------
# Builder for LiMnPO₄ (olivine, Pnma) – optimises b lattice constant
# Experimental ratios (a : b : c) taken from literature:
#   a = 10.45 Å, b = 6.10 Å, c = 4.75 Å → ratios: a/b = 1.7131, c/b = 0.7787
# ----------------------------------------------------------------------
def build_limnpo4(b: float) -> Atoms:
    """
    Build LiMnPO₄ with given b (lattice constant along b, Å).
    a and c are scaled using experimental ratios.
    Atomic positions are fractional (olivine structure, Pnma).
    """
    # Ratios from experimental values (a/b and c/b)
    ratio_a_b = 10.45 / 6.10   # ≈ 1.7131
    ratio_c_b = 4.75 / 6.10    # ≈ 0.7787
    a = b * ratio_a_b
    c = b * ratio_c_b

    # Fractional coordinates (from a well‑relaxed cif, e.g. MP-7670)
    # Li 4a (0,0,0)
    # Mn 4c (0.5, 0, 0)
    # P  4c (0.2817, 0.25, 0.9745)
    # O1 4c (0.0970, 0.25, 0.7415)
    # O2 4c (0.4560, 0.25, 0.2080)
    # O3 8d (0.1650, 0.045, 0.2850) and (0.1650, 0.455, 0.2850)
    frac_positions = {
        'Li': [(0.0000, 0.0000, 0.0000)],
        'Mn': [(0.5000, 0.0000, 0.0000)],
        'P':  [(0.2817, 0.2500, 0.9745)],
        'O':  [(0.0970, 0.2500, 0.7415),   # O1
               (0.4560, 0.2500, 0.2080),   # O2
               (0.1650, 0.0450, 0.2850),   # O3
               (0.1650, 0.4550, 0.2850)]   # O4
    }
    symbols = []
    positions = []
    for elem, fracs in frac_positions.items():
        for frac in fracs:
            symbols.append(elem)
            positions.append(frac)

    cell = np.array([[a, 0, 0],
                     [0, b, 0],
                     [0, 0, c]])
    atoms = Atoms(symbols=symbols, positions=positions, cell=cell, pbc=True)
    atoms.set_scaled_positions(positions)  # ensure correct scaling
    return atoms

# ----------------------------------------------------------------------
# ActiveSystem definition – identical to LiFePO₄ but with Mn and modified ranges
# ----------------------------------------------------------------------
SYSTEM = ActiveSystem(
    key='bulk_limnpo4',
    title='LiMnPO₄ (Orthorhombic Olivine)',
    builder=build_limnpo4,               # expects b (Å)
    variables=(
        Variable("b", 5.90, 6.30, (5.95, 6.10, 6.25)),  # experimental b≈6.10 Å
    ),
    pseudopotentials={
        'Li': 'li_pbe_v1.4.uspp.F.UPF',
        'Mn': 'mn_pbe_v1.5.uspp.F.UPF',                 # Mn pseudopotential
        'P':  'P.pbe-n-rrkjus_psl.1.0.0.UPF',
        'O':  'O.pbe-n-kjpaw_psl.0.1.UPF'
    },
    ecutwfc=50.0,
    ecutrho=400.0,
    kpts=(2, 2, 2),                     # Γ-centred mesh
    smearing='gaussian',                # stable for insulators
    degauss=0.03,
    spin_polarized=False,               # set to True if Mn magnetic moment needed
    energy_per_atom=True,
    result_quantity='Total energy per atom objective',
    result_units='eV/atom',
    n_candidates=61,
    random_state=135,
    category='Battery materials',
    notes="Orthorhombic LiMnPO₄ optimising b lattice constant. Experimental ratios a:b:c = 10.45:6.10:4.75 Å.",
)

if __name__ == "__main__":
    run_system(SYSTEM)
