import atexit
import datetime
import json
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

if sys.platform == "darwin":  # macOS
    BASE_LOG_DIR = Path.home() / "logs"
else:  # Linux (production)
    BASE_LOG_DIR = Path("/home/physics/srf/logfiles")

# More readable format option
READABLE_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s"

# Track created loggers to avoid duplicates
_created_loggers = {}


class NameOverrideFilter(logging.Filter):
    """Filter that overrides the logger name in the record."""

    def __init__(self, display_name: str):
        super().__init__()
        self.display_name = display_name

    def filter(self, record):
        record.name = self.display_name
        return True


class ExtraDataMixin:
    """Mixin to add extra_data formatting capability."""

    def format_extra_data(self, record):
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

    def format(self, record):
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

    def format(self, record):
        result = super().format(record)

        extra_str = self.format_extra_data(record)
        if extra_str:
            result = f"{result} | {extra_str}"

        return result


class JSONFormatter(logging.Formatter):
    """JSON formatter for file output (JSON Lines format)."""

    def format(self, record):
        log_data = {
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


def custom_logger(
    name: str,
    log_filename: str,
    log_dir: str = BASE_LOG_DIR,
    level: int = logging.DEBUG,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
) -> logging.Logger:
    """
    Create a logger with colored console output and dual file logging.

    Always writes to three destinations:
    - Console: Colored, human-readable
    - {log_dir}/{log_filename}.log: Plain text, human-readable (with rotation)
    - {log_dir}/{log_filename}.jsonl: JSON Lines format (with rotation)

    Args:
        name: Logger name (typically __name__)
        log_dir: Directory for log files
        log_filename: Base filename without extension
        level: Logging level (default: DEBUG)
        max_bytes: Maximum file size before rotation (default: 10MB)
        backup_count: Number of backup files to keep (default: 5)

    Returns:
        Logger instance
    """

    # Validate inputs
    if not log_filename:
        raise ValueError("log_filename cannot be empty")

    # Use log path to make logger unique
    unique_logger_name = f"{name}#{log_dir}/{log_filename}"

    # Return existing logger if already created
    if unique_logger_name in _created_loggers:
        return _created_loggers[unique_logger_name]

    logger = logging.getLogger(unique_logger_name)

    # If logger already has handlers, it was created elsewhere, return it
    if logger.handlers:
        _created_loggers[unique_logger_name] = logger
        return logger

    logger.setLevel(level)
    logger.propagate = False

    # Add name override filter
    logger.addFilter(NameOverrideFilter(name))

    # Ensure log directory exists
    log_dir_path = Path(log_dir)
    log_dir_path.mkdir(parents=True, exist_ok=True)

    # Console handler - colored
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_formatter = ColoredFormatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(funcName)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # Rotating text file handler with ExtendedFormatter
    text_file = log_dir_path / f"{log_filename}.log"
    text_handler = RotatingFileHandler(
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
    logger.addHandler(text_handler)

    # Rotating JSON Lines file handler
    jsonl_file = log_dir_path / f"{log_filename}.jsonl"
    json_handler = RotatingFileHandler(
        jsonl_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    json_handler.setLevel(level)
    json_handler.setFormatter(JSONFormatter())
    logger.addHandler(json_handler)

    # Register cleanup on exit
    def cleanup():
        for handler in logger.handlers[:]:
            handler.close()
            logger.removeHandler(handler)

    atexit.register(cleanup)

    # Store the logger
    _created_loggers[unique_logger_name] = logger

    return logger
