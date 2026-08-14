"""
Smart archiver routing wrapper.

Public API:
- get_values_over_time_range(...)

Routing:
- If SC_ARCHIVER_MOCK=1 -> always mock
- Else -> real archiver (errors propagate; NO mock fallback)

When SC_ARCHIVER_MOCK=1, importing this package also installs a PyDM patch so
archiver time plots are fed by the mock generator without any display edits.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Dict, List

from .models import ArchiveDataHandler, ArchiverValue
from .mock import mock_get_values_over_time_range, PVProfile, PROFILE_STORE
from .client import (
    real_get_values_over_time_range,
    is_archiver_available,
    ArchiverConnectionError,
    ArchiverTimeoutError,
    ArchiverError,
)

__all__ = [
    "ArchiveDataHandler",
    "ArchiverValue",
    "ArchiverError",
    "ArchiverTimeoutError",
    "ArchiverConnectionError",
    "PVProfile",
    "PROFILE_STORE",
    "get_values_over_time_range",
    "is_archiver_available",
    "real_get_values_over_time_range",
]

logger = logging.getLogger(__name__)


def _should_force_mock() -> bool:
    return os.getenv("SC_ARCHIVER_MOCK") == "1"


def get_values_over_time_range(
    pv_list: List[str],
    start_time: datetime,
    end_time: datetime,
) -> Dict[str, ArchiveDataHandler]:
    """
    Get historical PV data over a time range.

    Mock is used ONLY when explicitly forced (SC_ARCHIVER_MOCK=1). Otherwise the
    real archiver is used and its errors propagate — there is no silent fallback
    to mock data.

    Returns:
        Dict[pv_name, ArchiveDataHandler]
    """
    if not pv_list:
        return {}

    if _should_force_mock():
        logger.debug("Using mock archiver (forced mode)")
        return mock_get_values_over_time_range(pv_list, start_time, end_time)

    logger.debug("Fetching from real archiver")
    return real_get_values_over_time_range(pv_list, start_time, end_time)


# --- Auto-install the PyDM mock patch when forced (no display edits needed) ---
if _should_force_mock():
    try:
        from .pydm_mock_patch import install_mock_archiver_patch

        install_mock_archiver_patch()
    except Exception as e:  # PyDM not importable here — safe to ignore
        logger.debug("PyDM mock patch not installed: %s", e)