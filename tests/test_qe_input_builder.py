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


def test_load_selected_candidate_targets_matches_audit_csv():
    targets = qe_mod.load_selected_candidate_targets()
    assert len(targets) == 12
    system_counts = {}
    for candidate_id, system_id, xyz_path in targets:
        system_counts.setdefault(system_id, 0)
        system_counts[system_id] += 1
        assert xyz_path.exists(), f"{candidate_id}: missing structure {xyz_path}"
    assert system_counts == {"ferrocene": 3, "ni_co4": 3, "cr_co6": 3, "fe_co5": 3}


def test_generated_candidate_inputs_exist_and_are_well_formed():
    from _common import resolve_path
    project_cfg = load_yaml("configs/project_config.yaml")
    pseudo_dir_raw = project_cfg["paths"]["pseudo_dir"]
    pseudo_dir = Path(pseudo_dir_raw)
    pseudo_dir_resolved = resolve_path(pseudo_dir_raw)
    for candidate_id, system_id, _ in qe_mod.load_selected_candidate_targets():
        in_path = PROJECT_ROOT / "qe" / "inputs" / "relax" / f"{candidate_id}.in"
        assert in_path.exists(), f"run scripts/06_build_qe_inputs.py --source candidates first ({candidate_id})"
        content = in_path.read_text(encoding="utf-8")
        assert "ibrav = 1" in content
        assert f"prefix = '{candidate_id}'" in content
        if pseudo_dir_resolved.exists():
            assert qe_mod.validate_generated_input(in_path, pseudo_dir) == []


def test_validate_generated_input_catches_missing_ibrav(tmp_path):
    bad_input = tmp_path / "bad.in"
    bad_input.write_text(
        "&CONTROL\n  calculation = 'relax'\n/\n&SYSTEM\n  ibrav = 0\n/\n&IONS\n  trust_radius_min = 1e-6\n/\n"
        "ATOMIC_SPECIES\n  C  12.0  C.UPF\nATOMIC_POSITIONS (angstrom)\n  C  0.0  0.0  0.0\nK_POINTS gamma\n",
        encoding="utf-8")
    issues = qe_mod.validate_generated_input(bad_input, Path("."))
    assert any("ibrav" in i for i in issues)


def test_validate_generated_input_catches_mnt_outdir(tmp_path):
    bad_input = tmp_path / "bad.in"
    bad_input.write_text(
        "&CONTROL\n  calculation = 'relax'\n  outdir = '/mnt/d/foo'\n/\n&SYSTEM\n  ibrav = 1\n  celldm(1) = 10.0\n/\n"
        "&IONS\n  trust_radius_min = 1e-6\n/\nATOMIC_SPECIES\n  C  12.0  C.UPF\n"
        "ATOMIC_POSITIONS (angstrom)\n  C  0.0  0.0  0.0\nK_POINTS gamma\n",
        encoding="utf-8")
    issues = qe_mod.validate_generated_input(bad_input, Path("."))
    assert any("/mnt" in i for i in issues)


def test_validate_generated_input_catches_atom_overlap(tmp_path):
    bad_input = tmp_path / "bad.in"
    bad_input.write_text(
        "&CONTROL\n  calculation = 'relax'\n  outdir = '/home/x'\n/\n&SYSTEM\n  ibrav = 1\n  celldm(1) = 10.0\n/\n"
        "&IONS\n  trust_radius_min = 1e-6\n/\nATOMIC_SPECIES\n  C  12.0  C.UPF\n"
        "ATOMIC_POSITIONS (angstrom)\n  C  0.0  0.0  0.0\n  C  0.1  0.0  0.0\nK_POINTS gamma\n",
        encoding="utf-8")
    issues = qe_mod.validate_generated_input(bad_input, Path("."))
    assert any("overlap" in i for i in issues)


def test_validate_generated_input_catches_missing_pseudopotential_file(tmp_path):
    bad_input = tmp_path / "bad.in"
    bad_input.write_text(
        "&CONTROL\n  calculation = 'relax'\n  outdir = '/home/x'\n/\n&SYSTEM\n  ibrav = 1\n  celldm(1) = 10.0\n/\n"
        "&IONS\n  trust_radius_min = 1e-6\n/\nATOMIC_SPECIES\n  C  12.0  does_not_exist.UPF\n"
        "ATOMIC_POSITIONS (angstrom)\n  C  0.0  0.0  0.0\nK_POINTS gamma\n",
        encoding="utf-8")
    issues = qe_mod.validate_generated_input(bad_input, tmp_path)
    assert any("does_not_exist.UPF" in i for i in issues)


def test_validate_generated_input_passes_clean_file(tmp_path):
    (tmp_path / "C.UPF").write_text("dummy")
    good_input = tmp_path / "good.in"
    good_input.write_text(
        "&CONTROL\n  calculation = 'relax'\n  outdir = '/home/x'\n/\n&SYSTEM\n  ibrav = 1\n  celldm(1) = 10.0\n/\n"
        "&IONS\n  trust_radius_min = 1e-6\n/\nATOMIC_SPECIES\n  C  12.0  C.UPF\n"
        "ATOMIC_POSITIONS (angstrom)\n  C  0.0  0.0  0.0\n  C  5.0  0.0  0.0\nK_POINTS gamma\n",
        encoding="utf-8")
    assert qe_mod.validate_generated_input(good_input, tmp_path) == []


def test_pre_run_report_exists_and_lists_all_12_candidates():
    report_path = PROJECT_ROOT / "reports" / "pre_run_report_candidates_v0.md"
    assert report_path.exists(), "run scripts/06_build_qe_inputs.py --source candidates first"
    content = report_path.read_text(encoding="utf-8")
    assert "Total: 12 candidates, 4 systems." in content
    for candidate_id, _, _ in qe_mod.load_selected_candidate_targets():
        assert candidate_id in content


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
        assert "outdir = '/home/duets/qe_workdirs/" in content, \
            "outdir must stay on native WSL ext4, not the 9p-mounted D: drive (caused a real .save/ create-directory crash)"
        assert "/mnt/d" not in content.split("outdir")[1].split("\n")[0], "outdir must not point at the Windows-mounted drive"
