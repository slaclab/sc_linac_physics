import json
from datetime import datetime
from typing import List, Dict, Optional, Tuple, TYPE_CHECKING

import numpy as np
from scipy.stats import linregress

from sc_linac_physics.applications.q0 import q0_utils

if TYPE_CHECKING:
    from sc_linac_physics.applications.q0.q0_cryomodule import Q0Cryomodule


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
                    heater_run_data[q0_utils.JSON_END_KEY],
                    q0_utils.DATETIME_FORMATTER,
                )

                ll_data = {}
                for timestamp_str, val in heater_run_data[
                    q0_utils.JSON_LL_KEY
                ].items():
                    ll_data[float(timestamp_str)] = val

                run.ll_data = ll_data
                run.average_heat = heater_run_data[
                    q0_utils.JSON_HEATER_READBACK_KEY
                ]

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
        q0_utils.require_no_fit_windows(self.heater_runs)
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
        q0_utils.require_no_fit_windows(self.heater_runs)
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

            slope, intercept, r_val, p_val, std_err = linregress(
                heat_loads, dll_dts
            )

            if np.isnan(slope):
                raise ValueError("Cannot calculate a linear regression")
            else:
                self.adjustment = intercept
                self._slope = slope

        return self._slope

    def linregress_line(self) -> Tuple[float, float]:
        """(slope, intercept) of the calibration line built from each run's
        dll_dt_linregress instead of dll_dt.

        Only used to show a second Q0 beside the official one; it does not
        touch dLLdt_dheat or adjustment.
        """
        result = linregress(
            [run.average_heat for run in self.heater_runs],
            [run.dll_dt_linregress for run in self.heater_runs],
        )
        return result.slope, result.intercept

    def set_fit_window(
        self,
        run: q0_utils.HeaterRun,
        window: Optional[Tuple[float, float]],
    ) -> None:
        """Fit run's dLL/dt to the samples in window only (None for all).

        Clears the cached slope and adjustment, and the loaded Q0
        measurement's results, since those are computed from this curve.
        """
        if not any(run is heater_run for heater_run in self.heater_runs):
            raise ValueError(f"{run} is not one of this calibration's runs")
        run.fit_window = window
        self._slope = None
        if self.cryomodule.q0_measurement is not None:
            self.cryomodule.q0_measurement.reset_calculated_properties()

    def get_heat(self, dll_dt: float):
        # dLLdt_dheat sets adjustment, so read the slope first.
        slope = self.dLLdt_dheat
        return (dll_dt - self.adjustment) / slope
