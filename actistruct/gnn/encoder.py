"""SchNet-style GNN encoder with real geometry-aware message passing.

Key design decisions (all required, not optional)
--------------------------------------------------
1. Neighbor list via ase.neighborlist — gives real pairwise distances d_ij.
   Structures with identical composition but different bond lengths will
   produce *different* embeddings (this is the whole point).

2. Gaussian RBF expansion of distances — maps each scalar d_ij onto a
   n_gaussians-dimensional feature vector. Centres evenly span [0, cutoff].

3. Message-passing interaction block:
     filter_ij = MLP(rbf(d_ij))          # continuous convolution filter
     message_i = sum_j( filter_ij * h_j ) # neighbour-weighted messages
     h_i = h_i + message_i               # residual update

4. Mean-pool over atoms → one fixed-size structure embedding per structure.

Geometry-sensitivity guarantee
-------------------------------
The geometry sensitivity test (test_hybrid_surrogate.py) verifies that two
structures with identical composition but different bond lengths produce
embeddings that differ by more than a numerical tolerance. This test FAILS
against any implementation that discards distance information (e.g. pure
atom-number mean-pool). It must pass against this implementation.

Permutation invariance
----------------------
The mean-pool aggregation and pairwise-distance message passing are
inherently permutation-invariant: swapping atom indices changes neither the
set of pairwise distances nor the sum/mean of atom embeddings.
"""
from __future__ import annotations

import math

import numpy as np
import torch
import torch.nn as nn
from ase import Atoms
from ase.neighborlist import neighbor_list

from actistruct.gnn.config import GNNConfig


# ── Radial Basis Function expansion ──────────────────────────────────────────

class GaussianRBF(nn.Module):
    """Expand a scalar distance into n_gaussians Gaussian basis values.

    Centres are evenly spaced in [0, cutoff]. Width sigma is set so adjacent
    Gaussians overlap at half-maximum, giving smooth coverage of the range.
    """

    def __init__(self, n_gaussians: int, cutoff: float) -> None:
        super().__init__()
        centres = torch.linspace(0.0, cutoff, n_gaussians)
        self.register_buffer("centres", centres)
        self.sigma = cutoff / n_gaussians   # width ≈ spacing between centres

    def forward(self, distances: torch.Tensor) -> torch.Tensor:
        # distances: (n_edges,)
        # output:    (n_edges, n_gaussians)
        d = distances.unsqueeze(-1)  # (n_edges, 1)
        return torch.exp(-((d - self.centres) ** 2) / (2 * self.sigma ** 2))


# ── Single interaction block ──────────────────────────────────────────────────

class InteractionBlock(nn.Module):
    """One SchNet message-passing step.

    filter_network: RBF embedding → distance-conditioned filter weights
    atom_update:    linear transform of the filtered message aggregate
    """

    def __init__(self, embedding_dim: int, n_gaussians: int) -> None:
        super().__init__()
        self.filter_network = nn.Sequential(
            nn.Linear(n_gaussians, embedding_dim),
            nn.SiLU(),
            nn.Linear(embedding_dim, embedding_dim),
        )
        self.atom_update = nn.Linear(embedding_dim, embedding_dim)

    def forward(
        self,
        h: torch.Tensor,          # (n_atoms, D)
        edge_index: torch.Tensor,  # (2, n_edges) — [source, target]
        rbf_feats: torch.Tensor,   # (n_edges, n_gaussians)
    ) -> torch.Tensor:
        src, tgt = edge_index[0], edge_index[1]

        # Continuous convolution filter for each edge.
        W_ij = self.filter_network(rbf_feats)   # (n_edges, D)

        # Weighted neighbour embeddings.
        msg = W_ij * h[src]                     # (n_edges, D)

        # Aggregate messages at target atoms (scatter-add).
        agg = torch.zeros_like(h)
        agg.index_add_(0, tgt, msg)             # (n_atoms, D)

        # Residual update.
        return h + self.atom_update(agg)        # (n_atoms, D)


# ── Full SchNet encoder ───────────────────────────────────────────────────────

class SchNetEncoder(nn.Module):
    """Geometry-aware GNN encoder (SchNet-style).

    Input:  ASE Atoms object
    Output: 1D structure embedding tensor of shape (embedding_dim,)

    The embedding encodes both composition (atomic numbers) and geometry
    (pairwise distances via the RBF + message-passing stack). Two structures
    with identical composition but different bond lengths will have different
    embeddings — this is a hard requirement, tested in test_hybrid_surrogate.py.
    """

    # Periodic table up to Pu (Z=94) — covers all elements in typical DFT studies.
    MAX_ATOMIC_NUMBER = 94

    def __init__(self, config: GNNConfig) -> None:
        super().__init__()
        self.config = config
        D  = config.embedding_dim
        Ng = config.n_gaussians

        # Learnable embedding for each atomic species.
        self.atom_embedding = nn.Embedding(self.MAX_ATOMIC_NUMBER + 1, D)

        # Distance feature extractor.
        self.rbf = GaussianRBF(Ng, config.cutoff)

        # Stack of interaction blocks.
        self.interactions = nn.ModuleList(
            [InteractionBlock(D, Ng) for _ in range(config.num_interactions)]
        )

        # Output projection (optional but helps separate the embedding space
        # from the atom-level interaction space).
        self.output_proj = nn.Sequential(
            nn.Linear(D, D),
            nn.SiLU(),
            nn.Linear(D, D),
        )

        self._init_weights()

    def _init_weights(self) -> None:
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.xavier_uniform_(m.weight)
                if m.bias is not None:
                    nn.init.zeros_(m.bias)

    def forward(self, atoms: Atoms) -> torch.Tensor:
        """Encode one ASE Atoms object → embedding vector (embedding_dim,)."""
        # Build neighbour list (periodic boundary conditions respected).
        i_idx, j_idx, distances = neighbor_list("ijd", atoms, cutoff=self.config.cutoff)

        atomic_numbers = torch.tensor(
            atoms.get_atomic_numbers(), dtype=torch.long
        )                                                   # (n_atoms,)

        if len(i_idx) == 0:
            # Isolated atoms / very large cutoff miss — fall back to pure
            # atom embedding (no messages). Unusual but shouldn't crash.
            h = self.atom_embedding(atomic_numbers)         # (n_atoms, D)
        else:
            edge_index = torch.tensor(
                np.stack([i_idx, j_idx], axis=0), dtype=torch.long
            )                                               # (2, n_edges)
            dist_tensor = torch.tensor(distances, dtype=torch.float32)  # (n_edges,)
            rbf_feats   = self.rbf(dist_tensor)             # (n_edges, Ng)

            # Initial atom embeddings.
            h = self.atom_embedding(atomic_numbers)         # (n_atoms, D)

            # Message-passing rounds.
            for block in self.interactions:
                h = block(h, edge_index, rbf_feats)         # (n_atoms, D)

        # Mean-pool over atoms → structure-level embedding.
        embedding = h.mean(dim=0)                           # (D,)
        return self.output_proj(embedding)                  # (D,)

    def embed(self, atoms: Atoms) -> np.ndarray:
        """Return a numpy embedding vector (no gradient tracking)."""
        self.eval()
        with torch.no_grad():
            return self.forward(atoms).numpy()
