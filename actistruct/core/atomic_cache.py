"""Atomic file-lock cache utilities.

Extracted verbatim from qe_active_inverse_common.py so new v2 modules can
share the same battle-tested locking pattern without duplicating it.

Lock mechanism: os.O_CREAT | os.O_EXCL atomic file creation.
This is NTFS-safe (drvfs via WSL2 does not reliably support fcntl/flock).
Do NOT replace this with fcntl, flock, or SQLite writes from concurrent workers.
"""
from __future__ import annotations

import os
import pickle
import time
from pathlib import Path


def acquire_lock(lock_path: Path, timeout: float = 600.0, poll: float = 0.1) -> int:
    """Spin-wait until we atomically create the lock file; return its file descriptor."""
    start = time.time()
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_RDWR)
            os.write(fd, str(os.getpid()).encode())
            return fd
        except FileExistsError:
            if time.time() - start > timeout:
                raise TimeoutError(f"Cache lock timeout: {lock_path}")
            time.sleep(poll)


def release_lock(fd: int, lock_path: Path) -> None:
    """Close the lock file descriptor and delete the lock file."""
    try:
        os.close(fd)
    finally:
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def load_cache(cache_path: Path) -> dict:
    """Load the pickle cache from disk. Returns empty dict if not found."""
    if not cache_path.exists():
        return {}
    with cache_path.open("rb") as f:
        return pickle.load(f)


def save_cache(cache_path: Path, data: dict) -> None:
    """Atomically write cache dict to disk via a .tmp rename."""
    tmp = cache_path.with_suffix(".tmp")
    with tmp.open("wb") as f:
        pickle.dump(data, f)
    os.replace(tmp, cache_path)


def get_cached(cache_path: Path, lock_path: Path, key: str) -> float | None:
    """Thread/process-safe read of one key from the cache. Returns None if missing."""
    fd = acquire_lock(lock_path)
    try:
        return load_cache(cache_path).get(key)
    finally:
        release_lock(fd, lock_path)


def set_cached(cache_path: Path, lock_path: Path, key: str, value: float) -> None:
    """Thread/process-safe write of one key into the cache."""
    fd = acquire_lock(lock_path)
    try:
        data = load_cache(cache_path)
        data[key] = float(value)
        save_cache(cache_path, data)
    finally:
        release_lock(fd, lock_path)
