"""Frequency Tuning phase display with live detune plot."""

import time

import pyqtgraph as pg
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QDoubleSpinBox

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
        self._live_times: list[float] = []
        self._live_hz: list[float] = []
        self._run_start_time: float = time.time()
        self._projection_curve: pg.PlotDataItem | None = None
        self._live_curve: pg.PlotDataItem | None = None
        self._setup_plot_curves()

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
            "on_run_stage_1": self._controller.run_stage_1,
            "on_run_stage_2": self._controller.run_stage_2,
            "on_run_stage_3": self._controller.run_stage_3,
            "on_confirm_and_save": self._controller.confirm_and_save,
            "on_pause_test": self._controller.on_pause_test,
            "on_abort_test": self._controller.on_abort,
            "on_move_left": self._controller.on_move_left,
            "on_move_right": self._controller.on_move_right,
        }
        self.ui = self.UI_CLASS(self, callbacks)
        main_layout = self.ui.build()
        self._bind_ui_widgets()

        self._controller.hz_per_step_updated.connect(
            self._on_hz_per_step_updated
        )

        hz_spinbox = getattr(self, "hz_per_step_spinbox", None)
        if isinstance(hz_spinbox, QDoubleSpinBox):
            hz_spinbox.valueChanged.connect(
                self._on_hz_per_step_spinbox_changed
            )

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

        if self._live_hz:
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
        self._live_times.clear()
        self._live_hz.clear()
        if self._projection_curve is not None:
            self._projection_curve.setData([], [])
        if self._live_curve is not None:
            self._live_curve.setData([], [])

    @pyqtSlot()
    def _refresh_live_detune(self) -> None:
        detune = self._controller.get_live_detune()
        if detune is not None and self._live_curve is not None:
            elapsed = time.time() - self._run_start_time
            self._live_times.append(elapsed)
            self._live_hz.append(detune)
            self._live_curve.setData(self._live_times, self._live_hz)

    # ------------------------------------------------------------------
    # Hz/step spinbox slots
    # ------------------------------------------------------------------

    @pyqtSlot(float)
    def _on_hz_per_step_updated(self, hz_per_step: float) -> None:
        """Update spinbox when the controller refines the Hz/step estimate."""
        hz_spinbox = getattr(self, "hz_per_step_spinbox", None)
        if hz_spinbox is not None:
            hz_spinbox.blockSignals(True)
            hz_spinbox.setValue(hz_per_step)
            hz_spinbox.blockSignals(False)
        if hz_per_step > 0:
            self.set_projection(0.0, hz_per_step)

    @pyqtSlot(float)
    def _on_hz_per_step_spinbox_changed(self, hz_per_step: float) -> None:
        """Redraw projection when operator edits Hz/step manually."""
        if hz_per_step > 0:
            self.set_projection(0.0, hz_per_step)

    def get_current_hz_per_step(self) -> float | None:
        """Return the current Hz/step value from the editable spinbox."""
        hz_spinbox = getattr(self, "hz_per_step_spinbox", None)
        if hz_spinbox is not None:
            val = float(hz_spinbox.value())
            return val if val > 0 else None
        return None

    # ------------------------------------------------------------------
    # Record load hooks
    # ------------------------------------------------------------------

    def on_record_loaded(self, record, record_id: int) -> None:
        """Lock Stage 1 and restore stage states when a saved record is loaded."""
        super().on_record_loaded(record, record_id)
        self._controller.restore_from_record(record)

    def refresh_from_record(self, record) -> None:
        """Re-apply stage restore whenever the active record changes."""
        super().refresh_from_record(record)
        self._controller.restore_from_record(record)

    # ------------------------------------------------------------------
    # Readout helpers called by FrequencyTuningController
    # ------------------------------------------------------------------

    def _update_local_results(self, phase_data: FrequencyTuningData) -> None:
        self._apply_phase_specific_readouts(phase_data)

    def _update_stored_readout(self, phase_data: FrequencyTuningData) -> None:
        self._set_generic_stored_data(phase_data)
