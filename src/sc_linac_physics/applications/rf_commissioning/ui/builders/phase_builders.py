"""Phase-specific UI builder classes for RF commissioning displays."""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)
from pydm.widgets import PyDMEnumComboBox, PyDMLabel

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
        spinbox = self._register("drive_max_spinbox", QDoubleSpinBox())
        spinbox.setRange(0.01, 1.0)
        spinbox.setSingleStep(0.01)
        spinbox.setDecimals(3)
        spinbox.setValue(0.670)
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
