import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QKeySequence
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
)
from pydm import Display

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

HEATMAP_ROWS = [
    [("L0B", L0B), ("L1B", L1B + L1BHL), ("L2B", L2B)],
    [("L3B", L3B)],
    [("L4B", L4B)],
]

HIGHLIGHT_THRESHOLD_FRACTION = 0.75


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

        self._color_mapper = ColorMapper(vmin=0, vmax=1, log_scale=True)
        self._severity_filter = SeverityFilter()

        self._cm_widgets: Dict[str, HeatmapCMWidget] = {}
        self._section_labels: Dict[str, QLabel] = {}
        self._section_cm_names: Dict[str, list] = {}
        self._selection: Set[Tuple[str, int]] = set()
        self._last_edited: str = "end"

        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._auto_fit)
        self._auto_fit_in_progress = False

        self._setup_ui()
        self._set_quick_range(hours=1)

        self._cm_to_section: Dict[str, str] = {}
        for row_sections in HEATMAP_ROWS:
            for section_name, cm_names in row_sections:
                self._section_cm_names[section_name] = cm_names
                for cm in cm_names:
                    self._cm_to_section[cm] = section_name

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(2, 2, 2, 2)
        main_layout.setSpacing(4)
        self.setLayout(main_layout)

        main_layout.addLayout(self._build_controls_row())
        main_layout.addLayout(self._build_summary_row())

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

        refresh_shortcut = QShortcut(QKeySequence(Qt.Key_F5), self)
        refresh_shortcut.activated.connect(self._on_refresh_clicked)

        clear_sel_shortcut = QShortcut(QKeySequence(Qt.Key_Escape), self)
        clear_sel_shortcut.activated.connect(self._clear_selection)

    def _build_controls_row(self) -> QHBoxLayout:
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

    def _build_heatmap_row(self, sections: list) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(4)

        for section_name, cm_names in sections:
            section_widget = self._create_linac_section(section_name, cm_names)
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
        """Reset to scale 1.0, then measure on next tick to get correct sizes."""
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
            self._apply_results_to_heatmap(self._results)

    def _populate_tlc_combo(self) -> None:
        """Rebuild TLC dropdown from current results, preserving selection."""
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
        self._apply_results_to_heatmap(self._results)

        valid = [r for r in self._results if not r.is_error]
        errors = sum(1 for r in self._results if r.is_error)
        aborted = self._fetcher.is_abort_requested if self._fetcher else False

        self._status_label.setText(
            self._build_status_text(valid, errors, aborted)
        )
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
        self, results: List[CavityFaultResult]
    ) -> None:
        valid_results = [r for r in results if not r.is_error]
        if not valid_results:
            for section_name, label in self._section_labels.items():
                label.setText(f"{section_name}: \u2014")
            return

        filtered_counts = {
            (r.cm_name, r.cavity_num): self._get_filtered_count(r)
            for r in valid_results
        }

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

        self._update_section_summaries()

    def _update_section_summaries(self) -> None:
        """Aggregate filtered fault counts per linac section."""
        section_totals: Dict[str, int] = {s: 0 for s in self._section_labels}
        for result in self._results:
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
        """Open fault detail display for the double-clicked cavity."""
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
        if self._fetcher and self._fetcher.isRunning():
            self._fetcher.abort()
            if not self._fetcher.wait(timeout=5000):
                self._fetcher.terminate()
                self._fetcher.wait(timeout=2000)
        super().closeEvent(event)


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
