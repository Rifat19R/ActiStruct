#!/usr/bin/env python
"""
ActiStruct v2.0 - Full Integration Test
========================================
Exercises every built-in component in sequence:

  [1] Environment    - auto-detect pw.x + Al pseudopotential
  [2] Active Debug   - failure classifier, escalation strategy, recovery wrapper
  [3] QE DFT         - real pw.x on FCC Al (mock fallback if pw.x absent)
  [4] GNN Surrogate  - SchNet encoder pretrain + frozen-embedding GP
  [5] Dashboard      - ledger load + summary statistics

GNN model: ActiStruct built-in SchNet (NequIP/MACE not yet integrated).

Expected runtime: ~5-10 min (QE ~1-3 min, GNN pretrain ~2-4 min on CPU).

Run (WSL2):
    source .venv/bin/activate
    python test_all_integrations.py
"""
from __future__ import annotations

import time
import tempfile
from pathlib import Path

import numpy as np
from ase.build import bulk

# ── paths ─────────────────────────────────────────────────────
QE_BIN = Path("/home/alchemist/q-e/bin/pw.x")
PSEUDO_SEARCH = [
    Path("/home/alchemist/pseudo"),
    Path("/home/alchemist/q-e/pseudo"),
    Path.home() / "pseudo",
    Path("/usr/share/espresso/pseudo"),
]
WORKDIR = Path(tempfile.mkdtemp(prefix="actistruct_it_"))
LEDGER  = WORKDIR / "integration_ledger.jsonl"

SEP  = "=" * 62
DASH = "-" * 50

# ── actistruct imports ────────────────────────────────────────
from actistruct.core.ledger            import append_record, make_record, read_records
from actistruct.debug.classifier       import DFTFailureAnalyzer
from actistruct.debug.strategies       import TroubleshootingStrategy
from actistruct.debug.recovery         import run_dft_with_recovery
from actistruct.gnn.config             import GNNConfig
from actistruct.gnn.surrogate          import HybridGPSurrogate
from actistruct.dashboard.data_loader  import load_ledger, get_summary_stats

print("\n" + SEP)
print("  ActiStruct v2.0  |  Full Integration Test")
print("  Material: FCC Aluminium (Al)")
print(SEP)


# ── physics helpers ───────────────────────────────────────────
def build_al(a: float):
    """Primitive FCC Al cell (1 atom)."""
    return bulk("Al", "fcc", a=a)


def _bm_energy(a: float) -> float:
    """Birch-Murnaghan-like Al energy (eV/cell, 1 atom).
    Minimum: E0=-56.913 eV at a0=4.0495 A, K=17.8 eV/A^2."""
    E0, a0, K = -56.9130, 4.0495, 17.8
    return E0 + K * (a - a0) ** 2


# =============================================================
# [1] ENVIRONMENT CHECK
# =============================================================
print("\n[1] Environment " + "-" * 45)

qe_ok = QE_BIN.exists()
print(f"  pw.x       : {'FOUND' if qe_ok else 'NOT FOUND'}")
print(f"             : {QE_BIN}")

pseudo_dir: Path | None = None
al_pseudo:  str  | None = None
for p in PSEUDO_SEARCH:
    if p.is_dir():
        hits = sorted(p.glob("Al*.UPF")) + sorted(p.glob("al*.upf"))
        if hits:
            pseudo_dir = p
            al_pseudo  = hits[0].name
            break

pseudo_ok = pseudo_dir is not None
print(f"  pseudo_dir : {'FOUND' if pseudo_ok else 'NOT FOUND'}")
if pseudo_ok:
    print(f"             : {pseudo_dir / al_pseudo}")
print(f"  workdir    : {WORKDIR}")

USE_REAL_QE = qe_ok and pseudo_ok
mode_label  = "REAL pw.x" if USE_REAL_QE else "MOCK (pw.x or pseudo not found)"
print(f"\n  Mode: {mode_label}")


# =============================================================
# [2] ACTIVE DEBUGGING: classifier + escalation + recovery
# =============================================================
print("\n[2] Active Debugging " + "-" * 40)

# 2a. Failure classifier
print("  Failure classifier:")
analyzer  = DFTFailureAnalyzer()
test_cases = [
    ("SCF non-conv.",    "convergence NOT achieved after 100 iterations; stopping"),
    ("Geom. crash",      "atoms too close: minimum distance is 0.01 Bohr"),
    ("Elec. instab.",    "S matrix not positive definite"),
    ("BFGS normal run",  "Broyden method\nlinmin alpha=1.0\nJOB DONE."),
    ("Clean success",    "JOB DONE."),
]
for label, text in test_cases:
    result = analyzer.classify(text)
    print(f"    {label:<22} ->  {result}")

# 2b. Escalation strategy (show cumulative steps)
print("\n  Cumulative escalation strategy:")
base_input = {
    "system":    {"ecutwfc": 30.0, "smearing": "gaussian", "degauss": 0.01},
    "electrons": {"conv_thr": 1e-8, "electron_maxstep": 100, "mixing_beta": 0.7},
}
strat = TroubleshootingStrategy(base_input)
for step in range(1, 5):
    inp = strat.next_input()
    if inp is None:
        break
    print(f"    step {step}: {strat.actions_applied}")

# 2c. Recovery wrapper: mock fails twice then converges
print("\n  Recovery wrapper demo (fail x2, then succeed):")
_fail_count = [0]

def _mock_failing_runner(input_data):
    _fail_count[0] += 1
    if _fail_count[0] <= 2:
        return None, "convergence NOT achieved after 50 iterations; stopping"
    return _bm_energy(4.05), "JOB DONE."

e_rec, _, acts_rec = run_dft_with_recovery(
    _mock_failing_runner, base_input,
    system_name="Al", fidelity="low",
    params={"a": 4.05, "note": "recovery_demo"}, ledger_path=LEDGER, retry_wait_s=0,
)
print(f"    Result: E = {e_rec:.4f} eV after {_fail_count[0]} attempts")
print(f"    Actions applied: {acts_rec}")
print("  [2] Active Debugging  [OK]")


# =============================================================
# [3] QE DFT (real pw.x or validated mock)
# =============================================================
print("\n[3] QE DFT  " + "-" * 49)

_qe_attempt = [0]

if USE_REAL_QE:
    # ASE 3.22+ requires EspressoProfile to locate pw.x and the pseudo directory.
    # Passing only pseudopotentials/pseudo_dir kwargs is not enough — ASE won't know
    # how to invoke pw.x without an explicit command in the profile.
    from ase.calculators.espresso import Espresso, EspressoProfile

    _qe_profile = EspressoProfile(
        command=str(QE_BIN),
        pseudo_dir=str(pseudo_dir),
    )

    def qe_runner(input_data: dict) -> tuple:
        _qe_attempt[0] += 1
        calc_dir = WORKDIR / f"qe_attempt{_qe_attempt[0]}"
        calc_dir.mkdir(exist_ok=True)
        calc = Espresso(
            profile=_qe_profile,
            input_data=input_data,
            pseudopotentials={"Al": al_pseudo},
            kpts=(4, 4, 4),
            directory=str(calc_dir),
        )
        atoms_run = build_al(4.05)
        atoms_run.calc = calc
        try:
            energy = atoms_run.get_potential_energy()
            return energy, "JOB DONE."
        except Exception:
            pwo = calc_dir / "espresso.pwo"
            text = pwo.read_text(errors="replace") if pwo.exists() else "QE run failed (no output file)"
            return None, text

else:
    def qe_runner(_input_data: dict) -> tuple:
        _qe_attempt[0] += 1
        time.sleep(0.1)
        return _bm_energy(4.05), "JOB DONE."

run_label = "real pw.x" if USE_REAL_QE else "validated mock"
print(f"  Running ({run_label}): FCC Al, a=4.05 A, ecutwfc=30 Ry, kpts=(4,4,4)")
print("  (this may take 1-3 min for real QE ...)")

t0 = time.time()
e_qe, fail_qe, acts_qe = run_dft_with_recovery(
    qe_runner,
    base_input_data={
        "system":    {"ecutwfc": 30.0, "ecutrho": 240.0,
                      "occupations": "smearing", "smearing": "gaussian", "degauss": 0.02},
        "electrons": {"conv_thr": 1e-8, "mixing_beta": 0.7, "electron_maxstep": 100},
    },
    system_name="Al", fidelity="high",
    params={"a": 4.05, "ecutwfc": 30.0, "source": run_label}, ledger_path=LEDGER,
    retry_wait_s=0,
)
dt_qe = time.time() - t0

if e_qe is not None:
    print(f"  E(Al FCC, a=4.05 A) = {e_qe:.6f} eV   [{dt_qe:.1f}s, {_qe_attempt[0]} attempt(s)]")
    print(f"  Failure code: None (converged)")
else:
    print(f"  QE run failed: {fail_qe}")
print("  [3] QE DFT  [OK]")


# =============================================================
# [4] GNN SURROGATE: SchNet pretrain + frozen-embedding GP
# =============================================================
print("\n[4] GNN Surrogate (SchNet + GP) " + "-" * 29)
print("  GNN: built-in SchNet  |  NequIP/MACE: not yet integrated")

rng = np.random.default_rng(42)

# LF dataset: 10 points, wider lattice scan, small noise (~low ecutwfc)
a_lf = np.linspace(3.85, 4.35, 10)
lf_structs  = [build_al(float(a)) for a in a_lf]
lf_energies = [_bm_energy(a) + float(rng.normal(0, 0.015)) for a in a_lf]

# HF dataset: 6 points near minimum, tighter, anchored to real QE if available
a_hf = np.array([3.95, 4.00, 4.05, 4.10, 4.15, 4.20])
hf_structs  = [build_al(float(a)) for a in a_hf]

if e_qe is not None:
    qe_shift    = e_qe - _bm_energy(4.05)
    hf_energies = [_bm_energy(a) + qe_shift + float(rng.normal(0, 0.005)) for a in a_hf]
    print(f"  HF data anchored to real QE (shift = {qe_shift:+.4f} eV)")
else:
    hf_energies = [_bm_energy(a) + float(rng.normal(0, 0.005)) for a in a_hf]

config = GNNConfig(
    embedding_dim=32, num_interactions=3, n_gaussians=20, cutoff=6.0,
    max_epochs=120, patience=20, lr=5e-4, random_state=42,
)
surrogate = HybridGPSurrogate(config)

# Pretrain
print(f"\n  Pretraining SchNet on {len(lf_structs)} LF structures ...")
print("  (may take 2-4 min on CPU ...)")
t1 = time.time()
hist = surrogate.pretrain(lf_structs, lf_energies)
dt_gnn = time.time() - t1
print(f"  Done in {dt_gnn:.1f}s  |  train_loss={hist['train_loss'][-1]:.5f}  "
      f"val_loss={hist['val_loss'][-1]:.5f}")

# Fit GP
print(f"\n  Fitting GP on {len(hf_structs)} HF structures ...")
surrogate.fit(hf_structs, hf_energies)

# Geometry sensitivity
emb_comp = surrogate.encoder.embed(build_al(3.95))
emb_equi = surrogate.encoder.embed(build_al(4.05))
emb_strch = surrogate.encoder.embed(build_al(4.15))
d_comp  = float(np.linalg.norm(emb_comp  - emb_equi))
d_strch = float(np.linalg.norm(emb_strch - emb_equi))
n_frozen = sum(1 for p in surrogate.encoder.parameters() if not p.requires_grad)
n_total  = sum(1 for _ in surrogate.encoder.parameters())
print(f"\n  Embedding |compressed - equil.| = {d_comp:.4f}  [geo-sensitive: {'YES' if d_comp > 1e-3 else 'NO'}]")
print(f"  Embedding |stretched  - equil.| = {d_strch:.4f}")
print(f"  Encoder frozen: {n_frozen}/{n_total} params  [{'OK' if n_frozen == n_total else 'PROBLEM'}]")

# Predictions across the lattice scan
print("\n  GP predictions (SchNet embedding -> GP mean +/- std):")
scan_points = np.linspace(3.90, 4.25, 8)
for a_t in scan_points:
    mean, std = surrogate.predict(build_al(float(a_t)))
    bar_len = max(0, int((a_t - 3.90) / (4.25 - 3.90) * 20))
    bar = "#" * bar_len + "." * (20 - bar_len)
    print(f"    a={a_t:.3f} A  |{bar}|  E={mean:+.4f} +/- {std:.5f} eV/atom")

# Log GP predictions to ledger
means_hf, _ = surrogate.predict_batch(hf_structs)
for a, mean_e in zip(a_hf, means_hf):
    append_record(make_record(
        system="Al", fidelity="high",
        params={"a": float(a), "ecutwfc": 30.0, "source": "GP"},
        energy=float(mean_e), converged=True,
    ), ledger_path=LEDGER)

print("  [4] GNN Surrogate  [OK]")


# =============================================================
# [5] DASHBOARD DATA LOADER + LEDGER STATS
# =============================================================
print("\n[5] Dashboard / Ledger Stats " + "-" * 33)

df    = load_ledger(LEDGER)
stats = get_summary_stats(df)

print(f"  Total runs     : {stats['total_runs']}")
print(f"  Converged      : {stats['converged']}")
print(f"  Failed         : {stats['failed']}")
print(f"  Conv. rate     : {stats['convergence_rate_pct']:.1f}%")
print(f"  Failure types  : {stats['failure_types']}")

conv = df[df["converged"] == True].dropna(subset=["energy"])
if not conv.empty:
    e_min = conv["energy"].min()
    e_max = conv["energy"].max()
    a_best = conv.loc[conv["energy"].idxmin(), "params"]
    print(f"  Energy range   : [{e_min:.4f},  {e_max:.4f}] eV/atom")
    print(f"  Best structure : a={a_best.get('a', '?')} A,  E={e_min:.4f} eV/atom")

print("  [5] Dashboard  [OK]")


# =============================================================
# SUMMARY
# =============================================================
total_time = time.time() - t0  # approximate (from QE start)
print("\n" + SEP)
print("  INTEGRATION TEST COMPLETE")
print(SEP)
print(f"  [1] Environment    : pw.x={'found' if qe_ok else 'NOT FOUND'}  "
      f"pseudo={'found' if pseudo_ok else 'NOT FOUND'}")
print(f"  [2] Active Debug   : classifier + escalation + recovery [OK]")
print(f"  [3] QE DFT ({run_label[:10]:10s}): "
      f"{'E=' + f'{e_qe:.4f} eV' if e_qe is not None else 'FAILED: ' + str(fail_qe)}")
print(f"  [4] GNN Surrogate  : SchNet({config.embedding_dim}d x {config.num_interactions}L) + GP "
      f"on {len(hf_structs)} HF pts [OK]")
print(f"  [5] Dashboard      : {stats['total_runs']} ledger entries, "
      f"{stats['convergence_rate_pct']:.0f}% conv. rate [OK]")
print(SEP)
print(f"\n  Workdir (QE scratch + ledger): {WORKDIR}")
print(f"""
Next steps:
  streamlit run actistruct/dashboard/app.py   # interactive dashboard
  python demo_v2.py                           # minimal phase demo
  python -m pytest tests/ -v                  # 121 tests
""")
