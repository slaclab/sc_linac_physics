import time
from typing import TYPE_CHECKING

from sc_linac_physics.utils.epics import LazyPV
from sc_linac_physics.utils.sc_linac import linac_utils

if TYPE_CHECKING:
    from cavity import Cavity


class Piezo(linac_utils.SCLinacObject):
    """
    Python representation of LCLS II piezo tuners. This class provides utility
    functions for toggling feedback mode and changing bias voltage and DC offset

    """

    ENABLE_MAX_ATTEMPTS = 10
    FEEDBACK_MAX_ATTEMPTS = 10

    def __init__(self, cavity: "Cavity"):
        """
        @param cavity: The cavity object tuned by this piezo
        """

        self.cavity: "Cavity" = cavity
        self._pv_prefix: str = self.cavity.pv_addr("PZT:")

        self.enable_pv: str = self.pv_addr("ENABLE")

        self.enable_stat_pv: str = self.pv_addr("ENABLESTAT")

        self.feedback_control_pv: str = self.pv_addr("MODECTRL")

        self.feedback_stat_pv: str = self.pv_addr("MODESTAT")

        self.feedback_setpoint_pv: str = self.pv_addr("INTEG_SP")

        self.dc_setpoint_pv: str = self.pv_addr("DAC_SP")

        self.bias_voltage_pv: str = self.pv_addr("BIAS")

        self.voltage_pv: str = self.pv_addr("V")

        self.hz_per_v_pv: str = self.pv_addr("SCALE")

    def __str__(self):
        return self.cavity.__str__() + " Piezo"

    @property
    def pv_prefix(self):
        return self._pv_prefix

    hz_per_v_pv_obj = LazyPV("hz_per_v_pv")

    @property
    def hz_per_v(self):
        return self.hz_per_v_pv_obj.get()

    voltage_pv_obj = LazyPV("voltage_pv")

    @property
    def voltage(self):
        return self.voltage_pv_obj.get()

    bias_voltage_pv_obj = LazyPV("bias_voltage_pv")

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

    dc_setpoint_pv_obj = LazyPV("dc_setpoint_pv")

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

    feedback_setpoint_pv_obj = LazyPV("feedback_setpoint_pv")

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

    enable_pv_obj = LazyPV("enable_pv")
    enable_stat_pv_obj = LazyPV("enable_stat_pv")

    @property
    def is_enabled(self) -> bool:
        return (
            self.enable_stat_pv_obj.get(use_monitor=False)
            == linac_utils.PIEZO_ENABLE_VALUE
        )

    feedback_control_pv_obj = LazyPV("feedback_control_pv")

    feedback_stat_pv_obj = LazyPV("feedback_stat_pv")

    @property
    def feedback_stat(self):
        return self.feedback_stat_pv_obj.get(use_monitor=False)

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
            if attempt > self.ENABLE_MAX_ATTEMPTS:
                message = (
                    f"Piezo failed to enable after {self.ENABLE_MAX_ATTEMPTS} "
                    "attempts"
                )
                self.cavity.logger.error(
                    message,
                    extra={
                        "extra_data": {
                            "attempt": attempt - 1,
                            "enable_status": (
                                self._enable_stat_pv_obj.value_or_none
                                if self._enable_stat_pv_obj
                                else None
                            ),
                            "piezo": str(self),
                        }
                    },
                )
                raise RuntimeError(message)
            self.cavity.logger.debug(
                "Piezo not enabled, attempting to enable (attempt %d)",
                attempt,
                extra={
                    "extra_data": {
                        "attempt": attempt,
                        "enable_status": (
                            self._enable_stat_pv_obj.value_or_none
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
            if attempt > self.FEEDBACK_MAX_ATTEMPTS:
                message = (
                    "Piezo feedback failed to enable after "
                    f"{self.FEEDBACK_MAX_ATTEMPTS} attempts"
                )
                self.cavity.logger.error(
                    message,
                    extra={
                        "extra_data": {
                            "attempt": attempt - 1,
                            "feedback_stat": (
                                self._feedback_stat_pv_obj.value_or_none
                                if self._feedback_stat_pv_obj
                                else None
                            ),
                            "piezo": str(self),
                        }
                    },
                )
                raise RuntimeError(message)
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
            if attempt > self.FEEDBACK_MAX_ATTEMPTS:
                message = (
                    "Piezo feedback failed to disable after "
                    f"{self.FEEDBACK_MAX_ATTEMPTS} attempts"
                )
                self.cavity.logger.error(
                    message,
                    extra={
                        "extra_data": {
                            "attempt": attempt - 1,
                            "feedback_stat": (
                                self._feedback_stat_pv_obj.value_or_none
                                if self._feedback_stat_pv_obj
                                else None
                            ),
                            "piezo": str(self),
                        }
                    },
                )
                raise RuntimeError(message)
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
