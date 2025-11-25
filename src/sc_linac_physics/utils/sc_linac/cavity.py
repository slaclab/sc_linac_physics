import logging
import time
from datetime import datetime
from typing import Optional, Callable, TYPE_CHECKING

from sc_linac_physics.utils.epics import PV, EPICS_INVALID_VAL, PVInvalidError
from sc_linac_physics.utils.logger import BASE_LOG_DIR, custom_logger
from sc_linac_physics.utils.sc_linac import linac_utils
from sc_linac_physics.utils.sc_linac.linac_utils import (
    STATUS_RUNNING_VALUE,
    STATUS_ERROR_VALUE,
)

if TYPE_CHECKING:
    from linac import Linac
    from cryomodule import Cryomodule

    from piezo import Piezo
    from rack import Rack
    from ssa import SSA
    from stepper import StepperTuner


class Cavity(linac_utils.SCLinacObject):
    """
    Python representation of LCLS II cavities. This class provides utility
    functions for commonly used tasks including powering on/off, changing RF mode,
    setting amplitude, characterizing, and tuning to resonance

    """

    def __init__(self, cavity_num: int, rack_object: "Rack"):
        """
        @param cavity_num: int cavity number i.e. 1 - 8
        @param rack_object: the rack object the cavities belong to
        """

        self.number: int = cavity_num
        self.rack: Rack = rack_object
        self.cryomodule: "Cryomodule" = self.rack.cryomodule
        self.linac: "Linac" = self.cryomodule.linac

        # Initialize logger (can be overridden by subclasses)
        self._logger = None

        if self.cryomodule.is_harmonic_linearizer:
            self.length = 0.346
            self.frequency = 3.9e9
            self.loaded_q_lower_limit = linac_utils.LOADED_Q_LOWER_LIMIT_HL
            self.loaded_q_upper_limit = linac_utils.LOADED_Q_UPPER_LIMIT_HL
            self.scale_factor_lower_limit = (
                linac_utils.CAVITY_SCALE_LOWER_LIMIT_HL
            )
            self.scale_factor_upper_limit = (
                linac_utils.CAVITY_SCALE_UPPER_LIMIT_HL
            )
        else:
            self.length = 1.038
            self.frequency = 1.3e9
            self.loaded_q_lower_limit = linac_utils.LOADED_Q_LOWER_LIMIT
            self.loaded_q_upper_limit = linac_utils.LOADED_Q_UPPER_LIMIT
            self.scale_factor_lower_limit = linac_utils.CAVITY_SCALE_LOWER_LIMIT
            self.scale_factor_upper_limit = linac_utils.CAVITY_SCALE_UPPER_LIMIT

        self._pv_prefix = (
            f"ACCL:{self.linac.name}:{self.cryomodule.name}{self.number}0:"
        )

        self.ctePrefix = f"CTE:CM{self.cryomodule.name}:1{self.number}"

        self.chirp_prefix = self._pv_prefix + "CHIRP:"

        self.abort_flag: bool = False

        # These need to be created after all the base cavity properties are defined
        self.ssa: "SSA" = self.rack.ssa_class(cavity=self)
        self.stepper_tuner: "StepperTuner" = self.rack.stepper_class(
            cavity=self
        )
        self.piezo: "Piezo" = self.rack.piezo_class(cavity=self)

        self._calc_probe_q_pv_obj: Optional[PV] = None
        self.calc_probe_q_pv: str = self.pv_addr("QPROBE_CALC1.PROC")

        self._push_ssa_slope_pv_obj: Optional[PV] = None
        self.push_ssa_slope_pv: str = self.pv_addr("PUSH_SSA_SLOPE.PROC")

        self.save_ssa_slope_pv: str = self.pv_addr("SAVE_SSA_SLOPE.PROC")
        self._save_ssa_slope_pv_obj: Optional[PV] = None

        self.interlock_reset_pv: str = self.pv_addr("INTLK_RESET_ALL")
        self._interlock_reset_pv_obj: Optional[PV] = None

        self.drive_level_pv: str = self.pv_addr("SEL_ASET")
        self._drive_level_pv_obj: Optional[PV] = None

        self.characterization_start_pv: str = self.pv_addr("PROBECALSTRT")
        self._characterization_start_pv_obj: Optional[PV] = None

        self.characterization_status_pv: str = self.pv_addr("PROBECALSTS")
        self._characterization_status_pv_obj: Optional[PV] = None

        self.current_q_loaded_pv: str = self.pv_addr("QLOADED")

        self.measured_loaded_q_pv: str = self.pv_addr("QLOADED_NEW")
        self._measured_loaded_q_pv_obj: Optional[PV] = None

        self.push_loaded_q_pv: str = self.pv_addr("PUSH_QLOADED.PROC")
        self._push_loaded_q_pv_obj: Optional[PV] = None

        self.save_q_loaded_pv: str = self.pv_addr("SAVE_QLOADED.PROC")

        self.current_cavity_scale_pv: str = self.pv_addr("CAV:SCALER_SEL.B")

        self.measured_scale_factor_pv: str = self.pv_addr("CAV:CAL_SCALEB_NEW")
        self._measured_scale_factor_pv_obj: Optional[PV] = None

        self.push_scale_factor_pv: str = self.pv_addr("PUSH_CAV_SCALE.PROC")
        self._push_scale_factor_pv_obj: Optional[PV] = None

        self.save_cavity_scale_pv: str = self.pv_addr("SAVE_CAV_SCALE.PROC")

        self.ades_pv: str = self.pv_addr("ADES")
        self._ades_pv_obj: Optional[PV] = None

        self.acon_pv: str = self.pv_addr("ACON")
        self._acon_pv_obj: Optional[PV] = None

        self.aact_pv: str = self.pv_addr("AACTMEAN")
        self._aact_pv_obj: Optional[PV] = None

        self.ades_max_pv: str = self.pv_addr("ADES_MAX")
        self._ades_max_pv_obj: Optional[PV] = None

        self.rf_mode_ctrl_pv: str = self.pv_addr("RFMODECTRL")
        self._rf_mode_ctrl_pv_obj: Optional[PV] = None

        self.rf_mode_pv: str = self.pv_addr("RFMODE")
        self._rf_mode_pv_obj: Optional[PV] = None

        self.rf_state_pv: str = self.pv_addr("RFSTATE")
        self._rf_state_pv_obj: Optional[PV] = None

        self.rf_control_pv: str = self.pv_addr("RFCTRL")
        self._rf_control_pv_obj: Optional[PV] = None

        self.pulse_go_pv: str = self.pv_addr("PULSE_DIFF_SUM")
        self._pulse_go_pv_obj: Optional[PV] = None

        self.pulse_status_pv: str = self.pv_addr("PULSE_STATUS")
        self._pulse_status_pv_obj: Optional[PV] = None

        self.pulse_on_time_pv: str = self.pv_addr("PULSE_ONTIME")
        self._pulse_on_time_pv_obj: Optional[PV] = None

        self.rev_waveform_pv: str = self.pv_addr("REV:AWF")
        self.fwd_waveform_pv: str = self.pv_addr("FWD:AWF")
        self.cav_waveform_pv: str = self.pv_addr("CAV:AWF")

        self.stepper_temp_pv: str = self.pv_addr("STEPTEMP")

        self.detune_best_pv: str = self.pv_addr("DFBEST")
        self._detune_best_pv_obj: Optional[PV] = None

        self.detune_chirp_pv: str = self.pv_addr("CHIRP:DF")
        self._detune_chirp_pv_obj: Optional[PV] = None

        self.rf_permit_pv: str = self.pv_addr("RFPERMIT")
        self._rf_permit_pv_obj: Optional[PV] = None

        self.quench_latch_pv: str = self.pv_addr("QUENCH_LTCH")
        self._quench_latch_pv_obj: Optional[PV] = None

        self.quench_bypass_pv: str = self.pv_addr("QUENCH_BYP")

        self.cw_data_decimation_pv: str = self.pv_addr("ACQ_DECIM_SEL.A")
        self._cw_data_decim_pv_obj: Optional[PV] = None

        self.pulsed_data_decimation_pv: str = self.pv_addr("ACQ_DECIM_SEL.C")
        self._pulsed_data_decim_pv_obj: Optional[PV] = None

        self.tune_config_pv: str = self.pv_addr("TUNE_CONFIG")
        self._tune_config_pv_obj: Optional[PV] = None

        self.chirp_freq_start_pv: str = self.chirp_prefix + "FREQ_START"
        self._chirp_freq_start_pv_obj: Optional[PV] = None

        self.chirp_freq_stop_pv: str = self.chirp_prefix + "FREQ_STOP"
        self._chirp_freq_stop_pv_obj: Optional[PV] = None

        self.hw_mode_pv: str = self.pv_addr("HWMODE")
        self._hw_mode_pv_obj: Optional[PV] = None

        self.char_timestamp_pv: str = self.pv_addr("PROBECALTS")
        self._char_timestamp_pv_obj: Optional[PV] = None

        self.progress_pv: str = self.auto_pv_addr("PROG")
        self._progress_pv_obj: Optional[PV] = None

        self.status_pv: str = self.auto_pv_addr("STATUS")
        self._status_pv_obj: Optional[PV] = None

        self.status_msg_pv: str = self.auto_pv_addr("MSG")
        self._status_msg_pv_obj: Optional[PV] = None

        self.note_pv: str = self.auto_pv_addr("NOTE")
        self._note_pv_obj: Optional[PV] = None

    def __str__(self):
        return (
            f"{self.linac.name} CM{self.cryomodule.name} Cavity {self.number}"
        )

    def _init_logger(self):
        """Initialize the default logger. Can be overridden by subclasses."""

        log_dir = BASE_LOG_DIR / self.cryomodule.name / f"cavity_{self.number}"
        logger_name = f"{self.cryomodule.name}.CAV{self.number}"

        self._logger = custom_logger(
            name=logger_name,
            log_dir=str(log_dir),
            log_filename=f"cavity_{self.number}",
        )

    @property
    def logger(self):
        """Get the logger instance (lazy initialization)."""
        if self._logger is None:
            self._init_logger()
        return self._logger

    @logger.setter
    def logger(self, logger_instance):
        """Allow setting a custom logger."""
        self._logger = logger_instance

    @property
    def pv_prefix(self):
        return self._pv_prefix

    @property
    def note_pv_obj(self) -> PV:
        if not self._note_pv_obj:
            self._note_pv_obj = PV(self.note_pv)
        return self._note_pv_obj

    @property
    def status_pv_obj(self):
        if not self._status_pv_obj:
            self._status_pv_obj = PV(self.status_pv)
        return self._status_pv_obj

    @property
    def status(self):
        return self.status_pv_obj.get()

    @status.setter
    def status(self, value: int):
        self.status_pv_obj.put(value)

    @property
    def script_is_running(self) -> bool:
        return self.status == STATUS_RUNNING_VALUE

    @property
    def progress_pv_obj(self):
        if not self._progress_pv_obj:
            self._progress_pv_obj = PV(self.progress_pv)
        return self._progress_pv_obj

    @property
    def progress(self) -> float:
        return self.progress_pv_obj.get()

    @progress.setter
    def progress(self, value: float):
        self.progress_pv_obj.put(value)

    @property
    def status_msg_pv_obj(self) -> PV:
        if not self._status_msg_pv_obj:
            self._status_msg_pv_obj = PV(self.status_msg_pv)
        return self._status_msg_pv_obj

    @property
    def status_message(self):
        return self.status_msg_pv_obj.get()

    @status_message.setter
    def status_message(self, message: str):
        # Default to INFO level for backward compatibility
        self.set_status_message(message, logging.INFO)

    def set_status_message(
        self, message: str, level: int = logging.INFO, extra_data: dict = None
    ):
        """
        Set the status message and log it at the specified level.

        @param message: The status message to set and log
        @param level: The logging level (default: logging.INFO)
        @param extra_data: Optional dictionary of extra context data for logging
        """
        # Prepare extra parameter for logging if extra_data is provided
        extra = {"extra_data": extra_data} if extra_data else None

        # Map logging level to appropriate logger method
        if level >= logging.ERROR:
            self.status = STATUS_ERROR_VALUE
            self.logger.error(message, extra=extra)
        elif level >= logging.WARNING:
            self.logger.warning(message, extra=extra)
        elif level >= logging.INFO:
            self.logger.info(message, extra=extra)
        else:
            self.logger.debug(message, extra=extra)

        self.status_msg_pv_obj.put(message)

    @property
    def microsteps_per_hz(self):
        return 1 / self.stepper_tuner.hz_per_microstep

    def start_characterization(self):
        if not self._characterization_start_pv_obj:
            self._characterization_start_pv_obj = PV(
                self.characterization_start_pv
            )
        self._characterization_start_pv_obj.put(1, wait=False)

    @property
    def cw_data_decimation_pv_obj(self) -> PV:
        if not self._cw_data_decim_pv_obj:
            self._cw_data_decim_pv_obj = PV(self.cw_data_decimation_pv)
        return self._cw_data_decim_pv_obj

    @property
    def cw_data_decimation(self):
        return self.cw_data_decimation_pv_obj.get()

    @cw_data_decimation.setter
    def cw_data_decimation(self, value: float):
        self.cw_data_decimation_pv_obj.put(value)

    @property
    def pulsed_data_decimation_pv_obj(self) -> PV:
        if not self._pulsed_data_decim_pv_obj:
            self._pulsed_data_decim_pv_obj = PV(self.pulsed_data_decimation_pv)
        return self._pulsed_data_decim_pv_obj

    @property
    def pulsed_data_decimation(self):
        return self.pulsed_data_decimation_pv_obj.get()

    @pulsed_data_decimation.setter
    def pulsed_data_decimation(self, value):
        self.pulsed_data_decimation_pv_obj.put(value)

    @property
    def rf_control_pv_obj(self) -> PV:
        if not self._rf_control_pv_obj:
            self._rf_control_pv_obj = PV(self.rf_control_pv)
        return self._rf_control_pv_obj

    @property
    def rf_control(self):
        return self.rf_control_pv_obj.get()

    @rf_control.setter
    def rf_control(self, value):
        self.rf_control_pv_obj.put(value)

    @property
    def rf_mode(self):
        if not self._rf_mode_pv_obj:
            self._rf_mode_pv_obj = PV(self.rf_mode_pv)
        return self._rf_mode_pv_obj.get()

    @property
    def rf_mode_ctrl_pv_obj(self) -> PV:
        if not self._rf_mode_ctrl_pv_obj:
            self._rf_mode_ctrl_pv_obj = PV(self.rf_mode_ctrl_pv)
        return self._rf_mode_ctrl_pv_obj

    def set_chirp_mode(self):
        self.rf_mode_ctrl_pv_obj.put(linac_utils.RF_MODE_CHIRP)

    def set_sel_mode(self):
        self.rf_mode_ctrl_pv_obj.put(linac_utils.RF_MODE_SEL)

    def set_sela_mode(self):
        self.rf_mode_ctrl_pv_obj.put(linac_utils.RF_MODE_SELA)

    def set_selap_mode(self):
        self.rf_mode_ctrl_pv_obj.put(linac_utils.RF_MODE_SELAP)

    @property
    def drive_level_pv_obj(self):
        if not self._drive_level_pv_obj:
            self._drive_level_pv_obj = PV(self.drive_level_pv)
        return self._drive_level_pv_obj

    @property
    def drive_level(self):
        return self.drive_level_pv_obj.get()

    @drive_level.setter
    def drive_level(self, value):
        self.drive_level_pv_obj.put(value)

    def push_ssa_slope(self):
        if not self._push_ssa_slope_pv_obj:
            self._push_ssa_slope_pv_obj = PV(
                self._pv_prefix + "PUSH_SSA_SLOPE.PROC"
            )
        self._push_ssa_slope_pv_obj.put(1, wait=False)

    def save_ssa_slope(self):
        if not self._save_ssa_slope_pv_obj:
            self._save_ssa_slope_pv_obj = PV(self.save_ssa_slope_pv)
        self._save_ssa_slope_pv_obj.put(1, wait=False)

    @property
    def measured_loaded_q(self) -> float:
        if not self._measured_loaded_q_pv_obj:
            self._measured_loaded_q_pv_obj = PV(self.measured_loaded_q_pv)
        return self._measured_loaded_q_pv_obj.get()

    @property
    def measured_loaded_q_in_tolerance(self) -> bool:
        return (
            self.loaded_q_lower_limit
            <= self.measured_loaded_q
            <= self.loaded_q_upper_limit
        )

    def push_loaded_q(self):
        if not self._push_loaded_q_pv_obj:
            self._push_loaded_q_pv_obj = PV(self.push_loaded_q_pv)
        self._push_loaded_q_pv_obj.put(1, wait=False)

    @property
    def measured_scale_factor(self) -> float:
        if not self._measured_scale_factor_pv_obj:
            self._measured_scale_factor_pv_obj = PV(
                self.measured_scale_factor_pv
            )
        return self._measured_scale_factor_pv_obj.get()

    @property
    def measured_scale_factor_in_tolerance(self) -> bool:
        return (
            self.scale_factor_lower_limit
            <= self.measured_scale_factor
            <= self.scale_factor_upper_limit
        )

    def push_scale_factor(self):
        if not self._push_scale_factor_pv_obj:
            self._push_scale_factor_pv_obj = PV(self.push_scale_factor_pv)
        self._push_scale_factor_pv_obj.put(1, wait=False)

    @property
    def characterization_status(self):
        if not self._characterization_status_pv_obj:
            self._characterization_status_pv_obj = PV(
                self.characterization_status_pv
            )
        return self._characterization_status_pv_obj.get()

    @property
    def characterization_running(self) -> bool:
        return (
            self.characterization_status
            == linac_utils.CHARACTERIZATION_RUNNING_VALUE
        )

    @property
    def characterization_crashed(self) -> bool:
        return (
            self.characterization_status
            == linac_utils.CHARACTERIZATION_CRASHED_VALUE
        )

    @property
    def pulse_on_time(self):
        if not self._pulse_on_time_pv_obj:
            self._pulse_on_time_pv_obj = PV(self.pulse_on_time_pv)
        return self._pulse_on_time_pv_obj.get()

    @pulse_on_time.setter
    def pulse_on_time(self, value: int):
        if not self._pulse_on_time_pv_obj:
            self._pulse_on_time_pv_obj = PV(self.pulse_on_time_pv)
        self._pulse_on_time_pv_obj.put(value)

    @property
    def pulse_status(self):
        if not self._pulse_status_pv_obj:
            self._pulse_status_pv_obj = PV(self.pulse_status_pv)
        return self._pulse_status_pv_obj.get()

    @property
    def rf_permit(self):
        if not self._rf_permit_pv_obj:
            self._rf_permit_pv_obj = PV(self.rf_permit_pv)
        return self._rf_permit_pv_obj.get()

    @property
    def rf_inhibited(self) -> bool:
        return self.rf_permit == 0

    @property
    def ades(self):
        if not self._ades_pv_obj:
            self._ades_pv_obj = PV(self.ades_pv)
        return self._ades_pv_obj.get()

    @ades.setter
    def ades(self, value: float):
        if not self._ades_pv_obj:
            self._ades_pv_obj = PV(self._pv_prefix + "ADES")
        self._ades_pv_obj.put(value)

    @property
    def acon(self):
        if not self._acon_pv_obj:
            self._acon_pv_obj = PV(self.acon_pv)
        return self._acon_pv_obj.get()

    @acon.setter
    def acon(self, value: float):
        if not self._acon_pv_obj:
            self._acon_pv_obj = PV(self.acon_pv)
        self._acon_pv_obj.put(value)

    @property
    def aact(self):
        if not self._aact_pv_obj:
            self._aact_pv_obj = PV(self.aact_pv)
        return self._aact_pv_obj.get()

    @property
    def ades_max(self):
        if not self._ades_max_pv_obj:
            self._ades_max_pv_obj = PV(self.ades_max_pv)
        return self._ades_max_pv_obj.get()

    @property
    def edm_macro_string(self):
        rfs_map = {
            1: "1A",
            2: "1A",
            3: "2A",
            4: "2A",
            5: "1B",
            6: "1B",
            7: "2B",
            8: "2B",
        }

        rfs = rfs_map[self.number]

        r = self.rack.rack_name

        # need to remove trailing colon and zeroes to match needed format
        cm = self.cryomodule.pv_prefix[:-3]

        # "id" shadows built-in id, renaming
        macro_id = self.cryomodule.name

        ch = 2 if self.number in [2, 4] else 1

        return f"C={self.number},RFS={rfs},R={r},CM={cm},ID={macro_id},CH={ch}"

    @property
    def cryo_edm_macro_string(self):
        cm = self.cryomodule.name
        area = self.cryomodule.linac.name
        return f"CM={cm},AREA={area}"

    @property
    def hw_mode_pv_obj(self) -> PV:
        if not self._hw_mode_pv_obj:
            self._hw_mode_pv_obj = PV(self.hw_mode_pv)
        return self._hw_mode_pv_obj

    @property
    def hw_mode(self):
        return self.hw_mode_pv_obj.get()

    @property
    def is_online(self) -> bool:
        return self.hw_mode == linac_utils.HW_MODE_ONLINE_VALUE

    @property
    def is_offline(self) -> bool:
        return self.hw_mode == linac_utils.HW_MODE_OFFLINE_VALUE

    @property
    def is_quenched(self) -> bool:
        if not self._quench_latch_pv_obj:
            self._quench_latch_pv_obj = PV(self.quench_latch_pv)
        if self._quench_latch_pv_obj.severity == EPICS_INVALID_VAL:
            raise PVInvalidError(f"{self} quench latch PV invalid")
        return self._quench_latch_pv_obj.get() == 1

    @property
    def tune_config_pv_obj(self) -> PV:
        if not self._tune_config_pv_obj:
            self._tune_config_pv_obj = PV(self.tune_config_pv)
        return self._tune_config_pv_obj

    @property
    def chirp_freq_start_pv_obj(self) -> PV:
        if not self._chirp_freq_start_pv_obj:
            self._chirp_freq_start_pv_obj = PV(self.chirp_freq_start_pv)
        return self._chirp_freq_start_pv_obj

    @property
    def chirp_freq_start(self):
        return self.chirp_freq_start_pv_obj.get()

    @chirp_freq_start.setter
    def chirp_freq_start(self, value):
        self.chirp_freq_start_pv_obj.put(value)

    @property
    def freq_stop_pv_obj(self) -> PV:
        if not self._chirp_freq_stop_pv_obj:
            self._chirp_freq_stop_pv_obj = PV(self.chirp_freq_stop_pv)
        return self._chirp_freq_stop_pv_obj

    @property
    def chirp_freq_stop(self):
        return self.freq_stop_pv_obj.get()

    @chirp_freq_stop.setter
    def chirp_freq_stop(self, value):
        self.freq_stop_pv_obj.put(value)

    @property
    def calc_probe_q_pv_obj(self) -> PV:
        if not self._calc_probe_q_pv_obj:
            self._calc_probe_q_pv_obj = PV(self.calc_probe_q_pv)
        return self._calc_probe_q_pv_obj

    def calculate_probe_q(self):
        self.calc_probe_q_pv_obj.put(1, wait=False)

    def set_chirp_range(self, offset: int):
        offset = abs(offset)
        self.set_status_message(
            f"Setting chirp range to +/- {offset} Hz",
            logging.INFO,
            extra_data={"offset_hz": offset, "cavity": str(self)},
        )
        self.chirp_freq_start = -offset
        self.chirp_freq_stop = offset
        self.set_status_message("Chirp range set successfully", logging.INFO)

    @property
    def rf_state_pv_obj(self) -> PV:
        if not self._rf_state_pv_obj:
            self._rf_state_pv_obj = PV(self.rf_state_pv)
        return self._rf_state_pv_obj

    @property
    def rf_state(self):
        """This property is read only"""
        return self.rf_state_pv_obj.get()

    @property
    def is_on(self) -> bool:
        return self.rf_state == 1

    @property
    def turned_off(self) -> bool:
        return self.rf_control == 0

    def delta_piezo(self):
        delta_volts = self.piezo.voltage - linac_utils.PIEZO_CENTER_VOLTAGE
        delta_hz = delta_volts * self.piezo.hz_per_v
        self.set_status_message(
            "Piezo detune calculated",
            logging.DEBUG,
            extra_data={
                "delta_volts": delta_volts,
                "delta_hz": delta_hz,
                "cavity": str(self),
            },
        )
        return (
            delta_hz
            if not self.cryomodule.is_harmonic_linearizer
            else -delta_hz
        )

    def move_to_resonance(self, reset_signed_steps=False, use_sela=False):
        def delta_detune():
            return self.detune

        self.setup_tuning(use_sela=use_sela)
        mode = "SELA" if use_sela else "chirp"
        self.set_status_message(
            f"Tuning to resonance in {mode} mode",
            logging.INFO,
            extra_data={
                "reset_signed_steps": reset_signed_steps,
                "mode": mode,
                "cavity": str(self),
            },
        )

        self._auto_tune(
            delta_hz_func=delta_detune,
            tolerance=(500 if self.cryomodule.is_harmonic_linearizer else 50),
            reset_signed_steps=reset_signed_steps,
        )

        if use_sela:
            self.set_status_message("Centering piezo", logging.INFO)
            self._auto_tune(
                delta_hz_func=self.delta_piezo,
                tolerance=5 * self.piezo.hz_per_v,
                reset_signed_steps=False,
            )

        self.tune_config_pv_obj.put(linac_utils.TUNE_CONFIG_RESONANCE_VALUE)

    @property
    def detune_best_pv_obj(self) -> PV:
        if not self._detune_best_pv_obj:
            self._detune_best_pv_obj = PV(self.detune_best_pv)
        return self._detune_best_pv_obj

    @property
    def detune_chirp_pv_obj(self) -> PV:
        if not self._detune_chirp_pv_obj:
            self._detune_chirp_pv_obj = PV(self.detune_chirp_pv)
        return self._detune_chirp_pv_obj

    @property
    def detune_best(self):
        return self.detune_best_pv_obj.get()

    @property
    def detune_chirp(self):
        return self.detune_chirp_pv_obj.get()

    @property
    def detune(self):
        if self.rf_mode == linac_utils.RF_MODE_CHIRP:
            return self.detune_chirp
        else:
            return self.detune_best

    @property
    def detune_invalid(self) -> bool:
        if self.rf_mode == linac_utils.RF_MODE_CHIRP:
            return self.detune_chirp_pv_obj.severity == EPICS_INVALID_VAL
        else:
            return self.detune_best_pv_obj.severity == EPICS_INVALID_VAL

    def _auto_tune(
        self,
        delta_hz_func: Callable,
        tolerance: int = 50,
        reset_signed_steps: bool = False,
    ):
        if self.detune_invalid:
            raise linac_utils.DetuneError(f"{self} detune invalid")

        delta_hz = delta_hz_func()
        expected_steps: int = abs(int(delta_hz * self.microsteps_per_hz))

        stepper_tol_factor = linac_utils.stepper_tol_factor(expected_steps)

        steps_moved: int = 0

        if reset_signed_steps:
            self.stepper_tuner.reset_signed_steps()

        self.tune_config_pv_obj.put(linac_utils.TUNE_CONFIG_OTHER_VALUE)

        while abs(delta_hz) > tolerance:
            self.check_abort()
            est_steps = int(0.9 * delta_hz * self.microsteps_per_hz)

            self.set_status_message(
                "Moving stepper",
                logging.DEBUG,
                extra_data={
                    "estimated_steps": est_steps,
                    "delta_hz": delta_hz,
                    "cavity": str(self),
                },
            )

            self.stepper_tuner.move(
                est_steps,
                max_steps=int(abs(est_steps) * 1.1),
                speed=linac_utils.MAX_STEPPER_SPEED,
            )

            steps_moved += abs(est_steps)

            if steps_moved > expected_steps * stepper_tol_factor:
                self.set_status_message(
                    "Motor moved more steps than expected",
                    logging.ERROR,
                    extra_data={
                        "steps_moved": steps_moved,
                        "expected_steps": expected_steps,
                        "tolerance_factor": stepper_tol_factor,
                        "cavity": str(self),
                    },
                )
                raise linac_utils.DetuneError(
                    f"{self} motor moved more steps than expected"
                )

            # this should catch if the chirp range is wrong or if the cavity is off
            self.check_detune()

            delta_hz = delta_hz_func()

    def check_detune(self):
        if self.detune_invalid:
            if self.rf_mode == linac_utils.RF_MODE_CHIRP:
                self.set_status_message(
                    "Detune invalid, adjusting chirp range", logging.WARNING
                )
                self.find_chirp_range(self.chirp_freq_start * 1.1)
            else:
                self.set_status_message(
                    "Cannot tune in SELA with invalid detune",
                    logging.ERROR,
                    extra_data={
                        "rf_mode": self.rf_mode,
                        "cavity": str(self),
                    },
                )
                raise linac_utils.DetuneError(
                    f"Cannot tune {self} in SELA with invalid detune"
                )

    def check_and_set_on_time(self):
        """
        In pulsed mode the cavity has a duty cycle determined by the on time and
        off time. We want the on time to be 70 ms or else the various cavity
        parameters calculated from the waveform (e.g. the RF gradient) won't be
        accurate.
        :return:
        """
        self.set_status_message("Checking RF Pulse On Time", logging.DEBUG)
        if self.pulse_on_time != linac_utils.NOMINAL_PULSED_ONTIME:
            self.set_status_message(
                f"Setting RF Pulse On Time to {linac_utils.NOMINAL_PULSED_ONTIME} ms",
                logging.INFO,
                extra_data={
                    "previous_ontime": self.pulse_on_time,
                    "new_ontime": linac_utils.NOMINAL_PULSED_ONTIME,
                    "cavity": str(self),
                },
            )
            self.pulse_on_time = linac_utils.NOMINAL_PULSED_ONTIME
            self.push_go_button()

    @property
    def pulse_go_pv_obj(self) -> PV:
        if not self._pulse_go_pv_obj:
            self._pulse_go_pv_obj = PV(self._pv_prefix + "PULSE_DIFF_SUM")
        return self._pulse_go_pv_obj

    def push_go_button(self):
        """
        Many of the changes made to a cavity don't actually take effect until the
        go button is pressed
        :return:
        """
        self._pulse_go_pv_obj.put(1, wait=False)
        while self.pulse_status < 2:
            self.check_abort()
            self.set_status_message(
                "Waiting for pulse state to change",
                logging.DEBUG,
                extra_data={
                    "current_pulse_status": self.pulse_status,
                    "cavity": str(self),
                },
            )
            time.sleep(1)
        if self.pulse_status > 2:
            self.set_status_message(
                "Pulse operation failed",
                logging.ERROR,
                extra_data={
                    "pulse_status": self.pulse_status,
                    "cavity": str(self),
                },
            )
            raise linac_utils.PulseError(f"Unable to pulse {self}")

    def turn_on(self):
        self.set_status_message("Turning cavity on", logging.INFO)
        if self.is_online:
            self.ssa.turn_on()
            self.reset_interlocks()
            self.rf_control = 1

            while not self.is_on:
                self.check_abort()
                self.set_status_message(
                    "Waiting for cavity to turn on",
                    logging.DEBUG,
                    extra_data={
                        "rf_state": self.rf_state,
                        "cavity": str(self),
                    },
                )
                time.sleep(1)

            self.set_status_message(
                "Cavity successfully turned on", logging.INFO
            )
        else:
            self.set_status_message(
                "Cannot turn on cavity - not online",
                logging.ERROR,
                extra_data={"hw_mode": self.hw_mode, "cavity": str(self)},
            )
            raise linac_utils.CavityHWModeError(f"{self} not online")

    def turn_off(self):
        self.set_status_message("Turning cavity off", logging.INFO)
        self.rf_control = 0
        while self.is_on:
            self.check_abort()
            self.set_status_message(
                "Waiting for cavity to turn off", logging.DEBUG
            )
            time.sleep(1)
        self.set_status_message("Cavity successfully turned off", logging.INFO)

    def setup_selap(self, des_amp: float = 5):
        self.setup_rf(des_amp)
        self.set_selap_mode()
        self.set_status_message(
            "Cavity set up in SELAP mode",
            logging.INFO,
            extra_data={
                "desired_amplitude": des_amp,
                "cavity": str(self),
            },
        )

    def setup_sela(self, des_amp: float = 5):
        self.setup_rf(des_amp)
        self.set_sela_mode()
        self.set_status_message(
            "Cavity set up in SELA mode",
            logging.INFO,
            extra_data={
                "desired_amplitude": des_amp,
                "cavity": str(self),
            },
        )

    def request_abort(self):
        self.abort_flag = True
        self.set_status_message("Abort requested", logging.WARNING)

    def check_abort(self):
        if self.abort_flag:
            self.abort_flag = False
            self.turn_off()
            self.set_status_message(
                "Operation aborted by user request", logging.ERROR
            )
            raise linac_utils.CavityAbortError(f"Abort requested for {self}")

    def setup_rf(self, des_amp):
        if des_amp > self.ades_max:
            self.set_status_message(
                "Requested amplitude too high - using AMAX instead",
                logging.WARNING,
                extra_data={
                    "requested_amp": des_amp,
                    "ades_max": self.ades_max,
                    "cavity": str(self),
                },
            )
            des_amp = self.ades_max

        self.set_status_message(
            "Setting up RF",
            logging.INFO,
            extra_data={
                "desired_amplitude": des_amp,
                "cavity": str(self),
            },
        )

        self.turn_off()
        self.ssa.calibrate(self.ssa.drive_max)
        self.move_to_resonance()

        self.characterize()
        self.calculate_probe_q()

        self.check_abort()

        self.reset_data_decimation()

        self.check_abort()

        self.ades = min(5, des_amp)
        self.set_sel_mode()
        self.piezo.enable_feedback()
        self.set_sela_mode()

        self.check_abort()

        if des_amp <= 10:
            self.walk_amp(des_amp, 0.5)

        else:
            self.walk_amp(10, 0.5)
            self.walk_amp(des_amp, 0.1)

    def reset_data_decimation(self):
        self.set_status_message("Setting data decimation to 255", logging.INFO)
        self.cw_data_decimation = 255
        self.pulsed_data_decimation = 255

    def setup_tuning(self, chirp_range=50000, use_sela=False):
        self.piezo.enable()

        if not use_sela:
            self.piezo.disable_feedback()

            self.set_status_message(
                "Setting piezo DC voltage offset to 0V", logging.INFO
            )
            self.piezo.dc_setpoint = 0

            self.set_status_message(
                f"Setting drive level to {linac_utils.SAFE_PULSED_DRIVE_LEVEL}",
                logging.INFO,
            )
            self.drive_level = linac_utils.SAFE_PULSED_DRIVE_LEVEL

            self.set_status_message("Setting RF to chirp mode", logging.INFO)
            self.set_chirp_mode()

            self.set_status_message(
                "Turning RF on and waiting 5s for detune to stabilize",
                logging.INFO,
            )
            self.turn_on()
            time.sleep(5)
            self.find_chirp_range(chirp_range)

        else:
            self.piezo.enable_feedback()
            self.set_sela_mode()
            self.turn_on()

    def find_chirp_range(self, chirp_range=50000):
        self.check_abort()
        self.set_chirp_range(chirp_range)
        time.sleep(1)
        if self.detune_invalid:
            if chirp_range < 400000:
                self.set_status_message(
                    "Detune invalid, increasing chirp range",
                    logging.DEBUG,
                    extra_data={
                        "current_range": chirp_range,
                        "new_range": int(chirp_range * 1.1),
                        "cavity": str(self),
                    },
                )
                self.find_chirp_range(int(chirp_range * 1.1))
            else:
                self.set_status_message(
                    "No valid detune found within +/-400000Hz chirp range",
                    logging.ERROR,
                    extra_data={
                        "final_chirp_range": chirp_range,
                        "cavity": str(self),
                    },
                )
                raise linac_utils.DetuneError(
                    f"{self}: No valid detune found within"
                    f"+/-400000Hz chirp range"
                )

    def reset_interlocks(self, wait: int = 3, attempt: int = 0):
        # TODO see if it makes more sense to implement this non-recursively
        self.set_status_message(
            f"Resetting interlocks (attempt {attempt + 1}, wait {wait}s)",
            logging.INFO,
            extra_data={
                "attempt": attempt + 1,
                "wait_time": wait,
                "cavity": str(self),
            },
        )

        if not self._interlock_reset_pv_obj:
            self._interlock_reset_pv_obj = PV(self.interlock_reset_pv)

        self._interlock_reset_pv_obj.put(1, wait=False)
        time.sleep(wait)

        self.set_status_message("Checking RF permit status", logging.DEBUG)
        if self.rf_inhibited:
            if attempt >= linac_utils.INTERLOCK_RESET_ATTEMPTS:
                self.set_status_message(
                    f"Cavity still faulted after {linac_utils.INTERLOCK_RESET_ATTEMPTS} reset attempts",
                    logging.ERROR,
                    extra_data={
                        "total_attempts": linac_utils.INTERLOCK_RESET_ATTEMPTS,
                        "cavity": str(self),
                    },
                )
                raise linac_utils.CavityFaultError(
                    f"{self} still faulted after"
                    f" {linac_utils.INTERLOCK_RESET_ATTEMPTS} "
                    f"reset attempts"
                )
            else:
                self.set_status_message(
                    f"Reset attempt {attempt + 1} unsuccessful, retrying",
                    logging.WARNING,
                )
                self.reset_interlocks(wait=wait + 2, attempt=attempt + 1)
        else:
            self.set_status_message(
                "Interlocks successfully reset", logging.INFO
            )

    @property
    def characterization_timestamp(self) -> datetime:
        if not self._char_timestamp_pv_obj:
            self._char_timestamp_pv_obj = PV(self.char_timestamp_pv)
        date_string = self._char_timestamp_pv_obj.get()
        time_readback = datetime.strptime(date_string, "%Y-%m-%d-%H:%M:%S")
        return time_readback

    def characterize(self):
        """
        Calibrates the cavity's RF probe so that the amplitude readback will be
        accurate. Also measures the loaded Q (quality factor) of the cavity power
        coupler
        :return:
        """

        self.reset_interlocks()

        self.set_status_message(
            f"Setting drive level to {linac_utils.SAFE_PULSED_DRIVE_LEVEL}",
            logging.INFO,
        )
        self.drive_level = linac_utils.SAFE_PULSED_DRIVE_LEVEL

        if (
            datetime.now() - self.characterization_timestamp
        ).total_seconds() < 60:
            if self.characterization_status == 1:
                self.set_status_message(
                    "Recent successful characterization found, skipping",
                    logging.INFO,
                    extra_data={
                        "timestamp": self.characterization_timestamp.isoformat(),
                        "cavity": str(self),
                    },
                )
                self.finish_characterization()
                return

        self.set_status_message(
            "Starting cavity characterization", logging.INFO
        )
        self.start_characterization()
        time.sleep(2)

        while self.characterization_running:
            self.check_abort()
            self.set_status_message(
                "Waiting for characterization to complete",
                logging.DEBUG,
                extra_data={
                    "characterization_status": self.characterization_status,
                    "cavity": str(self),
                },
            )
            time.sleep(1)

        if (
            self.characterization_status
            == linac_utils.CALIBRATION_COMPLETE_VALUE
        ):
            seconds_since_char = (
                datetime.now() - self.characterization_timestamp
            ).total_seconds()

            if seconds_since_char > 300:
                self.set_status_message(
                    "No valid characterization within the last 5 minutes",
                    logging.ERROR,
                    extra_data={
                        "seconds_since_characterization": seconds_since_char,
                        "timestamp": self.characterization_timestamp.isoformat(),
                        "cavity": str(self),
                    },
                )
                raise linac_utils.CavityCharacterizationError(
                    f"No valid {self} characterization within the last 5 min"
                )
            self.finish_characterization()

        if self.characterization_crashed:
            self.set_status_message(
                "Characterization crashed",
                logging.ERROR,
                extra_data={
                    "characterization_status": self.characterization_status,
                    "cavity": str(self),
                },
            )
            raise linac_utils.CavityCharacterizationError(
                f"{self} characterization crashed"
            )

    def finish_characterization(self):
        self.set_status_message(
            "Pushing characterization results", logging.INFO
        )

        if self.measured_loaded_q_in_tolerance:
            self.set_status_message(
                "Loaded Q in tolerance",
                logging.DEBUG,
                extra_data={
                    "measured_q": self.measured_loaded_q,
                    "lower_limit": self.loaded_q_lower_limit,
                    "upper_limit": self.loaded_q_upper_limit,
                    "cavity": str(self),
                },
            )
            self.push_loaded_q()
        else:
            self.set_status_message(
                "Loaded Q out of tolerance",
                logging.ERROR,
                extra_data={
                    "measured_q": self.measured_loaded_q,
                    "lower_limit": self.loaded_q_lower_limit,
                    "upper_limit": self.loaded_q_upper_limit,
                    "cavity": str(self),
                },
            )
            raise linac_utils.CavityQLoadedCalibrationError(
                f"{self} loaded Q out of tolerance"
            )

        if self.measured_scale_factor_in_tolerance:
            self.set_status_message(
                "Scale factor in tolerance",
                logging.DEBUG,
                extra_data={
                    "measured_scale_factor": self.measured_scale_factor,
                    "lower_limit": self.scale_factor_lower_limit,
                    "upper_limit": self.scale_factor_upper_limit,
                    "cavity": str(self),
                },
            )
            self.push_scale_factor()
        else:
            self.set_status_message(
                "Scale factor out of tolerance",
                logging.ERROR,
                extra_data={
                    "measured_scale_factor": self.measured_scale_factor,
                    "lower_limit": self.scale_factor_lower_limit,
                    "upper_limit": self.scale_factor_upper_limit,
                    "cavity": str(self),
                },
            )
            raise linac_utils.CavityScaleFactorCalibrationError(
                f"{self} scale factor out of tolerance"
            )

        self.reset_data_decimation()

        self.set_status_message(
            "Restoring piezo feedback setpoint to 0", logging.INFO
        )
        self.piezo.feedback_setpoint = 0

        self.set_status_message(
            "Characterization completed successfully", logging.INFO
        )

    def walk_amp(self, des_amp, step_size):
        self.set_status_message(
            f"Walking amplitude to {des_amp:.2f} MV from {self.ades:.2f} MV (step size: {step_size:.2f})",
            logging.INFO,
            extra_data={
                "target_amplitude": des_amp,
                "current_amplitude": self.ades,
                "step_size": step_size,
                "cavity": str(self),
            },
        )

        while self.ades <= (des_amp - step_size):
            self.check_abort()
            if self.is_quenched:
                self.set_status_message(
                    "Quench detected during RF ramp",
                    logging.ERROR,
                    extra_data={
                        "current_amplitude": self.ades,
                        "target_amplitude": des_amp,
                        "cavity": str(self),
                    },
                )
                raise linac_utils.QuenchError(
                    f"{self} quench detected, aborting RF ramp"
                )
            self.ades = self.ades + step_size
            # to avoid tripping sensitive interlock
            time.sleep(0.1)

        if self.ades != des_amp:
            self.ades = des_amp

        self.set_status_message(
            f"Amplitude walk complete - at {des_amp:.2f} MV",
            logging.INFO,
            extra_data={"final_amplitude": des_amp, "cavity": str(self)},
        )
