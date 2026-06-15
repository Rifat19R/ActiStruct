\# Task: Active Learning + Inverse Design for Bulk Silicon (Diamond Cubic, 8 atoms) using Quantum ESPRESSO



You are an expert Python and DFT programmer. Write a complete script that implements \*\*combined active learning and inverse design\*\* for bulk silicon (Si) in the diamond cubic structure (conventional cell, 8 atoms) using Quantum ESPRESSO (QE) via ASE.



The goal is to find the \*\*equilibrium lattice constant\*\* that minimises the total energy per atom using as few QE calculations as possible.



\## 1. System definition

\- \*\*Material\*\*: Silicon, diamond cubic structure.

\- \*\*Conventional cell\*\*: 8 atoms (positions: (0,0,0), (0,1/2,1/2), (1/2,0,1/2), (1/2,1/2,0) plus the same shifted by (1/4,1/4,1/4)).

\- \*\*Variable\*\*: lattice constant `a` (Å). Typical range: 5.2 – 5.6 Å (equilibrium with PBE is about 5.43–5.47 Å).

\- \*\*Target\*\*: minimise total energy per atom (or total energy of the cell). This is a minimisation problem – no fixed energy target; the algorithm should find the lattice constant that gives the lowest energy.



\## 2. DFT parameters for QE (well converged for Si)

\- \*\*Pseudopotential\*\*: `Si.pbe-n-rrkjus\_psl.1.0.0.UPF` (ultrasoft, from SSSP efficiency library) – user provides path. (Alternative: `Si.pbe-n-kjpaw\_psl.1.0.0.UPF` – any standard PBE pseudopotential for Si is fine.)

\- `ecutwfc = 50.0` Ry, `ecutrho = 400.0` Ry (8× for ultrasoft).

\- \*\*k‑points\*\*: Gamma‑centered Monkhorst‑Pack grid, e.g., `8×8×8` (dense enough for an 8‑atom cell). Use `kpts=(8,8,8)`.

\- Smearing: Not strictly needed for an insulator but can help SCF convergence. Use `occupations='smearing'`, `smearing='gaussian'`, `degauss=0.01` Ry.

\- `conv\_thr = 1e-8` Ry, `electron\_maxstep = 200`.

\- Spin: unpolarised (`nspin=1`).



\## 3. Required functions



\### 3.1 Build diamond cubic silicon cell (conventional, 8 atoms)

```python

from ase import Atoms

import numpy as np



def build\_si\_diamond(a):

&#x20;   """Create diamond cubic Si conventional cell (8 atoms) with lattice constant a (Å)."""

&#x20;   # Positions in fractional coordinates for diamond cubic (two interpenetrating FCC lattices)

&#x20;   # First FCC set: (0,0,0), (0,1/2,1/2), (1/2,0,1/2), (1/2,1/2,0)

&#x20;   # Second set shifted by (1/4,1/4,1/4)

&#x20;   positions = \[

&#x20;       \[0.0, 0.0, 0.0], \[0.0, 0.5, 0.5], \[0.5, 0.0, 0.5], \[0.5, 0.5, 0.0],

&#x20;       \[0.25, 0.25, 0.25], \[0.25, 0.75, 0.75], \[0.75, 0.25, 0.75], \[0.75, 0.75, 0.25]

&#x20;   ]

&#x20;   cell = np.eye(3) \* a

&#x20;   atoms = Atoms('Si8', positions=positions, cell=cell, pbc=True)

&#x20;   return atoms

