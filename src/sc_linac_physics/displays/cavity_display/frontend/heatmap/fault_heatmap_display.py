import math
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QKeySequence
from PyQt5.QtGui import QColor, QPainter
from PyQt5.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QLabel,
    QPushButton,
    QProgressBar,
    QDateTimeEdit,
    QCheckBox,
    QGroupBox,
    QScrollArea,
    QMessageBox,
    QShortcut,
    QSizePolicy,
    QComboBox,
    QSlider,
)
from pydm import Display

from sc_linac_physics.displays.cavity_display.backend.fault import (
    SeverityLevel,
)
from sc_linac_physics.displays.cavity_display.frontend.heatmap.color_bar_widget import (
    ColorBarWidget,
)
from sc_linac_physics.displays.cavity_display.frontend.heatmap.color_mapper import (
    ColorMapper,
)
from sc_linac_physics.displays.cavity_display.frontend.heatmap.fault_data_fetcher import (
    CavityFaultResult,
    FaultDataFetcher,
)
from sc_linac_physics.displays.cavity_display.frontend.heatmap.heatmap_cm_widget import (
    HeatmapCMWidget,
    format_cm_display_name,
)
from sc_linac_physics.displays.cavity_display.frontend.heatmap.severity_filter import (
    SeverityFilter,
)
from sc_linac_physics.utils.sc_linac.linac_utils import (
    L0B,
    L1B,
    L1BHL,
    L2B,
    L3B,
    L4B,
)

# Grid layout mirrors the physical linac, each inner list is one row,
# each tuple is (section label, list of CM names in that section)
HEATMAP_ROWS = [
    [("L0B", L0B), ("L1B", L1B + L1BHL), ("L2B", L2B)],
    [("L3B", L3B)],
    [("L4B", L4B)],
]

# Cavities at or above this fraction of the max get a red highlight border
HIGHLIGHT_THRESHOLD_FRACTION = 0.75

# Per-section color themes for visual distinction between linac regions
LINAC_COLORS = {
    "L0B": {
        "border": "rgb(100, 180, 255)",
        "text": "rgb(100, 180, 255)",
        "bg": "rgb(20, 40, 80)",
    },
    "L1B": {
        "border": "rgb(0, 200, 200)",
        "text": "rgb(0, 220, 220)",
        "bg": "rgb(0, 60, 60)",
    },
    "L2B": {
        "border": "rgb(255, 140, 0)",
        "text": "rgb(255, 160, 40)",
        "bg": "rgb(80, 50, 10)",
    },
    "L3B": {
        "border": "rgb(255, 100, 180)",
        "text": "rgb(255, 120, 200)",
        "bg": "rgb(80, 30, 60)",
    },
    "L4B": {
        "border": "rgb(100, 200, 255)",
        "text": "rgb(120, 200, 255)",
        "bg": "rgb(30, 50, 80)",
    },
}
DEFAULT_LINAC_COLORS = {
    "border": "rgb(100, 100, 100)",
    "text": "rgb(200, 200, 200)",
    "bg": "rgb(50, 50, 50)",
}


class FaultHeatmapDisplay(Display):
    """Main PyDM display for visualizing fault activity across all cavities."""

    def __init__(
        self,
        machine=None,
        parent=None,
        args=None,
        macros=None,
    ) -> None:
        super().__init__(parent=parent, args=args, macros=macros)

        self._machine = machine
        self._fetcher: Optional[FaultDataFetcher] = None
        self._results: List[CavityFaultResult] = []
        self._cavity_filter_active = False

        # Time slider state
        self._slider_active = False
        self._fetch_start: Optional[datetime] = None
        self._fetch_end: Optional[datetime] = None
        # Full-range status text, restored when the slider is disabled
        self._full_range_status: str = ""
        # Fallback when the zoom box holds text that doesn't parse
        self._last_window_duration = timedelta(hours=1)

        # Log scale by default, most cavities cluster near zero, a few spike high
        self._color_mapper = ColorMapper(vmin=0, vmax=1, log_scale=True)
        self._severity_filter = SeverityFilter()

        self._cm_widgets: Dict[str, HeatmapCMWidget] = {}
        self._section_labels: Dict[str, QLabel] = {}
        self._section_cm_names: Dict[str, list] = {}
        self._selection: Set[Tuple[str, int]] = set()
        self._last_edited: str = "end"

        # Debounced resize, without this, dragging the window edge triggers
        # hundreds of expensive relayout cycles
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._auto_fit)
        self._auto_fit_in_progress = False

        # debounce so dragging doesn't recolor on every step
        self._slider_debounce = QTimer(self)
        self._slider_debounce.setSingleShot(True)
        self._slider_debounce.setInterval(50)
        self._slider_debounce.timeout.connect(self._apply_slider_position)

        # playback advances the window one width per tick
        self._play_timer = QTimer(self)
        self._play_timer.setInterval(500)
        self._play_timer.timeout.connect(self._play_step)

        self._setup_ui()
        self._set_quick_range(hours=1)

        self._cm_to_section: Dict[str, str] = {}
        for row_sections in HEATMAP_ROWS:
            for section_name, cm_names in row_sections:
                self._section_cm_names[section_name] = cm_names
                for cm in cm_names:
                    self._cm_to_section[cm] = section_name

    def _setup_ui(self) -> None:
        """Build the full window layout top to bottom:
        controls row, summary row, scrollable heatmap grid + color bar,
        progress bar, status label, selection label."""
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(2, 2, 2, 2)
        main_layout.setSpacing(4)
        self.setLayout(main_layout)

        # Top controls and per section summary
        main_layout.addLayout(self._build_controls_row())
        main_layout.addLayout(self._build_summary_row())
        main_layout.addLayout(self._build_time_slider_row())

        # Scrollable heatmap grid with color bar on the right
        heatmap_row = QHBoxLayout()

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        heatmap_container = QWidget()
        heatmap_layout = QVBoxLayout()
        heatmap_layout.setContentsMargins(0, 0, 0, 0)
        heatmap_layout.setSpacing(4)
        heatmap_container.setLayout(heatmap_layout)

        for row_sections in HEATMAP_ROWS:
            heatmap_layout.addLayout(self._build_heatmap_row(row_sections))

        self._scroll.setWidget(heatmap_container)
        heatmap_row.addWidget(self._scroll, stretch=1)

        self._color_bar = ColorBarWidget(
            color_mapper=self._color_mapper, title="Faults"
        )
        heatmap_row.addWidget(self._color_bar)

        main_layout.addLayout(heatmap_row, stretch=1)

        # Bottom: progress bar, status text, selection info
        self._progress_bar = QProgressBar()
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setFormat("Ready")
        self._progress_bar.setMaximumHeight(14)
        main_layout.addWidget(self._progress_bar)

        self._status_label = QLabel(
            "Select a time range and click Load All Faults."
        )
        self._status_label.setAlignment(Qt.AlignLeft)
        main_layout.addWidget(self._status_label)

        self._selection_label = QLabel("")
        self._selection_label.setAlignment(Qt.AlignLeft)
        self._selection_label.setVisible(False)
        main_layout.addWidget(self._selection_label)

        self.setWindowTitle("LCLS-II Fault Heatmap")

        # Keyboard shortcuts
        refresh_shortcut = QShortcut(QKeySequence(Qt.Key_F5), self)
        refresh_shortcut.activated.connect(self._on_refresh_clicked)

        clear_sel_shortcut = QShortcut(QKeySequence(Qt.Key_Escape), self)
        clear_sel_shortcut.activated.connect(self._clear_selection)

    def _build_controls_row(self) -> QHBoxLayout:
        """Build the top row: time range pickers, quick-range buttons,
        severity checkboxes, TLC dropdown, and action buttons."""
        row = QHBoxLayout()
        row.setSpacing(6)

        # Time range
        time_group = QGroupBox("Time Range")
        time_layout = QHBoxLayout()
        time_layout.setContentsMargins(4, 2, 4, 2)
        time_layout.setSpacing(3)
        time_group.setLayout(time_layout)

        time_layout.addWidget(QLabel("Start:"))
        self._start_dt = QDateTimeEdit()
        self._start_dt.setCalendarPopup(True)
        self._start_dt.setDisplayFormat("yyyy-MM-dd HH:mm")
        self._start_dt.setMinimumWidth(170)
        self._start_dt.dateTimeChanged.connect(
            lambda: setattr(self, "_last_edited", "start")
        )
        time_layout.addWidget(self._start_dt)

        time_layout.addWidget(QLabel("End:"))
        self._end_dt = QDateTimeEdit()
        self._end_dt.setCalendarPopup(True)
        self._end_dt.setDisplayFormat("yyyy-MM-dd HH:mm")
        self._end_dt.setMinimumWidth(170)
        self._end_dt.setDateTime(datetime.now())
        self._end_dt.dateTimeChanged.connect(
            lambda: setattr(self, "_last_edited", "end")
        )
        time_layout.addWidget(self._end_dt)

        for label, kwargs in [
            ("30m", {"minutes": 30}),
            ("1h", {"hours": 1}),
            ("4h", {"hours": 4}),
            ("24h", {"hours": 24}),
            ("1w", {"days": 7}),
        ]:
            btn = QPushButton(label)
            btn.setMinimumWidth(40)
            btn.setFixedHeight(28)
            btn.clicked.connect(
                lambda _, kw=kwargs: self._set_quick_range(**kw)
            )
            time_layout.addWidget(btn)

        row.addWidget(time_group)

        # Severity filters
        filter_group = QGroupBox("Severity Filter")
        filter_layout = QHBoxLayout()
        filter_layout.setContentsMargins(4, 2, 4, 2)
        filter_layout.setSpacing(3)
        filter_group.setLayout(filter_layout)

        self._cb_alarms = QCheckBox("Alarms")
        self._cb_alarms.setChecked(True)
        self._cb_alarms.toggled.connect(self._on_filter_changed)
        filter_layout.addWidget(self._cb_alarms)

        self._cb_warnings = QCheckBox("Warnings")
        self._cb_warnings.setChecked(True)
        self._cb_warnings.toggled.connect(self._on_filter_changed)
        filter_layout.addWidget(self._cb_warnings)

        self._cb_invalid = QCheckBox("Invalid")
        self._cb_invalid.setChecked(True)
        self._cb_invalid.toggled.connect(self._on_filter_changed)
        filter_layout.addWidget(self._cb_invalid)

        row.addWidget(filter_group)

        # TLC fault type selector
        self._tlc_combo = QComboBox()
        self._tlc_combo.addItem("All Fault Types")
        self._tlc_combo.setMinimumWidth(130)
        self._tlc_combo.setFixedHeight(28)
        self._tlc_combo.currentTextChanged.connect(self._on_tlc_filter_changed)
        row.addWidget(self._tlc_combo)

        self._refresh_btn = QPushButton("Load All Faults")
        self._refresh_btn.setFixedHeight(28)
        self._refresh_btn.setMinimumWidth(140)
        refresh_font = QFont()
        refresh_font.setBold(True)
        self._refresh_btn.setFont(refresh_font)
        self._refresh_btn.clicked.connect(self._on_refresh_clicked)
        row.addWidget(self._refresh_btn)

        self._fetch_selected_btn = QPushButton("Fetch Selected")
        self._fetch_selected_btn.setFixedHeight(28)
        self._fetch_selected_btn.setMinimumWidth(120)
        self._fetch_selected_btn.setEnabled(False)
        self._fetch_selected_btn.clicked.connect(
            self._on_fetch_selected_clicked
        )
        row.addWidget(self._fetch_selected_btn)

        self._abort_btn = QPushButton("Abort")
        self._abort_btn.setFixedHeight(28)
        self._abort_btn.setEnabled(False)
        self._abort_btn.clicked.connect(self._on_abort_clicked)
        row.addWidget(self._abort_btn)

        self._clear_selection_btn = QPushButton("Clear Selection")
        self._clear_selection_btn.setFixedHeight(28)
        self._clear_selection_btn.setEnabled(False)
        self._clear_selection_btn.clicked.connect(self._clear_selection)
        row.addWidget(self._clear_selection_btn)

        return row

    def _build_summary_row(self) -> QHBoxLayout:
        """Build a row of color-coded labels showing per-section totals."""
        row = QHBoxLayout()
        row.setSpacing(4)
        for row_sections in HEATMAP_ROWS:
            for section_name, _ in row_sections:
                colors = LINAC_COLORS.get(section_name, DEFAULT_LINAC_COLORS)
                label = QLabel(f"{section_name}: \u2014")  # em-dash
                label.setAlignment(Qt.AlignCenter)
                label.setStyleSheet(
                    f"QLabel {{"
                    f"  color: {colors['text']};"
                    f"  background-color: {colors['bg']};"
                    f"  border: 1px solid {colors['border']};"
                    f"  border-radius: 3px;"
                    f"  padding: 2px 8px;"
                    f"  font-weight: bold;"
                    f"}}"
                )
                row.addWidget(label, stretch=1)
                self._section_labels[section_name] = label
        return row

    def _build_time_slider_row(self) -> QHBoxLayout:
        """Build the time slider controls for scrubbing through fetched data.

        Layout: [Enable checkbox] [Window: combo] [density bar] [slider] [time label]
        The density bar shows where faults are concentrated across the
        fetched time range so you can see hot spots at a glance.
        """
        row = QHBoxLayout()
        row.setSpacing(6)

        slider_group = QGroupBox("Time Slider")
        slider_layout = QHBoxLayout()
        slider_layout.setContentsMargins(4, 2, 4, 2)
        slider_layout.setSpacing(4)
        slider_group.setLayout(slider_layout)

        self._slider_enable_cb = QCheckBox("Enable")
        self._slider_enable_cb.setChecked(False)
        self._slider_enable_cb.setToolTip(
            "Enable to zoom into and scrub through the fetched time range"
        )
        self._slider_enable_cb.toggled.connect(self._on_slider_toggled)
        slider_layout.addWidget(self._slider_enable_cb)

        slider_layout.addWidget(QLabel("Zoom:"))
        self._window_combo = QComboBox()
        # editable so you can type a custom window, not just the presets
        self._window_combo.setEditable(True)
        self._window_combo.setInsertPolicy(QComboBox.NoInsert)
        self._window_combo.addItems(self.ZOOM_PRESETS)
        self._window_combo.setCurrentText("1h")
        self._window_combo.setFixedHeight(28)
        self._window_combo.setMinimumWidth(70)
        self._window_combo.setToolTip(
            "Zoom level — pick a preset or type a custom window size "
            "like 45m, 90m, or 1h30m"
        )
        # activated = dropdown pick, editingFinished = typed value
        self._window_combo.activated.connect(self._on_window_size_changed)
        self._window_combo.lineEdit().editingFinished.connect(
            self._on_window_size_changed
        )
        slider_layout.addWidget(self._window_combo)

        # play/pause steps the window through the range
        self._play_btn = QPushButton("▶")
        self._play_btn.setCheckable(True)
        self._play_btn.setFixedSize(28, 28)
        self._play_btn.setEnabled(False)
        self._play_btn.setToolTip(
            "Play — step the window through the time range automatically"
        )
        self._play_btn.toggled.connect(self._on_play_toggled)
        slider_layout.addWidget(self._play_btn)

        # density bar shows where faults cluster across the range
        self._density_bar = FaultDensityBar()
        self._density_bar.setFixedHeight(16)
        self._density_bar.setMinimumWidth(300)
        self._density_bar.setToolTip(
            "Fault density across the fetched time range — "
            "click to jump the window there"
        )
        self._density_bar.time_clicked.connect(self._on_density_bar_clicked)
        slider_layout.addWidget(self._density_bar, stretch=1)

        self._time_slider = QSlider(Qt.Horizontal)
        self._time_slider.setRange(0, 1000)
        self._time_slider.setValue(0)
        self._time_slider.setEnabled(False)
        self._time_slider.setTickPosition(QSlider.TicksBelow)
        self._time_slider.setTickInterval(100)
        self._time_slider.setMinimumWidth(300)
        self._time_slider.valueChanged.connect(self._on_slider_value_changed)
        slider_layout.addWidget(self._time_slider, stretch=1)

        self._slider_time_label = QLabel("Full Range")
        self._slider_time_label.setMinimumWidth(220)
        self._slider_time_label.setAlignment(Qt.AlignCenter)
        self._slider_time_label.setStyleSheet(
            "QLabel {"
            "  font-weight: bold;"
            "  color: rgb(200, 200, 200);"
            "  background-color: rgb(50, 50, 50);"
            "  border: 1px solid rgb(80, 80, 80);"
            "  border-radius: 3px;"
            "  padding: 2px 6px;"
            "}"
        )
        slider_layout.addWidget(self._slider_time_label)

        row.addWidget(slider_group)
        return row

    # quick-pick presets; custom values can be typed too
    ZOOM_PRESETS = ["15m", "30m", "1h", "2h", "4h"]

    @staticmethod
    def _parse_window_text(text: str) -> Optional[timedelta]:
        """Parse "45m", "1.5h", "1h30m", or a bare number (minutes).

        Returns None if it doesn't parse or is under a minute.
        """
        text = text.strip().lower().replace(" ", "")
        match = re.fullmatch(
            r"(?:(\d+(?:\.\d+)?)h)?(?:(\d+(?:\.\d+)?)m?)?", text
        )
        if not match or not any(match.groups()):
            return None
        hours = float(match.group(1)) if match.group(1) else 0.0
        minutes = float(match.group(2)) if match.group(2) else 0.0
        duration = timedelta(hours=hours, minutes=minutes)
        if duration < timedelta(minutes=1):
            return None
        return duration

    def _get_window_duration(self) -> timedelta:
        """Window size from the zoom box; falls back to the last valid one."""
        duration = self._parse_window_text(self._window_combo.currentText())
        if duration is None:
            return self._last_window_duration
        self._last_window_duration = duration
        return duration

    def _update_zoom_options(self) -> None:
        """Show only presets ≤ half the fetch range (need room to scrub)."""
        if not self._fetch_start or not self._fetch_end:
            return

        total = self._fetch_end - self._fetch_start
        half = total / 2

        previous = self._window_combo.currentText()
        self._window_combo.blockSignals(True)
        self._window_combo.clear()

        for label in self.ZOOM_PRESETS:
            duration = self._parse_window_text(label)
            if duration is not None and duration <= half:
                self._window_combo.addItem(label)

        # keep the previous selection if it still fits the half-range rule
        previous_duration = self._parse_window_text(previous)
        idx = self._window_combo.findText(previous)
        if idx >= 0:
            self._window_combo.setCurrentIndex(idx)
        elif previous_duration is not None and previous_duration <= half:
            self._window_combo.setCurrentText(previous)
        elif self._window_combo.count() > 0:
            self._window_combo.setCurrentIndex(self._window_combo.count() - 1)
        else:
            # nothing fits, so use half the range as a custom window
            minutes = max(1, int(half.total_seconds() // 60))
            self._window_combo.setCurrentText(f"{minutes}m")

        self._window_combo.blockSignals(False)

    def _format_slider_time(
        self, window_start: datetime, window_end: datetime
    ) -> str:
        """Format the slider label, including date when range spans > 24h."""
        if not self._fetch_start or not self._fetch_end:
            return "Full Range"
        total_hours = (
            self._fetch_end - self._fetch_start
        ).total_seconds() / 3600
        if total_hours > 24:
            return (
                f"{window_start.strftime('%m/%d %H:%M')} — "
                f"{window_end.strftime('%m/%d %H:%M')}"
            )
        return (
            f"{window_start.strftime('%H:%M')} — "
            f"{window_end.strftime('%H:%M')}"
        )

    def _on_slider_toggled(self, enabled: bool) -> None:
        """Enable or disable the time slider."""
        self._slider_active = enabled
        self._time_slider.setEnabled(enabled)
        self._window_combo.setEnabled(enabled)
        self._play_btn.setEnabled(enabled)
        if not enabled and self._play_btn.isChecked():
            self._play_btn.setChecked(False)

        if not enabled:
            self._slider_time_label.setText("Full Range")
            self._density_bar.clear_window_position()
            if self._full_range_status:
                self._status_label.setText(self._full_range_status)
            if self._results:
                self._apply_results_to_heatmap(self._results)
        else:
            if self._results and self._fetch_start and self._fetch_end:
                self._apply_slider_position()
            else:
                self._slider_time_label.setText("No data loaded")

    def _on_window_size_changed(self) -> None:
        """Re-apply the slider when the window size changes."""
        if self._slider_active and self._results:
            self._apply_slider_position()

    def _get_slider_geometry(self) -> Optional[Tuple[float, float, float]]:
        """Total, window, and slidable seconds for the fetched range.

        slidable is how far the window can travel (total minus window).
        Returns None if no range is loaded or the window is the whole
        range, since then there's nothing to slide.
        """
        if not self._fetch_start or not self._fetch_end:
            return None
        total = (self._fetch_end - self._fetch_start).total_seconds()
        window = self._get_window_duration().total_seconds()
        slidable = total - window
        if slidable <= 0:
            return None
        return total, window, slidable

    def _on_density_bar_clicked(self, frac: float) -> None:
        """Center the window on the clicked point of the density bar."""
        if not self._slider_active or not self._results:
            return
        geometry = self._get_slider_geometry()
        if geometry is None:
            return
        total, window, slidable = geometry

        offset = frac * total - window / 2
        value = round(offset / slidable * 1000)
        self._time_slider.setValue(max(0, min(1000, value)))

    def _get_play_step(self) -> Optional[int]:
        """One window width in slider units, for playback stepping."""
        geometry = self._get_slider_geometry()
        if geometry is None:
            return None
        _, window, slidable = geometry
        return max(1, round(window / slidable * 1000))

    def _on_play_toggled(self, playing: bool) -> None:
        """Start or stop stepping the window through the range."""
        if playing:
            if (
                not self._results
                or not self._fetch_start
                or not self._fetch_end
            ):
                self._play_btn.setChecked(False)
                return
            # Restart from the beginning if already at the end
            if self._time_slider.value() >= self._time_slider.maximum():
                self._time_slider.setValue(0)
            self._play_btn.setText("⏸")
            self._play_timer.start()
        else:
            self._play_timer.stop()
            self._play_btn.setText("▶")

    def _play_step(self) -> None:
        """Advance the window one width; stop at the end of the range."""
        step = self._get_play_step()
        if step is None:
            self._play_btn.setChecked(False)
            return
        new_value = self._time_slider.value() + step
        if new_value >= self._time_slider.maximum():
            self._time_slider.setValue(self._time_slider.maximum())
            self._play_btn.setChecked(False)
            return
        self._time_slider.setValue(new_value)

    def _on_slider_value_changed(self, value: int) -> None:
        """Restart the 50ms debounce timer on each drag step."""
        if not self._slider_active:
            return
        self._slider_debounce.start()

    def _get_slider_window(self) -> Optional[Tuple[datetime, datetime]]:
        """Calculate the time window for the current slider position.

        Returns None if preconditions aren't met (no data, no range).
        """
        if not self._fetch_start or not self._fetch_end:
            return None
        if not self._results:
            return None

        geometry = self._get_slider_geometry()
        if geometry is None:
            # window covers the whole range, nothing to slide
            return self._fetch_start, self._fetch_end
        _, window_secs, slidable = geometry

        value = self._time_slider.value()
        offset_secs = (value / 1000.0) * slidable
        window_start = self._fetch_start + timedelta(seconds=offset_secs)
        window_end = window_start + timedelta(seconds=window_secs)
        return window_start, window_end

    def _apply_slider_position(self) -> None:
        """Recolor the heatmap for the time window at the current slider pos.

        Called by the debounce timer after the user stops dragging (or
        pauses for 50ms).
        """
        window = self._get_slider_window()
        if window is None:
            return
        window_start, window_end = window

        # Groove clicks and PgUp/PgDn move exactly one window width
        step = self._get_play_step()
        if step is not None:
            self._time_slider.setPageStep(step)

        self._slider_time_label.setText(
            self._format_slider_time(window_start, window_end)
        )

        # Update the density bar overlay to highlight the current window
        if self._fetch_start and self._fetch_end:
            total = (self._fetch_end - self._fetch_start).total_seconds()
            if total > 0:
                start_frac = (
                    window_start - self._fetch_start
                ).total_seconds() / total
                end_frac = (
                    window_end - self._fetch_start
                ).total_seconds() / total
                self._density_bar.set_window_position(start_frac, end_frac)

        self._apply_windowed_results(window_start, window_end)

    def _apply_windowed_results(
        self, window_start: datetime, window_end: datetime
    ) -> None:
        """Re-aggregate fault events for a window and recolor.

        Builds temporary windowed CavityFaultResults and runs them
        through the normal coloring pipeline. Pins the color scale to the
        full-range max so windows stay comparable as you scrub.
        """
        # filtered so the scale tracks the active severity/TLC filters
        full_range_max = max(
            (
                self._get_filtered_count(r)
                for r in self._results
                if not r.is_error
            ),
            default=0,
        )

        windowed_results: List[CavityFaultResult] = []
        for result in self._results:
            if result.is_error:
                windowed_results.append(result)
                continue

            windowed_counts = result.get_windowed_counts(
                window_start, window_end
            )
            if windowed_counts is not None:
                windowed_result = CavityFaultResult(
                    cm_name=result.cm_name,
                    cavity_num=result.cavity_num,
                    fault_counts_by_tlc=windowed_counts,
                    fault_events=result.fault_events,
                )
                windowed_results.append(windowed_result)
            else:
                windowed_results.append(result)

        self._apply_results_to_heatmap(
            windowed_results, vmax_override=full_range_max
        )
        self._update_window_status(windowed_results, window_start, window_end)

    def _update_window_status(
        self,
        windowed_results: List[CavityFaultResult],
        window_start: datetime,
        window_end: datetime,
    ) -> None:
        """Show the current window's totals in the status bar.

        The full-range status is kept in _full_range_status and restored
        when the slider is disabled.
        """
        valid = [r for r in windowed_results if not r.is_error]
        if not valid:
            return

        # One filtered-count pass shared by the total and the max
        counts = [(self._get_filtered_count(r), r) for r in valid]
        total = sum(count for count, _ in counts)
        time_label = self._format_slider_time(window_start, window_end)

        if total == 0:
            self._status_label.setText(f"Window {time_label}: no faults")
            return

        max_count, max_result = max(counts, key=lambda pair: pair[0])
        self._status_label.setText(
            f"Window {time_label}: {total} faults | "
            f"Max: {format_cm_display_name(max_result.cm_name)} "
            f"Cav {max_result.cavity_num} ({max_count})"
        )

    def _update_density_bar(self) -> None:
        """Rebuild the fault density bar from current results.

        Called after a fetch completes and whenever the severity/TLC
        filters change, so the bar shows the same population of faults
        as the heatmap.
        """
        if not self._results or not self._fetch_start or not self._fetch_end:
            self._density_bar.set_data([], self._fetch_start, self._fetch_end)
            return

        include_by_severity = {
            SeverityLevel.WARNING: self._severity_filter.include_warnings,
            SeverityLevel.ALARM: self._severity_filter.include_alarms,
        }
        tlc = self._get_selected_tlc()

        all_timestamps: List[datetime] = []
        for result in self._results:
            if not result.fault_events:
                continue
            for event in result.fault_events:
                # OK transitions are state markers
                if event.severity == SeverityLevel.NO_ALARM:
                    continue
                if tlc is not None and event.status != tlc:
                    continue
                # Anything that isn't warning/alarm counts as invalid
                if not include_by_severity.get(
                    event.severity, self._severity_filter.include_invalid
                ):
                    continue
                all_timestamps.append(event.timestamp)

        self._density_bar.set_data(
            all_timestamps, self._fetch_start, self._fetch_end
        )

    def _build_heatmap_row(self, sections: list) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(4)

        for section_name, cm_names in sections:
            section_widget = self._create_linac_section(section_name, cm_names)
            # Stretch proportional to number of CMs so each cavity column
            # gets roughly the same width across sections
            row.addWidget(section_widget, len(cm_names))

        return row

    def _create_linac_section(
        self, section_name: str, cm_names: list
    ) -> QWidget:
        """Create a bordered section for a linac with header and CMs."""
        section = QWidget()
        section_layout = QVBoxLayout()
        section_layout.setSpacing(2)
        section_layout.setContentsMargins(3, 3, 3, 3)

        # Colored header label
        colors = LINAC_COLORS.get(section_name, DEFAULT_LINAC_COLORS)
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(2)

        header = QLabel(section_name)
        header.setAlignment(Qt.AlignCenter)
        header.setStyleSheet(
            f"QLabel {{"
            f"  font-weight: bold; font-size: 10pt;"
            f"  color: {colors['text']};"
            f"  background-color: {colors['bg']};"
            f"  padding: 3px; border-radius: 2px;"
            f"}}"
        )
        header.setFixedHeight(20)
        header_row.addWidget(header, stretch=1)

        section_select_btn = QPushButton("\u25a3")  # ▣
        section_select_btn.setFixedSize(20, 20)
        section_select_btn.setToolTip(f"Select all cavities in {section_name}")
        section_select_btn.setStyleSheet(
            f"QPushButton {{"
            f"  color: {colors['text']};"
            f"  background-color: {colors['bg']};"
            f"  border: 1px solid {colors['border']};"
            f"  border-radius: 2px;"
            f"  padding: 0px;"
            f"  font-size: 10pt;"
            f"  font-weight: bold;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background-color: {colors['border']};"
            f"}}"
        )
        section_select_btn.clicked.connect(
            lambda _, s=section_name, cms=list(
                cm_names
            ): self._on_section_select_clicked(s, cms)
        )
        header_row.addWidget(section_select_btn)

        section_layout.addLayout(header_row)

        # CM columns side by side
        body = QHBoxLayout()
        body.setSpacing(2)

        for cm_name in cm_names:
            cm_widget = HeatmapCMWidget(cm_name=cm_name)
            cm_widget.cavity_clicked.connect(self._on_cavity_clicked)
            cm_widget.cavity_double_clicked.connect(
                self._on_cavity_double_clicked
            )
            cm_widget.cm_label_clicked.connect(self._on_cm_label_clicked)
            body.addWidget(cm_widget, stretch=1)
            self._cm_widgets[cm_name] = cm_widget

        section_layout.addLayout(body, stretch=1)
        section.setLayout(section_layout)

        # objectName scopes the stylesheet so it only applies to this widget,
        # not its children
        section.setObjectName("linac_section")
        section.setStyleSheet(
            f"#linac_section {{"
            f"  background-color: rgb(35, 35, 35);"
            f"  border: 2px solid {colors['border']};"
            f"  border-radius: 3px;"
            f"}}"
        )
        section.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        return section

    def _set_quick_range(self, minutes=0, hours=0, days=0):
        """Apply a preset time window. Anchors to whichever end the user
        last touched, so clicking '1h' after editing the start time sets
        end = start + 1h, not the other way around."""
        delta = timedelta(minutes=minutes, hours=hours, days=days)
        if getattr(self, "_last_edited", "end") == "start":
            start = self._start_dt.dateTime().toPyDateTime()
            self._end_dt.setDateTime(start + delta)
        else:
            end = self._end_dt.dateTime().toPyDateTime()
            self._start_dt.setDateTime(end - delta)

    def _get_time_range(self) -> tuple:
        start = self._start_dt.dateTime().toPyDateTime()
        end = self._end_dt.dateTime().toPyDateTime()
        if start >= end:
            raise ValueError("Start time must be before end time.")
        return start, end

    def resizeEvent(self, event) -> None:
        """Auto-fit heatmap when window is resized (300ms debounce)."""
        super().resizeEvent(event)
        self._resize_timer.start(300)

    def showEvent(self, event) -> None:
        """Auto-fit on first show."""
        super().showEvent(event)
        self._resize_timer.start(200)

    def _auto_fit(self) -> None:
        """Reset to scale 1.0, then measure on next tick to get correct sizes.

        Two-phase approach: we reset to 1.0 first because Qt's sizeHint is
        wrong if we measure while already scaled. The singleShot(0) lets the
        layout engine settle before we read dimensions.
        """
        if self._auto_fit_in_progress:
            return
        self._auto_fit_in_progress = True

        viewport = self._scroll.viewport()
        if viewport.width() <= 0 or viewport.height() <= 0:
            self._auto_fit_in_progress = False
            return

        self._apply_scale(1.0)
        QTimer.singleShot(0, self._measure_and_fit)

    def _measure_and_fit(self) -> None:
        """Phase 2 of auto-fit: measure content at scale=1.0 and apply."""
        try:
            viewport = self._scroll.viewport()
            available_w = viewport.width()
            available_h = viewport.height()

            if available_w <= 0 or available_h <= 0:
                return

            container = self._scroll.widget()
            if container is None:
                return
            hint = container.sizeHint()
            content_w = hint.width()
            content_h = hint.height()

            if content_w <= 0 or content_h <= 0:
                return

            w_scale = available_w / content_w
            h_scale = available_h / content_h
            scale = min(w_scale, h_scale)
            scale = max(0.5, min(2.0, scale))

            self._apply_scale(scale)
        finally:
            self._auto_fit_in_progress = False

    def _apply_scale(self, scale: float) -> None:
        """Apply zoom scale to CM label fonts."""
        for cm_widget in self._cm_widgets.values():
            cm_widget.set_scale(scale)

    def _on_filter_changed(self) -> None:
        self._severity_filter.set_filter(
            include_alarms=self._cb_alarms.isChecked(),
            include_warnings=self._cb_warnings.isChecked(),
            include_invalid=self._cb_invalid.isChecked(),
        )
        if self._results:
            self._update_density_bar()
            if self._slider_active:
                self._apply_slider_position()
            else:
                self._apply_results_to_heatmap(self._results)

    # TLC fault type filter

    def _get_selected_tlc(self) -> Optional[str]:
        """Return selected TLC code, or None for 'All Fault Types'."""
        text = self._tlc_combo.currentText()
        if text == "All Fault Types":
            return None
        return text

    def _on_tlc_filter_changed(self) -> None:
        """Re-apply heatmap coloring when TLC selection changes."""
        if self._results:
            self._update_density_bar()
            if self._slider_active:
                self._apply_slider_position()
            else:
                self._apply_results_to_heatmap(self._results)

    def _populate_tlc_combo(self) -> None:
        """Rebuild TLC dropdown from current results, preserving selection.

        blockSignals prevents the combo's currentTextChanged from firing
        during the rebuild, which would trigger a redundant recolor."""
        tlc_codes: Set[str] = set()
        for result in self._results:
            if result.fault_counts_by_tlc:
                tlc_codes.update(result.fault_counts_by_tlc.keys())

        current = self._tlc_combo.currentText()
        self._tlc_combo.blockSignals(True)
        self._tlc_combo.clear()
        self._tlc_combo.addItem("All Fault Types")
        for code in sorted(tlc_codes):
            self._tlc_combo.addItem(code)
        # Restore previous selection if still valid
        idx = self._tlc_combo.findText(current)
        self._tlc_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._tlc_combo.blockSignals(False)

    # Fetch lifecycle

    def _on_refresh_clicked(self) -> None:
        """Load faults for ALL cavities."""
        if self._fetcher and self._fetcher.isRunning():
            return
        self._clear_selection()
        self._start_fetch(cavity_filter=None)

    def _on_fetch_selected_clicked(self) -> None:
        """Load faults for only the selected cavities."""
        if not self._selection:
            return
        if self._fetcher and self._fetcher.isRunning():
            return
        self._start_fetch(cavity_filter=set(self._selection))

    def _start_fetch(
        self,
        cavity_filter: Optional[Set[Tuple[str, int]]] = None,
    ) -> None:
        """Kick off a background fetch. If cavity_filter is None, fetches
        everything. Otherwise only re-fetches the specified (cm, cav) pairs
        and merges them into the existing results."""
        try:
            start, end = self._get_time_range()
        except ValueError as e:
            QMessageBox.warning(self, "Invalid Time Range", str(e))
            return

        if self._machine is None:
            QMessageBox.information(
                self,
                "No Machine",
                "No BackendMachine connected.\n"
                "Pass a machine instance to "
                "FaultHeatmapDisplay to fetch real data.",
            )
            return

        self._cavity_filter_active = cavity_filter is not None

        # Store the fetch time range for the slider
        self._fetch_start = start
        self._fetch_end = end

        if cavity_filter is None:
            self._results.clear()
            for cm_widget in self._cm_widgets.values():
                cm_widget.clear_all()
        else:
            self._results = [
                r
                for r in self._results
                if (r.cm_name, r.cavity_num) not in cavity_filter
            ]
            for cm_name, cav_num in cavity_filter:
                cm_widget = self._cm_widgets.get(cm_name)
                if cm_widget:
                    cav_widget = cm_widget.cavity_widgets.get(cav_num)
                    if cav_widget:
                        cav_widget.clear()

        self._refresh_btn.setEnabled(False)
        self._fetch_selected_btn.setEnabled(False)
        self._abort_btn.setEnabled(True)
        self._start_dt.setEnabled(False)
        self._end_dt.setEnabled(False)
        self._progress_bar.setValue(0)
        self._progress_bar.setFormat("Fetching...")
        self._status_label.setText("Fetching fault data from archiver...")

        self._fetcher = FaultDataFetcher(
            self._machine,
            start,
            end,
            cavity_filter=cavity_filter,
            cm_whitelist=set(self._cm_widgets.keys()),
        )
        self._fetcher.progress.connect(self._on_fetch_progress)
        self._fetcher.cavity_result.connect(self._on_cavity_result)
        self._fetcher.finished_all.connect(self._on_fetch_finished)
        self._fetcher.fetch_error.connect(self._on_fetch_error)
        self._fetcher.start()

    def _on_abort_clicked(self) -> None:
        if self._fetcher:
            self._fetcher.abort()
            self._status_label.setText("Aborting...")
            self._abort_btn.setEnabled(False)

    def _on_fetch_progress(self, current: int, total: int) -> None:
        self._progress_bar.setMaximum(total)
        self._progress_bar.setValue(current)
        self._progress_bar.setFormat(f"{current}/{total} cavities")

    def _on_cavity_result(self, result: CavityFaultResult) -> None:
        cm_widget = self._cm_widgets.get(result.cm_name)
        if not cm_widget:
            return
        if result.is_error:
            cm_widget.set_cavity_error(
                result.cavity_num, result.error or "Unknown error"
            )
        else:
            cm_widget.set_cavity_data_pending(result.cavity_num)

    def _on_fetch_finished(self, results: List[CavityFaultResult]) -> None:
        self._merge_results(results)
        self._populate_tlc_combo()
        self._update_zoom_options()
        self._update_density_bar()

        valid = [r for r in self._results if not r.is_error]
        errors = sum(1 for r in self._results if r.is_error)
        aborted = self._fetcher.is_abort_requested if self._fetcher else False
        self._full_range_status = self._build_status_text(
            valid, errors, aborted
        )
        self._status_label.setText(self._full_range_status)

        # after the status text, so an active slider overwrites it
        if self._slider_active and self._fetch_start and self._fetch_end:
            self._apply_slider_position()
        else:
            self._apply_results_to_heatmap(self._results)

        self._progress_bar.setFormat("Done")
        self._cavity_filter_active = False
        self._set_idle_state()

    def _merge_results(self, new_results: List[CavityFaultResult]) -> None:
        """Replace existing results for re-fetched cavities, keep the rest."""
        new_keys = {(r.cm_name, r.cavity_num) for r in new_results}
        self._results = [
            r
            for r in self._results
            if (r.cm_name, r.cavity_num) not in new_keys
        ]
        self._results.extend(new_results)

    def _build_status_text(
        self,
        valid_results: List[CavityFaultResult],
        error_count: int,
        aborted: bool,
    ) -> str:
        """Build the status bar summary string."""
        if valid_results:
            faulted = sum(
                1 for r in valid_results if self._get_filtered_count(r) > 0
            )
            ok_cavities = len(valid_results) - faulted
            max_result = max(
                valid_results,
                key=lambda r: self._get_filtered_count(r),
            )
            max_count = self._get_filtered_count(max_result)
            max_cm = format_cm_display_name(max_result.cm_name)

            parts = [f"{faulted} faulted", f"{ok_cavities} OK"]
            if error_count:
                parts.append(f"{error_count} errors")
            parts.append(
                f"Max: {max_cm} Cav {max_result.cavity_num}" f" ({max_count})"
            )
        else:
            parts = ["0 cavities loaded"]
            if error_count:
                parts.append(f"{error_count} errors")

        if aborted:
            parts.append("(aborted)")

        timestamp = datetime.now().strftime("%H:%M:%S")
        parts.append(f"Updated {timestamp}")
        return " | ".join(parts)

    def _on_fetch_error(self, msg: str) -> None:
        self._status_label.setText(f"Error: {msg}")
        self._progress_bar.setValue(0)
        self._progress_bar.setFormat("Error")
        self._cavity_filter_active = False
        self._set_idle_state()

    def _set_idle_state(self) -> None:
        self._refresh_btn.setEnabled(True)
        self._abort_btn.setEnabled(False)
        self._start_dt.setEnabled(True)
        self._end_dt.setEnabled(True)
        self._fetcher = None
        self._update_selection_ui()

    # Heatmap coloring

    def _get_filtered_count(self, result: CavityFaultResult) -> int:
        tlc = self._get_selected_tlc()
        if tlc is not None and result.fault_counts_by_tlc:
            counter = result.fault_counts_by_tlc.get(tlc)
            if counter is None:
                return 0
            return self._severity_filter.get_filtered_count(counter)
        return self._severity_filter.get_filtered_count(
            result.to_fault_counter()
        )

    def _apply_results_to_heatmap(
        self,
        results: List[CavityFaultResult],
        vmax_override: Optional[int] = None,
    ) -> None:
        """Color the heatmap from the given results.

        vmax_override pins the top of the color scale instead of deriving
        it from the results. The time slider passes the full-range max so
        colors stay comparable as the user scrubs between windows.
        """
        valid_results = [r for r in results if not r.is_error]
        if not valid_results:
            for section_name, label in self._section_labels.items():
                label.setText(f"{section_name}: \u2014")
            return

        filtered_counts = {
            (r.cm_name, r.cavity_num): self._get_filtered_count(r)
            for r in valid_results
        }

        if vmax_override is not None:
            vmax = vmax_override
        else:
            counts = list(filtered_counts.values())
            vmax = max(counts) if counts else 1
        if vmax == 0:
            vmax = 1

        self._color_mapper.set_range(0, vmax)
        self._color_bar.update_range()

        highlight_threshold = math.ceil(HIGHLIGHT_THRESHOLD_FRACTION * vmax)

        for cm_widget in self._cm_widgets.values():
            cm_widget.reset_highlight()

        for result in results:
            cm_widget = self._cm_widgets.get(result.cm_name)
            if not cm_widget:
                continue

            if result.is_error:
                cm_widget.set_cavity_error(
                    result.cavity_num,
                    result.error or "Unknown error",
                )
                continue

            count = filtered_counts[(result.cm_name, result.cavity_num)]
            color = self._color_mapper.get_color(count)
            tooltip = self._build_tooltip(result, count)
            highlight = count >= highlight_threshold and count > 0
            cm_widget.update_cavity(
                result.cavity_num,
                count,
                color,
                tooltip,
                highlight=highlight,
            )

        self._update_section_summaries(results)

    def _update_section_summaries(
        self, results: Optional[List[CavityFaultResult]] = None
    ) -> None:
        """Aggregate filtered fault counts per linac section.

        Uses the passed-in results so the summary reflects windowed
        data when the slider is active, not just the full-range totals.
        """
        if results is None:
            results = self._results
        section_totals: Dict[str, int] = {s: 0 for s in self._section_labels}
        for result in results:
            if result.is_error:
                continue
            section = self._cm_to_section.get(result.cm_name)
            if section:
                section_totals[section] += self._get_filtered_count(result)
        for section_name, label in self._section_labels.items():
            total = section_totals[section_name]
            label.setText(f"{section_name}: {total}")

    def _build_tooltip(
        self, result: CavityFaultResult, filtered_count: int
    ) -> str:
        total = result.alarm_count + result.warning_count + result.invalid_count
        return (
            f"{format_cm_display_name(result.cm_name)} "
            f"Cavity {result.cavity_num}\n"
            f"Alarms:   {result.alarm_count}\n"
            f"Warnings: {result.warning_count}\n"
            f"Invalid:  {result.invalid_count}\n"
            f"Total:    {total}\n"
            f"Filtered: {filtered_count}"
        )

    def _on_cavity_clicked(self, cm_name: str, cavity_num: int) -> None:
        key = (cm_name, cavity_num)
        if key in self._selection:
            self._selection.discard(key)
        else:
            self._selection.add(key)

        cm_widget = self._cm_widgets.get(cm_name)
        if cm_widget:
            cm_widget.set_cavity_selected(cavity_num, key in self._selection)
        self._update_selection_ui()

    def _on_cavity_double_clicked(self, cm_name: str, cavity_num: int) -> None:
        """Open fault detail display for the double-clicked cavity.
        Has to walk the machine hierarchy to find the actual cavity object
        since we only store cm_name/cavity_num in the widget layer."""
        if self._machine is None:
            return
        for linac in self._machine.linacs:
            cm = linac.cryomodules.get(cm_name)
            if cm is None:
                continue
            cavity = cm.cavities.get(cavity_num)
            if cavity is None:
                continue
            if hasattr(cavity, "show_fault_display"):
                cavity.show_fault_display()
            return

    def _on_cm_label_clicked(self, cm_name: str) -> None:
        cm_widget = self._cm_widgets.get(cm_name)
        if not cm_widget:
            return

        if cm_widget.all_selected():
            for cav_num in range(1, HeatmapCMWidget.NUM_CAVITIES + 1):
                self._selection.discard((cm_name, cav_num))
            cm_widget.deselect_all()
        else:
            for cav_num in range(1, HeatmapCMWidget.NUM_CAVITIES + 1):
                self._selection.add((cm_name, cav_num))
            cm_widget.select_all()

        self._update_selection_ui()

    def _on_section_select_clicked(
        self, section_name: str, cm_names: List[str]
    ) -> None:
        """Toggle selection of all cavities in a linac section."""
        cavs = range(1, HeatmapCMWidget.NUM_CAVITIES + 1)
        all_selected = all(
            (cm, cav) in self._selection for cm in cm_names for cav in cavs
        )
        if all_selected:
            for cm in cm_names:
                for cav in cavs:
                    self._selection.discard((cm, cav))
                cm_widget = self._cm_widgets.get(cm)
                if cm_widget:
                    cm_widget.deselect_all()
        else:
            for cm in cm_names:
                for cav in cavs:
                    self._selection.add((cm, cav))
                cm_widget = self._cm_widgets.get(cm)
                if cm_widget:
                    cm_widget.select_all()
        self._update_selection_ui()

    def _update_selection_ui(self) -> None:
        has_selection = len(self._selection) > 0
        self._fetch_selected_btn.setEnabled(has_selection)
        self._clear_selection_btn.setEnabled(has_selection)

        if has_selection:
            count = len(self._selection)
            cm_count = len({cm for cm, _ in self._selection})
            self._selection_label.setText(
                f"{count} cavit{'y' if count == 1 else 'ies'} selected "
                f"across {cm_count} CM{'s' if cm_count != 1 else ''}"
            )
            self._selection_label.setVisible(True)
        else:
            self._selection_label.setVisible(False)

    def _clear_selection(self) -> None:
        self._selection.clear()
        for cm_widget in self._cm_widgets.values():
            cm_widget.deselect_all()
        self._update_selection_ui()

    def closeEvent(self, event) -> None:
        # Give the fetcher thread a chance to exit cleanly before we
        # force terminate, avoids occasional segfaults on shutdown
        if self._fetcher and self._fetcher.isRunning():
            self._fetcher.abort()
            if not self._fetcher.wait(5000):
                self._fetcher.terminate()
                self._fetcher.wait(2000)
        super().closeEvent(event)


class FaultDensityBar(QWidget):
    """Miniature bar chart showing where faults cluster in the time range.

    Divides the fetched time range into equal-width buckets and draws a
    bar for each one proportional to the number of fault events in that
    bucket. Hot spots appear as taller/brighter bars, and clicking one
    emits time_clicked so the display can jump the window there.

    Sits above the slider in the Time Slider group box.
    """

    # Click position as a fraction of the bar width (0.0-1.0)
    time_clicked = pyqtSignal(float)

    NUM_BUCKETS = 100
    BAR_COLOR = QColor(255, 140, 0)  # orange
    BAR_PEAK_COLOR = QColor(255, 60, 60)  # red for the densest buckets
    BG_COLOR = QColor(40, 40, 40)
    WINDOW_COLOR = QColor(100, 180, 255, 60)  # translucent blue overlay
    WINDOW_BORDER = QColor(100, 180, 255, 200)  # bright blue edge lines

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._buckets: List[int] = []
        self._max_count = 0
        # Window overlay position as fractions of the bar width (0.0–1.0)
        self._window_start_frac: Optional[float] = None
        self._window_end_frac: Optional[float] = None
        self.setMinimumHeight(12)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self.width() > 0:
            frac = event.x() / self.width()
            self.time_clicked.emit(max(0.0, min(1.0, frac)))

    def set_data(
        self,
        timestamps: List[datetime],
        start: Optional[datetime],
        end: Optional[datetime],
    ) -> None:
        """Bucket the timestamps and trigger a repaint."""
        if not timestamps or not start or not end:
            self._buckets = []
            self._max_count = 0
            self.update()
            return

        total_secs = (end - start).total_seconds()
        if total_secs <= 0:
            self._buckets = []
            self._max_count = 0
            self.update()
            return

        buckets = [0] * self.NUM_BUCKETS
        for ts in timestamps:
            # the archiver's pre-range sample would land in a bad bucket
            if ts < start or ts > end:
                continue
            offset = (ts - start).total_seconds()
            idx = int((offset / total_secs) * self.NUM_BUCKETS)
            idx = max(0, min(idx, self.NUM_BUCKETS - 1))
            buckets[idx] += 1

        self._buckets = buckets
        self._max_count = max(buckets) if buckets else 0
        self.update()

    def set_window_position(
        self,
        start_frac: float,
        end_frac: float,
    ) -> None:
        """Overlay the current window on the bar (fractions 0.0-1.0)."""
        self._window_start_frac = max(0.0, min(1.0, start_frac))
        self._window_end_frac = max(0.0, min(1.0, end_frac))
        self.update()

    def clear_window_position(self) -> None:
        """Remove the window overlay."""
        self._window_start_frac = None
        self._window_end_frac = None
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)

        w = self.width()
        h = self.height()

        # Background
        painter.fillRect(0, 0, w, h, self.BG_COLOR)

        if not self._buckets or self._max_count == 0:
            painter.end()
            return

        n = len(self._buckets)
        bar_width = w / n

        for i, count in enumerate(self._buckets):
            if count == 0:
                continue
            fraction = count / self._max_count
            bar_height = max(1, int(fraction * h))

            # Interpolate color from orange to red based on density
            r = int(
                self.BAR_COLOR.red()
                + (self.BAR_PEAK_COLOR.red() - self.BAR_COLOR.red()) * fraction
            )
            g = int(
                self.BAR_COLOR.green()
                + (self.BAR_PEAK_COLOR.green() - self.BAR_COLOR.green())
                * fraction
            )
            b = int(
                self.BAR_COLOR.blue()
                + (self.BAR_PEAK_COLOR.blue() - self.BAR_COLOR.blue())
                * fraction
            )
            color = QColor(r, g, b)

            x = int(i * bar_width)
            bw = max(1, int(bar_width))
            painter.fillRect(x, h - bar_height, bw, bar_height, color)

        # Draw translucent overlay showing the current slider window
        if (
            self._window_start_frac is not None
            and self._window_end_frac is not None
        ):
            x0 = int(self._window_start_frac * w)
            x1 = int(self._window_end_frac * w)
            overlay_w = max(1, x1 - x0)
            painter.fillRect(x0, 0, overlay_w, h, self.WINDOW_COLOR)
            # Left and right edge lines for crisp borders
            painter.fillRect(x0, 0, 1, h, self.WINDOW_BORDER)
            painter.fillRect(x0 + overlay_w - 1, 0, 1, h, self.WINDOW_BORDER)

        painter.end()


if __name__ == "__main__":
    import logging
    import sys

    import lcls_tools.common.data.archiver as _archiver
    from PyQt5.QtWidgets import QApplication as _QApp

    from sc_linac_physics.displays.cavity_display.backend.backend_machine import (
        BackendMachine,
    )

    from sc_linac_physics.displays.cavity_display.utils.utils import (
        cavity_fault_logger,
    )

    cavity_fault_logger.setLevel(logging.WARNING)

    _archiver.TIMEOUT = 30

    app = _QApp(sys.argv)
    machine = BackendMachine(lazy_fault_pvs=True)
    window = FaultHeatmapDisplay(machine=machine)
    window.resize(1400, 700)
    window.show()
    sys.exit(app.exec_())
