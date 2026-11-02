"""
Commissioning-specific Cavity extension.

Gives RF commissioning a public tuning call, so phases never call the private
Cavity._auto_tune from outside the class.
"""

from typing import Callable

from sc_linac_physics.utils.sc_linac.cavity import Cavity


class CommissioningCavity(Cavity):
    """Cavity with the tuning entry point the frequency tuning phase uses."""

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
