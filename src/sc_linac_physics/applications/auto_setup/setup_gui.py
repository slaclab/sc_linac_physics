from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from lcls_tools.common.frontend.display.util import ERROR_STYLESHEET
from pydm import Display
from pydm.widgets import PyDMLabel

from sc_linac_physics.applications.auto_setup.backend.setup_machine import (
    SETUP_MACHINE,
)
from sc_linac_physics.applications.auto_setup.frontend.cavity_cell import (
    CavityPanel,
)
from sc_linac_physics.applications.auto_setup.frontend.utils import Settings
from sc_linac_physics.utils.qt import make_sanity_check_popup
from sc_linac_physics.utils.sc_linac import linac_utils

_LINAC_NAMES = ["L0B", "L1B", "L2B", "L3B", "L4B"]
_SETUP_STYLE = "background-color: #1e5799; color: white;"


class SetupGUI(Display):
    def __init__(self, parent=None, args=None):
        super(SetupGUI, self).__init__(parent=parent, args=args)
        self.setWindowTitle("SRF Auto Setup")
        self.setMinimumWidth(560)

        self.linac_names = _LINAC_NAMES

        self.ssa_cal_checkbox = QCheckBox("SSA Calibration")
        self.ssa_cal_checkbox.setChecked(True)
        self.autotune_checkbox = QCheckBox("Auto Tune")
        self.autotune_checkbox.setChecked(True)
        self.cav_char_checkbox = QCheckBox("Cavity Characterization")
        self.cav_char_checkbox.setChecked(True)
        self.rf_ramp_checkbox = QCheckBox("RF Ramp")
        self.rf_ramp_checkbox.setChecked(True)

        self.settings = Settings(
            ssa_cal_checkbox=self.ssa_cal_checkbox,
            auto_tune_checkbox=self.autotune_checkbox,
            cav_char_checkbox=self.cav_char_checkbox,
            rf_ramp_checkbox=self.rf_ramp_checkbox,
        )

        # Exposed as instance attributes for testability and external tooling.
        self.machine_setup_button: QPushButton = QPushButton("Set Up Machine")
        self.machine_shutdown_button: QPushButton = QPushButton(
            "Shut Down Machine"
        )
        self.machine_abort_button: QPushButton = QPushButton("Abort Machine")
        self.machine_setup_popup = make_sanity_check_popup(
            "This will set up all online cavities"
        )
        self.machine_shutdown_popup = make_sanity_check_popup(
            "This will turn off all online cavities and SSAs"
        )
        self.machine_abort_popup = make_sanity_check_popup(
            "This will abort all scripts running on all online cavities"
        )

        main_layout = QVBoxLayout()
        self.setLayout(main_layout)
        main_layout.addWidget(self._make_top_bar())

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        matrix_widget = QWidget()
        matrix_layout = QVBoxLayout()
        matrix_layout.setSpacing(0)
        matrix_layout.setContentsMargins(4, 4, 4, 4)
        matrix_widget.setLayout(matrix_layout)
        scroll_area.setWidget(matrix_widget)
        main_layout.addWidget(scroll_area)

        for linac_idx in range(5):
            if linac_idx > 0:
                matrix_layout.addSpacing(8)
            linac_name = _LINAC_NAMES[linac_idx]

            cm_container = QWidget()
            cm_layout = QVBoxLayout()
            cm_layout.setContentsMargins(0, 0, 0, 0)
            cm_layout.setSpacing(0)
            cm_container.setLayout(cm_layout)
            for cm_name in linac_utils.LINAC_CM_MAP[linac_idx]:
                cm_layout.addWidget(self._make_cm_section(linac_idx, cm_name))
            cm_container.setVisible(False)

            matrix_layout.addWidget(
                self._make_linac_header(linac_idx, linac_name, cm_container)
            )
            matrix_layout.addWidget(cm_container)

        matrix_layout.addStretch()

    def _make_top_bar(self) -> QWidget:
        top = QWidget()
        top_layout = QVBoxLayout()
        top.setLayout(top_layout)

        self.machine_setup_button.setStyleSheet(_SETUP_STYLE)
        self.machine_abort_button.setStyleSheet(ERROR_STYLESHEET)

        self.machine_setup_button.clicked.connect(
            lambda: self._confirm_and_run(
                self.machine_setup_popup,
                lambda: self._apply_settings_and_run(SETUP_MACHINE),
            )
        )
        self.machine_shutdown_button.clicked.connect(
            lambda: self._confirm_and_run(
                self.machine_shutdown_popup, SETUP_MACHINE.trigger_shutdown
            )
        )
        self.machine_abort_button.clicked.connect(
            lambda: self._confirm_and_run(
                self.machine_abort_popup, SETUP_MACHINE.trigger_abort
            )
        )

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(self.machine_setup_button)
        btn_layout.addWidget(self.machine_shutdown_button)
        btn_layout.addWidget(self.machine_abort_button)
        btn_layout.addStretch()
        top_layout.addLayout(btn_layout)

        option_layout = QHBoxLayout()
        option_layout.addStretch()
        option_layout.addWidget(self.ssa_cal_checkbox)
        option_layout.addWidget(self.autotune_checkbox)
        option_layout.addWidget(self.cav_char_checkbox)
        option_layout.addWidget(self.rf_ramp_checkbox)
        option_layout.addStretch()
        top_layout.addLayout(option_layout)

        return top

    def _make_linac_header(
        self, linac_idx: int, linac_name: str, cm_container: QWidget
    ) -> QFrame:
        header = QFrame()
        header.setStyleSheet(
            "QFrame { background: #1a3a5c; border-bottom: 2px solid #4a8abf; }"
        )
        layout = QHBoxLayout()
        layout.setContentsMargins(8, 4, 8, 4)
        header.setLayout(layout)

        toggle_btn = QToolButton()
        toggle_btn.setArrowType(Qt.RightArrow)
        toggle_btn.setFixedSize(20, 20)
        toggle_btn.clicked.connect(
            lambda: self._toggle_section(cm_container, toggle_btn)
        )
        layout.addWidget(toggle_btn)

        name_label = QLabel(linac_name)
        name_label.setStyleSheet(
            "font-weight: bold; font-size: 14px; color: white;"
        )
        layout.addWidget(name_label)

        aact_prefix = QLabel("AACT:")
        aact_prefix.setStyleSheet("color: #cccccc;")
        layout.addWidget(aact_prefix)

        aact_label = PyDMLabel(init_channel=f"ACCL:L{linac_idx}B:1:AACTMEANSUM")
        aact_label.alarmSensitiveContent = True
        aact_label.alarmSensitiveBorder = True
        aact_label.showUnits = True
        layout.addWidget(aact_label)

        layout.addStretch()

        linac_obj = SETUP_MACHINE.linacs[linac_idx]

        setup_btn = QPushButton("Set Up")
        setup_btn.setStyleSheet(_SETUP_STYLE)
        setup_btn.clicked.connect(
            lambda: self._apply_settings_and_run(linac_obj)
        )
        layout.addWidget(setup_btn)

        abort_btn = QPushButton("Abort")
        abort_btn.setStyleSheet(ERROR_STYLESHEET)
        abort_btn.clicked.connect(linac_obj.trigger_abort)
        layout.addWidget(abort_btn)

        acon_btn = QPushButton("Capture ACON")
        acon_btn.clicked.connect(lambda: self._capture_linac_acon(linac_idx))
        layout.addWidget(acon_btn)

        return header

    def _make_cm_section(self, linac_idx: int, cm_name: str) -> QWidget:
        """CM header row + collapsible inline CavityPanel."""
        section = QWidget()
        section_layout = QVBoxLayout()
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(0)
        section.setLayout(section_layout)

        panel = CavityPanel(cm_name, linac_idx, self.settings, parent=section)
        panel.setVisible(False)

        # ── Header line ──────────────────────────────────────────────────────
        header = QWidget()
        ctrl_line = QHBoxLayout()
        ctrl_line.setContentsMargins(4, 2, 4, 2)
        ctrl_line.setSpacing(6)
        header.setLayout(ctrl_line)

        toggle_btn = QToolButton()
        toggle_btn.setArrowType(Qt.RightArrow)
        toggle_btn.setFixedSize(16, 16)
        toggle_btn.clicked.connect(
            lambda: self._toggle_section(panel, toggle_btn)
        )
        ctrl_line.addWidget(toggle_btn)

        cm_label = QLabel(f"CM{cm_name}")
        cm_label.setFixedWidth(44)
        ctrl_line.addWidget(cm_label)

        aact_label = PyDMLabel(
            init_channel=f"ACCL:L{linac_idx}B:{cm_name}00:AACTMEANSUM"
        )
        aact_label.alarmSensitiveContent = True
        aact_label.alarmSensitiveBorder = True
        aact_label.showUnits = True
        aact_label.setToolTip("Cryomodule AACTMEANSUM")
        aact_label.setMinimumWidth(45)
        aact_label.setMaximumWidth(70)
        ctrl_line.addWidget(aact_label)

        ctrl_line.addStretch()

        cm_obj = SETUP_MACHINE.cryomodules[cm_name]

        setup_btn = QPushButton("Set Up")
        setup_btn.setStyleSheet(_SETUP_STYLE)
        setup_btn.clicked.connect(lambda: self._apply_settings_and_run(cm_obj))
        ctrl_line.addWidget(setup_btn)

        off_btn = QPushButton("Turn Off")
        off_btn.clicked.connect(cm_obj.trigger_shutdown)
        ctrl_line.addWidget(off_btn)

        abort_btn = QPushButton("Abort")
        abort_btn.setStyleSheet(ERROR_STYLESHEET)
        abort_btn.clicked.connect(cm_obj.trigger_abort)
        ctrl_line.addWidget(abort_btn)

        acon_btn = QPushButton("ACON")
        acon_btn.setToolTip(f"Push all CM{cm_name} ADES to ACON")
        acon_btn.clicked.connect(lambda: self._capture_cm_acon(cm_name))
        ctrl_line.addWidget(acon_btn)

        section_layout.addWidget(header)
        section_layout.addWidget(panel)

        return section

    @staticmethod
    def _toggle_section(container: QWidget, btn: QToolButton) -> None:
        visible = not container.isVisible()
        container.setVisible(visible)
        btn.setArrowType(Qt.DownArrow if visible else Qt.RightArrow)

    def _apply_settings_and_run(self, obj) -> None:
        obj.ssa_cal_requested = self.settings.ssa_cal_checkbox.isChecked()
        obj.auto_tune_requested = self.settings.auto_tune_checkbox.isChecked()
        obj.cav_char_requested = self.settings.cav_char_checkbox.isChecked()
        obj.rf_ramp_requested = self.settings.rf_ramp_checkbox.isChecked()
        obj.trigger_start()

    def _capture_linac_acon(self, linac_idx: int) -> None:
        for cm_name in linac_utils.LINAC_CM_MAP[linac_idx]:
            self._capture_cm_acon(cm_name)

    def _capture_cm_acon(self, cm_name: str) -> None:
        for cavity in SETUP_MACHINE.cryomodules[cm_name].cavities.values():
            cavity.capture_acon()

    @staticmethod
    def _confirm_and_run(popup, action) -> None:
        if popup.exec() == QMessageBox.Yes:
            action()
