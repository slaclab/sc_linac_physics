import dataclasses
from datetime import datetime
from typing import Union

from lcls_tools.common.controls.pyepics.utils import PV
from lcls_tools.common.data_analysis.archiver import (
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


class PVInvalidError(Exception):
    def __init__(self, message):
        super(PVInvalidError, self).__init__(message)


class Fault:
    def __init__(
        self,
        tlc,
        severity,
        pv,
        ok_value,
        fault_value,
        long_description,
        short_description,
        button_level,
        button_command,
        macros,
        button_text,
        button_macro,
        action,
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

        self.pv: PV = PV(pv, connection_timeout=PV_TIMEOUT)

    def is_currently_faulted(self):
        return self.is_faulted(self.pv)

    def is_faulted(self, obj: Union[PV, ArchiverValue]):
        """
        Dug through the pyepics source code to find the severity values:
        class AlarmSeverity(DefaultIntEnum):
            NO_ALARM = 0
            MINOR = 1
            MAJOR = 2
            INVALID = 3
        """
        if obj.severity == 3 or obj.status is None:
            raise PVInvalidError(self.pv.pvname)

        if self.ok_value is not None:
            return obj.val != self.ok_value

        elif self.fault_value is not None:
            return obj.val == self.fault_value

        else:
            print(self)
            raise Exception(
                "Fault has neither 'Fault if equal to' nor"
                " 'OK if equal to' parameter"
            )

    def was_faulted(self, time: datetime):
        archiver_value: ArchiverValue = get_data_at_time(
            pv_list=[self.pv.pvname], time_requested=time
        )[self.pv.pvname]
        return self.is_faulted(archiver_value)

    def get_fault_count_over_time_range(
        self, start_time: datetime, end_time: datetime
    ) -> FaultCounter:
        result = get_values_over_time_range(
            pv_list=[self.pv.pvname], start_time=start_time, end_time=end_time
        )

        data_handler: ArchiveDataHandler = result[self.pv.pvname]

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
