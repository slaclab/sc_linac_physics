from sc_linac_physics.utils.epics import PV

from sc_linac_physics.utils.sc_linac.linac_utils import MAX_STEPPER_SPEED
from sc_linac_physics.utils.sc_linac.stepper import StepperTuner


class TuneStepper(StepperTuner):
    def __init__(self, cavity):
        super().__init__(cavity)
        self.nsteps_park_pv: str = self.pv_addr("NSTEPS_PARK")
        self._nsteps_park_pv_obj: PV = None

        self.nsteps_cold_pv: str = self.pv_addr("NSTEPS_COLD")
        self._nsteps_cold_pv_obj: PV = None

        self._step_signed_pv_obj: PV = None
        self._steps_cold_landing_pv_obj: PV = None

    @property
    def steps_cold_landing_pv_obj(self) -> PV:
        if not self._steps_cold_landing_pv_obj:
            self._steps_cold_landing_pv_obj = PV(self.steps_cold_landing_pv)
        return self._steps_cold_landing_pv_obj

    @property
    def nsteps_park_pv_obj(self) -> PV:
        if not self._nsteps_park_pv_obj:
            self._nsteps_park_pv_obj = PV(self.nsteps_park_pv)
        return self._nsteps_park_pv_obj

    @property
    def nsteps_cold_pv_obj(self) -> PV:
        if not self._nsteps_cold_pv_obj:
            self._nsteps_cold_pv_obj = PV(self.nsteps_cold_pv)
        return self._nsteps_cold_pv_obj

    @property
    def step_signed_pv_obj(self):
        if not self._step_signed_pv_obj:
            self._step_signed_pv_obj = PV(self.step_signed_pv)
        return self._step_signed_pv_obj

    def move_to_cold_landing(
        self, count_current: bool = False, check_detune: bool = False
    ):
        recorded_steps = self.nsteps_cold_pv_obj.get()
        if count_current:
            steps = recorded_steps - self.step_signed_pv_obj.get()
        else:
            steps = recorded_steps
        print(f"Moving {steps} steps")
        self.move(
            steps,
            max_steps=abs(steps),
            speed=MAX_STEPPER_SPEED,
            check_detune=check_detune,
        )

    def park(self, count_current: bool):
        adjustment = self.step_signed_pv_obj.get() if count_current else 0
        print(f"Moving {self.cavity} tuner 1.8e6 steps")
        self.move(1800000 - adjustment)
