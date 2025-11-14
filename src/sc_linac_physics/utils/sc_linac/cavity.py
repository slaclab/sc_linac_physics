import logging
import time
from datetime import datetime
from typing import Optional, Callable, TYPE_CHECKING

from sc_linac_physics.utils.epics import (
    PV,
    EPICS_INVALID_VAL,
    PVInvalidError,
)
from sc_linac_physics.utils.sc_linac import linac_utils
from sc_linac_physics.utils.sc_linac.linac_utils import STATUS_RUNNING_VALUE

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
    setting amplitude, characterizing, and tuning to resonance.
    """

    def __init__(self, cavity_num: int, rack_object: "Rack"):
        """
        Initialize a Cavity instance.

        Args:
            cavity_num: Cavity number (1-8)
            rack_object: The rack object the cavity belongs to
        """
        self.number: int = cavity_num
        self.rack: Rack = rack_object
        self.cryomodule: "Cryomodule" = self.rack.cryomodule
        self.linac: "Linac" = self.cryomodule.linac

        # Initialize logger
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        # Add console handler if no handlers exist
        if not self.logger.handlers:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)  # Adjust level as needed
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
            self.logger.setLevel(logging.INFO)  # Adjust level as needed

        # Set cavity parameters based on type
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

        # Set PV prefixes
        self._pv_prefix = (
            f"ACCL:{self.linac.name}:{self.cryomodule.name}{self.number}0:"
        )
        self.ctePrefix = f"CTE:CM{self.cryomodule.name}:1{self.number}"
        self.chirp_prefix = self._pv_prefix + "CHIRP:"

        self.abort_flag: bool = False

        # Initialize all PV addresses and objects
        self._init_pv_addresses()
        self._init_pv_objects()

        # Initialize sub-components (must be after base properties)
        self.ssa: "SSA" = self.rack.ssa_class(cavity=self)
        self.stepper_tuner: "StepperTuner" = self.rack.stepper_class(
            cavity=self
        )
        self.piezo: "Piezo" = self.rack.piezo_class(cavity=self)

    def _init_pv_addresses(self):
        """Initialize all PV address strings."""
        # Characterization PVs
        self.calc_probe_q_pv: str = self.pv_addr("QPROBE_CALC1.PROC")
        self.characterization_start_pv: str = self.pv_addr("PROBECALSTRT")
        self.characterization_status_pv: str = self.pv_addr("PROBECALSTS")
        self.char_timestamp_pv: str = self.pv_addr("PROBECALTS")

        # SSA PVs
        self.push_ssa_slope_pv: str = self.pv_addr("PUSH_SSA_SLOPE.PROC")
        self.save_ssa_slope_pv: str = self.pv_addr("SAVE_SSA_SLOPE.PROC")

        # Interlock PVs
        self.interlock_reset_pv: str = self.pv_addr("INTLK_RESET_ALL")

        # Loaded Q PVs
        self.current_q_loaded_pv: str = self.pv_addr("QLOADED")
        self.measured_loaded_q_pv: str = self.pv_addr("QLOADED_NEW")
        self.push_loaded_q_pv: str = self.pv_addr("PUSH_QLOADED.PROC")
        self.save_q_loaded_pv: str = self.pv_addr("SAVE_QLOADED.PROC")

        # Scale factor PVs
        self.current_cavity_scale_pv: str = self.pv_addr("CAV:SCALER_SEL.B")
        self.measured_scale_factor_pv: str = self.pv_addr("CAV:CAL_SCALEB_NEW")
        self.push_scale_factor_pv: str = self.pv_addr("PUSH_CAV_SCALE.PROC")
        self.save_cavity_scale_pv: str = self.pv_addr("SAVE_CAV_SCALE.PROC")

        # Amplitude PVs
        self.ades_pv: str = self.pv_addr("ADES")
        self.acon_pv: str = self.pv_addr("ACON")
        self.aact_pv: str = self.pv_addr("AACTMEAN")
        self.ades_max_pv: str = self.pv_addr("ADES_MAX")

        # RF mode and control PVs
        self.rf_mode_ctrl_pv: str = self.pv_addr("RFMODECTRL")
        self.rf_mode_pv: str = self.pv_addr("RFMODE")
        self.rf_state_pv: str = self.pv_addr("RFSTATE")
        self.rf_control_pv: str = self.pv_addr("RFCTRL")

        # Drive level PV
        self.drive_level_pv: str = self.pv_addr("SEL_ASET")

        # Pulse PVs
        self.pulse_go_pv: str = self.pv_addr("PULSE_DIFF_SUM")
        self.pulse_status_pv: str = self.pv_addr("PULSE_STATUS")
        self.pulse_on_time_pv: str = self.pv_addr("PULSE_ONTIME")

        # Waveform PVs
        self.rev_waveform_pv: str = self.pv_addr("REV:AWF")
        self.fwd_waveform_pv: str = self.pv_addr("FWD:AWF")
        self.cav_waveform_pv: str = self.pv_addr("CAV:AWF")

        # Temperature PV
        self.stepper_temp_pv: str = self.pv_addr("STEPTEMP")

        # Detune PVs
        self.detune_best_pv: str = self.pv_addr("DFBEST")
        self.detune_chirp_pv: str = self.pv_addr("CHIRP:DF")

        # Permit and quench PVs
        self.rf_permit_pv: str = self.pv_addr("RFPERMIT")
        self.quench_latch_pv: str = self.pv_addr("QUENCH_LTCH")
        self.quench_bypass_pv: str = self.pv_addr("QUENCH_BYP")

        # Data decimation PVs
        self.cw_data_decimation_pv: str = self.pv_addr("ACQ_DECIM_SEL.A")
        self.pulsed_data_decimation_pv: str = self.pv_addr("ACQ_DECIM_SEL.C")

        # Tune configuration PV
        self.tune_config_pv: str = self.pv_addr("TUNE_CONFIG")

        # Chirp frequency PVs
        self.chirp_freq_start_pv: str = self.chirp_prefix + "FREQ_START"
        self.chirp_freq_stop_pv: str = self.chirp_prefix + "FREQ_STOP"

        # Hardware mode PV
        self.hw_mode_pv: str = self.pv_addr("HWMODE")

        # Status and progress PVs
        self.progress_pv: str = self.auto_pv_addr("PROG")
        self.status_pv: str = self.auto_pv_addr("STATUS")
        self.status_msg_pv: str = self.auto_pv_addr("MSG")
        self.note_pv: str = self.auto_pv_addr("NOTE")

    def _init_pv_objects(self):
        """Initialize all PV object attributes to None."""
        # Characterization PV objects
        self._calc_probe_q_pv_obj: Optional[PV] = None
        self._characterization_start_pv_obj: Optional[PV] = None
        self._characterization_status_pv_obj: Optional[PV] = None
        self._char_timestamp_pv_obj: Optional[PV] = None

        # SSA PV objects
        self._push_ssa_slope_pv_obj: Optional[PV] = None
        self._save_ssa_slope_pv_obj: Optional[PV] = None

        # Interlock PV objects
        self._interlock_reset_pv_obj: Optional[PV] = None

        # Loaded Q PV objects
        self._measured_loaded_q_pv_obj: Optional[PV] = None
        self._push_loaded_q_pv_obj: Optional[PV] = None

        # Scale factor PV objects
        self._measured_scale_factor_pv_obj: Optional[PV] = None
        self._push_scale_factor_pv_obj: Optional[PV] = None

        # Amplitude PV objects
        self._ades_pv_obj: Optional[PV] = None
        self._acon_pv_obj: Optional[PV] = None
        self._aact_pv_obj: Optional[PV] = None
        self._ades_max_pv_obj: Optional[PV] = None

        # RF mode and control PV objects
        self._rf_mode_ctrl_pv_obj: Optional[PV] = None
        self._rf_mode_pv_obj: Optional[PV] = None
        self._rf_state_pv_obj: Optional[PV] = None
        self._rf_control_pv_obj: Optional[PV] = None

        # Drive level PV object
        self._drive_level_pv_obj: Optional[PV] = None

        # Pulse PV objects
        self._pulse_go_pv_obj: Optional[PV] = None
        self._pulse_status_pv_obj: Optional[PV] = None
        self._pulse_on_time_pv_obj: Optional[PV] = None

        # Detune PV objects
        self._detune_best_pv_obj: Optional[PV] = None
        self._detune_chirp_pv_obj: Optional[PV] = None

        # Permit and quench PV objects
        self._rf_permit_pv_obj: Optional[PV] = None
        self._quench_latch_pv_obj: Optional[PV] = None

        # Data decimation PV objects
        self._cw_data_decim_pv_obj: Optional[PV] = None
        self._pulsed_data_decim_pv_obj: Optional[PV] = None

        # Tune configuration PV object
        self._tune_config_pv_obj: Optional[PV] = None

        # Chirp frequency PV objects
        self._chirp_freq_start_pv_obj: Optional[PV] = None
        self._chirp_freq_stop_pv_obj: Optional[PV] = None

        # Hardware mode PV object
        self._hw_mode_pv_obj: Optional[PV] = None

        # Status and progress PV objects
        self._progress_pv_obj: Optional[PV] = None
        self._status_pv_obj: Optional[PV] = None
        self._status_msg_pv_obj: Optional[PV] = None
        self._note_pv_obj: Optional[PV] = None

    def __str__(self):
        return (
            f"{self.linac.name} CM{self.cryomodule.name} Cavity {self.number}"
        )

    @property
    def pv_prefix(self):
        return self._pv_prefix

    @property
    def microsteps_per_hz(self):
        return 1 / self.stepper_tuner.hz_per_microstep

    # Status and progress properties
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
    def status_message(self, message):
        self.set_status_message(message, level=logging.INFO)

    def set_status_message(self, message, level=logging.INFO):
        self.logger.log(level, message)
        self.status_msg_pv_obj.put(message)

    # Characterization methods and properties
    def start_characterization(self):
        if not self._characterization_start_pv_obj:
            self._characterization_start_pv_obj = PV(
                self.characterization_start_pv
            )
        self._characterization_start_pv_obj.put(1)

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
    def characterization_timestamp(self) -> datetime:
        if not self._char_timestamp_pv_obj:
            self._char_timestamp_pv_obj = PV(self.char_timestamp_pv)
        date_string = self._char_timestamp_pv_obj.get()
        return datetime.strptime(date_string, "%Y-%m-%d-%H:%M:%S")

    # Data decimation properties
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

    # RF control and mode properties
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

    # Drive level properties
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

    # SSA slope methods
    def push_ssa_slope(self):
        if not self._push_ssa_slope_pv_obj:
            self._push_ssa_slope_pv_obj = PV(self.push_ssa_slope_pv)
        self._push_ssa_slope_pv_obj.put(1)

    def save_ssa_slope(self):
        if not self._save_ssa_slope_pv_obj:
            self._save_ssa_slope_pv_obj = PV(self.save_ssa_slope_pv)
        self._save_ssa_slope_pv_obj.put(1)

    # Loaded Q properties and methods
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
        self._push_loaded_q_pv_obj.put(1)

    # Scale factor properties and methods
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
        self._push_scale_factor_pv_obj.put(1)

    # Pulse properties
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
    def pulse_go_pv_obj(self) -> PV:
        if not self._pulse_go_pv_obj:
            self._pulse_go_pv_obj = PV(self.pulse_go_pv)
        return self._pulse_go_pv_obj

    # RF permit and state properties
    @property
    def rf_permit(self):
        if not self._rf_permit_pv_obj:
            self._rf_permit_pv_obj = PV(self.rf_permit_pv)
        return self._rf_permit_pv_obj.get()

    @property
    def rf_inhibited(self) -> bool:
        return self.rf_permit == 0

    @property
    def rf_state_pv_obj(self) -> PV:
        if not self._rf_state_pv_obj:
            self._rf_state_pv_obj = PV(self.rf_state_pv)
        return self._rf_state_pv_obj

    @property
    def rf_state(self):
        """This property is read only."""
        return self.rf_state_pv_obj.get()

    @property
    def is_on(self) -> bool:
        return self.rf_state == 1

    @property
    def turned_off(self) -> bool:
        return self.rf_control == 0

    # Amplitude properties
    @property
    def ades(self):
        if not self._ades_pv_obj:
            self._ades_pv_obj = PV(self.ades_pv)
        return self._ades_pv_obj.get()

    @ades.setter
    def ades(self, value: float):
        if not self._ades_pv_obj:
            self._ades_pv_obj = PV(self.ades_pv)
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

    # EDM macro strings
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
        cm = self.cryomodule.pv_prefix[:-3]  # Remove trailing colon and zeroes
        macro_id = self.cryomodule.name
        ch = 2 if self.number in [2, 4] else 1
        return f"C={self.number},RFS={rfs},R={r},CM={cm},ID={macro_id},CH={ch}"

    @property
    def cryo_edm_macro_string(self):
        return f"CM={self.cryomodule.name},AREA={self.cryomodule.linac.name}"

    # Hardware mode properties
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

    # Tune configuration properties
    @property
    def tune_config_pv_obj(self) -> PV:
        if not self._tune_config_pv_obj:
            self._tune_config_pv_obj = PV(self.tune_config_pv)
        return self._tune_config_pv_obj

    # Chirp frequency properties
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
        self.calc_probe_q_pv_obj.put(1)

    # Detune properties
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

    # Piezo methods
    def delta_piezo(self):
        """Calculate the detuning contribution from piezo offset."""
        delta_volts = self.piezo.voltage - linac_utils.PIEZO_CENTER_VOLTAGE
        delta_hz = delta_volts * self.piezo.hz_per_v
        self.logger.debug(f"{self} piezo detune: {delta_hz}")
        return -delta_hz if self.cryomodule.is_harmonic_linearizer else delta_hz

    # Abort functionality
    def request_abort(self):
        self.abort_flag = True

    def check_abort(self):
        if self.abort_flag:
            self.abort_flag = False
            self.turn_off()
            raise linac_utils.CavityAbortError(f"Abort requested for {self}")

    # Tuning methods
    def set_chirp_range(self, offset: int):
        """Set the chirp frequency range."""
        offset = abs(offset)
        self.logger.info(f"Setting chirp range for {self} to +/- {offset} Hz")
        self.chirp_freq_start = -offset
        self.chirp_freq_stop = offset
        self.logger.info(f"Chirp range set for {self}")

    def find_chirp_range(self, chirp_range=50000):
        """Find a valid chirp range that gives a good detune reading."""
        self.check_abort()
        self.set_chirp_range(chirp_range)
        time.sleep(1)
        if self.detune_invalid:
            if chirp_range < 400000:
                self.find_chirp_range(int(chirp_range * 1.1))
            else:
                raise linac_utils.DetuneError(
                    f"{self}: No valid detune found within +/-400000Hz chirp range"
                )

    def check_detune(self):
        """Check if detune is valid, and adjust chirp range if needed."""
        if self.detune_invalid:
            if self.rf_mode == linac_utils.RF_MODE_CHIRP:
                self.find_chirp_range(self.chirp_freq_start * 1.1)
            else:
                raise linac_utils.DetuneError(
                    f"Cannot tune {self} in SELA with invalid detune"
                )

    def setup_tuning(self, chirp_range=50000, use_sela=False):
        """Set up cavity for tuning in either chirp or SELA mode."""
        self.piezo.enable()

        if not use_sela:
            self.piezo.disable_feedback()
            self.logger.info(f"Setting {self} piezo DC voltage offset to 0V")
            self.piezo.dc_setpoint = 0
            self.logger.info(
                f"Setting {self} drive level to {linac_utils.SAFE_PULSED_DRIVE_LEVEL}"
            )
            self.drive_level = linac_utils.SAFE_PULSED_DRIVE_LEVEL
            self.logger.info(f"Setting {self} RF to chirp")
            self.set_chirp_mode()
            self.logger.info(
                f"Turning {self} RF on and waiting 5s for detune to catch up"
            )
            self.turn_on()
            time.sleep(5)
            self.find_chirp_range(chirp_range)
        else:
            self.piezo.enable_feedback()
            self.set_sela_mode()
            self.turn_on()

    def _auto_tune(
        self,
        delta_hz_func: Callable,
        tolerance: int = 50,
        reset_signed_steps: bool = False,
    ):
        """
        Auto-tune the cavity by moving the stepper motor.

        Args:
            delta_hz_func: Function that returns the frequency offset in Hz
            tolerance: Acceptable frequency tolerance in Hz
            reset_signed_steps: Whether to reset the stepper's signed step count
        """
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

            self.logger.info(f"Moving stepper for {self} {est_steps} steps")
            self.stepper_tuner.move(
                est_steps,
                max_steps=int(abs(est_steps) * 1.1),
                speed=linac_utils.MAX_STEPPER_SPEED,
            )

            steps_moved += abs(est_steps)

            if steps_moved > expected_steps * stepper_tol_factor:
                raise linac_utils.DetuneError(
                    f"{self} motor moved more steps than expected"
                )

            self.check_detune()
            delta_hz = delta_hz_func()

    def move_to_resonance(self, reset_signed_steps=False, use_sela=False):
        """
        Move the cavity to resonance.

        Args:
            reset_signed_steps: Whether to reset the stepper's signed step count
            use_sela: Whether to use SELA mode (True) or chirp mode (False)
        """

        def delta_detune():
            return self.detune

        self.setup_tuning(use_sela=use_sela)
        self.logger.info(
            f"Tuning {self} to resonance in "
            + ("SELA" if use_sela else "chirp")
        )
        self._auto_tune(
            delta_hz_func=delta_detune,
            tolerance=(500 if self.cryomodule.is_harmonic_linearizer else 50),
            reset_signed_steps=reset_signed_steps,
        )

        if use_sela:
            self.logger.info(f"Centering {self} piezo")
            self._auto_tune(
                delta_hz_func=self.delta_piezo,
                tolerance=5 * self.piezo.hz_per_v,
                reset_signed_steps=False,
            )

        self.tune_config_pv_obj.put(linac_utils.TUNE_CONFIG_RESONANCE_VALUE)

    # RF control methods
    def turn_on(self):
        """Turn the cavity RF on."""
        self.logger.info(f"Turning {self} on")
        if self.is_online:
            self.ssa.turn_on()
            self.reset_interlocks()
            self.rf_control = 1

            while not self.is_on:
                self.check_abort()
                self.logger.debug(
                    f"Waiting for {self} to turn on at {datetime.now()}"
                )
                time.sleep(1)

            self.logger.info(f"{self} on")
        else:
            raise linac_utils.CavityHWModeError(f"{self} not online")

    def turn_off(self):
        """Turn the cavity RF off."""
        self.logger.info(f"Turning {self} off")
        self.rf_control = 0
        while self.is_on:
            self.check_abort()
            self.logger.debug(f"Waiting for {self} to turn off")
            time.sleep(1)
        self.logger.info(f"{self} off")

    def reset_interlocks(self, wait: int = 3, attempt: int = 0):
        """
        Reset cavity interlocks.

        Args:
            wait: Time to wait after reset in seconds
            attempt: Current attempt number (used for recursion)
        """
        self.logger.info(f"Resetting interlocks for {self} and waiting {wait}s")

        if not self._interlock_reset_pv_obj:
            self._interlock_reset_pv_obj = PV(self.interlock_reset_pv)

        self._interlock_reset_pv_obj.put(1)
        time.sleep(wait)

        self.logger.info(f"Checking {self} RF permit")
        if self.rf_inhibited:
            if attempt >= linac_utils.INTERLOCK_RESET_ATTEMPTS:
                raise linac_utils.CavityFaultError(
                    f"{self} still faulted after "
                    f"{linac_utils.INTERLOCK_RESET_ATTEMPTS} reset attempts"
                )
            else:
                self.logger.warning(
                    f"{self} reset {attempt} unsuccessful; retrying"
                )
                self.reset_interlocks(wait=wait + 2, attempt=attempt + 1)
        else:
            self.logger.info(f"{self} interlocks reset")

    # Pulse methods
    def check_and_set_on_time(self):
        """
        Check and set the RF pulse on time.

        In pulsed mode, the cavity has a duty cycle determined by on/off time.
        The on time should be 70 ms for accurate waveform-based calculations.
        """
        self.logger.info("Checking RF Pulse On Time...")
        if self.pulse_on_time != linac_utils.NOMINAL_PULSED_ONTIME:
            self.logger.info(
                f"Setting RF Pulse On Time to {linac_utils.NOMINAL_PULSED_ONTIME} ms"
            )
            self.pulse_on_time = linac_utils.NOMINAL_PULSED_ONTIME
            self.push_go_button()

    def push_go_button(self):
        """
        Push the go button to apply pending changes.

        Many cavity changes don't take effect until this is called.
        """
        self.pulse_go_pv_obj.put(1)
        while self.pulse_status < 2:
            self.check_abort()
            self.logger.debug(f"Waiting for pulse state at {datetime.now()}")
            time.sleep(1)
        if self.pulse_status > 2:
            raise linac_utils.PulseError(f"Unable to pulse {self}")

    # Setup methods
    def setup_selap(self, des_amp: float = 5):
        """Set up cavity in SELAP mode."""
        self.setup_rf(des_amp)
        self.set_selap_mode()
        self.logger.info(f"{self} set up in SELAP")

    def setup_sela(self, des_amp: float = 5):
        """Set up cavity in SELA mode."""
        self.setup_rf(des_amp)
        self.set_sela_mode()
        self.logger.info(f"{self} set up in SELA")

    def setup_rf(self, des_amp):
        """
        Set up cavity RF to a desired amplitude.

        Args:
            des_amp: Desired amplitude in MV
        """
        if des_amp > self.ades_max:
            self.logger.warning(
                f"Requested amplitude for {self} too high - ramping up to AMAX instead"
            )
            des_amp = self.ades_max

        self.logger.info(f"Setting up {self}")
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
        """Reset data decimation to default values."""
        self.logger.info(f"Setting data decimation for {self}")
        self.cw_data_decimation = 255
        self.pulsed_data_decimation = 255

    # Characterization methods
    def characterize(self):
        """
        Calibrate the cavity's RF probe and measure loaded Q.

        This ensures amplitude readback accuracy and measures the quality
        factor of the cavity power coupler.
        """
        self.reset_interlocks()
        self.logger.info(
            f"Setting {self} drive to {linac_utils.SAFE_PULSED_DRIVE_LEVEL}"
        )
        self.drive_level = linac_utils.SAFE_PULSED_DRIVE_LEVEL

        # Check if recent successful characterization exists
        if (
            datetime.now() - self.characterization_timestamp
        ).total_seconds() < 60:
            if self.characterization_status == 1:
                self.logger.info(
                    f"{self} successful characterization within the last minute, "
                    f"not starting a new one"
                )
                self.finish_characterization()
                return

        self.logger.info(
            f"Starting {self} cavity characterization at {datetime.now()}"
        )
        self.start_characterization()
        time.sleep(2)

        while self.characterization_running:
            self.check_abort()
            self.logger.debug(
                f"Waiting for {self} characterization to stop running at {datetime.now()}"
            )
            time.sleep(1)

        if (
            self.characterization_status
            == linac_utils.CALIBRATION_COMPLETE_VALUE
        ):
            if (
                datetime.now() - self.characterization_timestamp
            ).total_seconds() > 300:
                raise linac_utils.CavityCharacterizationError(
                    f"No valid {self} characterization within the last 5 min"
                )
            self.finish_characterization()

        if self.characterization_crashed:
            raise linac_utils.CavityCharacterizationError(
                f"{self} characterization crashed"
            )

    def finish_characterization(self):
        """Complete the characterization by pushing results and resetting settings."""
        self.logger.info(f"Pushing {self} characterization results")

        if self.measured_loaded_q_in_tolerance:
            self.push_loaded_q()
        else:
            raise linac_utils.CavityQLoadedCalibrationError(
                f"{self} loaded Q out of tolerance"
            )

        if self.measured_scale_factor_in_tolerance:
            self.push_scale_factor()
        else:
            raise linac_utils.CavityScaleFactorCalibrationError(
                f"{self} scale factor out of tolerance"
            )

        self.reset_data_decimation()
        self.logger.info(f"Restoring {self} piezo feedback setpoint to 0")
        self.piezo.feedback_setpoint = 0
        self.logger.info(f"{self} characterization successful")

    def walk_amp(self, des_amp, step_size):
        """
        Gradually increase cavity amplitude to desired value.

        Args:
            des_amp: Desired amplitude in MV
            step_size: Step size for amplitude increases in MV
        """
        self.logger.info(f"Walking {self} to {des_amp} from {self.ades}")

        while self.ades <= (des_amp - step_size):
            self.check_abort()
            if self.is_quenched:
                raise linac_utils.QuenchError(
                    f"{self} quench detected, aborting RF ramp"
                )
            self.ades = self.ades + step_size
            time.sleep(0.1)  # Avoid tripping sensitive interlocks

        if self.ades != des_amp:
            self.ades = des_amp

        self.logger.info(f"{self} at {des_amp} MV")
