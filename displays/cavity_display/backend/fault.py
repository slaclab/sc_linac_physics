import dataclasses
from datetime import datetime
from typing import Union, Optional, Dict

from lcls_tools.common.controls.pyepics.utils import (
    PV,
    EPICS_INVALID_VAL,
    PVInvalidError,
)
from lcls_tools.common.data.archiver import (
    ArchiveDataHandler,
    ArchiverValue,
    get_data_at_time,
    get_values_over_time_range,
)

PV_TIMEOUT = 0.01


@dataclasses.dataclass
class FaultCounter:
    fault_count: int = 0
    ok_count: int = 0
    invalid_count: int = 0

    @property
    def sum_fault_count(self) -> int:
        return self.fault_count + self.invalid_count

    @property
    def ratio_ok(self):
        try:
            return self.ok_count / (self.fault_count + self.invalid_count)
        except ZeroDivisionError:
            return 1

    def __gt__(self, other) -> bool:
        return self.sum_fault_count > other.sum_fault_count

    def __eq__(self, other) -> bool:
        return self.sum_fault_count == other.sum_fault_count


class Fault:
    def __init__(
        self,
        tlc=None,
        severity=None,
        pv=None,
        ok_value=None,
        fault_value=None,
        long_description=None,
        short_description=None,
        button_level=None,
        button_command=None,
        macros=None,
        button_text=None,
        button_macro=None,
        action=None,
        lazy_pv=False,
    ):
        self.tlc = tlc
        self.severity = int(severity)
        self.long_description = long_description
        self.short_description = short_description
        self.ok_value = float(ok_value) if ok_value else None
        self.fault_value = float(fault_value) if fault_value else None
        self.button_level = button_level
        self.button_command = button_command
        self.macros = macros
        self.button_text = button_text
        self.button_macro = button_macro
        self.action = action

        # Storing PV name as a string instead of making a PV obj
        self.pv: str = pv
        # TODO figure out why lazy generation breaks the backend runner
        self._pv_obj: Optional[PV] = (
            PV(self.pv, connection_timeout=PV_TIMEOUT) if not lazy_pv else None
        )

    @property
    def pv_obj(self) -> PV:
        if not self._pv_obj:
            self._pv_obj = PV(self.pv, connection_timeout=PV_TIMEOUT)
        return self._pv_obj

    def is_currently_faulted(self) -> bool:
        # returns "TRUE" if faulted
        # returns "FALSE" if not faulted
        return self.is_faulted(self.pv_obj)

    def is_faulted(self, obj: Union[PV, ArchiverValue]) -> bool:
        """
        Dug through the pyepics source code to find the severity values:
        class AlarmSeverity(DefaultIntEnum):
            NO_ALARM = 0
            MINOR = 1
            MAJOR = 2
            INVALID = 3
        """
        if obj.severity == EPICS_INVALID_VAL or obj.status is None:
            raise PVInvalidError(self.pv)

        # self.ok_value is the value stated in spreadsheet
        # obj.value is the actual reading value from pv
        if self.ok_value is not None:
            # return "TRUE" means they do NOT match
            # return "FALSE" means is_okay, not faulted
            return obj.val != self.ok_value

        elif self.fault_value is not None:
            # return "TRUE" means faulted
            # return "FALSE" means not faulted
            return obj.val == self.fault_value

        else:
            print(self)
            raise Exception(
                "Fault has neither 'Fault if equal to' nor"
                " 'OK if equal to' parameter"
            )

    def was_faulted(self, time: datetime) -> bool:
        archiver_result: Dict[str, ArchiverValue] = get_data_at_time(
            pv_list=[self.pv], time_requested=time
        )
        archiver_value: ArchiverValue = archiver_result[self.pv]
        return self.is_faulted(archiver_value)

    def get_fault_count_over_time_range(
        self, start_time: datetime, end_time: datetime
    ) -> FaultCounter:
        result = get_values_over_time_range(
            pv_list=[self.pv], start_time=start_time, end_time=end_time
        )

        data_handler: ArchiveDataHandler = result[self.pv]

        counter = FaultCounter()

        for archiver_value in data_handler.value_list:
            try:
                if self.is_faulted(archiver_value):
                    counter.fault_count += 1
                else:
                    counter.ok_count += 1
            except PVInvalidError:
                counter.invalid_count += 1

        return counter
