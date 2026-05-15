"""Frequency Tuning phase display with live detune plot."""

import time

import pyqtgraph as pg
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot

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
    tuning_data_signal = pyqtSignal(float, float)

    def __init__(
        self, parent=None, session: CommissioningSession | None = None
    ):
        super().__init__(parent, session=session)
        # super().__init__ → setup_ui() → _bind_ui_widgets() → self.tuning_plot set
        self._detune_times: list[float] = []
        self._detune_hz: list[float] = []
        self._live_times: list[float] = []
        self._live_hz: list[float] = []
        self._run_start_time: float = time.time()
        self._actual_curve: pg.PlotDataItem | None = None
        self._projection_curve: pg.PlotDataItem | None = None
        self._live_curve: pg.PlotDataItem | None = None
        self._setup_plot_curves()
        self.tuning_data_signal.connect(self._on_tuning_update)

        self._detune_refresh_timer = QTimer(self)
        self._detune_refresh_timer.setInterval(500)
        self._detune_refresh_timer.timeout.connect(self._refresh_live_detune)
        self._detune_refresh_timer.start()

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
            "on_confirm_and_tune": self._controller.on_confirm_and_tune,
            "on_pause_test": self._controller.on_pause_test,
            "on_abort_test": self._controller.on_abort,
            "on_move_left": self._controller.on_move_left,
            "on_move_right": self._controller.on_move_right,
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

        self._live_curve = pw.plot(
            [],
            [],
            pen=pg.mkPen(color="#ff6b6b", width=1),
            name="Live detune",
        )
        self._actual_curve = pw.plot(
            [],
            [],
            pen=pg.mkPen(color="#4a9eff", width=2),
            symbol="o",
            symbolSize=5,
            symbolBrush="#4a9eff",
            name="Phase run",
        )
        self._projection_curve = pw.plot(
            [],
            [],
            pen=pg.mkPen(color="#ff8c42", width=2, style=Qt.DashLine),
            name="Projection",
        )

    # ------------------------------------------------------------------
    # Public API called by the controller
    # ------------------------------------------------------------------

    def set_projection(
        self, initial_detune_hz: float, hz_per_step: float
    ) -> None:
        """Draw a predictive time-to-resonance line after the probe step completes."""
        if self._projection_curve is None or hz_per_step <= 0:
            return

        t_now = time.time() - self._run_start_time

        if self._detune_hz:
            current_detune = self._detune_hz[-1]
        elif self._live_hz:
            current_detune = self._live_hz[-1]
        else:
            current_detune = initial_detune_hz

        try:
            motor_speed = float(self.speed_spinbox.value())
        except Exception:
            from sc_linac_physics.utils.sc_linac import linac_utils

            motor_speed = float(linac_utils.DEFAULT_STEPPER_SPEED)

        if motor_speed <= 0:
            return

        hz_per_sec = hz_per_step * motor_speed
        t_to_zero = abs(current_detune) / hz_per_sec
        self._projection_curve.setData(
            [t_now, t_now + t_to_zero],
            [current_detune, 0.0],
        )

    def reset_plot(self) -> None:
        """Clear all plot data and reset the time reference at the start of a new run."""
        self._run_start_time = time.time()
        self._detune_times.clear()
        self._detune_hz.clear()
        self._live_times.clear()
        self._live_hz.clear()
        if self._actual_curve is not None:
            self._actual_curve.setData([], [])
        if self._projection_curve is not None:
            self._projection_curve.setData([], [])
        if self._live_curve is not None:
            self._live_curve.setData([], [])

    # ------------------------------------------------------------------
    # Slot — called on the GUI thread via Qt signal/slot
    # ------------------------------------------------------------------

    @pyqtSlot(float, float)
    def _on_tuning_update(self, timestamp: float, detune_hz: float) -> None:
        elapsed = (
            (timestamp - self._run_start_time) if self._run_start_time else 0.0
        )
        self._detune_times.append(elapsed)
        self._detune_hz.append(detune_hz)
        if self._actual_curve is not None:
            self._actual_curve.setData(self._detune_times, self._detune_hz)

    @pyqtSlot()
    def _refresh_live_detune(self) -> None:
        detune = self._controller.get_live_detune()
        if detune is not None and self._live_curve is not None:
            elapsed = time.time() - self._run_start_time
            self._live_times.append(elapsed)
            self._live_hz.append(detune)
            self._live_curve.setData(self._live_times, self._live_hz)

    # ------------------------------------------------------------------
    # Readout helpers called by FrequencyTuningController
    # ------------------------------------------------------------------

    def _update_local_results(self, phase_data: FrequencyTuningData) -> None:
        self._apply_phase_specific_readouts(phase_data)

    def _update_stored_readout(self, phase_data: FrequencyTuningData) -> None:
        self._set_generic_stored_data(phase_data)
