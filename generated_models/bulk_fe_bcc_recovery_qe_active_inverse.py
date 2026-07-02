"""Active learning + inverse design for BCC Fe with recovery-enabled DFT.

This is a recovery-enabled variant of bulk_fe_bcc_qe_active_inverse.py.
Key differences from the benchmark version:
  - spin_polarized=True  (Fe is ferromagnetic; False was a known bug in the
    benchmark script — it gave wrong magnetic ordering and struggled to converge)
  - use_recovery=True    (every QE attempt is classified, escalated, and logged)
  - recovery_ledger_path points to the native-Linux production ledger
  - ESPRESSO_PSEUDO set explicitly to the full SSSP 1.3.0 PBE efficiency set

Pseudopotential type audit (SSSP 1.3.0):
  Fe: Fe.pbe-spn-kjpaw_psl.0.2.1.UPF -> PAW (kjpaw)
  Single element: no PAW/USPP mixing possible.

Convergence risk profile:
  - Fe 3d d-electrons with PAW -> slow charge relaxation
  - Dense k-grid (14x14x14) amplifies oscillations
  - spin_polarized=True adds magnetic degree of freedom (more SCF variables)
  - These are exactly the conditions the recovery escalation is designed for
"""
from __future__ import annotations

import os
from pathlib import Path
import sys

# Set PSEUDO_DIR before qe_active_inverse_common is imported (reads env at load time).
_SSSP_DIR = "/mnt/d/Rifat/Research/SSSP_1.3.0_PBE_efficiency"
os.environ["ESPRESSO_PSEUDO"] = _SSSP_DIR

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qe_active_inverse_common import ActiveSystem, Variable, run_system
from generated_models.structure_builders import build_bulk_bcc


def build_bulk_fe_recovery(a: float):
    return build_bulk_bcc("Fe", a)


SYSTEM = ActiveSystem(
    key="bulk_fe_bcc_recovery",
    title="BCC Fe (recovery-enabled, spin-polarized)",
    builder=build_bulk_fe_recovery,
    variables=(
        Variable("a", 2.65, 3.05, (2.70, 2.87, 3.00)),
    ),
    pseudopotentials={"Fe": "Fe.pbe-spn-kjpaw_psl.0.2.1.UPF"},  # PAW only
    ecutwfc=70.0,
    ecutrho=560.0,
    kpts=(14, 14, 14),
    smearing="mv",
    degauss=0.02,
    spin_polarized=True,   # correct: Fe is ferromagnetic (benchmark had False)
    energy_per_atom=True,
    result_quantity="Total energy per atom objective",
    result_units="eV/atom",
    n_candidates=61,
    random_state=106,
    category="Simple metals (FCC, BCC)",
    notes=(
        "Recovery-enabled BCC Fe. spin_polarized=True corrects the benchmark "
        "bug. Pseudopotential is PAW-only (no mixing). SSSP 1.3.0 PBE efficiency."
    ),
    use_recovery=True,
    recovery_ledger_path=Path("/home/alchemist/actistruct_data/Fe_BCC/recovery.jsonl"),
)


if __name__ == "__main__":
    run_system(SYSTEM)
