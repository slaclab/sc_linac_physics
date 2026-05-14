"""Frequency Tuning phase display with live detune plot."""

import pyqtgraph as pg
from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    FrequencyTuningData,
)
from sc_linac_physics.applications.rf_commissioning.session_manager import (
    CommissioningSession,
)
from sc_linac_physics.applications.rf_commissioning.ui.builders import (
    FrequencyTuningUI,
)

from .base_placeholder import BasePlaceholderDisplay


class FrequencyTuningDisplay(BasePlaceholderDisplay):
    """Display for the Frequency Tuning phase with a live detune vs. steps plot."""

    UI_CLASS = FrequencyTuningUI
    PHASE_NAME = "Frequency Tuning"
    DATA_ATTR = "frequency_tuning"
    DATA_MODEL = FrequencyTuningData

    # Emitted from the background worker thread; slot runs on the GUI thread.
    tuning_data_signal = pyqtSignal(int, float)

    def __init__(
        self, parent=None, session: CommissioningSession | None = None
    ):
        super().__init__(parent, session=session)
        # super().__init__ → setup_ui() → _bind_ui_widgets() → self.tuning_plot set
        self._detune_steps: list[int] = []
        self._detune_hz: list[float] = []
        self._actual_curve: pg.PlotDataItem | None = None
        self._projection_curve: pg.PlotDataItem | None = None
        self._setup_plot_curves()
        self.tuning_data_signal.connect(self._on_tuning_update)

    # ------------------------------------------------------------------
    # UI setup — overrides base to wire controller callbacks
    # ------------------------------------------------------------------

    def setup_ui(self) -> None:
        from sc_linac_physics.applications.rf_commissioning.ui.controllers.frequency_tuning_controller import (  # noqa: E501
            FrequencyTuningController,
        )

        self._controller = FrequencyTuningController(self, self.session)
        callbacks = {
            "on_run_automated_test": self._controller.on_run_automated_test,
            "on_pause_test": self._controller.on_pause_test,
            "on_abort_test": self._controller.on_abort,
        }
        self.ui = self.UI_CLASS(self, callbacks)
        main_layout = self.ui.build()
        self._bind_ui_widgets()
        self.setLayout(main_layout)
        self.update_timestamp()

    # ------------------------------------------------------------------
    # Plot setup
    # ------------------------------------------------------------------

    def _setup_plot_curves(self) -> None:
        pw: pg.PlotWidget | None = getattr(self, "tuning_plot", None)
        if pw is None:
            return

        self._actual_curve = pw.plot(
            [],
            [],
            pen=pg.mkPen(color="#4a9eff", width=2),
            symbol="o",
            symbolSize=5,
            symbolBrush="#4a9eff",
            name="Measured detune",
        )
        self._projection_curve = pw.plot(
            [],
            [],
            pen=pg.mkPen(color="#ff8c42", width=2, style=Qt.DashLine),
            name="Hz/step projection",
        )

    # ------------------------------------------------------------------
    # Public API called by the controller
    # ------------------------------------------------------------------

    def set_projection(
        self, initial_detune_hz: float, hz_per_step: float
    ) -> None:
        """Draw the linear Hz/step projection after the probe step completes."""
        if self._projection_curve is None or hz_per_step <= 0:
            return
        steps_to_zero = abs(initial_detune_hz) / hz_per_step
        self._projection_curve.setData(
            [0.0, steps_to_zero],
            [initial_detune_hz, 0.0],
        )

    def reset_plot(self) -> None:
        """Clear all plot data at the start of a new run."""
        self._detune_steps.clear()
        self._detune_hz.clear()
        if self._actual_curve is not None:
            self._actual_curve.setData([], [])
        if self._projection_curve is not None:
            self._projection_curve.setData([], [])

    # ------------------------------------------------------------------
    # Slot — called on the GUI thread via Qt signal/slot
    # ------------------------------------------------------------------

    @pyqtSlot(int, float)
    def _on_tuning_update(self, total_steps: int, detune_hz: float) -> None:
        self._detune_steps.append(total_steps)
        self._detune_hz.append(detune_hz)
        if self._actual_curve is not None:
            self._actual_curve.setData(self._detune_steps, self._detune_hz)

    # ------------------------------------------------------------------
    # Readout helpers called by FrequencyTuningController
    # ------------------------------------------------------------------

    def _update_local_results(self, phase_data: FrequencyTuningData) -> None:
        self._apply_phase_specific_readouts(phase_data)

    def _update_stored_readout(self, phase_data: FrequencyTuningData) -> None:
        self._set_generic_stored_data(phase_data)
