from time import sleep
from typing import Optional

from epics.ca import CASeverityException

from lcls_tools.common.controls.pyepics.utils import PV, PVInvalidError
from lcls_tools.superconducting import sc_linac_utils
from lcls_tools.superconducting.sc_linac import (
    Cavity,
    Cryomodule,
    Linac,
    Machine,
)
from lcls_tools.superconducting.sc_linac_utils import RF_MODE_SELA, SCLinacObject

STATUS_READY_VALUE = 0
STATUS_RUNNING_VALUE = 1
STATUS_ERROR_VALUE = 2


class AutoLinacObject(SCLinacObject):
    def auto_pv_addr(self, suffix: str):
        return self.pv_addr("AUTO:" + suffix)

    def __init__(self):
        self.abort_pv: str = self.auto_pv_addr("ABORT")
        self._abort_pv_obj: Optional[PV] = None

        self.off_stop_pv: str = self.auto_pv_addr("OFFSTOP")
        self._off_stop_pv_obj: Optional[PV] = None

        self.shutoff_pv: str = self.auto_pv_addr("OFFSTRT")
        self._shutoff_pv_obj: Optional[PV] = None

        self.start_pv: str = self.auto_pv_addr("SETUPSTRT")
        self._start_pv_obj: Optional[PV] = None

        self.stop_pv: str = self.auto_pv_addr("SETUPSTOP")
        self._stop_pv_obj: Optional[PV] = None

        self.ssa_cal_requested_pv: str = self.auto_pv_addr("SETUP_SSAREQ")
        self._ssa_cal_requested_pv_obj: Optional[PV] = None

        self.auto_tune_requested_pv: str = self.auto_pv_addr("SETUP_TUNEREQ")
        self._auto_tune_requested_pv_obj: Optional[PV] = None

        self.cav_char_requested_pv: str = self.auto_pv_addr("SETUP_CHARREQ")
        self._cav_char_requested_pv_obj: Optional[PV] = None

        self.rf_ramp_requested_pv: str = self.auto_pv_addr("SETUP_RAMPREQ")
        self._rf_ramp_requested_pv_obj: Optional[PV] = None

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

    @property
    def shutoff_pv_obj(self) -> PV:
        if not self._shutoff_pv_obj:
            self._shutoff_pv_obj = PV(self.shutoff_pv)
        return self._shutoff_pv_obj

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

    def trigger_setup(self):
        self.start_pv_obj.put(1)

    def trigger_shutdown(self):
        self.shutoff_pv_obj.put(1)

    def request_abort(self):
        self.abort_pv_obj.put(1)

    def kill_setup(self):
        self.stop_pv_obj.put(1)

    @property
    def ssa_cal_requested_pv_obj(self):
        if not self._ssa_cal_requested_pv_obj:
            self._ssa_cal_requested_pv_obj = PV(self.ssa_cal_requested_pv)
        return self._ssa_cal_requested_pv_obj

    @property
    def ssa_cal_requested(self):
        return bool(self.ssa_cal_requested_pv_obj.get())

    @ssa_cal_requested.setter
    def ssa_cal_requested(self, value: bool):
        self.ssa_cal_requested_pv_obj.put(value)

    @property
    def auto_tune_requested_pv_obj(self):
        if not self._auto_tune_requested_pv_obj:
            self._auto_tune_requested_pv_obj = PV(self.auto_tune_requested_pv)
        return self._auto_tune_requested_pv_obj

    @property
    def auto_tune_requested(self):
        return bool(self.auto_tune_requested_pv_obj.get())

    @auto_tune_requested.setter
    def auto_tune_requested(self, value: bool):
        self.auto_tune_requested_pv_obj.put(value)

    @property
    def cav_char_requested_pv_obj(self):
        if not self._cav_char_requested_pv_obj:
            self._cav_char_requested_pv_obj = PV(self.cav_char_requested_pv)
        return self._cav_char_requested_pv_obj

    @property
    def cav_char_requested(self):
        return bool(self.cav_char_requested_pv_obj.get())

    @cav_char_requested.setter
    def cav_char_requested(self, value: bool):
        self.cav_char_requested_pv_obj.put(value)

    @property
    def rf_ramp_requested_pv_obj(self):
        if not self._rf_ramp_requested_pv_obj:
            self._rf_ramp_requested_pv_obj = PV(self.rf_ramp_requested_pv)
        return self._rf_ramp_requested_pv_obj

    @property
    def rf_ramp_requested(self):
        return bool(self.rf_ramp_requested_pv_obj.get())

    @rf_ramp_requested.setter
    def rf_ramp_requested(self, value: bool):
        self.rf_ramp_requested_pv_obj.put(value)


class SetupCavity(Cavity, AutoLinacObject):
    def __init__(
        self,
        cavity_num,
        rack_object,
    ):
        Cavity.__init__(self, cavity_num=cavity_num, rack_object=rack_object)
        AutoLinacObject.__init__(self)

        self.progress_pv: str = self.auto_pv_addr("PROG")
        self._progress_pv_obj: Optional[PV] = None

        self.status_pv: str = self.auto_pv_addr("STATUS")
        self._status_pv_obj: Optional[PV] = None

        self.status_msg_pv: str = self.auto_pv_addr("MSG")
        self._status_msg_pv_obj: Optional[PV] = None

        self.note_pv: str = self.auto_pv_addr("NOTE")
        self._note_pv_obj: Optional[PV] = None

    def capture_acon(self):
        self.acon = self.ades

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
        print(message)
        self.status_msg_pv_obj.put(message)

    def clear_abort(self):
        self.abort_pv_obj.put(0)

    def request_abort(self):
        if self.script_is_running:
            self.status_message = f"Requesting stop for {self}"
            self.abort_pv_obj.put(1)
        else:
            self.status_message = f"{self} script not running, no abort needed"

    def check_abort(self):
        if self.abort_requested:
            self.clear_abort()
            raise sc_linac_utils.CavityAbortError(f"Abort requested for {self}")

    def shut_down(self):
        if self.script_is_running:
            self.status_message = f"{self} script already running"
            return

        self.clear_abort()

        try:
            self.status = STATUS_RUNNING_VALUE
            self.progress = 0
            self.status_message = f"Turning {self} RF off"
            self.turn_off()
            self.progress = 50
            self.status_message = f"Turning {self} SSA off"
            self.ssa.turn_off()
            self.progress = 100
            self.status = STATUS_READY_VALUE
            self.status_message = f"{self} RF and SSA off"
        except (CASeverityException, sc_linac_utils.CavityAbortError) as e:
            self.status = STATUS_ERROR_VALUE
            self.clear_abort()
            self.status_message = str(e)

    def setup(self):
        try:
            if self.script_is_running:
                self.status_message = f"{self} script already running"
                return

            if not self.is_online:
                self.status_message = f"{self} not online, not setting up"
                self.status = STATUS_ERROR_VALUE
                return

            self.clear_abort()

            self.status = STATUS_RUNNING_VALUE
            self.progress = 0

            # Not turning it off can cause problems if an interlock is tripped
            # but the requested RF state is on
            self.status_message = f"Turning {self} off before starting setup"
            self.turn_off()
            self.progress = 5

            self.status_message = f"Turning on {self} SSA if not on already"
            self.ssa.turn_on()
            self.progress = 10

            self.status_message = f"Resetting {self} interlocks"
            self.reset_interlocks()
            self.progress = 15

            if self.ssa_cal_requested:
                self.status_message = f"Running {self} SSA Calibration"
                self.turn_off()
                self.progress = 20
                self.ssa.calibrate(self.ssa.drive_max)
                self.status_message = f"{self} SSA Calibrated"

            self.progress = 25
            self.check_abort()

            if self.auto_tune_requested:
                self.status_message = f"Tuning {self} to Resonance"
                self.move_to_resonance(use_sela=False)
                self.status_message = f"{self} Tuned to Resonance"

            self.progress = 50
            self.check_abort()

            if self.cav_char_requested:
                self.status_message = f"Running {self} Cavity Characterization"
                self.characterize()
                self.progress = 60
                self.calc_probe_q_pv_obj.put(1)
                self.progress = 70
                self.status_message = f"{self} Characterized"

            self.progress = 75
            self.check_abort()

            if self.rf_ramp_requested:
                self.status_message = f"Ramping {self} to {self.acon}"
                self.piezo.enable_feedback()
                self.progress = 80

                if not self.is_on or (
                    self.is_on and self.rf_mode != sc_linac_utils.RF_MODE_SELAP
                ):
                    self.ades = min(5, self.acon)

                self.turn_on()
                self.progress = 85

                self.check_abort()

                self.set_sela_mode()

                while self.rf_mode != RF_MODE_SELA:
                    self.check_abort()
                    self.status_message = "Waiting for cavity to be in SELA"
                    sleep(0.5)

                self.walk_amp(self.acon, 0.1)
                self.progress = 90

                self.status_message = f"Centering {self} piezo"
                self.move_to_resonance(use_sela=True)
                self.progress = 95

                self.set_selap_mode()

                self.status_message = f"{self} Ramped Up to {self.acon} MV"

            self.progress = 100
            self.status = STATUS_READY_VALUE
        except (
            sc_linac_utils.StepperError,
            sc_linac_utils.DetuneError,
            sc_linac_utils.SSACalibrationError,
            PVInvalidError,
            sc_linac_utils.QuenchError,
            sc_linac_utils.CavityQLoadedCalibrationError,
            sc_linac_utils.CavityScaleFactorCalibrationError,
            sc_linac_utils.SSAFaultError,
            sc_linac_utils.StepperAbortError,
            sc_linac_utils.CavityHWModeError,
            sc_linac_utils.CavityFaultError,
            sc_linac_utils.CavityAbortError,
            CASeverityException,
            sc_linac_utils.CavityCharacterizationError,
        ) as e:
            self.status = STATUS_ERROR_VALUE
            self.clear_abort()
            self.status_message = str(e)


class SetupCryomodule(Cryomodule, AutoLinacObject):
    def __init__(
        self,
        cryo_name,
        linac_object,
    ):
        Cryomodule.__init__(
            self,
            cryo_name=cryo_name,
            linac_object=linac_object,
        )
        AutoLinacObject.__init__(self)

    def clear_abort(self):
        for cavity in self.cavities.values():
            cavity.clear_abort()


class SetupLinac(Linac, AutoLinacObject):
    @property
    def pv_prefix(self):
        return f"ACCL:{self.name}:1:"

    def __init__(
        self,
        linac_section,
        beamline_vacuum_infixes,
        insulating_vacuum_cryomodules,
        machine,
    ):
        Linac.__init__(
            self,
            linac_section=linac_section,
            beamline_vacuum_infixes=beamline_vacuum_infixes,
            insulating_vacuum_cryomodules=insulating_vacuum_cryomodules,
            machine=machine,
        )
        AutoLinacObject.__init__(self)

    def clear_abort(self):
        for cm in self.cryomodules.values():
            cm.clear_abort()


class SetupMachine(Machine, AutoLinacObject):
    @property
    def pv_prefix(self):
        return "ACCL:SYS0:SC:"

    def __init__(self):
        Machine.__init__(
            self,
            cavity_class=SetupCavity,
            cryomodule_class=SetupCryomodule,
            linac_class=SetupLinac,
        )
        AutoLinacObject.__init__(self)

    def clear_abort(self):
        for cm in self.cryomodules.values():
            cm.clear_abort()


SETUP_MACHINE = SetupMachine()
