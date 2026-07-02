# Archived: CaAlN2 as ActiStruct Phase 2 Target

**Dropped:** 2026-07-02  
**Reason:** CaAlN2 never connected to either active project objective
(JOSS submission or MXene HER research). It was pulled from an early
draft blueprint as a convenient hexagonal nitride test case and was
never a committed research target. Using it as the Phase 2 GNN/multi-
fidelity development target would have tested generic surrogate mechanics
at the cost of DFT time on a system unrelated to the actual science.

**Replacement target:** Ti3C2-O (O-terminated MXene), part of the
Ti3C2 / V2C HER study that is the actual MXene research objective.

## What is archived here

- `demo_v2.py` — end-to-end ActiStruct v2 demo using synthetic CaAlN2
  structures. Useful as a reference for the GNN/GP surrogate mechanics
  (training loop, HF anchor, ledger integration). The code is generic;
  only the structure builder and system_name are CaAlN2-specific.

- `verify_gnn_claims.py` — explicit numerical verification script for
  permutation invariance, geometry sensitivity, and R2. Used during
  Phase 2 development to confirm the SchNet encoder worked. The
  verification patterns are valid for any system; the CaAlN2 geometry
  was just the convenient test case.

## What was NOT archived

Generic library code (ledger.py, classifier.py, strategies.py,
surrogate.py, encoder.py, data_loader.py) was only TESTED using CaAlN2
as a convenient synthetic structure. It is system-agnostic and stays in
the active codebase unchanged. References to "CaAlN2" in those files
were changed to generic strings (system_name="test_material") or removed
from docstring examples.

## Production ledger path (outside repo)

/home/alchemist/actistruct_data/CaAlN2/

This directory on the native Linux filesystem may contain a campaign.jsonl
from any partial CaAlN2 runs. It is NOT deleted here — review and clean
up manually if disk space is a concern. The directory path will no longer
appear in any active script or config after this archive commit.

## Geometry-sensitivity test

The GNN geometry-sensitivity test used a CaAlN2-like 4-atom hexagonal
structure (Ca/Al/N2). The test logic (two structures with different bond
lengths -> embeddings differ) is generic and was kept in
tests/test_hybrid_surrogate.py as a generic synthetic structure test,
renamed from _make_hexagonal_nitride() to _make_test_slab().
