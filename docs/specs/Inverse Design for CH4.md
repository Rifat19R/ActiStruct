\# Task: Active Learning + Inverse Design for CH₄ (Methane) using Quantum ESPRESSO



You are an expert Python and DFT programmer. Write a complete script that implements \*\*combined active learning and inverse design\*\* for a single methane molecule (CH₄) in a large cubic box (gas phase) using Quantum ESPRESSO (QE) via ASE.



The goal is to find the \*\*equilibrium C–H bond length\*\* that minimises the total energy of the molecule, using as few QE calculations as possible. This is a \*\*1‑dimensional minimisation\*\* problem.



\## 1. System definition

\- \*\*Molecule\*\*: CH₄ (5 atoms: 1 carbon, 4 hydrogens). Tetrahedral geometry.

\- \*\*Geometry\*\*: The molecule is placed in a cubic box (side length 10–12 Å) to avoid interactions with periodic images.

\- \*\*Parameter\*\*: bond length `r` (Å): C–H distance. All four C–H bonds are kept equal (tetrahedral angles fixed at 109.47°).

\- \*\*Search range\*\*: `r = 1.05 – 1.15 Å` (equilibrium experimental ≈ 1.087 Å; PBE typically gives \~1.09 Å).

\- \*\*Target\*\*: minimise total energy of the molecule.



\## 2. DFT parameters for QE (well converged for CH₄)

\- \*\*Pseudopotentials\*\* (ultrasoft, from SSSP efficiency library or PSLibrary):

&#x20; - C: `C.pbe-n-rrkjus\_psl.1.0.0.UPF`

&#x20; - H: `H.pbe-rrkjus\_psl.1.0.0.UPF`

\- `ecutwfc = 50.0` Ry, `ecutrho = 400.0` Ry (8× for ultrasoft).

\- \*\*k‑points\*\*: Gamma point only (`kpts=(1,1,1)`) because the molecule is isolated.

\- \*\*Smearing\*\*: Not strictly needed for a molecule, but can help SCF convergence. Use `occupations='smearing'`, `smearing='gaussian'`, `degauss=0.01` Ry.

\- `conv\_thr = 1e-8` Ry, `electron\_maxstep = 200`.

\- Spin: unpolarised (`nspin=1`).

\- \*\*Box size\*\*: Use a cubic cell of side `box = 10.0` Å to ensure no intermolecular interactions.



\## 3. Required functions



\### 3.1 Build CH₄ molecule with given bond length

```python

from ase import Atoms

import numpy as np



def build\_ch4(r, box=10.0):

&#x20;   """

&#x20;   Build CH4 molecule with C–H bond length r (Å) in a cubic box of side 'box' (Å).

&#x20;   Places C at center, H at tetrahedral corners.

&#x20;   Tetrahedral angle 109.47°: coordinates normalized to length r.

&#x20;   """

&#x20;   # Tetrahedral directions (normalized vectors)

&#x20;   # One convenient set: (1,1,1), (1,-1,-1), (-1,1,-1), (-1,-1,1) then normalize

&#x20;   vectors = np.array(\[\[1,1,1], \[1,-1,-1], \[-1,1,-1], \[-1,-1,1]], dtype=float)

&#x20;   norm = np.linalg.norm(vectors\[0])

&#x20;   vectors = vectors / norm \* r   # scale to length r

&#x20;   positions = \[ (0,0,0) ] + \[tuple(v) for v in vectors]

&#x20;   cell = \[box, box, box]

&#x20;   atoms = Atoms('CH4', positions=positions, cell=cell, pbc=True)

&#x20;   return atoms

