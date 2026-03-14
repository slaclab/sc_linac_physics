"""Shared utilities for tuning state command-line tools."""

import logging
import platform
import sqlite3
from collections.abc import Iterator, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import TypeVar

from sc_linac_physics.applications.tuning.tune_utils import TUNE_LOG_DIR
from sc_linac_physics.utils.logger import custom_logger

DEFAULT_DB_FILENAME = "tune_status.sqlite"
DEFAULT_JSON_FILENAME = "tune_status.json"
DEFAULT_LOG_FILENAME = "tune_status_poll.log"

_T = TypeVar("_T")


def _platform_default_paths(
    system_name: str,
    home_dir: Path,
) -> tuple[Path, Path, Path]:
    """Return (base_dir, db_path, json_path) for the active platform."""
    if system_name == "Linux":
        base_dir = Path("/home/physics/srf")
        return (
            base_dir,
            base_dir / "databases" / DEFAULT_DB_FILENAME,
            base_dir / DEFAULT_JSON_FILENAME,
        )

    return (
        home_dir,
        home_dir / "databases" / DEFAULT_DB_FILENAME,
        home_dir / DEFAULT_JSON_FILENAME,
    )


DEFAULT_BASE_DIR, DEFAULT_DB_PATH, DEFAULT_JSON_PATH = _platform_default_paths(
    platform.system(), Path.home()
)
DEFAULT_LOG_PATH = TUNE_LOG_DIR / DEFAULT_LOG_FILENAME


def now_utc_iso() -> str:
    """Return the current UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat()


def build_state_logger(
    name: str,
    log_path: Path,
    verbose: bool = False,
) -> logging.Logger:
    """Create a file-backed logger using the shared package logger utility."""
    return custom_logger(
        name=name,
        log_dir=log_path.parent,
        log_filename=log_path.stem,
        level=logging.DEBUG if verbose else logging.INFO,
    )


def connect_db(
    db_path: Path,
    *,
    row_factory: type[sqlite3.Row] | None = None,
) -> sqlite3.Connection:
    """Create a SQLite connection with consistent path setup."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    if row_factory is not None:
        conn.row_factory = row_factory
    return conn


def batched(items: Sequence[_T], batch_size: int) -> Iterator[Sequence[_T]]:
    """Yield fixed-size slices from a sequence."""
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")

    for start in range(0, len(items), batch_size):
        yield items[start : start + batch_size]


def resolve_db_path(base_dir: Path, db_path: Path | None = None) -> Path:
    """Resolve tuning-state SQLite database path from base dir and optional override."""
    if db_path:
        return db_path
    if base_dir == DEFAULT_BASE_DIR:
        return DEFAULT_DB_PATH
    return base_dir / DEFAULT_DB_FILENAME


def resolve_poll_paths(
    base_dir: Path,
    db_path: Path | None = None,
    json_path: Path | None = None,
    log_path: Path | None = None,
) -> tuple[Path, Path, Path]:
    """Resolve poller output file paths from base dir and optional overrides."""
    return (
        resolve_db_path(base_dir, db_path),
        json_path
        or (
            DEFAULT_JSON_PATH
            if base_dir == DEFAULT_BASE_DIR
            else base_dir / DEFAULT_JSON_FILENAME
        ),
        log_path or DEFAULT_LOG_PATH,
    )
