import json
from datetime import datetime
from typing import List, Dict, TYPE_CHECKING

import numpy as np
from scipy.stats import linregress

from applications.q0 import q0_utils

if TYPE_CHECKING:
    from applications.q0.q0_cryomodule import Q0Cryomodule


class Calibration:
    def __init__(self, time_stamp: str, cryomodule: "Q0Cryomodule") -> None:
        self.time_stamp: str = time_stamp
        self.cryomodule: Q0Cryomodule = cryomodule

        self.heater_runs: List[q0_utils.HeaterRun] = []
        self._slope = None
        self.adjustment = 0

    def load_data(self):
        self.heater_runs: List[q0_utils.HeaterRun] = []

        with open(self.cryomodule.calib_data_file, "r+") as f:
            all_data: Dict = json.load(f)
            data: Dict = all_data[self.time_stamp]

            for heater_run_data in data.values():
                run = q0_utils.HeaterRun(heater_run_data["Desired Heat Load"])
                run._start_time = datetime.strptime(
                    heater_run_data[q0_utils.JSON_START_KEY],
                    q0_utils.DATETIME_FORMATTER,
                )
                run._end_time = datetime.strptime(
                    heater_run_data[q0_utils.JSON_END_KEY], q0_utils.DATETIME_FORMATTER
                )

                ll_data = {}
                for timestamp_str, val in heater_run_data[q0_utils.JSON_LL_KEY].items():
                    ll_data[float(timestamp_str)] = val

                run.ll_data = ll_data
                run.average_heat = heater_run_data[q0_utils.JSON_HEATER_READBACK_KEY]

                self.heater_runs.append(run)

            with open(self.cryomodule.calib_idx_file, "r+") as f:
                all_data: Dict = json.load(f)
                data: Dict = all_data[self.time_stamp]

                self.cryomodule.valveParams = q0_utils.ValveParams(
                    refValvePos=data["JT Valve Position"],
                    refHeatLoadDes=data["Total Reference Heater Setpoint"],
                    refHeatLoadAct=data["Total Reference Heater Readback"],
                )
                print("Loaded new reference parameters")

    def save_data(self):
        new_data = {}
        for idx, heater_run in enumerate(self.heater_runs):
            key = heater_run.start_time
            heater_data = {
                q0_utils.JSON_START_KEY: heater_run.start_time,
                q0_utils.JSON_END_KEY: heater_run.end_time,
                "Desired Heat Load": heater_run.heat_load_des,
                q0_utils.JSON_HEATER_READBACK_KEY: heater_run.average_heat,
                q0_utils.JSON_DLL_KEY: heater_run.dll_dt,
                q0_utils.JSON_LL_KEY: heater_run.ll_data,
            }

            new_data[key] = heater_data

        q0_utils.update_json_data(
            self.cryomodule.calib_data_file, self.time_stamp, new_data
        )

    def save_results(self):
        newData = {
            q0_utils.JSON_START_KEY: self.time_stamp,
            "Calculated Heat vs dll/dt Slope": self.dLLdt_dheat,
            "Calculated Adjustment": self.adjustment,
            "Total Reference Heater Setpoint": self.cryomodule.valveParams.refHeatLoadDes,
            "Total Reference Heater Readback": self.cryomodule.valveParams.refHeatLoadAct,
            "JT Valve Position": self.cryomodule.valveParams.refValvePos,
        }
        q0_utils.update_json_data(
            self.cryomodule.calib_idx_file, self.time_stamp, newData
        )

    @property
    def dLLdt_dheat(self):
        if not self._slope:
            heat_loads = []
            dll_dts = []
            for run in self.heater_runs:
                heat_loads.append(run.average_heat)
                dll_dts.append(run.dll_dt)

            slope, intercept, r_val, p_val, std_err = linregress(heat_loads, dll_dts)

            if np.isnan(slope):
                self._slope = None
            else:
                self.adjustment = intercept
                self._slope = slope

        return self._slope

    def get_heat(self, dll_dt: float):
        return (dll_dt - self.adjustment) / self.dLLdt_dheat
