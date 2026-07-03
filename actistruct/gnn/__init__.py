"""Phase 2 — Hybrid GNN + multi-fidelity GP surrogate.

Architecture summary
--------------------
GNN encoder (SchNet-style):
  - Neighbor list via ase.neighborlist (real pairwise distances, cutoff-based)
  - Radial basis function expansion of distances (n_gaussians centres)
  - num_interactions message-passing blocks with residual updates
  - Mean-pool over atoms → structure embedding vector

Hybrid surrogate:
  - Pretrain GNN on cheap low-fidelity (LF) energies (Adam + MSE, early stopping)
  - Freeze encoder weights (requires_grad_(False))
  - Fit sklearn GP on frozen embeddings of high-fidelity (HF) data
  - GP provides Bayesian uncertainty estimates for active learning

Naming honesty (per blueprint)
------------------------------
This is FROZEN-EMBEDDING TRANSFER LEARNING, not Kennedy-O'Hagan co-kriging.
LF pretraining teaches geometry-aware embeddings; the GP is fit on those
frozen embeddings using HF data. A true multi-fidelity discrepancy correction
(delta(x) = E_HF(x) - rho * E_LF(x)) is a stretch goal, not implemented here.
"""

from .config import GNNConfig, MultiFidelityConfig
from .encoder import SchNetEncoder
from .surrogate import HybridGPSurrogate

__all__ = [
    "GNNConfig",
    "MultiFidelityConfig",
    "SchNetEncoder",
    "HybridGPSurrogate",
]
