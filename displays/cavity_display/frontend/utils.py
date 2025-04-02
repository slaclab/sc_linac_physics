from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QFrame, QSizePolicy, QGridLayout, QLabel
from lcls_tools.common.controls.pyepics.utils import PVInvalidError
from pydm.widgets import PyDMLabel, PyDMRelatedDisplayButton

from displays.cavity_display.backend.fault import Fault


def make_line(shape=QFrame.VLine):
    line = QFrame()
    line.setFrameShape(shape)
    line.setStyleSheet("background-color: rgb(255, 255, 255);")
    return line


class EnumLabel(PyDMLabel):
    """
    PyDMLabel subclass to change PyDMLabel Alarm channel text
    """

    def __init__(self, fault: Fault, code_label: QLabel, parent=None, args=None):
        super(EnumLabel, self).__init__(parent=parent, init_channel=fault.pv)
        self.fault: Fault = fault
        self.code_label: QLabel = code_label

        self.setMaximumWidth(100)
        self.setMaximumHeight(28)
        self.setMinimumHeight(28)
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        self.setAlignment(Qt.AlignCenter)

    def value_changed(self, new_value):
        super(EnumLabel, self).value_changed(new_value)
        try:
            if self.fault.is_currently_faulted():
                self.setText("FAULTED")
                self.setStyleSheet(
                    "background-color: rgb(255,0,0); font-weight: "
                    "bold; border: 2px solid black; color: white;"
                )
                self.code_label.setStyleSheet("font-weight:bold;")

            else:
                self.setText("OK")
                self.setStyleSheet(
                    "background-color: rgb(0,255,0);font-weight: bold; "
                    "border: 2px solid black;"
                )
                self.code_label.setStyleSheet("font-weight:plain;")

        except PVInvalidError:
            self.setText("INVALID")
            self.setStyleSheet(
                "background-color: rgb(255,0,255);font-weight: bold;"
                "border: 2px solid black;"
            )
            self.code_label.setStyleSheet("font-weight:bold;")


class PyDMFaultButton(PyDMRelatedDisplayButton):
    def __init__(self, filename):
        super().__init__(filename=filename)

    def push_button_release_event(self, mouse_event) -> None:
        for item in self._get_items():
            self.open_display(
                item["filename"],
                item["macros"],
                target=PyDMRelatedDisplayButton.NEW_WINDOW,
            )


def make_header() -> QGridLayout:
    grid_layout: QGridLayout = QGridLayout()
    status_header_label = QLabel("Status")
    status_header_label.setAlignment(Qt.AlignHCenter)
    status_header_label.setStyleSheet("text-decoration:underline")

    name_header_label = QLabel("Name")
    name_header_label.setAlignment(Qt.AlignLeft)
    name_header_label.setStyleSheet("text-decoration:underline")

    code_header_label = QLabel("Code")
    code_header_label.setAlignment(Qt.AlignHCenter)
    code_header_label.setStyleSheet("text-decoration:underline")

    button_header_label = QLabel("Panel")
    button_header_label.setAlignment(Qt.AlignHCenter)
    button_header_label.setStyleSheet("text-decoration:underline")

    action_header_label: QLabel = QLabel("Recommended Corrective Action")
    action_header_label.setAlignment(Qt.AlignHCenter)
    action_header_label.setStyleSheet("text-decoration:underline")

    grid_layout.addWidget(code_header_label, 0, 0)
    grid_layout.addWidget(name_header_label, 0, 1)
    grid_layout.addWidget(status_header_label, 0, 2)
    grid_layout.addWidget(button_header_label, 0, 3)
    grid_layout.addWidget(action_header_label, 0, 4)
    return grid_layout
