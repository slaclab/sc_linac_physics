from typing import Optional

from lcls_tools.common.controls.pyepics.utils import PV

from sc_linac_physics.utils.sc_linac.linac_utils import SCLinacObject


class LauncherLinacObject(SCLinacObject):
    @property
    def pv_prefix(self):
        return super().pv_prefix

    def auto_pv_addr(self, suffix: str):
        return self.pv_addr(f"AUTO:{suffix}")

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
        self.start_pv_obj.put(1)


class SetupLinacObject(LauncherLinacObject):
    def __init__(self):
        super().__init__(name="SETUP")

        self.off_stop_pv: str = self.auto_pv_addr("OFFSTOP")
        self._off_stop_pv_obj: Optional[PV] = None

        self.shutoff_pv: str = self.auto_pv_addr("OFFSTRT")
        self._shutoff_pv_obj: Optional[PV] = None

        self.ssa_cal_requested_pv: str = self.auto_pv_addr("SETUP_SSAREQ")
        self._ssa_cal_requested_pv_obj: Optional[PV] = None

        self.auto_tune_requested_pv: str = self.auto_pv_addr("SETUP_TUNEREQ")
        self._auto_tune_requested_pv_obj: Optional[PV] = None

        self.cav_char_requested_pv: str = self.auto_pv_addr("SETUP_CHARREQ")
        self._cav_char_requested_pv_obj: Optional[PV] = None

        self.rf_ramp_requested_pv: str = self.auto_pv_addr("SETUP_RAMPREQ")
        self._rf_ramp_requested_pv_obj: Optional[PV] = None

    @property
    def shutoff_pv_obj(self) -> PV:
        if not self._shutoff_pv_obj:
            self._shutoff_pv_obj = PV(self.shutoff_pv)
        return self._shutoff_pv_obj

    def trigger_shutdown(self):
        self.shutoff_pv_obj.put(1)

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
