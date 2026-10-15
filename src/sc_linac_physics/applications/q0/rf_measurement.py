import json
from datetime import datetime
from typing import Optional, Dict, Tuple, TYPE_CHECKING

import numpy as np

from sc_linac_physics.applications.q0 import q0_utils
from sc_linac_physics.applications.q0.q0_cavity import Q0Cavity

if TYPE_CHECKING:
    from sc_linac_physics.applications.q0.q0_cryomodule import Q0Cryomodule
from sc_linac_physics.applications.q0.rf_run import RFRun


class Q0Measurement:
    def __init__(self, cryomodule: "Q0Cryomodule") -> None:
        self.cryomodule: "Q0Cryomodule" = cryomodule
        self.heater_run: Optional[q0_utils.HeaterRun] = None
        self.rf_run: Optional[RFRun] = None
        self._raw_heat: Optional[float] = None
        self._adjustment: Optional[float] = None
        self._heat_load: Optional[float] = None
        self._q0: Optional[float] = None
        self._start_time: Optional[str] = None
        self._amplitudes: Optional[Dict[int, float]] = None
        self._heater_run_heatload: Optional[float] = None

    @property
    def amplitudes(self):
        return self._amplitudes

    def reset_calculated_properties(self):
        """Reset all calculated properties when base data changes"""
        self._raw_heat = None
        self._adjustment = None
        self._heat_load = None
        self._q0 = None

    def set_fit_window(
        self,
        run: q0_utils.DataRun,
        window: Optional[Tuple[float, float]],
    ) -> None:
        """Fit run's dLL/dt to the samples in window only (None for all).

        run is heater_run or rf_run. Clears the cached heat loads and Q0.
        """
        if run is not self.heater_run and run is not self.rf_run:
            raise ValueError(
                f"{run} is not this measurement's heater or RF run"
            )
        run.fit_window = window
        self.reset_calculated_properties()

    @amplitudes.setter
    def amplitudes(self, amplitudes: Dict[int, float]):
        """Set amplitudes with validation"""
        if not isinstance(amplitudes, dict):
            raise TypeError("Amplitudes must be a dictionary")

        if not amplitudes:
            raise ValueError("Amplitudes dictionary cannot be empty")

        # Validate amplitude values
        for cav_num, amp in amplitudes.items():
            if not isinstance(cav_num, int):
                raise TypeError(
                    f"Cavity number must be integer, got {type(cav_num)}"
                )
            if not isinstance(amp, (int, float)):
                raise TypeError(f"Amplitude must be numeric, got {type(amp)}")
            if amp < 0:
                raise ValueError(f"Amplitude cannot be negative: {amp}")
        self._amplitudes = amplitudes
        self.rf_run = RFRun(amplitudes)
        self.reset_calculated_properties()  # Reset when data changes

    @property
    def heater_run_heatload(self):
        return self._heater_run_heatload

    @heater_run_heatload.setter
    def heater_run_heatload(self, heat_load: float):
        self._heater_run_heatload = heat_load
        self.heater_run = q0_utils.HeaterRun(heat_load)

    @property
    def start_time(self) -> Optional[str]:
        return self._start_time

    @start_time.setter
    def start_time(self, start_time: datetime):
        if not self._start_time:
            self._start_time = start_time.strftime(q0_utils.DATETIME_FORMATTER)

    def load_data(self, time_stamp: str):
        """Load measurement data with improved error handling"""
        try:
            self.start_time = datetime.strptime(
                time_stamp, q0_utils.DATETIME_FORMATTER
            )
        except ValueError as e:
            raise ValueError(f"Invalid timestamp format: {time_stamp}") from e

        try:
            with open(
                self.cryomodule.q0_data_file, "r"
            ) as f:  # Changed from "r+"
                all_data: Dict = json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Q0 data file not found: {self.cryomodule.q0_data_file}"
            )
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in Q0 data file: {e}")

        if time_stamp not in all_data:
            raise KeyError(f"No data found for timestamp: {time_stamp}")

        try:
            q0_meas_data = all_data[time_stamp]
            self._load_heater_run_data(q0_meas_data)
            self._load_rf_run_data(q0_meas_data)
            self.save_data()
        except KeyError as e:
            raise ValueError(f"Missing required data field: {e}")

    def _load_rf_run_data(self, q0_meas_data: dict):
        rf_run_data: Dict = q0_meas_data[q0_utils.JSON_RF_RUN_KEY]
        cav_amps = {}
        for cav_num_str, amp in rf_run_data[q0_utils.JSON_CAV_AMPS_KEY].items():
            cav_amps[int(cav_num_str)] = amp

        self.amplitudes = cav_amps
        self.rf_run.start_time = datetime.strptime(
            rf_run_data[q0_utils.JSON_START_KEY], q0_utils.DATETIME_FORMATTER
        )
        self.rf_run.end_time = datetime.strptime(
            rf_run_data[q0_utils.JSON_END_KEY], q0_utils.DATETIME_FORMATTER
        )
        self.rf_run.average_heat = rf_run_data[
            q0_utils.JSON_HEATER_READBACK_KEY
        ]

        ll_data = {}
        for time_str, val in rf_run_data[q0_utils.JSON_LL_KEY].items():
            ll_data[float(time_str)] = val
        self.rf_run.ll_data = ll_data

        self.rf_run.avg_pressure = rf_run_data[q0_utils.JSON_AVG_PRESS_KEY]

    def _load_heater_run_data(self, q0_meas_data: dict):
        heater_run_data: Dict = q0_meas_data[q0_utils.JSON_HEATER_RUN_KEY]

        self.heater_run_heatload = heater_run_data[
            q0_utils.JSON_HEATER_READBACK_KEY
        ]
        self.heater_run.average_heat = heater_run_data[
            q0_utils.JSON_HEATER_READBACK_KEY
        ]
        self.heater_run.start_time = datetime.strptime(
            heater_run_data[q0_utils.JSON_START_KEY],
            q0_utils.DATETIME_FORMATTER,
        )
        self.heater_run.end_time = datetime.strptime(
            heater_run_data[q0_utils.JSON_END_KEY], q0_utils.DATETIME_FORMATTER
        )
        ll_data = {}
        for time_str, val in heater_run_data[q0_utils.JSON_LL_KEY].items():
            ll_data[float(time_str)] = val
        self.heater_run.ll_data = ll_data

    def save_data(self):
        q0_utils.require_no_fit_windows([self.heater_run, self.rf_run])
        q0_utils.make_json_file(self.cryomodule.q0_data_file)
        heater_data = {
            q0_utils.JSON_START_KEY: self.heater_run.start_time,
            q0_utils.JSON_END_KEY: self.heater_run.end_time,
            q0_utils.JSON_LL_KEY: self.heater_run.ll_data,
            q0_utils.JSON_HEATER_READBACK_KEY: self.heater_run.average_heat,
            q0_utils.JSON_DLL_KEY: self.heater_run.dll_dt,
        }

        rf_data = {
            q0_utils.JSON_START_KEY: self.rf_run.start_time,
            q0_utils.JSON_END_KEY: self.rf_run.end_time,
            q0_utils.JSON_LL_KEY: self.rf_run.ll_data,
            q0_utils.JSON_HEATER_READBACK_KEY: self.rf_run.average_heat,
            q0_utils.JSON_AVG_PRESS_KEY: self.rf_run.avg_pressure,
            q0_utils.JSON_DLL_KEY: self.rf_run.dll_dt,
            q0_utils.JSON_CAV_AMPS_KEY: self.rf_run.amplitudes,
        }

        new_data = {
            q0_utils.JSON_HEATER_RUN_KEY: heater_data,
            q0_utils.JSON_RF_RUN_KEY: rf_data,
        }

        q0_utils.update_json_data(
            self.cryomodule.q0_data_file, self.start_time, new_data
        )

    def save_results(self):
        # The results also come from the calibration curve, so its runs
        # must be unwindowed too.
        q0_utils.require_no_fit_windows(
            [self.heater_run, self.rf_run]
            + self.cryomodule.calibration.heater_runs
        )
        newData = {
            q0_utils.JSON_START_KEY: self.start_time,
            q0_utils.JSON_CAV_AMPS_KEY: self.rf_run.amplitudes,
            "Calculated Adjusted Heat Load": self.heat_load,
            "Calculated Raw Heat Load": self.raw_heat,
            "Calculated Adjustment": self.adjustment,
            "Calculated Q0": self.q0,
            "Calibration Used": self.cryomodule.calibration.time_stamp,
        }

        q0_utils.update_json_data(
            self.cryomodule.q0_idx_file, self.start_time, newData
        )

    @property
    def raw_heat(self):
        if not self._raw_heat:
            self._raw_heat = self.cryomodule.calibration.get_heat(
                self.rf_run.dll_dt
            )
        return self._raw_heat

    @property
    def adjustment(self):
        if not self._adjustment:
            heater_run_raw_heat = self.cryomodule.calibration.get_heat(
                self.heater_run.dll_dt
            )
            self._adjustment = (
                self.heater_run.average_heat - heater_run_raw_heat
            )
        return self._adjustment

    @property
    def heat_load(self):
        if not self._heat_load:
            self._heat_load = self.raw_heat + self.adjustment
        return self._heat_load

    def _q0_from_heat(self, heat_load: float) -> float:
        sum_square_amp = 0

        for amp in self.rf_run.amplitudes.values():
            sum_square_amp += amp**2

        effective_amplitude = np.sqrt(sum_square_amp)

        cavity: "Q0Cavity" = self.cryomodule.cavities[1]
        return q0_utils.calc_q0(
            amplitude=effective_amplitude,
            rf_heat_load=heat_load,
            avg_pressure=self.rf_run.avg_pressure,
            cav_length=cavity.length,
            r_over_q=cavity.r_over_q,
        )

    @property
    def q0(self):
        if not self._q0:
            self._q0 = self._q0_from_heat(self.heat_load)
        return self._q0

    @property
    def q0_linregress(self) -> float:
        """Q0 with every dLL/dt (calibration runs, heater run, RF run) fit
        by linregress instead of dll_dt. Shown beside q0, never saved.

        Same arithmetic as heat_load: raw_heat + adjustment reduces to
        heater average_heat + (rf dLL/dt - heater dLL/dt) / slope, because
        the calibration intercept cancels.
        """
        slope, _ = self.cryomodule.calibration.linregress_line()
        heat_load = (
            self.heater_run.average_heat
            + (
                self.rf_run.dll_dt_linregress
                - self.heater_run.dll_dt_linregress
            )
            / slope
        )
        return self._q0_from_heat(heat_load)

    @property
    def q0_sigma(self) -> float:
        """One-sigma spread on q0 from the RF and heater run fits only.

        sigma_heat = sqrt(rf stderr^2 + heater stderr^2) / |dLLdt_dheat|,
        using each run's correlation-widened linregress stderr
        (DataRun.dll_dt_stderr) as the noise scale for both fits.
        calc_q0 is called uncorrected (use_correction=False), where Q0 is
        proportional to 1 / heat load, so sigma_q0 = q0 * sigma_heat / heat.
        Leaves out calibration-line uncertainty and heater readback error.
        """
        sigma_heat = np.hypot(
            self.rf_run.dll_dt_stderr, self.heater_run.dll_dt_stderr
        ) / abs(self.cryomodule.calibration.dLLdt_dheat)
        return abs(self.q0) * sigma_heat / abs(self.heat_load)

    @property
    def fit_sensitive(self) -> bool:
        """True when q0 and q0_linregress differ by more than
        FIT_SENSITIVE_SIGMAS * q0_sigma."""
        gap = abs(self.q0 - self.q0_linregress)
        return gap > q0_utils.FIT_SENSITIVE_SIGMAS * self.q0_sigma
