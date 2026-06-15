\# Task Active Learning + Inverse Design for Graphene (12 atoms) using Quantum ESPRESSO



You are an expert Python and DFT programmer. Write a complete script that implements combined active learning and inverse design for a periodic graphene sheet (12 carbon atoms) using Quantum ESPRESSO (QE) via ASE.



The goal is to find the in‑plane lattice constant that yields a target total energy per atom (or the minimum energy) using as few QE calculations as possible.



\## 1. System definition

\- Material Graphene (single layer, periodic in x and y, vacuum in z).

\- Supercell 12 carbon atoms.  

&#x20; A convenient choice create a 2×3 supercell of the graphene primitive cell.  

&#x20; Primitive cell has 2 atoms, lattice vectors  

&#x20; a1 = (a, 0), a2 = (-a2, asqrt(3)2) with a = lattice constant.  

&#x20; A 2×3 supercell repeats a1 twice and a2 three times → 23 = 6 primitive cells ×2 atoms = 12 atoms.  

&#x20; This gives a rectangular cell with good aspect ratio.

\- Variable the lattice constant `a` (in Å). Typical range 2.3 to 2.7 Å (equilibrium \~2.46 Å).

\- Target total energy per atom (or total energy of the cell). We will target the minimum total energy (most stable lattice constant) as a proof of concept. Alternatively, a specific energy offset can be used later.



\## 2. DFT parameters for QE (well converged for graphene)

\- Pseudopotential `C.pbe-n-rrkjus\_psl.1.0.0.UPF` (ultrasoft, from SSSP efficiency library) – user must provide path.

\- `ecutwfc = 50.0` Ry, `ecutrho = 400.0` Ry (8× for ultrasoft).

\- k‑points Gamma‑centered Monkhorst‑Pack grid, e.g., `8×8×1` (dense enough for a 2×3 supercell; adjust automatically based on cell size).

\- Smearing `occupations='smearing'`, `smearing='gaussian'`, `degauss=0.02` Ry.

\- Vacuum at least 15 Å in the z‑direction. Set cell vector c = 15 Å (or more) and ensure `pbc=(True, True, True)` but with large c to avoid interlayer interaction.

\- `conv\_thr = 1e-8` Ry, `electron\_maxstep = 200`.

\- Spin unpolarised (`nspin=1`).



\## 3. Required functions (similar to H₂ QE script)



\### 3.1 Build graphene supercell

```python

def build\_graphene(a, nx=2, ny=3, vacuum=15.0)

&#x20;   

&#x20;   Build a graphene supercell with lattice constant a (Å).

&#x20;   Returns an ASE Atoms object with periodic boundary conditions.

&#x20;   

&#x20;   from ase import Atoms

&#x20;   import numpy as np



&#x20;   # Primitive vectors for graphene (carbon atoms)

&#x20;   a1 = np.array(\[a, 0.0, 0.0])

&#x20;   a2 = np.array(\[-a2, anp.sqrt(3)2, 0.0])

&#x20;   primitive\_cell = np.array(\[a1, a2, \[0,0,vacuum]])



&#x20;   # Two atoms in primitive cell C at (0,0,0) and (a3, a3, 0) in fractional coordinates Wait standard positions (0,0) and (13,23) in fractional of primitive

&#x20;   # Actually for graphene, basis C1 at (0,0,0), C2 at (13, 23, 0) in fractional coordinates of primitive cell.

&#x20;   # Build supercell repeat primitive cell nx times along a1, ny times along a2.

&#x20;   from ase.build import make\_supercell

&#x20;   primitive = Atoms('C2', cell=primitive\_cell, pbc=True)

&#x20;   primitive.set\_scaled\_positions(\[\[0,0,0], \[13, 23, 0]])

&#x20;   supercell = make\_supercell(primitive, \[\[nx,0,0],\[0,ny,0],\[0,0,1]])

&#x20;   return supercell

