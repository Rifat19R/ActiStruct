import csv

import numpy as np

from _load import load_script
from _common import PROJECT_ROOT

pert_mod = load_script("05_generate_perturbation_candidates.py")

EXPECTED_COUNTS = {
    "ferrocene": 12,
    "ni_co4": 12,
    "cr_co6": 12,
    "fe_co5": 16,
}


def test_each_complex_within_phase1_candidate_range():
    for complex_id, (builder, formula, variables) in pert_mod.COMPLEXES.items():
        candidates = pert_mod.generate_candidates(complex_id, builder, formula, variables)
        assert len(candidates) == EXPECTED_COUNTS[complex_id], complex_id
        assert 10 <= len(candidates) <= 20, f"{complex_id} outside 10-20 phase-1 range"


def test_candidates_preserve_atom_count_of_baseline():
    baseline_mod = load_script("04_build_initial_structures.py")
    for complex_id, (builder, formula, variables) in pert_mod.COMPLEXES.items():
        baseline_atoms = baseline_mod.BUILDERS[complex_id][0]()
        candidates = pert_mod.generate_candidates(complex_id, builder, formula, variables)
        for cand in candidates:
            assert len(cand["atoms"]) == len(baseline_atoms), cand["candidate_id"]


def test_candidates_have_no_overlapping_atoms():
    for complex_id, (builder, formula, variables) in pert_mod.COMPLEXES.items():
        candidates = pert_mod.generate_candidates(complex_id, builder, formula, variables)
        for cand in candidates:
            positions = cand["atoms"].get_positions()
            n = len(positions)
            for i in range(n):
                for j in range(i + 1, n):
                    dist = np.linalg.norm(positions[i] - positions[j])
                    assert dist > 0.4, f"{cand['candidate_id']}: atoms {i},{j} overlap (dist={dist:.3f})"


def test_candidate_ids_are_unique():
    all_ids = []
    for complex_id, (builder, formula, variables) in pert_mod.COMPLEXES.items():
        candidates = pert_mod.generate_candidates(complex_id, builder, formula, variables)
        all_ids.extend(c["candidate_id"] for c in candidates)
    assert len(all_ids) == len(set(all_ids))


def test_candidate_manifest_csv_matches_generated_candidates():
    manifest_path = PROJECT_ROOT / "data" / "raw" / "candidate_manifest_v0.csv"
    assert manifest_path.exists(), "run scripts/05_generate_perturbation_candidates.py first"
    with manifest_path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == sum(EXPECTED_COUNTS.values())
    required_columns = {"candidate_id", "complex_id", "formula", "charge", "spin_setting",
                         "structure_path", "generation_method", "variables_json", "notes"}
    assert required_columns.issubset(rows[0].keys())
    for row in rows:
        assert row["charge"] == "0"
