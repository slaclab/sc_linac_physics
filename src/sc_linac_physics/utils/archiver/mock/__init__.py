"""Mock archiver data generator (package).

Public API (unchanged from the old mock.py module):
    - mock_get_values_over_time_range(...)
    - MockArchiveDataHandler

Adjustability:
    - PROFILE_STORE (process-global ProfileStore) lets a runtime GUI or config
      file tune per-PV behavior. Both archiver transports read from it via the
      generator, so changes propagate everywhere with no call-site edits.
"""

from __future__ import annotations

from .api import mock_get_values_over_time_range
from .engine import MockArchiveDataHandler
from .profiles import PVProfile, ProfileStore, PROFILE_STORE

from .trends import TREND_FUNCTIONS, _trend_for_pv  #
from .seeding import _stable_seed  
from .resolver import _live_kind  

__all__ = [
    "mock_get_values_over_time_range",
    "MockArchiveDataHandler",
    "PVProfile",
    "ProfileStore",
    "PROFILE_STORE",
    "TREND_FUNCTIONS",
]