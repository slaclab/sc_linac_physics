import json
from typing import TYPE_CHECKING, Optional

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QSizePolicy,
    QGroupBox,
    QScrollArea,
    QAbstractScrollArea,
    QLabel,
)
from edmbutton import PyDMEDMDisplayButton
from lcls_tools.common.frontend.display.util import showDisplay
from pydm import Display
from pydm.widgets import (
    PyDMByteIndicator,
    PyDMShellCommand,
    PyDMRelatedDisplayButton,
)

from sc_linac_physics.displays.cavity_display.backend.backend_cavity import (
    BackendCavity,
)
from sc_linac_physics.displays.cavity_display.frontend.cavity_widget import (
    CavityWidget,
)
from sc_linac_physics.displays.cavity_display.frontend.utils import (
    make_header,
    EnumLabel,
    PyDMFaultButton,
)

if TYPE_CHECKING:
    from sc_linac_physics.utils.sc_linac.rack import Rack


class GUICavity(BackendCavity):
    def __init__(self, cavity_num: int, rack_object: "Rack"):
        super().__init__(cavity_num, rack_object)
        self._fault_display: Optional[Display] = None
        self.fault_display_grid_layout = make_header()

        self.vert_layout = QVBoxLayout()
        self.cavity_widget = CavityWidget()
        self.cavity_widget.setMinimumSize(10, 10)
        self.cavity_widget.setAccessibleName("cavity_widget")
        self.cavity_widget.cavity_text = str(cavity_num)
        self.cavity_widget.setSizePolicy(
            QSizePolicy.Preferred, QSizePolicy.Preferred
        )
        self.cavity_widget.clicked.connect(self.show_fault_display)

        self.hor_layout = QHBoxLayout()

        self.ssa_bar = PyDMByteIndicator()
        self.ssa_bar.setAccessibleName("SSA")
        self.ssa_bar.onColor = QColor(92, 255, 92)
        self.ssa_bar.offColor = QColor(40, 40, 40)
        self.ssa_bar.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self.ssa_bar.showLabels = False
        self.ssa_bar.channel = self.ssa.status_pv
        self.ssa_bar.setFixedHeight(5)

        self.rf_bar = PyDMByteIndicator()
        self.rf_bar.setAccessibleName("RFSTATE")
        self.rf_bar.onColor = QColor(14, 191, 255)
        self.rf_bar.offColor = QColor(40, 40, 40)
        self.rf_bar.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self.rf_bar.showLabels = False
        self.rf_bar.channel = self.rf_state_pv
        self.rf_bar.setFixedHeight(5)

        self.hor_layout.addWidget(self.ssa_bar)
        self.hor_layout.addWidget(self.rf_bar)

        self.vert_layout.addWidget(self.cavity_widget)
        self.vert_layout.addLayout(self.hor_layout)

        severity_pv: str = self.pv_addr("CUDSEVR")
        status_pv: str = self.pv_addr("CUDSTATUS")
        description_pv: str = self.pv_addr("CUDDESC")

        self.cavity_widget.channel = status_pv
        self.cavity_widget.severity_channel = severity_pv
        self.cavity_widget.description_channel = description_pv

        rule = [
            {
                "channels": [
                    {
                        "channel": self.ssa.status_pv,
                        "trigger": True,
                        "use_enum": True,
                    }
                ],
                "property": "Opacity",
                "expression": "ch[0] == 'SSA On'",
                "initial_value": "0",
                "name": "show",
            }
        ]

        self.ssa_bar.rules = json.dumps(rule)

    def populate_fault_display(self):
        for idx, fault in enumerate(self.faults.values()):
            code_label = QLabel(fault.tlc)
            code_label.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
            code_label.setAlignment(Qt.AlignCenter)

            short_description_label = QLabel(fault.short_description)
            short_description_label.setSizePolicy(
                QSizePolicy.Maximum, QSizePolicy.Preferred
            )
            short_description_label.setAlignment(Qt.AlignLeft)
            short_description_label.setWordWrap(True)

            action_label = QLabel(fault.action)
            action_label.setSizePolicy(
                QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding
            )
            action_label.setAlignment(Qt.AlignLeft)
            action_label.setWordWrap(True)

            status_label = EnumLabel(fault=fault, code_label=code_label)
            status_label.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)

            row_idx = idx + 1
            self.fault_display_grid_layout.addWidget(code_label, row_idx, 0)
            self.fault_display_grid_layout.addWidget(
                short_description_label, row_idx, 1
            )
            self.fault_display_grid_layout.addWidget(status_label, row_idx, 2)

            if fault.button_level == "EDM":
                button = PyDMEDMDisplayButton()
                button.filenames = [fault.button_command]
                button.macros = fault.macros + (
                    "," + fault.button_macro if fault.button_macro else ""
                )

            elif fault.button_level == "SCRIPT":
                button = PyDMShellCommand()
                button.commands = [fault.button_command]

            elif fault.button_level == "PYDM":
                button = PyDMFaultButton(filename=fault.button_command)
                button.openInNewWindow = True
                button.macros = self.cryomodule.pydm_macros + (
                    "," + fault.button_macro if fault.button_macro else ""
                )

            else:
                button = PyDMRelatedDisplayButton()
                button.setEnabled(False)

            self.fault_display_grid_layout.addWidget(button, row_idx, 3)
            self.fault_display_grid_layout.addWidget(action_label, row_idx, 4)
            button.setText(fault.button_text)
            button.showIcon = False

    def show_fault_display(self):
        showDisplay(self.fault_display)

    @property
    def fault_display(self):
        if not self._fault_display:
            groupbox = QGroupBox()
            groupbox.setLayout(self.fault_display_grid_layout)
            self.populate_fault_display()

            self._fault_display = Display()
            self._fault_display.setWindowTitle(f"{self} Faults")
            vlayout = QVBoxLayout()

            self._fault_display.setLayout(vlayout)

            scroll_area = QScrollArea()
            scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
            scroll_area.setSizeAdjustPolicy(
                QAbstractScrollArea.AdjustToContents
            )
            scroll_area.setWidgetResizable(True)
            vlayout.addWidget(scroll_area)
            scroll_area.setWidget(groupbox)

        return self._fault_display
