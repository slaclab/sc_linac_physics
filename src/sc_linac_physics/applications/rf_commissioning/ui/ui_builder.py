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
    QProgressBar,
    QSpinBox,
    QTextEdit,
    QSizePolicy,
    QFrame,
    QComboBox,
)
from pydm.widgets import PyDMLabel

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
        """Create the main UI layout with optimized space usage."""
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(8)

        # === LEFT PANEL ===
        left_panel = QVBoxLayout()
        left_panel.setSpacing(6)

        # Top toolbar
        left_panel.addLayout(self._build_main_toolbar())

        # Piezo controls (now more compact without cavity selection)
        left_panel.addWidget(self._build_piezo_controls())

        # Phase history (collapsible)
        left_panel.addWidget(self._build_history())

        left_panel.addStretch()

        # === RIGHT PANEL ===
        right_panel = QVBoxLayout()
        right_panel.setSpacing(6)

        # Combined results section - fills available space
        right_panel.addWidget(self._build_combined_results_section(), stretch=1)
        # Removed addStretch() here so results section expands

        # Add panels with stretch factors
        main_layout.addLayout(left_panel, 3)
        main_layout.addLayout(right_panel, 2)

        return main_layout

    def _register(self, name: str, widget):
        self.widgets[name] = widget
        return widget

    def _connect(self, widget, callback_key: str) -> None:
        callback = self.callbacks.get(callback_key)
        if callback:
            widget.clicked.connect(callback)

    def _build_main_toolbar(self) -> QHBoxLayout:
        """Create a compact toolbar with automated test actions and abort."""
        toolbar = QHBoxLayout()
        toolbar.setSpacing(5)

        # Run automated test button
        run_button = self._register("run_button", QPushButton("Go"))
        run_button.setStyleSheet(
            "QPushButton { background-color: #1e3a8a; color: white; "
            "font-weight: bold; padding: 8px 16px; }"
        )
        self._connect(run_button, "on_run_automated_test")

        # Abort button (top-level - stops any operation)
        abort_button = self._register("abort_button", QPushButton("⛔ Abort"))
        abort_button.setStyleSheet(
            "QPushButton { background-color: #5c1a1a; color: white; "
            "font-weight: bold; padding: 8px 16px; }"
        )
        abort_button.setEnabled(False)

        # Timestamp
        timestamp_label = self._register("timestamp_label", QLabel())
        timestamp_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        timestamp_label.setStyleSheet("color: #888; font-size: 9pt;")

        # Add to toolbar
        toolbar.addWidget(run_button)
        toolbar.addWidget(abort_button)
        toolbar.addStretch()
        toolbar.addWidget(timestamp_label)

        return toolbar

    def _build_piezo_controls(self) -> QGroupBox:
        """Build Piezo controls."""
        group = QGroupBox("Piezo Tuner Pre-RF Test")
        layout = QGridLayout()
        layout.setSpacing(5)
        layout.setContentsMargins(8, 8, 8, 8)

        row = 0

        # Row 1: Enable Piezo
        layout.addWidget(QLabel("Enable Piezo:"), row, 0)
        enable_btn = self._register(
            "enable_disable_btn", QPushButton("Disable")
        )
        enable_btn.setCheckable(True)
        enable_btn.setFixedWidth(80)
        self._connect(enable_btn, "toggle_piezo_enable")
        layout.addWidget(enable_btn, row, 1)

        status_label = self._register("piezo_status_label", QLabel("Disabled"))
        status_label.setStyleSheet(
            "QLabel { background-color: #3a3a3a; color: #cccccc; "
            "padding: 5px; border-radius: 3px; }"
        )
        layout.addWidget(status_label, row, 2)
        row += 1

        # Row 2: Manual Mode
        layout.addWidget(QLabel("Manual Mode:"), row, 0)
        manual_btn = self._register(
            "manual_feedback_btn", QPushButton("Manual")
        )
        manual_btn.setCheckable(True)
        manual_btn.setFixedWidth(80)
        self._connect(manual_btn, "toggle_manual_mode")
        layout.addWidget(manual_btn, row, 1)

        mode_label = self._register("mode_status_label", QLabel("Feedback"))
        mode_label.setStyleSheet(
            "QLabel { background-color: #3a3a3a; color: #cccccc; "
            "padding: 5px; border-radius: 3px; }"
        )
        layout.addWidget(mode_label, row, 2)
        row += 1

        # Row 3: DC Offset + Piezo Voltage (combined row to save space)
        layout.addWidget(QLabel("DC Offset:"), row, 0)

        offset_row = QHBoxLayout()
        offset_row.setSpacing(3)
        offset_spinbox = self._register("offset_spinbox", QSpinBox())
        offset_spinbox.setRange(-100, 100)
        offset_spinbox.setValue(0)
        offset_spinbox.setFixedWidth(60)
        offset_row.addWidget(offset_spinbox)
        offset_row.addWidget(QLabel("V"))

        offset_row.addWidget(QLabel("  Piezo V:"))
        voltage_spinbox = self._register("voltage_spinbox", QSpinBox())
        voltage_spinbox.setRange(0, 100)
        voltage_spinbox.setValue(17)
        voltage_spinbox.setFixedWidth(60)
        offset_row.addWidget(voltage_spinbox)
        offset_row.addStretch()

        layout.addLayout(offset_row, row, 1, 1, 2)
        row += 1

        group.setLayout(layout)
        return group

    def _build_setup_row(self) -> QHBoxLayout:
        """Build compact single-row setup for operator and cavity selection."""
        row = QHBoxLayout()
        row.setSpacing(15)  # Increased spacing, no need for separator

        # Operator selection (more compact)
        operator_label = QLabel("👤 Operator:")
        operator_label.setStyleSheet(
            "QLabel { color: #ffd700; font-weight: bold; font-size: 10pt; }"
        )

        operator_combo = self._register("operator_combo", QComboBox())
        operator_combo.setMinimumWidth(180)
        operator_combo.setMaximumWidth(220)
        operator_combo.setStyleSheet(
            "QComboBox { background-color: #ffffff; color: #000000; "
            "font-size: 10pt; font-weight: bold; padding: 4px; "
            "border: 2px solid #5a9a3a; border-radius: 3px; } "
            "QComboBox::drop-down { border: none; } "
            "QComboBox QAbstractItemView { background-color: #ffffff; "
            "color: #000000; selection-background-color: #5a9a3a; }"
        )

        # Cavity selection (inline, compact with dropdowns)
        cavity_label = QLabel("🎯 Cavity:")
        cavity_label.setStyleSheet(
            "QLabel { color: #4a9eff; font-weight: bold; font-size: 10pt; }"
        )

        cm_label = QLabel("CM:")
        cm_combo = self._register(
            "cm_spinbox", QComboBox()
        )  # Keep name for compatibility
        cm_combo.setFixedWidth(60)
        cm_combo.setStyleSheet("QComboBox { padding: 3px; font-weight: bold; }")
        # Populate with CM options
        for i in range(1, 21):
            cm_combo.addItem(str(i))
        cm_combo.setCurrentIndex(0)  # Default to CM 1

        cav_label = QLabel("Cav:")
        cav_combo = self._register(
            "cav_spinbox", QComboBox()
        )  # Keep name for compatibility
        cav_combo.setFixedWidth(60)
        cav_combo.setStyleSheet(
            "QComboBox { padding: 3px; font-weight: bold; }"
        )
        # Populate with cavity options
        for i in range(1, 9):
            cav_combo.addItem(str(i))
        cav_combo.setCurrentIndex(0)  # Default to Cavity 1

        # Build the row (no separator)
        row.addWidget(operator_label)
        row.addWidget(operator_combo)
        row.addWidget(cavity_label)
        row.addWidget(cm_label)
        row.addWidget(cm_combo)
        row.addWidget(cav_label)
        row.addWidget(cav_combo)
        row.addStretch()

        # Add subtle background to emphasize importance
        frame = QFrame()
        frame.setStyleSheet(
            "QFrame { background-color: #2a2a2a; border: 1px solid #4a4a4a; "
            "border-radius: 4px; padding: 6px; }"
        )
        frame.setLayout(row)

        wrapper = QHBoxLayout()
        wrapper.addWidget(frame)
        wrapper.setContentsMargins(0, 0, 0, 0)

        return wrapper

    def _build_history(self) -> QGroupBox:
        """Build a space-efficient phase history section."""
        group = QGroupBox("Phase History")

        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(3)

        history_text = self._register("history_text", QTextEdit())
        history_text.setReadOnly(True)
        history_text.setStyleSheet(
            "QTextEdit { background-color: #1a1a1a; color: #00ff00; "
            "font-family: 'Courier New', monospace; font-size: 10pt; }"
        )

        history_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        history_text.setMinimumHeight(60)
        history_text.setMaximumHeight(180)

        layout.addWidget(history_text)
        group.setLayout(layout)
        return group

    def _build_combined_results_section(self) -> QGroupBox:
        """Combine PV and Local results into one compact section."""
        group = QGroupBox("Test Status & Results")
        layout = QVBoxLayout()
        layout.setSpacing(3)
        layout.setContentsMargins(5, 5, 5, 5)

        # Create a grid for side-by-side comparison
        grid = QGridLayout()
        grid.setSpacing(4)
        grid.setVerticalSpacing(
            6
        )  # Add a bit more vertical spacing for readability

        # Headers
        grid.addWidget(QLabel(""), 0, 0)
        pv_header = QLabel("Live (EPICS)")
        pv_header.setStyleSheet(
            "font-weight: bold; color: #4a9eff; font-size: 11pt;"
        )
        pv_header.setAlignment(Qt.AlignCenter)
        grid.addWidget(pv_header, 0, 1)

        local_header = QLabel("Automated")
        local_header.setStyleSheet(
            "font-weight: bold; color: #ff9a4a; font-size: 11pt;"
        )
        local_header.setAlignment(Qt.AlignCenter)
        grid.addWidget(local_header, 0, 2)

        row = 1

        # Overall Status
        overall_label = QLabel("Overall:")
        overall_label.setStyleSheet("font-weight: bold; font-size: 10pt;")
        grid.addWidget(overall_label, row, 0)
        pv_overall = self._register("pv_overall", PyDMLabel(parent=self.parent))
        pv_overall.setStyleSheet(PV_LABEL_STYLE + "min-height: 24px;")
        pv_overall.setAlignment(Qt.AlignCenter)
        grid.addWidget(pv_overall, row, 1)

        local_overall = self._register(
            "local_overall_result", self._make_local_label("-")
        )
        local_overall.setStyleSheet(
            LOCAL_LABEL_STYLE + "font-weight: bold; min-height: 24px;"
        )
        grid.addWidget(local_overall, row, 2)
        row += 1

        # Progress (local only)
        grid.addWidget(QLabel("Progress:"), row, 0)
        progress_bar = self._register("local_progress_bar", QProgressBar())
        progress_bar.setStyleSheet(
            "QProgressBar { border: 1px solid #ff9a4a; border-radius: 3px; "
            "background-color: #2a2a1a; text-align: center; color: white; "
            "min-height: 20px; max-height: 20px; } "
            "QProgressBar::chunk { background-color: #ff9a4a; }"
        )
        grid.addWidget(progress_bar, row, 1, 1, 2)
        row += 1

        # Ch A Status
        grid.addWidget(QLabel("Ch A:"), row, 0)
        pv_cha = self._register("pv_cha_status", PyDMLabel(parent=self.parent))
        pv_cha.setStyleSheet(PV_LABEL_STYLE)
        pv_cha.setAlignment(Qt.AlignCenter)
        grid.addWidget(pv_cha, row, 1)

        local_cha = self._register(
            "local_cha_result", self._make_local_label("-")
        )
        grid.addWidget(local_cha, row, 2)
        row += 1

        # Ch A Capacitance
        cap_a_label = QLabel("  Cap A:")
        cap_a_label.setStyleSheet("padding-left: 10px;")
        grid.addWidget(cap_a_label, row, 0)
        pv_cha_cap = self._register("pv_cha_cap", PyDMLabel(parent=self.parent))
        pv_cha_cap.setStyleSheet(PV_CAP_STYLE)
        pv_cha_cap.setAlignment(Qt.AlignCenter)
        pv_cha_cap.showUnits = True
        grid.addWidget(pv_cha_cap, row, 1)

        local_cha_cap = self._register(
            "local_cha_cap", self._make_local_cap_label("-")
        )
        grid.addWidget(local_cha_cap, row, 2)
        row += 1

        # Ch B Status
        grid.addWidget(QLabel("Ch B:"), row, 0)
        pv_chb = self._register("pv_chb_status", PyDMLabel(parent=self.parent))
        pv_chb.setStyleSheet(PV_LABEL_STYLE)
        pv_chb.setAlignment(Qt.AlignCenter)
        grid.addWidget(pv_chb, row, 1)

        local_chb = self._register(
            "local_chb_result", self._make_local_label("-")
        )
        grid.addWidget(local_chb, row, 2)
        row += 1

        # Ch B Capacitance
        cap_b_label = QLabel("  Cap B:")
        cap_b_label.setStyleSheet("padding-left: 10px;")
        grid.addWidget(cap_b_label, row, 0)
        pv_chb_cap = self._register("pv_chb_cap", PyDMLabel(parent=self.parent))
        pv_chb_cap.setStyleSheet(PV_CAP_STYLE)
        pv_chb_cap.setAlignment(Qt.AlignCenter)
        pv_chb_cap.showUnits = True
        grid.addWidget(pv_chb_cap, row, 1)

        local_chb_cap = self._register(
            "local_chb_cap", self._make_local_cap_label("-")
        )
        grid.addWidget(local_chb_cap, row, 2)
        row += 1

        # Step/Phase info (local only)
        grid.addWidget(QLabel("Step:"), row, 0)
        local_step = self._register(
            "local_current_step", self._make_local_label("-")
        )
        grid.addWidget(local_step, row, 1, 1, 2)
        row += 1

        grid.addWidget(QLabel("Phase:"), row, 0)
        local_phase = self._register(
            "local_phase_status", self._make_local_label("-")
        )
        grid.addWidget(local_phase, row, 1, 1, 2)

        layout.addLayout(grid)
        layout.addStretch()  # Add stretch here to push content to top of group
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
