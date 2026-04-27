"""Phase-specific UI builder classes for RF commissioning displays."""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
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


class FrequencyTuningUI(_StandardPlaceholderUI):
    """UI builder for Frequency Tuning phase (cold landing + pi-mode)."""

    PHASE_TITLE = "Frequency Tuning"


class SSACharUI(_StandardPlaceholderUI):
    """UI builder for SSA Characterization phase (placeholder)."""

    PHASE_TITLE = "SSA Characterization"


class CavityCharUI(_StandardPlaceholderUI):
    """UI builder for Cavity Characterization phase (placeholder)."""

    PHASE_TITLE = "Cavity Characterization"


class PiezoWithRFUI(_StandardPlaceholderUI):
    """UI builder for Piezo with RF phase (placeholder)."""

    PHASE_TITLE = "Piezo with RF"


class HighPowerUI(_StandardPlaceholderUI):
    """UI builder for High Power Ramp phase (placeholder)."""

    PHASE_TITLE = "High Power Ramp"


class GenericPhaseUI(_StandardPlaceholderUI):
    """Generic UI builder for phases without a specialised UI class."""

    @property
    def PHASE_TITLE(self) -> str:  # type: ignore[override]
        return getattr(self.parent, "PHASE_NAME", "Phase")
