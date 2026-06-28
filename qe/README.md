Quantum ESPRESSO inputs/outputs for the TMC benchmark.

- `inputs/relax/`, `inputs/scf/` — generated `.in` files, tracked in git.
- `outputs/relax/`, `outputs/scf/` — QE run outputs. Large binary artifacts (`.wfc*`, `.save/`) are gitignored.
- `workdirs/` — scratch run directories, gitignored entirely.

pw.x for this project runs at `/home/duets/q-e-qe-7.4.1/bin/pw.x` inside WSL (Ubuntu, user `duets`), not on Windows PATH. Not installed inside the `actistruct` venv — it's a separate QE build.
