"""Helper to import numbered scripts/NN_name.py as modules (not valid identifiers for `import`)."""
import importlib.util
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


def load_script(filename: str):
    path = SCRIPTS_DIR / filename
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
