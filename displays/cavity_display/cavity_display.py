from functools import partial

from PyQt5.QtGui import QColor, QCursor
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QVBoxLayout,
    QFrame,
    QPushButton,
    QGroupBox,
)
from lcls_tools.common.frontend.display.util import showDisplay
from pydm import Display
from pydm.utilities import IconFont
from pydm.widgets import PyDMByteIndicator, PyDMLabel

from displays.cavity_display.frontend.fault_count_display import FaultCountDisplay
from frontend.decoder import DecoderDisplay
from frontend.gui_machine import GUIMachine
from frontend.utils import make_line


class CavityDisplayGUI(Display):
    def __init__(self, parent=None, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.setStyleSheet(
            "background-color: rgb(35, 35, 35); color: rgb(255, 255, 255); font-size: 15pt;"
        )

        self.gui_machine = GUIMachine()

        self.header = QHBoxLayout()
        heartbeat_indicator = PyDMByteIndicator(
            init_channel="ALRM:SYS0:SC_CAV_FAULT:ALHBERR"
        )
        heartbeat_indicator.onColor = QColor(255, 0, 0)
        heartbeat_indicator.offColor = QColor(0, 255, 0)
        heartbeat_indicator.showLabels = False
        heartbeat_indicator.circles = True
        heartbeat_indicator.showLabels = False

        heartbeat_label = PyDMLabel(init_channel="ALRM:SYS0:SC_CAV_FAULT:ALHBERR")
        heartbeat_counter = PyDMLabel(init_channel="PHYS:SYS0:1:SC_CAV_FAULT_HEARTBEAT")

        self.header.addWidget(heartbeat_indicator)
        self.header.addWidget(heartbeat_label)
        self.header.addWidget(heartbeat_counter)
        self.header.addStretch()

        self.decoder_window: DecoderDisplay = DecoderDisplay()
        self.decoder_button = QPushButton("Three Letter Code Decoder")
        self.add_header_button(self.decoder_button, self.decoder_window)

        self.setWindowTitle("SRF Cavity Display")

        self.vlayout = QVBoxLayout()
        self.vlayout.setContentsMargins(0, 0, 0, 0)
        self.groupbox_vlayout = QVBoxLayout()
        self.groupbox_vlayout.addLayout(self.header)
        self.setLayout(self.vlayout)

        self.groupbox_vlayout.addLayout(self.gui_machine.top_half)
        self.groupbox_vlayout.addSpacing(10)
        self.groupbox_vlayout.addWidget(make_line(QFrame.HLine))
        self.groupbox_vlayout.addLayout(self.gui_machine.bottom_half)

        self.groupbox = QGroupBox()
        self.groupbox.setLayout(self.groupbox_vlayout)
        self.vlayout.addWidget(self.groupbox)

        self.fault_count_display: FaultCountDisplay = FaultCountDisplay()
        self.fault_count_button: QPushButton = QPushButton("Fault Counter")
        self.fault_count_button.setToolTip("See fault history using archived data")
        self.add_header_button(self.fault_count_button, self.fault_count_display)

    def add_header_button(self, button: QPushButton, display: Display):
        button.clicked.connect(partial(showDisplay, display))

        icon = IconFont().icon("file")
        button.setIcon(icon)
        button.setCursor(QCursor(icon.pixmap(16, 16)))
        button.openInNewWindow = True
        self.header.addWidget(button)
