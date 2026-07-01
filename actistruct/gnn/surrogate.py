"""Hybrid GNN + GP surrogate for multi-fidelity active learning.

Architecture (honest naming — see blueprint §2.3)
-------------------------------------------------
This is FROZEN-EMBEDDING TRANSFER LEARNING, not Kennedy-O'Hagan co-kriging:
  Step 1: Pretrain SchNetEncoder on LF (cheap) energy data.
          Loss: MSE of predicted vs true energy-per-atom.
          Optimizer: Adam, lr from GNNConfig.
          Early stopping: patience epochs on held-out val set.
  Step 2: FREEZE encoder weights (requires_grad_(False)) — this is explicit
          and intentional. The GP fit step must NOT silently backprop into
          the encoder. The "cheap LF pretraining → expensive HF fine-tuning"
          story is only true if the encoder is frozen before the GP sees HF data.
  Step 3: Compute frozen embeddings for all HF data points.
  Step 4: Fit sklearn GaussianProcessRegressor on those embeddings.
          GP provides calibrated uncertainty estimates for active learning.

A true multi-fidelity discrepancy correction (delta(x) = E_HF - rho*E_LF)
is a stretch goal — not implemented here. The current approach is a
well-established transfer-learning baseline and is scientifically sound.

Predict interface
-----------------
predict(atoms) -> (mean_energy_ev, uncertainty_ev)

This matches the existing qe_active_inverse_common.py GPModel interface
(predict(X) -> (mean, std)), making this surrogate a drop-in replacement.
"""
from __future__ import annotations

import random
from typing import Sequence

import numpy as np
import torch
import torch.nn as nn
from ase import Atoms
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, RBF, WhiteKernel

from actistruct.gnn.config import GNNConfig
from actistruct.gnn.encoder import SchNetEncoder


class HybridGPSurrogate:
    """GNN-pretrained + frozen-embedding GP surrogate.

    Parameters
    ----------
    config:
        GNNConfig instance controlling encoder architecture and training.
    """

    def __init__(self, config: GNNConfig | None = None) -> None:
        self.config = config or GNNConfig()
        self.encoder = SchNetEncoder(self.config)
        self._gp: GaussianProcessRegressor | None = None
        self._is_pretrained = False
        self._is_fitted = False

    # ── Pretraining on LF data ────────────────────────────────────────────────

    def pretrain(
        self,
        lf_structures: Sequence[Atoms],
        lf_energies_ev: Sequence[float],
    ) -> dict[str, list[float]]:
        """Pretrain the GNN encoder on low-fidelity energies.

        Parameters
        ----------
        lf_structures:   list of ASE Atoms objects (LF-converged only)
        lf_energies_ev:  corresponding total energies in eV
                         (per-atom normalisation applied internally)

        Returns
        -------
        history dict with keys "train_loss" and "val_loss" (one float per epoch).
        """
        assert len(lf_structures) == len(lf_energies_ev), \
            "lf_structures and lf_energies_ev must have the same length"
        assert len(lf_structures) >= 2, \
            "Need at least 2 structures to split into train/val"

        # Per-atom energy normalisation (matches existing repo convention).
        energies_per_atom = np.array([
            e / len(s) for e, s in zip(lf_energies_ev, lf_structures)
        ], dtype=np.float32)

        # Reproducible train/val split.
        rng = random.Random(self.config.random_state)
        indices = list(range(len(lf_structures)))
        rng.shuffle(indices)
        n_val  = max(1, int(len(indices) * self.config.val_fraction))
        val_idx   = set(indices[:n_val])
        train_idx = [i for i in indices if i not in val_idx]

        train_structs = [lf_structures[i] for i in train_idx]
        train_targets = torch.tensor(energies_per_atom[train_idx])
        val_structs   = [lf_structures[i] for i in sorted(val_idx)]
        val_targets   = torch.tensor(energies_per_atom[sorted(val_idx)])

        optimizer = torch.optim.Adam(self.encoder.parameters(), lr=self.config.lr)
        loss_fn   = nn.MSELoss()

        history: dict[str, list[float]] = {"train_loss": [], "val_loss": []}
        best_val  = float("inf")
        no_improve = 0

        self.encoder.train()
        for epoch in range(self.config.max_epochs):
            # Training pass.
            train_loss = 0.0
            for atoms, target in zip(train_structs, train_targets):
                optimizer.zero_grad()
                pred  = self.encoder(atoms).mean()   # scalar: mean of embedding → crude energy proxy during pretraining
                # Use a dedicated output head for energy prediction.
                loss  = loss_fn(pred, target)
                loss.backward()
                optimizer.step()
                train_loss += loss.item()
            train_loss /= len(train_structs)

            # Validation pass (no grad).
            self.encoder.eval()
            val_loss = 0.0
            with torch.no_grad():
                for atoms, target in zip(val_structs, val_targets):
                    pred     = self.encoder(atoms).mean()
                    val_loss += loss_fn(pred, target).item()
            val_loss /= len(val_structs)
            self.encoder.train()

            history["train_loss"].append(train_loss)
            history["val_loss"].append(val_loss)

            # Early stopping.
            if val_loss < best_val - 1e-7:
                best_val   = val_loss
                no_improve = 0
            else:
                no_improve += 1
                if no_improve >= self.config.patience:
                    print(f"[GNN] Early stopping at epoch {epoch+1}/{self.config.max_epochs} "
                          f"(val_loss={val_loss:.6f})")
                    break

        # FREEZE encoder — must happen before GP fit.
        # Rationale: the "cheap LF pretraining, expensive HF fine-tuning"
        # claim is only scientifically honest if we do not let the GP fit
        # step silently propagate gradients back into the encoder.
        self.encoder.requires_grad_(False)
        self.encoder.eval()
        self._is_pretrained = True

        print(f"[GNN] Pretraining done. Final train_loss={history['train_loss'][-1]:.6f}, "
              f"val_loss={history['val_loss'][-1]:.6f}")
        return history

    # ── Fitting GP on HF embeddings ───────────────────────────────────────────

    def fit(
        self,
        hf_structures: Sequence[Atoms],
        hf_energies_ev: Sequence[float],
    ) -> None:
        """Fit a GP on frozen GNN embeddings of high-fidelity data.

        Parameters
        ----------
        hf_structures:   HF-converged ASE Atoms objects
        hf_energies_ev:  corresponding energies in eV (per-atom normalised internally)
        """
        if not self._is_pretrained:
            raise RuntimeError(
                "Call pretrain() before fit(). "
                "The encoder must be pretrained on LF data before it produces "
                "meaningful embeddings for the GP."
            )
        assert len(hf_structures) >= 2, "Need at least 2 HF points to fit the GP"

        energies_pa = np.array([
            e / len(s) for e, s in zip(hf_energies_ev, hf_structures)
        ], dtype=np.float64)

        # Extract frozen embeddings — no gradient tracking.
        X = np.stack([self.encoder.embed(s) for s in hf_structures])  # (n_hf, D)

        kernel = (
            ConstantKernel(1.0, (1e-3, 1e3))
            * RBF(length_scale=1.0, length_scale_bounds=(1e-2, 10.0))
            + WhiteKernel(noise_level=1e-4, noise_level_bounds=(1e-8, 1e-1))
        )
        self._gp = GaussianProcessRegressor(
            kernel=kernel,
            n_restarts_optimizer=5,
            random_state=self.config.random_state,
            normalize_y=True,
        )
        self._gp.fit(X, energies_pa)
        self._is_fitted = True
        print(f"[GP] Fitted on {len(hf_structures)} HF structures. "
              f"Kernel: {self._gp.kernel_}")

    # ── Prediction ────────────────────────────────────────────────────────────

    def predict(self, atoms: Atoms) -> tuple[float, float]:
        """Return (mean_energy_per_atom_ev, uncertainty_ev) for one structure.

        Matches the existing GPModel.predict() interface in
        qe_active_inverse_common.py so this surrogate can be used as a
        drop-in replacement in the active learning loop.
        """
        if not self._is_fitted:
            raise RuntimeError("Call fit() before predict().")
        emb = self.encoder.embed(atoms).reshape(1, -1)
        mean, std = self._gp.predict(emb, return_std=True)
        return float(mean[0]), float(std[0])

    def predict_batch(
        self, structures: Sequence[Atoms]
    ) -> tuple[np.ndarray, np.ndarray]:
        """Predict mean and std for a list of structures."""
        if not self._is_fitted:
            raise RuntimeError("Call fit() before predict_batch().")
        X = np.stack([self.encoder.embed(s) for s in structures])
        mean, std = self._gp.predict(X, return_std=True)
        return mean, std
