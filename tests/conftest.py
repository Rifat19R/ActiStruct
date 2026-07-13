import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
TESTS_DIR = Path(__file__).resolve().parent

# _load.py lives in tests/; add tests/ so it is importable even when pytest
# treats the package as tests.* (i.e. when tests/__init__.py is present).
sys.path.insert(0, str(TESTS_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))
