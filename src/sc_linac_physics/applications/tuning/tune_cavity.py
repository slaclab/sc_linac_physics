from sc_linac_physics.utils.epics import PV

from sc_linac_physics.utils.sc_linac.cavity import Cavity
from sc_linac_physics.utils.sc_linac.linac_utils import (
    TUNE_CONFIG_PARKED_VALUE,
    TUNE_CONFIG_RESONANCE_VALUE,
    TUNE_CONFIG_COLD_VALUE,
    HW_MODE_MAINTENANCE_VALUE,
    HW_MODE_ONLINE_VALUE,
    CavityHWModeError,
    HW_MODE_READY_VALUE,
)

PARK_DETUNE = 10000


class TuneCavity(Cavity):
    def __init__(
        self,
        cavity_num,
        rack_object,
    ):
        super().__init__(cavity_num=cavity_num, rack_object=rack_object)
        self.df_cold_pv: str = self.pv_addr("DF_COLD")
        self._df_cold_pv_obj: PV = None

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

    def park(self, count_current: bool):
        if self.tune_config_pv_obj.get() == TUNE_CONFIG_PARKED_VALUE:
            return

        starting_config = self.tune_config_pv_obj.get()

        if not count_current:
            print(f"Resetting {self} stepper signed count")
            self.stepper_tuner.reset_signed_steps()

        if self.detune_best < PARK_DETUNE:

            def delta_detune():
                return self.detune_best

            self._auto_tune(delta_hz_func=delta_detune, tolerance=1000)

        if starting_config == TUNE_CONFIG_RESONANCE_VALUE:
            print(
                f"Updating stored steps to park to current step count for {self}"
            )
            self.stepper_tuner.nsteps_park_pv_obj.put(
                self.stepper_tuner.step_tot_pv_obj.get()
            )

        self.tune_config_pv_obj.put(TUNE_CONFIG_PARKED_VALUE)

        print("Turning cavity and SSA off")
        self.turn_off()
        self.ssa.turn_off()

    def move_to_cold_landing(self, count_current: bool = False, use_rf=True):
        if self.tune_config_pv_obj.get() == TUNE_CONFIG_COLD_VALUE:
            print(f"{self} at cold landing")
            print(f"Turning {self} and SSA off")
            self.turn_off()
            self.ssa.turn_off()
            return

        if not count_current:
            print(f"Resetting {self} stepper signed count")
            self.stepper_tuner.reset_signed_steps()

        if use_rf:
            self.detune_with_rf(count_current)

        else:
            self.detune_no_rf(count_current)

        self.tune_config_pv_obj.put(TUNE_CONFIG_COLD_VALUE)

    def detune_no_rf(self, count_current=False):
        if self.hw_mode not in [
            HW_MODE_MAINTENANCE_VALUE,
            HW_MODE_ONLINE_VALUE,
            HW_MODE_READY_VALUE,
        ]:
            raise CavityHWModeError(f"{self} not Online, Maintenance, or Ready")
        self.check_resonance()
        # If we're not using frequency, it's likely that the cavity is neither
        # on nor in chirp (so the detune check will fail and raise an
        # exception before marking the cavity as at cold landing). This is
        # likely the case when we have lost site power and the cryoplant is
        # unable to support 2 K operation
        self.stepper_tuner.move_to_cold_landing(
            count_current=count_current, check_detune=False
        )

    def detune_with_rf(self, count_current=False):
        if self.hw_mode not in [
            HW_MODE_MAINTENANCE_VALUE,
            HW_MODE_ONLINE_VALUE,
        ]:
            raise CavityHWModeError(f"{self} not Online or in Maintenance")

        df_cold = self.df_cold_pv_obj.get()
        if df_cold:
            chirp_range = abs(df_cold) + 50000
            print(f"Tuning {self} to {df_cold} Hz")

            def delta_func():
                return self.detune_best - df_cold

            self.setup_tuning(use_sela=False, chirp_range=chirp_range)
            self._auto_tune(delta_hz_func=delta_func, tolerance=1000)

        else:
            self.detune_by_steps(count_current)

        self.tune_config_pv_obj.put(TUNE_CONFIG_COLD_VALUE)
        print("Turning cavity and SSA off")
        self.turn_off()
        self.ssa.turn_off()

    def detune_by_steps(self, count_current):
        print("No cold landing frequency recorded, moving by steps instead")
        self.check_resonance()
        abs_est_detune = abs(
            self.stepper_tuner.steps_cold_landing_pv_obj.get()
            / self.microsteps_per_hz
        )
        self.setup_tuning(chirp_range=abs_est_detune + 50000)
        self.stepper_tuner.move_to_cold_landing(
            count_current=count_current, check_detune=True
        )

    def check_resonance(self):
        if self.tune_config_pv_obj.get() != TUNE_CONFIG_RESONANCE_VALUE:
            raise CavityHWModeError(
                f"{self} not on resonance, not moving to cold landing by steps"
            )
