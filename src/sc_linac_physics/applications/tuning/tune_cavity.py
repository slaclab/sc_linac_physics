from typing import Optional

from lcls_tools.common.controls.pyepics.utils import PV

from sc_linac_physics.applications.tuning.tune_utils import (
    ColdLinacObject,
    TUNE_LOG_DIR,
)
from sc_linac_physics.utils.logger import custom_logger
from sc_linac_physics.utils.sc_linac.cavity import Cavity
from sc_linac_physics.utils.sc_linac.linac_utils import (
    TUNE_CONFIG_PARKED_VALUE,
    TUNE_CONFIG_RESONANCE_VALUE,
    TUNE_CONFIG_COLD_VALUE,
    HW_MODE_MAINTENANCE_VALUE,
    HW_MODE_ONLINE_VALUE,
    CavityHWModeError,
    HW_MODE_READY_VALUE,
    PARK_DETUNE,
)


class TuneCavity(Cavity, ColdLinacObject):
    def __init__(
        self,
        cavity_num,
        rack_object,
    ):
        Cavity.__init__(self, cavity_num=cavity_num, rack_object=rack_object)
        ColdLinacObject.__init__(self)
        self.df_cold_pv: str = self.pv_addr("DF_COLD")
        self._df_cold_pv_obj: Optional[PV] = None

    def _init_logger(self):
        """Initialize logger for TuneCavity with TUNE_LOG_DIR."""
        log_dir = TUNE_LOG_DIR / self.cryomodule.name / f"cavity_{self.number}"
        logger_name = f"{self.cryomodule.name}.CAV{self.number}"

        self._logger = custom_logger(
            name=logger_name,
            log_dir=str(log_dir),
            log_filename=f"cavity_{self.number}",
        )

    @property
    def hw_mode_str(self):
        if not self._hw_mode_pv_obj:
            self._hw_mode_pv_obj = PV(self.hw_mode_pv)
        return self._hw_mode_pv_obj.get(as_string=True)

    @property
    def df_cold_pv_obj(self) -> PV:
        if not self._df_cold_pv_obj:
            self._df_cold_pv_obj = PV(self.df_cold_pv)
        return self._df_cold_pv_obj

    def park(self, reset_stepper_count: bool = True):
        if self.tune_config_pv_obj.get() == TUNE_CONFIG_PARKED_VALUE:
            self._logger.debug("Already parked")
            return

        starting_config = self.tune_config_pv_obj.get()

        if reset_stepper_count:
            self._logger.info("Resetting stepper signed count")
            self.stepper_tuner.reset_signed_steps()

        if self.detune_best < PARK_DETUNE:

            def delta_detune():
                return self.detune_best

            self._auto_tune(delta_hz_func=delta_detune, tolerance=1000)

        if starting_config == TUNE_CONFIG_RESONANCE_VALUE:
            self._logger.info(
                "Updating stored steps to park to current step count",
                extra={
                    "extra_data": {
                        "current_steps": self.stepper_tuner.step_tot_pv_obj.get()
                    }
                },
            )
            self.stepper_tuner.nsteps_park_pv_obj.put(
                self.stepper_tuner.step_tot_pv_obj.get()
            )

        self.tune_config_pv_obj.put(TUNE_CONFIG_PARKED_VALUE)

        self._logger.info("Turning cavity and SSA off")
        self.turn_off()
        self.ssa.turn_off()

    def move_to_cold_landing(self, use_rf=True):
        if self.tune_config_pv_obj.get() == TUNE_CONFIG_COLD_VALUE:
            self._logger.info("Already at cold landing")
            self._logger.info("Turning cavity and SSA off")
            self.turn_off()
            self.ssa.turn_off()
            return

        self._logger.debug(
            "Starting move to cold landing",
            extra={"extra_data": {"use_rf": use_rf}},
        )
        self.stepper_tuner.reset_signed_steps()

        if use_rf:
            self.detune_with_rf()
        else:
            self.detune_no_rf()

        self.tune_config_pv_obj.put(TUNE_CONFIG_COLD_VALUE)

    def detune_no_rf(self):
        if self.hw_mode not in [
            HW_MODE_MAINTENANCE_VALUE,
            HW_MODE_ONLINE_VALUE,
            HW_MODE_READY_VALUE,
        ]:
            raise CavityHWModeError(f"{self} not Online, Maintenance, or Ready")

        self._logger.info(
            "Detuning without RF",
            extra={"extra_data": {"hw_mode": self.hw_mode_str}},
        )
        self.check_resonance()
        # If we're not using frequency, it's likely that the cavity is neither
        # on nor in chirp (so the detune check will fail and raise an
        # exception before marking the cavity as at cold landing). This is
        # likely the case when we have lost site power and the cryoplant is
        # unable to support 2 K operation
        self.stepper_tuner.move_to_cold_landing(check_detune=False)

    def detune_with_rf(self):
        if self.hw_mode not in [
            HW_MODE_MAINTENANCE_VALUE,
            HW_MODE_ONLINE_VALUE,
        ]:
            raise CavityHWModeError(f"{self} not Online or in Maintenance")

        df_cold = self.df_cold_pv_obj.get()
        if df_cold:
            chirp_range = abs(df_cold) + 50000
            self._logger.info(
                "Tuning to cold landing frequency",
                extra={
                    "extra_data": {
                        "df_cold_hz": df_cold,
                        "chirp_range_hz": chirp_range,
                    }
                },
            )

            def delta_func():
                return self.detune_best - df_cold

            self.setup_tuning(use_sela=False, chirp_range=chirp_range)
            self._auto_tune(delta_hz_func=delta_func, tolerance=1000)

        else:
            self.detune_by_steps()

        self.tune_config_pv_obj.put(TUNE_CONFIG_COLD_VALUE)
        self._logger.info("Turning cavity and SSA off")
        self.turn_off()
        self.ssa.turn_off()

    def detune_by_steps(self):
        self._logger.info(
            "No cold landing frequency recorded, moving by steps instead"
        )
        self.check_resonance()
        abs_est_detune = abs(
            self.stepper_tuner.steps_cold_landing_pv_obj.get()
            / self.microsteps_per_hz
        )
        self._logger.debug(
            "Moving to cold landing by steps",
            extra={
                "extra_data": {
                    "estimated_detune_hz": abs_est_detune,
                    "chirp_range_hz": abs_est_detune + 50000,
                }
            },
        )
        self.setup_tuning(chirp_range=abs_est_detune + 50000)
        self.stepper_tuner.move_to_cold_landing(check_detune=True)

    def check_resonance(self):
        if self.tune_config_pv_obj.get() != TUNE_CONFIG_RESONANCE_VALUE:
            self._logger.error(
                "Not on resonance, cannot move to cold landing by steps",
                extra={
                    "extra_data": {"tune_config": self.tune_config_pv_obj.get()}
                },
            )
            raise CavityHWModeError(
                f"{self} not on resonance, not moving to cold landing by steps"
            )
