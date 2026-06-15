\# Task: Active Learning + Inverse Design for Bulk LiCoO₂ (Layered R-3m, 6 formula units / 18 atoms) using Quantum ESPRESSO



You are an expert Python and DFT programmer. Write a complete script that implements \*\*combined active learning and inverse design\*\* for bulk lithium cobalt oxide (LiCoO₂) in its layered rhombohedral (R-3m, 166) structure using Quantum ESPRESSO (QE) via ASE.



The goal is to find the \*\*equilibrium in‑plane lattice constant (a) and the out‑of‑plane lattice constant (c)\*\* that minimise the total energy per atom (or total energy of the cell), using as few QE calculations as possible. This is a \*\*2‑dimensional minimisation\*\* problem on a realistic battery cathode material.



\## 1. System definition

\- \*\*Material\*\*: LiCoO₂, layered Li‑ion battery cathode (space group R-3m, 166).  

\- \*\*Conventional hexagonal cell\*\*: contains \*\*6 formula units\*\* → 18 atoms (6 Li, 6 Co, 12 O).  

&#x20; - Li positions: (0,0,0), (0,0,1/2) and the equivalent ones shifted by the in‑plane lattice (e.g., fractional (1/3,2/3,0) etc. Actually the standard description uses three Li layers per supercell, but for a 1×1×1 hexagonal cell the number of atoms is 3 Li, 3 Co, 6 O = 12 atoms. Wait – let’s be precise: The conventional R-3m cell (hexagonal setting) contains 3 Li, 3 Co, 6 O = \*\*12 atoms\*\*. However, many DFT calculations use a 2×2×1 supercell or a primitive cell. For the purpose of an active learning demonstration, we can use the conventional hexagonal cell (12 atoms) which is still manageable.  

&#x20; - \*\*Final choice\*\*: Use the conventional hexagonal cell with lattice constants `a` (in‑plane) and `c` (out‑of‑plane). The cell contains 12 atoms:  

&#x20;   - Li: (0,0,0), (0,0,0.5) – two layers, but in R-3m the Li and Co layers alternate. Actually the correct fractional coordinates are:  

&#x20;     Li: (0,0,0), (0,0,0.5)  

&#x20;     Co: (0,0,0.25), (0,0,0.75)  

&#x20;     O: (0.25,0.25,0.25), (0.75,0.75,0.25), (0.25,0.25,0.75), (0.75,0.75,0.75) – but with the full hexagonal cell this gives 12 atoms.  

&#x20;   For simplicity, the user will import the structure from a CIF file (e.g., from Materials Project or ICSD) using `ase.io.read()`. That is the safest and most accurate approach.



\### 1.1 Recommended approach to create the structure

```python

from ase.io import read

\# Download a standard CIF file for LiCoO2 (R-3m) from Materials Project or use a built-in ASE method.

\# Here we construct manually for reproducibility:

import numpy as np

from ase import Atoms



def build\_licoo2(a, c, cell=None):

&#x20;   """

&#x20;   Build LiCoO2 conventional hexagonal cell (12 atoms) with lattice constants a and c (Angstrom).

&#x20;   The fractional coordinates are taken from ICSD #: Li (0,0,0), (0,0,0.5);

&#x20;   Co (0,0,0.25), (0,0,0.75); O (1/3,2/3,0.25), (2/3,1/3,0.25), (1/3,2/3,0.75), (2/3,1/3,0.75).

&#x20;   (These are approximate; the user should verify. For real calculations, prefer reading from a reliable CIF.)

&#x20;   """

&#x20;   # This is a placeholder – the codex should implement a proper builder or use ase.io.read with a template CIF.

&#x20;   # For now, we instruct the assistant to use a pre‑computed CIF file.

&#x20;   pass

