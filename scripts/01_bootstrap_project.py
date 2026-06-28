"""Create/verify the project directory architecture. Idempotent and backup-safe.

Usage:
    python scripts/01_bootstrap_project.py
    python scripts/01_bootstrap_project.py --dry-run
    python scripts/01_bootstrap_project.py --force   # back up existing files before overwrite
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import PROJECT_ROOT, setup_logger  # noqa: E402

logger = setup_logger("bootstrap_project", "bootstrap.log")

DIRECTORIES = [
    "configs",
    "references/literature_notes",
    "references/raw_downloads",
    "structures/initial_xyz",
    "structures/generated_candidates",
    "structures/optimized_xyz",
    "structures/neb_endpoints",
    "qe/inputs/relax",
    "qe/inputs/scf",
    "qe/outputs/relax",
    "qe/outputs/scf",
    "qe/workdirs",
    "data/raw",
    "data/parsed",
    "data/processed",
    "data/features",
    "data/selected_batches",
    "models/baseline",
    "models/uncertainty",
    "reports/daily_logs",
    "reports/figures",
    "reports/tables",
    "reports/benchmark_reports",
    "scripts",
    "tests/fixtures",
    "logs",
]

README_DIRS = {
    "structures": "Molecular structures for the TMC benchmark: initial_xyz, generated_candidates, optimized_xyz, neb_endpoints.",
    "qe": "Quantum ESPRESSO inputs/outputs. pw.x runs via WSL at /home/duets/q-e-qe-7.4.1/bin/pw.x, not Windows PATH.",
    "data": "Dataset pipeline: raw -> parsed -> processed -> features -> selected_batches.",
    "models": "Trained surrogate/uncertainty models. Created only once enough labeled QE rows exist.",
    "reports": "Daily logs, figures, tables, and the benchmark report.",
    "references/literature_notes": "Manual literature notes backing reference_values_tmc_v0.yaml.",
    "references/raw_downloads": "Raw downloaded reference material. Use a manifest instead of committing large/copyrighted files.",
}


def backup_if_exists(path: Path) -> None:
    if path.exists():
        backup = path.with_suffix(path.suffix + ".bak")
        shutil.copy2(path, backup)
        logger.info("Backed up %s -> %s", path, backup)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="Back up and overwrite existing README files")
    args = parser.parse_args()

    for rel_dir in DIRECTORIES:
        target = PROJECT_ROOT / rel_dir
        if args.dry_run:
            logger.info("[dry-run] would ensure directory: %s", target)
            continue
        target.mkdir(parents=True, exist_ok=True)
        logger.info("Ensured directory: %s", target)

    for rel_dir, text in README_DIRS.items():
        readme_path = PROJECT_ROOT / rel_dir / "README.md"
        if args.dry_run:
            logger.info("[dry-run] would write: %s", readme_path)
            continue
        if readme_path.exists() and not args.force:
            logger.info("Skipping existing %s (use --force to overwrite)", readme_path)
            continue
        if readme_path.exists() and args.force:
            backup_if_exists(readme_path)
        readme_path.parent.mkdir(parents=True, exist_ok=True)
        readme_path.write_text(text + "\n", encoding="utf-8")
        logger.info("Wrote %s", readme_path)

    logger.info("Bootstrap complete (dry_run=%s, force=%s)", args.dry_run, args.force)
    return 0


if __name__ == "__main__":
    sys.exit(main())
