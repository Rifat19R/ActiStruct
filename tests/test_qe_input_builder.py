from pathlib import Path

import pytest

from _load import load_script
from _common import load_yaml

qe_mod = load_script("06_build_qe_inputs.py")
PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("win_path,expected", [
    ("D:/Rifat_kh/SSSP_1.3.0_PBE_efficiency", "/mnt/d/Rifat_kh/SSSP_1.3.0_PBE_efficiency"),
    (r"D:\Research\Dr.Kulik_MIT\qe\workdirs\ferrocene_initial",
     "/mnt/d/Research/Dr.Kulik_MIT/qe/workdirs/ferrocene_initial"),
])
def test_windows_to_wsl_path(win_path, expected):
    assert qe_mod.windows_to_wsl_path(win_path) == expected


def test_build_input_file_rejects_missing_pseudopotential(tmp_path):
    from ase import Atoms
    from ase.io import write

    atoms = Atoms(symbols=["Au"], positions=[[0.0, 0.0, 0.0]])
    xyz_path = tmp_path / "dummy.xyz"
    write(xyz_path, atoms, format="xyz")

    qe_cfg = load_yaml("configs/qe_molecule_settings.yaml")
    qe_cfg["qe"]["calculation"] = "relax"
    project_cfg = load_yaml("configs/project_config.yaml")
    empty_manifest = {"elements": {}}

    with pytest.raises(ValueError):
        qe_mod.build_input_file("dummy", xyz_path, qe_cfg, empty_manifest, project_cfg)


def test_generated_relax_inputs_exist_for_all_primary_systems():
    project_cfg = load_yaml("configs/project_config.yaml")
    for complex_id in project_cfg["systems"]["primary"]:
        in_path = PROJECT_ROOT / "qe" / "inputs" / "relax" / f"{complex_id}_initial.in"
        assert in_path.exists(), f"run scripts/06_build_qe_inputs.py first ({complex_id})"
        content = in_path.read_text(encoding="utf-8")
        assert "&CONTROL" in content
        assert "ATOMIC_POSITIONS" in content
        assert "K_POINTS gamma" in content
        assert f"prefix = '{complex_id}_initial'" in content
        assert "ibrav = 1" in content, "must use cubic ibrav, not ibrav=0 (DISCOURAGED, caused cr_co6 bfgs noise)"
        assert "celldm(1)" in content
        assert "CELL_PARAMETERS" not in content, "ibrav=1 uses celldm(1), not an explicit cell matrix"
        assert "trust_radius_min" in content, "needed so bfgs doesn't abort near-convergence (cr_co6 failure)"
