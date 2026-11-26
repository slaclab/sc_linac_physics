"""MP Processing commissioning display."""

from datetime import datetime

import pyqtgraph as pg
from PyQt5.QtCore import Qt, QTimer, pyqtSlot
from PyQt5.QtWidgets import QTableWidgetItem

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningRecord,
    MPProcessingData,
)
from sc_linac_physics.applications.rf_commissioning.ui.builders import (
    MPProcessingUI,
)
from sc_linac_physics.applications.rf_commissioning.ui.builders.mp_processing import (  # noqa: E501
    DECARAD_CHOICES,
    FE_DATA_FIELDS,
    SETTINGS,
)
from sc_linac_physics.applications.rf_commissioning.ui.controllers.mp_processing_controller import (  # noqa: E501
    MPProcessingController,
)
from sc_linac_physics.applications.rf_commissioning.ui.stale_result_prompt import (  # noqa: E501
    ask_rerun,
)

from sc_linac_physics.applications.rf_commissioning.ui.builders.theme import (
    COLOR_ERROR,
    COLOR_PRIMARY,
    COLOR_WARNING,
    SANS_FONT_STACK,
)

from .base_placeholder import BasePlaceholderDisplay

# How often the status box and quench table re-read record.mp_processing.
REFRESH_MS = 1000
PAUSE_TEXT = "⏸ Pause"
RESUME_TEXT = "▶ Resume"
# MPProcessingPhase.pause_state -> (button text, button enabled, status).
PAUSE_STATES = {
    "running": (PAUSE_TEXT, True, "RUNNING"),
    "pausing": ("⏸ Pausing…", False, "PAUSING"),
    "paused": (RESUME_TEXT, True, "PAUSED"),
    "resuming": ("▶ Resuming…", False, "PAUSED"),
}


def since_last_quench_text(
    data: MPProcessingData | None,
    process_started: datetime | None,
    now: datetime,
    resumed_at: datetime | None = None,
) -> str:
    """The "Since last quench" readout, e.g. "4 min 12 s".

    data is this run's record.mp_processing; process_started is when the
    process step began, or None before it has. Before the first quench it
    counts from process_started and says so.

    Each quench's timestamp is when the phase saw the latch
    (MPProcessingData.add_quench), before the 1 s settle and the interlock
    reset. The phase's own stable clock starts after the reset, which can
    retry for about 48 s, so this readout can run that far ahead of it.

    resumed_at is when the last pause ended. Time across a pause means
    nothing, so once it is later than the last quench it counts from there.
    """
    if data is not None and data.quench_events:
        since, suffix = data.quench_events[-1].timestamp, ""
    elif process_started is not None:
        since, suffix = process_started, " (no quench yet)"
    else:
        return "-"
    if resumed_at is not None and resumed_at > since:
        since, suffix = resumed_at, " (since resume)"
    seconds = max(0, int((now - since).total_seconds()))
    return f"{seconds // 60} min {seconds % 60:02d} s{suffix}"


# plot_top uses the readings' 95th percentile only from this many on.
PLOT_MIN_READINGS = 20


def plot_top(doses: list[float], threshold: float) -> float:
    """Top of the radiation plot's y axis, over background.

    The larger of 3 x the FE pause threshold, so the line and the onset
    below it always show, and, from PLOT_MIN_READINGS readings on, 1.2 x
    the 95th percentile reading, so sustained radiation still fits. A
    handful of MP quench spikes don't move it.
    """
    floor = 3 * max(threshold, 1.0)
    # Too few readings for a percentile: two spikes would be the 95th.
    if len(doses) < PLOT_MIN_READINGS:
        return floor
    ordered = sorted(doses)
    p95 = ordered[min(len(ordered) - 1, int(0.95 * len(ordered)))]
    return max(floor, 1.2 * p95)


class MPProcessingDisplay(BasePlaceholderDisplay):
    """Display for the MP Processing phase."""

    UI_CLASS = MPProcessingUI
    PHASE_NAME = "MP Processing"
    DATA_ATTR = "mp_processing"
    DATA_MODEL = MPProcessingData

    def __init__(self, parent=None, session=None):
        self._process_started: datetime | None = None
        # Pause is offered only during the process step.
        self._pause_allowed = False
        # The MPProcessingData the quench table rows came from.
        self._table_data: MPProcessingData | None = None
        super().__init__(parent, session=session)
        self.controller = MPProcessingController(self, self.session)
        self.controller.phase_completed.connect(self._notify_phase_advanced)
        self.controller.setup_pv_connections()
        # Empty plot on its default axes until the first refresh.
        self._draw_radiation_plot()

    def setup_ui(self):
        callbacks = {
            "on_run_automated_test": self.on_start_test,
            "on_pause_test": self.on_pause,
            "on_abort_test": self.on_abort,
            "on_toggle_step_mode": self.on_toggle_step_mode,
            "on_next_step": self.on_next_step,
        }
        self.ui = self.UI_CLASS(self, callbacks)
        main_layout = self.ui.build()
        self._bind_ui_widgets()
        self.setLayout(main_layout)
        self.update_timestamp()
        # setup_ui runs inside BasePlaceholderDisplay.__init__, before the
        # controller exists, so set_running(False) can't be used yet.
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(REFRESH_MS)
        self._refresh_timer.timeout.connect(self.refresh_progress)
        self.ui.update_toolbar_state("idle")
        self.pause_button.setEnabled(False)
        self.fe_save_button.clicked.connect(self.on_save_fe)
        self.override_radiation_button.clicked.connect(
            self.on_override_radiation
        )
        self._build_plot_items()
        self.fe_pause_spin.valueChanged.connect(self._draw_radiation_plot)
        self.full_range_check.toggled.connect(self._draw_radiation_plot)

    # ------------------------------------------------------------------
    # Record
    # ------------------------------------------------------------------

    def refresh_from_record(self, record: CommissioningRecord) -> None:
        context = self.controller.context
        if context is not None and record is not context.record:
            # The session holds a different record object now, e.g. the same
            # cavity reselected from the header, which reloads it. A save
            # retry would save the new object without this run's results.
            self.controller.forget_run()
        data = record.mp_processing
        self.show_fe_fields(data)
        if data is None:
            self._clear_phase_specific_readouts()
            return
        self._set_generic_stored_data(data)
        self._apply_phase_specific_readouts(data)

    def _set_generic_stored_data(self, phase_data) -> None:
        """Stored Data, with Notes cut to its newest line.

        Each pause and resume adds a line to notes. Shown whole they
        stretched the window and squeezed Phase History. The full notes
        are on the label's tooltip and in the database.
        """
        super()._set_generic_stored_data(phase_data)
        notes = (getattr(phase_data, "notes", None) or "").strip()
        lines = notes.splitlines()
        label = self.local_stored_notes
        label.setToolTip(notes)
        if len(lines) > 1:
            label.setText(f"{lines[-1]} (+{len(lines) - 1} more, hover)")

    def on_record_loaded(
        self, record: CommissioningRecord, record_id: int
    ) -> None:
        # A finished-but-unsaved run belongs to the previous record.
        self.controller.forget_run()
        self.controller.update_pv_addresses(
            record.cryomodule, str(record.cavity_number)
        )
        self.refresh_from_record(record)

    def is_running_phase(self) -> bool:
        """The container refuses to change the record while this is True."""
        return self.controller.running

    def _notify_phase_advanced(self, record) -> None:
        parent = self.parent()
        while parent:
            if hasattr(parent, "on_phase_advanced"):
                parent.on_phase_advanced(record)
                break
            parent = parent.parent()

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def read_settings(self) -> dict[str, float | int | None]:
        """MPProcessingLimits keyword arguments from the Settings box."""
        settings = {
            s.field: getattr(self, s.widget).value() * s.scale for s in SETTINGS
        }
        settings["decarad"] = DECARAD_CHOICES[
            self.decarad_combo.currentIndex()
        ][1]
        return settings

    def read_fe_fields(self) -> dict[str, float | None]:
        """MPProcessingData field -> ADES in MV, or None for "not seen"."""
        values = {}
        for widget, field in FE_DATA_FIELDS.items():
            spin = getattr(self, widget)
            value = spin.value()
            values[field] = None if value <= spin.minimum() else value
        return values

    def show_fe_fields(self, data: MPProcessingData | None) -> None:
        """Fill the Field Emission box from a stored run (0 = not seen).

        Save FE is offered when the record has a run to save them to and
        none is running.
        """
        for widget, field in FE_DATA_FIELDS.items():
            value = None if data is None else getattr(data, field)
            getattr(self, widget).setValue(0.0 if value is None else value)
        self.fe_save_button.setEnabled(
            data is not None and not self.controller.running
        )

    def _build_plot_items(self) -> None:
        """The radiation plot's three items, filled by _draw_radiation_plot."""
        plot = self.radiation_plot
        self._reading_dots = plot.plot(
            [],
            [],
            pen=None,
            symbol="o",
            symbolSize=5,
            symbolPen=None,
            symbolBrush=pg.mkBrush(COLOR_PRIMARY),
            name="1 s readings",
        )
        self._quench_crosses = plot.plot(
            [],
            [],
            pen=None,
            symbol="x",
            symbolSize=14,
            symbolPen=pg.mkPen(COLOR_ERROR, width=2),
            symbolBrush=pg.mkBrush(COLOR_ERROR),
            name="just before a quench",
        )
        self._off_scale = plot.plot(
            [],
            [],
            pen=None,
            symbol="t1",
            symbolSize=9,
            symbolPen=None,
            symbolBrush=pg.mkBrush(COLOR_WARNING),
            name="off scale (spike)",
        )
        self._threshold_line = pg.InfiniteLine(
            angle=0,
            movable=False,
            pen=pg.mkPen(COLOR_WARNING, width=1, style=Qt.DashLine),
            label="FE pause above",
            labelOpts={
                "position": 0.97,
                "anchors": [(1, 1), (1, 1)],
                "color": COLOR_WARNING,
            },
        )
        plot.addItem(self._threshold_line, ignoreBounds=False)

    def _draw_radiation_plot(self, *_args) -> None:
        """Redraw from this run's points. Reads no PVs.

        MP quenches can spike far above FE onset, which would flatten the
        low readings if the y axis fitted everything. So by default the axis
        tops out at plot_top() and higher readings show as triangles on the
        top edge. With Full range checked every point is at its real value
        and the axis fits them all, until it is unchecked.
        """
        controller = getattr(self, "controller", None)
        points, quenches = (
            ([], []) if controller is None else controller.plot_points
        )
        threshold = self.fe_pause_spin.value()
        self._threshold_line.setValue(threshold)
        view = self.radiation_plot.getPlotItem()
        xs = [a for a, _ in points]
        if self.full_range_check.isChecked():
            self._reading_dots.setData(xs, [d for _, d in points])
            self._off_scale.setData([], [])
            self._quench_crosses.setData(
                [a for a, _ in quenches], [d for _, d in quenches]
            )
            view.enableAutoRange(x=True, y=True)
            return
        top = plot_top([dose for _, dose in points], threshold)
        on = [(a, d) for a, d in points if d <= top]
        off = [(a, top) for a, d in points if d > top]
        self._reading_dots.setData([p[0] for p in on], [p[1] for p in on])
        self._off_scale.setData([p[0] for p in off], [p[1] for p in off])
        self._quench_crosses.setData(
            [p[0] for p in quenches], [min(p[1], top) for p in quenches]
        )
        view.enableAutoRange(x=True, y=False)
        view.setYRange(0, top * 1.05, padding=0)

    def set_settings_enabled(self, enabled: bool) -> None:
        for setting in SETTINGS:
            getattr(self, setting.widget).setEnabled(enabled)
        self.decarad_combo.setEnabled(enabled)

    # ------------------------------------------------------------------
    # Progress, read from record.mp_processing
    # ------------------------------------------------------------------

    def on_step_started(self, step: str) -> None:
        if step == "process":
            self._process_started = datetime.now()
        self._pause_allowed = step == "process"
        self.pause_button.setEnabled(self._pause_allowed)
        self.pause_button.setText(PAUSE_TEXT)

    def _show_pause_state(self) -> None:
        """The Pause button and status, from the phase's own state.

        Only the worker moves between running and paused, so the tab says
        Paused, and offers Resume, only once the phase has stopped writing.
        While a press is pending the button is off.
        """
        if not self._pause_allowed:
            return
        state = self.controller.pause_state
        text, enabled, status = PAUSE_STATES[state]
        self.pause_button.setText(text)
        self.pause_button.setEnabled(enabled)
        self.local_phase_status.setText(status)
        color = COLOR_PRIMARY if state == "running" else COLOR_WARNING
        self._show_indicator(f"● {status}", color)

    def _show_indicator(self, text: str, color: str) -> None:
        """The toolbar's status text. Same style as update_toolbar_state."""
        indicator = self.ui.widgets["status_indicator"]
        indicator.setText(text)
        indicator.setStyleSheet(
            f"QLabel {{ color: {color}; font-weight: bold; "
            f"font-size: 10pt; font-family: {SANS_FONT_STACK}; }}"
        )

    def refresh_progress(self, now: datetime | None = None) -> None:
        """Re-read this run's quenches. Reads no PVs."""
        self._show_pause_state()
        self.radiation_label.setText(self.controller.radiation_text)
        self._draw_radiation_plot()
        self.override_radiation_button.setEnabled(
            self._pause_allowed and self.controller.radiation_check_on
        )
        data = self.controller.mp_data
        now = now or datetime.now()
        if data is None:
            return
        self.quench_count_label.setText(str(data.quench_count))
        top = data.max_amplitude_reached
        self.max_ades_label.setText("-" if top is None else f"{top:.2f} MV")
        self.since_quench_label.setText(
            since_last_quench_text(
                data,
                self._process_started,
                now,
                resumed_at=self.controller.resumed_at,
            )
        )
        self._fill_quench_table(data)

    def _fill_quench_table(self, data: MPProcessingData) -> None:
        """Add rows for quenches not yet shown. Rows are never rewritten."""
        table = self.quench_table
        if data is not self._table_data:
            # A rerun's verify_initial_state starts a new MPProcessingData.
            table.setRowCount(0)
            self._table_data = data
        events = data.quench_events
        shown = table.rowCount()
        for row in range(shown, len(events)):
            event = events[row]
            if row == 0:
                since = "-"
            elif event.after_pause:
                # The interval spans a pause; see MPProcessingPhase.
                since = "after pause"
            else:
                since = f"{data.quench_intervals_seconds[row - 1]:.0f}"
            table.insertRow(row)
            for column, text in enumerate(
                (
                    str(row + 1),
                    f"{event.timestamp:%H:%M:%S}",
                    f"{event.amplitude:.2f}",
                    since,
                )
            ):
                table.setItem(row, column, QTableWidgetItem(text))
        # Scroll only when a row was added, so an operator who scrolled up
        # to read an earlier quench is not pulled back every second.
        if len(events) > shown:
            table.scrollToBottom()

    def clear_run(self) -> None:
        """Blank this run's readouts and put Start Test back.

        After forget_run, a button still labelled Retry save would start a
        hardware run, not a database write.
        """
        self._process_started = None
        self._table_data = None
        self.quench_table.setRowCount(0)
        # The timer is stopped after a run, so clear the plot here too.
        for item in (self._reading_dots, self._quench_crosses, self._off_scale):
            item.setData([], [])
        if not self.controller.running:
            self.ui.update_toolbar_state("idle")
            self.pause_button.setEnabled(False)
        for name in (
            "step_label",
            "local_phase_status",
            "quench_count_label",
            "max_ades_label",
            "since_quench_label",
        ):
            getattr(self, name).setText("-")

    # ------------------------------------------------------------------
    # Called by the controller
    # ------------------------------------------------------------------

    def set_running(self, running: bool) -> None:
        self.ui.update_toolbar_state("running" if running else "idle")
        # Pause works only inside the process step; on_step_started turns
        # it on there. See MPProcessingController.on_pause.
        self._pause_allowed = False
        self.pause_button.setEnabled(False)
        self.pause_button.setText(PAUSE_TEXT)
        self.set_settings_enabled(not running)
        if running:
            self.fe_save_button.setEnabled(False)
        if running:
            self.local_phase_status.setText("RUNNING")
            self._refresh_timer.start()
        else:
            self._refresh_timer.stop()
            self.refresh_progress()

    def set_next_enabled(self, enabled: bool) -> None:
        self.next_step_btn.setEnabled(enabled)

    def set_step(self, text: str) -> None:
        self.step_label.setText(text)

    def set_retry_save(self) -> None:
        """After a failed database write: Start Test only retries it."""
        self.run_button.setEnabled(True)
        self.run_button.setText("↻ Retry save")

    def on_phase_finished(self, status: str) -> None:
        """status is "COMPLETED" or "FAILED"."""
        self.local_phase_status.setText(status)
        self.set_next_enabled(False)
        self.ui.update_toolbar_state(
            "complete" if status == "COMPLETED" else "error"
        )
        self.pause_button.setEnabled(False)

    def ask_rerun(
        self, label: str, pv: str, stamp: datetime | None, good: bool | None
    ) -> bool | None:
        """Rerun (True), Skip (False) or closed (None) for one stale result."""
        return ask_rerun(self, label, pv, stamp, good)

    # ------------------------------------------------------------------
    # Toolbar
    # ------------------------------------------------------------------

    @pyqtSlot()
    def on_start_test(self):
        self.controller.on_start_test()

    @pyqtSlot()
    def on_override_radiation(self):
        self.controller.on_override_radiation()
        self.override_radiation_button.setEnabled(False)

    @pyqtSlot()
    def on_save_fe(self):
        self.controller.save_fe_fields()

    @pyqtSlot()
    def on_pause(self):
        self.controller.on_pause()
        self._show_pause_state()

    @pyqtSlot()
    def on_abort(self):
        self.controller.on_abort()

    @pyqtSlot()
    def on_toggle_step_mode(self):
        self.controller.on_toggle_step_mode()

    @pyqtSlot()
    def on_next_step(self):
        self.controller.on_next_step()
