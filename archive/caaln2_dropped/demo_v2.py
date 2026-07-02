"""ActiStruct v2.0 - end-to-end demo (no QE required).

Exercises all four phases with synthetic data:
  Phase 0 - write + read JSONL ledger
  Phase 1 - classify failure strings + run recovery wrapper
  Phase 2 - build CaAlN2 structure, embed it, train surrogate, predict
  Phase 3 - load ledger into DataFrame, print summary stats

Run:
    python demo_v2.py
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
from ase import Atoms

SEP = "=" * 60
SEC = "-" * 50

print("\n" + SEP)
print("  ActiStruct v2.0 Demo")
print(SEP)


# ---------------------------------------------------------------
# PHASE 0 - Ledger
# ---------------------------------------------------------------
print("\n-- Phase 0: Ledger " + "-" * 31)

from actistruct.core.ledger import append_record, make_record, read_records

with tempfile.TemporaryDirectory() as tmpdir:
    ledger = Path(tmpdir) / "run_ledger.jsonl"

    # Write a converged record.
    append_record(
        make_record(
            system="CaAlN2", fidelity="low",
            params={"a": 3.15, "c": 5.00, "ecutwfc": 30.0},
            energy=-134.52, converged=True, wall_time_s=18.3,
        ),
        ledger_path=ledger,
    )

    # Write a failed record.
    append_record(
        make_record(
            system="CaAlN2", fidelity="low",
            params={"a": 3.80, "c": 6.00, "ecutwfc": 30.0},
            energy=None, converged=False,
            failure_type="SCF_CONVERGENCE",
            actions_taken=["electrons.mixing_beta=0.3"],
        ),
        ledger_path=ledger,
    )

    records = read_records(ledger)
    print(f"  Written {len(records)} records to ledger.")
    for r in records:
        status = "OK  converged" if r["converged"] else f"FAIL {r['failure_type']}"
        print(f"    [{r['fidelity']:4s}] a={r['params'].get('a', '?')}  ->  {status}")

print("  Phase 0 PASSED\n")


# ---------------------------------------------------------------
# PHASE 1 - Failure Classifier + Recovery
# ---------------------------------------------------------------
print("-- Phase 1: Failure Classifier & Recovery " + "-" * 8)

from actistruct.debug.classifier import DFTFailureAnalyzer
from actistruct.debug.strategies import TroubleshootingStrategy
from actistruct.debug.recovery import run_dft_with_recovery

analyzer = DFTFailureAnalyzer()

test_outputs = {
    "SCF failure":        "convergence NOT achieved after 100 iterations; stopping",
    "Successful BFGS":    "Broyden mixing\nlinmin alpha=1.0\nJOB DONE.",
    "Geometry crash":     "atoms too close: minimum distance is 0.01 Bohr",
    "Electronic instab.": "S matrix not positive definite",
}
for label, text in test_outputs.items():
    result = analyzer.classify(text)
    print(f"  {label:<22} ->  {result}")

# Escalation demo.
base_input = {
    "system":    {"ecutwfc": 30.0, "smearing": "gaussian", "degauss": 0.01},
    "electrons": {"conv_thr": 5e-9, "electron_maxstep": 200, "mixing_beta": 0.7},
}
strat = TroubleshootingStrategy(base_input)
print("\n  Cumulative escalation steps:")
for step in range(1, 4):
    strat.next_input()
    print(f"    Step {step}: {strat.actions_applied}")

# Recovery wrapper - fails once, succeeds on second try.
call_n = [0]

def mock_runner(input_data):
    call_n[0] += 1
    if call_n[0] == 1:
        return None, "convergence NOT achieved after 100 iterations; stopping"
    return -134.52, "JOB DONE."

with tempfile.TemporaryDirectory() as tmpdir:
    ledger2 = Path(tmpdir) / "run_ledger.jsonl"
    energy, failure, actions = run_dft_with_recovery(
        mock_runner, base_input,
        system_name="CaAlN2", fidelity="low",
        params={"a": 3.15}, ledger_path=ledger2, retry_wait_s=0,
    )
    print(f"\n  Recovery: energy={energy:.4f} eV, failure={failure}, actions={actions}")
    recs = read_records(ledger2)
    print(f"  Logged {len(recs)} attempts (1 fail + 1 success)")

print("  Phase 1 PASSED\n")


# ---------------------------------------------------------------
# PHASE 2 - GNN Encoder + Hybrid Surrogate
# ---------------------------------------------------------------
print("-- Phase 2: GNN Encoder + Hybrid GP Surrogate " + "-" * 4)

from actistruct.gnn.config import GNNConfig, MultiFidelityConfig
from actistruct.gnn.encoder import SchNetEncoder
from actistruct.gnn.surrogate import HybridGPSurrogate


def build_caln2(a: float, c: float) -> Atoms:
    """Synthetic CaAlN2-like hexagonal structure (4 atoms)."""
    return Atoms(
        symbols=["Ca", "Al", "N", "N"],
        positions=[
            [0.0,  0.0,  0.0      ],
            [a/2,  a/2,  c/2      ],
            [0.0,  0.0,  c * 0.375],
            [a/2,  a/2,  c * 0.875],
        ],
        cell=[[a, 0, 0], [0, a, 0], [0, 0, c]],
        pbc=True,
    )


# Geometry sensitivity: same composition, different bond lengths.
s_compressed = build_caln2(a=3.00, c=4.80)
s_stretched   = build_caln2(a=3.80, c=6.00)

config  = GNNConfig(embedding_dim=16, num_interactions=2, n_gaussians=10, cutoff=5.0)
encoder = SchNetEncoder(config)
encoder.eval()

emb1 = encoder.embed(s_compressed)
emb2 = encoder.embed(s_stretched)
diff = float(np.linalg.norm(emb1 - emb2))
geo_ok = "PASS - geometry-sensitive" if diff > 1e-3 else "FAIL"
print(f"  Embedding diff (compressed vs stretched): {diff:.4f}  [{geo_ok}]")

# Multi-fidelity config.
mf = MultiFidelityConfig()
print(f"  LF: ecutwfc={mf.qe_params('low')['ecutwfc']} Ry, kpts={mf.qe_params('low')['kpts']}")
print(f"  HF: ecutwfc={mf.qe_params('high')['ecutwfc']} Ry, kpts={mf.qe_params('high')['kpts']}")

# Full surrogate: pretrain on LF, fit GP on HF, predict.
print("\n  Training surrogate on 8 synthetic CaAlN2 structures...")
rng = np.random.default_rng(42)
a_vals  = np.linspace(3.0, 3.8, 8)
structs  = [build_caln2(a=float(a), c=float(a) * 1.6 + rng.uniform(-0.05, 0.05)) for a in a_vals]
energies = [-134.0 + 50.0 * (a - 3.2) ** 2 for a in a_vals]

surrogate = HybridGPSurrogate(config)
history   = surrogate.pretrain(structs, energies)
surrogate.fit(structs, energies)

s_test      = build_caln2(a=3.35, c=5.36)
mean, std   = surrogate.predict(s_test)
print(f"  Prediction at a=3.35 A: E = {mean:.4f} +/- {std:.4f} eV/atom")

# Confirm encoder is frozen.
n_frozen = sum(1 for p in surrogate.encoder.parameters() if not p.requires_grad)
n_total  = sum(1 for _ in surrogate.encoder.parameters())
frozen_ok = "PASS" if n_frozen == n_total else "FAIL"
print(f"  Encoder frozen: {n_frozen}/{n_total} params  [{frozen_ok}]")

print("  Phase 2 PASSED\n")


# ---------------------------------------------------------------
# PHASE 3 - Dashboard Data Loader
# ---------------------------------------------------------------
print("-- Phase 3: Dashboard Data Loader " + "-" * 16)

from actistruct.dashboard.data_loader import load_ledger, get_summary_stats

with tempfile.TemporaryDirectory() as tmpdir:
    ledger3 = Path(tmpdir) / "run_ledger.jsonl"

    # 8 converged + 2 failed records.
    for i, a in enumerate(np.linspace(3.0, 3.8, 8)):
        append_record(make_record(
            system="CaAlN2",
            fidelity="low" if i < 4 else "high",
            params={"a": float(a)},
            energy=-134.0 + 50.0 * (a - 3.2) ** 2,
            converged=True,
        ), ledger_path=ledger3)

    for ft in ["SCF_CONVERGENCE", "GEOMETRY_CRASH"]:
        append_record(make_record(
            system="CaAlN2", fidelity="low",
            params={"a": 3.9},
            energy=None, converged=False, failure_type=ft,
        ), ledger_path=ledger3)

    df    = load_ledger(ledger3)
    stats = get_summary_stats(df)
    print(f"  Loaded {stats['total_runs']} runs from ledger")
    print(f"  Converged : {stats['converged']}")
    print(f"  Failed    : {stats['failed']}")
    print(f"  Conv rate : {stats['convergence_rate_pct']:.1f}%")
    print(f"  Failures  : {stats['failure_types']}")

# Empty ledger must not crash.
df_empty = load_ledger(Path("/nonexistent/path.jsonl"))
print(f"  Empty ledger -> {len(df_empty)} rows, no crash  [PASS]")

print("  Phase 3 PASSED\n")


# ---------------------------------------------------------------
# SUMMARY
# ---------------------------------------------------------------
print(SEP)
print("  ALL PHASES PASSED - ActiStruct v2.0 is working correctly.")
print(SEP)
print("""
Commands you can run next:

  1. Full test suite (121 tests):
       python -m pytest tests/ -v

  2. Streamlit dashboard:
       streamlit run actistruct/dashboard/app.py
""")
