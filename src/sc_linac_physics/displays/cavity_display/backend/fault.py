"""
Fault monitoring and analysis module for LCLS accelerator systems.

This module provides classes for tracking and analyzing fault conditions
in EPICS process variables, including historical fault analysis.
"""

import dataclasses
from datetime import datetime
from typing import Union, Optional, Dict

from lcls_tools.common.data.archiver import (
    ArchiveDataHandler,
    ArchiverValue,
    get_data_at_time,
    get_values_over_time_range,
)

from sc_linac_physics.utils.epics import (
    PV,
    EPICS_INVALID_VAL,
    PVInvalidError,
)


@dataclasses.dataclass
class FaultCounter:
    """Tracks fault statistics over a time period.

    Attributes:
        alarm_count: Number of times the PV was in an alarm/fault state
        ok_count: Number of times the PV was in an acceptable state
        invalid_count: Number of times the PV had invalid/unavailable data
        warning_count: Number of times the PV was in a warning state
    """

    alarm_count: int = 0
    ok_count: int = 0
    invalid_count: int = 0
    warning_count: int = 0

    @property
    def sum_fault_count(self) -> int:
        """Total number of fault events (alarms + invalid states)."""
        return self.alarm_count + self.invalid_count

    @property
    def total_count(self) -> int:
        """Total number of all recorded states."""
        return (
            self.alarm_count
            + self.ok_count
            + self.invalid_count
            + self.warning_count
        )

    @property
    def ratio_ok(self) -> float:
        """Ratio of OK states to fault states.

        Returns:
            Float ratio, or 1.0 if no faults occurred (perfect uptime).
        """
        fault_count = self.sum_fault_count
        if fault_count == 0:
            return 1.0
        return self.ok_count / fault_count

    @property
    def uptime_percentage(self) -> float:
        """Percentage of time in OK state.

        Returns:
            Percentage (0-100), or 100.0 if no data points.
        """
        if self.total_count == 0:
            return 100.0
        return (self.ok_count / self.total_count) * 100

    def __gt__(self, other: "FaultCounter") -> bool:
        """Compare fault counters by total fault count."""
        return self.sum_fault_count > other.sum_fault_count

    def __eq__(self, other: "FaultCounter") -> bool:
        """Check equality based on total fault count."""
        return self.sum_fault_count == other.sum_fault_count

    def __repr__(self) -> str:
        """Provide detailed string representation."""
        return (
            f"FaultCounter(alarm={self.alarm_count}, ok={self.ok_count}, "
            f"invalid={self.invalid_count}, warning={self.warning_count}, "
            f"uptime={self.uptime_percentage:.1f}%)"
        )


class Fault:
    """Represents a fault condition for a specific EPICS PV.

    This class encapsulates fault detection logic and historical analysis
    for a single process variable in the accelerator control system.

    Args:
        tlc: Three-letter code for the device/system
        severity: Fault severity level (integer)
        pv: EPICS process variable name
        ok_value: Value indicating normal operation (mutually exclusive with fault_value)
        fault_value: Value indicating fault condition (mutually exclusive with ok_value)
        long_description: Detailed description of the fault
        short_description: Brief description of the fault
        button_level: UI button access level
        button_command: Command to execute when button is pressed
        macros: EPICS macros for the fault
        button_text: Text to display on UI button
        button_macro: Macro for the button
        action: Corrective action recommendation
        lazy_pv: If True, delay PV object creation until first access
        connection_timeout: Timeout for PV connection (seconds)
    """

    def __init__(
        self,
        tlc: Optional[str] = None,
        severity: Optional[Union[int, str]] = None,
        pv: Optional[str] = None,
        ok_value: Optional[Union[float, int, str]] = None,
        fault_value: Optional[Union[float, int, str]] = None,
        long_description: Optional[str] = None,
        short_description: Optional[str] = None,
        button_level: Optional[str] = None,
        button_command: Optional[str] = None,
        macros: Optional[str] = None,
        button_text: Optional[str] = None,
        button_macro: Optional[str] = None,
        action: Optional[str] = None,
        lazy_pv: bool = True,
        connection_timeout: float = 1.0,  # Reduced from default 5.0
    ):
        self.tlc = tlc
        self.severity = int(severity) if severity is not None else 0
        self.long_description = long_description
        self.short_description = short_description
        self.ok_value = self._parse_numeric_value(ok_value)
        self.fault_value = self._parse_numeric_value(fault_value)
        self.button_level = button_level
        self.button_command = button_command
        self.macros = macros
        self.button_text = button_text
        self.button_macro = button_macro
        self.action = action
        self.connection_timeout = connection_timeout

        # Validate that exactly one of ok_value or fault_value is set
        if self.ok_value is not None and self.fault_value is not None:
            raise ValueError(
                f"Fault for {pv}: Cannot specify both 'ok_value' and 'fault_value'"
            )
        if self.ok_value is None and self.fault_value is None:
            raise ValueError(
                f"Fault for {pv}: Must specify either 'ok_value' or 'fault_value'"
            )

        # Store PV name as string
        self.pv: str = pv or ""
        # Lazy PV object creation
        self._pv_obj: Optional[PV] = None

        # Create immediately if not lazy
        if not lazy_pv and self.pv:
            self._create_pv_obj()

    @staticmethod
    def _parse_numeric_value(
        value: Optional[Union[float, int, str]],
    ) -> Optional[float]:
        """Convert value to float if present, otherwise return None."""
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def _create_pv_obj(self) -> None:
        """Create the PV object with optimized settings."""
        if not self.pv:
            raise ValueError("Cannot create PV object: PV name is empty")

        self._pv_obj = PV(
            self.pv,
            connection_timeout=self.connection_timeout,
            auto_monitor=False,  # Don't need continuous monitoring
            require_connection=False,  # Don't fail if PV doesn't exist
        )

    @property
    def pv_obj(self) -> PV:
        """Lazy-loaded PV object. Creates on first access if not already created."""
        if not self._pv_obj:
            self._create_pv_obj()
        return self._pv_obj

    def is_currently_faulted(self) -> bool:
        """Check if the PV is currently in a fault state.

        Returns:
            True if currently faulted, False if OK.

        Raises:
            PVInvalidError: If PV is disconnected or invalid.
        """
        return self.is_faulted(self.pv_obj)

    def is_currently_faulted_with_value(
        self, value: Union[float, int, str, None]
    ) -> bool:
        """Check if a pre-fetched value indicates a fault condition.

        This method is optimized for batch PV reads where values are fetched
        all at once using PV.get_many_values().

        Args:
            value: The current PV value (from batch read)

        Returns:
            True if the value indicates a fault, False if OK.

        Raises:
            PVInvalidError: If value is None (disconnected/invalid PV).
        """
        if value is None:
            raise PVInvalidError(
                f"{self.pv} returned None (disconnected or invalid)"
            )

        # Check fault condition using the same logic as is_faulted()
        if self.ok_value is not None:
            # Fault if the value does NOT match the expected OK value
            return value != self.ok_value
        elif self.fault_value is not None:
            # Fault if the value matches the fault value
            return value == self.fault_value
        else:
            # This should never happen due to __init__ validation
            raise RuntimeError(
                f"Fault for {self.pv} has neither 'ok_value' nor 'fault_value' parameter"
            )

    def is_faulted(self, obj: Union[PV, ArchiverValue]) -> bool:
        """Determine if a PV object or archiver value indicates a fault.

        EPICS severity values:
            NO_ALARM = 0
            MINOR = 1
            MAJOR = 2
            INVALID = 3

        Args:
            obj: PV object or ArchiverValue to check

        Returns:
            True if the value indicates a fault, False if OK.

        Raises:
            PVInvalidError: If the PV severity is invalid or status is None.
        """
        if obj.severity == EPICS_INVALID_VAL or obj.status is None:
            raise PVInvalidError(self.pv)

        if self.ok_value is not None:
            # Fault if the value does NOT match the expected OK value
            return obj.val != self.ok_value
        elif self.fault_value is not None:
            # Fault if the value matches the fault value
            return obj.val == self.fault_value
        else:
            # This should never happen due to __init__ validation
            raise RuntimeError(
                f"Fault for {self.pv} has neither 'ok_value' nor 'fault_value' parameter"
            )

    def was_faulted(self, time: datetime) -> bool:
        """Check if the PV was in a fault state at a specific time.

        Args:
            time: DateTime to check fault status

        Returns:
            True if the PV was faulted at the specified time, False otherwise.

        Raises:
            PVInvalidError: If archiver data is invalid for the requested time.
        """
        archiver_result: Dict[str, ArchiverValue] = get_data_at_time(
            pv_list=[self.pv], time_requested=time
        )
        archiver_value: ArchiverValue = archiver_result[self.pv]
        return self.is_faulted(archiver_value)

    def get_fault_count_over_time_range(
        self, start_time: datetime, end_time: datetime
    ) -> FaultCounter:
        """Analyze fault history over a time range.

        Retrieves archived data and counts fault occurrences, OK states,
        and invalid data points.

        Args:
            start_time: Beginning of time range to analyze
            end_time: End of time range to analyze

        Returns:
            FaultCounter object with statistics for the time period.
        """
        result = get_values_over_time_range(
            pv_list=[self.pv], start_time=start_time, end_time=end_time
        )

        data_handler: ArchiveDataHandler = result[self.pv]
        counter = FaultCounter()

        for archiver_value in data_handler.value_list:
            try:
                if self.is_faulted(archiver_value):
                    counter.alarm_count += 1
                else:
                    counter.ok_count += 1
            except PVInvalidError:
                counter.invalid_count += 1

        return counter

    def __repr__(self) -> str:
        """Provide string representation for debugging."""
        return (
            f"Fault(pv='{self.pv}', severity={self.severity}, "
            f"ok_value={self.ok_value}, fault_value={self.fault_value})"
        )
