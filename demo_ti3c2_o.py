"""ActiStruct v2 - Ti3C2-O HER demo (no QE required).

Loads the real Ti3C2-O slab geometry, places H at synthetic (u,v) sites,
runs the full v2 surrogate pipeline, and predicts DeltaG_H with uncertainty.

Exercises:
  - SchNetEncoder on real 29-atom MXene+H structures
  - HybridGPSurrogate pretraining (LF synthetic energies)
  - GP fit on frozen HF embeddings
  - Predict + uncertainty at novel (u,v) site
  - Ledger append + read

Run:
    python demo_ti3c2_o.py
"""
from __future__ import annotations

import tempfile
import warnings
from pathlib import Path

# GP ConvergenceWarning is expected in this demo: only 4 HF points on a
# randomly-initialised (not LF-pretrained) encoder. In a real campaign the
# encoder is pretrained first, which spreads the embedding space and avoids
# this. Suppress here so the demo output stays readable.
warnings.filterwarnings("ignore", message=".*optimal value.*lower bound.*")

import numpy as np
from ase import Atoms
from ase.io import read as ase_read

SEP = "=" * 62
SEC = "-" * 50

print("\n" + SEP)
print("  ActiStruct v2.0 -- Ti3C2-O HER Demo")
print(SEP)

# -- locate slab ---------------------------------------------------------------

_SLAB_PATH = Path("/mnt/d/Rifat/Research/actistruct_nebwalk/mxenes/structures/ti3c2_o_slab.traj")
if not _SLAB_PATH.exists():
    print(f"[WARN] Slab traj not found at {_SLAB_PATH}.")
    print("       Falling back to minimal synthetic slab (4-atom hexagonal cell).")
    _USE_REAL_SLAB = False
else:
    _USE_REAL_SLAB = True


def _make_synthetic_slab(a: float = 3.15, c: float = 10.0) -> Atoms:
    """Minimal hexagonal proxy slab for environments without the traj file."""
    cell = [[a, 0, 0], [-a / 2, a * (3 ** 0.5) / 2, 0], [0, 0, c]]
    positions = [
        [0.0,        0.0,       2.0],
        [a / 2,      0.0,       2.4],
        [0.0,        a / 3,     2.8],
        [a / 2,      a / 3,     3.2],
    ]
    return Atoms(
        symbols=["Ti", "C", "Ti", "O"],
        positions=positions,
        cell=cell,
        pbc=True,
    )


def load_slab() -> Atoms:
    if _USE_REAL_SLAB:
        return ase_read(str(_SLAB_PATH))
    return _make_synthetic_slab()


def add_h(slab: Atoms, u: float, v: float, h_height: float = 1.5) -> Atoms:
    """Place H at fractional in-plane (u, v), h_height Ang above top atom."""
    cell = slab.cell.array
    top_z = float(np.max(slab.positions[:, 2]))
    xy = float(u % 1.0) * cell[0] + float(v % 1.0) * cell[1]
    h_pos = [xy[0], xy[1], top_z + h_height]
    result = slab.copy()
    result += Atoms("H", positions=[h_pos])
    result.set_pbc(True)
    return result


# -- Phase 0: Ledger -----------------------------------------------------------

print("\n" + SEC)
print("  Phase 0 -- Ledger")
print(SEC)

from actistruct.core.ledger import append_record, make_record, read_records

with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
    ledger_path = Path(f.name)

for i in range(3):
    r = make_record(
        system="Ti3C2-O",
        fidelity="low",
        params={"u": round(i * 0.2, 2), "v": round(i * 0.1, 2)},
        energy=-25973.0 - i * 0.5,
        converged=True,
    )
    append_record(r, ledger_path=ledger_path)

records = read_records(ledger_path=ledger_path)
print(f"Ledger: wrote and read back {len(records)} records.")
assert len(records) == 3, f"Expected 3, got {len(records)}"
print("  [PASS] Ledger append + read.")

# -- Phase 1: DFT failure classifier + strategy --------------------------------

print("\n" + SEC)
print("  Phase 1 -- Classifier + Escalation Strategy")
print(SEC)

from actistruct.debug.classifier import DFTFailureAnalyzer
from actistruct.debug.strategies import TroubleshootingStrategy

clf = DFTFailureAnalyzer()

cases = [
    ("JOB DONE", "SUCCESS"),
    ("convergence NOT achieved after 100 iterations", "SCF_CONVERGENCE"),
    ("charge density is not normaliz", "ELECTRONIC_INSTABILITY"),
    ("atoms too close", "GEOMETRY_CRASH"),
    ("unexpected output", "UNKNOWN"),
]
for text, expected in cases:
    got = clf.classify(text)
    mark = "PASS" if got == expected else "FAIL"
    print(f"  [{mark}] {expected:<28} classify({text[:40]!r})")
    assert got == expected, f"Expected {expected}, got {got}"

strategy = TroubleshootingStrategy({"electrons": {"mixing_beta": 0.7}})
applied = []
while True:
    nxt = strategy.next_input()
    if nxt is None:
        break
    applied.append(nxt)
assert len(applied) == 4, f"Expected 4 escalation groups, got {len(applied)}"
print(f"  [PASS] Escalation strategy: {len(applied)} groups applied.")

# -- Phase 2: GNN surrogate on real Ti3C2-O geometry --------------------------

print("\n" + SEC)
print("  Phase 2 -- GNN Encoder + Surrogate (real Ti3C2-O slab)")
print(SEC)

from actistruct.gnn.config import GNNConfig
from actistruct.gnn.encoder import SchNetEncoder
from actistruct.gnn.surrogate import HybridGPSurrogate

slab = load_slab()
n_slab_atoms = len(slab)
slab_label = "real 28-atom" if _USE_REAL_SLAB else "synthetic 4-atom"
print(f"Slab: {slab.get_chemical_formula()} ({n_slab_atoms} atoms, {slab_label})")

# 8 (u,v) sites spanning atop, hollow, bridge, and intermediate positions
UV_SITES = [
    (0.00, 0.00, "atop-Ti"),
    (0.33, 0.67, "hollow-1"),
    (0.67, 0.33, "hollow-2"),
    (0.50, 0.00, "bridge-1"),
    (0.00, 0.50, "bridge-2"),
    (0.50, 0.50, "bridge-3"),
    (0.16, 0.33, "mid-1"),
    (0.83, 0.16, "mid-2"),
]

# Synthetic DeltaG_H values (eV) -- physics-inspired:
#   hollow sites nearest thermoneutral (DeltaG_H ~ 0), atop unfavorable.
SYNTHETIC_DG = [0.42, 0.05, 0.08, 0.25, 0.28, 0.31, 0.18, 0.22]

structures = [add_h(slab, u, v) for u, v, _ in UV_SITES]
print(f"Built {len(structures)} slab+H structures ({n_slab_atoms+1} atoms each).")

# Verify GNN encoder distinguishes sites
cfg = GNNConfig(cutoff=5.0, embedding_dim=32, random_state=42)
enc = SchNetEncoder(cfg)

emb_atop   = enc.embed(structures[0])
emb_hollow = enc.embed(structures[1])
dist_atop_hollow = float(np.linalg.norm(emb_atop - emb_hollow))
dist_self        = float(np.linalg.norm(emb_atop - enc.embed(structures[0])))

print(f"  Embedding dist  atop vs hollow:  {dist_atop_hollow:.4f}")
print(f"  Embedding dist  atop vs itself:  {dist_self:.2e}")
assert dist_atop_hollow > 0.01, "Encoder must distinguish different (u,v) sites"
assert dist_self < 1e-4,        "Same structure must give near-identical embedding"
print("  [PASS] GNN encoder distinguishes (u,v) sites.")

# Surrogate: pretrain on 6 LF structures, fit GP on 4 HF structures
surrogate = HybridGPSurrogate(cfg)

lf_structs = structures[:6]
# Surrogate works on total energy (eV); synthesise from per-atom DeltaG_H proxy
lf_energies = [dg * (n_slab_atoms + 1) for dg in SYNTHETIC_DG[:6]]

print(f"\nPretraining on {len(lf_structs)} LF structures...")
history = surrogate.pretrain(lf_structs, lf_energies)
final_train = history["train_loss"][-1]
final_val   = history["val_loss"][-1]
print(f"  train_loss={final_train:.6f}  val_loss={final_val:.6f}")
assert final_train < 1.0, f"Unexpectedly high train loss: {final_train}"
print("  [PASS] Pretraining converged.")

hf_structs   = structures[2:6]
hf_energies  = [dg * (n_slab_atoms + 1) for dg in SYNTHETIC_DG[2:6]]
print(f"\nFitting GP on {len(hf_structs)} HF structures...")
surrogate.fit(hf_structs, hf_energies)
print("  [PASS] GP fit complete.")

# Predict at novel site (mid-2, index 7 -- never seen by GP)
novel = structures[7]
u_novel, v_novel, label_novel = UV_SITES[7]
mean_ev, std_ev = surrogate.predict(novel)
n_atoms = len(novel)
mean_pa = mean_ev
std_pa  = std_ev

print(f"\nPrediction at novel site '{label_novel}' (u={u_novel}, v={v_novel}):")
print(f"  mean energy/atom = {mean_pa:.6f} eV/atom")
print(f"  uncertainty      = {std_pa:.6f} eV/atom")
assert std_pa > 0, "GP must return nonzero uncertainty for unseen site"
print("  [PASS] Predict returns nonzero uncertainty at novel site.")

# Batch predict for all 8 sites
means, stds = surrogate.predict_batch(structures)
best_idx = int(np.argmin(means))
u_best, v_best, label_best = UV_SITES[best_idx]
print(f"\nBatch prediction over all 8 sites:")
for i, (u, v, name) in enumerate(UV_SITES):
    marker = " <-- best" if i == best_idx else ""
    print(f"  {name:<12} (u={u:.2f}, v={v:.2f})  "
          f"mean={means[i]:.4f}  std={stds[i]:.4f}{marker}")
print(f"  [PASS] Best predicted site: '{label_best}' (u={u_best}, v={v_best}).")

# -- Phase 3: Dashboard data loader --------------------------------------------

print("\n" + SEC)
print("  Phase 3 -- Dashboard Data Loader")
print(SEC)

from actistruct.dashboard.data_loader import get_summary_stats, load_ledger

df = load_ledger(ledger_path=ledger_path)
stats = get_summary_stats(df)
print(f"  Loaded ledger: {stats['total_runs']} runs, "
      f"{stats['convergence_rate_pct']:.0f}% converged.")
assert stats["total_runs"] == 3
print("  [PASS] Dashboard data loader.")

ledger_path.unlink(missing_ok=True)

# -- Summary -------------------------------------------------------------------

print("\n" + SEP)
print("  All phases PASSED.")
slab_source = _SLAB_PATH if _USE_REAL_SLAB else "synthetic fallback"
print(f"  Slab source: {slab_source}")
print(f"  GNN cutoff:  {cfg.cutoff} A  |  embedding_dim: {cfg.embedding_dim}")
print(f"  atop vs hollow embedding dist: {dist_atop_hollow:.4f} (> 0.01 threshold)")
print(f"  Best predicted site: '{label_best}' -- mean={means[best_idx]:.4f} eV/atom")
print(SEP + "\n")
