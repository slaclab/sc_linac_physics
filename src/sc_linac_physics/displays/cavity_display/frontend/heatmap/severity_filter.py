from typing import Optional

from sc_linac_physics.displays.cavity_display.backend.fault import (
    FaultCounter,
)


class SeverityFilter:
    """Filters fault counts by severity level (alarm/warning/invalid)."""

    def __init__(
        self,
        include_alarms: bool = True,
        include_warnings: bool = True,
        include_invalid: bool = True,
    ) -> None:
        self.include_alarms = include_alarms
        self.include_warnings = include_warnings
        self.include_invalid = include_invalid

    def get_filtered_count(self, counter: FaultCounter) -> int:
        total = 0
        if self.include_alarms:
            total += counter.alarm_count
        if self.include_warnings:
            total += counter.warning_count
        if self.include_invalid:
            total += counter.invalid_count
        return total

    def set_filter(
        self,
        include_alarms: Optional[bool] = None,
        include_warnings: Optional[bool] = None,
        include_invalid: Optional[bool] = None,
    ) -> None:
        if include_alarms is not None:
            self.include_alarms = include_alarms
        if include_warnings is not None:
            self.include_warnings = include_warnings
        if include_invalid is not None:
            self.include_invalid = include_invalid
