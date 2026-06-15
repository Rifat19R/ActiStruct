\# Task: Active Learning + Inverse Design for Bulk Copper (FCC, 4 atoms) using Quantum ESPRESSO



Write a complete Python script that implements \*\*combined active learning and inverse design\*\* for bulk copper (face‑centered cubic, 4 atoms per conventional cell) using Quantum ESPRESSO (QE) via ASE. The goal is to find the \*\*equilibrium lattice constant\*\* that minimises the total energy per atom using as few QE calculations as possible.



\## 1. System definition

\- \*\*Material\*\*: FCC copper, conventional cubic cell (4 atoms).

\- \*\*Variable\*\*: lattice constant `a` (Å). Typical range: 3.4 to 3.8 Å (equilibrium \~3.61 Å).

\- \*\*Target\*\*: minimise total energy per atom (or total energy of the cell). This is a minimisation problem – no fixed energy target; the algorithm should find the lattice constant that gives the lowest energy.



\## 2. DFT parameters for QE (converged for Cu)

\- Pseudopotential: `Cu.pbe-dn-rrkjus\_psl.1.0.0.UPF` (ultrasoft, from SSSP efficiency library) – user provides path. (For copper, a d‑electron pseudopotential is needed; the one above is suitable.)

\- `ecutwfc = 50.0` Ry, `ecutrho = 400.0` Ry (8× for ultrasoft).

\- k‑points: Gamma‑centered Monkhorst‑Pack grid, e.g., `12×12×12` (dense enough for a 4‑atom cell). Use `kpts=(12,12,12)`.

\- Smearing: `occupations='smearing'`, `smearing='gaussian'`, `degauss=0.02` Ry.

\- `conv\_thr = 1e-8` Ry, `electron\_maxstep = 200`.

\- Spin: unpolarised (`nspin=1`) for bulk Cu (non‑magnetic).



\## 3. Required functions



\### 3.1 Build FCC copper cell

```python

from ase import Atoms



def build\_fcc\_cu(a):

&#x20;   """Create FCC Cu conventional cell (4 atoms) with lattice constant a (Å)."""

&#x20;   return Atoms('Cu4',

&#x20;                positions=\[\[0,0,0], \[0,a/2,a/2], \[a/2,0,a/2], \[a/2,a/2,0]],

&#x20;                cell=\[a,a,a],

&#x20;                pbc=True)

