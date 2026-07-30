# Scientific scope

ActiStruct addresses targeted atomistic structure exploration when the design
variables and DFT workflow are already defined. Examples include adsorption
coordinates, lattice parameters, molecular geometry parameters, and other
small search spaces.

The software combines candidate selection, surrogate updates, QE execution
management, failure recording, and provenance. It is designed to make a
calculation campaign easier to inspect and reproduce, including when runs fail.

## Evidence currently supported

- TMC QE parsing and reliability tracking on ferrocene, Ni(CO)4, Cr(CO)6,
  and Fe(CO)5.
- A retrospective GP/AL demonstration on the 16-row TMC dataset.
- A completed Ti3C2-O low-fidelity, three-track campaign.
- Offline failure-aware acquisition experiments.
- Software invariants covered by the no-QE test suite.

## Out of scope

ActiStruct is not a global crystal-structure search engine, a general catalyst
discovery system, an experimental validation pipeline, or a guarantee of DFT
cost reduction. A successful low-fidelity campaign does not establish
high-fidelity ranking transfer.

Every public quantitative statement must appear in
[claim governance](claim_governance.md) with evidence, a reproduction command
where available, and a limitation.
