\# Task: Active Learning + Inverse Design for H₂O (Water) using Quantum ESPRESSO



You are an expert Python and DFT programmer. Write a complete script that implements \*\*combined active learning and inverse design\*\* for a single water molecule (H₂O) in a large cubic box (gas phase) using Quantum ESPRESSO (QE) via ASE.



The goal is to find the \*\*equilibrium bond length (r\_OH) and bond angle (H‑O‑H)\*\* that minimise the total energy of the molecule, using as few QE calculations as possible.



\## 1. System definition

\- \*\*Molecule\*\*: H₂O (3 atoms: 1 oxygen, 2 hydrogens).

\- \*\*Geometry\*\*: The molecule is placed in a cubic box (side length 10–12 Å) to avoid interactions with periodic images.

\- \*\*Parameters\*\* (two variables):

&#x20; 1. Bond length `r` (Å): O–H distance.

&#x20; 2. Bond angle `theta` (degrees): H‑O‑H angle.

\- \*\*Search range\*\*:

&#x20; - `r`: 0.85 – 1.05 Å (equilibrium \~0.96 Å with PBE)

&#x20; - `theta`: 95 – 115° (equilibrium \~104.5°)

\- \*\*Target\*\*: minimise total energy of the molecule. This is a \*\*2‑dimensional minimisation\*\* problem. The algorithm must learn a 2D energy landscape.



\## 2. DFT parameters for QE (well converged for H₂O)

\- \*\*Pseudopotentials\*\*:

&#x20; - O: `O.pbe-n-rrkjus\_psl.1.0.0.UPF` (ultrasoft, from SSSP efficiency)

&#x20; - H: `H.pbe-rrkjus\_psl.1.0.0.UPF` (same library)

\- `ecutwfc = 50.0` Ry, `ecutrho = 400.0` Ry (8× for ultrasoft).

\- \*\*k‑points\*\*: Gamma point only (`kpts=(1,1,1)`) because the system is isolated (large vacuum).

\- \*\*Smearing\*\*: Not required for a molecule. Use `occupations='smearing'`, `smearing='gaussian'`, `degauss=0.01` Ry to help SCF stability.

\- `conv\_thr = 1e-8` Ry, `electron\_maxstep = 200`.

\- Spin: unpolarised (`nspin=1`).

\- \*\*Box size\*\*: Use a cubic cell of side `box = 10.0` Å to ensure no intermolecular interactions.



\## 3. Required functions



\### 3.1 Build H₂O molecule with given r and angle

```python

from ase import Atoms

import numpy as np



def build\_h2o(r, theta\_deg, box=10.0):

&#x20;   """

&#x20;   Build H2O molecule with bond length r (Å) and H-O-H angle theta\_deg (degrees).

&#x20;   Places O at origin, H in xz-plane.

&#x20;   Returns Atoms object in a cubic box of side 'box' (pbc=True).

&#x20;   """

&#x20;   theta\_rad = np.radians(theta\_deg)

&#x20;   # O at (0,0,0)

&#x20;   # H1 along x-axis

&#x20;   h1 = np.array(\[r, 0.0, 0.0])

&#x20;   # H2 in xz-plane, rotated by theta\_rad from H1

&#x20;   h2 = np.array(\[r \* np.cos(theta\_rad), 0.0, r \* np.sin(theta\_rad)])

&#x20;   positions = \[ (0,0,0), tuple(h1), tuple(h2) ]

&#x20;   cell = \[box, box, box]

&#x20;   atoms = Atoms('OH2', positions=positions, cell=cell, pbc=True)

&#x20;   return atoms

