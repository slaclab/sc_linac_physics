"""
Shared UI builder for RF commissioning displays.
"""

from typing import Callable, Dict, Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QLabel,
    QGridLayout,
    QPushButton,
    QCheckBox,
    QProgressBar,
    QSpinBox,
    QTextEdit,
)
from pydm.widgets import PyDMLabel, PyDMPushButton

PV_LABEL_STYLE = """
    background: #1a2a3a;
    padding: 2px 6px;
    border: 1px solid #4a9eff;
    border-left: 3px solid #4a9eff;
    font-size: 11px;
"""

PV_CAP_STYLE = """
    background-color: #1a2a00;
    padding: 2px 6px;
    border: 1px solid #4a9eff;
    border-left: 3px solid #4a9eff;
    font-family: monospace;
    font-size: 11px;
"""

LOCAL_LABEL_STYLE = """
    background: #2a2a1a;
    padding: 2px 6px;
    border: 1px solid #ff9a4a;
    border-left: 3px solid #ff9a4a;
    font-size: 11px;
"""

LOCAL_CAP_STYLE = """
    background-color: #2a2a00;
    padding: 2px 6px;
    border: 1px solid #ff9a4a;
    border-left: 3px solid #ff9a4a;
    font-family: monospace;
    font-size: 11px;
"""


class PiezoPreRFUI:
    """Builds the Piezo Pre-RF display UI and exposes widget references."""

    def __init__(
        self,
        parent,
        callbacks: Optional[Dict[str, Callable[[], None]]] = None,
    ) -> None:
        self.parent = parent
        self.callbacks = callbacks or {}
        self.widgets: Dict[str, object] = {}

    def build(self) -> QHBoxLayout:
        """Create the main UI layout and return it."""
        main_layout = QHBoxLayout()

        left_panel = QVBoxLayout()
        left_panel.addWidget(self._build_cavity_selection())
        left_panel.addWidget(self._build_piezo_controls())
        left_panel.addLayout(self._build_action_buttons())
        left_panel.addLayout(self._build_auto_test())
        left_panel.addLayout(self._build_view_buttons())
        left_panel.addWidget(self._build_history())

        right_panel = QVBoxLayout()
        right_panel.addWidget(self._build_live_pv_section())
        right_panel.addWidget(self._build_local_results_section())
        right_panel.addStretch()

        main_layout.addLayout(left_panel, 1)
        main_layout.addLayout(right_panel, 1)

        return main_layout

    def _register(self, name: str, widget):
        self.widgets[name] = widget
        return widget

    def _connect(self, widget, callback_key: str) -> None:
        callback = self.callbacks.get(callback_key)
        if callback:
            widget.clicked.connect(callback)

    def _build_cavity_selection(self) -> QGroupBox:
        group = QGroupBox("Cavity Selection")
        layout = QHBoxLayout()

        cm_label = QLabel("Cryomodule:")
        cm_spinbox = self._register("cm_spinbox", QSpinBox())
        cm_spinbox.setRange(1, 20)
        cm_spinbox.setValue(1)

        cav_label = QLabel("Cavity:")
        cav_spinbox = self._register("cav_spinbox", QSpinBox())
        cav_spinbox.setRange(1, 8)
        cav_spinbox.setValue(1)

        layout.addWidget(cm_label)
        layout.addWidget(cm_spinbox)
        layout.addWidget(cav_label)
        layout.addWidget(cav_spinbox)
        layout.addStretch()
        group.setLayout(layout)
        return group

    def _build_piezo_controls(self) -> QGroupBox:
        group = QGroupBox("Piezo Tuner Pre-RF Test")
        layout = QGridLayout()

        enable_label = QLabel("Enable Piezo:")
        enable_btn = self._register(
            "enable_disable_btn", QPushButton("Disable")
        )
        enable_btn.setCheckable(True)
        self._connect(enable_btn, "toggle_piezo_enable")

        status_label = self._register("piezo_status_label", QLabel("Disabled"))
        status_label.setStyleSheet(
            "QLabel { background-color: #3a3a3a; color: #cccccc; "
            "padding: 5px; border-radius: 3px; }"
        )

        layout.addWidget(enable_label, 0, 0)
        layout.addWidget(enable_btn, 0, 1)
        layout.addWidget(status_label, 0, 2)

        manual_label = QLabel("Manual Mode:")
        manual_btn = self._register(
            "manual_feedback_btn", QPushButton("Manual")
        )
        manual_btn.setCheckable(True)
        self._connect(manual_btn, "toggle_manual_mode")

        mode_label = self._register("mode_status_label", QLabel("Feedback"))
        mode_label.setStyleSheet(
            "QLabel { background-color: #3a3a3a; color: #cccccc; "
            "padding: 5px; border-radius: 3px; }"
        )

        layout.addWidget(manual_label, 1, 0)
        layout.addWidget(manual_btn, 1, 1)
        layout.addWidget(mode_label, 1, 2)

        offset_label = QLabel("DC Offset:")
        offset_spinbox = self._register("offset_spinbox", QSpinBox())
        offset_spinbox.setRange(-100, 100)
        offset_spinbox.setValue(0)
        offset_unit = QLabel("V")

        layout.addWidget(offset_label, 2, 0)
        layout.addWidget(offset_spinbox, 2, 1)
        layout.addWidget(offset_unit, 2, 2)

        voltage_label = QLabel("Piezo Voltage:")
        voltage_spinbox = self._register("voltage_spinbox", QSpinBox())
        voltage_spinbox.setRange(0, 100)
        voltage_spinbox.setValue(17)

        layout.addWidget(voltage_label, 3, 0)
        layout.addWidget(voltage_spinbox, 3, 1, 1, 2)

        group.setLayout(layout)
        return group

    def _build_action_buttons(self) -> QHBoxLayout:
        layout = QHBoxLayout()

        go_button = self._register(
            "go_button",
            PyDMPushButton(parent=self.parent, label="Go", pressValue=1),
        )
        go_button.setStyleSheet(
            "QPushButton { background-color: #2d5016; color: white; "
            "font-weight: bold; padding: 8px; }"
        )

        abort_button = self._register("abort_button", QPushButton("Abort"))
        abort_button.setStyleSheet(
            "QPushButton { background-color: #5c1a1a; color: white; "
            "font-weight: bold; padding: 8px; }"
        )
        abort_button.setEnabled(False)

        dry_run_checkbox = self._register(
            "dry_run_checkbox", QCheckBox("Dry Run")
        )

        timestamp_label = self._register("timestamp_label", QLabel())
        timestamp_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        layout.addWidget(go_button)
        layout.addWidget(abort_button)
        layout.addWidget(dry_run_checkbox)
        layout.addStretch()
        layout.addWidget(timestamp_label)

        return layout

    def _build_auto_test(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        run_button = self._register(
            "run_button", QPushButton("Run Automated Test")
        )
        run_button.setStyleSheet(
            "QPushButton { background-color: #1e3a8a; color: white; "
            "font-weight: bold; padding: 10px; }"
        )
        self._connect(run_button, "on_run_automated_test")
        layout.addWidget(run_button)
        return layout

    def _build_view_buttons(self) -> QHBoxLayout:
        layout = QHBoxLayout()

        save_button = self._register("save_button", QPushButton("View Results"))
        self._connect(save_button, "on_save_report")
        save_button.setEnabled(False)

        db_button = self._register("db_button", QPushButton("View Database"))
        self._connect(db_button, "on_view_database")

        layout.addWidget(save_button)
        layout.addWidget(db_button)
        return layout

    def _build_history(self) -> QGroupBox:
        group = QGroupBox("Phase History")
        layout = QVBoxLayout()
        history_text = self._register("history_text", QTextEdit())
        history_text.setReadOnly(True)
        history_text.setStyleSheet(
            "QTextEdit { background-color: #1a1a1a; color: #00ff00; "
            "font-family: 'Courier New', monospace; font-size: 10pt; }"
        )
        layout.addWidget(history_text)
        group.setLayout(layout)
        return group

    def _build_live_pv_section(self) -> QGroupBox:
        group = QGroupBox("📡 Live Test Status (EPICS PV):")
        layout = QGridLayout()
        row = 0

        for label_text, name in (
            ("Overall:", "pv_overall"),
            ("Ch A:", "pv_cha_status"),
            ("Ch B:", "pv_chb_status"),
        ):
            layout.addWidget(QLabel(label_text), row, 0)
            label = self._register(name, PyDMLabel(parent=self.parent))
            label.setStyleSheet(PV_LABEL_STYLE)
            label.setAlignment(Qt.AlignCenter)
            layout.addWidget(label, row, 1)
            row += 1

        layout.addWidget(QLabel(""), row, 0)
        row += 1

        cap_header = QLabel("🔧 Live Capacitance (EPICS PV):")
        cap_header.setStyleSheet("font-weight: bold; color: #ff9a4a;")
        layout.addWidget(cap_header, row, 0, 1, 2)
        row += 1

        for label_text, name in (
            ("Ch A:", "pv_cha_cap"),
            ("Ch B:", "pv_chb_cap"),
        ):
            layout.addWidget(QLabel(label_text), row, 0)
            label = self._register(name, PyDMLabel(parent=self.parent))
            label.setStyleSheet(PV_CAP_STYLE)
            label.setAlignment(Qt.AlignCenter)
            label.showUnits = True
            layout.addWidget(label, row, 1)
            row += 1

        group.setLayout(layout)
        return group

    def _build_local_results_section(self) -> QGroupBox:
        group = QGroupBox("⚙️ Automated Test Progress (Local):")
        layout = QGridLayout()
        row = 0

        layout.addWidget(QLabel("Progress:"), row, 0)
        progress_bar = self._register("local_progress_bar", QProgressBar())
        progress_bar.setStyleSheet(
            "QProgressBar { border: 2px solid #ff9a4a; border-radius: 5px; "
            "background-color: #2a2a1a; text-align: center; color: white; } "
            "QProgressBar::chunk { background-color: #ff9a4a; }"
        )
        layout.addWidget(progress_bar, row, 1)
        row += 1

        for label_text, name in (
            ("Step:", "local_current_step"),
            ("Phase:", "local_phase_status"),
        ):
            layout.addWidget(QLabel(label_text), row, 0)
            label = self._register(name, self._make_local_label("-"))
            layout.addWidget(label, row, 1)
            row += 1

        layout.addWidget(QLabel(""), row, 0)
        row += 1

        results_header = QLabel("📊 Automated Test Results (Local):")
        results_header.setStyleSheet("font-weight: bold; color: #ff9a4a;")
        layout.addWidget(results_header, row, 0, 1, 2)
        row += 1

        result_rows = (
            ("Ch A:", "local_cha_result", self._make_local_label),
            ("Cap:", "local_cha_cap", self._make_local_cap_label),
            ("Ch B:", "local_chb_result", self._make_local_label),
            ("Cap:", "local_chb_cap", self._make_local_cap_label),
            ("Overall:", "local_overall_result", self._make_local_label),
        )

        for label_text, name, factory in result_rows:
            layout.addWidget(QLabel(label_text), row, 0)
            label = self._register(name, factory("-"))
            layout.addWidget(label, row, 1)
            row += 1

        self.widgets["local_overall_result"].setStyleSheet(
            LOCAL_LABEL_STYLE + "font-weight: bold;"
        )

        group.setLayout(layout)
        return group

    def _make_local_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(LOCAL_LABEL_STYLE)
        label.setAlignment(Qt.AlignCenter)
        return label

    def _make_local_cap_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(LOCAL_CAP_STYLE)
        label.setAlignment(Qt.AlignCenter)
        return label
