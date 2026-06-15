"""Generated workflow coverage tests that do not launch Quantum ESPRESSO."""

from __future__ import annotations

import importlib
from pathlib import Path
import sys

from ase import Atoms


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GENERATED_DIR = PROJECT_ROOT / "generated_models"
for path in (PROJECT_ROOT, GENERATED_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

HELPER_MODULES = {
    "__init__.py",
    "qe_active_inverse_common.py",
    "structure_builders.py",
}


def generated_workflow_modules() -> list[str]:
    modules = []
    for path in sorted(GENERATED_DIR.glob("*_active_inverse.py")):
        if path.name not in HELPER_MODULES:
            modules.append(f"generated_models.{path.stem}")
    return modules


def representative_params(system) -> tuple[float, ...]:
    params = []
    for variable in system.variables:
        assert variable.name
        assert variable.lo < variable.hi
        assert variable.initial
        for value in variable.initial:
            assert variable.lo <= value <= variable.hi
        params.append(variable.initial[0])
    return tuple(params)


def assert_system_is_valid(module_name: str) -> None:
    module = importlib.import_module(module_name)
    assert hasattr(module, "SYSTEM"), f"{module_name} does not define SYSTEM"
    system = module.SYSTEM

    assert system.key
    assert system.title
    assert callable(system.builder)
    assert 1 <= len(system.variables) <= 2
    assert system.pseudopotentials
    assert system.ecutwfc > 0
    assert system.ecutrho >= system.ecutwfc
    assert len(system.kpts) == 3
    assert all(isinstance(k, int) and k >= 1 for k in system.kpts)

    atoms = system.builder(*representative_params(system))
    assert isinstance(atoms, Atoms)
    assert len(atoms) > 0

    atom_symbols = set(atoms.get_chemical_symbols())
    pseudo_symbols = set(system.pseudopotentials)
    missing = pseudo_symbols - atom_symbols
    assert not missing, f"{module_name} pseudopotential symbols absent from built atoms: {sorted(missing)}"

    for element, pseudo in system.pseudopotentials.items():
        assert pseudo.lower().endswith(".upf"), f"{module_name} has non-UPF pseudo for {element}: {pseudo}"


def test_all_generated_workflows_import_and_build() -> None:
    modules = generated_workflow_modules()
    assert len(modules) == 51
    for module_name in modules:
        assert_system_is_valid(module_name)


if __name__ == "__main__":
    test_all_generated_workflows_import_and_build()
    print("Generated workflow tests passed.")
