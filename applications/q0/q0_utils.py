import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from os import devnull
from os.path import isfile
from typing import Any, Dict, List, Optional

import numpy as np
from matplotlib import pyplot as plt
from matplotlib.axes import Axes
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from scipy.stats import linregress, siegelslopes

USE_SIEGELSLOPES = True

DATETIME_FORMATTER = "%m/%d/%y %H:%M:%S"

# The relationship between the LHE content of a cryomodule and the readback from
# the liquid level sensors isn't linear over the full range of the sensors. We
# have chosen to gather all our data with the downstream sensor above 90%. When
# refilling the cryomodule we refill to at least 95%.
MIN_DS_LL = 90
MAX_DS_LL = 93

MIN_US_LL = 66

# Used to reject data where the JT valve wasn't at the correct position
VALVE_POS_TOL = 2

# Used to reject data where the cavity heater wasn't at the correct value
HEATER_TOL = 1.2

# We want the liquid level to drop by at least 2.5% during our runs. This isn't
# actually enforced however, unlike the run duration.
TARGET_LL_DIFF = 4

# Used to reject data where the cavity amplitude wasn't at the correct value
AMPLITUDE_TOL = 0.3

# We fetch data from the JLab archiver with a program called MySampler, which
# samples the chosen PVs at a user-specified time interval. Increase to improve
# statistics, decrease to lower the size of the CSV files and speed up
# MySampler data acquisition.
ARCHIVER_TIME_INTERVAL = 1

# Used in custom input functions
ERROR_MESSAGE = "Please provide valid input"

# This is used to suppress the output of the caput function.
FNULL = open(devnull, "w")

# The starting point for our calibration
INITIAL_CAL_HEAT_LOAD = 8

# The number of distinct heater settings we're using for cryomodule calibrations
NUM_CAL_STEPS = 7

NUM_LL_POINTS_TO_AVG = 10

CAV_HEATER_RUN_LOAD = 24
FULL_MODULE_CALIBRATION_LOAD = 80

CAL_HEATER_DELTA = 8

JT_SEARCH_TIME_RANGE: timedelta = timedelta(hours=24)
JT_SEARCH_OVERLAP_DELTA: timedelta = timedelta(minutes=30)
DELTA_NEEDED_FOR_FLATNESS: timedelta = timedelta(hours=2)

RUN_STATUS_MSSG = "\nWaiting for the LL to drop {DIFF}% " "or below {MIN}%...".format(
    MIN=MIN_DS_LL, DIFF=TARGET_LL_DIFF
)

JT_MANUAL_MODE_VALUE = 0
JT_AUTO_MODE_VALUE = 1

HEATER_MANUAL_VALUE = 0
HEATER_SEQUENCER_VALUE = 2

CRYO_ACCESS_VALUE = 1
MINIMUM_HEATLOAD = 48

JSON_START_KEY = "Start Time"
JSON_END_KEY = "End Time"
JSON_LL_KEY = "Liquid Level Data"
JSON_HEATER_RUN_KEY = "Heater Run"
JSON_RF_RUN_KEY = "RF Run"
JSON_HEATER_READBACK_KEY = "Average Heater Readback"
JSON_DLL_KEY = "dLL/dt"
JSON_CAV_AMPS_KEY = "Cavity Amplitudes"
JSON_AVG_PRESS_KEY = "Average Pressure"


class DataError(Exception):
    pass


class Q0AbortError(Exception):
    pass


class DataRun:
    def __init__(self, reference_heat=0):
        self.ll_data: Dict[float, float] = {}
        self.heater_readback_buffer: List[float] = []
        self._dll_dt = None
        self._start_time: Optional[datetime] = None
        self._end_time: Optional[datetime] = None
        self._average_heat = None
        self.reference_heat = reference_heat

    @property
    def average_heat(self) -> float:
        if not self._average_heat:
            self._average_heat = (
                np.mean(self.heater_readback_buffer) - self.reference_heat
            )
        return self._average_heat

    @average_heat.setter
    def average_heat(self, value: float):
        self._average_heat = value

    @property
    def start_time(self) -> Optional[str]:
        if not self._start_time:
            return None
        return self._start_time.strftime(DATETIME_FORMATTER)

    @start_time.setter
    def start_time(self, value: datetime):
        self._start_time = value

    @property
    def end_time(self) -> Optional[str]:
        if not self._end_time:
            return None
        return self._end_time.strftime(DATETIME_FORMATTER)

    @end_time.setter
    def end_time(self, value: datetime):
        self._end_time = value

    @property
    def dll_dt(self) -> float:
        if not self._dll_dt:
            if USE_SIEGELSLOPES:
                slope, intercept = siegelslopes(
                    list(self.ll_data.values()), list(self.ll_data.keys())
                )
            else:
                slope, intercept, r_val, p_val, std_err = linregress(
                    list(self.ll_data.keys()), list(self.ll_data.values())
                )
            self._dll_dt = slope
        return self._dll_dt

    @dll_dt.setter
    def dll_dt(self, value: float):
        self._dll_dt = value


class HeaterRun(DataRun):
    def __init__(self, heat_load: float, reference_heat=0):
        super().__init__(reference_heat=reference_heat)
        self.heat_load_des: float = heat_load


def update_json_data(filepath, time_stamp, new_data):
    make_json_file(filepath)
    with open(filepath, "r+") as f:
        data: Dict = json.load(f)
        data[time_stamp] = new_data

        # go to the beginning of the file to overwrite the existing data structure
        f.seek(0)
        json.dump(data, f, indent=4)
        f.truncate()


# The calculated Q0 value for this run. Formula from Mike Drury
# (drury@jlab.org) to calculate Q0 from the measured heat load on a cavity,
# the RF gradient used during the test, and the pressure of the incoming
# 2 K helium.
def calc_q0(
    amplitude: float,
    rf_heat_load: float,
    avg_pressure: float,
    cav_length: float,
    use_correction: bool = False,
) -> float:
    # The initial Q0 calculation doesn't account for the temperature
    # variation of the 2 K helium
    r_over_q = 1012

    uncorrected_q0 = ((amplitude * 1e6) ** 2) / (r_over_q * rf_heat_load)
    print(f"Uncorrected Q0: {uncorrected_q0}")

    # We can correct Q0 for the helium temperature
    mbar_to_torr = 0.750062
    temp_from_press = (mbar_to_torr * avg_pressure * 0.0125) + 1.705

    c1 = 271
    c2 = 0.0000726
    c3 = 0.00000214
    c4 = amplitude / cav_length - 0.7
    c5 = 0.000000043
    c6 = -17.02
    c7 = c2 - (c3 * c4) + (c5 * (c4**2))

    corrected_q0 = c1 / (
        (c7 / 2) * np.exp(c6 / 2)
        + c1 / uncorrected_q0
        - (c7 / temp_from_press) * np.exp(c6 / temp_from_press)
    )
    print(f"Corrected Q0: {corrected_q0}")

    return corrected_q0 if use_correction else uncorrected_q0


def make_json_file(filepath):
    if not isfile(filepath):
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w+") as f:
            json.dump({}, f)


class RFError(Exception):
    """
    Exception thrown during RF Execution for the GUI to catch
    """

    pass


class QuenchError(RFError):
    def __init__(self):
        super().__init__("Quench Detected")


class CryoError(Exception):
    """
    Exception thrown during Cryo Execution for the GUI to catch
    """

    pass


def q0_hash(arg_list: List[Any]):
    """
    A hash is effectively a unique numerical identifier. The purpose of a
    hash function is to generate an ID for an object. This function
    takes all the input parameters and XORs (the ^ symbol) them.

    What is an XOR? It's an operator that takes two bit strings and goes
    through them, bit by bit, returning True (1) only if one bit is 0 and the
    other is 1

    EX: consider the following two bit strings a, b, and c = a^b:
          a: 101010010010 (2706 in base 10)
          b: 100010101011 (2219)
          ---------------
          c: 001000111001 (569)

    What we're doing here is taking each input data object's built-in hash
    function (which returns an int) and XORing those ints together. It's not
    QUITE unique, but XOR is the accepted way to hash in Python because
    collisions are extremely rare.

    As to WHY we're doing this, it's to have an easy way to compare
    two data sessions so that we can avoid creating (and storing) duplicate
    data sessions.
    """

    if len(arg_list) == 1:
        return hash(arg_list.pop())

    for arg in arg_list:
        return hash(arg) ^ q0_hash(arg_list[1:])


@dataclass
class ValveParams:
    refValvePos: float
    refHeatLoadDes: float
    refHeatLoadAct: float


def gen_axis(title, xlabel, ylabel):
    # type: (str, str, str) -> Axes
    fig = plt.figure()
    ax = fig.add_subplot(111)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    return ax


def redraw_axis(canvas, title, xlabel, ylabel):
    # type: (FigureCanvasQTAgg, str, str, str) -> None
    canvas.axes.cla()
    canvas.draw_idle()
    canvas.axes.set_title(title)
    canvas.axes.set_xlabel(xlabel)
    canvas.axes.set_ylabel(ylabel)


def draw_and_show():
    # type: () -> None
    plt.draw()
    plt.show()
