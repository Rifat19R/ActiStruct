"""Shared helpers for TMC benchmark scripts: logging setup and config loading."""
from __future__ import annotations

import logging
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_yaml(relative_path: str) -> dict:
    path = PROJECT_ROOT / relative_path
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def setup_logger(name: str, log_filename: str) -> logging.Logger:
    log_path = PROJECT_ROOT / "logs" / log_filename
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger
