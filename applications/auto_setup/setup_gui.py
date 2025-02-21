from typing import List

from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QPushButton,
    QCheckBox,
    QMessageBox,
)
from lcls_tools.common.controls.pyepics.utils import PV
from lcls_tools.common.frontend.display.util import ERROR_STYLESHEET
from pydm import Display

from applications.auto_setup.backend.setup_machine import SETUP_MACHINE
from applications.auto_setup.frontend.gui_linac import GUILinac
from applications.auto_setup.frontend.utils import Settings
from utils.qt import make_sanity_check_popup
from utils.sc_linac import linac_utils
from utils.sc_linac.linac_utils import ALL_CRYOMODULES


class SetupGUI(Display):
    def __init__(self, parent=None, args=None):
        super(SetupGUI, self).__init__(parent=parent, args=args)
        self.setWindowTitle("SRF Auto Setup")

        self.main_layout: QVBoxLayout = QVBoxLayout()
        self.setLayout(self.main_layout)

        num_total_cavities = len(ALL_CRYOMODULES) * 8

        self.machine_setup_button: QPushButton = QPushButton("Set Up Machine")
        self.machine_setup_popup = make_sanity_check_popup(
            f"This will set up all {num_total_cavities} cavities"
        )

        self.machine_shutdown_button: QPushButton = QPushButton("Shut Down Machine")
        self.machine_shutdown_popup = make_sanity_check_popup(
            f"This will turn off all {num_total_cavities} cavities and SSAs"
        )

        self.machine_abort_button: QPushButton = QPushButton("Abort Machine")
        self.machine_abort_popup = make_sanity_check_popup(
            f"This will abort all scripts running on all {num_total_cavities} cavities"
        )

        self.machine_button_layout: QHBoxLayout = QHBoxLayout()
        self.machine_button_layout.addStretch()
        self.machine_button_layout.addWidget(self.machine_setup_button)
        self.machine_button_layout.addWidget(self.machine_shutdown_button)
        self.machine_button_layout.addWidget(self.machine_abort_button)
        self.machine_button_layout.addStretch()
        self.main_layout.addLayout(self.machine_button_layout)

        self.connect_buttons()

        self.ssa_cal_checkbox = QCheckBox("SSA Calibration")
        self.ssa_cal_checkbox.setChecked(True)
        self.autotune_checkbox: QCheckBox = QCheckBox("Auto Tune")
        self.autotune_checkbox.setChecked(True)
        self.cav_char_checkbox: QCheckBox = QCheckBox("Cavity Characterization")
        self.cav_char_checkbox.setChecked(True)
        self.rf_ramp_checkbox: QCheckBox = QCheckBox("RF Ramp")
        self.rf_ramp_checkbox.setChecked(True)

        self.option_layout: QHBoxLayout = QHBoxLayout()
        self.option_layout.addStretch()
        self.option_layout.addWidget(self.ssa_cal_checkbox)
        self.option_layout.addWidget(self.autotune_checkbox)
        self.option_layout.addWidget(self.cav_char_checkbox)
        self.option_layout.addWidget(self.rf_ramp_checkbox)
        self.option_layout.addStretch()
        self.main_layout.addLayout(self.option_layout)

        self.tabWidget_linac = QTabWidget()
        self.main_layout.addWidget(self.tabWidget_linac)

        self.settings = Settings(
            ssa_cal_checkbox=self.ssa_cal_checkbox,
            auto_tune_checkbox=self.autotune_checkbox,
            cav_char_checkbox=self.cav_char_checkbox,
            rf_ramp_checkbox=self.rf_ramp_checkbox,
        )
        self.linac_widgets: List[GUILinac] = []
        self.populate_linac_widgets()

        self.linac_aact_pvs: List[PV] = [
            PV(f"ACCL:L{i}B:1:AACTMEANSUM") for i in range(4)
        ]

        self.populate_tabs()

    def populate_tabs(self):
        linac_tab_widget: QTabWidget = self.tabWidget_linac
        for linac in self.linac_widgets:
            page: QWidget = QWidget()
            vlayout: QVBoxLayout = QVBoxLayout()
            page.setLayout(vlayout)
            linac_tab_widget.addTab(page, linac.name)

            hlayout: QHBoxLayout = QHBoxLayout()
            hlayout.addStretch()
            hlayout.addWidget(QLabel(f"{linac.name} Amplitude:"))
            hlayout.addWidget(linac.readback_label)
            hlayout.addWidget(linac.setup_button)
            hlayout.addWidget(linac.abort_button)
            hlayout.addWidget(linac.acon_button)
            hlayout.addStretch()

            vlayout.addLayout(hlayout)
            vlayout.addWidget(linac.cm_tab_widget)

    def populate_linac_widgets(self):
        for linac_idx in range(0, 4):
            self.linac_widgets.append(
                GUILinac(
                    f"L{linac_idx}B",
                    linac_idx,
                    linac_utils.LINAC_TUPLES[linac_idx][1],
                    settings=self.settings,
                    parent=self,
                )
            )
        self.linac_widgets.insert(
            2,
            GUILinac(
                "L1BHL", 1, linac_utils.L1BHL, settings=self.settings, parent=self
            ),
        )

    def connect_buttons(self):
        self.machine_abort_button.setStyleSheet(ERROR_STYLESHEET)
        self.machine_abort_button.clicked.connect(self.trigger_machine_abort)
        self.machine_setup_button.clicked.connect(self.trigger_machine_setup)
        self.machine_shutdown_button.clicked.connect(self.trigger_machine_shutdown)

    def trigger_machine_setup(self):
        selection = self.machine_setup_popup.exec()
        if selection == QMessageBox.Yes:
            SETUP_MACHINE.ssa_cal_requested = self.settings.ssa_cal_checkbox.isChecked()
            SETUP_MACHINE.auto_tune_requested = (
                self.settings.auto_tune_checkbox.isChecked()
            )
            SETUP_MACHINE.cav_char_requested = (
                self.settings.cav_char_checkbox.isChecked()
            )
            SETUP_MACHINE.rf_ramp_requested = self.settings.rf_ramp_checkbox.isChecked()
            SETUP_MACHINE.trigger_machine_setup()

    def trigger_machine_shutdown(self):
        selection = self.machine_shutdown_popup.exec()
        if selection == QMessageBox.Yes:
            SETUP_MACHINE.trigger_shutdown()

    def trigger_machine_abort(self):
        selection = self.machine_abort_popup.exec()
        if selection == QMessageBox.Yes:
            SETUP_MACHINE.trigger_abort()
