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
        self.status.emit(f"Starting {self.cavity} quench processing")

        try:
            self.cavity.quench_process(
                start_amp=self.start_amp,
                end_amp=self.end_amp,
                step_size=self.step_size,
                step_time=self.step_time,
            )

            self.finished.emit(f"{self.cavity} quench processing finished")

        except (QuenchError, CavityAbortError) as e:
            self.error.emit(f"{self.cavity}: {e}")
            self.cavity.turn_off()
