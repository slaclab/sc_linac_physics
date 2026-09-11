"""Public entry point mirroring the original mock.py function."""

from __future__ import annotations

from datetime import datetime

from ..models import ArchiverValue, ArchiveDataHandler
from .engine import MockArchiveDataHandler


def mock_get_values_over_time_range(
    pv_list: list[str],
    start_time: datetime,
    end_time: datetime,
    trend: str | None = None,
    trend_amplitude: float | None = None,
    noise_scale: float | None = None,
) -> dict[str, ArchiveDataHandler]:
    """Generate mock data for multiple PVs.

    Behavior is driven per-PV by PROFILE_STORE (see mock.profiles). Explicit
    trend/amplitude/noise arguments override the store for all PVs in the call.
    """
    if not pv_list:
        return {}

    result: dict[str, ArchiveDataHandler] = {}
    for pv_name in pv_list:
        mock = MockArchiveDataHandler(
            pv_name,
            start_time,
            end_time,
            trend=trend,
            trend_amplitude=trend_amplitude,
            noise_scale=noise_scale,
        )
        archiver_values = [
            ArchiverValue(value=val, timestamp=ts, severity=sev, status=stat)
            for val, ts, sev, stat in zip(
                mock.values, mock.timestamps, mock.severities, mock.statuses
            )
        ]
        result[pv_name] = ArchiveDataHandler.from_archiver_values(
            pv_name, archiver_values
        )
    return result