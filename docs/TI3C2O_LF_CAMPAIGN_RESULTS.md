# Ti3C2-O LF Campaign Results

**Protocol:** `docs/BENCHMARK_PROTOCOL.md` (frozen 2026-07-16, amended through Amendment 4, 2026-07-22).
**Evidence file:** `outputs/campaigns/ti3c2_o_lf_campaign.jsonl` (15 rows, one per track-query).
**Commands used:**
```bash
FIDELITY=low python -m examples.manual_qe.run_ti3c2_o_grid_campaign   # 6/6 seeds, all cache hits
FIDELITY=low python -m examples.manual_qe.run_ti3c2_o_al_loop         # 5 iterations x 3 tracks
```
**Cache:** `outputs/cache/ti3c2_o_her_low_protocol_v1_amend1.pkl`.

## Seed dataset

6/6 frozen seeds present, all real DFT, `DeltaG_H` range `[-0.7582, 2.4752]` eV. Best seed by `|DeltaG_H|`: hollow site, `0.4773` eV.

## Per-track results (5 iterations each, real DFT)

| Track | Queries | Physical DFT calls | Cache hits | Duplicates | Failed | Wall time (physical only) |
|---|---:|---:|---:|---:|---:|---:|
| GNN | 5 | 4 | 1 | 0 | 0 | 58.7 h |
| plain-GP | 5 | 0 | 0 | 5 | 0 | ~0 h |
| random | 5 | 5 | 0 | 0 | 1 | 88.8 h |

Total physical DFT calls across all tracks: **9**. Total campaign wall time: **~147.5 h (~6.1 days)**.

### New real discoveries made during this run (excludes seed/cache carryover)

| Track | New `DeltaG_H` values (eV) | Best new `\|DeltaG_H\|` |
|---|---|---:|
| GNN | -0.7405, -0.0672, -0.2236, -0.6193 | 0.0672 |
| plain-GP | (none -- every proposal was a duplicate) | -- |
| random | 2.4873, -0.5835, -0.0239, -0.4096 | **0.0239** |

### Final best `\|DeltaG_H\|` per track (including seed/cache carryover)

| Track | Final best `\|DeltaG_H\|` | Source |
|---|---:|---|
| GNN | 0.0004 | Iteration 1 was a **cache hit** at (0.2242, 0.5071) -- this exact point and value were already computed and cached before this run (see note below), not a new discovery made during this campaign. |
| plain-GP | 0.4773 | Unchanged from the seed set (hollow site); the track never added a single new point. |
| random | 0.0239 | A genuine new discovery, iteration 4, real DFT. |

**Note on GNN's cache hit:** (0.2242, 0.5071) -> -0.0004 eV is real, previously-computed DFT data (from earlier work on this same campaign, before this protocol was frozen and reconciled), not fabricated. It is reported here because the protocol requires cache hits be counted and reported, not hidden. But crediting the GNN track with this result as evidence of *this run's* active learning would overstate what the live campaign demonstrated: excluding that carryover, GNN's own new proposals in this run found nothing better than 0.0672 eV.

## Observed failure: plain-GP track never explored

Every one of plain-GP's 5 proposals landed within `duplicate_tol` of the same near-boundary point (`u,v` near `(1.0, 1.0)`, equivalent to the atop-O seed at `(0.0, 0.0)` after periodic wrapping). The thermoneutral-LCB acquisition on a plain 2D `(u,v)` RBF kernel converged to a single strong local exploitation point and never moved off it across all 5 iterations -- a real limitation of this track under this seed set and acquisition budget, not a bug in the duplicate-rejection logic (which worked correctly: it is exactly why plain-GP made zero new physical DFT calls instead of recomputing the same site 5 times).

## Observed failure: random iteration 1 did not converge

`(0.7740, 0.4389)` failed all 3 allowed attempts -- BFGS hit the 50-step limit without reaching `fmax=0.05 eV/A` (final forces 1.21, 1.38, 1.29 eV/A across the 3 attempts). Recorded as a failed candidate per protocol; not cached as a successful `DeltaG_H`, best value carried forward unchanged.

## Verdict

None of the plan's three pre-specified decision-rule outcomes (GNN wins by >25% fewer calls / GNN and plain-GP roughly tied / GNN underperforms plain-GP) cleanly describes what happened, because plain-GP did not meaningfully compete -- it got stuck re-proposing a duplicate of an already-known site every single iteration and made zero new discoveries. The actual, honest result:

- **The random baseline outperformed both engineered surrogates** in new discoveries made during this specific campaign: its best new find (0.0239 eV) beat GNN's best new find (0.0672 eV), and easily beat plain-GP's (none).
- **GNN explored but did not improve on already-known data** in this run; its reported "best" result is a real but pre-existing value, not a product of this campaign's active learning.
- **plain-GP, as configured (raw 2D coordinates, thermoneutral-LCB, this seed set), did not function as an active learner in this run** -- it exploited a single point repeatedly instead of exploring.

**Recommendation, consistent with the plan's "never claim discovery, only report honestly" standard:** do not claim GNN-forward or GP-forward superiority from this single-system, single-budget run. If anything, this result argues for investigating *why* plain-GP collapsed to one exploitation point (kernel length-scale/acquisition interaction with this seed set is the leading suspect) before drawing any comparative conclusion, and for not treating a single frozen-budget campaign as evidence of general active-learning benefit over random search here.

## Known limitations (carried from `docs/BENCHMARK_PROTOCOL.md`)

- LF only; HF validation deferred.
- GNN pretrain/fit both use the same LF-only dataset, not a true LF/HF transfer split.
- GNN-embedded structures use nominal (u,v) placement on the relaxed clean slab, not each site's archived final relaxed geometry (not retained -- see `docs/BENCHMARK_PROTOCOL.md` provenance notes).
- `+0.04 eV` is an approximate HER ZPE/entropy correction, not a full vibrational free-energy calculation. `0.0004 eV` and `0.0239 eV` are "near-thermoneutral within the resolution of this LF screening protocol," not citation-grade precision claims.
