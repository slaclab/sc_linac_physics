import dataclasses
from datetime import datetime
from typing import Union, Optional

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
    def ratio_ok(self):
        try:
            return self.ok_count / (self.fault_count + self.invalid_count)
        except ZeroDivisionError:
            return 1


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

        self._pv_obj: Optional[PV] = None
        self.pv: str = pv

    @property
    def pv_obj(self) -> PV:
        if not self._pv_obj:
            self._pv_obj = PV(self.pv, connection_timeout=PV_TIMEOUT)
        return self._pv_obj

    def is_currently_faulted(self):
        return self.is_faulted(self.pv_obj)

    def is_faulted(self, obj: Union[PV, ArchiverValue]):
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

        if self.ok_value is not None:
            return obj.val != self.ok_value

        elif self.fault_value is not None:
            return obj.val == self.fault_value

        else:
            print(self.pv)
            raise Exception(
                "Fault has neither 'Fault if equal to' nor"
                " 'OK if equal to' parameter"
            )

    def was_faulted(self, time: datetime):
        archiver_result = get_data_at_time(pv_list=[self.pv], time_requested=time)
        archiver_value = archiver_result[self.pv]
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
