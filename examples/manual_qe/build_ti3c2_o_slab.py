"""Build (and, if QE is available, relax) the Ti3C2-O slab used by
ti3c2_o_her_qe_active_inverse.py.

The original ti3c2_o_slab.traj / ti3c2_o_slab_relaxed.traj (referenced by both
the oracle script and demo_ti3c2_o.py) were produced on a different
machine/environment and are not present here. This script regenerates them:

  1. Build a 2x2 (28-atom) Ti3C2O2 slab from a rock-salt(111)-derived
     Ti-C-Ti-C-Ti core plus O termination (generated_models/structure_builders.py
     :build_ti3c2o2_slab), targeting this repo's own documented bond lengths
     (Ti-C ~2.1 A, Ti-O ~2.0 A). Save as ti3c2_o_slab.traj (unrelaxed).
  2. Run a real QE ionic relaxation (BFGS, bottom 3 atomic layers fixed --
     same convention as the oracle's CONFIG.n_fixed_layers) at LF settings
     (ecutwfc=40, kpts=3x3x1). Save as ti3c2_o_slab_relaxed.traj.

Output directory: $TI3C2_O_STRUCTURES_DIR, default <repo>/data/structures/ti3c2_o.

Run (as a module, from the repo root -- needed for the cross-import of the
oracle script; examples/ has no __init__.py so a direct script path fails):
    python -m examples.manual_qe.build_ti3c2_o_slab            # build + relax
    python -m examples.manual_qe.build_ti3c2_o_slab --no-relax # build only
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from ase.io import write as ase_write

from generated_models.structure_builders import build_ti3c2o2_slab

ROOT = Path(__file__).resolve().parents[2]
STRUCTURES_DIR = Path(os.environ.get(
    "TI3C2_O_STRUCTURES_DIR", str(ROOT / "data" / "structures" / "ti3c2_o")
))


def build_and_save_unrelaxed() -> Path:
    STRUCTURES_DIR.mkdir(parents=True, exist_ok=True)
    atoms = build_ti3c2o2_slab()
    out = STRUCTURES_DIR / "ti3c2_o_slab.traj"
    ase_write(str(out), atoms)
    print(f"Built unrelaxed slab: {atoms.get_chemical_formula()} ({len(atoms)} atoms) -> {out}")
    return out


def relax() -> Path:
    # Import here (not at module scope) so --no-relax / --build-only doesn't
    # require QE_RUN_DIR creation, pseudopotentials, etc.
    import examples.manual_qe.ti3c2_o_her_qe_active_inverse as oracle

    atoms = oracle.load_clean_slab()
    print(
        f"Relaxing clean slab: {atoms.get_chemical_formula()} ({len(atoms)} atoms), "
        f"fidelity={oracle.FIDELITY}, ecutwfc={oracle.ECUTWFC}, kpts={oracle.KPTS_SLAB}, "
        f"QE command: {oracle.QE_COMMAND}"
    )
    wdir = oracle.QE_RUN_DIR / "clean_slab_relax_build"
    oracle.run_energy(atoms, wdir, "ti3c2o_clean_relax", oracle.KPTS_SLAB, relax=True)

    out = STRUCTURES_DIR / "ti3c2_o_slab_relaxed.traj"
    ase_write(str(out), atoms)
    print(f"Relaxed slab saved -> {out}")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-relax", action="store_true", help="Build unrelaxed structure only, skip QE relaxation.")
    args = parser.parse_args()

    build_and_save_unrelaxed()
    if args.no_relax:
        return
    relax()


if __name__ == "__main__":
    main()
