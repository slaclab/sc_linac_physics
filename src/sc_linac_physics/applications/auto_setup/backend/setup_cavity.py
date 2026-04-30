import logging
from time import sleep

from epics.ca import CASeverityException

from sc_linac_physics.applications.auto_setup.backend.setup_utils import (
    SetupLinacObject,
    SETUP_LOG_DIR,
)
from sc_linac_physics.utils.logger import custom_logger
from sc_linac_physics.utils.sc_linac.cavity import Cavity, linac_utils
from sc_linac_physics.utils.sc_linac.linac_utils import (
    RF_MODE_SELA,
    STATUS_READY_VALUE,
    STATUS_RUNNING_VALUE,
    STATUS_ERROR_VALUE,
)


class SetupCavity(Cavity, SetupLinacObject):
    """RF cavity with automated setup logic.

    Inherits hardware control from Cavity and setup request flags from
    SetupLinacObject. The main entry point is setup(), which sequences
    SSA calibration → auto-tune → cavity characterization → RF ramp based
    on which request flags are set.
    """

    def __init__(
        self,
        cavity_num,
        rack_object,
    ):
        Cavity.__init__(self, cavity_num=cavity_num, rack_object=rack_object)
        SetupLinacObject.__init__(self)

    def _init_logger(self):
        """Initialize a setup-specific logger."""

        self.logger = custom_logger(
            __name__,
            log_dir=str(SETUP_LOG_DIR / self.cryomodule.name),
            log_filename=f"setup_cavity_{self.number}",
        )

    def capture_acon(self):
        """Copy the current ADES value into ACON, locking in the operating amplitude."""
        self.acon = self.ades

    def clear_abort(self):
        """Clear the abort PV so a subsequent setup() call is not immediately aborted."""
        self.abort_pv_obj.put(0)

    def trigger_abort(self):
        """Request a safe mid-sequence abort if a script is running; no-op otherwise."""
        if self.script_is_running:
            self.set_status_message(
                f"Requesting safe abort for {self}", logging.WARNING
            )
            self.abort_pv_obj.put(1)
        else:
            self.set_status_message(
                f"{self} script not running, no abort needed", logging.INFO
            )

    def check_abort(self):
        """Raise CavityAbortError if the abort PV is set; clear the PV first so it doesn't re-trigger."""
        if self.abort_requested:
            self.clear_abort()
            err_msg = f"Abort requested for {self}"
            self.set_status_message(err_msg, logging.ERROR)
            raise linac_utils.CavityAbortError(err_msg)

    def shut_down(self):
        """Turn RF and SSA off. Simpler than setup(); no abort polling needed."""
        if self.script_is_running:
            self.set_status_message(
                f"{self} script already running", logging.WARNING
            )
            return

        self.clear_abort()

        try:
            self.status = STATUS_RUNNING_VALUE
            self.progress = 0
            self.set_status_message(f"Turning {self} RF off", logging.INFO)
            self.turn_off()
            self.progress = 50
            self.set_status_message(f"Turning {self} SSA off", logging.INFO)
            self.ssa.turn_off()
            self.progress = 100
            self.status = STATUS_READY_VALUE
            self.set_status_message(f"{self} RF and SSA off", logging.INFO)
        except (CASeverityException, linac_utils.CavityAbortError) as e:
            self.status = STATUS_ERROR_VALUE
            self.clear_abort()
            self.set_status_message(str(e), logging.ERROR)

    def setup(self):
        """Run the full cavity setup sequence based on active request flags.

        Steps (each gated by its request flag):
          1. SSA calibration   (ssa_cal_requested)
          2. Auto-tune         (auto_tune_requested)
          3. Characterization  (cav_char_requested)
          4. RF ramp to ACON   (rf_ramp_requested)

        Always turns RF off first regardless of which steps are requested, to
        clear any latched interlocks. Skips silently if already running or
        offline. Sets status to ERROR on any unhandled exception.
        """
        try:
            if self.script_is_running:
                self.set_status_message(
                    f"{self} script already running", logging.WARNING
                )
                return

            if not self.is_online:
                self.set_status_message(
                    f"{self} not online, not setting up", logging.ERROR
                )
                self.status = STATUS_ERROR_VALUE
                return

            self.clear_abort()

            self.status = STATUS_RUNNING_VALUE
            self.progress = 0

            # Not turning it off can cause problems if an interlock is tripped
            # but the requested RF state is on
            self.set_status_message(
                f"Turning {self} off before starting setup", logging.INFO
            )
            self.turn_off()
            self.progress = 5

            self.set_status_message(
                f"Turning on {self} SSA if not on already", logging.INFO
            )
            self.ssa.turn_on()
            self.progress = 10

            self.set_status_message(
                f"Resetting {self} interlocks", logging.INFO
            )
            self.reset_interlocks()
            self.progress = 15

            self.request_ssa_cal()
            self.request_auto_tune()
            self.request_characterization()
            self.request_ramp()

            self.progress = 100
            self.status = STATUS_READY_VALUE
        except Exception as e:
            self.status = STATUS_ERROR_VALUE
            self.clear_abort()
            self.set_status_message(str(e), logging.ERROR)

    def request_ramp(self):
        """Ramp RF amplitude to ACON if rf_ramp_requested.

        Enables piezo feedback, turns RF on in SELA mode, walks amplitude up
        to ACON in 0.1 MV steps, centers piezo, then switches to SELAP for
        closed-loop operation. Raises CavityFaultError if ACON <= 0.
        """
        try:
            # Always check for abort first
            self.check_abort()

            if self.rf_ramp_requested:
                try:
                    if self.acon <= 0:
                        err_msg = f"Cannot ramp {self} to {self.acon}"
                        self.set_status_message(err_msg, logging.ERROR)
                        raise linac_utils.CavityFaultError(err_msg)

                    self.set_status_message(
                        f"Waiting for {self} piezo to be in feedback mode",
                        logging.DEBUG,
                    )
                    self.piezo.enable_feedback()
                    self.progress = 80

                    if not self.is_on or (
                        self.is_on and self.rf_mode != linac_utils.RF_MODE_SELAP
                    ):
                        self.ades = min(2, self.acon)

                    self.turn_on()
                    self.progress = 85

                    self.set_status_message(
                        f"Waiting for {self} to be in SELA", logging.DEBUG
                    )
                    self.set_sela_mode()
                    while self.rf_mode != RF_MODE_SELA:
                        self.check_abort()
                        sleep(0.5)

                    self.set_status_message(
                        f"Walking {self} to {self.acon}", logging.INFO
                    )
                    self.walk_amp(self.acon, 0.1)
                    self.progress = 90

                    self.set_status_message(
                        f"Centering {self} piezo", logging.INFO
                    )
                    self.move_to_resonance(use_sela=True)
                    self.progress = 95

                    self.set_status_message(
                        f"Setting {self} to SELAP", logging.INFO
                    )
                    self.set_selap_mode()

                    self.set_status_message(
                        f"{self} Ramped Up to {self.acon} MV", logging.INFO
                    )
                except Exception as e:
                    self.status = STATUS_ERROR_VALUE
                    self.set_status_message(str(e), logging.ERROR)
                    raise

        except Exception as e:
            self.set_status_message(str(e), logging.ERROR)
            raise

    def request_characterization(self):
        """Run cavity characterization (Q-loaded, scale factor) if cav_char_requested."""
        self.check_abort()
        if self.cav_char_requested:
            self.set_status_message(
                f"Running {self} Cavity Characterization", logging.INFO
            )
            self.characterize()
            self.progress = 60
            self.calc_probe_q_pv_obj.put(1)
            self.progress = 70
            self.set_status_message(f"{self} Characterized", logging.INFO)
        self.progress = 75

    def request_auto_tune(self):
        """Move cavity to resonance using stepper if auto_tune_requested."""
        self.check_abort()
        if self.auto_tune_requested:
            self.set_status_message(f"Tuning {self} to Resonance", logging.INFO)
            self.move_to_resonance(use_sela=False)
            self.set_status_message(f"{self} Tuned to Resonance", logging.INFO)
        self.progress = 50

    def request_ssa_cal(self):
        """Run SSA calibration if ssa_cal_requested.

        Resets RF DAC amplitudes to 0 before calibrating (required by the
        calibration procedure). Uses drive_max from the SSA object.
        """
        try:
            if self.ssa_cal_requested:
                self.set_status_message(
                    f"Running {self} SSA Calibration", logging.INFO
                )
                self.turn_off()
                self.rack.rfs1.dac_amp = 0
                self.rack.rfs2.dac_amp = 0
                self.progress = 20
                self.ssa.calibrate(self.ssa.drive_max, attempt=2)
                self.set_status_message(f"{self} SSA Calibrated", logging.INFO)
            self.progress = 25
            self.check_abort()
        except Exception as e:
            self.set_status_message(str(e), logging.ERROR)
            raise
