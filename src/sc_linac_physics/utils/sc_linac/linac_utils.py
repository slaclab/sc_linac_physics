"""Cryomodule groupings, PV naming, and hardware constants.

Tuner references
----------------
Several tuner constants below are measurements, not choices. Both papers are
open access (CC BY 3.0).

[TUNER-2015]
    Y. Pischalnikov, E. Borissov, I. Gonin, J. Holzbauer, T. Khabiboulline,
    W. Schappert, S. Smith, J.C. Yun (FNAL), "Design and Test of Compact Tuner
    for Narrow Bandwidth SRF Cavities", Proc. IPAC'15, Richmond, VA, USA,
    paper WEPTY035, pp. 3352-3354.
    doi:10.18429/JACoW-IPAC2015-WEPTY035
    https://proceedings.jacow.org/IPAC2015/papers/wepty035.pdf

    Prototype tuner bench measurements: slow tuner sensitivity 1.4 Hz/step
    over a ~450 kHz range (1.3 mm stroke, hard stops); ~30 steps of mechanical
    backlash and ~45 Hz of hysteresis over a +/-150 Hz range; piezo resolution
    bounded at 110 mHz; strongest mechanical resonances near 250 Hz.

[TUNER-2018]
    J.P. Holzbauer, C. Contreras, Y. Pischalnikov, W. Schappert, J.C. Yun
    (FNAL), "Production Tuner Testing for LCLS-II Cryomodule Production",
    Proc. IPAC'18, Vancouver, BC, Canada, paper WEPML004, pp. 2678-2680.
    doi:10.18429/JACoW-IPAC2018-WEPML004
    https://proceedings.jacow.org/IPAC2018/papers/wepml004.pdf

    Acceptance data for 56 tuner/cavity systems across CM1-7, so this is the
    better source for anything expected to hold on a production cavity.
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional

from numpy import polyfit

from sc_linac_physics.utils.epics import PV

# Cryomodule definitions
L0B = ["01"]
L1B = ["02", "03"]
L1BHL = ["H1", "H2"]
L2B = [f"{i:02d}" for i in range(4, 16)]
L3B = [f"{i:02d}" for i in range(16, 36)]
L4B = [f"{i:02d}" for i in range(37, 60)]

# Derived collections
ALL_CRYOMODULES = L0B + L1B + L1BHL + L2B + L3B + L4B
ALL_CRYOMODULES_NO_HL = L0B + L1B + L2B + L3B + L4B

# Linac groupings
LINAC_TUPLES = [
    ("L0B", L0B),
    ("L1B", L1B),
    ("L2B", L2B),
    ("L3B", L3B),
    ("L4B", L4B),
]
LINAC_CM_DICT = dict(enumerate([L0B, L1B + L1BHL, L2B, L3B, L4B]))
LINAC_CM_MAP = [L0B, L1B + L1BHL, L2B, L3B, L4B]

# Vacuum systems
BEAMLINE_VACUUM_INFIXES = [
    ["0198"],
    ["0202", "H292"],
    ["0402", "1592"],
    ["1602", "2594", "2598", "3592"],
    [],  # L4B - update with actual values when known
]

INSULATING_VACUUM_CRYOMODULES = [
    ["01"],
    ["02", "H1"],
    [f"{i:02d}" for i in range(4, 16, 2)],  # Even numbers 04-14
    ["16", "18", "20", "22", "24", "27", "29", "31", "33", "34"],
    [],  # L4B - update with actual values when known
]

CHARACTERIZATION_CRASHED_VALUE = 0
CHARACTERIZATION_RUNNING_VALUE = 2
CALIBRATION_COMPLETE_VALUE = 1


def get_linac_for_cryomodule(cryomodule: str) -> Optional[str]:
    """Get the linac identifier for a given cryomodule.

    Args:
        cryomodule: Cryomodule identifier (e.g., "01", "02", "H1")

    Returns:
        Linac identifier (e.g., "L0B", "L1B") or None if not found
    """
    linac_names = ["L0B", "L1B", "L2B", "L3B", "L4B"]
    for i, cm_list in enumerate(LINAC_CM_MAP):
        if cryomodule in cm_list:
            return linac_names[i]
    return None


SSA_STATUS_ON_VALUE = 3
SSA_STATUS_FAULTED_VALUE = 1
SSA_STATUS_OFF_VALUE = 2
SSA_STATUS_RESETTING_FAULTS_VALUE = 4
SSA_STATUS_FAULT_RESET_FAILED_VALUE = 7
SSA_SLOPE_LOWER_LIMIT = 0.3
SSA_SLOPE_UPPER_LIMIT = 2.0
SSA_RESULT_GOOD_STATUS_VALUE = 0
SSA_FWD_PWR_LOWER_LIMIT = 3000
SSA_CALIBRATION_RUNNING_VALUE = 2
SSA_CALIBRATION_CRASHED_VALUE = 0

HL_SSA_MAP = {1: 1, 2: 2, 3: 3, 4: 4, 5: 1, 6: 2, 7: 3, 8: 4}
HL_SSA_SHARED_PVS = [
    "PSVoltSetpt1",
    "PSVoltSetpt2",
    "StatusMsg",
    "PowerOn",
    "PowerOff",
    "FaultReset",
    "NRP_PRMT",
    "FaultSummary.SEVR",
    "480VACStat",
]

HL_SSA_PS_SETPOINT = 2500

LOADED_Q_LOWER_LIMIT = int(2.5e7)
LOADED_Q_UPPER_LIMIT = int(5.1e7)
DESIGN_Q_LOADED = int(4.1e7)

LOADED_Q_LOWER_LIMIT_HL = int(1.5e7)
LOADED_Q_UPPER_LIMIT_HL = int(3.5e7)
DESIGN_Q_LOADED_HL = int(2.5e7)

CAVITY_SCALE_UPPER_LIMIT = 125
CAVITY_SCALE_LOWER_LIMIT = 10

CAVITY_SCALE_UPPER_LIMIT_HL = 25
CAVITY_SCALE_LOWER_LIMIT_HL = 5

RF_MODE_SELAP = 0
RF_MODE_SELA = 1
RF_MODE_SEL = 2
RF_MODE_SEL_RAW = 3
RF_MODE_PULSE = 4
RF_MODE_CHIRP = 5

SAFE_PULSED_DRIVE_LEVEL = 10
NOMINAL_PULSED_ONTIME = 70

# Kelvin, not Celsius. The stepper sits in the cryomodule insulating vacuum:
# [TUNER-2018] interlocks the motor below 70 K and reports it starting around
# 30 K and rising no more than 4 K during a long motion. The simulation agrees,
# serving STEPTEMP at 35.0 with its alarm limit at 70 (cavity_service.py).
#
# Several call sites label this Celsius -- StepperTempError's message in
# Cavity._auto_tune, and FrequencyTuningLimits.temp_limit_c with the
# stepper_temp_c/temp_limit_c log keys. Those names and that operator-facing
# message are wrong and are being corrected separately; the number is right.
STEPPER_TEMP_LIMIT = 70

# A single move is capped at 1,000,000 usteps; VELO runs at 20,000 usteps/s
# (its EGU reads "usteps/"), so a full-range move is ~50 s. For scale,
# [TUNER-2015] puts the coarse tuner's whole range at ~450 kHz between hard
# stops, and [TUNER-2018] needed ~200 kHz on average -- 300 kHz at worst -- to
# bring a production cavity from cold landing to 1.3 GHz.
DEFAULT_STEPPER_MAX_STEPS = 1000000
DEFAULT_STEPPER_SPEED = 20000
MAX_STEPPER_SPEED = 60000
STEPPER_ON_LIMIT_SWITCH_VALUE = 1

# these values are based on the list of enum states found by probing {magnet_type}:L{x}B:{cm}85:CTRL
MAGNET_RESET_VALUE = 10
MAGNET_ON_VALUE = 11
MAGNET_OFF_VALUE = 12
MAGNET_DEGAUSS_VALUE = 13
MAGNET_TRIM_VALUE = 1

PIEZO_ENABLE_VALUE = 1
PIEZO_DISABLE_VALUE = 0
PIEZO_MANUAL_VALUE = 0
PIEZO_FEEDBACK_VALUE = 1
PIEZO_SCRIPT_RUNNING_VALUE = 2
PIEZO_SCRIPT_COMPLETE_VALUE = 1
PIEZO_SCRIPT_CRASH_VALUE = 0
PIEZO_PRE_RF_CHECKOUT_PASS_VALUE = 0
PIEZO_WITH_RF_GRAD = 6.5
PIEZO_CENTER_VOLTAGE = 25
# 20 Hz/V is the production acceptance figure: +20 V on all four piezo-stacks
# detunes a cavity by ~400 Hz, which is the check that the piezo wiring and
# stacks are healthy before the 100 V measurement [TUNER-2018]. Only the
# simulation uses this; live code reads the per-cavity PZT:SCALE PV, and
# [TUNER-2018] found CM2 running ~2x high because its piezos had not finished
# cooling down when they were qualified.
PIEZO_HZ_PER_VOLT = 20

MICROSTEPS_PER_STEP = 256

# 1.4 Hz/step is the measured slow-tuner sensitivity, not a nominal: the
# prototype measured it over a ~450 kHz range [TUNER-2015], and production
# acceptance requires each cavity to come within 20% of -1.4 Hz/step before the
# tuner is driven to 1.3 GHz [TUNER-2018]. The sign is negative on the machine
# (positive steps lower the frequency); the magnitude is what is stored here,
# and StepperTuner.hz_per_microstep takes abs() of the live SCALE PV.
HZ_PER_STEP = 1.4
HL_HZ_PER_STEP = 18.3

# These are very rough values obtained empirically
# ...and they are one prototype's numbers. [TUNER-2018] measured 56
# tuner/cavity systems and found real spread: CM1 ran 5% low against CM2-6
# (different split-ring cavity interface), and cavity 1 on CM4 and CM5 lower
# again after a change in tuner mounting technique. Live tuning reads the
# per-cavity SCALE PV instead of these; nothing in utils/sc_linac/ or
# applications/ consumes them.
ESTIMATED_MICROSTEPS_PER_HZ = MICROSTEPS_PER_STEP / HZ_PER_STEP
ESTIMATED_MICROSTEPS_PER_HZ_HL = MICROSTEPS_PER_STEP / HL_HZ_PER_STEP

TUNE_CONFIG_RESONANCE_VALUE = 0
TUNE_CONFIG_COLD_VALUE = 1
TUNE_CONFIG_PARKED_VALUE = 2
TUNE_CONFIG_OTHER_VALUE = 3

HW_MODE_ONLINE_VALUE = 0
HW_MODE_MAINTENANCE_VALUE = 1
HW_MODE_OFFLINE_VALUE = 2
HW_MODE_MAIN_DONE_VALUE = 3
HW_MODE_READY_VALUE = 4

INTERLOCK_RESET_ATTEMPTS = 5

# this value is based on historical data, when the decarads were on, but not seeing any FE from a cavity
DECARAD_BACKGROUND_READING_AVG = 0.8
DECARAD_BACKGROUND_READING_RAW = 8

CRYO_NAME_MAP: Dict[str, str] = {"H1": "HL01", "H2": "HL02"}


class SCLinacObject(ABC, object):
    """
    Base class used to represent all components of the LCLS II superconducting
    accelerator (linacs, cryomodules, racks, cavities, SSAs, and tuners)
    """

    @property
    @abstractmethod
    def pv_prefix(self):
        raise NotImplementedError(
            "SC Linac Objects need to implement pv_prefix"
        )

    def pv_addr(self, suffix: str):
        return self.pv_prefix + suffix

    def auto_pv_addr(self, suffix: str):
        return self.pv_addr(f"AUTO:{suffix}")


def build_cavity_pv_base(
    linac_name: str,
    cryomodule_name: str,
    cavity_num: int,
) -> str:
    """Build the base cavity PV without a trailing field suffix."""
    return f"ACCL:{linac_name}:{cryomodule_name}{cavity_num}0"


def build_cavity_pv_prefix(
    linac_name: str,
    cryomodule_name: str,
    cavity_num: int,
) -> str:
    """Build the cavity PV prefix including the trailing separator."""
    return f"{build_cavity_pv_base(linac_name, cryomodule_name, cavity_num)}:"


def build_cavity_pv(
    linac_name: str,
    cryomodule_name: str,
    cavity_num: int,
    suffix: str,
) -> str:
    """Build a full cavity PV for the given suffix."""
    return (
        build_cavity_pv_prefix(linac_name, cryomodule_name, cavity_num) + suffix
    )


def stepper_tol_factor(num_steps) -> float:
    """
    First attempt at making the stepper mover tolerance dependent on the
    steps to move. We have empirically determined that 1.3GHz cavities move
    around 50,000 steps around resonance and 50,000,000 steps for cold landing.
    We want to allow 5x the expected steps around resonance, and 1% of the
    expected steps around cold landing. We also empirically determined that
    this also works to (roughly) triple the steps around resonance for 3.9GHz
    cavities, which are about an order of magnitude lower at resonance (while
    the steps to cold landing are about the same due to both large dead zones
    and large detunes). We are starting with a linear function and seeing how
    that goes.

    Why small moves need the slack: the prototype tuner measured ~30 steps of
    mechanical backlash (motor/planetary gear/spindle/traveling nut) and ~45 Hz
    of hysteresis over a +/-150 Hz range [TUNER-2015]. Those are one effect in
    two units -- 45 Hz at 1.4 Hz/step is ~32 steps -- so at and below the
    10,000 step plateau the backlash is a real fraction of the commanded move,
    and a tolerance factor near 1 would fail on a healthy tuner.
    """

    num_steps = abs(num_steps)

    if num_steps <= 10000:
        return 5

    step_tol_des = {
        10e3: 5,
        100e3: 2.5,
        1e6: 1.25,
        5e6: 1.1,
        10e6: 1.05,
        50e6: 1.01,
    }
    ranges = [(10e3, 100e3), (100e3, 1e6), (1e6, 5e6), (5e6, 50e6)]

    for start, end in ranges:
        if end >= num_steps > start:
            x = [start, end]
            y = [step_tol_des[start], step_tol_des[end]]
            m, b = polyfit(x, y, 1)
            return m * num_steps + b

    return 1.01


class PulseError(Exception):
    """Exception thrown during pulsed cavity operation."""

    pass


class StepperError(Exception):
    """Exception thrown when the stepper tuner motor fails or times out."""

    pass


class StepperTempError(StepperError):
    """Exception thrown when the stepper motor exceeds its temperature limit."""

    pass


class FSCANError(Exception):
    """Exception thrown when a rack FSCAN scan fails or times out."""

    pass


class SSACalibrationError(Exception):
    """
    Exception thrown during cavity SSA calibration
    """

    pass


class SSACalibrationToleranceError(Exception):
    """
    Exception thrown during cavity SSA calibration
    """

    pass


class CavityQLoadedCalibrationError(Exception):
    """
    Exception thrown during cavity loaded Q measurement
    """

    pass


class CavityCharacterizationError(Exception):
    """
    Exception thrown during cavity characterization
    """

    pass


class CavityScaleFactorCalibrationError(Exception):
    """
    Exception thrown during cavity scale factor calibration
    """

    pass


class SSAPowerError(Exception):
    """
    Exception thrown while trying to turn an SSA on or off
    """

    pass


class SSAFaultError(Exception):
    """Exception thrown when an SSA fault is detected and cannot be cleared."""

    pass


class DetuneError(Exception):
    """
    Exception thrown when the detune PV is out of tolerance or invalid
    """

    pass


class QuenchError(Exception):
    """
    Exception thrown when the quench fault is latched
    """

    pass


class StepperAbortError(Exception):
    pass


class CavityAbortError(Exception):
    pass


class CavityFaultError(Exception):
    pass


class CavityHWModeError(Exception):
    pass


class LauncherLinacObject(SCLinacObject):
    """Mixin for objects that can be started, stopped, and aborted via AUTO: PVs.

    Provides trigger_start/trigger_stop/trigger_abort/clear_abort methods backed
    by EPICS PVs at ``{pv_prefix}AUTO:{name}STRT``, ``{pv_prefix}AUTO:{name}STOP``,
    and ``{pv_prefix}AUTO:ABORT``.
    Used by all setup/commissioning hierarchy classes.
    """

    @property
    def pv_prefix(self):
        return super().pv_prefix

    def __init__(self, name: str):
        super().__init__()
        self.abort_pv: str = self.auto_pv_addr("ABORT")
        self._abort_pv_obj: Optional[PV] = None

        self.stop_pv: str = self.auto_pv_addr(f"{name}STOP")
        self._stop_pv_obj: Optional[PV] = None

        self.start_pv: str = self.auto_pv_addr(f"{name}STRT")
        self._start_pv_obj: Optional[PV] = None

    @property
    def start_pv_obj(self) -> PV:
        if not self._start_pv_obj:
            self._start_pv_obj = PV(self.start_pv)
        return self._start_pv_obj

    @property
    def stop_pv_obj(self) -> PV:
        if not self._stop_pv_obj:
            self._stop_pv_obj = PV(self.stop_pv)
        return self._stop_pv_obj

    def trigger_abort(self):
        self.abort_pv_obj.put(1)

    def trigger_stop(self):
        self.stop_pv_obj.put(1)

    @property
    def abort_pv_obj(self):
        if not self._abort_pv_obj:
            self._abort_pv_obj = PV(self.abort_pv)
        return self._abort_pv_obj

    @property
    def abort_requested(self):
        return bool(self.abort_pv_obj.get())

    def clear_abort(self):
        raise NotImplementedError

    def trigger_start(self):
        self.start_pv_obj.put(1, wait=False)


PARK_DETUNE = 10000
STATUS_READY_VALUE = 0
STATUS_RUNNING_VALUE = 1
STATUS_ERROR_VALUE = 2
