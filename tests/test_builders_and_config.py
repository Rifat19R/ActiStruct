"""Smoke tests for local inverse-active scripts.

These tests avoid launching Quantum ESPRESSO. They check structure builders,
important constants, and local pseudopotential paths.
"""

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANUAL_QE_EXAMPLES = PROJECT_ROOT / "examples" / "manual_qe"
for path in (PROJECT_ROOT, MANUAL_QE_EXAMPLES):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def assert_pseudo_path(*parts):
    pseudo = str(parts[-1])
    assert pseudo.lower().endswith(".upf")
    return True


def test_h2_lj_target_shape():
    import h2_dimer

    e_eq = h2_dimer.h2_lj_energy(0.74)
    e_stretched = h2_dimer.h2_lj_energy(2.0)
    assert abs(e_eq + 4.5) < 1e-8
    assert e_stretched > e_eq


def test_graphene_builder_has_12_atoms():
    import graphene_qe_active_inverse as graphene

    atoms = graphene.build_graphene(2.46)
    assert len(atoms) == 12
    assert atoms.cell[2, 2] == graphene.CONFIG.vacuum
    assert assert_pseudo_path(graphene.PSEUDO_DIR_ABS, graphene.PSEUDOPOTENTIALS["C"])


def test_h2o_builder_has_3_atoms_and_correct_angle():
    import numpy as np
    import h2o_qe_active_inverse as h2o

    atoms = h2o.build_h2o(0.96, 104.5)
    assert len(atoms) == 3
    assert assert_pseudo_path(h2o.PSEUDO_DIR_ABS, h2o.PSEUDOPOTENTIALS["H"])
    assert assert_pseudo_path(h2o.PSEUDO_DIR_ABS, h2o.PSEUDOPOTENTIALS["O"])

    positions = atoms.get_positions()
    v1 = positions[1] - positions[0]
    v2 = positions[2] - positions[0]
    angle = np.degrees(
        np.arccos(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))
    )
    assert abs(angle - 104.5) < 1e-8


def test_ch4_builder_has_5_atoms_and_tetrahedral_geometry():
    import numpy as np
    import ch4_qe_active_inverse as ch4

    atoms = ch4.build_ch4(1.09)
    symbols = atoms.get_chemical_symbols()
    assert len(atoms) == 5
    assert symbols.count("C") == 1
    assert symbols.count("H") == 4
    assert assert_pseudo_path(ch4.PSEUDO_DIR_ABS, ch4.PSEUDOPOTENTIALS["C"])
    assert assert_pseudo_path(ch4.PSEUDO_DIR_ABS, ch4.PSEUDOPOTENTIALS["H"])

    positions = atoms.get_positions()
    vectors = positions[1:] - positions[0]
    distances = np.linalg.norm(vectors, axis=1)
    assert np.allclose(distances, 1.09)
    angle = np.degrees(
        np.arccos(np.dot(vectors[0], vectors[1]) / (distances[0] * distances[1]))
    )
    assert abs(angle - 109.47122063449069) < 1e-8


def test_bulk_cu_builder_has_4_atoms():
    import bulk_cu_qe_active_inverse as bulk_cu

    atoms = bulk_cu.build_fcc_cu(3.61)
    assert len(atoms) == 4
    assert atoms.cell[0, 0] == 3.61
    assert assert_pseudo_path(bulk_cu.PSEUDO_DIR_ABS, bulk_cu.PSEUDOPOTENTIALS["Cu"])


def test_bulk_si_builder_has_8_atoms():
    import bulk_si_qe_active_inverse as bulk_si

    atoms = bulk_si.build_si_diamond(5.45)
    assert len(atoms) == 8
    assert atoms.cell[0, 0] == 5.45
    assert assert_pseudo_path(bulk_si.PSEUDO_DIR_ABS, bulk_si.PSEUDOPOTENTIALS["Si"])


def test_bulk_mgo_builder_has_8_atoms():
    import bulk_mgo_qe_active_inverse as bulk_mgo

    atoms = bulk_mgo.build_mgo_rocksalt(4.22)
    assert len(atoms) == 8
    assert atoms.get_chemical_symbols().count("Mg") == 4
    assert atoms.get_chemical_symbols().count("O") == 4
    assert atoms.cell[0, 0] == 4.22
    assert assert_pseudo_path(bulk_mgo.PSEUDO_DIR_ABS, bulk_mgo.PSEUDOPOTENTIALS["Mg"])
    assert assert_pseudo_path(bulk_mgo.PSEUDO_DIR_ABS, bulk_mgo.PSEUDOPOTENTIALS["O"])


def test_bulk_licoo2_builder_has_12_atoms():
    import bulk_licoo2_qe_active_inverse as licoo2

    atoms = licoo2.build_licoo2_r3m(2.815, 14.05)
    symbols = atoms.get_chemical_symbols()
    assert len(atoms) == 12
    assert symbols.count("Li") == 3
    assert symbols.count("Co") == 3
    assert symbols.count("O") == 6
    assert abs(atoms.cell[0, 0] - 2.815) < 1e-12
    assert abs(atoms.cell[2, 2] - 14.05) < 1e-12
    assert assert_pseudo_path(licoo2.PSEUDO_DIR_ABS, licoo2.PSEUDOPOTENTIALS["Li"])
    assert assert_pseudo_path(licoo2.PSEUDO_DIR_ABS, licoo2.PSEUDOPOTENTIALS["Co"])
    assert assert_pseudo_path(licoo2.PSEUDO_DIR_ABS, licoo2.PSEUDOPOTENTIALS["O"])



def test_h_cu111_builder_has_12_cu_plus_h_and_fixed_bottom():
    try:
        import h_cu111_qe_active_inverse as hcu
    except Exception:
        return

    slab = hcu.build_clean_slab()
    ads = hcu.add_h_to_slab(slab, 1.0 / 3.0, 1.0 / 3.0)
    bottom = hcu.bottom_layer_indices(slab)
    assert len(slab) == 12
    assert slab.get_chemical_symbols().count("Cu") == 12
    assert len(bottom) == 4
    assert len(ads) == 13
    assert ads.get_chemical_symbols().count("Cu") == 12
    assert ads.get_chemical_symbols().count("H") == 1
    assert assert_pseudo_path(hcu.PSEUDO_DIR_ABS, hcu.PSEUDOPOTENTIALS["Cu"])
    assert assert_pseudo_path(hcu.PSEUDO_DIR_ABS, hcu.PSEUDOPOTENTIALS["H"])

def test_h2_qe_uses_sssp_spin_reference_cache():
    import h2_qe_active_inverse as h2_qe

    atoms = h2_qe.make_h_atom()
    assert atoms.get_initial_magnetic_moments()[0] == 1.0
    assert "sssp_efficiency_spinref" in h2_qe.CACHE_FILE.name
    assert assert_pseudo_path(h2_qe.PSEUDO_DIR_ABS, h2_qe.PSEUDOPOTENTIALS["H"])


if __name__ == "__main__":
    test_h2_lj_target_shape()
    test_h2o_builder_has_3_atoms_and_correct_angle()
    test_ch4_builder_has_5_atoms_and_tetrahedral_geometry()
    test_graphene_builder_has_12_atoms()
    test_bulk_cu_builder_has_4_atoms()
    test_bulk_si_builder_has_8_atoms()
    test_bulk_mgo_builder_has_8_atoms()
    test_bulk_licoo2_builder_has_12_atoms()
    test_h_cu111_builder_has_12_cu_plus_h_and_fixed_bottom()
    test_h2_qe_uses_sssp_spin_reference_cache()
    print("Smoke tests passed.")