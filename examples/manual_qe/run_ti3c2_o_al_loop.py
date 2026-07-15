"""Phase 3 driver: active-learning loop closure, two parallel surrogate tracks.

Fits both surrogates on the same seed dataset, then runs 5 AL iterations for
each track independently, proposing the next (u,v) via differential_evolution
minimizing a thermoneutral-LCB score, evaluating the real DFT oracle, and
retraining.

Track A -- HybridGPSurrogate (actistruct.gnn.surrogate): SchNetEncoder
pretrained + frozen, GP fit on embeddings of the actual Atoms structure.
Track B -- plain sklearn GP (oracle.GPModel): fit directly on raw (u,v).

Two adaptations from the plan, both necessary given real constraints,
both logged here and in report.md:

1. HybridGPSurrogate.predict() returns (mean_energy_per_atom_eV, std_eV),
   not DeltaG_H directly. Converted: mean_total = mean_per_atom * n_atoms;
   DeltaG_H = mean_total - E_slab - 0.5*E_H2 + 0.04. Uncertainty (std) scales
   the same way (std_total = std_per_atom * n_atoms) since this is a fixed
   linear transform, not a nonlinear one.

2. HybridGPSurrogate is designed for LF-pretrain -> frozen-embedding HF-fit
   (two fidelities). Only LF data exists in this repo (HF deferred, WSL2
   OOM -- see README). Both pretrain() and fit() are called on the same
   dataset here -- not the intended two-fidelity split, the only sensible
   adaptation given the data that actually exists. Flagged as a limitation.

3. The Atoms structures fed to the GNN encoder use H at its exact (u,v) and
   nominal initial height on the already-relaxed clean slab -- NOT each
   site's true final relaxed geometry, which no longer exists on disk (see
   report.md, Phase 2: two unplanned machine restarts wiped /tmp/qe_scratch
   before the trajectories could be archived). (u,v) is exact (H's lateral
   position was frozen during relaxation, never drifted); height/top-layer
   relaxation details are approximated. Flagged as a limitation, not hidden.

Run:
    python -m examples.manual_qe.run_ti3c2_o_al_loop
"""
from __future__ import annotations

import time

import numpy as np
from scipy.optimize import differential_evolution

import examples.manual_qe.ti3c2_o_her_qe_active_inverse as oracle
from actistruct.gnn.config import GNNConfig
from actistruct.gnn.surrogate import HybridGPSurrogate

SEED_POINTS = [
    (0.0, 0.0),          # atop-O (first campaign)
    (1.0 / 3.0, 1.0 / 6.0),   # atop-Ti
    (1.0 / 6.0, 1.0 / 3.0),   # atop-C
    (1.0 / 12.0, 1.0 / 6.0),  # hollow
    (0.25, 0.0),          # O-O bridge
    (0.125, 0.125),        # intermediate
]

MAX_ITERATIONS = 5
KAPPA = 1.0
RANDOM_STATE = 42


def thermoneutral_lcb(mean_delta_g_h: float, std: float, kappa: float = KAPPA) -> float:
    """HER acquisition score: target DeltaG_H near zero, not most negative."""
    return abs(float(mean_delta_g_h)) - kappa * float(std)


def best_thermoneutral_delta(deltas: list[float]) -> float:
    """Return the observed DeltaG_H closest to thermoneutrality."""
    if not deltas:
        raise ValueError("Cannot choose best observed DeltaG_H from an empty list.")
    return min(deltas, key=lambda dg: abs(float(dg)))


def _seed_data():
    oracle.ensure_environment()
    e_slab = oracle.get_clean_slab_energy(retries=oracle.CONFIG.retries)
    e_h2 = oracle.get_h2_energy(retries=oracle.CONFIG.retries)
    points, deltas = [], []
    for u, v in SEED_POINTS:
        dg = oracle.compute_delta_g_h((u, v), retries=oracle.CONFIG.retries)
        if dg is None:
            raise RuntimeError(f"Seed point ({u},{v}) not cached -- run the grid campaign first.")
        points.append((u, v))
        deltas.append(dg)
    return points, deltas, e_slab, e_h2


def _structure_for(u: float, v: float):
    slab = oracle.load_clean_slab()
    return oracle.add_h_to_slab(slab, u, v)


def _to_total_energy(dg: float, e_slab: float, e_h2: float) -> float:
    return dg + e_slab + 0.5 * e_h2 - oracle.DELTA_ZPE_TS_EV


class GNNTrack:
    name = "GNN"

    def __init__(self, points, deltas, e_slab, e_h2):
        self.points = list(points)
        self.deltas = list(deltas)
        self.e_slab = e_slab
        self.e_h2 = e_h2
        self.cfg = GNNConfig(cutoff=5.0, embedding_dim=32, random_state=RANDOM_STATE)
        self._retrain()

    def _retrain(self):
        structures = [_structure_for(u, v) for u, v in self.points]
        totals = [_to_total_energy(dg, self.e_slab, self.e_h2) for dg in self.deltas]
        self.surrogate = HybridGPSurrogate(self.cfg)
        self.surrogate.pretrain(structures, totals)
        self.surrogate.fit(structures, totals)

    def predict(self, u: float, v: float) -> tuple[float, float]:
        atoms = _structure_for(u, v)
        n = len(atoms)
        mean_pa, std_pa = self.surrogate.predict(atoms)
        mean_dg = mean_pa * n - self.e_slab - 0.5 * self.e_h2 + oracle.DELTA_ZPE_TS_EV
        std_dg = std_pa * n
        return mean_dg, std_dg

    def add_point(self, u: float, v: float, dg: float) -> None:
        self.points.append((u, v))
        self.deltas.append(dg)
        self._retrain()


class PlainGPTrack:
    name = "plain-GP"

    def __init__(self, points, deltas):
        self.points = list(points)
        self.deltas = list(deltas)
        self._retrain()

    def _retrain(self):
        self.model = oracle.GPModel()
        self.model.train(self.points, self.deltas)

    def predict(self, u: float, v: float) -> tuple[float, float]:
        mean, std = self.model.predict([(u, v)])
        return float(mean[0]), float(std[0])

    def add_point(self, u: float, v: float, dg: float) -> None:
        self.points.append((u, v))
        self.deltas.append(dg)
        self._retrain()


def propose_next(track, seed: int) -> tuple[tuple[float, float], float, float]:
    def lcb(x: np.ndarray) -> float:
        mean, std = track.predict(float(x[0]) % 1.0, float(x[1]) % 1.0)
        return thermoneutral_lcb(mean, std)

    result = differential_evolution(
        lcb, [(0.0, 1.0), (0.0, 1.0)], seed=seed, maxiter=200, tol=1e-6, polish=True,
    )
    u, v = float(result.x[0]) % 1.0, float(result.x[1]) % 1.0
    mean, std = track.predict(u, v)
    return (u, v), mean, std


def run() -> list[dict]:
    points, deltas, e_slab, e_h2 = _seed_data()
    print(f"Seed dataset: {len(points)} points, DeltaG_H range "
          f"[{min(deltas):.4f}, {max(deltas):.4f}] eV", flush=True)

    tracks = [GNNTrack(points, deltas, e_slab, e_h2), PlainGPTrack(points, deltas)]
    log: list[dict] = []

    for iteration in range(1, MAX_ITERATIONS + 1):
        for track in tracks:
            t0 = time.time()
            (u, v), pred_mean, pred_std = propose_next(track, seed=RANDOM_STATE + iteration)
            is_new_point = oracle.is_new((u, v), track.points)
            dg = oracle.compute_delta_g_h((u, v), retries=oracle.CONFIG.retries)
            if dg is None:
                print(f"[{track.name} it{iteration}] DFT failed at ({u:.4f},{v:.4f}), skipping.", flush=True)
                continue
            wall = time.time() - t0
            track.add_point(u, v, dg)
            best = best_thermoneutral_delta(track.deltas)
            row = {
                "iteration": iteration, "track": track.name, "u": u, "v": v,
                "new_dft_call": is_new_point, "delta_g_h": dg,
                "pred_mean": pred_mean, "pred_std": pred_std,
                "abs_delta_g_h": abs(dg),
                "acquisition_score": thermoneutral_lcb(pred_mean, pred_std),
                "best_delta_g_h": best, "best_abs_delta_g_h": abs(best),
                "n_points": len(track.points), "wall_s": wall,
            }
            log.append(row)
            print(
                f"[{track.name} it{iteration}] u={u:.4f} v={v:.4f} "
                f"DeltaG_H={dg:.4f} (pred={pred_mean:.4f}+/-{pred_std:.4f}) "
                f"best_abs={abs(best):.4f} n={len(track.points)} wall={wall/60:.1f}min "
                f"{'(new DFT call)' if is_new_point else '(cache hit)'}",
                flush=True,
            )

    print("\n=== AL LOOP SUMMARY ===", flush=True)
    for row in log:
        print(row, flush=True)
    return log


if __name__ == "__main__":
    run()
