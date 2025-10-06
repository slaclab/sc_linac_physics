from collections import OrderedDict, defaultdict
from datetime import datetime, timedelta
from typing import DefaultDict, Optional, Dict

from lcls_tools.common.controls.pyepics.utils import PV
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
)
from sc_linac_physics.utils.sc_linac.cavity import Cavity


class BackendCavity(Cavity):
    def __init__(self, cavity_num, rack_object):
        super(BackendCavity, self).__init__(cavity_num=cavity_num, rack_object=rack_object)
        self.status_pv: str = self.pv_addr(STATUS_SUFFIX)
        self._status_pv_obj: Optional[PV] = None
        self.severity_pv: str = self.pv_addr(SEVERITY_SUFFIX)
        self._severity_pv_obj: Optional[PV] = None
        self.description_pv: str = self.pv_addr(DESCRIPTION_SUFFIX)
        self._description_pv_obj: Optional[PV] = None

        self.faults: OrderedDict[int, Fault] = OrderedDict()
        self.create_faults()

    @property
    def status_pv_obj(self) -> PV:
        if not self._status_pv_obj:
            self._status_pv_obj = PV(self.status_pv)
        return self._status_pv_obj

    @property
    def severity_pv_obj(self) -> PV:
        if not self._severity_pv_obj:
            self._severity_pv_obj = PV(self.severity_pv)
        return self._severity_pv_obj

    @property
    def description_pv_obj(self) -> PV:
        if not self._description_pv_obj:
            self._description_pv_obj = PV(self.description_pv)
        return self._description_pv_obj

    def create_faults(self):
        for csv_fault_dict in utils.parse_csv():
            level: str = csv_fault_dict["Level"]
            suffix: str = csv_fault_dict["PV Suffix"]
            rack: str = csv_fault_dict["Rack"]

            button_command = csv_fault_dict["Button Path"]
            macros = self.edm_macro_string

            if level == "RACK":
                # Rack A cavities don't care about faults for Rack B and vice versa
                if rack != self.rack.rack_name:
                    # Takes us to the next iteration of the for loop
                    continue

                # tested in the python console that strings without one of these
                # formatting keys just ignores them and moves on
                prefix = csv_fault_dict["PV Prefix"].format(
                    LINAC=self.linac.name,
                    CRYOMODULE=self.cryomodule.name,
                    RACK=self.rack.rack_name,
                    CAVITY=self.number,
                )
                pv: str = prefix + suffix

            elif level == "CRYO":
                prefix = csv_fault_dict["PV Prefix"].format(CRYOMODULE=self.cryomodule.name, CAVITY=self.number)
                pv: str = prefix + suffix
                macros = self.cryo_edm_macro_string

            elif level == "SSA":
                pv: str = self.ssa.pv_addr(suffix)
                button_command = button_command.format(
                    cm_OR_hl="hl" if self.cryomodule.is_harmonic_linearizer else "cm"
                )

            elif level == "CAV":
                pv: str = self.pv_addr(suffix)

            elif level == "CM":
                cm_type = csv_fault_dict["CM Type"]
                prefix = csv_fault_dict["PV Prefix"].format(
                    LINAC=self.linac.name,
                    CRYOMODULE=self.cryomodule.name,
                    CAVITY=self.number,
                )

                if (cm_type == "1.3" and self.cryomodule.is_harmonic_linearizer) or (
                    cm_type == "3.9" and not self.cryomodule.is_harmonic_linearizer
                ):
                    continue
                pv: str = prefix + suffix

            elif level == "ALL":
                prefix = csv_fault_dict["PV Prefix"]
                pv: str = prefix + suffix

            else:
                raise (SpreadsheetError("Unexpected fault level in fault spreadsheet"))

            tlc: str = csv_fault_dict["Three Letter Code"]
            ok_condition: str = csv_fault_dict["OK If Equal To"]
            fault_condition: str = csv_fault_dict["Faulted If Equal To"]
            csv_prefix: str = csv_fault_dict["PV Prefix"]

            key: int = display_hash(
                rack=rack,
                fault_condition=fault_condition,
                ok_condition=ok_condition,
                tlc=tlc,
                suffix=suffix,
                prefix=csv_prefix,
            )

            # setting key of faults dictionary to be row number b/c it's unique (i.e. not repeated)
            self.faults[key]: OrderedDict[int, Fault] = Fault(
                tlc=tlc,
                severity=csv_fault_dict["Severity"],
                pv=pv,
                ok_value=ok_condition,
                fault_value=fault_condition,
                long_description=csv_fault_dict["Long Description"],
                short_description=csv_fault_dict["Short Description"],
                button_level=csv_fault_dict["Button Type"],
                button_command=button_command,
                macros=macros,
                button_text=csv_fault_dict["Three Letter Code"],
                button_macro=csv_fault_dict["Button Macros"],
                action=csv_fault_dict["Recommended Corrective Actions"],
                lazy_pv=self.rack.cryomodule.linac.machine.lazy_fault_pvs,
            )

    def get_fault_counts(self, start_time: datetime, end_time: datetime) -> DefaultDict[str, FaultCounter]:
        """
        Using max function to get the maximum fault or invalid count for duplicate TLCs
            i.e. MGT tlc has three PVs associated with it (X, Y, and Q) but we
            only want the fault and invalid count for whichever PV had the
            greatest number of faults
        """
        result: DefaultDict[str, FaultCounter] = defaultdict(FaultCounter)

        data: Dict[str, ArchiveDataHandler] = get_values_over_time_range(
            pv_list=[self.pv_addr("CUDSTATUS"), self.pv_addr("CUDSEVR")],
            start_time=start_time,
            end_time=end_time,
        )

        statuses: ArchiveDataHandler = data[self.pv_addr("CUDSTATUS")]
        severities: ArchiveDataHandler = data[self.pv_addr("CUDSEVR")]

        for status, status_ts in zip(statuses.values, statuses.timestamps):
            if status == str(self.number):
                continue

            try:
                ts = status_ts.replace(microsecond=round(status_ts.microsecond / 10000) * 10000)
            except ValueError:
                ts = status_ts + timedelta(seconds=1)

            severity = severity_of_fault(ts, severities)

            if severity == 0:
                result[status].ok_count += 1
            elif severity == 1:
                result[status].warning_count += 1
            elif severity == 2:
                result[status].alarm_count += 1
            else:
                result[status].invalid_count += 1

        # for fault in self.faults.values():
        #     result[fault.tlc] = max(
        #         result[fault.tlc],
        #         fault.get_fault_count_over_time_range(
        #             start_time=start_time, end_time=end_time
        #         ),
        #     )
        return result

    def run_through_faults(self):
        is_okay: bool = True
        invalid: bool = False

        for fault in self.faults.values():
            try:
                if fault.is_currently_faulted():
                    is_okay = False
                    break
            except PVInvalidError as e:
                print(e, " is disconnected")
                is_okay = False
                invalid = True
                break

        if is_okay:
            self.severity_pv_obj.put(0)
            self.status_pv_obj.put(str(self.number))
            self.description_pv_obj.put(" ")
        else:
            if not invalid:
                self.severity_pv_obj.put(fault.severity)
            else:
                self.severity_pv_obj.put(3)

            self.status_pv_obj.put(fault.tlc)
            self.description_pv_obj.put(fault.short_description)
