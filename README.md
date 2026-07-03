# ActiStruct

ActiStruct is an **active-learning workflow for DFT-guided materials discovery**
that combines a GNN-pretrained surrogate, a multi-fidelity oracle, and an
autonomous QE fault-recovery engine. It does not replace Quantum ESPRESSO
(QE/PBE) calculations — it learns from completed QE runs (including failures)
to decide which candidate structures are worth computing next.

```text
GNN encodes. GP ranks by uncertainty. Debug engine recovers. QE/PBE validates.
```

**Current release: v2.0** — `pytest -q` passes **128 tests, 0 warnings**.
v2.0 adds a SchNet-style GNN encoder, a frozen-embedding GP surrogate
(`HybridGPSurrogate`), an autonomous QE fault-recovery engine, a Streamlit
monitoring dashboard, and the first real Phase 2 campaign oracle targeting
Ti3C2-O MXene for hydrogen evolution reaction (HER) screening.

## Topics

`inverse-design` `active-learning` `dft` `quantum-espresso` `ase`
`gaussian-process` `bayesian-optimization` `gnn` `schnet`
`materials-science` `mxene` `hydrogen-evolution` `multi-fidelity`
`atomistic-simulation` `reliability-aware-al`

---

## What v2.0 Adds

| Layer | v0.x (retained) | v2.0 (new) |
|---|---|---|
| Active-learning core | GP/LCB + failure-risk penalty | DE-based acquisition in 2D (u,v) space |
| Surrogate | Simple sklearn GP on raw descriptors | `HybridGPSurrogate`: GNN pretrain -> frozen embeddings -> GP |
| GNN encoder | None | `SchNetEncoder`: neighbor list + Gaussian RBF + message passing |
| DFT fault handling | Manual | `DFTFailureAnalyzer` + `TroubleshootingStrategy` + `run_dft_with_recovery()` |
| Campaign oracle | 50 generated bulk/surface scripts | Ti3C2-O HER: `DeltaG_H = E_slab+H - E_slab - 0.5*E_H2 + 0.04 eV` |
| Monitoring | None | 4-tab Streamlit dashboard + JSONL ledger |
| Test suite | 81 tests | 128 tests, 0 warnings |

---

## Architecture

```text
                     Low-Fidelity DFT (ecutwfc=40)
                              |
                    SchNetEncoder (pretrain)
                     cutoff=5.0 A, 3 message-passing blocks
                     Gaussian RBF, embedding_dim=64
                              |
                         FREEZE encoder
                              |
                     High-Fidelity DFT (ecutwfc=60)
                              |
                    HybridGPSurrogate.fit()
                     StandardScaler -> ConstantKernel*RBF
                     alpha=1e-4, 5 optimizer restarts
                              |
              ┌───────────────┴───────────────┐
           predict()                   predict_batch()
         (mean, std)                   (mean[], std[])
              |
    differential_evolution -> next (u,v) candidate
              |
    DFT oracle (with recovery)
    DFTFailureAnalyzer -> TroubleshootingStrategy
    run_dft_with_recovery() -> ledger append
```

The surrogate is **frozen-embedding transfer learning**, not Kennedy-O'Hagan
co-kriging. The LF encoder is pretrained once, frozen, and its embeddings
serve as features for the HF GP. This is a well-established transfer-learning
baseline and is named honestly throughout the code.

---

## Implemented Components

### Phase 0 — Ledger (`actistruct/core/`)

- **`atomic_cache.py`** — NTFS-safe atomic file cache using `O_CREAT | O_EXCL`
  locking (not `fcntl`/`flock`, which WSL2/NTFS does not support reliably).
- **`ledger.py`** — Append-only JSONL run ledger; one record per DFT attempt
  (converged or failed). Atomically locked during writes, safe under concurrent
  Pool workers.

### Phase 1 — Debug and Recovery Engine (`actistruct/debug/`)

- **`classifier.py` — `DFTFailureAnalyzer`**: Regex classifier for `pw.x`
  output. Four categories: `SUCCESS`, `SCF_CONVERGENCE`,
  `ELECTRONIC_INSTABILITY`, `GEOMETRY_CRASH`, `UNKNOWN`. All patterns
  verified against real QE 7.x `.pwo` output. `Broyden`/`linmin` intentionally
  excluded from `GEOMETRY_CRASH` (they appear in normal BFGS relaxation logs).
- **`strategies.py` — `TroubleshootingStrategy`**: Four cumulative escalation
  groups applied atomically per retry: (1) soften mixing, (2) Gaussian smearing
  + `degauss=0.02`, (3) Methfessel-Paxton + `degauss=0.03`, (4)
  `electron_maxstep=300`. Smearing method and `degauss` always change together
  (physically coupled). `nspin` is never touched automatically.
- **`recovery.py` — `run_dft_with_recovery()`**: Wraps a single static SCF
  call with automatic fault detection, escalation logging, and ledger append.
  Not adapted for ionic relaxation (use `restart_mode='restart'` manually).

### Phase 2 — GNN Surrogate (`actistruct/gnn/`)

- **`encoder.py` — `SchNetEncoder`**: Real geometry-aware message passing.
  Pairwise distances from `ase.neighborlist`, Gaussian RBF expansion,
  message-passing interaction block (`filter_ij = MLP(rbf(d_ij))`), mean-pool
  to fixed-size embedding. Identical composition + different bond lengths ->
  different embeddings (verified by test).
- **`surrogate.py` — `HybridGPSurrogate`**: (1) Pretrain encoder + energy head
  on LF energies with early stopping. (2) Freeze encoder. (3) StandardScaler
  on HF embeddings. (4) Fit `ConstantKernel * RBF` GP with fixed `alpha=1e-4`.
  `predict(atoms)` returns `(mean_eV/atom, uncertainty_eV/atom)` — drop-in for
  the existing `GPModel` interface in `qe_active_inverse_common.py`.
- **`config.py` — `GNNConfig` / `MultiFidelityConfig`**: Per-system cutoff
  guidance documented. Ti3C2-O default: `cutoff=5.0 A` (Ti-C ~2.1 A,
  Ti-O ~2.0 A; 5.0 A captures both bond shells with margin to distinguish
  hollow vs atop H adsorption sites).

### Phase 3 — Dashboard (`actistruct/dashboard/`)

- **`app.py`**: 4-tab Streamlit dashboard. Tab 1: campaign scorecard +
  convergence rate + failure breakdown. Tab 2: energy vs iteration + best
  candidate trajectory. Tab 3: 3D structure viewer (`py3Dmol`/`stmol`). Tab 4:
  full sortable/filterable run log. Multi-ledger support: one file per system,
  selectable from sidebar. Handles empty ledger gracefully.
- **`data_loader.py`**: `load_ledger()`, `load_multi_ledger()`,
  `get_summary_stats()`. Reads JSONL ledger into a pandas DataFrame.

Launch: `streamlit run actistruct/dashboard/app.py`

### Phase 2 Oracle — Ti3C2-O MXene HER (`examples/manual_qe/`)

**`ti3c2_o_her_qe_active_inverse.py`** — Full active-learning campaign oracle:

- `DeltaG_H = E(slab+H) - E(slab) - 0.5 * E(H2) + 0.04 eV`
  (Norskov ZPE-entropy correction, standard HER descriptor)
- Design variable: `(u, v)` in-plane fractional coordinates of adsorbed H
- `FIDELITY=low` (env var): `ecutwfc=40`, `ecutrho=320`, `kpts=(3,3,1)`
- `FIDELITY=high`: `ecutwfc=60`, `ecutrho=480`, `kpts=(6,6,1)`
- All energies cached per fidelity level; E_slab and E_H2 computed once and
  reused across all (u,v) evaluations
- Pseudopotentials: Ti(USPP) + C(PAW) + O(PAW) + H(USPP),
  SSSP 1.3.0 PBE efficiency
- Candidate acquisition via `differential_evolution` minimising LCB over (u,v)
- 2x2 Ti3C2-O supercell, 28 atoms; bottom-layer FixAtoms constraint

**LF static verified**: `E(clean slab) = -25973.017 eV`, JOB DONE, 1h43m wall
time, no augmentation-charge warnings (WSL2, mpirun -np 2).

### v0.x Reliability-Aware Layer (retained)

- **QE reliability parser** — `actistruct/parsers/qe.py`,
  `actistruct/datasets/qe_records.py`. Records both successful and failed QE
  runs. Failures are never discarded.
- **Reliability classifier (v0.3.2)** — `analysis/train_qe_reliability_classifier.py`.
  Predicts pre-run failure risk from setup-time features only (cutoffs,
  k-points, smearing, pseudopotential family, composition).
- **Failure-aware acquisition** — `actistruct/acquisition/reliability.py`.
  Soft triage penalty on GP/LCB scores; old LCB behavior preserved exactly
  when no risk estimate is available or `gamma=0`.
- **Offline benchmarks (v0.5.0/v0.5.1)** — Simulated, reproducible comparisons
  of candidate-selection policies using completed records; no new QE jobs
  launched.
- **50+ generated QE workflows** — `generated_models/`, covering bulk solids,
  2D materials, molecules, battery/perovskite systems, and surfaces.
- **Direct grid validation** — 4 systems (Cu FCC, MoS2, Si, MgO) validated
  against a 20-49 point DFT grid; max delta 0.00092 eV/atom vs AL result.

---

## Test Suite

**128 tests, 0 warnings** (Python 3.12, WSL2).

| Test file | Coverage |
|---|---|
| `test_hybrid_surrogate.py` | GNN geometry sensitivity, permutation invariance, fidelity config, overfit sanity, (u,v) UV design variable sensitivity (3 tests) |
| `test_debugging.py` | `DFTFailureAnalyzer` (5 failure types), `TroubleshootingStrategy` (4 groups), `run_dft_with_recovery()` |
| `test_dashboard.py` | Ledger loading, summary stats, multi-ledger root, empty-ledger safety |
| `test_ledger.py` | Append, concurrent writes, lock timeout, schema validation |
| `test_generated_workflows.py` | All `generated_models/*.py` import and define required attributes |
| `test_debugging.py`, `test_failure_aware_acquisition.py`, `test_qe_reliability_*` | v0.x reliability and acquisition layer |

```bash
pytest -q          # 128 passed, 0 warnings
```

---

## Repository Structure

```text
ActiStruct/
|-- demo_ti3c2_o.py                  # no-QE end-to-end demo (real Ti3C2-O slab)
|-- qe_active_inverse_common.py      # shared GP/LCB active-learning QE engine
|-- actistruct/
|   |-- core/
|   |   |-- atomic_cache.py          # NTFS-safe atomic file cache (O_CREAT|O_EXCL)
|   |   `-- ledger.py                # append-only JSONL run ledger
|   |-- debug/
|   |   |-- classifier.py            # DFTFailureAnalyzer (regex, 4 failure types)
|   |   |-- strategies.py            # TroubleshootingStrategy (4 escalation groups)
|   |   `-- recovery.py              # run_dft_with_recovery() wrapper
|   |-- gnn/
|   |   |-- config.py                # GNNConfig, MultiFidelityConfig
|   |   |-- encoder.py               # SchNetEncoder (geometry-aware message passing)
|   |   `-- surrogate.py             # HybridGPSurrogate (frozen-embedding + GP)
|   |-- dashboard/
|   |   |-- app.py                   # 4-tab Streamlit dashboard
|   |   `-- data_loader.py           # ledger -> DataFrame, summary stats
|   |-- acquisition/reliability.py   # failure-aware LCB acquisition scoring
|   |-- parsers/qe.py                # QE output parser (records failures too)
|   `-- datasets/qe_records.py       # dataset builder for parsed QE records
|-- examples/manual_qe/
|   |-- ti3c2_o_her_qe_active_inverse.py  # Ti3C2-O HER oracle (Phase 2)
|   `-- h_cu111_qe_active_inverse.py      # Cu(111) H adsorption (reference)
|-- generated_models/                # 50+ generated QE benchmark scripts
|-- tests/                           # pytest suite (128 tests, no QE/DFT launched)
|-- archive/caaln2_dropped/          # archived CaAlN2 candidate scripts
|-- analysis/                        # classifier training, offline benchmarks
|-- docs/                            # setup notes, parser/spec documentation
|-- reports/                         # reliability/acquisition/benchmark reports
|-- outputs/
|   |-- cache/                       # DFT energy caches (per fidelity level)
|   |-- reports/                     # campaign report text files
|   `-- plots/                       # convergence and energy landscape plots
|-- pseudo/README.md                 # pseudopotential notes
|-- requirements.txt
|-- pyproject.toml
|-- CHANGELOG.md
|-- CITATION.cff
`-- README.md
```

---

## Getting Started

### 1. Install

```bash
git clone https://github.com/Rifat19R/ActiStruct.git
cd ActiStruct

# WSL2 / Linux (recommended -- QE runs on Linux only)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e ".[test]"
```

Required packages: `numpy`, `scipy`, `matplotlib`, `scikit-learn`, `ase`,
`torch`, `plotly`, `streamlit`, `stmol`, `py3Dmol`.

### 2. Run the test suite

```bash
pytest -q          # 128 passed, 0 warnings — no QE/DFT launched
```

### 3. Run the no-QE demo (verifies full v2 stack)

```bash
python demo_ti3c2_o.py
```

Loads the real 28-atom Ti3C2-O slab (from `actistruct_nebwalk/mxenes/` if
present, else a synthetic fallback), places H at 8 (u,v) sites, runs the full
surrogate pipeline (GNN encode -> pretrain -> GP fit -> batch predict), and
exercises the ledger and dashboard data loader. No QE/DFT is launched.

### 4. Launch the dashboard

```bash
streamlit run actistruct/dashboard/app.py
```

---

## Quantum ESPRESSO Setup

QE runs require a Linux/WSL2 environment with `pw.x` compiled and
pseudopotentials downloaded.

```bash
export ESPRESSO_PSEUDO=/path/to/SSSP_1.3.0_PBE_efficiency
export ESPRESSO_COMMAND="mpirun -np 2 pw.x"
which pw.x
```

All Ti3C2-O campaign pseudopotentials are from SSSP 1.3.0 PBE efficiency:
Ti (`ti_pbe_v1.4.uspp.F.UPF`), C (`C.pbe-n-kjpaw_psl.1.0.0.UPF`),
O (`O.pbe-n-kjpaw_psl.0.1.UPF`), H (`H.pbe-rrkjus_psl.1.0.0.UPF`).

See `pseudo/README.md` and `docs/qe_setup.md` for full setup notes.

**WSL2 RAM note**: The 28-atom Ti3C2-O slab at LF (ecutwfc=40) peaks at
~3.3 GB. HF (ecutwfc=60) ionic relaxation needs ~5.4 GB -- add
`memory=6GB` to `.wslconfig` or use a cluster for HF relax.

---

## Running the Ti3C2-O HER Campaign

```bash
# Single oracle call -- LF (computes and caches E_slab + E_H2 on first call)
FIDELITY=low python examples/manual_qe/ti3c2_o_her_qe_active_inverse.py

# Switch to HF (requires .wslconfig memory=6GB or cluster)
FIDELITY=high python examples/manual_qe/ti3c2_o_her_qe_active_inverse.py
```

E_slab and E_H2 are cached after the first call; subsequent (u,v) evaluations
at the same fidelity level only run a single slab+H SCF (~1.7h on WSL2 at LF).

## Running the 50-Workflow QE Benchmark (v0.x)

```bash
bash run.sh all
bash run.sh battery
bash run.sh one generated_models/bulk_lifepo4_qe_active_inverse.py
```

---

## Benchmark Status

### v2.0 Ti3C2-O HER (Phase 2, ongoing)

| Run | System | ecutwfc | kpts | Energy | Status |
|---|---|---|---|---|---|
| LF static (clean slab) | Ti3C2-O 2x2 (28 at.) | 40 Ry | (3,3,1) | -25973.017 eV | JOB DONE |
| LF (u,v) grid campaign | 6-9 sites | 40 Ry | (3,3,1) | pending | not started |
| HF ionic relax | Ti3C2-O 2x2 | 60 Ry | (6,6,1) | -- | deferred (OOM on WSL2) |

### v0.x Reliability Classifier (v0.3.2, 20 repeated group splits)

```text
threshold 0.05 -> failure recall 0.776 +/- 0.344
threshold 0.10 -> failure recall 0.725 +/- 0.377
threshold 0.30 -> failure recall 0.300 +/- 0.359
```

Large split-to-split variance. This is a soft triage signal, not a hard filter.

### v0.5.1 Offline Stress Benchmark (50 trials, 4 pool modes)

Failure-aware LCB reduced mean predicted failure risk across all four pool modes
and reduced known-failed selections clearly in normal and failure-enriched pools.
Improvement was weaker in held-out-material and high-uncertainty pools.

### Direct Grid Validation (GP/LCB engine)

| System | Grid | Status | Delta vs AL |
|---|---:|---|---:|
| Cu FCC | 20/20 | pass | 0.000198 eV/atom |
| MoS2 monolayer | 49/49 | pass | 0.000916 eV/atom |
| Rocksalt MgO | 20/20 | pass | 0.000157 eV/atom |
| Diamond Si | 20/20 | pass | 0.000233 eV/atom |

Validates the GP/LCB structure-optimization engine, not the v2 GNN surrogate.

---

## Safe Claims

- The SchNetEncoder produces geometry-sensitive embeddings: same composition
  but different bond lengths -> different embedding (verified by test).
- The `HybridGPSurrogate` is **frozen-embedding transfer learning**, not
  Kennedy-O'Hagan co-kriging. The LF-to-HF transfer is only scientifically
  valid because the encoder is frozen before the GP sees HF data.
- The `StandardScaler` before GP fit is required: raw SchNet embeddings have
  ~20x per-dim variance, which pushes optimal length scale below the 1e-2
  lower bound and causes `ConvergenceWarning`. After scaling, optimal LS ~3-5.
- The LF static calculation on the clean 28-atom Ti3C2-O slab is validated:
  JOB DONE, no spurious warnings, energy = -25973.017 eV.
- The (u,v) fractional-coordinate design variable produces meaningfully
  distinct embeddings across adsorption sites (atop vs hollow distance ~1.0,
  well above the 1e-2 threshold).
- The v0.x offline benchmark results (classifier, acquisition, grid validation)
  remain valid and are retained exactly.

ActiStruct does **not** claim:

- a live Ti3C2-O HER active-learning run has been completed (LF grid campaign
  not yet started),
- that the HF ionic relaxation is feasible on WSL2 without `.wslconfig`
  memory increase (it OOMs at default 3.7 GB),
- that the GNN surrogate outperforms the simple sklearn GP on real HER data
  (no comparative benchmark has been run yet),
- that it replaces QE/PBE validation.

---

## Limitations

- **HF ionic relax** deferred: ecutwfc=60 on the 28-atom slab needs ~5.4 GB;
  WSL2 default is 3.7 GB. Needs `.wslconfig memory=6GB` or a compute cluster.
- **`run_dft_with_recovery()`** wraps static SCF only. Ionic relaxation restart
  requires manual `restart_mode='restart'` in the QE control namelist.
- **Uncertainty Evolution dashboard tab** not yet wired: requires per-iteration
  GP std stored in the ledger, available only once the surrogate runs live.
- **GP ConvergenceWarning** can appear in the demo/test with a
  randomly-initialized encoder and very few (< 6) HF points; this is expected
  and suppressed in the demo. In a real campaign the encoder is pretrained
  first, spreading the embedding space.
- v0.x reliability-classifier recall has large split-to-split variance on
  held-out materials; it should not be used as a hard accept/reject filter.
- No live QE/DFT active-learning run with failure-aware acquisition has been
  performed yet; all v0.x reliability/acquisition evidence is offline.

---

## Roadmap

### v2.x (near-term)

1. **LF grid campaign**: run `FIDELITY=low` oracle at 6-9 initial (u,v) sites
   (atop, hollow, bridge, intermediate) to build the LF DeltaG_H dataset.
2. **GNN pretraining**: train `SchNetEncoder` on LF structures + energies.
3. **Bayesian optimization**: `HybridGPSurrogate` proposes next (u,v) via
   `differential_evolution` minimising LCB; run oracle at proposed site.
4. **HF evaluation**: after LF convergence, run 3-4 selected sites at
   `FIDELITY=high` (needs cluster or `.wslconfig memory=6GB`).
5. **Active learning loop**: iterate surrogate fit -> propose -> evaluate
   until DeltaG_H uncertainty at best site < convergence tolerance.
6. **Uncertainty Evolution tab**: store GP std per iteration in ledger, wire
   into dashboard.

### Longer term

- True multi-fidelity co-kriging (Kennedy-O'Hagan discrepancy correction)
  as a stretch goal beyond frozen-embedding transfer learning.
- Extend to other MXene terminations (Ti3C2-F, Ti3C2-OH, V2C-O) and
  compare DeltaG_H landscape across terminations.
- Validate failure-aware acquisition (v0.x) in a live GP/QE run before
  claiming live DFT savings.

---

## Citation

If ActiStruct supports your work, please cite the repository metadata in
`CITATION.cff`. Update the DOI after archival release.

## Acknowledgments

ActiStruct was developed with selective AI-assisted support for code review,
debugging guidance, documentation refinement, and release-workflow cleanup.
Scientific direction, algorithmic design, implementation decisions, validation
strategy, benchmark interpretation, and release responsibility remain with the
project maintainer.

## License

MIT License. See `LICENSE`.
