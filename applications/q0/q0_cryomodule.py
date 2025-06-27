import os
from datetime import datetime, timedelta
from os.path import isfile
from time import sleep
from typing import Dict, Optional

import numpy as np
from epics import caget, caput, camonitor, camonitor_clear
from lcls_tools.common.data.archiver import get_values_over_time_range
from numpy import linspace, sign, floor
from scipy.signal import medfilt
from scipy.stats import linregress

from applications.q0 import q0_utils
from applications.q0.calibration import Calibration
from applications.q0.q0_utils import round_for_printing
from applications.q0.rf_measurement import Q0Measurement
from applications.q0.rf_run import RFRun
from utils.sc_linac.cryomodule import Cryomodule


class Q0Cryomodule(Cryomodule):
    def __init__(
        self,
        cryo_name,
        linac_object,
    ):
        super().__init__(cryo_name, linac_object)

        self.jt_mode_pv: str = self.make_jt_pv("MODE")
        self.jt_mode_str_pv: str = self.make_jt_pv("MODE_STRING")
        self.jt_manual_select_pv: str = self.make_jt_pv("MANUAL")
        self.jt_auto_select_pv: str = self.make_jt_pv("AUTO")
        self.ds_liq_lev_setpoint_pv: str = self.make_jt_pv("SP_RQST")
        self.jt_man_pos_setpoint_pv: str = self.make_jt_pv("MANPOS_RQST")

        self.heater_setpoint_pv: str = self.make_heater_pv("MANPOS_RQST")
        self.heater_manual_pv: str = self.make_heater_pv("MANUAL")
        self.heater_sequencer_pv: str = self.make_heater_pv("SEQUENCER")
        self.heater_mode_string_pv: str = self.make_heater_pv("MODE_STRING")
        self.heater_mode_pv: str = self.make_heater_pv("MODE")

        self.cryo_access_pv: str = f"CRYO:{self.cryo_name}:0:CAS_ACCESS"

        self.q0_measurements: Dict[str, Q0Measurement] = {}
        self.calibrations: Dict[str, Calibration] = {}

        self.valveParams: Optional[q0_utils.ValveParams] = None

        base_dir = os.path.dirname(os.path.realpath(__file__))

        self._calib_idx_file = f"{base_dir}/calibrations/cm{self.name}.json"
        self._calib_data_file = f"{base_dir}/data/calibrations/cm{self.name}.json"
        self._q0_idx_file = f"{base_dir}/q0_measurements/cm{self.name}.json"
        self._q0_data_file = f"{base_dir}/data/q0_measurements/cm{self.name}.json"

        self.ll_buffer: np.array = np.empty(q0_utils.NUM_LL_POINTS_TO_AVG)
        self.ll_buffer[:] = np.nan
        self._ll_buffer_size = q0_utils.NUM_LL_POINTS_TO_AVG
        self.ll_buffer_idx = 0

        self.measurement_buffer = []
        self.calibration: Optional[Calibration] = None
        self.q0_measurement: Optional[Q0Measurement] = None
        self.current_data_run: Optional[q0_utils.DataRun] = None
        self.cavity_amplitudes = {}

        self.fill_data_run_buffer = False

        self.abort_flag: bool = False

    def check_abort(self):
        if self.abort_flag:
            self.abort_flag = False
            self.restore_cryo()
            for cavity in self.cavities.values():
                cavity.abort_flag = True
            raise q0_utils.Q0AbortError(f"Abort requested for {self}")

    @property
    def calib_data_file(self):
        if not isfile(self._calib_data_file):
            q0_utils.make_json_file(self._calib_data_file)
        return self._calib_data_file

    @property
    def q0_data_file(self):
        if not isfile(self._q0_data_file):
            q0_utils.make_json_file(self._q0_data_file)
        return self._q0_data_file

    @property
    def ll_buffer_size(self):
        return self._ll_buffer_size

    @ll_buffer_size.setter
    def ll_buffer_size(self, value):
        self._ll_buffer_size = value
        self.clear_ll_buffer()

    def clear_ll_buffer(self):
        self.ll_buffer = np.empty(self.ll_buffer_size)
        self.ll_buffer[:] = np.nan
        self.ll_buffer_idx = 0

    def monitor_ll(self, value, **kwargs):
        self.ll_buffer[self.ll_buffer_idx] = value
        self.ll_buffer_idx = (self.ll_buffer_idx + 1) % self.ll_buffer_size
        if self.fill_data_run_buffer:
            self.current_data_run.ll_data[datetime.now().timestamp()] = value

    @property
    def averaged_liquid_level(self) -> float:
        # try to do averaging of the last NUM_LL_POINTS_TO_AVG points to account
        # for signal noise
        avg_ll = np.nanmean(self.ll_buffer)
        if np.isnan(avg_ll):
            return caget(self.ds_level_pv)
        else:
            return avg_ll

    @property
    def q0_idx_file(self) -> str:
        if not isfile(self._q0_idx_file):
            q0_utils.make_json_file(self._q0_idx_file)

        return self._q0_idx_file

    @property
    def calib_idx_file(self) -> str:
        if not isfile(self._calib_idx_file):
            q0_utils.make_json_file(self._calib_idx_file)

        return self._calib_idx_file

    def shut_off(self):
        print("Restoring cryo")
        caput(self.heater_sequencer_pv, 1, wait=True)
        caput(self.jt_auto_select_pv, 1, wait=True)
        print("Turning cavities and SSAs off")
        for cavity in self.cavities.values():
            cavity.turn_off()
            cavity.ssa.turn_off()

    @property
    def heater_power(self):
        return caget(self.heater_readback_pv)

    @heater_power.setter
    def heater_power(self, value):
        while caget(self.heater_mode_pv) != q0_utils.HEATER_MANUAL_VALUE:
            self.check_abort()
            print(f"Setting {self} heaters to manual and waiting 3s")
            caput(self.heater_manual_pv, 1, wait=True)
            sleep(3)

        caput(self.heater_setpoint_pv, value)

        print(f"set {self} heater power to {value} W")

    @property
    def ds_liquid_level(self):
        return self.ds_level_pv_obj.get()

    @ds_liquid_level.setter
    def ds_liquid_level(self, value):
        self.ds_level_pv_obj.put(value)

    def fill(self, desired_level=q0_utils.MAX_DS_LL, turn_cavities_off: bool = True):
        self.ds_liquid_level = desired_level
        print(f"Setting JT to auto for refill to {desired_level}")
        caput(self.jt_auto_select_pv, 1, wait=True)
        self.heater_power = 0

        if turn_cavities_off:
            for cavity in self.cavities.values():
                cavity.turn_off()

        self.waitForLL(desired_level)

    def fillAndLock(self, desiredLevel=q0_utils.MAX_DS_LL):
        self.ds_liquid_level = desiredLevel

        print(f"Setting JT to auto for refill to {desiredLevel}")
        caput(self.jt_auto_select_pv, 1, wait=True)

        self.heater_power = self.valveParams.refHeatLoadDes

        self.waitForLL(desiredLevel)

        self.jt_position = self.valveParams.refValvePos

    def getRefValveParams(self, start_time: datetime, end_time: datetime):
        print(f"\nSearching {start_time} to {end_time} for period of JT stability")
        window_start = start_time
        window_end = start_time + q0_utils.DELTA_NEEDED_FOR_FLATNESS
        while window_end <= end_time:
            self.check_abort()
            print(f"\nChecking window {window_start} to {window_end}")

            data = get_values_over_time_range(
                pv_list=[self.ds_level_pv], start_time=window_start, end_time=window_end
            )
            llVals = medfilt(data.values[self.ds_level_pv])

            # Fit a line to the liquid level over the last [numHours] hours
            m, b, r, _, _ = linregress(range(len(llVals)), llVals)
            print(f"r^2 of linear fit: {r ** 2}")
            print(f"Slope: {m}")

            # If the LL slope is small enough, this may be a good period from
            # which to get a reference valve position & heater params
            if np.log10(abs(m)) < -5:
                signals = [
                    self.jt_valve_readback_pv,
                    self.heater_setpoint_pv,
                    self.heater_readback_pv,
                ]

                data = get_values_over_time_range(
                    pv_list=signals, start_time=window_start, end_time=window_end
                )

                des_val_set = set(data.values[self.heater_setpoint_pv])
                print(
                    f"number of heater setpoints during this time: {len(des_val_set)}"
                )

                # We only want to use time periods in which there were no
                # changes made to the heater settings
                if len(des_val_set) == 1:
                    des_pos = round(np.mean(data.values[self.jt_valve_readback_pv]), 1)
                    heater_des = des_val_set.pop()
                    heater_act = np.mean(data.values[self.heater_readback_pv])

                    print("Stable period found.")
                    print(f"Desired JT valve position: {des_pos}")
                    print(f"Total heater des setting: {heater_des}")

                    self.valveParams = q0_utils.ValveParams(
                        des_pos, heater_des, heater_act
                    )
                    return self.valveParams

            window_end += q0_utils.JT_SEARCH_OVERLAP_DELTA
            window_start += q0_utils.JT_SEARCH_OVERLAP_DELTA

        # If we broke out of the while loop without returning anything, that
        # means that the LL hasn't been stable enough recently. Wait a while for
        # it to stabilize and then try again.
        print(
            "Stable cryo conditions not found in search window  - determining"
            " new JT valve position. Please do not adjust the heaters. Allow "
            "the PID loop to regulate the JT valve position."
        )

        print("Waiting 30 minutes for LL to stabilize then retrying")

        start = datetime.now()
        while (datetime.now() - start) < timedelta(minutes=30):
            self.check_abort()
            sleep(5)

        # Try again but only search the recent past. We have to manipulate the
        # search range a little bit due to how the search start time is rounded
        # down to the nearest half hour.
        return self.getRefValveParams(
            start_time=start_time + timedelta(minutes=30),
            end_time=end_time + timedelta(minutes=30),
        )

    def launchHeaterRun(
        self,
        heater_setpoint,
        target_ll_diff: float = q0_utils.TARGET_LL_DIFF,
        is_cal=True,
    ) -> None:
        self.heater_power = heater_setpoint

        print(f"Waiting for the LL to drop {target_ll_diff}%")

        self.current_data_run: q0_utils.HeaterRun = q0_utils.HeaterRun(
            heater_setpoint - self.valveParams.refHeatLoadAct,
            reference_heat=self.valveParams.refHeatLoadAct,
        )
        if is_cal:
            self.calibration.heater_runs.append(self.current_data_run)

        self.current_data_run.start_time = datetime.now()

        camonitor(self.heater_readback_pv, callback=self.fill_heater_readback_buffer)
        self.fill_data_run_buffer = True
        self.wait_for_ll_drop(target_ll_diff)
        self.fill_data_run_buffer = False
        camonitor_clear(self.heater_readback_pv)

        self.current_data_run.end_time = datetime.now()

        print("Heater run done")

    def wait_for_ll_drop(self, target_ll_diff):
        starting_level = self.averaged_liquid_level
        avg_level = starting_level
        while (starting_level - avg_level) < target_ll_diff:
            self.check_abort()
            avg_level_rounded = round_for_printing(self.averaged_liquid_level)
            print(f"Averaged level is {avg_level_rounded}; waiting 10s")
            avg_level = self.averaged_liquid_level
            sleep(10)

    def fill_pressure_buffer(self, value, **kwargs):
        if self.q0_measurement:
            self.q0_measurement.rf_run.pressure_buffer.append(value)

    def fill_heater_readback_buffer(self, value, **kwargs):
        if self.current_data_run:
            self.current_data_run.heater_readback_buffer.append(value)

    # to be called after setup_for_q0 and each cavity's setup_SELA
    def takeNewQ0Measurement(
        self,
        desiredAmplitudes: Dict[int, float],
        desired_ll: float = q0_utils.MAX_DS_LL,
        ll_drop: float = q0_utils.TARGET_LL_DIFF,
    ):
        self.setup_cryo_for_measurement(desired_ll, turn_cavities_off=False)

        for cav_num, des_amp in desiredAmplitudes.items():
            while abs(caget(self.cavities[cav_num].aact_pv) - des_amp) > 0.1:
                self.check_abort()
                print(f"Waiting for CM{self.name} cavity {cav_num} to be ready")
                sleep(5)

        self.current_data_run: RFRun = self.q0_measurement.rf_run
        self.q0_measurement.rf_run.reference_heat = self.valveParams.refHeatLoadAct
        camonitor(self.heater_readback_pv, callback=self.fill_heater_readback_buffer)
        camonitor(self.ds_pressure_pv, callback=self.fill_pressure_buffer)

        start_time = datetime.now()
        self.q0_measurement.start_time = start_time
        self.q0_measurement.rf_run.start_time = start_time

        self.fill_data_run_buffer = True
        self.wait_for_ll_drop(ll_drop)
        self.fill_data_run_buffer = False
        camonitor_clear(self.heater_readback_pv)
        camonitor_clear(self.ds_pressure_pv)
        self.q0_measurement.rf_run.end_time = datetime.now()

        print(self.q0_measurement.rf_run.dll_dt)

        self.setup_cryo_for_measurement(desired_ll)

        self.launchHeaterRun(
            q0_utils.FULL_MODULE_CALIBRATION_LOAD + self.valveParams.refHeatLoadDes,
            target_ll_diff=ll_drop,
            is_cal=False,
        )
        self.q0_measurement.heater_run = self.current_data_run
        self.q0_measurement.heater_run.reference_heat = self.valveParams.refHeatLoadAct

        print(self.q0_measurement.heater_run.dll_dt)

        self.q0_measurement.save_data()

        end_time = datetime.now()
        caput(
            self.heater_setpoint_pv,
            caget(self.heater_readback_pv) - q0_utils.FULL_MODULE_CALIBRATION_LOAD,
        )

        camonitor_clear(self.ds_level_pv)

        print("\nStart Time: {START}".format(START=start_time))
        print("End Time: {END}".format(END=end_time))

        duration = (end_time - start_time).total_seconds() / 3600
        print("Duration in hours: {DUR}".format(DUR=duration))

        print("Caluclated Q0: ", self.q0_measurement.q0)
        self.q0_measurement.save_results()
        self.restore_cryo()

    def setup_for_q0(
        self, desiredAmplitudes, desired_ll, jt_search_end, jt_search_start
    ):
        self.q0_measurement = Q0Measurement(cryomodule=self)
        self.q0_measurement.amplitudes = desiredAmplitudes
        self.q0_measurement.heater_run_heatload = q0_utils.FULL_MODULE_CALIBRATION_LOAD

        if not self.valveParams:
            self.valveParams = self.getRefValveParams(
                start_time=jt_search_start, end_time=jt_search_end
            )

        camonitor(self.ds_level_pv, callback=self.monitor_ll)
        self.fill(desired_ll)

    def load_calibration(self, time_stamp: str):
        self.calibration: Calibration = Calibration(
            time_stamp=time_stamp, cryomodule=self
        )
        self.calibration.load_data()

    def load_q0_measurement(self, time_stamp):
        self.q0_measurement: Q0Measurement = Q0Measurement(self)
        self.q0_measurement.load_data(time_stamp)

    def take_new_calibration(
        self,
        jt_search_start: datetime = None,
        jt_search_end: datetime = None,
        desired_ll: float = q0_utils.MAX_DS_LL,
        ll_drop: float = q0_utils.TARGET_LL_DIFF,
        num_cal_steps: int = q0_utils.NUM_CAL_STEPS,
        heat_start: float = 130,
        heat_end: float = 160,
    ):
        if not self.valveParams:
            self.valveParams = self.getRefValveParams(
                start_time=jt_search_start, end_time=jt_search_end
            )

        startTime = datetime.now().replace(microsecond=0)
        self.calibration = Calibration(
            time_stamp=startTime.strftime(q0_utils.DATETIME_FORMATTER), cryomodule=self
        )

        print(f"setting {self} heater to {self.valveParams.refHeatLoadDes} W")
        self.heater_power = self.valveParams.refHeatLoadDes

        starting_ll_setpoint = caget(self.ds_liq_lev_setpoint_pv)
        print(f"Starting liquid level setpoint: {starting_ll_setpoint}")

        camonitor(self.ds_level_pv, callback=self.monitor_ll)

        self.setup_cryo_for_measurement(desired_ll)

        for setpoint in linspace(heat_start, heat_end, num_cal_steps):
            self.setup_cryo_for_measurement(desired_ll)
            self.launchHeaterRun(setpoint, target_ll_diff=ll_drop)
            self.current_data_run = None

        self.calibration.save_data()

        print("\nStart Time: {START}".format(START=startTime))
        print("End Time: {END}".format(END=datetime.now()))

        duration = (datetime.now() - startTime).total_seconds() / 3600
        print("Duration in hours: {DUR}".format(DUR=duration))

        self.heater_power = self.valveParams.refHeatLoadDes

        self.restore_cryo()

        self.calibration.save_results()
        camonitor_clear(self.ds_level_pv)

    def restore_cryo(self):
        print("Restoring initial cryo conditions")
        caput(self.jt_auto_select_pv, 1, wait=True)
        self.ds_liquid_level = 92
        caput(self.heater_sequencer_pv, 1, wait=True)

    def setup_cryo_for_measurement(self, desired_ll, turn_cavities_off: bool = True):
        self.fill(desired_ll, turn_cavities_off=turn_cavities_off)
        self.jt_position = self.valveParams.refValvePos
        self.heater_power = self.valveParams.refHeatLoadDes

    @property
    def jt_position(self):
        return caget(self.jt_valve_readback_pv)

    @jt_position.setter
    def jt_position(self, value):
        delta = value - self.jt_position
        step = sign(delta)

        print("Setting JT to manual and waiting for readback to change")
        caput(self.jt_manual_select_pv, 1, wait=True)

        # One way for the JT valve to be locked in the correct position is for
        # it to be in manual mode and at the desired value
        while caget(self.jt_mode_pv) != q0_utils.JT_MANUAL_MODE_VALUE:
            self.check_abort()
            sleep(1)

        print(f"Walking {self} JT to {value}%")
        for _ in range(int(floor(abs(delta)))):
            caput(self.jt_man_pos_setpoint_pv, self.jt_position + step, wait=True)
            sleep(3)

        caput(self.jt_man_pos_setpoint_pv, value)

        print(f"Waiting for {self} JT Valve position to be in tolerance")
        # Wait for the valve position to be within tolerance before continuing
        while abs(self.jt_position - value) > q0_utils.VALVE_POS_TOL:
            self.check_abort()
            sleep(1)

        print(f"{self} JT Valve at {value}")

    def waitForLL(self, desiredLiquidLevel=q0_utils.MAX_DS_LL):
        print(f"Waiting for downstream liquid level to be {desiredLiquidLevel}%")

        while (desiredLiquidLevel - self.averaged_liquid_level) > 0.01:
            self.check_abort()
            avgLevel_rounded = round_for_printing(self.averaged_liquid_level)
            print(
                f"Current averaged level is {avgLevel_rounded}; waiting 10 seconds for more data."
            )
            sleep(10)

        print("downstream liquid level at required value.")
