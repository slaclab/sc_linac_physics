"""Logger for EPICS utilities."""

from sc_linac_physics.utils.logger import custom_logger, BASE_LOG_DIR

# Lazy logger initialization
_logger = None


def get_logger():
    """Get or create the EPICS logger"""
    global _logger
    if _logger is None:
        _logger = custom_logger(
            "sc_linac_physics.utils.epics",
            log_dir=str(BASE_LOG_DIR / "epics"),
            log_filename="pv_operations",
        )
    return _logger
