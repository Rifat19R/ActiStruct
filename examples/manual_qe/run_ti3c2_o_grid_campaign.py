"""Phase 2 driver: real DFT seed campaign at the oracle's 6 seed (u,v) sites.

Reuses ti3c2_o_her_qe_active_inverse.py's own initial-labeling loop (same
logic as main(), lines computing the initial training set) but stops there --
deliberately not entering the active-learning iteration loop, so Phase 2
(grid campaign) and Phase 3 (AL loop closure) stay reportable as separate,
gated steps.

CONFIG.initial_points defines the frozen six-site seed set used by the AL
driver: atop-O, atop-Ti, atop-C, hollow, O-O bridge, and an intermediate site.
This script must be run before the AL loop if any seed value is missing from
cache.

Run:
    python -m examples.manual_qe.run_ti3c2_o_grid_campaign
"""
from __future__ import annotations

import time

import examples.manual_qe.ti3c2_o_her_qe_active_inverse as oracle


def main() -> None:
    oracle.ensure_environment()
    print(f"Slab: {oracle.SLAB_LABEL}  ({oracle.SLAB_TRAJ})", flush=True)

    labeled_points: list[tuple[float, float]] = []
    labeled_values: list[float] = []
    site_log: list[dict] = []

    for site_idx, (base_u, base_v) in enumerate(oracle.CONFIG.initial_points):
        t0 = time.time()
        status = "FAILED"
        dg = None
        used_point = None
        for du, dv in [(0.0, 0.0), (0.02, 0.0), (-0.02, 0.0), (0.0, 0.02)]:
            trial = ((base_u + du) % 1.0, (base_v + dv) % 1.0)
            if not oracle.is_new(trial, labeled_points):
                continue
            dg = oracle.compute_delta_g_h(trial, retries=oracle.CONFIG.retries)
            if dg is None:
                continue
            labeled_points.append(trial)
            labeled_values.append(dg)
            used_point = trial
            status = "JOB DONE"
            break
        wall = time.time() - t0
        site_log.append({
            "site_idx": site_idx, "base": (base_u, base_v), "used_point": used_point,
            "delta_g_h": dg, "status": status, "wall_s": wall,
        })
        print(
            f"[site {site_idx}] base=({base_u:.4f},{base_v:.4f}) "
            f"used={used_point} status={status} "
            f"DeltaG_H={dg if dg is not None else 'N/A'} "
            f"wall={wall/60:.1f} min",
            flush=True,
        )

    print("\n=== GRID CAMPAIGN SUMMARY ===", flush=True)
    for row in site_log:
        print(row, flush=True)
    n_ok = sum(1 for r in site_log if r["status"] == "JOB DONE")
    print(f"\n{n_ok}/{len(site_log)} sites completed.", flush=True)
    if n_ok < len(site_log):
        raise RuntimeError(f"Only {n_ok}/{len(site_log)} sites succeeded -- see per-site log above.")


if __name__ == "__main__":
    main()
