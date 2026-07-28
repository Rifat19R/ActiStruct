"""Amendment 5 re-run: PlainGPTrack only, with the periodic-kernel fix.

The completed 3-track campaign (docs/TI3C2O_LF_CAMPAIGN_RESULTS.md) found
plain-GP's raw-(u,v) RBF kernel was blind to the periodic domain, causing it
to propose a near-duplicate of the atop-O seed in all 5 iterations and make
zero new discoveries (see docs/BENCHMARK_PROTOCOL.md Amendment 5 for the root
cause and the fix -- GPModel now fits on periodic (sin/cos) features).

GNN and random tracks are untouched by this bug (neither uses GPModel) and
are NOT re-run here -- their results from the completed campaign stand.

Logs to a separate evidence file (not the original campaign log) so the
pre-fix and post-fix plain-GP data stay distinguishable, per this project's
own reporting convention of dated, evidence-cited amendments.

Run:
    python -m examples.manual_qe.rerun_plain_gp_track
"""
from __future__ import annotations

import time

import examples.manual_qe.ti3c2_o_her_qe_active_inverse as oracle
from examples.manual_qe.run_ti3c2_o_al_loop import (
    MAX_ITERATIONS,
    RANDOM_STATE,
    PlainGPTrack,
    _seed_data,
    append_campaign_record,
    build_campaign_record,
    best_thermoneutral_delta,
    propose_next,
)

RERUN_LOG = oracle.ROOT / "outputs" / "campaigns" / "ti3c2_o_lf_campaign_plain_gp_rerun_amend5.jsonl"


def run() -> list[dict]:
    points, deltas, _e_slab, _e_h2 = _seed_data()
    print(f"Seed dataset: {len(points)} points, DeltaG_H range "
          f"[{min(deltas):.4f}, {max(deltas):.4f}] eV", flush=True)

    track = PlainGPTrack(points, deltas)
    log: list[dict] = []
    track_query_count = 0
    physical_call_count = 0

    for iteration in range(1, MAX_ITERATIONS + 1):
        t0 = time.time()
        (u, v), pred_mean, pred_std, score = propose_next(track, seed=RANDOM_STATE + iteration)
        track_query_count += 1
        is_new_point = oracle.is_new((u, v), track.points)
        current_best = best_thermoneutral_delta(track.deltas)

        if not is_new_point:
            wall = time.time() - t0
            row = build_campaign_record(
                iteration=iteration, track_name="plain-GP-amend5", u=u, v=v,
                pred_mean=pred_mean, pred_std=pred_std, acquisition_score=score,
                status="duplicate", track_oracle_query=1, physical_new_dft_call=False,
                cache_hit=False, duplicate=True,
                delta_g_h=None, best_delta_g_h=current_best,
                n_points=len(track.points), wall_s=wall,
                cumulative_track_oracle_queries=track_query_count,
                cumulative_physical_new_dft_calls=physical_call_count,
            )
            log.append(row)
            append_campaign_record(RERUN_LOG, row)
            print(f"[plain-GP-amend5 it{iteration}] duplicate proposal at "
                  f"({u:.4f},{v:.4f}); not adding or retraining.", flush=True)
            continue

        cache_hit = oracle.cache_get(oracle.delta_g_cache_key((u, v))) is not None
        physical_new_dft_call = not cache_hit
        if physical_new_dft_call:
            physical_call_count += 1
        dg = oracle.compute_delta_g_h((u, v), retries=oracle.CONFIG.retries)
        wall = time.time() - t0

        if dg is None:
            row = build_campaign_record(
                iteration=iteration, track_name="plain-GP-amend5", u=u, v=v,
                pred_mean=pred_mean, pred_std=pred_std, acquisition_score=score,
                status="failed", track_oracle_query=1,
                physical_new_dft_call=physical_new_dft_call, cache_hit=cache_hit,
                duplicate=False, delta_g_h=None, best_delta_g_h=current_best,
                n_points=len(track.points), wall_s=wall,
                cumulative_track_oracle_queries=track_query_count,
                cumulative_physical_new_dft_calls=physical_call_count,
            )
            log.append(row)
            append_campaign_record(RERUN_LOG, row)
            print(f"[plain-GP-amend5 it{iteration}] DFT failed at ({u:.4f},{v:.4f}), skipping.", flush=True)
            continue

        track.add_point(u, v, dg)
        best = best_thermoneutral_delta(track.deltas)
        row = build_campaign_record(
            iteration=iteration, track_name="plain-GP-amend5", u=u, v=v,
            pred_mean=pred_mean, pred_std=pred_std, acquisition_score=score,
            status="success", track_oracle_query=1,
            physical_new_dft_call=physical_new_dft_call, cache_hit=cache_hit,
            duplicate=False, delta_g_h=dg, best_delta_g_h=best,
            n_points=len(track.points), wall_s=wall,
            cumulative_track_oracle_queries=track_query_count,
            cumulative_physical_new_dft_calls=physical_call_count,
        )
        log.append(row)
        append_campaign_record(RERUN_LOG, row)
        print(
            f"[plain-GP-amend5 it{iteration}] u={u:.4f} v={v:.4f} "
            f"DeltaG_H={dg:.4f} (pred={pred_mean:.4f}+/-{pred_std:.4f}) "
            f"best_abs={abs(best):.4f} n={len(track.points)} wall={wall/60:.1f}min "
            f"{'(physical DFT call)' if physical_new_dft_call else '(cache hit)'}",
            flush=True,
        )

    print("\n=== PLAIN-GP AMEND5 RERUN SUMMARY ===", flush=True)
    for row in log:
        print(row, flush=True)
    return log


if __name__ == "__main__":
    run()
