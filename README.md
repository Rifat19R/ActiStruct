# ActiStruct

Active-learning workflow for DFT-guided materials discovery.

![Tests](https://img.shields.io/badge/tests-434%20passed%2C%200%20warnings-brightgreen)
![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue)
![CI](https://github.com/Rifat19R/ActiStruct/actions/workflows/ci.yml/badge.svg)
![License](https://img.shields.io/badge/license-MIT-green)

---

## What it does in 30 seconds

- Given a DFT geometry-search problem (adsorption site, bulk lattice, molecule),
  ActiStruct proposes the next candidate to compute using a Gaussian-Process
  surrogate over a geometry-aware GNN embedding.
- It records every DFT run -- successful and failed -- into a JSONL ledger,
  and automatically escalates failed runs through a four-group recovery strategy
  before giving up.
- It does not replace Quantum ESPRESSO. It decides which QE runs to launch and
  learns from the ones that fail.

---

## v2.0 status (honest)

> All code paths are implemented and unit-tested (434 tests, 0 warnings).
> One clean-slab QE static SCF was historically reported for the Ti3C2-O
> 2x2 slab (E = -25973.017 eV, JOB DONE, 1h43m on WSL2 mpirun -np 2), but
> raw QE output is not retained in the repo and must be regenerated before
> citation-grade use.
>
> **A closed active-learning loop has not yet been run on live DFT data.**
> The LF (u,v) campaign is next. HF ionic relaxation is deferred pending
> hardware upgrade (needs ~5.4 GB RAM; WSL2 default is 3.7 GB).

This is a development release. See [Roadmap](#roadmap) for what is planned next.

---

## What v2.0 adds

| Component | v0.x (retained) | v2.0 (new) |
|---|---|---|
| Active-learning core | GP/LCB + failure-risk penalty | Differential Evolution in 2D (u,v) space |
| Surrogate | sklearn GP on raw descriptors | HybridGPSurrogate: GNN pretrain -> frozen embeddings -> GP |
| GNN encoder | None | SchNetEncoder: neighbor list + Gaussian RBF + message passing |
| DFT fault handling | Manual | DFTFailureAnalyzer + TroubleshootingStrategy (4 groups) + run_dft_with_recovery() |
| Campaign oracle | 50 generated bulk/surface scripts | Ti3C2-O HER: DeltaG_H = E_slab+H - E_slab - 0.5*E_H2 + 0.04 eV |
| Ledger | None | Append-only JSONL, NTFS-safe atomic writes |
| Monitoring | None | 4-tab Streamlit dashboard |
| Tests | 81 tests | 433 tests, 0 warnings (3.11 + 3.12 CI) |

---

## Surrogate architecture

```
Low-fidelity DFT  (ecutwfc=40, kpts=3x3x1)
        |
  SchNetEncoder.pretrain()
  cutoff=5.0 A (Ti3C2-O), embedding_dim=64, 3 message-passing blocks
  Loss: MSE energy/atom via Linear->SiLU->Linear head
        |
   FREEZE encoder weights  (requires_grad_(False))
        |
High-fidelity DFT  (ecutwfc=60, kpts=6x6x1)
        |
  StandardScaler on frozen HF embeddings
        |
  GaussianProcessRegressor
  kernel: ConstantKernel(1.0) * RBF(ls=1.0, bounds=(1e-2, 1e5))
  alpha=1e-4, n_restarts_optimizer=5, normalize_y=True
        |
  predict(atoms) -> (mean eV/atom, uncertainty eV/atom)
        |
  differential_evolution minimises LCB -> next (u,v) candidate
        |
  DFT oracle + run_dft_with_recovery() -> ledger append
```

This is **frozen-embedding transfer learning**, not Kennedy-O'Hagan co-kriging.
The encoder is pretrained on LF data, frozen, and its outputs are features for
the HF GP. This is named honestly throughout the code.

Key design decisions:

- **GNN cutoff (Ti3C2-O):** 5.0 A. Ti-C ~2.1 A, Ti-O ~2.0 A; 5.0 A captures
  both bond shells with margin to distinguish hollow vs atop H adsorption sites.
- **StandardScaler before GP fit:** Raw SchNet embeddings have ~20x per-dim
  variance. After scaling, pairwise distances are ~1-12, optimal GP length
  scale ~3-5, and ConvergenceWarnings are eliminated on real data.
- **alpha=1e-4, no WhiteKernel:** WhiteKernel noise estimation is unreliable
  with 5-20 HF points and collapses to its lower bound on clean data. Fixed
  alpha=1e-4 is numerical regularization for stable GP fitting; it is not a
  measured physical DFT noise level.
- **NTFS-safe locking:** WSL2 /mnt/d/ (NTFS) does not support fcntl/flock.
  Ledger and cache use O_CREAT|O_EXCL for safe concurrent writes.
- **Cumulative escalation:** Smearing method and degauss always change together
  (physically coupled). electron_maxstep=300 (group 4) retains all prior group
  changes. nspin is never touched automatically.

---

## Implemented components

### Phase 0 -- Ledger (`actistruct/core/`)

- `atomic_cache.py` -- NTFS-safe atomic file cache (O_CREAT|O_EXCL locking,
  not fcntl/flock)
- `ledger.py` -- append-only JSONL run ledger; one record per DFT attempt;
  atomically locked during writes

### Phase 1 -- Debug and Recovery (`actistruct/debug/`)

- `classifier.py` -- `DFTFailureAnalyzer`: regex classifier for pw.x output;
  categories SUCCESS, SCF_CONVERGENCE, ELECTRONIC_INSTABILITY, GEOMETRY_CRASH,
  UNKNOWN. Patterns verified against real QE 7.x .pwo output. Broyden/linmin
  intentionally excluded from GEOMETRY_CRASH (appear in normal BFGS logs).
- `strategies.py` -- `TroubleshootingStrategy`: 4 cumulative escalation groups:
  (1) mixing_beta=0.3, (2) Gaussian smearing + degauss=0.02, (3) M-P smearing
  + degauss=0.03, (4) electron_maxstep=300. Smearing+degauss always together.
- `recovery.py` -- `run_dft_with_recovery()`: wraps static SCF with automatic
  fault detection, escalation, and ledger logging. Not adapted for ionic
  relaxation (use restart_mode='restart' manually).

### Phase 2 -- GNN Surrogate (`actistruct/gnn/`)

- `config.py` -- `GNNConfig`, `MultiFidelityConfig`. Per-system cutoff
  guidance documented.
- `encoder.py` -- `SchNetEncoder`: pairwise distances via ase.neighborlist,
  Gaussian RBF expansion, message-passing block (filter_ij = MLP(rbf(d_ij)),
  h_i += sum_j(filter_ij * h_j)), mean-pool. Same composition + different bond
  lengths -> different embedding (verified by test).
- `surrogate.py` -- `HybridGPSurrogate`: pretrain, freeze, StandardScaler,
  GP fit, predict, predict_batch. predict(atoms) returns (mean eV/atom,
  uncertainty eV/atom); drop-in for the existing GPModel interface.

### Phase 3 -- Dashboard (`actistruct/dashboard/`)

- `app.py` -- Streamlit dashboard (4 tabs: scorecard + convergence rate,
  energy landscape, 3D structure viewer via py3Dmol/stmol, run log). Multi-
  ledger support; handles empty ledger gracefully.
- `data_loader.py` -- load_ledger(), load_multi_ledger(), get_summary_stats().

Launch: `streamlit run actistruct/dashboard/app.py`

Screenshot pending first campaign run (empty ledger screenshot omitted per
project convention: real data or no screenshot).

### Phase 2 Oracle -- Ti3C2-O HER (`examples/manual_qe/`)

`ti3c2_o_her_qe_active_inverse.py`:

- `DeltaG_H = E(slab+H) - E(slab) - 0.5*E(H2) + 0.04 eV` (Norskov ZPE-TS)
- Design variable: (u,v) in-plane fractional coordinates of adsorbed H
- FIDELITY=low: ecutwfc=40, ecutrho=320, kpts=(3,3,1)
- FIDELITY=high: ecutwfc=60, ecutrho=480, kpts=(6,6,1)
- All energies cached per fidelity; E_slab and E_H2 computed once per run
- Pseudopotentials: Ti(USPP) + C(PAW) + O(PAW) + H(USPP), SSSP 1.3.0 PBE
  efficiency. All filenames verified against disk.
- Acquisition: differential_evolution minimising thermoneutral LCB over (u,v)
  space, targeting `|DeltaG_H|` near zero
- **LF static (clean slab) historically reported:** E = -25973.017 eV, JOB
  DONE, 1h43m; raw QE output must be regenerated before citation-grade use

### v0.x Reliability Layer (retained, unchanged)

- `actistruct/parsers/qe.py` -- QE output parser; failures recorded as data
- `actistruct/datasets/qe_records.py` -- dataset builder for parsed QE records
- `actistruct/acquisition/reliability.py` -- soft failure-risk LCB penalty;
  old LCB behavior preserved when gamma=0 or no risk estimate available
- `analysis/` -- reliability classifier (v0.3.2), offline benchmarks (v0.5.x)
- `generated_models/` -- 50 original v0.x QE workflow scripts (the Phase 2
  campaign scripts bulk_lifepo4 and bulk_fe_bcc are additional)

---

## Test suite

433 tests, 0 warnings (Python 3.11 + 3.12, CI). No QE/DFT is launched by any test.

**ActiStruct core tests:**

| Test file | What it covers |
|---|---|
| `test_hybrid_surrogate.py` | GNN geometry sensitivity, permutation invariance, fidelity config, overfit sanity, (u,v) UV design variable sensitivity |
| `test_debugging.py` | DFTFailureAnalyzer (5 categories), TroubleshootingStrategy (4 groups), run_dft_with_recovery() |
| `test_dashboard.py` | Ledger loading, summary stats, multi-ledger, empty-ledger safety |
| `test_ledger.py` | Append, concurrent writes, lock timeout, schema validation |
| `test_generated_workflows.py` | All generated_models scripts import and define required attributes |
| `test_failure_aware_acquisition.py`, `test_qe_reliability_*` | v0.x reliability and acquisition layer |

**TMC Reliability Benchmark tests (Tasks 1-9):**

| Test file | Tests | What it covers |
|---|---|---|
| `test_pseudo_verification.py` | 8 | SSSP checksums for Cr, Fe, Ni pseudopotentials |
| `test_qe_parser.py` | 18 | QE output parsing, force/energy extraction |
| `test_feature_builder.py` | 22 | Coulomb matrix + geometry reproducibility, DFT vs reference |
| `test_reference_data_integrity.py` | 11 | YAML reference schema and verification status |
| `test_convergence_and_consistency.py` | 12 | BFGS convergence, atom counts, energy ordering, dE sanity |
| `test_fe_cutoff_convergence.py` | 14 | Fe cutoff convergence data, ferrocene label disambiguation |
| `test_neb_endpoints.py` | 9 | XYZ files, stoichiometry, dE encoding, energy bounds |
| `test_ml_al_framing.py` | 31 | Report disclaimer presence, prohibited over-claim phrases |
| `test_baseline_model.py`, `test_al_demo.py`, others | 122 | Dataset loading, GP baseline, AL demo, candidates, structures |

```bash
pytest -q       # 433 passed, 0 warnings
```

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
|-- generated_models/                 # 50 original v0.x QE workflow scripts
|
|-- [TMC Reliability Benchmark - Tasks 1-9]
|-- scripts/                          # 17 numbered pipeline scripts (01-17)
|-- configs/                          # QE settings, pseudo manifest, project config
|-- data/
|   |-- processed/                    # full_dataset_v0.2.csv, cutoff convergence, candidates
|   |-- features/                     # Coulomb matrix + geometry features v0.1
|   |-- models/                       # GP baseline and AL demo model records
|   `-- references/                   # YAML reference values and sources
|-- qe/
|   |-- inputs/relax/                 # validated QE input files for all systems
|   `-- outputs/                      # cutoff convergence outputs, PBE-D3 rerun
|-- structures/
|   |-- initial_xyz/                  # starting geometries for 4 primary systems
|   |-- generated_candidates/         # 52 perturbation candidates
|   `-- neb_endpoints/                # ferrocene D5h/D5d endpoints for nebwalk
|-- references/                       # literature reference YAML and CSV
|-- reports/                          # benchmark reports, daily logs, figures
|
|-- tests/                            # 433 tests, no QE/DFT launched
|-- archive/caaln2_dropped/           # archived CaAlN2 scripts (scope change)
|-- analysis/                         # classifier training, offline benchmarks
|-- docs/                             # setup guides and specification docs
|-- outputs/
|   |-- cache/                        # DFT energy caches (gitignored)
|   `-- reports/                      # 50 completed benchmark reports (kept)
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
pytest -q       # 433 passed, 0 warnings
```

**Run the no-QE demo (exercises full v2 stack on real Ti3C2-O geometry):**
```bash
python demo_ti3c2_o.py
```

**Launch the monitoring dashboard:**
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

Ti3C2-O pseudopotentials (SSSP 1.3.0 PBE efficiency, verified on disk):
- Ti: `ti_pbe_v1.4.uspp.F.UPF` (USPP)
- C:  `C.pbe-n-kjpaw_psl.1.0.0.UPF` (PAW)
- O:  `O.pbe-n-kjpaw_psl.0.1.UPF` (PAW)
- H:  `H.pbe-rrkjus_psl.1.0.0.UPF` (USPP)

See `pseudo/README.md` and `docs/qe_setup.md` for full setup notes.

**WSL2 RAM:** LF slab (ecutwfc=40, 28 atoms) peaks at ~3.3 GB. HF ionic
relaxation (ecutwfc=60) needs ~5.4 GB -- add `memory=6GB` to
`C:\Users\<user>\.wslconfig` or run on a cluster.

---

## Running the Ti3C2-O HER campaign

```bash
# Step 1: LF oracle call (first call caches E_slab + E_H2; ~1.7h per
# (u,v) evaluation after that)
FIDELITY=low python examples/manual_qe/ti3c2_o_her_qe_active_inverse.py

# Step 2: run the frozen six-site (u,v) seed campaign
# (not yet completed -- see Roadmap)

# Step 3: HF evaluation at selected sites (requires .wslconfig memory=6GB
# or cluster -- deferred)
FIDELITY=high python examples/manual_qe/ti3c2_o_her_qe_active_inverse.py
```

Steps 2 and 3 have not been completed yet. Five preliminary development-site
calculations were completed earlier, but they were superseded after symmetry
aliasing and lateral adsorbate migration were identified. See Roadmap.

## Running the v0.x 50-workflow benchmark

```bash
bash run.sh all
bash run.sh one generated_models/bulk_lifepo4_qe_active_inverse.py
```

---

## Benchmark status

### Phase 2 -- Ti3C2-O HER (ongoing)

| Run | System | ecutwfc | kpts | Energy | Status |
|---|---|---|---|---|---|
| LF static, clean slab | Ti3C2-O 2x2, 28 atoms | 40 Ry | (3,3,1) | -25973.017 eV | JOB DONE |
| Frozen LF (u,v) seed campaign | 6 distinct (u,v) sites | 40 Ry | (3,3,1) | -- | not completed |
| HF ionic relax | Ti3C2-O 2x2 | 60 Ry | (6,6,1) | -- | deferred (WSL2 OOM) |

To reproduce: `FIDELITY=low python examples/manual_qe/ti3c2_o_her_qe_active_inverse.py`
Expected output: energy cached in
`outputs/cache/ti3c2_o_her_low_protocol_v1_amend1.pkl`

### v0.x -- reliability classifier (v0.3.2, 20 repeated group splits)

```
threshold 0.05  ->  failure recall 0.776 +/- 0.344
threshold 0.10  ->  failure recall 0.725 +/- 0.377
threshold 0.30  ->  failure recall 0.300 +/- 0.359
```

Large split-to-split variance. Soft triage signal; not a hard filter.

### v0.x -- structural parameter recovery (23-system check subset)

Mean absolute percentage deviation: **0.71%**. Median: 0.65%.
Source: `outputs/reports/ACTISTRUCT_RESULTS_DRAFT.md`.
This is a structural sanity check, not a claim that all 50 workflows are
literature-validated.

### v0.x -- direct grid validation (GP/LCB engine)

| System | Grid | Status | Delta vs AL | Reproduce |
|---|---:|---|---:|---|
| Cu FCC | 20/20 | pass | 0.000198 eV/atom | `analysis/direct_grid_validation.py` |
| MoS2 monolayer | 49/49 | pass | 0.000916 eV/atom | same |
| Rocksalt MgO | 20/20 | pass | 0.000157 eV/atom | same |
| Diamond Si | 20/20 | pass | 0.000233 eV/atom | same |

Validates the GP/LCB engine. Does not validate the v2.0 GNN surrogate.

### v0.x -- offline failure-aware benchmark (v0.5.1, 50 trials)

Failure-aware LCB reduced mean predicted failure risk across all four pool
modes and reduced known-failed selections most clearly in normal and
failure-enriched pools. Weaker in held-out-material and high-uncertainty pools.
Source: `reports/simulated_failure_aware_al_benchmark_v051.md`.

---

## Safe claims

Claim governance:

- `docs/FEATURE_FREEZE.md` records the current scientific-evidence freeze.
- `docs/CLAIMS_AND_EVIDENCE.md` maps major claims to evidence, commands, and
  limitations.
- `docs/BENCHMARK_PROTOCOL.md` freezes the next LF Ti3C2-O benchmark protocol
  before live campaign results are generated.

- The GNN encoder produces geometry-sensitive embeddings: same composition +
  different bond lengths -> different embedding (verified by test).
- The LF static SCF on the 28-atom Ti3C2-O slab was historically reported as
  JOB DONE with E = -25973.017 eV. Raw QE output is not retained in the repo,
  so this claim must be regenerated before citation-grade use.
- The (u,v) design variable produces meaningfully distinct embeddings across
  adsorption sites (atop vs hollow embedding distance ~1.0, >> 0.01 threshold).
- The 23-system structural check gives 0.71% mean deviation vs reference values.
- v0.x offline benchmark results are retained and unchanged.

ActiStruct does not claim:
- A live Ti3C2-O active-learning campaign has completed (frozen LF seed
  campaign not completed).
- The GNN surrogate outperforms a simple GP on real HER data (no head-to-head
  benchmark has been run).
- HF ionic relaxation is feasible on WSL2 without .wslconfig change (it OOMs).
- Guaranteed reduction of failed DFT jobs.
- Live DFT savings (no live active-learning run has been performed).
- It replaces QE/PBE validation.

---

## Limitations

- **HF ionic relax deferred**: ecutwfc=60 on 28-atom slab needs ~5.4 GB; WSL2
  default is 3.7 GB. Needs `.wslconfig memory=6GB` or a cluster.
- **run_dft_with_recovery()** wraps static SCF only. Ionic relaxation restart
  requires manual `restart_mode='restart'`.
- **Post-relax k-point consistency check** required before declaring any relaxed
  geometry canonical. Not needed for this sprint (no new relaxations).
- **Uncertainty Evolution dashboard tab** not yet wired: requires per-iteration
  GP std stored in the ledger.
- v0.x reliability classifier has large split-to-split variance on held-out
  materials. Do not use as a hard accept/reject filter.
- No live QE active-learning run with failure-aware acquisition has been
  performed. All v0.x evidence is offline.

---

## Roadmap

### v2.x near-term

1. Frozen LF seed campaign: run oracle at 6 distinct initial (u,v) sites.
2. GNN pretraining: train SchNetEncoder on LF DeltaG_H structures + energies.
3. Active learning loop: HybridGPSurrogate proposes next (u,v) via LCB;
   evaluate oracle; retrain. Iterate until convergence.
4. HF evaluation: 3-4 sites at FIDELITY=high (cluster or .wslconfig memory=6GB).
5. Uncertainty Evolution tab: store GP std per iteration in ledger; wire
   into dashboard.

### Longer term

- Head-to-head: HybridGPSurrogate vs sklearn GP on real HER data (requires
  the active-learning loop to have produced data first).
- Validate v0.x failure-aware acquisition in a live GP/QE run.
- Extend to other MXene terminations: Ti3C2-F, Ti3C2-OH, V2C-O.

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

---

## TMC Reliability Benchmark (v1.0)

The TMC Benchmark v1.0 is a separate benchmark artifact inside the ActiStruct
repository, distinct from the ActiStruct v2.0 software status above. It contains
converged QE records for transition-metal carbonyls and metallocenes, used to
assess ActiStruct's active-learning pipeline on real QE-relaxed structures.

**Systems**: Cr(CO)6, Fe(CO)5, Ni(CO)4, ferrocene (D5h/D5d conformers) -- 16
converged QE records passing internal checks, with Coulomb-matrix features, GP
baseline, and AL demo.

**Key results**:
- Ferrocene D5h -> D5d conformer energy difference: dE = 41.68 meV (same scale
  as the known experimental rotational barrier, ~41 meV); ferrocene reference
  geometry is primary-PDF verified. A true barrier claim would require a
  constrained rotational scan or NEB.
- Fe cutoff convergence: 90 Ry adopted; 60 Ry fails the Fe(CO)5 energy criterion
  (+18.55 meV/atom vs 90 Ry), while Fe-C bond lengths are already stable
- NEB endpoints prepared for nebwalk demo (`structures/neb_endpoints/`)

**Tests**: 424 passing across all ActiStruct and TMC benchmark test files (Python 3.11 + 3.12, CI green).
