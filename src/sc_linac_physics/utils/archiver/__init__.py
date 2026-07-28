"""
Smart archiver routing wrapper.

Public API:
- get_values_over_time_range(...)

Routing:
- If SC_ARCHIVER_MOCK=1 -> always mock
- Else -> real archiver (errors propagate; NO mock fallback)
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Dict, List

import logging
from .models import ArchiveDataHandler, ArchiverValue
from .mock import mock_get_values_over_time_range
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

    Mock is used ONLY when explicitly forced (SC_ARCHIVER_MOCK=1). 
    Otherwise the real archiver is used and itserrors propagate — 
    there is no silent fallback to mock data.

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