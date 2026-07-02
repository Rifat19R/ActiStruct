"""Explicit numerical verification of GNN claims. Delete after review."""
import numpy as np
from ase import Atoms
from actistruct.gnn.config import GNNConfig
from actistruct.gnn.encoder import SchNetEncoder
from actistruct.gnn.surrogate import HybridGPSurrogate

config = GNNConfig(embedding_dim=16, num_interactions=2, n_gaussians=10,
                   cutoff=5.0, max_epochs=50, patience=10, lr=1e-3, random_state=42)

def make_nitride(a, c):
    return Atoms(
        symbols=["Ca", "Al", "N", "N"],
        positions=[[0,0,0],[a/2,a/2,c/2],[0,0,c*0.375],[a/2,a/2,c*0.875]],
        cell=[[a,0,0],[0,a,0],[0,0,c]], pbc=True,
    )

print("=" * 55)
print("  GNN Numerical Verification")
print("=" * 55)

# ── 1. Permutation invariance ──────────────────────────────
print("\n[A] Permutation Invariance")
encoder = SchNetEncoder(config)
encoder.eval()

s = make_nitride(3.15, 5.00)
perm = [2, 0, 3, 1]   # Ca,Al,N,N -> N,Ca,N,Al
s_perm = Atoms(
    symbols=[s.symbols[i] for i in perm],
    positions=s.positions[perm],
    cell=s.cell, pbc=True,
)
e_orig = encoder.embed(s)
e_perm = encoder.embed(s_perm)
diff_perm = float(np.linalg.norm(e_orig - e_perm))
print(f"  |emb(Ca,Al,N,N) - emb(N,Ca,N,Al)| = {diff_perm:.2e}")
print(f"  Threshold < 1e-3 : {'PASS' if diff_perm < 1e-3 else 'FAIL'}")

# ── 2. Geometry sensitivity ────────────────────────────────
print("\n[B] Geometry Sensitivity")
s_compressed = make_nitride(3.15, 5.00)
s_stretched   = make_nitride(3.80, 6.20)
e_comp  = encoder.embed(s_compressed)
e_strch = encoder.embed(s_stretched)
diff_geo = float(np.linalg.norm(e_comp - e_strch))
print(f"  |emb(a=3.15) - emb(a=3.80)| = {diff_geo:.4f}")
print(f"  Threshold > 1e-3  : {'PASS' if diff_geo > 1e-3 else 'FAIL'}")

# ── 3. R² overfit sanity check ─────────────────────────────
print("\n[C] R2 Overfit Sanity Check (full pipeline on 8 CaAlN2 structures)")
surrogate = HybridGPSurrogate(config)
rng = np.random.default_rng(0)
a_vals = np.linspace(3.0, 3.8, 8)
structs, energies = [], []
for a in a_vals:
    c = a * 1.6 + rng.uniform(-0.05, 0.05)
    structs.append(make_nitride(float(a), float(c)))
    energies.append(-134.0 + 50.0 * (a - 3.2) ** 2)

surrogate.pretrain(structs, energies)
surrogate.fit(structs, energies)
means, stds = surrogate.predict_batch(structs)
targets = np.array([e / len(s) for e, s in zip(energies, structs)])

ss_res = float(np.sum((means - targets) ** 2))
ss_tot = float(np.sum((targets - targets.mean()) ** 2))
r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 1.0
print(f"\n  R2 on training data: {r2:.6f}")
print(f"  Threshold > 0.8   : {'PASS' if r2 > 0.8 else 'FAIL'}")
print(f"\n  {'a (A)':>6}  {'target':>10}  {'pred':>10}  {'|err|':>8}  {'std':>12}")
print(f"  {'-'*54}")
for a, t, m, s in zip(a_vals, targets, means, stds):
    flag = "<-- outside" if abs(m - t) > 0.5 else ""
    print(f"  {a:6.2f}  {t:10.4f}  {m:10.4f}  {abs(m-t):8.4f}  {s:12.8f}  {flag}")

print(f"\n  Encoder frozen: "
      f"{sum(1 for p in surrogate.encoder.parameters() if not p.requires_grad)}/"
      f"{sum(1 for _ in surrogate.encoder.parameters())} params")
print("=" * 55)
