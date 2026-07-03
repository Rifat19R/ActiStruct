"""Phase 2 -- GNN encoder and hybrid GP surrogate tests.

Test 1: GEOMETRY SENSITIVITY (the test that validates the fix)
    Two synthetic slabs with identical composition but different bond
    lengths must produce embeddings that differ. A mean-pool-of-atom-numbers
    stub would fail this test -- the RBF + message-passing must pass it.

Test 2: PERMUTATION ROBUSTNESS
    Same structure with atom order shuffled -> embedding must be near-identical.
    Message passing is inherently permutation-invariant; this catches accidental
    order-dependence.

Test 3: MULTI-FIDELITY CONFIG SWITCH
    LF and HF fidelity must produce different ecutwfc/kpts values.

Test 4: OVERFIT SANITY CHECK (replaces the old "returns a finite number" bar)
    Fit the full pipeline on 5-10 synthetic (structure, energy) pairs.
    Training loss must decrease over epochs.
    Predictions on training data must correlate with targets (R2 > 0.8).
    This proves gradients are flowing through the encoder into something
    meaningful, not just that the code runs without crashing.
"""
from __future__ import annotations

import math

import numpy as np
import pytest
import torch
from ase import Atoms

from actistruct.gnn.config import GNNConfig, MultiFidelityConfig
from actistruct.gnn.encoder import SchNetEncoder
from actistruct.gnn.surrogate import HybridGPSurrogate


# -- helper: build generic synthetic 4-atom slab ------------------------------

def _make_test_slab(a: float, c: float) -> Atoms:
    """Minimal 4-atom hexagonal unit for geometry-sensitivity tests.

    Composition (Ca/Al/N2) is arbitrary -- only the geometry matters here.
    Not tied to any specific material system.
    """
    positions = np.array([
        [0.0,      0.0,      0.0  ],   # Ca
        [a / 2.0,  a / 2.0,  c / 2.0],  # Al
        [0.0,      0.0,      c * 0.375],  # N
        [a / 2.0,  a / 2.0,  c * 0.875],  # N
    ])
    cell = [
        [a,   0.0, 0.0],
        [0.0,  a,  0.0],
        [0.0, 0.0,  c ],
    ]
    return Atoms(
        symbols=["Ca", "Al", "N", "N"],
        positions=positions,
        cell=cell,
        pbc=True,
    )


def _make_config(small: bool = True) -> GNNConfig:
    """Return a tiny config for fast tests (not production accuracy)."""
    return GNNConfig(
        embedding_dim=16,
        num_interactions=2,
        n_gaussians=10,
        cutoff=5.0,
        max_epochs=50,
        patience=10,
        lr=1e-3,
        random_state=42,
    )


# -- Test 1: Geometry sensitivity ----------------------------------------------

class TestGeometrySensitivity:
    """The embedding must change when bond lengths change."""

    def test_different_bond_lengths_different_embeddings(self):
        config  = _make_config()
        encoder = SchNetEncoder(config)
        encoder.eval()

        # Two synthetic slabs: same composition, very different lattice params.
        s1 = _make_test_slab(a=3.15, c=5.00)   # near-equilibrium
        s2 = _make_test_slab(a=3.80, c=6.20)   # stretched lattice

        emb1 = encoder.embed(s1)
        emb2 = encoder.embed(s2)

        diff = float(np.linalg.norm(emb1 - emb2))
        assert diff > 1e-3, (
            f"Geometry sensitivity test FAILED: embeddings differ by only {diff:.2e}. "
            "The encoder is not sensitive to bond lengths. "
            "Check that neighbor-list distances are being used in message passing."
        )

    def test_same_structure_same_embedding(self):
        """Sanity: identical structures must produce identical embeddings."""
        config  = _make_config()
        encoder = SchNetEncoder(config)
        encoder.eval()

        s = _make_test_slab(a=3.15, c=5.00)
        emb1 = encoder.embed(s)
        emb2 = encoder.embed(s)

        diff = float(np.linalg.norm(emb1 - emb2))
        assert diff < 1e-8, f"Same structure gave different embeddings (diff={diff:.2e})."


# -- Test 2: Permutation robustness -------------------------------------------

class TestPermutationRobustness:

    def test_shuffled_atom_order_same_embedding(self):
        config  = _make_config()
        encoder = SchNetEncoder(config)
        encoder.eval()

        s = _make_test_slab(a=3.15, c=5.00)

        # Shuffle atom indices (Ca, Al, N, N -> N, Ca, N, Al or similar).
        perm = [2, 0, 3, 1]
        s_shuffled = Atoms(
            symbols=[s.symbols[i] for i in perm],
            positions=s.positions[perm],
            cell=s.cell,
            pbc=True,
        )

        emb_orig    = encoder.embed(s)
        emb_shuffle = encoder.embed(s_shuffled)

        diff = float(np.linalg.norm(emb_orig - emb_shuffle))
        assert diff < 1e-3, (
            f"Permutation robustness FAILED: shuffling atoms changed embedding by {diff:.2e}. "
            "Mean-pool should be permutation-invariant."
        )


# -- Test 3: Multi-fidelity config switch -------------------------------------

class TestMultiFidelityConfig:

    def test_lf_and_hf_have_different_ecutwfc(self):
        mf = MultiFidelityConfig()
        lf = mf.qe_params("low")
        hf = mf.qe_params("high")
        assert lf["ecutwfc"] != hf["ecutwfc"], "LF and HF should have different ecutwfc"
        assert lf["ecutwfc"] == pytest.approx(30.0)
        assert hf["ecutwfc"] == pytest.approx(60.0)

    def test_lf_and_hf_have_different_kpts(self):
        mf = MultiFidelityConfig()
        assert mf.qe_params("low")["kpts"]  == (2, 2, 2)
        assert mf.qe_params("high")["kpts"] == (6, 6, 6)

    def test_invalid_fidelity_raises(self):
        mf = MultiFidelityConfig()
        with pytest.raises(ValueError, match="fidelity"):
            mf.qe_params("medium")


# -- Test 4: Overfit sanity check ----------------------------------------------

class TestOverfitSanityCheck:
    """Full pipeline on small synthetic data -- training loss must decrease
    and predictions on training set must correlate with targets (R^2 > 0.8)."""

    def _make_dataset(self, n: int = 8):
        """Generate n synthetic (atoms, energy) pairs with varied lattice params."""
        rng = np.random.default_rng(0)
        structures, energies = [], []
        a_vals = np.linspace(3.0, 3.8, n)
        for a in a_vals:
            c = a * 1.6 + rng.uniform(-0.05, 0.05)
            s = _make_test_slab(a=a, c=c)
            structures.append(s)
            # Synthetic energy: rough Birch-Murnaghan-like trend per atom.
            energies.append(-134.0 + 50.0 * (a - 3.2) ** 2)
        return structures, energies

    def test_training_loss_decreases(self):
        config    = _make_config()
        surrogate = HybridGPSurrogate(config)
        structs, energies = self._make_dataset(n=8)

        history = surrogate.pretrain(structs, energies)

        assert len(history["train_loss"]) >= 2, "No epochs recorded in history."
        first_loss = history["train_loss"][0]
        last_loss  = history["train_loss"][-1]
        assert last_loss < first_loss, (
            f"Training loss did not decrease: {first_loss:.6f} -> {last_loss:.6f}. "
            "Gradients may not be flowing through the encoder."
        )

    def test_gp_predictions_correlate_with_targets(self):
        """After pretraining + GP fit, predictions on training data must have R^2 > 0.8."""
        config    = _make_config()
        surrogate = HybridGPSurrogate(config)

        structs, energies = self._make_dataset(n=8)

        # Pretrain on all data (small dataset -- intentional overfit test).
        surrogate.pretrain(structs, energies)

        # Need at least 2 HF points for GP. Use the same data for this test.
        surrogate.fit(structs, energies)

        means, _ = surrogate.predict_batch(structs)
        targets  = np.array([e / len(s) for e, s in zip(energies, structs)])

        ss_res = float(np.sum((means - targets) ** 2))
        ss_tot = float(np.sum((targets - targets.mean()) ** 2))
        r2     = 1.0 - ss_res / ss_tot if ss_tot > 0 else 1.0

        assert r2 > 0.8, (
            f"GP R^2 on training data is {r2:.3f} (< 0.8). "
            "The surrogate is not fitting the training data -- "
            "check that the encoder produces informative embeddings."
        )

    def test_encoder_frozen_after_pretrain(self):
        """After pretrain(), no encoder parameter should require grad."""
        config    = _make_config()
        surrogate = HybridGPSurrogate(config)
        structs, energies = self._make_dataset(n=6)
        surrogate.pretrain(structs, energies)

        for name, param in surrogate.encoder.named_parameters():
            assert not param.requires_grad, (
                f"Parameter {name} still requires grad after pretrain() freeze. "
                "The GP fit step must not backprop into the encoder."
            )

    def test_predict_returns_finite_values(self):
        config    = _make_config()
        surrogate = HybridGPSurrogate(config)
        structs, energies = self._make_dataset(n=6)
        surrogate.pretrain(structs, energies)
        surrogate.fit(structs, energies)

        s_test = _make_test_slab(a=3.3, c=5.3)
        mean, std = surrogate.predict(s_test)

        assert math.isfinite(mean), f"Predicted mean is not finite: {mean}"
        assert math.isfinite(std),  f"Predicted std is not finite: {std}"
        assert std >= 0.0,          f"Predicted std is negative: {std}"


# -- helper: build slab + adsorbed H at fractional (u, v) ---------------------

def _make_slab_with_h(u: float, v: float, a: float = 3.15, c: float = 5.00) -> Atoms:
    """4-atom slab with H placed at in-plane fractional coordinate (u, v).

    Uses _make_test_slab as substrate.  H is placed h_height above the top
    atom (z = c*0.875), which is sufficient to produce distinct local
    environments for different (u, v) values within the GNN cutoff.
    """
    h_height = 1.5  # A above top surface atom
    slab = _make_test_slab(a=a, c=c)
    cell = slab.cell.array
    top_z = float(np.max(slab.positions[:, 2]))
    xy = float(u) * cell[0] + float(v) * cell[1]
    h_pos = [xy[0], xy[1], top_z + h_height]
    return Atoms(
        symbols=list(slab.get_chemical_symbols()) + ["H"],
        positions=np.vstack([slab.positions, h_pos]),
        cell=slab.cell,
        pbc=True,
    )


# -- Test 5: (u, v) design variable sensitivity -------------------------------

class TestUVDesignVariable:
    """The GNN embedding must change when H moves to a different (u, v) site.

    This validates that (u, v) is an informative design variable: the encoder
    can distinguish adsorption sites by their local geometry.  A surrogate
    that ignores H position would fail this test and would be unable to learn
    the DeltaG_H landscape for inverse design.
    """

    def test_different_uv_positions_different_embeddings(self):
        """H at atop vs hollow site must produce different GNN embeddings."""
        config  = _make_config()
        encoder = SchNetEncoder(config)
        encoder.eval()

        # atop: H directly above Ca at (0, 0) -- short Ca-H distance
        s_atop   = _make_slab_with_h(u=0.00, v=0.00)
        # hollow: H above cell center -- equal distances to surrounding atoms
        s_hollow = _make_slab_with_h(u=0.50, v=0.50)

        emb_atop   = encoder.embed(s_atop)
        emb_hollow = encoder.embed(s_hollow)

        diff = float(np.linalg.norm(emb_atop - emb_hollow))
        assert diff > 1e-3, (
            f"UV design variable test FAILED: embeddings at (0,0) and (0.5,0.5) "
            f"differ by only {diff:.2e}. The encoder cannot distinguish H adsorption "
            "sites. Check that H-to-surface distances are encoded in message passing."
        )

    def test_same_uv_same_embedding(self):
        """H at identical (u, v) must produce identical embeddings."""
        config  = _make_config()
        encoder = SchNetEncoder(config)
        encoder.eval()

        s1 = _make_slab_with_h(u=1.0/3.0, v=1.0/3.0)
        s2 = _make_slab_with_h(u=1.0/3.0, v=1.0/3.0)

        diff = float(np.linalg.norm(encoder.embed(s1) - encoder.embed(s2)))
        assert diff < 1e-8, (
            f"Same (u,v) gave different embeddings (diff={diff:.2e})."
        )

    def test_third_site_distinct_from_atop_and_hollow(self):
        """Bridge site (u=0.5, v=0) must differ from both atop and hollow."""
        config  = _make_config()
        encoder = SchNetEncoder(config)
        encoder.eval()

        s_atop   = _make_slab_with_h(u=0.00, v=0.00)
        s_hollow = _make_slab_with_h(u=0.50, v=0.50)
        s_bridge = _make_slab_with_h(u=0.50, v=0.00)

        emb_a = encoder.embed(s_atop)
        emb_h = encoder.embed(s_hollow)
        emb_b = encoder.embed(s_bridge)

        diff_ab = float(np.linalg.norm(emb_a - emb_b))
        diff_hb = float(np.linalg.norm(emb_h - emb_b))
        assert diff_ab > 1e-3, (
            f"Atop and bridge embeddings are identical (diff={diff_ab:.2e})."
        )
        assert diff_hb > 1e-3, (
            f"Hollow and bridge embeddings are identical (diff={diff_hb:.2e})."
        )
