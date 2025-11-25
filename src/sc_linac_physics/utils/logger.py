import atexit
import contextlib
import datetime
import json
import logging
import os
import sys
import time
import weakref
from logging.handlers import RotatingFileHandler
from pathlib import Path
from threading import Lock
from typing import Any

if sys.platform == "darwin":  # macOS
    BASE_LOG_DIR = Path.home() / "logs"
else:  # Linux (production)
    BASE_LOG_DIR = Path("/home/physics/srf/logfiles")

# More readable format option
READABLE_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s"

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


class RetryFileHandlerFilter(logging.Filter):
    """Filter that retries adding file handlers if they're missing."""

    def __init__(self, logger_manager: "LoggerFileHandlerManager"):
        super().__init__()
        self.logger_manager = logger_manager
        self._last_check = 0.0
        self._check_interval = 5.0  # Only check every 5 seconds max
        self._in_retry = False  # Prevent recursive retry attempts

    def filter(self, record: logging.LogRecord) -> bool:
        # Prevent recursive calls during retry
        if self._in_retry:
            return True

        # Fast path: if we have handlers, skip
        if self.logger_manager.has_file_handlers:
            return True

        # Rate limit the retry checks
        current_time = time.time()
        if current_time - self._last_check < self._check_interval:
            return True

        self._last_check = current_time

        # Attempt to ensure file handlers
        try:
            self._in_retry = True
            self.logger_manager.ensure_file_handlers()
        finally:
            self._in_retry = False

        return True


class LoggerFileHandlerManager:
    """Manages file handlers with retry capability."""

    def __init__(
        self,
        logger: logging.Logger,
        log_dir: str | Path,
        log_filename: str,
        level: int,
        max_bytes: int,
        backup_count: int,
        retry_interval: int = 60,  # seconds between retries
        max_retries: int = -1,  # -1 means infinite retries
    ):
        self.logger = logger
        self.log_dir = Path(log_dir)
        self.log_filename = log_filename
        self.level = level
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.retry_interval = retry_interval
        self.max_retries = max_retries

        self.has_file_handlers = False
        self.retry_count = 0
        self.last_retry_time = 0.0
        self.lock = Lock()

    def has_active_file_handlers(self) -> bool:
        """Check if logger has active file handlers."""
        return any(
            isinstance(h, RotatingFileHandler) for h in self.logger.handlers
        )

    def ensure_file_handlers(self) -> bool:
        """
        Ensure file handlers exist, retry if necessary.

        Returns:
            True if file handlers exist or were successfully added.
        """
        # Always check actual handlers first (cheap operation)
        if self.has_active_file_handlers():
            self.has_file_handlers = True  # Sync the flag
            return True

        with self.lock:
            # Recheck after acquiring lock
            if self.has_active_file_handlers():
                self.has_file_handlers = True
                return True

            # Check if we should retry
            current_time = time.time()
            if current_time - self.last_retry_time < self.retry_interval:
                return False

            # Check max retries
            if 0 <= self.max_retries <= self.retry_count:
                return False

            self.last_retry_time = current_time
            self.retry_count += 1

            # Attempt to add file handlers
            success = self._add_file_handlers()

            if success:
                self.has_file_handlers = True
                self.logger.info(
                    f"File logging restored after {self.retry_count} attempt(s): "
                    f"{self.log_dir}/{self.log_filename}"
                )
            else:
                self.logger.debug(
                    f"Retry {self.retry_count}: File logging still unavailable"
                )

            return success

    def _ensure_log_directory(self) -> None:
        """
        Create log directory with appropriate permissions.

        Raises:
            PermissionError: If directory cannot be created or accessed.
        """
        with safe_umask(0o002):
            self.log_dir.mkdir(parents=True, exist_ok=True)

        if not self.log_dir.exists():
            raise PermissionError(f"Failed to create directory: {self.log_dir}")

        self._set_directory_permissions()

    def _set_directory_permissions(self) -> None:
        """
        Set directory permissions if we own it, otherwise verify write access.

        Raises:
            PermissionError: If directory is not writable.
        """
        try:
            stat_info = self.log_dir.stat()
            current_uid = os.getuid()

            if stat_info.st_uid == current_uid:
                # We own it, set permissions
                os.chmod(self.log_dir, 0o775)
            elif not os.access(self.log_dir, os.W_OK):
                # We don't own it and can't write
                raise PermissionError(
                    f"Directory '{self.log_dir}' is not writable "
                    f"(owned by uid {stat_info.st_uid}, running as uid {current_uid})"
                )
        except (PermissionError, OSError):
            # Final check: can we write?
            if not os.access(self.log_dir, os.W_OK):
                raise

    def _add_file_handlers(self) -> bool:
        """
        Attempt to add file handlers to logger.

        Returns:
            True if file handlers were successfully added, False otherwise.
        """
        try:
            self._ensure_log_directory()

            text_handler = _create_text_file_handler(
                self.log_dir,
                self.log_filename,
                self.level,
                self.max_bytes,
                self.backup_count,
            )
            self.logger.addHandler(text_handler)

            json_handler = _create_json_file_handler(
                self.log_dir,
                self.log_filename,
                self.level,
                self.max_bytes,
                self.backup_count,
            )
            self.logger.addHandler(json_handler)

            return True

        except (PermissionError, OSError) as e:
            # Log at debug level to avoid spam
            if self.retry_count == 1:  # Only warn on first failure
                self.logger.warning(
                    f"Cannot create log files in '{self.log_dir}': {e}"
                )
            return False

        except Exception as e:
            self.logger.error(
                f"Unexpected error setting up file logging: {e}",
                exc_info=True,
            )
            return False


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
                extra_items.append(f"{key}={json.dumps(value)}")
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

        return json.dumps(log_data, ensure_ascii=False)


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
) -> RotatingFileHandler:
    """Create and configure rotating text file handler."""
    text_file = log_dir_path / f"{log_filename}.log"

    # Set umask to ensure file is created with proper permissions
    with safe_umask(0o002):
        text_handler = RotatingFileHandler(
            text_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        # Explicitly set permissions on the file
        if text_file.exists():
            try:
                os.chmod(text_file, 0o664)
            except (PermissionError, OSError):
                pass  # Best effort

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
) -> RotatingFileHandler:
    """Create and configure rotating JSON Lines file handler."""
    jsonl_file = log_dir_path / f"{log_filename}.jsonl"

    # Set umask to ensure file is created with proper permissions
    with safe_umask(0o002):
        json_handler = RotatingFileHandler(
            jsonl_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        # Explicitly set permissions on the file
        if jsonl_file.exists():
            try:
                os.chmod(jsonl_file, 0o664)
            except (PermissionError, OSError):
                pass  # Best effort

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
    enable_retry: bool = True,
    retry_interval: int = 60,  # seconds
    max_retries: int = -1,  # -1 = infinite
) -> logging.Logger:
    """
    Create a logger with colored console output and dual file logging with retry.

    Always writes to console. Attempts to write to files:
    - Console: Colored, human-readable (always)
    - {log_dir}/{log_filename}.log: Plain text, human-readable (with rotation)
    - {log_dir}/{log_filename}.jsonl: JSON Lines format (with rotation)

    If file logging fails due to permissions, falls back to console-only logging
    and retries on subsequent log entries.

    Args:
        name: Logger name (typically __name__)
        log_dir: Directory for log files (str or Path)
        log_filename: Base filename without extension
        level: Logging level (default: DEBUG)
        max_bytes: Maximum file size before rotation (default: 10MB)
        backup_count: Number of backup files to keep (default: 5)
        enable_retry: Enable automatic retry of file handler creation (default: True)
        retry_interval: Seconds between retry attempts (default: 60)
        max_retries: Maximum retry attempts, -1 for infinite (default: -1)

    Returns:
        Logger instance
    """
    if not log_filename:
        raise ValueError("log_filename cannot be empty")

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

    # Create file handler manager
    handler_manager = LoggerFileHandlerManager(
        logger=logger,
        log_dir=log_dir,
        log_filename=log_filename,
        level=level,
        max_bytes=max_bytes,
        backup_count=backup_count,
        retry_interval=retry_interval,
        max_retries=max_retries,
    )

    # Try initial file handler creation
    initial_success = handler_manager.ensure_file_handlers()

    # Add retry filter if enabled and initial creation failed
    if enable_retry and not initial_success:
        retry_filter = RetryFileHandlerFilter(handler_manager)
        logger.addFilter(retry_filter)
        logger.warning(
            f"File logging unavailable for '{log_dir}/{log_filename}'. "
            f"Will retry every {retry_interval}s on new log entries."
        )

    # Register cleanup
    _register_cleanup(logger)

    # Store the logger using weak reference to avoid memory leaks
    _created_loggers[unique_logger_name] = weakref.ref(logger)

    return logger
