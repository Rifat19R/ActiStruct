# Frozen LF Benchmark Protocol

Status: amended before live low-fidelity campaign.

Date frozen: 2026-07-16.

This protocol defines the next live ActiStruct campaign: low-fidelity Quantum
ESPRESSO active learning for H adsorption on Ti3C2-O. It is separate from the
TMC Reliability Benchmark v1.0, which is a molecular QE-record benchmark.

After live results exist, protocol changes require a dated amendment in this
file. Do not change acquisition settings, baselines, metrics, or stopping rules
after seeing results without recording the reason.

## Objective

Minimize the HER thermoneutrality score

```text
DeltaG_H = E_H_on_slab - E_slab - 0.5 * E_H2 + 0.04 eV
J(u, v) = |DeltaG_H(u, v)|
```

where the `+0.04 eV` term is the approximate HER ZPE/entropy correction already
used in `examples/manual_qe/ti3c2_o_her_qe_active_inverse.py`. This is a
screening descriptor, not a full free-energy calculation.

The target is a site with `DeltaG_H` close to 0 eV. The campaign therefore
minimizes `J = |DeltaG_H|`, not raw `DeltaG_H`. Strongly negative adsorption is
not treated as better than near-thermoneutral adsorption.

## System

- Surface: Ti3C2-O 2x2 slab.
- Structure source: `data/structures/ti3c2_o/ti3c2_o_slab_relaxed.traj` when
  present; otherwise `data/structures/ti3c2_o/ti3c2_o_slab.traj`.
- Adsorbate: one H atom at fractional in-plane coordinates `(u, v)`.
- H lateral position: fixed with `FixedLine` so only z relaxes.
- Slab relaxation: bottom three detected layers fixed; top slab layers and H
  relax during BFGS.
- BFGS settings: `fmax=0.05 eV/A`, `steps=50`.
- BFGS must report convergence. A relaxation that reaches the step limit
  without the frozen force threshold is a failed candidate and must not be
  cached as a successful `DeltaG_H`.

## Low-Fidelity DFT Settings

These settings are frozen for the live LF campaign.

| Setting | Value |
|---|---|
| `FIDELITY` | `low` |
| `ecutwfc` | `40 Ry` |
| `ecutrho` | `320 Ry` |
| slab k-points | `(3, 3, 1)` |
| H2 k-points | `(1, 1, 1)` |
| smearing | Marzari-Vanderbilt |
| `degauss` | `0.02` |
| `conv_thr` | `1e-8` |
| `electron_maxstep` | `300` |
| `mixing_beta` | `0.2` |
| QE scratch | `/tmp/qe_scratch` unless `QE_SCRATCH_ROOT` is set |
| default MPI ranks | `QE_NPROCS=2` |
| retries | `2` retries after the first failed attempt |
| cache namespace | `outputs/cache/ti3c2_o_her_low_protocol_v1_amend1.pkl` |

Pseudopotentials are SSSP 1.3.0 PBE efficiency:

- Ti: `ti_pbe_v1.4.uspp.F.UPF`
- C: `C.pbe-n-kjpaw_psl.1.0.0.UPF`
- O: `O.pbe-n-kjpaw_psl.0.1.UPF`
- H: `H.pbe-rrkjus_psl.1.0.0.UPF`

Required environment variables:

```bash
export FIDELITY=low
export ESPRESSO_PW=/path/to/pw.x
export ESPRESSO_PSEUDO=/path/to/SSSP_1.3.0_PBE_efficiency
export QE_SCRATCH_ROOT=/tmp/qe_scratch
export QE_NPROCS=2
```

## Seed Dataset

The frozen seed set for the AL driver is six distinct-site points:

| Label | `(u, v)` | Role |
|---|---:|---|
| atop-O | `(0.000000, 0.000000)` | atop O reference |
| atop-Ti | `(0.333333, 0.166667)` | outer Ti column |
| atop-C | `(0.166667, 0.333333)` | C column |
| hollow | `(0.083333, 0.166667)` | balanced hollow |
| O-O bridge | `(0.250000, 0.000000)` | bridge site |
| intermediate | `(0.125000, 0.125000)` | partial O-proximity site |

Five preliminary development-site calculations were completed before this
protocol, but they were superseded after symmetry aliasing and lateral
adsorbate migration were identified. The frozen six-point distinct-site seed
campaign has not yet been completed unless the cache contains all six values
under the current low-fidelity settings. If any seed value is missing from
cache, run the grid/seed campaign before the AL loop. Do not replace seed
points after inspecting results unless this file gets a dated protocol
amendment.

Seed coordinates are exact. The seed/grid campaign must not perturb failed
seeds to nearby `(u, v)` points. If an exact frozen seed fails, retain the
failure evidence and stop rather than silently substituting a nearby coordinate.

## Acquisition

Use the existing three-track driver:

```bash
python -m examples.manual_qe.run_ti3c2_o_al_loop
```

Frozen acquisition settings:

- Tracks: frozen SchNet embedding + GP (`GNNTrack`), direct `(u, v)` GP
  (`PlainGPTrack`), and deterministic random baseline (`RandomTrack`).
- Acquisition for GP tracks: thermoneutral Lower Confidence Bound,
  `score = |mean DeltaG_H| - kappa * std`.
- Acquisition for random baseline: deterministic random proposal from
  `random_state=42`, using the same duplicate tolerance and oracle path.
- `kappa = 1.0`.
- Optimizer: `scipy.optimize.differential_evolution`.
- Bounds: `(u, v) in [0, 1] x [0, 1]`, wrapped modulo 1.
- `RANDOM_STATE = 42`.
- DE settings in the three-track campaign driver: `maxiter=200`, `tol=1e-6`,
  `polish=True`.
- Budget: `5` AL iterations per track after the six seed points.

Cache hits are allowed and must be reported as cache hits. A cache hit is not a
new physical DFT call. Duplicate or near-duplicate proposals must be counted in
the duplicate metric rather than silently hidden. Duplicate proposals consume
the track's iteration, but must not be added to that track's training data and
must not trigger retraining.

Every proposal has two separate accounting dimensions:

- `track_oracle_query`: the algorithm asked the oracle for one label.
- `physical_new_dft_call`: the label required a new physical QE calculation.

Algorithm comparisons use cumulative `track_oracle_query`. Computational-cost
comparisons use cumulative `physical_new_dft_call`.

## Baselines

Report all baselines under the same data budget and seed set.

| Baseline | Status | Claim allowed before run |
|---|---|---|
| Random selection over `(u, v)` | required | none |
| Direct GP on raw `(u, v)` | implemented as `PlainGPTrack` | workflow only |
| Frozen SchNet embedding + GP | implemented as `GNNTrack` | workflow only |
| Descriptor GP | allowed comparison if implemented before campaign | none until run |
| Failure-aware acquisition | allowed comparison if live failure risk is wired in | none until run |

The report must not claim that the GNN track is superior unless it beats the
baselines under the frozen metrics and budget.

## Metrics

Report these metrics for every track:

- best observed `|DeltaG_H|` by DFT-call count
- `|DeltaG_H|` of the best observed site
- simple regret relative to the best LF value observed within the same frozen
  campaign budget
- number of track oracle queries
- number of physical new DFT calls
- number of cache hits
- number of failed QE attempts and skipped candidates
- duplicate or near-duplicate proposals
- wall-clock time per accepted candidate and total wall-clock time
- retrospective uncertainty calibration where enough held-out data exist

The primary algorithm plot is best observed `|DeltaG_H|` vs cumulative track
oracle queries. A second cost plot must show best observed `|DeltaG_H|` vs
cumulative physical new DFT calls.

## Stopping Rule

For the three-track campaign driver, run all five AL iterations per track unless
one of these hard stops occurs:

- two consecutive QE infrastructure failures prevent all tracks from acquiring
  a value
- no non-duplicate candidate can be proposed under the frozen duplicate
  tolerance
- the user explicitly stops the job for hardware, power, or storage reasons

Do not stop early because the result looks good.

The older single-track oracle has an internal convergence rule based on
uncertainty and predicted improvement. That rule is not the success criterion
for this frozen three-track benchmark unless the single-track script is used in
a separately dated amendment.

## Failure Handling

- Keep all failed attempts in the raw output or ledger location; do not delete
  failures to make the campaign look cleaner.
- `compute_delta_g_h()` retries each point with `CONFIG.retries=2`.
- A point returning `None` is a skipped candidate and must be counted.
- A BFGS relaxation with `converged=false` is a failed candidate. It must not
  be cached as a successful adsorption energy.
- Each QE working directory writes `run_metadata.json` with convergence status,
  BFGS step count, final max force, trajectory path, final energy if valid, and
  raw QE output hash when available.
- H2 reference calculations use the same metadata-writing path as clean-slab
  and slab+H calculations. H2 metadata must include the campaign fingerprint,
  active pseudopotential hash, input settings, total energy, and QE output hash.
- A fallback energy parsed from raw QE output is valid only when the output
  contains `JOB DONE` and does not contain `convergence NOT achieved`.
  Interrupted outputs with intermediate total-energy lines are failures.
- QE scratch must remain on the Linux filesystem, not `/mnt/d`, to avoid NTFS
  scratch corruption.
- If the process is interrupted, resume with the same command and cache. Record
  that the campaign was resumed.

## Reproduction Commands

Seed/grid campaign if a seed value is missing:

```bash
cd /mnt/d/Research/Dr.Kulik_MIT
source .venv/bin/activate
FIDELITY=low python -m examples.manual_qe.run_ti3c2_o_grid_campaign
```

Frozen three-track AL campaign:

```bash
cd /mnt/d/Research/Dr.Kulik_MIT
source .venv/bin/activate
FIDELITY=low python -m examples.manual_qe.run_ti3c2_o_al_loop
```

Monitor cache/report outputs:

```bash
tail -f outputs/campaigns/ti3c2_o_lf_campaign.jsonl
ls -lh outputs/cache/ti3c2_o_her_low_protocol_v1_amend1.pkl
```

## Reporting Rule

Every public statement from this campaign must name the evidence file and the
command used to produce it. Allowed language before the run is limited to:

> The LF campaign protocol is frozen and ready to run.

After the run, claims must be restricted to what the frozen metrics support.

## Known Limitations

- The `+0.04 eV` term is an approximate HER correction; vibrational free-energy
  calculations are not part of this LF campaign.
- Low fidelity does not replace the deferred high-fidelity validation.
- The current three-track GNN path pretrains and fits on LF data only; it is
  not a true LF/HF transfer result.
- The structures fed to the GNN use nominal H placement on the clean slab, not
  archived final relaxed adsorbate geometries for every site.
- A live LF win does not prove general predictive performance outside this
  system or acquisition budget.

## Evidence File

The live campaign driver appends every successful, failed, duplicate, and
cached proposal to:

```text
outputs/campaigns/ti3c2_o_lf_campaign.jsonl
```

Each row records track, iteration, proposal coordinates, prediction fields
where available, thermoneutral acquisition score, status, track oracle query,
physical new DFT call flag, cumulative query/cost counts, cache hit, duplicate
flag, `DeltaG_H`, `|DeltaG_H|`, current best `|DeltaG_H|`, point count, and wall
time. Failed rows retain the current best value from before the failure.

## Amendments

### Amendment 1 -- Pre-run Scientific Correction

Date: 2026-07-16.

Before any frozen-campaign result was generated, the objective was corrected
from minimization of raw `DeltaG_H` to minimization of `|DeltaG_H|`, consistent
with HER thermoneutrality. The GP acquisition is now a thermoneutral-LCB
heuristic: `|mean DeltaG_H| - kappa * std`. No live frozen-campaign result was
inspected before this amendment.

This amendment also records the deterministic random baseline and JSONL
proposal persistence required by the original protocol metrics.

### Amendment 2 -- Pre-run Provenance and Convergence Correction

Date: 2026-07-16.

Before any frozen-campaign result was generated, the campaign was moved into a
protocol-specific cache namespace:

```text
outputs/cache/ti3c2_o_her_low_protocol_v1_amend1.pkl
```

Cache keys now include the protocol ID, code commit, slab SHA-256,
pseudopotential SHA-256 values, fixed-line constraint, H initial height, BFGS
threshold and step limit, electronic settings, cutoffs, and k-points. Exact
frozen seed coordinates are required; nearby fallback seed substitutions are
not allowed. BFGS non-convergence is treated as failure and is not cached as a
successful `DeltaG_H`.

### Amendment 3 -- Pre-run QE Completion and H2 Metadata Check

Date: 2026-07-16.

Before any frozen-campaign result was generated, H2 reference calculations were
moved through the same `run_energy()` metadata path used for slab calculations.
QE fallback energy parsing now requires a complete `JOB DONE` output and
rejects `convergence NOT achieved`; intermediate total-energy lines from
incomplete outputs are not accepted as evidence.
