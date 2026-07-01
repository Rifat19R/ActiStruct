"""Configuration dataclasses for the Phase 2 GNN surrogate.

Python dataclasses only (no YAML) — consistent with the existing repo convention
of @dataclass Config in each workflow script.

Physics notes for CaAlN2 (hexagonal nitride):
  - LF: 30 Ry / 300 Ry / [2,2,2] — trend-capturing only, cheap screening.
  - HF: 60 Ry / 600 Ry / [6,6,6] — converged energetics, production accuracy.
  - cutoff=6.0 Å covers Ca–Al (~3.2 Å), Ca–N (~2.5 Å), and second-shell Ca–Ca.
  - n_gaussians=50 gives sufficient RBF resolution for the 0–6 Å distance range.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MultiFidelityConfig:
    """QE convergence parameters for low- and high-fidelity runs."""
    lf_ecutwfc:  float = 30.0
    lf_ecutrho:  float = 300.0
    lf_kpts:     tuple = (2, 2, 2)

    hf_ecutwfc:  float = 60.0
    hf_ecutrho:  float = 600.0
    hf_kpts:     tuple = (6, 6, 6)

    def qe_params(self, fidelity: str) -> dict:
        """Return a dict of ecutwfc/ecutrho/kpts for the requested fidelity."""
        if fidelity == "low":
            return {"ecutwfc": self.lf_ecutwfc, "ecutrho": self.lf_ecutrho, "kpts": self.lf_kpts}
        if fidelity == "high":
            return {"ecutwfc": self.hf_ecutwfc, "ecutrho": self.hf_ecutrho, "kpts": self.hf_kpts}
        raise ValueError(f"fidelity must be 'low' or 'high', got {fidelity!r}")


@dataclass
class GNNConfig:
    """Hyperparameters for the SchNet-style GNN encoder."""
    # Geometry
    cutoff:           float = 6.0    # Angstrom — neighbour search radius
    n_gaussians:      int   = 50     # RBF basis centres spanning [0, cutoff]

    # Network depth / width
    embedding_dim:    int   = 64     # atom embedding and message dimension
    num_interactions: int   = 3      # number of message-passing blocks

    # Training
    lr:               float = 1e-3
    max_epochs:       int   = 200
    patience:         int   = 20     # early-stopping patience (val epochs)
    val_fraction:     float = 0.2
    random_state:     int   = 42     # for reproducible train/val split
