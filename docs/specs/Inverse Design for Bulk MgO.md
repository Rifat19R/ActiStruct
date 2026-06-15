\# Task: Active Learning + Inverse Design for Bulk MgO (Rocksalt, 8 atoms) using Quantum ESPRESSO



You are an expert Python and DFT programmer. Write a complete script that implements \*\*combined active learning and inverse design\*\* for bulk magnesium oxide (MgO) in the rocksalt (NaCl) structure (conventional cubic cell, 8 atoms: 4 Mg, 4 O) using Quantum ESPRESSO (QE) via ASE.



The goal is to find the \*\*equilibrium lattice constant\*\* that minimises the total energy per atom (or total energy of the cell) using as few QE calculations as possible.



\## 1. System definition

\- \*\*Material\*\*: MgO, rocksalt (Fm-3m) structure.

\- \*\*Conventional cell\*\*: 8 atoms (Mg at corners and face centers? Actually rocksalt: two interpenetrating FCC lattices. The conventional cubic cell contains 4 Mg and 4 O atoms.)

&#x20; - Mg positions: (0,0,0), (0,1/2,1/2), (1/2,0,1/2), (1/2,1/2,0)

&#x20; - O positions: (1/2,0,0), (0,1/2,0), (0,0,1/2), (1/2,1/2,1/2)

\- \*\*Variable\*\*: lattice constant `a` (Å). Typical range: 4.1 – 4.4 Å (equilibrium experimental ≈ 4.21 Å; PBE usually gives \~4.21–4.24 Å).

\- \*\*Target\*\*: minimise total energy per atom (or total energy of the cell). This is a minimisation problem – find the lattice constant that gives the lowest energy.



\## 2. DFT parameters for QE (well converged for MgO)

\- \*\*Pseudopotentials\*\* (ultrasoft, from SSSP efficiency library or similar):

&#x20; - Mg: `Mg.pbe-spnl-rrkjus\_psl.1.0.0.UPF` (or `Mg.pbe-n-rrkjus\_psl.1.0.0.UPF`)

&#x20; - O: `O.pbe-n-rrkjus\_psl.1.0.0.UPF`

\- `ecutwfc = 60.0` Ry (Mg requires slightly higher cutoff; 50–60 Ry is safe). `ecutrho = 480.0` Ry (8× for ultrasoft).

\- \*\*k‑points\*\*: Gamma‑centered Monkhorst‑Pack grid, e.g., `8×8×8` (dense enough for an 8‑atom cell). Use `kpts=(8,8,8)`.

\- Smearing: For an insulator like MgO, smearing is not required but can help convergence. Use `occupations='smearing'`, `smearing='gaussian'`, `degauss=0.01` Ry.

\- `conv\_thr = 1e-8` Ry, `electron\_maxstep = 300` (MgO can be tricky to converge).

\- Spin: unpolarised (`nspin=1`).



\## 3. Required functions



\### 3.1 Build rocksalt MgO conventional cell

```python

from ase import Atoms

import numpy as np



def build\_mgo\_rocksalt(a):

&#x20;   """Create rocksalt MgO conventional cell (8 atoms) with lattice constant a (Å)."""

&#x20;   # Mg positions (fractional)

&#x20;   mg\_positions = \[

&#x20;       (0.0, 0.0, 0.0), (0.0, 0.5, 0.5),

&#x20;       (0.5, 0.0, 0.5), (0.5, 0.5, 0.0)

&#x20;   ]

&#x20;   # O positions (fractional)

&#x20;   o\_positions = \[

&#x20;       (0.5, 0.0, 0.0), (0.0, 0.5, 0.0),

&#x20;       (0.0, 0.0, 0.5), (0.5, 0.5, 0.5)

&#x20;   ]

&#x20;   positions = mg\_positions + o\_positions

&#x20;   symbols = \['Mg']\*4 + \['O']\*4

&#x20;   cell = np.eye(3) \* a

&#x20;   atoms = Atoms(symbols, positions=positions, cell=cell, pbc=True)

&#x20;   return atoms

