"""Mock archiver: deterministic synthetic data for offline and sim use.

Nothing calls it yet. It returns the same frames as
utils.archiver.get_values_over_time_range, so it can stand in for it.
"""

from sc_linac_physics.utils.archiver_mock.generator import (
    MAX_SAMPLES,
    guess_kind,
    mock_values_over_time_range,
)
from sc_linac_physics.utils.archiver_mock.profiles import (
    PROFILE_STORE,
    ProfileStore,
    PVProfile,
)

__all__ = [
    "MAX_SAMPLES",
    "PROFILE_STORE",
    "ProfileStore",
    "PVProfile",
    "guess_kind",
    "mock_values_over_time_range",
]
