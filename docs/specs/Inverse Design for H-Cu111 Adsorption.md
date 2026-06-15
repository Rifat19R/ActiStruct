\# Task: Active Learning + Inverse Design for H/Cu(111) Adsorption using Quantum ESPRESSO



You are an expert Python and DFT programmer. Write a complete script that implements \*\*combined active learning and inverse design\*\* for a single hydrogen atom adsorbed on a Cu(111) slab using Quantum ESPRESSO (QE) via ASE.



The goal is to find the \*\*in‑plane adsorption site (fractional coordinates x, y)\*\* that \*\*minimises the referenced surface objective\*\* of H on Cu(111), using as few QE calculations as possible. This is a \*\*2‑dimensional optimisation\*\* problem directly relevant to the Hydrogen Evolution Reaction (HER).



\## 1. System definition

\- \*\*Slab\*\*: Cu(111) surface, 3 layers, p(2×2) supercell in the surface plane.

&#x20; - Number of Cu atoms: 3 layers × 4 atoms per layer = 12 atoms.

&#x20; - Bottom layer is fixed at bulk positions to mimic a semi‑infinite substrate.

&#x20; - Top two layers are fully relaxed (ionic relaxation of all atoms except the fixed bottom layer). In the script, we will run a \*\*full relaxation\*\* of the H atom and the top two Cu layers for each candidate (x, y) – this ensures the geometry is physically realistic.

\- \*\*Adsorbate\*\*: single hydrogen atom (H) placed initially at a height of \~1.5 Å above the surface.

\- \*\*Adsorption sites\*\* (known from literature): top (above a Cu atom), bridge (between two Cu atoms), fcc hollow (above an octahedral hollow), hcp hollow (above a tetrahedral hollow).

\- \*\*Variables\*\*: in‑plane fractional coordinates `(x, y)` of the H atom within the p(2×2) surface cell. Range: `\[0, 1] × \[0, 1]`.

\- \*\*Target\*\*: minimise the \*\*referenced adsorption energy\*\* `E\_ads = E\_slab+H − (E\_slab\_clean + E\_H\_atom)`. A more negative value indicates stronger binding.

\- \*\*Expected result\*\*: literature shows the fcc hollow site is most stable (referenced adsorption energy ≈ −0.40 to −0.45 eV with PBE). The hcp site is slightly less stable, and top/bridge are higher in energy.



\## 2. DFT parameters for QE (converged for Cu/H system)

\- \*\*Pseudopotentials\*\* (ultrasoft, from SSSP efficiency library or PSLibrary):

&#x20; - Cu: `Cu.pbe-dn-rrkjus\_psl.1.0.0.UPF` (or `Cu.pbe-nd-rrkjus\_psl.1.0.0.UPF`)

&#x20; - H: `H.pbe-rrkjus\_psl.1.0.0.UPF`

\- `ecutwfc = 50.0` Ry, `ecutrho = 400.0` Ry (8× for ultrasoft).

\- \*\*k‑points\*\*: for the p(2×2) surface cell (in‑plane lattice constants `a` = 2× bulk lattice constant of Cu). Use `kpts = (4,4,1)` (gamma‑centered).

\- \*\*Smearing\*\*: for a metal surface, use `occupations='smearing'`, `smearing='mv'` (Marzari‑Vanderbilt) with `degauss = 0.02` Ry.

\- \*\*Relaxation\*\*: For each candidate `(x, y)`, perform a \*\*full geometry optimisation\*\* of the H atom and the top two Cu layers, while the bottom Cu layer is fixed. Use `ase.optimize.BFGS` or `FIRE` with `fmax = 0.05 eV/Å` and a maximum of 30 steps.

\- \*\*Spin\*\*: unpolarised (`nspin=1`).

\- \*\*Vacuum\*\*: ≥ 15 Å in the z‑direction to avoid slab‑slab interactions.



\## 3. Building the slab and adding H



\### 3.1 Clean Cu(111) slab

Use ASE’s `fcc111` function:

```python

from ase.build import fcc111

from ase.constraints import FixAtoms



def build\_clean\_slab(lattice\_constant=3.61, layers=3, vacuum=15.0, size=(2,2,1)):

&#x20;   """

&#x20;   Create Cu(111) slab with p(2x2) surface cell.

&#x20;   lattice\_constant: bulk fcc lattice constant of Cu (optimised PBE value \~3.61 Å, but you can use 3.61).

&#x20;   """

&#x20;   slab = fcc111('Cu', size=size, a=lattice\_constant, vacuum=vacuum, layers=layers)

&#x20;   # Fix the bottom layer (atoms with smallest z coordinate)

&#x20;   zpos = slab.get\_positions()\[:,2]

&#x20;   bottom\_thresh = min(zpos) + 0.5  # slightly above the very bottom

&#x20;   bottom\_indices = \[i for i, z in enumerate(zpos) if z < bottom\_thresh]

&#x20;   slab.set\_constraint(FixAtoms(indices=bottom\_indices))

&#x20;   return slab

