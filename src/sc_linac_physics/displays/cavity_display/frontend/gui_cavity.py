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

        # Build the cavity widget layout
        self._build_cavity_layout(cavity_num)

        # Configure PV channels
        self._setup_pv_channels()

    def _build_cavity_layout(self, cavity_num):
        """Build the complete layout for the cavity widget."""
        # Main vertical layout
        self.vert_layout = QVBoxLayout()
        self.vert_layout.setSpacing(0)
        self.vert_layout.setContentsMargins(0, 0, 0, 0)

        # Cavity widget (diamond/shape)
        self.cavity_widget = CavityWidget()
        self.cavity_widget.setMinimumSize(40, 40)
        self.cavity_widget.setMaximumSize(100, 100)
        self.cavity_widget.setAccessibleName("cavity_widget")
        self.cavity_widget.cavity_text = str(cavity_num)
        self.cavity_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.cavity_widget.clicked.connect(self.show_fault_display)
        self.cavity_widget._parent_cavity = self  # Link back for context menu

        # Status indicator bars (SSA and RF state)
        self.hor_layout = self._create_status_bars()

        # Add to layout
        self.vert_layout.addWidget(self.cavity_widget, alignment=Qt.AlignCenter)
        self.vert_layout.addLayout(self.hor_layout)

    def _create_status_bars(self):
        """Create SSA and RF status indicator bars."""
        hor_layout = QHBoxLayout()
        hor_layout.setSpacing(0)
        hor_layout.setContentsMargins(0, 0, 0, 0)

        # SSA bar
        self.ssa_bar = PyDMByteIndicator()
        self.ssa_bar.setAccessibleName("SSA")
        self.ssa_bar.onColor = QColor(92, 255, 92)
        self.ssa_bar.offColor = QColor(40, 40, 40)
        self.ssa_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.ssa_bar.showLabels = False
        self.ssa_bar.channel = self.ssa.status_pv
        self.ssa_bar.setFixedHeight(4)
        self.ssa_bar.setMaximumWidth(50)

        # RF bar
        self.rf_bar = PyDMByteIndicator()
        self.rf_bar.setAccessibleName("RFSTATE")
        self.rf_bar.onColor = QColor(14, 191, 255)
        self.rf_bar.offColor = QColor(40, 40, 40)
        self.rf_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.rf_bar.showLabels = False
        self.rf_bar.channel = self.rf_state_pv
        self.rf_bar.setFixedHeight(4)
        self.rf_bar.setMaximumWidth(50)

        # SSA visibility rule
        rule = [
            {
                "channels": [
                    {
                        "channel": self.ssa.status_pv,
                        "trigger": True,
                    }
                ],
                "property": "Opacity",
                "expression": "ch[0] == 'SSA On'",
                "initial_value": "0",
                "name": "show",
            }
        ]
        self.ssa_bar.rules = json.dumps(rule)

        hor_layout.addWidget(self.ssa_bar)
        hor_layout.addWidget(self.rf_bar)

        return hor_layout

    def _setup_pv_channels(self):
        """Configure PV channels for the cavity widget."""
        severity_pv = self.pv_addr("CUDSEVR")
        status_pv = self.pv_addr("CUDSTATUS")
        description_pv = self.pv_addr("CUDDESC")

        self.cavity_widget.channel = status_pv
        self.cavity_widget.severity_channel = severity_pv
        self.cavity_widget.description_channel = description_pv

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
        """Lazy-load the fault display window."""
        if not self._fault_display:
            groupbox = QGroupBox()
            groupbox.setLayout(self.fault_display_grid_layout)
            groupbox.setFlat(True)

            self._fault_display = Display()
            self._fault_display.setWindowTitle(f"{self} Faults")
            vlayout = QVBoxLayout()
            self._fault_display.setLayout(vlayout)

            scroll_area = QScrollArea()
            scroll_area.setWidget(groupbox)
            scroll_area.setWidgetResizable(True)
            vlayout.addWidget(scroll_area)

            self.populate_fault_display()

        return self._fault_display

    def set_scale(self, scale):  # ADD THIS ENTIRE METHOD
        """Scale the cavity widget and indicators based on zoom level."""
        base_cavity_size = 50
        base_indicator_height = 4

        scaled_cavity_size = max(20, int(base_cavity_size * scale))
        scaled_indicator_height = max(1, int(base_indicator_height * scale))

        # Scale cavity widget
        self.cavity_widget.setFixedSize(scaled_cavity_size, scaled_cavity_size)
        self.cavity_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.cavity_widget.setMinimumSize(
            scaled_cavity_size, scaled_cavity_size
        )
        self.cavity_widget.setMaximumSize(
            scaled_cavity_size, scaled_cavity_size
        )

        # Scale indicator bars
        bar_width = scaled_cavity_size // 2
        self.ssa_bar.setFixedSize(bar_width, scaled_indicator_height)
        self.rf_bar.setFixedSize(bar_width, scaled_indicator_height)

        # Update layout
        self.vert_layout.invalidate()
        self.vert_layout.update()
        self.cavity_widget.updateGeometry()
        self.cavity_widget.update()
