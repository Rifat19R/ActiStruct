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

import json
import time
from pathlib import Path

import numpy as np
from scipy.optimize import differential_evolution

import examples.manual_qe.ti3c2_o_her_qe_active_inverse as oracle
from actistruct.gnn.config import GNNConfig
from actistruct.gnn.surrogate import HybridGPSurrogate

SEED_POINTS = list(oracle.CONFIG.initial_points)

MAX_ITERATIONS = 5
KAPPA = 1.0
RANDOM_STATE = 42
FIDELITY_LABEL = "lf" if oracle.FIDELITY == "low" else "hf"
CAMPAIGN_LOG = oracle.ROOT / "outputs" / "campaigns" / f"ti3c2_o_{FIDELITY_LABEL}_campaign.jsonl"


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


class RandomTrack:
    name = "random"

    def __init__(self, points, deltas, random_state: int = RANDOM_STATE):
        self.points = list(points)
        self.deltas = list(deltas)
        self.rng = np.random.default_rng(random_state)

    def propose(self) -> tuple[tuple[float, float], None, None, None]:
        for _ in range(10_000):
            u, v = map(float, self.rng.random(2))
            if oracle.is_new((u, v), self.points):
                return (u, v), None, None, None
        raise RuntimeError("RandomTrack could not find a non-duplicate candidate.")

    def add_point(self, u: float, v: float, dg: float) -> None:
        self.points.append((u, v))
        self.deltas.append(dg)


def _cache_hit_before_compute(u: float, v: float) -> bool:
    return oracle.cache_get(oracle.delta_g_cache_key((u, v))) is not None


def append_campaign_record(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")


def build_campaign_record(
    *,
    iteration: int,
    track_name: str,
    u: float,
    v: float,
    pred_mean: float | None,
    pred_std: float | None,
    acquisition_score: float | None,
    status: str,
    new_dft_call: bool,
    cache_hit: bool,
    duplicate: bool,
    delta_g_h: float | None,
    best_delta_g_h: float | None,
    n_points: int,
    wall_s: float,
) -> dict:
    return {
        "track": track_name,
        "iteration": int(iteration),
        "u": float(u),
        "v": float(v),
        "pred_mean_delta_g_h": None if pred_mean is None else float(pred_mean),
        "pred_std": None if pred_std is None else float(pred_std),
        "acquisition_score": None if acquisition_score is None else float(acquisition_score),
        "status": status,
        "new_dft_call": bool(new_dft_call),
        "cache_hit": bool(cache_hit),
        "duplicate": bool(duplicate),
        "delta_g_h": None if delta_g_h is None else float(delta_g_h),
        "abs_delta_g_h": None if delta_g_h is None else abs(float(delta_g_h)),
        "best_delta_g_h": None if best_delta_g_h is None else float(best_delta_g_h),
        "best_abs_delta_g_h": None if best_delta_g_h is None else abs(float(best_delta_g_h)),
        "n_points": int(n_points),
        "wall_s": float(wall_s),
    }


def propose_next(track, seed: int) -> tuple[tuple[float, float], float | None, float | None, float | None]:
    if hasattr(track, "propose"):
        return track.propose()

    def lcb(x: np.ndarray) -> float:
        mean, std = track.predict(float(x[0]) % 1.0, float(x[1]) % 1.0)
        return thermoneutral_lcb(mean, std)

    result = differential_evolution(
        lcb, [(0.0, 1.0), (0.0, 1.0)], seed=seed, maxiter=200, tol=1e-6, polish=True,
    )
    u, v = float(result.x[0]) % 1.0, float(result.x[1]) % 1.0
    mean, std = track.predict(u, v)
    return (u, v), mean, std, thermoneutral_lcb(mean, std)


def run() -> list[dict]:
    points, deltas, e_slab, e_h2 = _seed_data()
    print(f"Seed dataset: {len(points)} points, DeltaG_H range "
          f"[{min(deltas):.4f}, {max(deltas):.4f}] eV", flush=True)

    tracks = [
        GNNTrack(points, deltas, e_slab, e_h2),
        PlainGPTrack(points, deltas),
        RandomTrack(points, deltas),
    ]
    log: list[dict] = []

    for iteration in range(1, MAX_ITERATIONS + 1):
        for track in tracks:
            t0 = time.time()
            (u, v), pred_mean, pred_std, score = propose_next(track, seed=RANDOM_STATE + iteration)
            is_new_point = oracle.is_new((u, v), track.points)
            cache_hit = _cache_hit_before_compute(u, v)
            new_dft_call = is_new_point and not cache_hit
            dg = oracle.compute_delta_g_h((u, v), retries=oracle.CONFIG.retries)
            wall = time.time() - t0
            if dg is None:
                row = build_campaign_record(
                    iteration=iteration, track_name=track.name, u=u, v=v,
                    pred_mean=pred_mean, pred_std=pred_std, acquisition_score=score,
                    status="failed", new_dft_call=new_dft_call,
                    cache_hit=cache_hit, duplicate=not is_new_point,
                    delta_g_h=None, best_delta_g_h=None,
                    n_points=len(track.points), wall_s=wall,
                )
                log.append(row)
                append_campaign_record(CAMPAIGN_LOG, row)
                print(f"[{track.name} it{iteration}] DFT failed at ({u:.4f},{v:.4f}), skipping.", flush=True)
                continue
            track.add_point(u, v, dg)
            best = best_thermoneutral_delta(track.deltas)
            row = build_campaign_record(
                iteration=iteration, track_name=track.name, u=u, v=v,
                pred_mean=pred_mean, pred_std=pred_std, acquisition_score=score,
                status="success", new_dft_call=new_dft_call,
                cache_hit=cache_hit, duplicate=not is_new_point,
                delta_g_h=dg, best_delta_g_h=best,
                n_points=len(track.points), wall_s=wall,
            )
            log.append(row)
            append_campaign_record(CAMPAIGN_LOG, row)
            pred_text = (
                "random"
                if pred_mean is None or pred_std is None
                else f"{pred_mean:.4f}+/-{pred_std:.4f}"
            )
            print(
                f"[{track.name} it{iteration}] u={u:.4f} v={v:.4f} "
                f"DeltaG_H={dg:.4f} (pred={pred_text}) "
                f"best_abs={abs(best):.4f} n={len(track.points)} wall={wall/60:.1f}min "
                f"{'(new DFT call)' if new_dft_call else '(cache hit or duplicate)'}",
                flush=True,
            )

    print("\n=== AL LOOP SUMMARY ===", flush=True)
    for row in log:
        print(row, flush=True)
    return log


if __name__ == "__main__":
    run()
