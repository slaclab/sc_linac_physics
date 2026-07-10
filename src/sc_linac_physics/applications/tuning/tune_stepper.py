import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sc_linac_physics.applications.tuning.tune_cavity import TuneCavity
from sc_linac_physics.utils.epics import PV
from sc_linac_physics.utils.sc_linac.linac_utils import MAX_STEPPER_SPEED
from sc_linac_physics.utils.sc_linac.stepper import StepperTuner


class TuneStepper(StepperTuner):
    def __init__(self, cavity: "TuneCavity"):
        super().__init__(cavity)
        self.nsteps_park_pv: str = self.pv_addr("NSTEPS_PARK")
        self._nsteps_park_pv_obj: PV = None

        self._park_steps = None

    @property
    def park_steps(self):
        if not self._park_steps:
            self._park_steps = self.cavity.park_detune / self.hz_per_microstep
        return self._park_steps

    @property
    def nsteps_park_pv_obj(self) -> PV:
        if not self._nsteps_park_pv_obj:
            self._nsteps_park_pv_obj = PV(self.nsteps_park_pv)
        return self._nsteps_park_pv_obj

    def move_to_cold_landing(self, check_detune: bool = False):
        steps = self.steps_cold_landing_pv_obj.get()
        self.cavity.set_status_message(
            "Moving stepper to cold landing",
            logging.INFO,
            extra_data={
                "steps": steps,
                "check_detune": check_detune,
                "speed": MAX_STEPPER_SPEED,
            },
        )
        self.move(
            num_steps=steps,
            max_steps=abs(steps),
            speed=MAX_STEPPER_SPEED,
            check_detune=check_detune,
        )

    def park(self, check_detune: bool = False):
        self.cavity.set_status_message(
            "Moving tuner to park position",
            logging.INFO,
            extra_data={
                "target_steps": self.park_steps,
                "check_detune": check_detune,
                "speed": MAX_STEPPER_SPEED,
            },
        )

        self.move(
            num_steps=self.park_steps,
            max_steps=abs(self.park_steps),
            speed=MAX_STEPPER_SPEED,
            check_detune=check_detune,
        )
