"""
Enhanced EPICS PV utilities with retry logic and batch operations.

This module provides a robust wrapper around PyEPICS with:
- Automatic retry logic for failed operations
- Thread-safe reconnection handling
- Batch operations for improved performance
- Comprehensive error handling
- Mock utilities for testing

Basic Usage:
    >>> from sc_linac_physics.utils.epics import PV
    >>> pv = PV("SOME:PV:NAME")
    >>> value = pv.get()
    >>> pv.put(42.0)

Batch Operations:
    >>> from sc_linac_physics.utils.epics import PV, PVBatch
    >>>
    >>> # Fast batch creation using PV class method
    >>> pvs = PV.batch_create(["PV:1", "PV:2", "PV:3"])
    >>>
    >>> # Low-level batch read (fastest for one-time operations)
    >>> values = PVBatch.get_values(["PV:1", "PV:2", "PV:3"])

Custom Configuration:
    >>> from sc_linac_physics.utils.epics import PV, PVConfig
    >>>
    >>> slow_config = PVConfig(
    ...     connection_timeout=10.0,
    ...     get_timeout=5.0,
    ...     put_timeout=60.0,
    ...     max_retries=5,
    ...     retry_delay=1.0
    ... )
    >>> pv = PV("SLOW:PV", config=slow_config)

Testing:
    >>> from sc_linac_physics.utils.epics.testing import make_mock_pv
    >>>
    >>> mock = make_mock_pv("TEST:PV", get_val=42.0)
    >>> assert mock.get() == 42.0
"""

# Batch operations
from .batch import PVBatch
from .config import (
    PVConfig,
    EPICS_NO_ALARM_VAL,
    EPICS_MINOR_VAL,
    EPICS_MAJOR_VAL,
    EPICS_INVALID_VAL,
)

# Core functionality
from .core import PV
from .exceptions import (
    PVConnectionError,
    PVGetError,
    PVPutError,
    PVInvalidError,
)

# Testing utilities
from .testing import make_mock_pv

# Utilities
from .utils import create_pv_safe, diagnose_pv_connection

__all__ = [
    # Core
    "PV",
    "PVConfig",
    # Constants
    "EPICS_NO_ALARM_VAL",
    "EPICS_MINOR_VAL",
    "EPICS_MAJOR_VAL",
    "EPICS_INVALID_VAL",
    # Exceptions
    "PVConnectionError",
    "PVGetError",
    "PVPutError",
    "PVInvalidError",
    # Batch operations
    "PVBatch",
    # Utilities
    "create_pv_safe",
    "diagnose_pv_connection",
    # Testing
    "make_mock_pv",
]

__version__ = "1.0.0"
