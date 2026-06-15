# Manual QE Examples

This folder keeps older standalone Quantum ESPRESSO demonstration scripts out of
the repository root. The production benchmark workflows are in `generated_models/`
and are run through the top-level `run.sh` script.

Before running any manual QE script, configure Quantum ESPRESSO in your shell:

```bash
export ESPRESSO_PSEUDO=/path/to/SSSP_1.3.0_PBE_efficiency
export ESPRESSO_COMMAND="mpirun -np 2 pw.x"
```

Example:

```bash
python examples/manual_qe/h2_qe_active_inverse.py
```

Runtime caches are written to `outputs/cache/` and ignored by git.
