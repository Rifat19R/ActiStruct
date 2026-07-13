import numpy as np
import pytest

from _load import load_script

struct_mod = load_script("04_build_initial_structures.py")

EXPECTED_ATOM_COUNTS = {
    "ferrocene": 21,
    "ni_co4": 9,
    "cr_co6": 13,
    "fe_co5": 11,
}

@pytest.mark.parametrize("complex_id", list(EXPECTED_ATOM_COUNTS.keys()))
def test_atom_count_matches_formula(complex_id):
    builder, formula, _ = struct_mod.BUILDERS[complex_id]
    atoms = builder()
    assert len(atoms) == EXPECTED_ATOM_COUNTS[complex_id], f"{complex_id} ({formula})"


def test_ferrocene_symbol_counts():
    atoms = struct_mod.build_ferrocene()
    symbols = atoms.get_chemical_symbols()
    assert symbols.count("Fe") == 1
    assert symbols.count("C") == 10
    assert symbols.count("H") == 10


def test_ni_co4_is_tetrahedral_around_metal():
    atoms = struct_mod.build_ni_co4()
    positions = atoms.get_positions()
    ni_pos = positions[0]
    c_positions = positions[1::2]
    distances = np.linalg.norm(c_positions - ni_pos, axis=1)
    assert np.allclose(distances, distances[0], atol=1e-6)


def test_cr_co6_is_octahedral_around_metal():
    atoms = struct_mod.build_cr_co6()
    positions = atoms.get_positions()
    cr_pos = positions[0]
    c_positions = positions[1::2]
    distances = np.linalg.norm(c_positions - cr_pos, axis=1)
    assert np.allclose(distances, distances[0], atol=1e-6)
    assert len(c_positions) == 6


def test_fe_co5_has_two_axial_and_three_equatorial_carbons():
    atoms = struct_mod.build_fe_co5()
    positions = atoms.get_positions()
    fe_pos = positions[0]
    c_positions = positions[1::2]
    assert len(c_positions) == 5
    z_coords = c_positions[:, 2]
    axial = np.sum(np.abs(z_coords) > 1.0)
    equatorial = np.sum(np.abs(z_coords) < 1.0)
    assert axial == 2
    assert equatorial == 3


def test_no_overlapping_atoms_in_any_builder():
    for complex_id, (builder, _, _) in struct_mod.BUILDERS.items():
        atoms = builder()
        positions = atoms.get_positions()
        n = len(positions)
        for i in range(n):
            for j in range(i + 1, n):
                dist = np.linalg.norm(positions[i] - positions[j])
                assert dist > 0.5, f"{complex_id}: atoms {i},{j} overlap (dist={dist:.3f})"
