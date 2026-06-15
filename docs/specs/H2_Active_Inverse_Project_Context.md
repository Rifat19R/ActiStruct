\# Project Context: Combined Active Learning + Inverse Design for H₂ Dimer



\## 1. Project Goal

Build a working Python pipeline that demonstrates \*\*combined active learning and inverse design\*\* for the H₂ molecule (two hydrogen atoms).  

The system must find the \*\*bond distance\*\* that yields a \*\*target total energy\*\* (e.g., the minimum energy, or a specific energy above the minimum) using as few “DFT” evaluations as possible.



This is an \*\*extension\*\* of the successful Cu₂ dimer project. Now we switch to a different chemical system to prove the method’s generality.



\## 2. Why H₂?

\- \*\*Simple and fast\*\* – only two electrons, calculations are extremely cheap.

\- \*\*Well‑known ground truth\*\* – equilibrium bond length ≈ 0.74 Å, dissociation energy ≈ 4.5 eV.

\- \*\*Smooth energy curve\*\* – no unexpected features.

\- \*\*Realistic test\*\* – the algorithm should find the correct minimum without prior knowledge.



\## 3. Important Difference from Cu₂

The EMT calculator (`ase.calculators.emt.EMT`) does \*\*not\*\* work for H₂ (it is parameterised for metals).  

Therefore we need a \*\*different surrogate for DFT\*\*. For the purpose of this MVP (proof‑of‑concept), we will use a \*\*Lennard‑Jones (LJ) potential\*\* that is parameterised to mimic the true H₂ energy curve.



\*\*Why Lennard‑Jones?\*\*  

\- It is analytical, extremely fast, and produces a realistic shape (repulsive at short distances, attractive at medium distances, goes to zero at infinity).  

\- The parameters can be tuned so that the minimum occurs at 0.74 Å and the well depth is 4.5 eV.  

\- Later, you can replace the LJ function with a real DFT calculator (VASP, GPAW, etc.) without changing the rest of the pipeline.



\*\*Alternative (if you want real DFT now):\*\*  

You could use `ase.calculators.emt` for H₂? – It does not work.  

You could use `GPAW` with a small grid, but that would be slower and require more setup. For rapid iteration and debugging, \*\*LJ is recommended first\*\*.



\## 4. Technical Constraints \& Libraries

\- Python 3.8+

\- Libraries: `numpy`, `matplotlib`, `scikit-learn`, `ase` (only for atoms object, not for calculator)

\- \*\*No real DFT\*\* in the first version – use the Lennard‑Jones function provided below.

\- The code must be \*\*self‑contained\*\* and run without any external DFT code.



\## 5. The Lennard‑Jones Calculator for H₂

We will define a simple function:



```python

def h2\_lj\_energy(r):

&#x20;   """

&#x20;   Lennard-Jones potential for H2.

&#x20;   Parameters chosen to give:

&#x20;     - minimum at r0 = 0.74 Angstrom

&#x20;     - well depth = 4.5 eV (so minimum energy = -4.5 eV)

&#x20;   """

&#x20;   r0 = 0.74          # equilibrium distance (Angstrom)

&#x20;   epsilon = 4.5      # well depth (eV), positive number

&#x20;   sigma = r0 / (2\*\*(1/6))

&#x20;   return 4 \* epsilon \* ((sigma/r)\*\*12 - (sigma/r)\*\*6)

