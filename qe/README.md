Quantum ESPRESSO inputs/outputs for the TMC benchmark.

- `inputs/relax/`, `inputs/scf/` — generated `.in` files, tracked in git.
- `outputs/relax/`, `outputs/scf/` — QE run outputs. Large binary artifacts (`.wfc*`, `.save/`) are gitignored.
- `workdirs/` — present in the scaffold but unused for `outdir` (see below); legacy/optional.

pw.x for this project runs at `/home/duets/q-e-qe-7.4.1/bin/pw.x` inside WSL (Ubuntu, user `duets`), not on Windows PATH. Not installed inside the `actistruct` venv — it's a separate QE build.

**`outdir` (scratch/checkpoint) lives on native WSL ext4, not this Windows-mounted drive.** `D:` is mounted via `9p` (DrvFs) in WSL, which proved unreliable for QE's `.save/` checkpoint directory creation under concurrent MPI ranks — a real ferrocene relax crashed with `unable to create directory .../ferrocene_initial.save/` right after a fully converged 38-iteration SCF. `scripts/06_build_qe_inputs.py` points `outdir` at `configs/project_config.yaml`'s `qe.workdir_native_root` (`/home/duets/qe_workdirs` by default) instead. Create that directory in WSL before running (`mkdir -p /home/duets/qe_workdirs/<candidate_id>`), not under `D:`.
