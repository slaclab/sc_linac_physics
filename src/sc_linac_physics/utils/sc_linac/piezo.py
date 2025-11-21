import time
from typing import Optional, TYPE_CHECKING

from sc_linac_physics.utils.epics import PV
from sc_linac_physics.utils.sc_linac import linac_utils

if TYPE_CHECKING:
    from cavity import Cavity


class Piezo(linac_utils.SCLinacObject):
    """
    Python representation of LCLS II piezo tuners. This class provides utility
    functions for toggling feedback mode and changing bias voltage and DC offset

    """

    def __init__(self, cavity: "Cavity"):
        """
        @param cavity: The cavity object tuned by this piezo
        """

        self.cavity: "Cavity" = cavity
        self._pv_prefix: str = self.cavity.pv_addr("PZT:")

        self.enable_pv: str = self.pv_addr("ENABLE")
        self._enable_pv_obj: Optional[PV] = None

        self.enable_stat_pv: str = self.pv_addr("ENABLESTAT")
        self._enable_stat_pv_obj: Optional[PV] = None

        self.feedback_control_pv: str = self.pv_addr("MODECTRL")
        self._feedback_control_pv_obj: Optional[PV] = None

        self.feedback_stat_pv: str = self.pv_addr("MODESTAT")
        self._feedback_stat_pv_obj: Optional[PV] = None

        self.feedback_setpoint_pv: str = self.pv_addr("INTEG_SP")
        self._feedback_setpoint_pv_obj: Optional[PV] = None

        self.dc_setpoint_pv: str = self.pv_addr("DAC_SP")
        self._dc_setpoint_pv_obj: Optional[PV] = None

        self.bias_voltage_pv: str = self.pv_addr("BIAS")
        self._bias_voltage_pv_obj: Optional[PV] = None

        self.voltage_pv: str = self.pv_addr("V")
        self._voltage_pv_obj: Optional[PV] = None

        self.hz_per_v_pv: str = self.pv_addr("SCALE")
        self._hz_per_v_pv_obj: Optional[PV] = None

    def __str__(self):
        return self.cavity.__str__() + " Piezo"

    @property
    def pv_prefix(self):
        return self._pv_prefix

    @property
    def hz_per_v(self):
        if not self._hz_per_v_pv_obj:
            self._hz_per_v_pv_obj = PV(self.hz_per_v_pv)
        return self._hz_per_v_pv_obj.get()

    @property
    def voltage_pv_obj(self):
        if not self._voltage_pv_obj:
            self._voltage_pv_obj = PV(self.voltage_pv)
        return self._voltage_pv_obj

    @property
    def voltage(self):
        return self.voltage_pv_obj.get()

    @property
    def bias_voltage_pv_obj(self):
        if not self._bias_voltage_pv_obj:
            self._bias_voltage_pv_obj = PV(self.bias_voltage_pv)
        return self._bias_voltage_pv_obj

    @property
    def bias_voltage(self):
        return self.bias_voltage_pv_obj.get()

    @bias_voltage.setter
    def bias_voltage(self, value):
        self.cavity.logger.debug(
            "Setting piezo bias voltage to %.2fV",
            value,
            extra={"extra_data": {"bias_voltage": value, "piezo": str(self)}},
        )
        self.bias_voltage_pv_obj.put(value)

    @property
    def dc_setpoint_pv_obj(self) -> PV:
        if not self._dc_setpoint_pv_obj:
            self._dc_setpoint_pv_obj = PV(self.dc_setpoint_pv)
        return self._dc_setpoint_pv_obj

    @property
    def dc_setpoint(self):
        return self.dc_setpoint_pv_obj.get()

    @dc_setpoint.setter
    def dc_setpoint(self, value: float):
        self.cavity.logger.debug(
            "Setting piezo DC setpoint to %.2fV",
            value,
            extra={"extra_data": {"dc_setpoint": value, "piezo": str(self)}},
        )
        self.dc_setpoint_pv_obj.put(value)

    @property
    def feedback_setpoint_pv_obj(self) -> PV:
        if not self._feedback_setpoint_pv_obj:
            self._feedback_setpoint_pv_obj = PV(self.feedback_setpoint_pv)
        return self._feedback_setpoint_pv_obj

    @property
    def feedback_setpoint(self):
        return self.feedback_setpoint_pv_obj.get()

    @feedback_setpoint.setter
    def feedback_setpoint(self, value):
        self.cavity.logger.debug(
            "Setting piezo feedback setpoint to %.2f",
            value,
            extra={
                "extra_data": {"feedback_setpoint": value, "piezo": str(self)}
            },
        )
        self.feedback_setpoint_pv_obj.put(value)

    @property
    def enable_pv_obj(self) -> PV:
        if not self._enable_pv_obj:
            self._enable_pv_obj = PV(self._pv_prefix + "ENABLE")
        return self._enable_pv_obj

    @property
    def is_enabled(self) -> bool:
        if not self._enable_stat_pv_obj:
            self._enable_stat_pv_obj = PV(self.enable_stat_pv)
        return self._enable_stat_pv_obj.get() == linac_utils.PIEZO_ENABLE_VALUE

    @property
    def feedback_control_pv_obj(self) -> PV:
        if not self._feedback_control_pv_obj:
            self._feedback_control_pv_obj = PV(self.feedback_control_pv)
        return self._feedback_control_pv_obj

    @property
    def feedback_stat(self):
        if not self._feedback_stat_pv_obj:
            self._feedback_stat_pv_obj = PV(self.feedback_stat_pv)
        return self._feedback_stat_pv_obj.get()

    @property
    def in_manual(self) -> bool:
        return self.feedback_stat == linac_utils.PIEZO_MANUAL_VALUE

    def set_to_feedback(self):
        self.cavity.logger.debug("Setting piezo to feedback mode")
        self.feedback_control_pv_obj.put(linac_utils.PIEZO_FEEDBACK_VALUE)

    def set_to_manual(self):
        self.cavity.logger.debug("Setting piezo to manual mode")
        self.feedback_control_pv_obj.put(linac_utils.PIEZO_MANUAL_VALUE)

    def enable(self):
        self.cavity.logger.info(
            "Enabling piezo with bias voltage 25V",
            extra={"extra_data": {"bias_voltage": 25, "piezo": str(self)}},
        )
        self.bias_voltage = 25

        attempt = 0
        while not self.is_enabled:
            self.cavity.check_abort()
            attempt += 1
            self.cavity.logger.debug(
                "Piezo not enabled, attempting to enable (attempt %d)",
                attempt,
                extra={
                    "extra_data": {
                        "attempt": attempt,
                        "enable_status": (
                            self._enable_stat_pv_obj.get()
                            if self._enable_stat_pv_obj
                            else None
                        ),
                        "piezo": str(self),
                    }
                },
            )
            self.enable_pv_obj.put(linac_utils.PIEZO_DISABLE_VALUE)
            time.sleep(2)
            self.enable_pv_obj.put(linac_utils.PIEZO_ENABLE_VALUE)
            time.sleep(2)

        self.cavity.logger.info(
            "Piezo successfully enabled",
            extra={
                "extra_data": {"total_attempts": attempt, "piezo": str(self)}
            },
        )

    def enable_feedback(self):
        self.cavity.logger.info("Enabling piezo feedback mode")
        self.enable()

        attempt = 0
        while self.in_manual:
            self.cavity.check_abort()
            attempt += 1
            self.cavity.logger.debug(
                "Piezo feedback not enabled, attempting to enable (attempt %d)",
                attempt,
                extra={
                    "extra_data": {
                        "attempt": attempt,
                        "feedback_stat": self.feedback_stat,
                        "piezo": str(self),
                    }
                },
            )
            self.set_to_manual()
            time.sleep(5)
            self.set_to_feedback()
            time.sleep(5)

        self.cavity.logger.info(
            "Piezo feedback successfully enabled",
            extra={
                "extra_data": {
                    "total_attempts": attempt,
                    "feedback_stat": self.feedback_stat,
                    "piezo": str(self),
                }
            },
        )

    def disable_feedback(self):
        self.cavity.logger.info("Disabling piezo feedback mode")
        self.enable()

        attempt = 0
        while not self.in_manual:
            self.cavity.check_abort()
            attempt += 1
            self.cavity.logger.debug(
                "Piezo feedback still enabled, attempting to disable (attempt %d)",
                attempt,
                extra={
                    "extra_data": {
                        "attempt": attempt,
                        "feedback_stat": self.feedback_stat,
                        "piezo": str(self),
                    }
                },
            )
            self.set_to_feedback()
            time.sleep(2)
            self.set_to_manual()
            time.sleep(2)

        self.cavity.logger.info(
            "Piezo feedback successfully disabled",
            extra={
                "extra_data": {
                    "total_attempts": attempt,
                    "feedback_stat": self.feedback_stat,
                    "piezo": str(self),
                }
            },
        )
