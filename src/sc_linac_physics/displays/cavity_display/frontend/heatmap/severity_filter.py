from sc_linac_physics.displays.cavity_display.backend.fault import FaultCounter


class SeverityFilter:
    """Filters fault counts by severity level using toggleable flags."""

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
        """Get the total fault count based on current filter settings."""
        total = 0

        if self.include_alarms:
            total += counter.alarm_count
        if self.include_warnings:
            total += counter.warning_count
        if self.include_invalid:
            total += counter.invalid_count

        return total

    def include_all(self) -> None:
        """Enable all severity filters."""
        self.include_alarms = True
        self.include_warnings = True
        self.include_invalid = True

    def exclude_all(self) -> None:
        """Disable all severity filters."""
        self.include_alarms = False
        self.include_warnings = False
        self.include_invalid = False

    def set_filter(
        self,
        include_alarms: bool | None = None,
        include_warnings: bool | None = None,
        include_invalid: bool | None = None,
    ) -> None:
        """Update filter settings selectively."""
        if include_alarms is not None:
            self.include_alarms = include_alarms
        if include_warnings is not None:
            self.include_warnings = include_warnings
        if include_invalid is not None:
            self.include_invalid = include_invalid
