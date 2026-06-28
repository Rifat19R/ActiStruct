"""Inspect the local environment: Python, actistruct import, pw.x, pseudopotentials.

Usage:
    python scripts/00_inspect_environment.py
    python scripts/00_inspect_environment.py --dry-run
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import PROJECT_ROOT, load_yaml, setup_logger  # noqa: E402

logger = setup_logger("inspect_environment", "bootstrap.log")


def check_actistruct_import() -> dict:
    result = {"package": None, "version": None, "location": None, "importable": False}
    for candidate in ("actistruct", "inverse_active"):
        spec = importlib.util.find_spec(candidate)
        if spec is not None:
            try:
                module = importlib.import_module(candidate)
                result["package"] = candidate
                result["version"] = getattr(module, "__version__", "unknown")
                result["location"] = getattr(module, "__file__", spec.origin)
                result["importable"] = True
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Found spec for %s but import failed: %s", candidate, exc)
            break
    return result


def check_pwx(qe_cfg: dict) -> dict:
    result = {
        "on_windows_path": shutil.which("pw.x") is not None,
        "wsl_path": qe_cfg["qe"]["pwx_path_wsl"],
        "wsl_path_exists": False,
        "wsl_runs": False,
    }
    try:
        proc = subprocess.run(
            ["wsl", "-e", "bash", "-lc", f"test -x '{result['wsl_path']}' && echo OK"],
            capture_output=True, text=True, timeout=20,
        )
        result["wsl_path_exists"] = proc.stdout.strip() == "OK"
        if result["wsl_path_exists"]:
            proc2 = subprocess.run(
                ["wsl", "-e", "bash", "-lc", f"'{result['wsl_path']}' -v"],
                capture_output=True, text=True, timeout=20,
            )
            result["wsl_runs"] = "PWSCF" in proc2.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        logger.warning("Could not query WSL for pw.x: %s", exc)
    return result


def check_pseudo_dir(pseudo_dir: str, required_elements: list[str]) -> dict:
    pdir = Path(pseudo_dir)
    result = {"pseudo_dir": pseudo_dir, "exists": pdir.exists(), "elements_found": {}}
    if not pdir.exists():
        return result
    files_lower = {f.name.lower(): f.name for f in pdir.iterdir() if f.is_file()}
    for element in required_elements:
        prefix = element.lower()
        matches = [
            orig for low, orig in files_lower.items()
            if low.startswith(prefix + ".") or low.startswith(prefix + "_")
        ]
        result["elements_found"][element] = matches
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Print report, do not write files")
    args = parser.parse_args()

    logger.info("Starting environment inspection")

    report = {
        "python_version": sys.version,
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "cwd": str(Path.cwd()),
        "project_root": str(PROJECT_ROOT),
    }

    actistruct_info = check_actistruct_import()
    report["actistruct"] = actistruct_info
    if actistruct_info["importable"]:
        logger.info("actistruct importable: %s (v%s) at %s",
                     actistruct_info["package"], actistruct_info["version"], actistruct_info["location"])
    else:
        logger.error("Neither 'actistruct' nor 'inverse_active' is importable in this environment.")

    qe_cfg = load_yaml("configs/project_config.yaml")
    pwx_info = check_pwx(qe_cfg)
    report["pwx"] = pwx_info
    if pwx_info["wsl_runs"]:
        logger.info("pw.x confirmed runnable via WSL at %s", pwx_info["wsl_path"])
    else:
        logger.warning("pw.x not confirmed runnable. Windows PATH: %s, WSL path exists: %s",
                        pwx_info["on_windows_path"], pwx_info["wsl_path_exists"])

    qe_mol_cfg = load_yaml("configs/qe_molecule_settings.yaml")
    required_elements = qe_mol_cfg["required_elements_phase1"]
    pseudo_info = check_pseudo_dir(qe_cfg["paths"]["pseudo_dir"], required_elements)
    report["pseudopotentials"] = pseudo_info
    missing = [el for el, matches in pseudo_info["elements_found"].items() if not matches]
    if missing:
        logger.warning("Missing pseudopotentials for elements: %s", missing)
    else:
        logger.info("All required elements have at least one pseudopotential candidate.")

    print(json.dumps(report, indent=2))

    if args.dry_run:
        logger.info("Dry run: not writing environment_report.json")
        return 0

    out_path = PROJECT_ROOT / "reports" / "tables" / "environment_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("Wrote %s", out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
