# Ti3C2-O Clean-Slab LF Evidence Audit

Audit date: 2026-07-16.

The README historically reported one low-fidelity Ti3C2-O clean-slab static SCF
as `JOB DONE` with total energy `-25973.017 eV`. During this audit, the raw
clean-slab QE output was not present in the repository or in the current
`/tmp/qe_scratch/ti3c2_o_her/low` scratch tree.

Therefore this directory is an evidence-gap record, not a primary QE evidence
package. The clean-slab claim must be regenerated before citation-grade use.

Available evidence:

- relaxed slab trajectory:
  `data/structures/ti3c2_o/ti3c2_o_slab_relaxed.traj`
- relaxed trajectory SHA-256:
  `55a23221a3e07ca161e73b7830b3532403125323f6c350c7a62cd25100518ac1`
- unrelaxed trajectory SHA-256:
  `b89f645969bdce25ce4cb91c80ecf16b360d201dd8b21308cd60956715068085`

Regeneration command:

```bash
cd /mnt/d/Research/Dr.Kulik_MIT
source .venv/bin/activate
FIDELITY=low python -m examples.manual_qe.ti3c2_o_her_qe_active_inverse
```

When regenerated, store a raw-output hash, input hash, parsed result, QE
version, pseudopotential checksums, and a short final-output excerpt here.
