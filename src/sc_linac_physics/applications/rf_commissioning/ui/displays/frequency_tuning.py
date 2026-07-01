"""Frequency Tuning phase display with live detune plot."""

import pyqtgraph as pg
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QDoubleSpinBox

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    FrequencyTuningData,
)
from sc_linac_physics.applications.rf_commissioning.phases.frequency_tuning import (
    FrequencyTuningLimits,
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
        self._live_steps: list[int] = []
        self._live_hz: list[float] = []
        self._projection_curve: pg.PlotDataItem | None = None
        self._live_curve: pg.PlotDataItem | None = None
        self._probe_fit_curve: pg.PlotDataItem | None = None
        self._cursor_curve: pg.PlotDataItem | None = None
        self._cursor_visible: bool = True
        self._setup_plot_curves()

        self._detune_refresh_timer = QTimer(self)
        self._detune_refresh_timer.setInterval(500)
        self._detune_refresh_timer.timeout.connect(self._refresh_live_detune)
        self._detune_refresh_timer.start()

        self._blink_timer = QTimer(self)
        self._blink_timer.setInterval(400)
        self._blink_timer.timeout.connect(self._blink_cursor)
        self._blink_timer.start()

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
            "on_run_stage_4": self._controller.run_stage_4,
            "on_confirm_and_save": self._controller.confirm_and_save,
            "on_pause_test": self._controller.on_pause_test,
            "on_abort_test": self._controller.on_abort,
            "on_move_left": self._controller.on_move_left,
            "on_move_right": self._controller.on_move_right,
            "on_push_to_df_cold": self._controller.push_detune_to_df_cold,
            "on_push_to_scale": self._controller.push_hz_per_step_to_scale,
            "on_confirm_probe_fit": self._controller.confirm_probe_fit,
        }
        self.ui = self.UI_CLASS(self, callbacks)
        main_layout = self.ui.build()
        self._bind_ui_widgets()

        # Widgets are now registered — safe to connect PVs for the active record.
        self._controller.setup_pv_connections()

        self._controller.hz_per_step_updated.connect(
            self._on_hz_per_step_updated
        )
        self.tuning_data_signal.connect(self._on_tuning_data_point)

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

    def _reset_plot_range(self) -> None:
        """Set x-axis to probe-step width so the initial empty plot is usefully ranged."""
        pw: pg.PlotWidget | None = getattr(self, "tuning_plot", None)
        if pw is None:
            return
        probe_steps = FrequencyTuningLimits().probe_steps
        pw.setXRange(0, probe_steps, padding=0.05)
        pw.enableAutoRange()

    def _setup_plot_curves(self) -> None:
        pw: pg.PlotWidget | None = getattr(self, "tuning_plot", None)
        if pw is None:
            return

        self._live_curve = pw.plot(
            [],
            [],
            pen=pg.mkPen(color="#ff6b6b", width=1),
            symbol="o",
            symbolSize=5,
            symbolBrush="#ff6b6b",
            symbolPen=None,
            name="Live detune",
        )
        self._probe_fit_curve = pw.plot(
            [],
            [],
            pen=pg.mkPen(color="#4dd0e1", width=2, style=Qt.DashLine),
            name="Probe fit",
        )
        self._projection_curve = pw.plot(
            [],
            [],
            pen=pg.mkPen(color="#ff8c42", width=2, style=Qt.DashLine),
            name="Projection",
        )
        self._cursor_curve = pw.plot(
            [],
            [],
            pen=None,
            symbol="o",
            symbolSize=10,
            symbolBrush="#ffffff",
            symbolPen=pg.mkPen(color="#ffffff", width=2),
        )

        self._reset_plot_range()

    # ------------------------------------------------------------------
    # Public API called by the controller
    # ------------------------------------------------------------------

    def set_projection(
        self, initial_detune_hz: float, hz_per_step: float
    ) -> None:
        """Draw a steps-to-resonance projection line."""
        if self._projection_curve is None or hz_per_step <= 0:
            return

        current_steps = self._live_steps[-1] if self._live_steps else 0
        current_detune = (
            self._live_hz[-1] if self._live_hz else initial_detune_hz
        )

        signed_hz = self._controller.get_signed_hz_per_step()
        if signed_hz is not None and signed_hz != 0:
            # SCALE convention: steps_to_zero = detune / SCALE (not negated)
            steps_to_target = current_detune / signed_hz
        else:
            # Fallback: infer direction from which way steps have been moving
            if len(self._live_steps) >= 2:
                direction = (
                    1 if self._live_steps[-1] >= self._live_steps[-2] else -1
                )
            else:
                direction = 1
            steps_to_target = direction * abs(current_detune) / hz_per_step

        self._projection_curve.setData(
            [current_steps, current_steps + steps_to_target],
            [current_detune, 0.0],
        )

    def reset_plot(self) -> None:
        """Clear all plot data at the start of a new stage."""
        self._live_steps.clear()
        self._live_hz.clear()
        for curve in (
            self._projection_curve,
            self._live_curve,
            self._probe_fit_curve,
            self._cursor_curve,
        ):
            if curve is not None:
                curve.setData([], [])

    def show_probe_fit(
        self,
        s_d0: int,
        d0_hz: float,
        s_d1: int,
        d1_hz: float,
    ) -> None:
        """Draw the forward-leg probe fit in step-space (s_d0→s_d1)."""
        if self._probe_fit_curve is None:
            return
        self._probe_fit_curve.setData([s_d0, s_d1], [d0_hz, d1_hz])

    def clear_probe_fit(self) -> None:
        if self._probe_fit_curve is not None:
            self._probe_fit_curve.setData([], [])

    @pyqtSlot(float, float)
    def _on_tuning_data_point(self, signed_steps: float, detune: float) -> None:
        """Receive a (signed_steps, detune) point emitted from the phase callback."""
        steps = int(signed_steps)
        self._live_steps.append(steps)
        self._live_hz.append(detune)
        if self._live_curve is not None:
            self._live_curve.setData(self._live_steps, self._live_hz)
        if self._cursor_curve is not None:
            self._cursor_curve.setData([steps], [detune])
        if (
            self._controller._probe_stage_confirmed
            and self._controller._current_stage >= 3
        ):
            hz = self.get_current_hz_per_step()
            if hz:
                self.set_projection(detune, abs(hz))

    @pyqtSlot()
    def _refresh_live_detune(self) -> None:
        """Update the cursor and live-detune line every 500 ms without adding to step history."""
        if not self._live_steps:
            return
        detune = self._controller.get_live_detune()
        if detune is None:
            return
        live_steps = self._controller.get_live_steps()
        steps = live_steps if live_steps is not None else self._live_steps[-1]
        if self._cursor_curve is not None:
            self._cursor_curve.setData([steps], [detune])
        # Extend the live curve to the current position so a line is visible
        # during long motor moves (the history arrays are unchanged).
        if self._live_curve is not None:
            self._live_curve.setData(
                self._live_steps + [steps],
                self._live_hz + [detune],
            )
        if (
            self._controller._probe_stage_confirmed
            and self._controller._current_stage >= 3
            and self._projection_curve is not None
        ):
            signed_hz = self._controller.get_signed_hz_per_step()
            if signed_hz:
                steps_to_target = detune / signed_hz
                self._projection_curve.setData(
                    [steps, steps + steps_to_target],
                    [detune, 0.0],
                )

    @pyqtSlot()
    def _blink_cursor(self) -> None:
        if self._cursor_curve is None:
            return
        self._cursor_visible = not self._cursor_visible
        self._cursor_curve.setVisible(self._cursor_visible)

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
        if hz_per_step != 0:
            self._redraw_fit_and_projection(hz_per_step)

    @pyqtSlot(float)
    def _on_hz_per_step_spinbox_changed(self, hz_per_step: float) -> None:
        """Redraw probe fit and projection when operator edits Hz/step manually."""
        if hz_per_step != 0:
            self._redraw_fit_and_projection(hz_per_step)

    def _redraw_fit_and_projection(self, signed_hz: float) -> None:
        """Recalculate probe fit slope and projection for the given Hz/step value."""
        anchor = self._controller.get_probe_anchor()
        if anchor is not None:
            s_d0, d0_hz, s_d1 = anchor
            probe_delta_steps = s_d1 - s_d0
            # Anchor the probe fit to the first live data point so the slope
            # stays visible in the context of the current stage's data.
            if self._live_steps:
                anchor_step = self._live_steps[0]
                anchor_hz = self._live_hz[0]
            else:
                anchor_step = s_d0
                anchor_hz = d0_hz
            fit_d1 = anchor_hz - signed_hz * probe_delta_steps
            self.show_probe_fit(
                anchor_step,
                anchor_hz,
                anchor_step + probe_delta_steps,
                fit_d1,
            )
        if (
            self._controller._probe_stage_confirmed
            and self._controller._current_stage >= 3
        ):
            self.set_projection(0.0, abs(signed_hz))

    def get_current_hz_per_step(self) -> float | None:
        """Return the current signed Hz/step value from the editable spinbox."""
        hz_spinbox = getattr(self, "hz_per_step_spinbox", None)
        if hz_spinbox is not None:
            val = float(hz_spinbox.value())
            return val if val != 0 else None
        return None

    # ------------------------------------------------------------------
    # Record load hooks
    # ------------------------------------------------------------------

    def on_record_loaded(self, record, record_id: int) -> None:
        """Lock Stage 1 and restore stage states when a saved record is loaded."""
        super().on_record_loaded(record, record_id)
        self._controller.update_pv_addresses(
            record.cryomodule, str(record.cavity_number)
        )
        self._controller.restore_from_record(record)

    def refresh_from_record(self, record) -> None:
        """Re-apply stage restore whenever the active record changes."""
        super().refresh_from_record(record)
        self._controller.update_pv_addresses(
            record.cryomodule, str(record.cavity_number)
        )
        self._controller.restore_from_record(record)

    # ------------------------------------------------------------------
    # Readout helpers called by FrequencyTuningController
    # ------------------------------------------------------------------

    def _update_local_results(self, phase_data: FrequencyTuningData) -> None:
        self._apply_phase_specific_readouts(phase_data)

    def _update_stored_readout(self, phase_data: FrequencyTuningData) -> None:
        self._set_generic_stored_data(phase_data)
