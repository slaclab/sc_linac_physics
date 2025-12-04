"""
Backend cavity fault monitoring and management with batch PV initialization.
"""

from collections import OrderedDict, defaultdict
from datetime import datetime, timedelta
from time import time
from typing import DefaultDict, Optional, Dict, List

from lcls_tools.common.data.archiver import (
    get_values_over_time_range,
    ArchiveDataHandler,
)

from sc_linac_physics.displays.cavity_display.backend.fault import (
    Fault,
    FaultCounter,
    PVInvalidError,
)
from sc_linac_physics.displays.cavity_display.utils import utils
from sc_linac_physics.displays.cavity_display.utils.utils import (
    STATUS_SUFFIX,
    DESCRIPTION_SUFFIX,
    SEVERITY_SUFFIX,
    SpreadsheetError,
    display_hash,
    severity_of_fault,
    cavity_fault_logger,
)
from sc_linac_physics.utils.epics import PV, PVBatch
from sc_linac_physics.utils.sc_linac.cavity import Cavity


# Constants for severity levels
class SeverityLevel:
    """EPICS alarm severity levels."""

    NO_ALARM = 0
    WARNING = 1
    ALARM = 2
    INVALID = 3


class FaultLevel:
    """Fault hierarchy levels in the accelerator system."""

    RACK = "RACK"
    CRYO = "CRYO"
    SSA = "SSA"
    CAVITY = "CAV"
    CRYOMODULE = "CM"
    ALL = "ALL"


class BackendCavity(Cavity):
    """Extended cavity class with fault monitoring and historical analysis.

    This class manages fault detection for a cavity by:
    - Creating fault objects from CSV configuration
    - Monitoring real-time fault status
    - Analyzing historical fault data from the archiver
    - Publishing fault status to EPICS PVs

    Attributes:
        status_pv: PV name for fault status output
        severity_pv: PV name for fault severity output
        description_pv: PV name for fault description output
        faults: Ordered dictionary of Fault objects keyed by unique hash
    """

    def __init__(self, cavity_num: int, rack_object):
        """Initialize backend cavity with fault monitoring.

        Args:
            cavity_num: Cavity number (1-8 typically)
            rack_object: Parent rack object containing this cavity
        """
        init_start = time()

        super().__init__(cavity_num=cavity_num, rack_object=rack_object)

        # PV names for fault reporting
        self.status_pv: str = self.pv_addr(STATUS_SUFFIX)
        self._status_pv_obj: Optional[PV] = None
        self.severity_pv: str = self.pv_addr(SEVERITY_SUFFIX)
        self._severity_pv_obj: Optional[PV] = None
        self.description_pv: str = self.pv_addr(DESCRIPTION_SUFFIX)
        self._description_pv_obj: Optional[PV] = None

        # Fault storage
        self.faults: OrderedDict[int, Fault] = OrderedDict()

        # Create fault objects (always lazy initially for speed)
        fault_creation_start = time()
        self.create_faults()
        fault_creation_duration = time() - fault_creation_start

        # Batch initialize PVs if not lazy mode
        if not self.rack.cryomodule.linac.machine.lazy_fault_pvs:
            self._batch_pv_init()

        else:
            total_duration = time() - init_start
            cavity_fault_logger.debug(
                "Cavity initialized (lazy mode)",
                extra={
                    "extra_data": {
                        "cavity": self.pv_prefix,
                        "num_faults": len(self.faults),
                        "fault_creation_sec": round(fault_creation_duration, 3),
                        "total_init_sec": round(total_duration, 3),
                    }
                },
            )

    def _batch_pv_init(self) -> int:
        """Initialize all PVs for this cavity using batch creation.

        Uses PV.batch_create() to connect to multiple PVs simultaneously,
        which is much faster than creating them one at a time.

        Returns:
            Number of successfully connected PVs
        """

        # Collect all PV names for this cavity
        pv_names = [
            self.status_pv,
            self.severity_pv,
            self.description_pv,
        ]

        # Add all fault PV names
        fault_pv_names = [fault.pv for fault in self.faults.values()]
        pv_names.extend(fault_pv_names)

        # Batch create all PVs at once (much faster!)
        try:
            all_pvs = PV.batch_create(
                pv_names,
                connection_timeout=0.5,
                auto_monitor=False,
                require_connection=False,  # Don't fail if some PVs don't exist
            )
        except Exception as e:
            cavity_fault_logger.error(
                f"Batch PV creation failed for {self.pv_prefix}: {e}"
            )
            # Fall back to sequential initialization
            return self._sequential_pv_init()

        # Count successful connections
        connected_count = sum(1 for pv in all_pvs if pv and pv.connected)

        # Now assign the PV objects to our instance variables
        # First three are status PVs
        if all_pvs[0] and all_pvs[0].connected:
            self._status_pv_obj = all_pvs[0]

        if all_pvs[1] and all_pvs[1].connected:
            self._severity_pv_obj = all_pvs[1]

        if all_pvs[2] and all_pvs[2].connected:
            self._description_pv_obj = all_pvs[2]

        # Rest are fault PVs - assign them to the fault objects
        fault_pvs = all_pvs[3:]  # Skip the first 3 status PVs

        for fault, pv_obj in zip(self.faults.values(), fault_pvs):
            if pv_obj and pv_obj.connected:
                fault._pv_obj = pv_obj

        return connected_count

    def _sequential_pv_init(self) -> int:
        """Fallback: Initialize all PVs sequentially.

        Used if batch initialization fails.

        Returns:
            Number of successfully connected PVs
        """
        success_count = 0

        # Initialize cavity status PVs
        try:
            _ = self.status_pv_obj
            success_count += 1
        except Exception:
            pass

        try:
            _ = self.severity_pv_obj
            success_count += 1
        except Exception:
            pass

        try:
            _ = self.description_pv_obj
            success_count += 1
        except Exception:
            pass

        # Initialize fault PVs
        for fault in self.faults.values():
            try:
                _ = fault.pv_obj
                success_count += 1
            except Exception:
                pass

        return success_count

    @property
    def status_pv_obj(self) -> PV:
        """Lazy-loaded PV object for fault status."""
        if not self._status_pv_obj:
            self._status_pv_obj = PV(
                self.status_pv,
                connection_timeout=0.1,  # Very short since we pre-connected
                auto_monitor=False,
            )
        return self._status_pv_obj

    @property
    def severity_pv_obj(self) -> PV:
        """Lazy-loaded PV object for fault severity."""
        if not self._severity_pv_obj:
            self._severity_pv_obj = PV(
                self.severity_pv,
                connection_timeout=0.1,
                auto_monitor=False,
            )
        return self._severity_pv_obj

    @property
    def description_pv_obj(self) -> PV:
        """Lazy-loaded PV object for fault description."""
        if not self._description_pv_obj:
            self._description_pv_obj = PV(
                self.description_pv,
                connection_timeout=0.1,
                auto_monitor=False,
            )
        return self._description_pv_obj

    def create_faults(self) -> None:
        """Parse CSV fault configuration and create Fault objects.

        All Fault objects are created with lazy_pv=True initially for speed,
        then PVs are initialized in batch if not in lazy mode.
        """
        for csv_fault_dict in utils.parse_csv():
            try:
                pv, macros = self._build_fault_pv(csv_fault_dict)
                if pv is None:
                    continue

                fault = self._create_fault_from_csv(csv_fault_dict, pv, macros)
                key = self._generate_fault_key(csv_fault_dict)
                self.faults[key] = fault

            except Exception as e:
                cavity_fault_logger.error(
                    f"Error creating fault for {self.pv_prefix}: "
                    f"{csv_fault_dict.get('Three Letter Code', 'UNKNOWN')} - {e}"
                )

    def _build_fault_pv(self, csv_fault_dict: Dict[str, str]) -> tuple:
        """Build the PV name and macros for a fault based on its level."""
        level = csv_fault_dict["Level"]
        suffix = csv_fault_dict["PV Suffix"]
        rack = csv_fault_dict["Rack"]
        button_command = csv_fault_dict["Button Path"]
        macros = self.edm_macro_string

        if level == FaultLevel.RACK:
            if rack != self.rack.rack_name:
                return None, ""
            prefix = csv_fault_dict["PV Prefix"].format(
                LINAC=self.linac.name,
                CRYOMODULE=self.cryomodule.name,
                RACK=self.rack.rack_name,
                CAVITY=self.number,
            )
            pv = prefix + suffix

        elif level == FaultLevel.CRYO:
            prefix = csv_fault_dict["PV Prefix"].format(
                CRYOMODULE=self.cryomodule.name, CAVITY=self.number
            )
            pv = prefix + suffix
            macros = self.cryo_edm_macro_string

        elif level == FaultLevel.SSA:
            pv = self.ssa.pv_addr(suffix)
            button_command = button_command.format(
                cm_OR_hl=(
                    "hl" if self.cryomodule.is_harmonic_linearizer else "cm"
                )
            )

        elif level == FaultLevel.CAVITY:
            pv = self.pv_addr(suffix)

        elif level == FaultLevel.CRYOMODULE:
            cm_type = csv_fault_dict["CM Type"]

            if (
                cm_type == "1.3" and self.cryomodule.is_harmonic_linearizer
            ) or (
                cm_type == "3.9" and not self.cryomodule.is_harmonic_linearizer
            ):
                return None, ""

            prefix = csv_fault_dict["PV Prefix"].format(
                LINAC=self.linac.name,
                CRYOMODULE=self.cryomodule.name,
                CAVITY=self.number,
            )
            pv = prefix + suffix

        elif level == FaultLevel.ALL:
            prefix = csv_fault_dict["PV Prefix"]
            pv = prefix + suffix

        else:
            raise SpreadsheetError(
                f"Unexpected fault level '{level}' in fault spreadsheet"
            )

        return pv, macros

    def _create_fault_from_csv(
        self, csv_fault_dict: Dict[str, str], pv: str, macros: str
    ) -> Fault:
        """Create a Fault object from CSV data."""
        return Fault(
            tlc=csv_fault_dict["Three Letter Code"],
            severity=csv_fault_dict["Severity"],
            pv=pv,
            ok_value=csv_fault_dict["OK If Equal To"],
            fault_value=csv_fault_dict["Faulted If Equal To"],
            long_description=csv_fault_dict["Long Description"],
            short_description=csv_fault_dict["Short Description"],
            button_level=csv_fault_dict["Button Type"],
            button_command=csv_fault_dict["Button Path"],
            macros=macros,
            button_text=csv_fault_dict["Three Letter Code"],
            button_macro=csv_fault_dict["Button Macros"],
            action=csv_fault_dict["Recommended Corrective Actions"],
            lazy_pv=True,
            connection_timeout=0.1,  # Short timeout since we pre-connect
        )

    def _generate_fault_key(self, csv_fault_dict: Dict[str, str]) -> int:
        """Generate unique hash key for a fault."""
        return display_hash(
            rack=csv_fault_dict["Rack"],
            fault_condition=csv_fault_dict["Faulted If Equal To"],
            ok_condition=csv_fault_dict["OK If Equal To"],
            tlc=csv_fault_dict["Three Letter Code"],
            suffix=csv_fault_dict["PV Suffix"],
            prefix=csv_fault_dict["PV Prefix"],
        )

    def get_fault_counts(
        self, start_time: datetime, end_time: datetime
    ) -> DefaultDict[str, FaultCounter]:
        """Analyze fault history over a time range using archiver data.

        This method retrieves cavity fault status and severity from the archiver
        and aggregates fault counts by TLC (Three Letter Code).

        For duplicate TLCs (e.g., MGT with X, Y, Q variants), the maximum
        fault count is used to represent the TLC.

        Args:
            start_time: Beginning of analysis period
            end_time: End of analysis period

        Returns:
            Dictionary mapping TLC to FaultCounter with statistics
        """
        result: DefaultDict[str, FaultCounter] = defaultdict(FaultCounter)

        try:
            data: Dict[str, ArchiveDataHandler] = get_values_over_time_range(
                pv_list=[self.pv_addr("CUDSTATUS"), self.pv_addr("CUDSEVR")],
                start_time=start_time,
                end_time=end_time,
            )
        except Exception as e:
            cavity_fault_logger.error(
                f"Error retrieving archiver data for {self.pv_prefix}: {e}"
            )
            return result

        statuses: ArchiveDataHandler = data[self.pv_addr("CUDSTATUS")]
        severities: ArchiveDataHandler = data[self.pv_addr("CUDSEVR")]

        for status, status_ts in zip(statuses.values, statuses.timestamps):
            # Skip if status indicates cavity number (no fault)
            if status == str(self.number):
                continue

            # Round timestamp to 10ms precision for matching with severity data
            try:
                ts = status_ts.replace(
                    microsecond=round(status_ts.microsecond / 10000) * 10000
                )
            except ValueError:
                # Handle edge case where rounding exceeds valid range
                ts = status_ts + timedelta(seconds=1)

            severity = severity_of_fault(ts, severities)

            # Categorize by severity level
            if severity == SeverityLevel.NO_ALARM:
                result[status].ok_count += 1
            elif severity == SeverityLevel.WARNING:
                result[status].warning_count += 1
            elif severity == SeverityLevel.ALARM:
                result[status].alarm_count += 1
            else:  # INVALID
                result[status].invalid_count += 1

        return result

    def run_through_faults(self) -> None:
        """Check all faults and update cavity status PVs (optimized batch version).

        Uses PV.get_many_values() to check all fault PVs simultaneously,
        which is significantly faster than checking them sequentially.
        Falls back to sequential checking if batch read fails.
        """

        is_okay = True
        invalid = False
        faulted_fault: Optional[Fault] = None

        # Get list of all faults
        fault_list = list(self.faults.values())

        # Early exit if no faults configured
        if not fault_list:
            self._update_status_pvs(is_okay=True, invalid=False, fault=None)
            return

        # Collect PV names for batch read
        pv_names = [fault.pv for fault in fault_list]

        try:
            # Batch read all fault PVs at once using our wrapper
            values = PVBatch.get_values(pv_names, timeout=0.5)

            # Check each fault with its pre-fetched value
            for fault, value in zip(fault_list, values):
                try:
                    if fault.is_currently_faulted_with_value(value):
                        is_okay = False
                        faulted_fault = fault
                        break  # Stop at first fault (maintains existing behavior)
                except PVInvalidError:
                    # PV is disconnected or returned None
                    is_okay = False
                    invalid = True
                    faulted_fault = fault
                    break

        except Exception as e:
            # If batch read fails entirely, fall back to sequential method
            cavity_fault_logger.debug(
                f"Batch fault check failed for {self.pv_prefix}, "
                f"falling back to sequential: {e}"
            )
            return self._run_through_faults_sequential()

        self._update_status_pvs(is_okay, invalid, faulted_fault)

    def _run_through_faults_sequential(self) -> None:
        """Fallback sequential fault checking (original implementation).

        Used if batch reading fails for any reason.
        """
        is_okay = True
        invalid = False
        faulted_fault: Optional[Fault] = None

        for fault in self.faults.values():
            try:
                if fault.is_currently_faulted():
                    is_okay = False
                    faulted_fault = fault
                    break
            except PVInvalidError as e:
                cavity_fault_logger.warning(f"{fault.pv} is disconnected: {e}")
                is_okay = False
                invalid = True
                faulted_fault = fault
                break

        self._update_status_pvs(is_okay, invalid, faulted_fault)

    def _update_status_pvs(
        self, is_okay: bool, invalid: bool, fault: Optional[Fault]
    ) -> None:
        """Update cavity status PVs based on fault state.

        Args:
            is_okay: True if no faults detected
            invalid: True if a PV was invalid/disconnected
            fault: The Fault object that triggered (if any)
        """
        try:
            if is_okay:
                self.severity_pv_obj.put(SeverityLevel.NO_ALARM)
                self.status_pv_obj.put(str(self.number))
                self.description_pv_obj.put(" ")
            else:
                if invalid:
                    self.severity_pv_obj.put(SeverityLevel.INVALID)
                else:
                    self.severity_pv_obj.put(fault.severity)

                self.status_pv_obj.put(fault.tlc)
                self.description_pv_obj.put(fault.short_description)
        except Exception as e:
            cavity_fault_logger.error(
                f"Error updating status PVs for {self.pv_prefix}: {e}"
            )

    def get_active_faults(self) -> List[Fault]:
        """Get list of all currently active faults.

        Returns:
            List of Fault objects that are currently faulted.
        """
        active_faults = []
        for fault in self.faults.values():
            try:
                if fault.is_currently_faulted():
                    active_faults.append(fault)
            except PVInvalidError:
                # Skip disconnected PVs
                continue
        return active_faults

    def __repr__(self) -> str:
        """Provide string representation for debugging."""
        return (
            f"BackendCavity(name='{self.pv_prefix}', "
            f"num_faults={len(self.faults)}, "
            f"status_pv='{self.status_pv}')"
        )
