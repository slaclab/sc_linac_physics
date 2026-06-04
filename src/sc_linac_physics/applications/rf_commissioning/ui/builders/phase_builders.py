"""Phase-specific UI builder classes for RF commissioning displays."""

import pyqtgraph as pg
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
)
from pydm.widgets import PyDMEnumComboBox, PyDMLabel, PyDMSpinbox
from sc_linac_physics.utils.sc_linac import linac_utils

from .base import PhaseUIBase
from .styles import PV_CAP_STYLE, PV_LABEL_STYLE


class PiezoPreRFUI(PhaseUIBase):
    """Builds the Piezo Pre-RF display UI and exposes widget references."""

    def build(self) -> QHBoxLayout:
        """Create the main UI layout with optimized space usage."""
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(8)

        left_panel = QVBoxLayout()
        left_panel.setSpacing(6)

        left_panel.addLayout(self._build_main_toolbar())
        left_panel.addWidget(self._build_piezo_controls())
        left_panel.addWidget(self._build_history())
        left_panel.addStretch()

        right_panel = QVBoxLayout()
        right_panel.setSpacing(6)

        right_panel.addWidget(
            self._build_combined_results_section("Piezo Pre-RF"), stretch=1
        )
        right_panel.addWidget(
            self._build_stored_data_section(
                self._get_parent_stored_data_fields()
            )
        )

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

        group.setLayout(layout)
        return group

    def _build_setup_row(self) -> QHBoxLayout:
        """Build compact single-row setup for operator and cavity selection."""
        row = QHBoxLayout()
        row.setSpacing(15)

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

        cavity_label = QLabel("🎯 Cavity:")
        cavity_label.setStyleSheet(
            "QLabel { color: #4a9eff; font-weight: bold; font-size: 10pt; }"
        )

        cm_label = QLabel("CM:")
        cm_combo = self._register("cm_spinbox", QComboBox())
        cm_combo.setFixedWidth(60)
        cm_combo.setStyleSheet("QComboBox { padding: 3px; font-weight: bold; }")
        for i in range(1, 21):
            cm_combo.addItem(str(i))
        cm_combo.setCurrentIndex(0)

        cav_label = QLabel("Cav:")
        cav_combo = self._register("cav_spinbox", QComboBox())
        cav_combo.setFixedWidth(60)
        cav_combo.setStyleSheet(
            "QComboBox { padding: 3px; font-weight: bold; }"
        )
        for i in range(1, 9):
            cav_combo.addItem(str(i))
        cav_combo.setCurrentIndex(0)

        row.addWidget(operator_label)
        row.addWidget(operator_combo)
        row.addWidget(cavity_label)
        row.addWidget(cm_label)
        row.addWidget(cm_combo)
        row.addWidget(cav_label)
        row.addWidget(cav_combo)
        row.addStretch()

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
        """Combine PV and local results into one compact section."""
        group = QGroupBox(f"{phase_name} - Status && Results")
        layout = QVBoxLayout()
        layout.setSpacing(3)
        layout.setContentsMargins(5, 5, 5, 5)

        grid = QGridLayout()
        grid.setSpacing(4)
        grid.setVerticalSpacing(6)

        pv_header = QLabel("Live (EPICS)")
        pv_header.setStyleSheet(
            "font-weight: bold; color: #4a9eff; font-size: 11pt;"
        )
        pv_header.setAlignment(Qt.AlignCenter)
        grid.addWidget(pv_header, 0, 1)

        row = 1

        overall_label = QLabel("Overall:")
        overall_label.setStyleSheet("font-weight: bold; font-size: 10pt;")
        grid.addWidget(overall_label, row, 0)
        pv_overall = self._register("pv_overall", PyDMLabel(parent=self.parent))
        pv_overall.setStyleSheet(PV_LABEL_STYLE + "min-height: 24px;")
        pv_overall.setAlignment(Qt.AlignCenter)
        grid.addWidget(pv_overall, row, 1)
        row += 1

        grid.addWidget(QLabel("Ch A:"), row, 0)
        pv_cha = self._register("pv_cha_status", PyDMLabel(parent=self.parent))
        pv_cha.setStyleSheet(PV_LABEL_STYLE)
        pv_cha.setAlignment(Qt.AlignCenter)
        grid.addWidget(pv_cha, row, 1)
        row += 1

        cap_a_label = QLabel("  Cap A:")
        cap_a_label.setStyleSheet("padding-left: 10px;")
        grid.addWidget(cap_a_label, row, 0)
        pv_cha_cap = self._register("pv_cha_cap", PyDMLabel(parent=self.parent))
        pv_cha_cap.setStyleSheet(PV_CAP_STYLE)
        pv_cha_cap.setAlignment(Qt.AlignCenter)
        pv_cha_cap.showUnits = True
        grid.addWidget(pv_cha_cap, row, 1)
        row += 1

        grid.addWidget(QLabel("Ch B:"), row, 0)
        pv_chb = self._register("pv_chb_status", PyDMLabel(parent=self.parent))
        pv_chb.setStyleSheet(PV_LABEL_STYLE)
        pv_chb.setAlignment(Qt.AlignCenter)
        grid.addWidget(pv_chb, row, 1)
        row += 1

        cap_b_label = QLabel("  Cap B:")
        cap_b_label.setStyleSheet("padding-left: 10px;")
        grid.addWidget(cap_b_label, row, 0)
        pv_chb_cap = self._register("pv_chb_cap", PyDMLabel(parent=self.parent))
        pv_chb_cap.setStyleSheet(PV_CAP_STYLE)
        pv_chb_cap.setAlignment(Qt.AlignCenter)
        pv_chb_cap.showUnits = True
        grid.addWidget(pv_chb_cap, row, 1)
        row += 1

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

        layout.addLayout(grid)
        layout.addStretch()
        group.setLayout(layout)

        return group


class _StandardPlaceholderUI(PhaseUIBase):
    """Shared layout for non-Piezo placeholder phases."""

    PHASE_TITLE = "Phase"

    def build(self) -> QHBoxLayout:
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(8)

        left_panel = QVBoxLayout()
        left_panel.setSpacing(6)
        left_panel.addLayout(self._build_main_toolbar())
        left_panel.addWidget(self._build_history())
        left_panel.addStretch()

        right_panel = QVBoxLayout()
        right_panel.setSpacing(6)
        right_panel.addWidget(
            self._build_basic_results_section(self.PHASE_TITLE), stretch=1
        )
        right_panel.addWidget(
            self._build_stored_data_section(
                self._get_parent_stored_data_fields()
            )
        )

        main_layout.addLayout(left_panel, 3)
        main_layout.addLayout(right_panel, 2)
        return main_layout


class GenericPhaseUI(_StandardPlaceholderUI):
    """Generic UI builder for phases without a specialised UI class."""

    @property
    def PHASE_TITLE(self) -> str:  # type: ignore[override]
        return getattr(self.parent, "PHASE_NAME", "Phase")


class SSACharUI(PhaseUIBase):
    """Builds the SSA Calibration display UI and exposes widget references."""

    def build(self) -> QHBoxLayout:
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(8)

        left_panel = QVBoxLayout()
        left_panel.setSpacing(6)
        left_panel.addLayout(self._build_main_toolbar())
        left_panel.addWidget(self._build_ssa_inputs())
        left_panel.addWidget(self._build_history())
        left_panel.addStretch()

        right_panel = QVBoxLayout()
        right_panel.setSpacing(6)
        right_panel.addWidget(self._build_ssa_results(), stretch=1)
        right_panel.addWidget(
            self._build_stored_data_section(
                self._get_parent_stored_data_fields()
            )
        )

        main_layout.addLayout(left_panel, 1)
        main_layout.addLayout(right_panel, 1)
        return main_layout

    def _build_ssa_inputs(self) -> QGroupBox:
        """Build the Inputs section matching the EDM screen."""
        group = QGroupBox("SSA Calibration Inputs")
        layout = QGridLayout()
        layout.setSpacing(6)
        layout.setContentsMargins(8, 8, 8, 8)

        layout.addWidget(QLabel("Calibration Drive Max:"), 0, 0)
        spinbox = self._register(
            "drive_max_spinbox", PyDMSpinbox(parent=self.parent)
        )
        spinbox.setRange(0.01, 1.0)
        spinbox.userDefinedLimits = True
        spinbox.userMinimum = 0.01
        spinbox.userMaximum = 1.0
        spinbox.setSingleStep(0.01)
        spinbox.setDecimals(3)
        spinbox.setValue(0.5)
        spinbox.precisionFromPV = False
        spinbox.precision = 3
        spinbox.showStepExponent = False
        spinbox.writeOnPress = True
        spinbox.editingFinished.connect(spinbox.send_value)
        spinbox.setFixedWidth(90)
        layout.addWidget(spinbox, 0, 1)
        layout.addWidget(QLabel("(range 0–1)"), 0, 2)

        plot_btn = self._register("plot_btn", QPushButton("Plot"))
        plot_btn.setStyleSheet(
            "QPushButton { background-color: #374151; color: #d1d5db; "
            "padding: 6px 14px; border-radius: 4px; border: 1px solid #4b5563; } "
            "QPushButton:hover { background-color: #4b5563; }"
        )
        self._connect(plot_btn, "on_plot")
        layout.addWidget(plot_btn, 1, 1)

        group.setLayout(layout)
        return group

    def _build_ssa_results(self) -> QGroupBox:
        """Build the Results section with live PV labels and local result indicators."""
        group = QGroupBox("SSA Calibration — Status && Results")
        outer = QVBoxLayout()
        outer.setSpacing(6)
        outer.setContentsMargins(8, 8, 8, 8)

        # Single unified grid: col 0 = label, cols 1-3 = New / Current / Saved
        grid = QGridLayout()
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(5)
        grid.setColumnMinimumWidth(0, 80)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)
        for col, text, color in (
            (1, "New", "#4a9eff"),
            (2, "Current", "#e0e0e0"),
        ):
            hdr = QLabel(text)
            hdr.setStyleSheet(
                f"color: {color}; font-weight: bold; font-size: 9pt;"
            )
            hdr.setAlignment(Qt.AlignCenter)
            grid.addWidget(hdr, 0, col)

        # SSA Slope row
        grid.addWidget(QLabel("SSA Slope:"), 1, 0)

        pv_slope_new = self._register(
            "pydm_slope_new", PyDMLabel(parent=self.parent)
        )
        pv_slope_new.setStyleSheet(PV_CAP_STYLE)
        pv_slope_new.setAlignment(Qt.AlignCenter)
        pv_slope_new.precisionFromPV = False
        pv_slope_new.precision = 5
        grid.addWidget(pv_slope_new, 1, 1)

        pv_slope_cur = self._register(
            "pydm_slope_current", PyDMLabel(parent=self.parent)
        )
        pv_slope_cur.setStyleSheet(PV_CAP_STYLE)
        pv_slope_cur.setAlignment(Qt.AlignCenter)
        pv_slope_cur.precisionFromPV = False
        pv_slope_cur.precision = 5
        grid.addWidget(pv_slope_cur, 1, 2)

        # Drive Max row
        grid.addWidget(QLabel("Drive Max:"), 2, 0)

        pv_drv_req = self._register(
            "pydm_drive_max_new", PyDMLabel(parent=self.parent)
        )
        pv_drv_req.setStyleSheet(PV_CAP_STYLE)
        pv_drv_req.setAlignment(Qt.AlignCenter)
        pv_drv_req.precisionFromPV = False
        pv_drv_req.precision = 3
        grid.addWidget(pv_drv_req, 2, 1)

        pv_drv_cur = self._register(
            "pydm_drive_max_current", PyDMLabel(parent=self.parent)
        )
        pv_drv_cur.setStyleSheet(PV_CAP_STYLE)
        pv_drv_cur.setAlignment(Qt.AlignCenter)
        pv_drv_cur.precisionFromPV = False
        pv_drv_cur.precision = 3
        grid.addWidget(pv_drv_cur, 2, 2)

        # Max Fwd Pwr row (single live value)
        grid.addWidget(QLabel("Max Fwd Pwr:"), 3, 0)
        pv_fwd_pwr = self._register(
            "pydm_max_fwd_pwr", PyDMLabel(parent=self.parent)
        )
        pv_fwd_pwr.setStyleSheet(PV_CAP_STYLE)
        pv_fwd_pwr.setAlignment(Qt.AlignCenter)
        pv_fwd_pwr.showUnits = True
        grid.addWidget(pv_fwd_pwr, 3, 1, 1, 2)

        # Cal Status row (EPICS value + local pass/fail)
        grid.addWidget(QLabel("Cal Status:"), 4, 0)
        pv_cal_status = self._register(
            "pydm_cal_status", PyDMLabel(parent=self.parent)
        )
        pv_cal_status.setStyleSheet(PV_LABEL_STYLE)
        pv_cal_status.setAlignment(Qt.AlignCenter)
        grid.addWidget(pv_cal_status, 4, 1)

        local_phase = self._register(
            "local_phase_status", self._make_local_label("-")
        )
        grid.addWidget(local_phase, 4, 2)

        # Step row
        grid.addWidget(QLabel("Step:"), 5, 0)
        local_step = self._register(
            "local_current_step", self._make_local_label("-")
        )
        grid.addWidget(local_step, 5, 1, 1, 2)

        outer.addLayout(grid)

        # Push / Save buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.setContentsMargins(0, 6, 0, 0)

        push_btn = self._register(
            "push_btn", QPushButton("Push New Slope to Cavity")
        )
        push_btn.setStyleSheet(
            "QPushButton { background-color: #1d6a3a; color: white; "
            "font-weight: bold; padding: 6px 18px; border-radius: 4px; } "
            "QPushButton:hover { background-color: #2d8a4a; } "
            "QPushButton:disabled { background-color: #374151; color: #6b7280; }"
        )
        self._connect(push_btn, "on_push_slope")
        btn_row.addWidget(push_btn)

        btn_row.addStretch()
        outer.addLayout(btn_row)
        outer.addStretch()

        group.setLayout(outer)
        return group


class FrequencyTuningUI(PhaseUIBase):
    """Builds the Frequency Tuning display UI with 3-stage checklist layout."""

    _STAGE_BTN_STYLE = """
        QPushButton {
            background-color: #2563eb;
            color: white;
            font-weight: bold;
            padding: 5px 14px;
            border-radius: 4px;
            border: none;
        }
        QPushButton:hover { background-color: #1d4ed8; }
        QPushButton:disabled { background-color: #374151; color: #6b7280; }
    """
    _CONFIRM_BTN_STYLE = """
        QPushButton {
            background-color: #059669;
            color: white;
            font-weight: bold;
            padding: 5px 14px;
            border-radius: 4px;
            border: none;
        }
        QPushButton:hover { background-color: #047857; }
        QPushButton:disabled { background-color: #374151; color: #6b7280; }
    """

    def build(self) -> QVBoxLayout:
        outer = QVBoxLayout()
        outer.setContentsMargins(5, 5, 5, 5)
        outer.setSpacing(4)

        outer.addLayout(self._build_status_bar())

        main = QHBoxLayout()
        main.setSpacing(6)

        # Left: stage checklist (scrollable so cards don't overlap)
        checklist = self._build_checklist_panel()
        checklist_scroll = QScrollArea()
        checklist_scroll.setWidgetResizable(True)
        checklist_scroll.setWidget(checklist)
        checklist_scroll.setFrameShape(QFrame.NoFrame)
        checklist_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        main.addWidget(checklist_scroll, stretch=2)

        # Center: plot + history
        center = QVBoxLayout()
        center.setSpacing(4)
        center.addWidget(self._build_tuning_plot(), stretch=3)
        center.addWidget(self._build_compact_history())
        main.addLayout(center, stretch=4)

        # Right: motor settings + stored data
        right = QVBoxLayout()
        right.setSpacing(4)
        right.addWidget(self._build_motor_settings())
        stored = self._build_stored_data_section(
            self._get_parent_stored_data_fields()
        )
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(stored)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        right.addWidget(scroll, stretch=1)
        main.addLayout(right, stretch=2)

        outer.addLayout(main, stretch=1)
        return outer

    def update_toolbar_state(self, state: str) -> None:
        """Override: checklist layout has no run_button."""
        pause_btn = self.widgets.get("pause_button")
        abort_btn = self.widgets.get("abort_button")
        status_ind = self.widgets.get("status_indicator")

        active = state in ("running", "paused")
        if pause_btn:
            pause_btn.setEnabled(active)
            if state != "paused":
                pause_btn.setText("⏸ Pause")
        if abort_btn:
            abort_btn.setEnabled(active)

        _status_map = {
            "idle": ("● IDLE", "#10b981"),
            "running": ("● RUNNING", "#3b82f6"),
            "paused": ("● PAUSED", "#f59e0b"),
            "complete": ("✓ COMPLETE", "#10b981"),
            "error": ("✗ ERROR", "#dc2626"),
        }
        if status_ind and state in _status_map:
            text, color = _status_map[state]
            status_ind.setText(text)
            status_ind.setStyleSheet(
                f"QLabel {{ color: {color}; font-weight: bold; font-size: 10pt; }}"
            )

    def _build_status_bar(self) -> QVBoxLayout:
        """Compact pause/abort/status bar spanning full width."""
        frame = QFrame()
        frame.setStyleSheet(self._TOOLBAR_FRAME_STYLE)

        layout = QHBoxLayout()
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        pause_button = self._register("pause_button", QPushButton("⏸ Pause"))
        pause_button.setStyleSheet("""
            QPushButton {
                background-color: #f59e0b; color: white;
                font-weight: bold; padding: 5px 14px;
                border-radius: 4px; border: none;
            }
            QPushButton:hover { background-color: #d97706; }
            QPushButton:disabled { background-color: #475569; color: #94a3b8; }
        """)
        pause_button.setFixedHeight(30)
        pause_button.setEnabled(False)
        self._connect(pause_button, "on_pause_test")
        layout.addWidget(pause_button)

        abort_button = self._register("abort_button", QPushButton("⏹ Abort"))
        abort_button.setStyleSheet("""
            QPushButton {
                background-color: #dc2626; color: white;
                font-weight: bold; padding: 5px 14px;
                border-radius: 4px; border: none;
            }
            QPushButton:hover { background-color: #b91c1c; }
            QPushButton:disabled { background-color: #475569; color: #94a3b8; }
        """)
        abort_button.setFixedHeight(30)
        abort_button.setEnabled(False)
        self._connect(abort_button, "on_abort_test")
        layout.addWidget(abort_button)

        layout.addStretch()

        status_indicator = self._register("status_indicator", QLabel("● IDLE"))
        status_indicator.setStyleSheet(
            "QLabel { color: #10b981; font-weight: bold; font-size: 10pt; }"
        )
        layout.addWidget(status_indicator)

        from .styles import MONO_FONT_STACK

        timestamp_label = self._register("timestamp_label", QLabel("--:--:--"))
        timestamp_label.setStyleSheet(
            f"QLabel {{ color: #9ca3af; font-size: 9pt; font-family: {MONO_FONT_STACK}; }}"
        )
        layout.addWidget(timestamp_label)

        frame.setLayout(layout)
        wrapper = QVBoxLayout()
        wrapper.setContentsMargins(0, 0, 0, 0)
        wrapper.addWidget(frame)
        return wrapper

    def _build_checklist_panel(self) -> QGroupBox:
        group = QGroupBox("Commissioning Stages")
        group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #334155;
                border-radius: 4px;
                margin-top: 6px;
                color: #94a3b8;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
            }
        """)
        layout = QVBoxLayout()
        layout.setContentsMargins(6, 8, 6, 6)
        layout.setSpacing(6)

        layout.addWidget(self._build_stage1_card())
        layout.addWidget(self._build_stage2_card())
        layout.addWidget(self._build_stage3_card())
        layout.addWidget(self._build_stage4_card())
        layout.addStretch()

        group.setLayout(layout)
        return group

    def _build_stage1_card(self) -> QFrame:
        return self._build_stage_card(
            stage=1,
            title="① Setup & Cold Landing",
            description="Verify stepper state and record cold landing frequency.",
            run_callback="on_run_stage_1",
            run_label="▶ Run Stage 1",
            initially_enabled=True,
            extra_widgets=self._build_stage1_extra,
        )

    def _build_stage2_card(self) -> QFrame:
        return self._build_stage_card(
            stage=2,
            title="② Probe Direction",
            description="Measure Hz/step from a probe move.",
            run_callback="on_run_stage_2",
            run_label="▶ Run Stage 2",
            initially_enabled=False,
            extra_widgets=self._build_stage2_extra,
        )

    def _build_stage3_card(self) -> QFrame:
        return self._build_stage_card(
            stage=3,
            title="③ Tune to Resonance",
            description="Move stepper to resonance using Hz/step estimate.",
            run_callback="on_run_stage_3",
            run_label="▶ Run Stage 3",
            initially_enabled=False,
            extra_widgets=self._build_stage3_extra,
        )

    def _build_stage4_card(self) -> QFrame:
        return self._build_stage_card(
            stage=4,
            title="④ Measure Pi Modes",
            description="Run rack FSCAN to find 8π/9 and 7π/9 parasitic modes.",
            run_callback="on_run_stage_4",
            run_label="▶ Run Stage 4",
            initially_enabled=False,
            extra_widgets=self._build_stage4_extra,
        )

    def _build_stage_card(
        self,
        stage: int,
        title: str,
        description: str,
        run_callback: str,
        run_label: str,
        initially_enabled: bool,
        extra_widgets,
    ) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 4px;
            }
        """)
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(5)

        hdr = QHBoxLayout()
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            "QLabel { color: #e2e8f0; font-weight: bold; font-size: 10pt; }"
        )
        hdr.addWidget(title_lbl)
        hdr.addStretch()
        status_lbl = self._register(
            f"stage{stage}_status_label", QLabel("⬜ Not started")
        )
        status_lbl.setStyleSheet("QLabel { color: #6b7280; font-size: 9pt; }")
        hdr.addWidget(status_lbl)
        layout.addLayout(hdr)

        desc = QLabel(description)
        desc.setStyleSheet("QLabel { color: #94a3b8; font-size: 9pt; }")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        run_btn = self._register(
            f"stage{stage}_run_btn", QPushButton(run_label)
        )
        run_btn.setStyleSheet(self._STAGE_BTN_STYLE)
        run_btn.setFixedHeight(28)
        run_btn.setEnabled(initially_enabled)
        self._connect(run_btn, run_callback)
        layout.addWidget(run_btn)

        extra_widgets(layout)

        frame.setLayout(layout)
        return frame

    def _build_stage1_extra(self, layout: QVBoxLayout) -> None:
        detune_row = QHBoxLayout()
        detune_row.addWidget(QLabel("Current detune:"))
        detune_lbl = self._register(
            "detune_chirp_readback", PyDMLabel(parent=self.parent)
        )
        detune_lbl.setStyleSheet(PV_CAP_STYLE)
        detune_lbl.showUnits = True
        detune_lbl.precisionFromPV = False
        detune_lbl.precision = 0
        detune_row.addWidget(detune_lbl)
        detune_row.addStretch()
        layout.addLayout(detune_row)

        df_cold_row = QHBoxLayout()
        df_cold_row.addWidget(QLabel("DF_COLD PV:"))
        df_cold_lbl = self._register(
            "df_cold_readback", PyDMLabel(parent=self.parent)
        )
        df_cold_lbl.setStyleSheet(PV_CAP_STYLE)
        df_cold_lbl.showUnits = True
        df_cold_lbl.precisionFromPV = False
        df_cold_lbl.precision = 0
        df_cold_row.addWidget(df_cold_lbl)
        push_btn = self._register(
            "push_df_cold_button", QPushButton("Push → DF_COLD")
        )
        push_btn.setFixedHeight(24)
        push_btn.setStyleSheet("""
            QPushButton {
                background-color: #374151; color: #e2e8f0;
                font-size: 9pt; padding: 2px 8px;
                border-radius: 3px; border: 1px solid #4b5563;
            }
            QPushButton:hover { background-color: #4b5563; }
            QPushButton:disabled { background-color: #1f2937; color: #6b7280; }
        """)
        self._connect(push_btn, "on_push_to_df_cold")
        df_cold_row.addWidget(push_btn)
        layout.addLayout(df_cold_row)

    def _build_stage2_extra(self, layout: QVBoxLayout) -> None:
        calc_row = QHBoxLayout()
        calc_row.addWidget(QLabel("Hz/step:"))

        hz_spinbox = self._register("hz_per_step_spinbox", QDoubleSpinBox())
        hz_spinbox.setRange(-1000.0, 1000.0)
        hz_spinbox.setDecimals(4)
        hz_spinbox.setSingleStep(0.0001)
        hz_spinbox.setValue(0.0)
        hz_spinbox.setEnabled(False)
        hz_spinbox.setStyleSheet(
            "QDoubleSpinBox { background-color: #0f172a; color: #4a9eff; "
            "border: 1px solid #334155; border-radius: 3px; padding: 2px 4px; "
            "font-family: monospace; }"
        )
        hz_spinbox.setFixedWidth(120)
        calc_row.addWidget(hz_spinbox)
        calc_row.addWidget(QLabel("Hz/step"))
        calc_row.addStretch()
        layout.addLayout(calc_row)

        scale_row = QHBoxLayout()
        scale_row.addWidget(QLabel("SCALE PV:"))
        scale_lbl = self._register(
            "scale_readback", PyDMLabel(parent=self.parent)
        )
        scale_lbl.setStyleSheet(PV_CAP_STYLE)
        scale_lbl.showUnits = True
        scale_lbl.precisionFromPV = False
        scale_lbl.precision = 4
        scale_row.addWidget(scale_lbl)
        push_scale_btn = self._register(
            "push_scale_button", QPushButton("Push → Scale")
        )
        push_scale_btn.setFixedHeight(24)
        push_scale_btn.setStyleSheet("""
            QPushButton {
                background-color: #374151; color: #e2e8f0;
                font-size: 9pt; padding: 2px 8px;
                border-radius: 3px; border: 1px solid #4b5563;
            }
            QPushButton:hover { background-color: #4b5563; }
            QPushButton:disabled { background-color: #1f2937; color: #6b7280; }
        """)
        self._connect(push_scale_btn, "on_push_to_scale")
        scale_row.addWidget(push_scale_btn)
        layout.addLayout(scale_row)

        confirm_probe_btn = self._register(
            "confirm_probe_fit_button", QPushButton("✓ Confirm Fit")
        )
        confirm_probe_btn.setStyleSheet(self._CONFIRM_BTN_STYLE)
        confirm_probe_btn.setFixedHeight(28)
        confirm_probe_btn.setEnabled(False)
        self._connect(confirm_probe_btn, "on_confirm_probe_fit")
        layout.addWidget(confirm_probe_btn)

    def _build_stage3_extra(self, layout: QVBoxLayout) -> None:
        row = QHBoxLayout()
        row.addWidget(QLabel("Net steps:"))
        net_lbl = self._register(
            "net_steps_label", PyDMLabel(parent=self.parent)
        )
        net_lbl.setStyleSheet(PV_LABEL_STYLE)
        net_lbl.showUnits = True
        row.addWidget(net_lbl)
        row.addStretch()
        layout.addLayout(row)

    def _build_stage4_extra(self, layout: QVBoxLayout) -> None:
        stat_row = QHBoxLayout()
        stat_row.addWidget(QLabel("Scan status:"))
        fscan_stat = self._register(
            "fscan_stat_readback", PyDMLabel(parent=self.parent)
        )
        fscan_stat.setStyleSheet(PV_LABEL_STYLE)
        fscan_stat.setAlignment(Qt.AlignCenter)
        stat_row.addWidget(fscan_stat)
        stat_row.addStretch()
        layout.addLayout(stat_row)

        for label, widget_name in (
            ("8π/9 mode:", "stage4_8pi9_label"),
            ("7π/9 mode:", "stage4_7pi9_label"),
        ):
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            lbl = self._register(widget_name, PyDMLabel(parent=self.parent))
            lbl.setStyleSheet(PV_CAP_STYLE)
            lbl.showUnits = True
            lbl.precisionFromPV = False
            lbl.precision = 0
            row.addWidget(lbl)
            row.addStretch()
            layout.addLayout(row)

        confirm_btn = self._register(
            "confirm_save_button", QPushButton("✓ Confirm & Save")
        )
        confirm_btn.setStyleSheet(self._CONFIRM_BTN_STYLE)
        confirm_btn.setFixedHeight(28)
        confirm_btn.setEnabled(False)
        self._connect(confirm_btn, "on_confirm_and_save")
        layout.addWidget(confirm_btn)

    def _build_compact_history(self) -> QGroupBox:
        group = self._build_history()
        history = self.widgets.get("history_text")
        if history:
            history.setMinimumHeight(50)
            history.setMaximumHeight(90)
        return group

    def _build_motor_settings(self) -> QGroupBox:
        """Speed, max steps, manual stepper controls, and live phase readouts."""
        group = QGroupBox("Stepper Settings")
        layout = QGridLayout()
        layout.setSpacing(4)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(3, 1)

        # Row 0: Speed | Max Steps
        layout.addWidget(QLabel("Speed (steps/s):"), 0, 0)
        speed_spinbox = self._register(
            "speed_spinbox", QSpinBox(parent=self.parent)
        )
        speed_spinbox.setRange(1, linac_utils.MAX_STEPPER_SPEED)
        speed_spinbox.setSingleStep(1000)
        speed_spinbox.setValue(linac_utils.DEFAULT_STEPPER_SPEED)
        layout.addWidget(speed_spinbox, 0, 1)

        layout.addWidget(QLabel("Max Steps:"), 0, 2)
        max_steps_spinbox = self._register(
            "max_steps_spinbox", PyDMSpinbox(parent=self.parent)
        )
        max_steps_spinbox.setRange(1, linac_utils.DEFAULT_STEPPER_MAX_STEPS)
        max_steps_spinbox.userDefinedLimits = True
        max_steps_spinbox.userMinimum = 1
        max_steps_spinbox.userMaximum = linac_utils.DEFAULT_STEPPER_MAX_STEPS
        max_steps_spinbox.setSingleStep(1000)
        max_steps_spinbox.setDecimals(0)
        max_steps_spinbox.setValue(linac_utils.DEFAULT_STEPPER_MAX_STEPS)
        max_steps_spinbox.precisionFromPV = False
        max_steps_spinbox.precision = 0
        max_steps_spinbox.showStepExponent = False
        max_steps_spinbox.writeOnPress = True
        max_steps_spinbox.editingFinished.connect(max_steps_spinbox.send_value)
        layout.addWidget(max_steps_spinbox, 0, 3)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        sep.setStyleSheet("QFrame { color: #3a3a3a; }")
        layout.addWidget(sep, 1, 0, 1, 4)

        # Row 2: Manual steps spinbox | directional buttons
        layout.addWidget(QLabel("Steps:"), 2, 0)
        steps_spinbox = self._register(
            "steps_spinbox", PyDMSpinbox(parent=self.parent)
        )
        steps_spinbox.setRange(1, linac_utils.DEFAULT_STEPPER_MAX_STEPS)
        steps_spinbox.userDefinedLimits = True
        steps_spinbox.userMinimum = 1
        steps_spinbox.userMaximum = linac_utils.DEFAULT_STEPPER_MAX_STEPS
        steps_spinbox.setSingleStep(1)
        steps_spinbox.setDecimals(0)
        steps_spinbox.setValue(100)
        steps_spinbox.precisionFromPV = False
        steps_spinbox.precision = 0
        steps_spinbox.showStepExponent = False
        steps_spinbox.writeOnPress = True
        steps_spinbox.editingFinished.connect(steps_spinbox.send_value)
        layout.addWidget(steps_spinbox, 2, 1)

        _btn_style = (
            "QPushButton { background-color: #374151; color: #d1d5db; "
            "padding: 3px 8px; border-radius: 3px; border: 1px solid #4b5563; "
            "font-size: 9pt; } "
            "QPushButton:hover { background-color: #4b5563; } "
            "QPushButton:disabled { background-color: #1f2937; color: #4b5563; }"
        )
        move_left_btn = self._register("move_left_btn", QPushButton("← Left"))
        move_left_btn.setStyleSheet(_btn_style)
        move_left_btn.setFixedHeight(26)
        self._connect(move_left_btn, "on_move_left")
        layout.addWidget(move_left_btn, 2, 2)

        move_right_btn = self._register(
            "move_right_btn", QPushButton("Right →")
        )
        move_right_btn.setStyleSheet(_btn_style)
        move_right_btn.setFixedHeight(26)
        self._connect(move_right_btn, "on_move_right")
        layout.addWidget(move_right_btn, 2, 3)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setFrameShadow(QFrame.Sunken)
        sep2.setStyleSheet("QFrame { color: #3a3a3a; }")
        layout.addWidget(sep2, 3, 0, 1, 4)

        # Row 4: Step | Status
        layout.addWidget(QLabel("Step:"), 4, 0)
        layout.addWidget(
            self._register("local_current_step", self._make_local_label("-")),
            4,
            1,
        )
        layout.addWidget(QLabel("Status:"), 4, 2)
        layout.addWidget(
            self._register("local_phase_status", self._make_local_label("-")),
            4,
            3,
        )

        group.setLayout(layout)
        return group

    def _build_stored_data_section(
        self, fields: list[tuple[str, str]] | None = None
    ) -> QGroupBox:
        """2-column stored data layout for frequency tuning."""
        fields = fields or []
        group = QGroupBox("Stored Data")
        layout = QVBoxLayout()
        layout.setSpacing(4)
        layout.setContentsMargins(8, 6, 8, 6)

        grid = QGridLayout()
        grid.setSpacing(4)
        grid.setVerticalSpacing(5)
        grid.setColumnMinimumWidth(0, 120)
        grid.setColumnStretch(1, 1)

        row = 0

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

        grid.addWidget(QLabel("Status:"), row, 0)
        grid.addWidget(
            self._register("local_stored_status", self._make_local_label("-")),
            row,
            1,
        )
        row += 1

        grid.addWidget(QLabel("Stored At:"), row, 0)
        grid.addWidget(
            self._register(
                "local_stored_timestamp", self._make_local_label("-")
            ),
            row,
            1,
        )
        row += 1

        for label, name in fields:
            grid.addWidget(QLabel(f"{label}:"), row, 0)
            grid.addWidget(
                self._register(name, self._make_local_label("-")), row, 1
            )
            row += 1

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

    def _build_tuning_plot(self) -> QGroupBox:
        group = QGroupBox("Detune vs. Steps")
        layout = QVBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)

        pw = pg.PlotWidget()
        pw.setBackground("#1a1a2e")
        pw.showGrid(x=True, y=True, alpha=0.3)
        pw.setLabel("left", "Detune", units="Hz")
        pw.setLabel("bottom", "Net Steps")
        pw.addLegend(offset=(10, 10))
        pw.setMinimumHeight(180)

        pw.addItem(
            pg.InfiniteLine(
                pos=0,
                angle=0,
                pen=pg.mkPen(color="#555555", width=1, style=Qt.DashLine),
            )
        )

        self._register("tuning_plot", pw)
        layout.addWidget(pw)
        group.setLayout(layout)
        return group
