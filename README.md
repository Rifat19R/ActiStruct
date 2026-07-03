# ActiStruct v2.0

Active-learning workflow for DFT-guided materials discovery combining a
GNN-pretrained surrogate, a multi-fidelity DFT oracle, and an autonomous
Quantum ESPRESSO fault-recovery engine.

```
GNN encodes. GP ranks by uncertainty. Debug engine recovers. QE/PBE validates.
```

**128 tests, 0 warnings** (Python 3.12, WSL2).

---

## What it does

ActiStruct runs a closed-loop active-learning campaign that finds the optimal
adsorption geometry (or any parameterised structure) using as few DFT
calculations as possible:

1. Build a small initial set of DFT-evaluated structures.
2. Pretrain a SchNet-style GNN encoder on low-fidelity (LF) energies.
3. Freeze encoder weights; fit a GP on high-fidelity (HF) embeddings.
4. Use Differential Evolution to minimise the Lower Confidence Bound (LCB)
   over the design-variable space and propose the next candidate.
5. Run DFT oracle with automatic fault detection and escalation.
6. Append result to ledger; retrain surrogate; repeat until convergence.

It does not replace QE/PBE -- it learns from completed calculations, including
failures, to decide which structures to compute next.

---

## What is new in v2.0

| Component | v2.0 addition |
|---|---|
| GNN encoder | SchNetEncoder: pairwise distances + Gaussian RBF + message passing |
| Surrogate | HybridGPSurrogate: LF pretrain -> freeze -> HF GP fit |
| GP fix | StandardScaler + fixed alpha=1e-4 (no WhiteKernel); eliminates ConvergenceWarning |
| Debug engine | DFTFailureAnalyzer, TroubleshootingStrategy (4 escalation groups), run_dft_with_recovery() |
| Ledger | Append-only JSONL run ledger; NTFS-safe atomic writes |
| Dashboard | 4-tab Streamlit campaign monitor |
| Phase 2 oracle | Ti3C2-O MXene HER: DeltaG_H = E_slab+H - E_slab - 0.5*E_H2 + 0.04 eV |
| Design variable | (u, v) in-plane fractional coordinates of adsorbed H |
| Tests | 128 passed, 0 warnings (was 81 in v0.7.2) |

The v0.x reliability-aware layer (QE parser, failure-risk classifier,
failure-aware LCB acquisition, 50-workflow benchmark) is retained unchanged.

---

## Surrogate architecture

```
Low-fidelity DFT  (ecutwfc=40, kpts=3x3x1)
        |
  SchNetEncoder.pretrain()
  cutoff=5.0 A, embedding_dim=64, 3 message-passing blocks
        |
   freeze weights
        |
High-fidelity DFT  (ecutwfc=60, kpts=6x6x1)
        |
  HybridGPSurrogate.fit()
  StandardScaler -> ConstantKernel * RBF, alpha=1e-4, n_restarts=5
        |
  predict(atoms) -> (mean eV/atom, std eV/atom)
        |
  differential_evolution -> next (u, v) candidate
        |
  DFT oracle + run_dft_with_recovery() -> ledger
```

The surrogate is **frozen-embedding transfer learning**, not Kennedy-O'Hagan
co-kriging. The encoder is pretrained once on LF data, frozen, and its outputs
serve as features for the HF GP.

---

## Key design decisions

**GNN cutoff (Ti3C2-O):** `cutoff=5.0 A`. Ti-C ~2.1 A, Ti-O ~2.0 A; 5.0 A
captures both bond shells with margin to distinguish hollow vs atop H sites.

**StandardScaler:** Raw SchNet embeddings have ~20x per-dim standard deviation
variance. After scaling, pairwise distances are ~1-12, optimal GP length scale
~3-5, no ConvergenceWarning.

**alpha=1e-4 (no WhiteKernel):** WhiteKernel noise estimation is unreliable
with 5-20 HF points and collapses to its lower bound. Fixed alpha provides
numerical regularisation appropriate for DFT convergence noise (~0.1 meV/atom)
with no lower bound to optimise against.

**NTFS file locking:** WSL2 /mnt/d/ (NTFS) does not support fcntl/flock. The
ledger and cache use O_CREAT|O_EXCL for atomic writes safe under concurrent
workers.

**Escalation groups:** Smearing method and degauss always change together
(physically coupled). nspin is never touched automatically.

---

## Implemented components

### actistruct/core/

- `atomic_cache.py` -- NTFS-safe atomic file cache (O_CREAT|O_EXCL locking)
- `ledger.py` -- append-only JSONL run ledger; one record per DFT attempt

### actistruct/debug/

- `classifier.py` -- DFTFailureAnalyzer: regex classifier for pw.x output;
  categories SUCCESS, SCF_CONVERGENCE, ELECTRONIC_INSTABILITY, GEOMETRY_CRASH,
  UNKNOWN. All patterns verified against real QE 7.x .pwo output.
- `strategies.py` -- TroubleshootingStrategy: 4 cumulative escalation groups
  (soften mixing -> Gaussian smearing -> M-P smearing -> more SCF iterations).
- `recovery.py` -- run_dft_with_recovery(): wraps a static SCF call with
  automatic fault detection, escalation, and ledger logging.

### actistruct/gnn/

- `config.py` -- GNNConfig, MultiFidelityConfig; per-system cutoff guidance.
- `encoder.py` -- SchNetEncoder: neighbor list, Gaussian RBF, message-passing
  interaction block, mean-pool. Geometry-sensitive: same composition + different
  bond lengths -> different embedding (verified by test).
- `surrogate.py` -- HybridGPSurrogate: pretrain, freeze, fit, predict, predict_batch.
  predict(atoms) returns (mean eV/atom, std eV/atom); drop-in for existing GPModel.

### actistruct/dashboard/

- `app.py` -- Streamlit dashboard (4 tabs: scorecard, energy landscape, 3D
  viewer, run log). Multi-ledger support; handles empty ledger gracefully.
- `data_loader.py` -- load_ledger(), load_multi_ledger(), get_summary_stats().

Launch: `streamlit run actistruct/dashboard/app.py`

### examples/manual_qe/

- `ti3c2_o_her_qe_active_inverse.py` -- Ti3C2-O HER oracle:
  - DeltaG_H = E(slab+H) - E(slab) - 0.5*E(H2) + 0.04 eV (Norskov correction)
  - Design variable: (u, v) in-plane fractional coordinates of adsorbed H
  - FIDELITY=low: ecutwfc=40, ecutrho=320, kpts=(3,3,1)
  - FIDELITY=high: ecutwfc=60, ecutrho=480, kpts=(6,6,1)
  - Energies cached per fidelity level; E_slab and E_H2 computed once
  - Pseudos: Ti(USPP) + C(PAW) + O(PAW) + H(USPP), SSSP 1.3.0 PBE efficiency
  - Acquisition: differential_evolution minimising LCB over (u, v) space
  - LF static verified: E(clean slab) = -25973.017 eV, JOB DONE, 1h43m

### v0.x layer (retained)

- `actistruct/parsers/qe.py` -- QE output parser; records failures as data
- `actistruct/datasets/qe_records.py` -- dataset builder for parsed QE records
- `actistruct/acquisition/reliability.py` -- failure-aware LCB acquisition
- `analysis/` -- reliability classifier (v0.3.2), offline benchmarks (v0.5.x)
- `generated_models/` -- 50+ generated QE benchmark scripts

---

## Repository structure

```
ActiStruct/
|-- demo_ti3c2_o.py                   # no-QE end-to-end demo (all 4 phases)
|-- qe_active_inverse_common.py       # shared GP/LCB active-learning engine
|-- actistruct/
|   |-- core/                         # ledger, atomic cache
|   |-- debug/                        # classifier, escalation, recovery
|   |-- gnn/                          # GNN config, encoder, surrogate
|   |-- dashboard/                    # Streamlit app, data loader
|   |-- acquisition/                  # failure-aware LCB (v0.x)
|   |-- parsers/                      # QE output parser (v0.x)
|   `-- datasets/                     # QE records dataset builder (v0.x)
|-- examples/manual_qe/
|   |-- ti3c2_o_her_qe_active_inverse.py   # Ti3C2-O HER oracle (Phase 2)
|   `-- h_cu111_qe_active_inverse.py       # Cu(111) H adsorption reference
|-- generated_models/                 # 50+ generated QE benchmark scripts
|-- tests/                            # 128 tests, no QE/DFT launched
|-- archive/caaln2_dropped/           # archived CaAlN2 scripts
|-- analysis/                         # classifier training, offline benchmarks
|-- docs/                             # setup guides and specification docs
|-- reports/                          # reliability and benchmark reports
|-- outputs/cache/                    # DFT energy caches (per fidelity)
|-- requirements.txt
|-- pyproject.toml
`-- CHANGELOG.md
```

---

## Getting started

```bash
git clone https://github.com/Rifat19R/ActiStruct.git
cd ActiStruct

# WSL2 / Linux (QE runs require Linux)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e ".[test]"
```

**Run tests (no QE launched):**
```bash
pytest -q       # 128 passed, 0 warnings
```

**Run the no-QE demo (verifies full v2 stack on real Ti3C2-O geometry):**
```bash
python demo_ti3c2_o.py
```

**Launch the dashboard:**
```bash
streamlit run actistruct/dashboard/app.py
```

---

## Quantum ESPRESSO setup

```bash
export ESPRESSO_PSEUDO=/path/to/SSSP_1.3.0_PBE_efficiency
export ESPRESSO_COMMAND="mpirun -np 2 pw.x"
which pw.x
```

See `pseudo/README.md` and `docs/qe_setup.md` for full setup notes.

**WSL2 RAM:** LF slab (ecutwfc=40, 28 atoms) peaks at ~3.3 GB. HF ionic
relaxation (ecutwfc=60) needs ~5.4 GB -- add `memory=6GB` to `.wslconfig`
or run on a cluster.

---

## Running the Ti3C2-O HER campaign

```bash
# LF oracle call (caches E_slab + E_H2 on first call; ~1.7h per (u,v) after)
FIDELITY=low python examples/manual_qe/ti3c2_o_her_qe_active_inverse.py

# HF oracle call (requires .wslconfig memory=6GB or cluster)
FIDELITY=high python examples/manual_qe/ti3c2_o_her_qe_active_inverse.py
```

## Running the 50-workflow benchmark (v0.x)

```bash
bash run.sh all
bash run.sh one generated_models/bulk_lifepo4_qe_active_inverse.py
```

---

## Benchmark status

### Phase 2 -- Ti3C2-O HER (ongoing)

| Run | System | ecutwfc | kpts | Energy | Status |
|---|---|---|---|---|---|
| LF static (clean slab) | Ti3C2-O 2x2, 28 atoms | 40 Ry | (3,3,1) | -25973.017 eV | JOB DONE |
| LF (u,v) grid campaign | 6-9 sites | 40 Ry | (3,3,1) | -- | not started |
| HF ionic relax | Ti3C2-O 2x2 | 60 Ry | (6,6,1) | -- | deferred (WSL2 OOM) |

### v0.x reliability classifier (v0.3.2, 20 repeated group splits)

```
threshold 0.05  ->  failure recall 0.776 +/- 0.344
threshold 0.10  ->  failure recall 0.725 +/- 0.377
threshold 0.30  ->  failure recall 0.300 +/- 0.359
```

Large split-to-split variance. Soft triage signal, not a hard filter.

### Direct grid validation (GP/LCB engine, v0.x)

| System | Grid points | Status | Delta vs AL |
|---|---:|---|---:|
| Cu FCC | 20/20 | pass | 0.000198 eV/atom |
| MoS2 monolayer | 49/49 | pass | 0.000916 eV/atom |
| Rocksalt MgO | 20/20 | pass | 0.000157 eV/atom |
| Diamond Si | 20/20 | pass | 0.000233 eV/atom |

---

## Honest claims

- The GNN encoder produces geometry-sensitive embeddings verified by test:
  same composition + different bond lengths -> different embedding.
- The LF static on the clean 28-atom Ti3C2-O slab is verified: JOB DONE,
  energy = -25973.017 eV, no spurious warnings.
- The (u,v) fractional-coordinate design variable produces meaningfully
  distinct embeddings across adsorption sites (atop vs hollow ~1.0, >> 0.01
  threshold).
- No live Ti3C2-O active-learning run has been completed yet (LF grid
  campaign not started).
- The HF ionic relaxation is not feasible on WSL2 without .wslconfig
  memory increase; deferred to cluster.
- The v0.x offline benchmark results are retained and unchanged.

ActiStruct does not claim:
- that the GNN surrogate outperforms a simple GP on real HER data (no
  comparative benchmark has been run),
- guaranteed reduction of failed DFT jobs,
- live DFT savings (no live active-learning run has been performed yet),
- that it replaces QE/PBE validation.

---

## Limitations

- **HF ionic relax deferred**: ecutwfc=60 on 28-atom slab needs ~5.4 GB;
  WSL2 default is 3.7 GB.
- **run_dft_with_recovery()** wraps static SCF only; ionic relaxation restart
  requires manual `restart_mode='restart'`.
- **Uncertainty Evolution dashboard tab** not yet wired: requires per-iteration
  GP std stored in the ledger.
- v0.x reliability-classifier recall has large split-to-split variance on
  held-out materials.
- No live QE active-learning run with failure-aware acquisition has been
  performed; all v0.x evidence is offline.

---

## Roadmap

1. LF grid campaign: run oracle at 6-9 initial (u,v) sites.
2. GNN pretraining: train SchNetEncoder on LF DeltaG_H structures + energies.
3. Active loop: HybridGPSurrogate proposes next (u,v) via LCB; evaluate; retrain.
4. HF evaluation: 3-4 sites at FIDELITY=high (cluster or .wslconfig memory=6GB).
5. Uncertainty Evolution tab: store GP std per iteration in ledger.
6. Extend to other MXene terminations (Ti3C2-F, Ti3C2-OH, V2C-O).

---

## Citation

If ActiStruct supports your work, please cite the repository metadata in
`CITATION.cff`.

## Acknowledgments

ActiStruct was developed with selective AI-assisted support for code review,
debugging guidance, documentation refinement, and release-workflow cleanup.
Scientific direction, algorithmic design, implementation decisions, validation
strategy, benchmark interpretation, and release responsibility remain with the
project maintainer.

## License

MIT License. See `LICENSE`.
