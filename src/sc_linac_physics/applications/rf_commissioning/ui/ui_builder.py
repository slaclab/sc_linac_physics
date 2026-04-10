"""
Shared UI builder for RF commissioning displays.
"""

import sys
from collections.abc import Callable

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
from pydm.widgets import PyDMLabel, PyDMEnumComboBox

if sys.platform == "darwin":
    MONO_FONT_STACK = (
        "'Menlo', 'Monaco', 'Consolas', 'DejaVu Sans Mono', "
        "'Liberation Mono', 'Noto Sans Mono'"
    )
elif sys.platform.startswith("linux"):
    MONO_FONT_STACK = (
        "'DejaVu Sans Mono', 'Liberation Mono', 'Noto Sans Mono', "
        "'Consolas', 'Menlo', 'Monaco'"
    )
else:
    MONO_FONT_STACK = (
        "'Consolas', 'DejaVu Sans Mono', 'Liberation Mono', "
        "'Noto Sans Mono', 'Menlo', 'Monaco'"
    )

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
    font-family: %s;
    font-size: 11px;
""" % MONO_FONT_STACK

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
    font-family: %s;
    font-size: 11px;
""" % MONO_FONT_STACK


class PhaseUIBase:
    """Base UI builder with common components for all commissioning phases."""

    def __init__(
        self,
        parent,
        callbacks: dict[str, Callable[[], None]] | None = None,
    ) -> None:
        self.parent = parent
        self.callbacks = callbacks or {}
        self.widgets: dict[str, object] = {}

    def _register(self, name: str, widget) -> object:
        """Register a widget by name for easy access."""
        self.widgets[name] = widget
        return widget

    def _connect(self, widget, callback_key: str) -> None:
        """Connect widget signal to callback if callback exists."""
        callback = self.callbacks.get(callback_key)
        if callback:
            widget.clicked.connect(callback)

    def _build_main_toolbar(self) -> QHBoxLayout:
        """Create an enhanced toolbar with better controls and visual hierarchy."""
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        toolbar.setContentsMargins(4, 4, 4, 4)

        # === PRIMARY CONTROLS (Left side) ===
        primary_group = QHBoxLayout()
        primary_group.setSpacing(4)

        # Run/Start button with icon
        run_button = self._register("run_button", QPushButton("▶ Start Test"))
        run_button.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 4px;
                border: none;
                font-size: 11pt;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
            QPushButton:pressed {
                background-color: #1e40af;
            }
            QPushButton:disabled {
                background-color: #475569;
                color: #94a3b8;
            }
        """)
        run_button.setFixedHeight(40)
        run_button.setMinimumWidth(120)
        self._connect(run_button, "on_run_automated_test")

        # Pause button
        pause_button = self._register("pause_button", QPushButton("⏸ Pause"))
        pause_button.setStyleSheet("""
            QPushButton {
                background-color: #f59e0b;
                color: white;
                font-weight: bold;
                padding: 10px 16px;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover {
                background-color: #d97706;
            }
            QPushButton:disabled {
                background-color: #475569;
                color: #94a3b8;
            }
        """)
        pause_button.setFixedHeight(40)
        pause_button.setEnabled(False)
        self._connect(pause_button, "on_pause_test")

        # Abort button
        abort_button = self._register("abort_button", QPushButton("⏹ Abort"))
        abort_button.setStyleSheet("""
            QPushButton {
                background-color: #dc2626;
                color: white;
                font-weight: bold;
                padding: 10px 16px;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover {
                background-color: #b91c1c;
            }
            QPushButton:disabled {
                background-color: #475569;
                color: #94a3b8;
            }
        """)
        abort_button.setFixedHeight(40)
        abort_button.setEnabled(False)
        self._connect(abort_button, "on_abort_test")

        primary_group.addWidget(run_button)
        primary_group.addWidget(pause_button)
        primary_group.addWidget(abort_button)

        # Separator
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.VLine)
        sep1.setFrameShadow(QFrame.Sunken)
        sep1.setStyleSheet("QFrame { color: #4a4a4a; }")

        # === SECONDARY CONTROLS ===
        secondary_group = QHBoxLayout()
        secondary_group.setSpacing(4)

        # Step Mode toggle
        step_mode_btn = self._register(
            "step_mode_btn", QPushButton("Step Mode")
        )
        step_mode_btn.setCheckable(True)
        step_mode_btn.setStyleSheet("""
            QPushButton {
                background-color: #374151;
                color: #d1d5db;
                padding: 8px 12px;
                border-radius: 4px;
                border: 1px solid #4b5563;
            }
            QPushButton:checked {
                background-color: #059669;
                color: white;
                border: 1px solid #047857;
            }
            QPushButton:hover {
                background-color: #4b5563;
            }
        """)
        step_mode_btn.setFixedHeight(40)
        self._connect(step_mode_btn, "on_toggle_step_mode")

        # Next Step button (only active in step mode)
        next_step_btn = self._register("next_step_btn", QPushButton("Next →"))
        next_step_btn.setStyleSheet("""
            QPushButton {
                background-color: #6366f1;
                color: white;
                padding: 8px 12px;
                border-radius: 4px;
            }
            QPushButton:disabled {
                background-color: #374151;
                color: #6b7280;
            }
        """)
        next_step_btn.setFixedHeight(40)
        next_step_btn.setEnabled(False)
        self._connect(next_step_btn, "on_next_step")

        secondary_group.addWidget(step_mode_btn)
        secondary_group.addWidget(next_step_btn)

        # === STATUS SECTION (Right side) ===
        status_section = QVBoxLayout()
        status_section.setSpacing(2)

        # System status indicator
        status_indicator = self._register("status_indicator", QLabel("● READY"))
        status_indicator.setStyleSheet("""
            QLabel {
                color: #10b981;
                font-weight: bold;
                font-size: 10pt;
            }
        """)
        status_indicator.setAlignment(Qt.AlignRight)

        # Timestamp
        timestamp_label = self._register("timestamp_label", QLabel("--:--:--"))
        timestamp_label.setAlignment(Qt.AlignRight)
        timestamp_label.setStyleSheet("""
            QLabel {
                color: #9ca3af;
                font-size: 9pt;
                font-family: %s;
            }
        """ % MONO_FONT_STACK)

        status_section.addWidget(status_indicator)
        status_section.addWidget(timestamp_label)

        # === ASSEMBLY ===
        toolbar.addLayout(primary_group)
        toolbar.addWidget(sep1)
        toolbar.addLayout(secondary_group)
        toolbar.addStretch()
        toolbar.addLayout(status_section)

        # Wrap in a frame for better visual grouping
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 4px;
            }
        """)
        frame.setLayout(toolbar)

        wrapper = QVBoxLayout()
        wrapper.setContentsMargins(0, 0, 0, 0)
        wrapper.addWidget(frame)

        return wrapper

    def update_toolbar_state(self, state: str) -> None:
        """Update toolbar button states based on test state.

        Args:
            state: One of 'idle', 'running', 'paused', 'complete', 'error'
        """
        run_btn = self.widgets.get("run_button")
        pause_btn = self.widgets.get("pause_button")
        abort_btn = self.widgets.get("abort_button")
        status_ind = self.widgets.get("status_indicator")

        if state == "idle":
            run_btn.setEnabled(True)
            run_btn.setText("▶ Start Test")
            pause_btn.setEnabled(False)
            abort_btn.setEnabled(False)
            status_ind.setText("● READY")
            status_ind.setStyleSheet(
                "QLabel { color: #10b981; font-weight: bold; font-size: 10pt; }"
            )

        elif state == "running":
            run_btn.setEnabled(False)
            pause_btn.setEnabled(True)
            abort_btn.setEnabled(True)
            status_ind.setText("● RUNNING")
            status_ind.setStyleSheet(
                "QLabel { color: #3b82f6; font-weight: bold; font-size: 10pt; }"
            )

        elif state == "paused":
            run_btn.setEnabled(True)
            run_btn.setText("▶ Resume")
            pause_btn.setEnabled(False)
            abort_btn.setEnabled(True)
            status_ind.setText("● PAUSED")
            status_ind.setStyleSheet(
                "QLabel { color: #f59e0b; font-weight: bold; font-size: 10pt; }"
            )

        elif state == "complete":
            run_btn.setEnabled(True)
            run_btn.setText("▶ Start Test")
            pause_btn.setEnabled(False)
            abort_btn.setEnabled(False)
            status_ind.setText("✓ COMPLETE")
            status_ind.setStyleSheet(
                "QLabel { color: #10b981; font-weight: bold; font-size: 10pt; }"
            )

        elif state == "error":
            run_btn.setEnabled(True)
            run_btn.setText("▶ Retry")
            pause_btn.setEnabled(False)
            abort_btn.setEnabled(False)
            status_ind.setText("✗ ERROR")
            status_ind.setStyleSheet(
                "QLabel { color: #dc2626; font-weight: bold; font-size: 10pt; }"
            )

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
            f"font-family: {MONO_FONT_STACK}; "
            "font-size: 10pt; }"
        )

        history_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        history_text.setMinimumHeight(60)
        history_text.setMaximumHeight(180)

        layout.addWidget(history_text)
        group.setLayout(layout)
        return group

    def _build_basic_results_section(self, phase_name: str) -> QGroupBox:
        """Build a basic results section for placeholder phases.

        Args:
            phase_name: Name of the phase for the section title.
        """
        group = QGroupBox(f"{phase_name} - Status && Results")
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)

        # Current step
        step_label = QLabel("Current Step:")
        step_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(step_label)

        current_step = self._register("local_current_step", QLabel("-"))
        current_step.setStyleSheet(
            LOCAL_LABEL_STYLE + "min-height: 30px; font-size: 12pt;"
        )
        current_step.setAlignment(Qt.AlignCenter)
        layout.addWidget(current_step)

        # Phase status
        phase_label = QLabel("Test Status:")
        phase_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        layout.addWidget(phase_label)

        phase_status = self._register("local_phase_status", QLabel("-"))
        phase_status.setStyleSheet(
            LOCAL_LABEL_STYLE + "min-height: 30px; font-size: 12pt;"
        )
        phase_status.setAlignment(Qt.AlignCenter)
        layout.addWidget(phase_status)

        layout.addStretch()
        group.setLayout(layout)
        return group

    def _make_local_label(self, text: str) -> QLabel:
        """Create a local (non-EPICS) label with standard styling."""
        label = QLabel(text)
        label.setStyleSheet(LOCAL_LABEL_STYLE)
        label.setAlignment(Qt.AlignCenter)
        return label

    def _build_stored_data_section(
        self, fields: list[tuple[str, str]] = None
    ) -> QGroupBox:
        """Build a generalized 'Stored Data' section with standard fields.

        Args:
            fields: List of (label, widget_name) tuples for phase-specific fields.
                   These will be inserted between Status and Stored At fields.
        """
        fields = fields or []
        group = QGroupBox("Stored Data")
        layout = QVBoxLayout()
        layout.setSpacing(5)
        layout.setContentsMargins(8, 8, 8, 8)

        grid = QGridLayout()
        grid.setSpacing(5)

        row = 0

        # Progress bar
        grid.addWidget(QLabel("Progress:"), row, 0)
        progress_bar = self._register("local_progress_bar", QProgressBar())
        progress_bar.setStyleSheet(
            "QProgressBar { border: 1px solid #ff9a4a; border-radius: 3px; "
            "background-color: #2a2a1a; text-align: center; color: white; "
            "min-height: 20px; max-height: 20px; } "
            "QProgressBar::chunk { background-color: #ff9a4a; }"
        )
        grid.addWidget(progress_bar, row, 1)
        row += 1

        # Status
        grid.addWidget(QLabel("Status:"), row, 0)
        status_label = self._register(
            "local_stored_status", self._make_local_label("-")
        )
        grid.addWidget(status_label, row, 1)
        row += 1

        # Phase-specific fields
        for label_text, widget_name in fields:
            grid.addWidget(QLabel(f"  {label_text}:"), row, 0)
            value_label = self._register(
                widget_name, self._make_local_label("-")
            )
            grid.addWidget(value_label, row, 1)
            row += 1

        # Stored At
        grid.addWidget(QLabel("Stored At:"), row, 0)
        timestamp_label = self._register(
            "local_stored_timestamp", self._make_local_label("-")
        )
        grid.addWidget(timestamp_label, row, 1)
        row += 1

        # Notes
        grid.addWidget(QLabel("Notes:"), row, 0)
        notes_label = self._register(
            "local_stored_notes", self._make_local_label("-")
        )
        notes_label.setWordWrap(True)
        notes_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        grid.addWidget(notes_label, row, 1)

        layout.addLayout(grid)
        layout.addStretch()
        group.setLayout(layout)
        return group

    def _get_parent_stored_data_fields(self) -> list[tuple[str, str]]:
        """Get stored-data field definitions from the parent display."""
        if hasattr(self.parent, "get_phase_stored_field_specs"):
            return [
                (spec.label, spec.widget_name)
                for spec in self.parent.get_phase_stored_field_specs()
            ]
        return []


class PiezoPreRFUI(PhaseUIBase):
    """Builds the Piezo Pre-RF display UI and exposes widget references."""

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

        # Combined results section - live PV data
        right_panel.addWidget(
            self._build_combined_results_section("Piezo Pre-RF"), stretch=1
        )

        # Stored data section - phase results
        right_panel.addWidget(
            self._build_stored_data_section(
                self._get_parent_stored_data_fields()
            )
        )

        # Add panels with stretch factors
        main_layout.addLayout(left_panel, 3)
        main_layout.addLayout(right_panel, 2)

        return main_layout

    def _build_piezo_controls(self) -> QGroupBox:
        """Build Piezo controls."""
        group = QGroupBox("Piezo Tuner Pre-RF Test")
        layout = QGridLayout()
        layout.setSpacing(5)
        layout.setContentsMargins(8, 8, 8, 8)

        row = 0

        # Row 1: Enable command + readback
        layout.addWidget(QLabel("Enable Piezo:"), row, 0)

        enable_ctrl = self._register(
            "pydm_enable_ctrl", PyDMEnumComboBox(parent=self.parent)
        )
        enable_ctrl.setFixedWidth(120)
        enable_ctrl.setStyleSheet(
            "QComboBox { background-color: #1a2a3a; color: #e6f2ff; "
            "border: 1px solid #4a9eff; border-left: 3px solid #4a9eff; "
            "padding: 4px; border-radius: 3px; }"
        )
        layout.addWidget(enable_ctrl, row, 1)

        enable_stat = self._register(
            "pydm_enable_stat", PyDMLabel(parent=self.parent)
        )
        enable_stat.setStyleSheet(PV_LABEL_STYLE)
        enable_stat.setAlignment(Qt.AlignCenter)
        layout.addWidget(enable_stat, row, 2)
        row += 1

        # Row 2: Mode command + readback
        layout.addWidget(QLabel("Mode Control:"), row, 0)

        mode_ctrl = self._register(
            "pydm_mode_ctrl", PyDMEnumComboBox(parent=self.parent)
        )
        mode_ctrl.setFixedWidth(120)
        mode_ctrl.setStyleSheet(
            "QComboBox { background-color: #1a2a3a; color: #e6f2ff; "
            "border: 1px solid #4a9eff; border-left: 3px solid #4a9eff; "
            "padding: 4px; border-radius: 3px; }"
        )
        layout.addWidget(mode_ctrl, row, 1)

        mode_stat = self._register(
            "pydm_mode_stat", PyDMLabel(parent=self.parent)
        )
        mode_stat.setStyleSheet(PV_LABEL_STYLE)
        mode_stat.setAlignment(Qt.AlignCenter)
        layout.addWidget(mode_stat, row, 2)
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

    def _build_combined_results_section(
        self, phase_name: str = "Piezo Pre-RF"
    ) -> QGroupBox:
        """Combine PV and Local results into one compact section.

        Args:
            phase_name: Name of the phase for the section title.
        """
        group = QGroupBox(f"{phase_name} - Status && Results")
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
        pv_header = QLabel("Live (EPICS)")
        pv_header.setStyleSheet(
            "font-weight: bold; color: #4a9eff; font-size: 11pt;"
        )
        pv_header.setAlignment(Qt.AlignCenter)
        grid.addWidget(pv_header, 0, 1)

        row = 1

        # Overall Status (PV only)
        overall_label = QLabel("Overall:")
        overall_label.setStyleSheet("font-weight: bold; font-size: 10pt;")
        grid.addWidget(overall_label, row, 0)
        pv_overall = self._register("pv_overall", PyDMLabel(parent=self.parent))
        pv_overall.setStyleSheet(PV_LABEL_STYLE + "min-height: 24px;")
        pv_overall.setAlignment(Qt.AlignCenter)
        grid.addWidget(pv_overall, row, 1)
        row += 1

        # Ch A Status
        grid.addWidget(QLabel("Ch A:"), row, 0)
        pv_cha = self._register("pv_cha_status", PyDMLabel(parent=self.parent))
        pv_cha.setStyleSheet(PV_LABEL_STYLE)
        pv_cha.setAlignment(Qt.AlignCenter)
        grid.addWidget(pv_cha, row, 1)
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
        row += 1

        # Ch B Status
        grid.addWidget(QLabel("Ch B:"), row, 0)
        pv_chb = self._register("pv_chb_status", PyDMLabel(parent=self.parent))
        pv_chb.setStyleSheet(PV_LABEL_STYLE)
        pv_chb.setAlignment(Qt.AlignCenter)
        grid.addWidget(pv_chb, row, 1)
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
        row += 1

        # Step/Phase info (local only)
        grid.addWidget(QLabel("Step:"), row, 0)
        local_step = self._register(
            "local_current_step", self._make_local_label("-")
        )
        grid.addWidget(local_step, row, 1)
        row += 1

        grid.addWidget(QLabel("Test Status:"), row, 0)
        local_phase = self._register(
            "local_phase_status", self._make_local_label("-")
        )
        grid.addWidget(local_phase, row, 1)
        row += 1

        layout.addLayout(grid)
        layout.addStretch()  # Add stretch here to push content to top of group
        group.setLayout(layout)

        return group


# =============================================================================
# Placeholder UI Builders for Other Phases
# =============================================================================


class FrequencyTuningUI(PhaseUIBase):
    """UI builder for Frequency Tuning phase (cold landing + π-mode measurement)."""

    def build(self) -> QHBoxLayout:
        """Create the main UI layout."""
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(8)

        # Left panel
        left_panel = QVBoxLayout()
        left_panel.setSpacing(6)
        left_panel.addLayout(self._build_main_toolbar())
        left_panel.addWidget(self._build_history())
        left_panel.addStretch()

        # Right panel
        right_panel = QVBoxLayout()
        right_panel.setSpacing(6)
        right_panel.addWidget(
            self._build_basic_results_section("Frequency Tuning"), stretch=1
        )
        right_panel.addWidget(
            self._build_stored_data_section(
                self._get_parent_stored_data_fields()
            )
        )

        main_layout.addLayout(left_panel, 3)
        main_layout.addLayout(right_panel, 2)

        return main_layout


class SSACharUI(PhaseUIBase):
    """UI builder for SSA Characterization phase (placeholder)."""

    def build(self) -> QHBoxLayout:
        """Create the main UI layout."""
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(8)

        # Left panel
        left_panel = QVBoxLayout()
        left_panel.setSpacing(6)
        left_panel.addLayout(self._build_main_toolbar())
        left_panel.addWidget(self._build_history())
        left_panel.addStretch()

        # Right panel
        right_panel = QVBoxLayout()
        right_panel.setSpacing(6)
        right_panel.addWidget(
            self._build_basic_results_section("SSA Characterization"), stretch=1
        )
        right_panel.addWidget(
            self._build_stored_data_section(
                self._get_parent_stored_data_fields()
            )
        )

        main_layout.addLayout(left_panel, 3)
        main_layout.addLayout(right_panel, 2)

        return main_layout


class CavityCharUI(PhaseUIBase):
    """UI builder for Cavity Characterization phase (placeholder)."""

    def build(self) -> QHBoxLayout:
        """Create the main UI layout."""
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(8)

        # Left panel
        left_panel = QVBoxLayout()
        left_panel.setSpacing(6)
        left_panel.addLayout(self._build_main_toolbar())
        left_panel.addWidget(self._build_history())
        left_panel.addStretch()

        # Right panel
        right_panel = QVBoxLayout()
        right_panel.setSpacing(6)
        right_panel.addWidget(
            self._build_basic_results_section("Cavity Characterization"),
            stretch=1,
        )
        right_panel.addWidget(
            self._build_stored_data_section(
                self._get_parent_stored_data_fields()
            )
        )

        main_layout.addLayout(left_panel, 3)
        main_layout.addLayout(right_panel, 2)

        return main_layout


class PiezoWithRFUI(PhaseUIBase):
    """UI builder for Piezo with RF phase (placeholder)."""

    def build(self) -> QHBoxLayout:
        """Create the main UI layout."""
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(8)

        # Left panel
        left_panel = QVBoxLayout()
        left_panel.setSpacing(6)
        left_panel.addLayout(self._build_main_toolbar())
        left_panel.addWidget(self._build_history())
        left_panel.addStretch()

        # Right panel
        right_panel = QVBoxLayout()
        right_panel.setSpacing(6)
        right_panel.addWidget(
            self._build_basic_results_section("Piezo with RF"), stretch=1
        )
        right_panel.addWidget(
            self._build_stored_data_section(
                self._get_parent_stored_data_fields()
            )
        )

        main_layout.addLayout(left_panel, 3)
        main_layout.addLayout(right_panel, 2)

        return main_layout


class HighPowerUI(PhaseUIBase):
    """UI builder for High Power Ramp phase (placeholder)."""

    def build(self) -> QHBoxLayout:
        """Create the main UI layout."""
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(8)

        # Left panel
        left_panel = QVBoxLayout()
        left_panel.setSpacing(6)
        left_panel.addLayout(self._build_main_toolbar())
        left_panel.addWidget(self._build_history())
        left_panel.addStretch()

        # Right panel
        right_panel = QVBoxLayout()
        right_panel.setSpacing(6)
        right_panel.addWidget(
            self._build_basic_results_section("High Power Ramp"), stretch=1
        )
        right_panel.addWidget(
            self._build_stored_data_section(
                self._get_parent_stored_data_fields()
            )
        )

        main_layout.addLayout(left_panel, 3)
        main_layout.addLayout(right_panel, 2)

        return main_layout


class GenericPhaseUI(PhaseUIBase):
    """Generic UI builder used automatically for phases without a specialised
    UI class.

    The phase name displayed in the results section is taken from the
    ``PHASE_NAME`` attribute of the parent display widget, so the same class
    works for any new phase added to ``PHASE_REGISTRY``.
    """

    def build(self) -> QHBoxLayout:
        """Create the standard placeholder layout."""
        phase_name = getattr(self.parent, "PHASE_NAME", "Phase")

        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(8)

        # Left panel
        left_panel = QVBoxLayout()
        left_panel.setSpacing(6)
        left_panel.addLayout(self._build_main_toolbar())
        left_panel.addWidget(self._build_history())
        left_panel.addStretch()

        # Right panel
        right_panel = QVBoxLayout()
        right_panel.setSpacing(6)
        right_panel.addWidget(
            self._build_basic_results_section(phase_name), stretch=1
        )
        right_panel.addWidget(
            self._build_stored_data_section(
                self._get_parent_stored_data_fields()
            )
        )

        main_layout.addLayout(left_panel, 3)
        main_layout.addLayout(right_panel, 2)

        return main_layout
