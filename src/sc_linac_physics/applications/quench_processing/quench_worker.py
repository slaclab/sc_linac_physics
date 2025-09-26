from sc_linac_physics.applications.quench_processing.quench_cavity import QuenchCavity
from sc_linac_physics.utils.qt import Worker
from sc_linac_physics.utils.sc_linac.linac_utils import CavityAbortError, QuenchError


class QuenchWorker(Worker):
    def __init__(
        self,
        cavity: QuenchCavity,
        start_amp: float,
        end_amp: float,
        step_time: float,
        step_size: float,
    ):
        super().__init__()
        self.cavity: QuenchCavity = cavity
        self.start_amp = start_amp
        self.end_amp = end_amp
        self.step_time = step_time
        self.step_size = step_size

    def run(self):
        self.status.emit(
            f"Starting {self.cavity} quench processing: "
            f"{self.start_amp} → {self.end_amp} MV, step={self.step_size} MV, wait={self.step_time}s"
        )

        # Defensive checks (UI should also validate, but don’t assume)
        if self.step_size <= 0:
            self.error.emit(f"{self.cavity}: Step Size must be > 0.")
            return
        if self.step_time <= 0:
            self.error.emit(f"{self.cavity}: Time Between Steps must be > 0.")
            return
        if self.start_amp > self.end_amp:
            # If descending ramps are intended, remove this and rely on quench_process behavior.
            self.error.emit(f"{self.cavity}: Starting Amplitude must be <= Ending Amplitude.")
            return

        try:
            self.cavity.quench_process(
                start_amp=self.start_amp,
                end_amp=self.end_amp,
                step_size=self.step_size,
                step_time=self.step_time,
            )
        except CavityAbortError as e:
            # Treat abort as a normal termination from the user perspective.
            self.status.emit(f"{self.cavity} quench processing aborted: {e}")
            try:
                self.cavity.turn_off()
            except Exception as off_e:
                self.status.emit(f"{self.cavity}: Turn-off after abort failed: {off_e}")
            # Use finished to drive UI cleanup; message clarifies it was aborted.
            self.finished.emit(f"{self.cavity} quench processing aborted")
        except QuenchError as e:
            # Real processing error
            self.error.emit(f"{self.cavity}: {e}")
            try:
                self.cavity.turn_off()
            except Exception as off_e:
                self.status.emit(f"{self.cavity}: Turn-off after error failed: {off_e}")
        except Exception as e:
            # Unexpected exception; keep users informed and try to safe the cavity.
            self.error.emit(f"Unexpected error during {self.cavity} quench processing: {e}")
            try:
                self.cavity.turn_off()
            except Exception as off_e:
                self.status.emit(f"{self.cavity}: Turn-off after unexpected error failed: {off_e}")
        else:
            # Normal completion path
            self.finished.emit(f"{self.cavity} quench processing finished")
