from collections import OrderedDict
from datetime import datetime
from typing import Dict

from epics import caput

from displays.cavity_display.backend.fault import Fault, FaultCounter, PVInvalidError
from displays.cavity_display.utils.utils import (
    STATUS_SUFFIX,
    DESCRIPTION_SUFFIX,
    SEVERITY_SUFFIX,
    parse_csv,
    SpreadsheetError,
    display_hash,
)
from utils.sc_linac.cavity import Cavity


class BackendCavity(Cavity):
    def __init__(
        self,
        cavity_num,
        rack_object,
    ):
        super(BackendCavity, self).__init__(
            cavity_num=cavity_num, rack_object=rack_object
        )
        self.status_pv: str = self.pv_addr(STATUS_SUFFIX)
        self.severity_pv: str = self.pv_addr(SEVERITY_SUFFIX)
        self.description_pv: str = self.pv_addr(DESCRIPTION_SUFFIX)

        self.faults: OrderedDict[int, Fault] = OrderedDict()
        self.create_faults()

    def create_faults(self):
        for csv_fault_dict in parse_csv():
            level = csv_fault_dict["Level"]
            suffix = csv_fault_dict["PV Suffix"]
            rack = csv_fault_dict["Rack"]

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
                pv = prefix + suffix

            elif level == "CRYO":
                prefix = csv_fault_dict["PV Prefix"].format(
                    CRYOMODULE=self.cryomodule.name, CAVITY=self.number
                )
                pv = prefix + suffix

            elif level == "SSA":
                pv = self.ssa.pv_addr(suffix)

            elif level == "CAV":
                pv = self.pv_addr(suffix)

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
                pv = prefix + suffix

            elif level == "ALL":
                prefix = csv_fault_dict["PV Prefix"]
                pv = prefix + suffix

            else:
                raise (SpreadsheetError("Unexpected fault level in fault spreadsheet"))

            tlc = csv_fault_dict["Three Letter Code"]
            ok_condition = csv_fault_dict["OK If Equal To"]
            fault_condition = csv_fault_dict["Faulted If Equal To"]
            csv_prefix = csv_fault_dict["PV Prefix"]

            key = display_hash(
                rack=rack,
                fault_condition=fault_condition,
                ok_condition=ok_condition,
                tlc=tlc,
                suffix=suffix,
                prefix=csv_prefix,
            )

            # setting key of faults dictionary to be row number b/c it's unique (i.e. not repeated)
            self.faults[key] = Fault(
                tlc=tlc,
                severity=csv_fault_dict["Severity"],
                pv=pv,
                ok_value=ok_condition,
                fault_value=fault_condition,
                long_description=csv_fault_dict["Long Description"],
                short_description=csv_fault_dict["Short Description"],
                button_level=csv_fault_dict["Button Type"],
                button_command=csv_fault_dict["Button Path"],
                macros=self.edm_macro_string,
                button_text=csv_fault_dict["Three Letter Code"],
                button_macro=csv_fault_dict["Button Macros"],
                action=csv_fault_dict["Recommended Corrective Actions"],
            )

    def get_fault_counts(
        self, start_time: datetime, end_time: datetime
    ) -> Dict[str, FaultCounter]:
        result: Dict[str, FaultCounter] = {}

        for fault in self.faults.values():
            result[fault.pv] = fault.get_fault_count_over_time_range(
                start_time=start_time, end_time=end_time
            )

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
            caput(self.status_pv, f"{self.number}")
            caput(self.severity_pv, 0)
            caput(self.description_pv, " ")
        else:
            caput(self.status_pv, fault.tlc)
            caput(self.description_pv, fault.short_description)
            if not invalid:
                caput(self.severity_pv, fault.severity)
            else:
                caput(self.severity_pv, 3)
