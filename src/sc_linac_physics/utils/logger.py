import atexit
import contextlib
import datetime
import json
import logging
import os
import sys
import threading
import time
import warnings
import weakref
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from sc_linac_physics.utils.platform_paths import get_log_base_dir

try:
    import fcntl
except ImportError:
    # Windows has no fcntl, so there is no file lock. Log files rotate
    # without one, as they did before.
    fcntl = None

BASE_LOG_DIR = get_log_base_dir()

# More readable format option
READABLE_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s"

# Default for custom_logger()'s old retry arguments, so it can tell an
# argument that was passed from one that wasn't.
_UNSET: Any = object()

# Track created loggers to avoid duplicates (using weak references to avoid memory leaks)
_created_loggers: dict[str, weakref.ref] = {}


@contextlib.contextmanager
def safe_umask(new_umask: int):
    """Context manager to temporarily set umask."""
    old_umask = os.umask(new_umask)
    try:
        yield
    finally:
        os.umask(old_umask)


class NameOverrideFilter(logging.Filter):
    """Filter that overrides the logger name in the record."""

    def __init__(self, display_name: str):
        super().__init__()
        self.display_name = display_name

    def filter(self, record: logging.LogRecord) -> bool:
        record.name = self.display_name
        return True


def _add_file_handlers(
    logger: logging.Logger,
    log_dir: Path,
    log_filename: str,
    level: int,
    max_bytes: int,
    backup_count: int,
) -> bool:
    """Add the .log and .jsonl handlers, creating log_dir if needed.

    umask 002 while creating, so new directories are 775 and new files 664.
    Existing permissions are left alone.

    Returns:
        False if log_dir or the files can't be created or opened. The logger
        then writes to the console only, for the life of the process.
    """
    handlers = []
    try:
        with safe_umask(0o002):
            log_dir.mkdir(parents=True, exist_ok=True)
        for create in (_create_text_file_handler, _create_json_file_handler):
            handlers.append(
                create(log_dir, log_filename, level, max_bytes, backup_count)
            )
    except Exception as e:
        for handler in handlers:
            handler.close()
        if isinstance(e, OSError):  # includes PermissionError
            logger.warning(
                f"File logging unavailable for '{log_dir}/{log_filename}', "
                f"console only: {e}"
            )
        else:
            logger.error(
                f"Unexpected error setting up file logging: {e}",
                exc_info=True,
            )
        return False
    for handler in handlers:
        logger.addHandler(handler)
    return True


# How long a write waits for another process's lock before writing unlocked.
LOG_LOCK_TIMEOUT_S = 1.0

# One thread lock per log file path, shared by every handler in this process
# that writes it. The file lock (flock) keeps other processes out, but not
# other threads in this one: over NFS, Linux turns flock into a POSIX lock,
# which only blocks other processes. So threads in this process wait here.
_path_locks: dict[str, threading.Lock] = {}
_path_locks_guard = threading.Lock()


def _path_lock(path: str) -> threading.Lock:
    with _path_locks_guard:
        return _path_locks.setdefault(path, threading.Lock())


class SharedRotatingFileHandler(RotatingFileHandler):
    """RotatingFileHandler for a file that several processes write.

    Every app that uses PV writes epics/pv_operations.log, and each cavity's
    cavity_N.log is written by whichever apps touch that cavity. A plain
    RotatingFileHandler checks the size and rotates in each process on its
    own. Two processes can rotate at once, so one renames over the other's
    backup. A process that didn't rotate keeps writing to the renamed file.

    Here each record is written like this:
    1. Take this file's thread lock, then an flock on <file>.lock.
    2. If the inode at the path isn't the open file's inode, another
       process rotated it, so reopen. Otherwise seek to the end, so the size
       check counts other processes' lines.
    3. RotatingFileHandler.emit: rotate if over max_bytes, then write.
    4. Close the lock file, which releases the flock.

    If the lock file can't be opened or the lock isn't free within
    LOG_LOCK_TIMEOUT_S, the record is written without it, as before.
    """

    def __init__(self, filename, *args, **kwargs):
        super().__init__(filename, *args, **kwargs)
        self.lock_path = self.baseFilename + ".lock"
        self._path_lock = _path_lock(self.baseFilename)

    def emit(self, record: logging.LogRecord) -> None:
        with self._path_lock:
            lock_fd = self._lock_file()
            try:
                self._follow_rotation()
                super().emit(record)
            finally:
                if lock_fd is not None:
                    os.close(lock_fd)

    def _lock_file(self) -> int | None:
        """Open <file>.lock and flock it. None if that isn't possible."""
        if fcntl is None:
            return None
        fd = self._open_lock_file()
        if fd is None:
            return None
        deadline = time.monotonic() + LOG_LOCK_TIMEOUT_S
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return fd
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    break
                time.sleep(0.01)
            except OSError:
                break
        os.close(fd)
        return None

    def _open_lock_file(self) -> int | None:
        try:
            fd = os.open(self.lock_path, os.O_RDWR | os.O_CREAT | os.O_EXCL)
        except FileExistsError:
            try:
                return os.open(self.lock_path, os.O_RDWR)
            except OSError:
                return None
        except OSError:
            return None
        # A lock file we just made: 664, so other group members can open it
        # read-write, which an exclusive lock needs on NFS.
        try:
            os.fchmod(fd, 0o664)
        except OSError:
            pass  # the lock still works for this user
        return fd

    def _follow_rotation(self) -> None:
        """Reopen if another process rotated the file, else seek to its end."""
        if self.stream is None:
            return  # RotatingFileHandler.emit opens it
        try:
            on_disk = os.stat(self.baseFilename)
            same = os.path.samestat(on_disk, os.fstat(self.stream.fileno()))
        except OSError:
            same = False
        if same:
            self.stream.seek(0, os.SEEK_END)
        else:
            self.stream.close()
            self.stream = self._open()


class ExtraDataMixin:
    """Mixin to add extra_data formatting capability."""

    def format_extra_data(self, record: logging.LogRecord) -> str:
        """Format extra_data as key=value pairs."""
        if not (hasattr(record, "extra_data") and record.extra_data):
            return ""

        extra_items = []
        for key, value in record.extra_data.items():
            if isinstance(value, str):
                extra_items.append(f"{key}='{value}'")
            elif isinstance(value, bool):
                extra_items.append(f"{key}={value}")
            elif isinstance(value, (int, float)):
                extra_items.append(f"{key}={value}")
            elif isinstance(value, dict):
                extra_items.append(f"{key}={json.dumps(value, default=str)}")
            else:
                extra_items.append(f"{key}={value}")

        return " | ".join(extra_items)


class ColoredFormatter(ExtraDataMixin, logging.Formatter):
    """Colored formatter for terminal output."""

    COLORS = {
        "DEBUG": "\033[36m",
        "INFO": "\033[32m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[1;31m",
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        record = logging.makeLogRecord(record.__dict__)
        log_color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{log_color}{record.levelname}{self.RESET}"
        result = super().format(record)

        extra_str = self.format_extra_data(record)
        if extra_str:
            result = f"{result} | {extra_str}"

        return result


class ExtendedFormatter(ExtraDataMixin, logging.Formatter):
    """Formatter that includes extra_data in human-readable format."""

    def format(self, record: logging.LogRecord) -> str:
        result = super().format(record)

        extra_str = self.format_extra_data(record)
        if extra_str:
            result = f"{result} | {extra_str}"

        return result


class JSONFormatter(logging.Formatter):
    """JSON formatter for file output (JSON Lines format)."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": datetime.datetime.fromtimestamp(
                record.created, datetime.UTC
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "message": record.getMessage(),
            "process": record.process,
            "thread": record.thread,
            "thread_name": record.threadName,
        }

        # Add extra fields if they exist
        if hasattr(record, "extra_data"):
            log_data["extra"] = record.extra_data

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # default=str: extra_data may hold Path, numpy, datetime values
        return json.dumps(log_data, ensure_ascii=False, default=str)


def _create_console_handler(level: int) -> logging.StreamHandler:
    """Create and configure console handler with colored formatter."""
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_formatter = ColoredFormatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(funcName)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(console_formatter)
    return console_handler


def _create_text_file_handler(
    log_dir_path: Path,
    log_filename: str,
    level: int,
    max_bytes: int,
    backup_count: int,
) -> SharedRotatingFileHandler:
    """Create and configure rotating text file handler."""
    text_file = log_dir_path / f"{log_filename}.log"

    with safe_umask(0o002):
        text_handler = SharedRotatingFileHandler(
            text_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )

    text_handler.setLevel(level)
    text_formatter = ExtendedFormatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    text_handler.setFormatter(text_formatter)
    return text_handler


def _create_json_file_handler(
    log_dir_path: Path,
    log_filename: str,
    level: int,
    max_bytes: int,
    backup_count: int,
) -> SharedRotatingFileHandler:
    """Create and configure rotating JSON Lines file handler."""
    jsonl_file = log_dir_path / f"{log_filename}.jsonl"

    with safe_umask(0o002):
        json_handler = SharedRotatingFileHandler(
            jsonl_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )

    json_handler.setLevel(level)
    json_handler.setFormatter(JSONFormatter())
    return json_handler


def _register_cleanup(logger: logging.Logger) -> None:
    """Register cleanup function to close handlers on exit."""

    def cleanup():
        for handler in logger.handlers[:]:
            try:
                handler.close()
            except Exception:
                pass  # Ignore errors during cleanup
            logger.removeHandler(handler)

    atexit.register(cleanup)


def custom_logger(
    name: str,
    log_filename: str,
    log_dir: str | Path = BASE_LOG_DIR,
    level: int = logging.DEBUG,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
    enable_retry: Any = _UNSET,
    retry_interval: Any = _UNSET,
    max_retries: Any = _UNSET,
) -> logging.Logger:
    """
    Create a logger with colored console output and dual file logging.

    Always writes to console. Attempts to write to files:
    - Console: Colored, human-readable (always)
    - {log_dir}/{log_filename}.log: Plain text, human-readable (with rotation)
    - {log_dir}/{log_filename}.jsonl: JSON Lines format (with rotation)

    If the files can't be opened when the logger is created, it logs one
    warning and writes to the console only from then on.

    Args:
        name: Logger name (typically __name__)
        log_dir: Directory for log files (str or Path)
        log_filename: Base filename without extension
        level: Logging level (default: DEBUG)
        max_bytes: Maximum file size before rotation (default: 10MB)
        backup_count: Number of backup files to keep (default: 5)
        enable_retry, retry_interval, max_retries: Deprecated and ignored,
            since file logging is no longer retried. Still accepted, by
            position or keyword, so old calls work. Passing any of them
            warns.

    Returns:
        Logger instance
    """
    if not log_filename:
        raise ValueError("log_filename cannot be empty")

    # Before the cache check, so a call that returns a cached logger warns too.
    passed = [
        arg
        for arg, value in (
            ("enable_retry", enable_retry),
            ("retry_interval", retry_interval),
            ("max_retries", max_retries),
        )
        if value is not _UNSET
    ]
    if passed:
        warnings.warn(
            f"custom_logger(): {passed} are ignored; "
            "file logging is no longer retried",
            DeprecationWarning,
            stacklevel=2,
        )

    # Normalize log_dir to Path for consistent handling
    log_dir = Path(log_dir)
    unique_logger_name = f"{name}#{log_dir}/{log_filename}"

    # Return existing logger if already created
    if unique_logger_name in _created_loggers:
        logger_ref = _created_loggers[unique_logger_name]
        logger = logger_ref()
        if logger is not None:
            return logger
        else:
            # Weak reference died, remove it
            del _created_loggers[unique_logger_name]

    logger = logging.getLogger(unique_logger_name)

    # If logger already has handlers, it was created elsewhere, return it
    if logger.handlers:
        _created_loggers[unique_logger_name] = weakref.ref(logger)
        return logger

    logger.setLevel(level)
    logger.propagate = False
    logger.addFilter(NameOverrideFilter(name))

    # Always add console handler first
    console_handler = _create_console_handler(level)
    logger.addHandler(console_handler)

    _add_file_handlers(
        logger, log_dir, log_filename, level, max_bytes, backup_count
    )

    # Register cleanup
    _register_cleanup(logger)

    # Store the logger using weak reference to avoid memory leaks
    _created_loggers[unique_logger_name] = weakref.ref(logger)

    return logger
