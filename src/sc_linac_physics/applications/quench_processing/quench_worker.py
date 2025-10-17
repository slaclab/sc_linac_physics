import logging

from sc_linac_physics.applications.quench_processing.quench_cavity import (
    QuenchCavity,
)
from sc_linac_physics.utils.qt import Worker
from sc_linac_physics.utils.sc_linac.linac_utils import (
    CavityAbortError,
    QuenchError,
)

logger = logging.getLogger(__name__)


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
        """Execute the quench processing workflow."""
        self._emit_start_status()

        if not self._validate_parameters():
            return

        try:
            self._execute_quench_process()
            self.finished.emit(f"{self.cavity} quench processing finished")
        except CavityAbortError as e:
            self._handle_abort(e)
        except QuenchError as e:
            self._handle_quench_error(e)
        except Exception as e:
            self._handle_unexpected_error(e)

    def _emit_start_status(self):
        """Emit the initial status message."""
        self.status.emit(
            f"Starting {self.cavity} quench processing: "
            f"{self.start_amp} → {self.end_amp} MV, step={self.step_size} MV, wait={self.step_time}s"
        )

    def _validate_parameters(self):
        """Validate input parameters.

        Returns:
            bool: True if parameters are valid, False otherwise.
        """
        if self.step_size <= 0:
            self.error.emit(f"{self.cavity}: Step Size must be > 0.")
            return False

        if self.step_time <= 0:
            self.error.emit(f"{self.cavity}: Time Between Steps must be > 0.")
            return False

        if self.start_amp > self.end_amp:
            # If descending ramps are intended, remove this and rely on quench_process behavior.
            self.error.emit(
                f"{self.cavity}: Starting Amplitude must be <= Ending Amplitude."
            )
            return False

        return True

    def _execute_quench_process(self):
        """Execute the main quench process on the cavity."""
        self.cavity.quench_process(
            start_amp=self.start_amp,
            end_amp=self.end_amp,
            step_size=self.step_size,
            step_time=self.step_time,
        )

    def _handle_abort(self, exception):
        """Handle abort exceptions.

        Args:
            exception: The CavityAbortError that was raised.
        """
        self.status.emit(
            f"{self.cavity} quench processing aborted: {exception}"
        )
        self._safe_turn_off("abort")
        # Use finished to drive UI cleanup; message clarifies it was aborted.
        self.finished.emit(f"{self.cavity} quench processing aborted")

    def _handle_quench_error(self, exception):
        """Handle quench-specific errors.

        Args:
            exception: The QuenchError that was raised.
        """
        self.error.emit(f"{self.cavity}: {exception}")
        self._safe_turn_off("error")

    def _handle_unexpected_error(self, exception):
        """Handle unexpected exceptions.

        Args:
            exception: The unexpected exception that was raised.
        """
        error_msg = f"Unexpected error during {self.cavity} quench processing: {exception}"
        logger.exception(error_msg)
        self.error.emit(error_msg)
        self._safe_turn_off("unexpected error")

    def _safe_turn_off(self, context="error"):
        """Safely turn off the cavity, handling any exceptions.

        Args:
            context: String describing the context for error reporting.
        """
        try:
            self.cavity.turn_off()
        except Exception as off_e:
            self.status.emit(
                f"{self.cavity}: Turn-off after {context} failed: {off_e}"
            )
