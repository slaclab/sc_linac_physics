import datetime
import json
import logging
import sys
from pathlib import Path

# More readable format option
READABLE_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s"

if sys.platform == "darwin":  # macOS
    BASE_LOG_DIR = Path.home() / "logs"
else:  # Linux (production)
    BASE_LOG_DIR = Path("/home/physics/srf/logfiles")


class ColoredFormatter(logging.Formatter):
    """Colored formatter for terminal output."""

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[1;31m",  # Bold Red
    }
    RESET = "\033[0m"

    def format(self, record):
        # Make a copy to avoid modifying the original record
        record = logging.makeLogRecord(record.__dict__)
        log_color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{log_color}{record.levelname}{self.RESET}"
        return super().format(record)


class JSONFormatter(logging.Formatter):
    """JSON formatter for file output (JSON Lines format)."""

    def format(self, record):
        log_data = {
            "timestamp": datetime.datetime.fromtimestamp(
                record.created
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_data)


def custom_logger(
    name: str,
    log_dir: str,
    log_filename: str,
    level: int = logging.DEBUG,
) -> logging.Logger:
    """
    Create a logger with colored console output and dual file logging.

    Always writes to three destinations:
    - Console: Colored, human-readable
    - {log_dir}/{log_filename}.log: Plain text, human-readable
    - {log_dir}/{log_filename}.jsonl: JSON Lines format (one JSON object per line)

    Args:
        name: Logger name (typically __name__)
        log_dir: Directory for log files (required)
        log_filename: Base filename without extension (required)
        level: Logging level (default: DEBUG)

    Returns:
        Logger instance
    """
    # Use log path to make logger unique, but keep name clean for display
    unique_logger_name = f"{name}#{log_dir}/{log_filename}"
    logger = logging.getLogger(unique_logger_name)

    # Override the name attribute to display the clean name
    logger.name = name

    if logger.handlers:
        return logger

    logger.setLevel(level)
    logger.propagate = False

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

    # Readable text file handler
    text_file = log_dir_path / f"{log_filename}.log"
    text_handler = logging.FileHandler(text_file, encoding="utf-8")
    text_handler.setLevel(level)
    text_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    text_handler.setFormatter(text_formatter)
    logger.addHandler(text_handler)

    # JSON Lines file handler
    jsonl_file = log_dir_path / f"{log_filename}.jsonl"
    json_handler = logging.FileHandler(jsonl_file, encoding="utf-8")
    json_handler.setLevel(level)
    json_handler.setFormatter(JSONFormatter())
    logger.addHandler(json_handler)

    return logger


# Usage examples:
if __name__ == "__main__":
    # Both directory and filename required
    log1 = custom_logger(__name__, log_dir="logs", log_filename="app")
    log1.info("Application logs")
    log1.debug("Debug message")

    print("\n" + "=" * 80 + "\n")

    # Database logs
    log2 = custom_logger(__name__, log_dir="logs", log_filename="database")
    log2.info("Database logs")
    log2.warning("Connection slow")

    print("\n" + "=" * 80 + "\n")

    # API logs in different directory
    log3 = custom_logger(__name__, log_dir="api_logs", log_filename="requests")
    log3.info("API request logs")
    log3.error("Request failed")

    print("\n" + "=" * 80 + "\n")

    # Nested directories
    log4 = custom_logger(
        __name__, log_dir="logs/2024/january", log_filename="sales"
    )
    log4.info("Nested directory structure")

    print("\n" + "=" * 80 + "\n")

    # Different log level
    log5 = custom_logger(
        __name__, log_dir="logs", log_filename="errors", level=logging.ERROR
    )
    log5.debug("This won't be logged")
    log5.info("This won't be logged either")
    log5.error("Only errors and above")

    print("\n" + "=" * 80 + "\n")

    # Test exception logging
    log6 = custom_logger(__name__, log_dir="logs", log_filename="exceptions")
    try:
        result = 1 / 0
    except Exception:
        log6.exception("An error occurred with traceback")

    print("\n✅ Check the log directories:")
    print("   - logs/app.{log,jsonl}")
    print("   - logs/database.{log,jsonl}")
    print("   - api_logs/requests.{log,jsonl}")
    print("   - logs/2024/january/sales.{log,jsonl}")
    print("   - logs/errors.{log,jsonl}")
    print("   - logs/exceptions.{log,jsonl}")

    print("\n📖 Reading JSONL file:")
    print("=" * 80)
    with open("logs/app.jsonl", "r") as f:
        for line in f:
            log_entry = json.loads(line)
            print(
                f"{log_entry['timestamp']} | {log_entry['level']:8} | {log_entry['logger']} | {log_entry['message']}"
            )
