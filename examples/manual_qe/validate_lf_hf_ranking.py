"""HF validation on representative sites (docs/FEATURE_FREEZE.md Priority 5).

Not a full HF re-run of the LF campaign (prohibitively expensive: ~3.4x the
plane-wave cutoff cost plus a denser 6x6x1 vs 3x3x1 k-point grid per site,
on top of LF sites that already took 4-20 hours each). Instead: three
representative (u,v) points spanning the full range the LF campaign
observed, to check whether HF preserves the LF ranking -- the actual
question docs/FEATURE_FREEZE.md's Priority 5 asks.

Sites chosen (real LF results, docs/TI3C2O_LF_CAMPAIGN_RESULTS.md):
  - (0.0479, 0.7894): the campaign's best find, LF DeltaG_H = +0.0020 eV
    (near-thermoneutral) -- the headline result; most important to validate.
  - (0.0, 0.0): atop-O seed, LF DeltaG_H = -0.7582 eV (strongly favorable).
  - (1.0/3.0, 1.0/6.0): atop-Ti seed, LF DeltaG_H = +2.4752 eV (strongly
    unfavorable).

Run:
    FIDELITY=high python -m examples.manual_qe.validate_lf_hf_ranking
"""
from __future__ import annotations

import json
import time

import examples.manual_qe.ti3c2_o_her_qe_active_inverse as oracle

SITES = [
    ("plain-GP best (LF)", (0.047890530279769736, 0.7893557062837071), 0.0019544716756589517),
    ("atop-O seed", (0.0, 0.0), -0.7582154009164279),
    ("atop-Ti seed", (1.0 / 3.0, 1.0 / 6.0), 2.475156334142908),
]

RESULTS_LOG = oracle.ROOT / "outputs" / "campaigns" / "ti3c2_o_hf_ranking_validation.jsonl"


def main() -> None:
    if oracle.FIDELITY != "high":
        raise RuntimeError(f"Run with FIDELITY=high, got FIDELITY={oracle.FIDELITY!r}")
    oracle.ensure_environment()

    print(f"HF settings: ecutwfc={oracle.ECUTWFC} ecutrho={oracle.ECUTRHO} kpts={oracle.KPTS_SLAB}", flush=True)
    e_slab = oracle.get_clean_slab_energy(retries=oracle.CONFIG.retries)
    print(f"HF clean slab energy: {e_slab:.8f} eV", flush=True)
    e_h2 = oracle.get_h2_energy(retries=oracle.CONFIG.retries)
    print(f"HF H2 energy: {e_h2:.8f} eV", flush=True)

    rows = []
    for label, (u, v), lf_dg in SITES:
        t0 = time.time()
        hf_dg = oracle.compute_delta_g_h((u, v), retries=oracle.CONFIG.retries)
        wall = time.time() - t0
        row = {
            "label": label, "u": u, "v": v,
            "lf_delta_g_h": lf_dg, "hf_delta_g_h": hf_dg,
            "wall_s": wall, "status": "success" if hf_dg is not None else "failed",
        }
        rows.append(row)
        RESULTS_LOG.parent.mkdir(parents=True, exist_ok=True)
        with RESULTS_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, sort_keys=True) + "\n")
        print(
            f"[{label}] ({u:.4f},{v:.4f}) LF={lf_dg:.4f} HF={hf_dg} wall={wall/60:.1f}min",
            flush=True,
        )

    print("\n=== HF RANKING VALIDATION SUMMARY ===", flush=True)
    lf_order = sorted(rows, key=lambda r: r["lf_delta_g_h"])
    hf_rows = [r for r in rows if r["hf_delta_g_h"] is not None]
    hf_order = sorted(hf_rows, key=lambda r: r["hf_delta_g_h"])
    print("LF order (most negative first):", [r["label"] for r in lf_order], flush=True)
    print("HF order (most negative first):", [r["label"] for r in hf_order], flush=True)
    rank_preserved = [r["label"] for r in lf_order if r in hf_rows] == [r["label"] for r in hf_order]
    print(f"Ranking preserved: {rank_preserved}", flush=True)
    for row in rows:
        print(row, flush=True)


if __name__ == "__main__":
    main()
