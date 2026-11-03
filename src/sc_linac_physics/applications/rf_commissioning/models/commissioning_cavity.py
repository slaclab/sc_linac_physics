"""
Commissioning-specific Cavity extension.

Gives RF commissioning a public tuning call, so phases never call the private
Cavity._auto_tune from outside the class. Also records which tab is running
the cavity, so two tabs never run it at once.
"""

import threading
from typing import TYPE_CHECKING, Callable

from sc_linac_physics.utils.sc_linac.cavity import Cavity

if TYPE_CHECKING:
    from sc_linac_physics.utils.sc_linac.rack import Rack


class CommissioningCavity(Cavity):
    """Cavity with the tuning entry point and the one-tab-at-a-time claim."""

    def __init__(self, cavity_num: int, rack_object: "Rack"):
        super().__init__(cavity_num=cavity_num, rack_object=rack_object)
        # Runs start on the GUI thread but batch piezo pre-RF claims from a
        # worker thread, so the check and the set happen under one lock.
        self._claim_lock = threading.Lock()
        self._claimed_by: object | None = None

    @property
    def claimed_by(self) -> object | None:
        """The holder running this cavity, or None if no tab is."""
        return self._claimed_by

    def claim(self, holder: object) -> bool:
        """Mark this cavity as run by holder.

        Returns True if it was free or holder already had it, False if
        another holder has it. Nothing is written to the machine.
        """
        with self._claim_lock:
            if self._claimed_by is not None and self._claimed_by is not holder:
                return False
            self._claimed_by = holder
            return True

    def release(self, holder: object) -> None:
        """Free this cavity if holder has it. Does nothing otherwise."""
        with self._claim_lock:
            if self._claimed_by is holder:
                self._claimed_by = None

    def tune_to_resonance_chirp(
        self,
        tolerance_hz: float,
        iteration_callback: Callable[[], None] | None = None,
        max_stepper_temp: float | None = None,
    ) -> None:
        """Move the stepper until |CHIRP:DF| <= tolerance_hz.

        Runs Cavity._auto_tune on detune_chirp (the CHIRP:DF PV), with the
        signed step count left as it is.

        It does not call setup_tuning, reset the signed steps, or write
        TUNE_CONFIG = RESONANCE. FrequencyTuningPhase does the setup in
        stage 1, then writes NSTEPS_COLD and TUNE_CONFIG itself after this
        returns. _auto_tune writes TUNE_CONFIG = OTHER on entry.

        Raises what _auto_tune raises: DetuneError, StepperError,
        StepperTempError (stepper over max_stepper_temp), StepperAbortError,
        CavityAbortError.
        """
        self._auto_tune(
            delta_hz_func=lambda: self.detune_chirp,
            tolerance=tolerance_hz,
            iteration_callback=iteration_callback,
            max_stepper_temp=max_stepper_temp,
        )
