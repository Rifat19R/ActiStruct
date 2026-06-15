\# Task: Active Learning + Inverse Design for H/Pt(111) Adsorption System using Quantum ESPRESSO



You are an expert Python and DFT programmer. Write a complete script that implements \*\*combined active learning and inverse design\*\* for a single hydrogen atom adsorbed on a Pt(111) slab surface using Quantum ESPRESSO (QE) via ASE.



The goal is to find the \*\*optimal adsorption site (in-plane coordinates x, y)\*\* that minimises the \*\*referenced adsorption energy\*\* of hydrogen on Pt(111), using as few QE calculations as possible. This is a \*\*2‑dimensional optimisation\*\* problem directly relevant to catalysis and the Hydrogen Evolution Reaction (HER).



\## 1. System definition

\- \*\*Slab\*\*: Pt(111) surface, 3 layers, p(2×2) supercell in the surface plane.

&#x20; - Number of Pt atoms: 3 layers × 4 atoms per layer = 12 atoms.

&#x20; - The bottom layer is fixed at bulk positions to mimic a semi‑infinite substrate (commonly used practice to reduce computational cost).

&#x20; - The top two layers are allowed to relax (optional, but for efficiency can be fixed in early iterations).

\- \*\*Adsorbate\*\*: single hydrogen atom (H) initially placed 1.5–2.0 Å above the surface.

\- \*\*Adsorption sites to optimise\*\*:

&#x20; - Top (above a Pt atom)

&#x20; - Bridge (between two Pt atoms)

&#x20; - fcc hollow (directly above an octahedral hollow site)

&#x20; - hcp hollow (directly above a tetrahedral hollow site)

\- \*\*Variables\*\*: in‑plane coordinates `(x, y)` of the H atom relative to the surface unit cell. The z‑coordinate (height) is also relaxed in each DFT calculation, but the active learning will focus on (x, y).

\- \*\*Search range\*\*: the irreducible wedge of the p(2×2) surface unit cell (typically 0 ≤ x ≤ a/2, 0 ≤ y ≤ a/√3/2, etc.).

\- \*\*Target\*\*: minimise the \*\*referenced adsorption energy\*\* `E\_ads = E\_slab+H − (E\_slab + E\_H\_atom)`, where `E\_H\_atom` is the total energy of an isolated H atom in a large box. A more negative value indicates stronger binding.



\## 2. Expected results (literature values)

&#x20; - The fcc hollow site is the most stable adsorption site for H on Pt(111), with a referenced adsorption energy around \*\*−0.52 eV\*\* (PBE).\[reference:0]

&#x20; - The hcp hollow site is slightly less stable (≈ −0.47 eV), and the top site is about −0.49 eV.\[reference:1]

&#x20; - Equilibrium height of H above the surface: ≈ 1.1 Å (fcc site).



\## 3. DFT parameters for QE (converged for Pt/H system)

&#x20; - \*\*Pseudopotentials\*\* (ultrasoft, from SSSP efficiency library or PSLibrary):

&#x20;   - Pt: `Pt.pbe-nd-rrkjus\_psl.1.0.0.UPF` (or `Pt.pbe-n-rrkjus\_psl.1.0.0.UPF`)

&#x20;   - H: `H.pbe-rrkjus\_psl.1.0.0.UPF`

&#x20; - `ecutwfc = 60.0` Ry (Pt requires higher cutoff; 50–60 Ry is safe). `ecutrho = 480.0` Ry (8× for ultrasoft).

&#x20; - \*\*k‑points\*\*: Γ‑centered Monkhorst‑Pack grid for the p(2×2) surface cell. Use `kpts=(4,4,1)` for the slab (dense enough in‑plane, single point along z due to vacuum). For metal surfaces, use \*\*Marzari‑Vanderbilt smearing\*\* (`smearing='mv'`) with `degauss=0.02` Ry to aid SCF convergence.

&#x20; - \*\*Vacuum\*\*: At least 15 Å of vacuum along the z‑direction to avoid interactions between periodic slabs. Set cell vector `c = 15.0` Å (or larger).

&#x20; - \*\*Convergence\*\*: `conv\_thr = 1e-8` Ry, `electron\_maxstep = 300` (metal surfaces can be slow to converge).

&#x20; - \*\*Spin\*\*: unpolarised (`nspin=1`) for H/Pt(111).



\## 4. Slab construction (detailed)

Use ASE’s `build` module to generate the slab:

```python

from ase.build import fcc111, add\_adsorbate

from ase import Atoms

import numpy as np



def build\_pt111\_slab(lattice\_constant, layers=3, vacuum=15.0, size=(2,2,1)):

&#x20;   """

&#x20;   Build Pt(111) slab with p(2×2) surface cell, 3 layers, and vacuum.

&#x20;   Returns an ASE Atoms object.

&#x20;   """

&#x20;   # Bulk Pt lattice constant: optimised value \~3.97 Å (PBE)\[reference:2]

&#x20;   # You may pre‑optimise it or use a literature value (e.g., 3.97).

&#x20;   a = lattice\_constant   # in Å

&#x20;   slab = fcc111('Pt', size=size, a=a, vacuum=vacuum, layers=layers)

&#x20;   # The `fcc111` function creates a slab with the correct orientation.

&#x20;   # The bottom layer(s) may be fixed later.

&#x20;   return slab



def add\_h\_to\_slab(slab, x, y, height=1.5):

&#x20;   """

&#x20;   Add a H atom at fractional coordinates (x, y) in the surface cell,

&#x20;   at a given height (Å) above the top layer.

&#x20;   """

&#x20;   # Get the topmost Pt atom’s z‑coordinate to set the height correctly.

&#x20;   # A simpler approach: add the H atom at the desired in‑plane position

&#x20;   # and a fixed z (e.g., 10 Å) then relax.

&#x20;   # ASE’s add\_adsorbate can place the H atom relative to the surface.

&#x20;   from ase.build import add\_adsorbate

&#x20;   # Convert (x,y) fractional to Cartesian (assuming p(2×2) cell)

&#x20;   cell = slab.cell

&#x20;   x\_cart = x \* cell\[0]\[0]

&#x20;   y\_cart = y \* cell\[1]\[1]

&#x20;   position = (x\_cart, y\_cart, height)

&#x20;   # Actually, add\_adsorbate is easier:

&#x20;   # slab = add\_adsorbate(slab, Atoms('H'), height, position=(x,y)) ... but careful.

&#x20;   # Let’s just create a new H atom at the desired coordinates.

&#x20;   h\_atom = Atoms('H', positions=\[\[x\_cart, y\_cart, height]])

&#x20;   slab += h\_atom

&#x20;   return slab

