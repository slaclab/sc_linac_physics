from typing import List

import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QPushButton,
    QGroupBox,
    QGridLayout,
    QLabel,
    QMessageBox,
    QWidget,
    QVBoxLayout,
)
from matplotlib import pyplot as plt
from pydm.widgets import PyDMLabel, PyDMEnumComboBox, PyDMSpinbox


class RFControls:
    def __init__(self):
        self.ssa_on_button: QPushButton = QPushButton("SSA On")
        self.ssa_off_button: QPushButton = QPushButton("SSA Off")
        self.ssa_readback_label: PyDMLabel = PyDMLabel()

        self.rf_mode_combobox: PyDMEnumComboBox = PyDMEnumComboBox()
        self.rf_mode_readback_label: PyDMLabel = PyDMLabel()

        self.rf_on_button: QPushButton = QPushButton("RF On")
        self.rf_off_button: QPushButton = QPushButton("RF Off")
        self.rf_status_readback_label: PyDMLabel = PyDMLabel()

        self.ades_spinbox: PyDMSpinbox = PyDMSpinbox()
        self.ades_spinbox.step_exponent = -1
        self.ades_spinbox.update_step_size()
        self.aact_readback_label: PyDMLabel = PyDMLabel()

        self.srf_max_spinbox: PyDMSpinbox = PyDMSpinbox()
        self.srf_max_spinbox.step_exponent = -1
        self.srf_max_spinbox.update_step_size()
        self.srf_max_readback_label: PyDMLabel = PyDMLabel()

        self.rf_control_groupbox: QGroupBox = QGroupBox("RF Controls")
        control_groupbox_layout = QGridLayout()
        self.rf_control_groupbox.setLayout(control_groupbox_layout)
        ssa_row = 0
        control_groupbox_layout.addWidget(self.ssa_on_button, ssa_row, 0)
        control_groupbox_layout.addWidget(self.ssa_off_button, ssa_row, 1)
        control_groupbox_layout.addWidget(self.ssa_readback_label, ssa_row, 2)

        rf_row = 1
        control_groupbox_layout.addWidget(self.rf_on_button, rf_row, 0)
        control_groupbox_layout.addWidget(self.rf_off_button, rf_row, 1)
        control_groupbox_layout.addWidget(self.rf_status_readback_label, rf_row, 2)

        mode_row = 2
        control_groupbox_layout.addWidget(self.rf_mode_combobox, mode_row, 0, 1, 3)

        amp_row = 3
        control_groupbox_layout.addWidget(QLabel("Amplitude:"), amp_row, 0)
        control_groupbox_layout.addWidget(self.ades_spinbox, amp_row, 1)
        control_groupbox_layout.addWidget(self.aact_readback_label, amp_row, 2)

        max_row = 4
        control_groupbox_layout.addWidget(QLabel("SRF Max"), max_row, 0)
        control_groupbox_layout.addWidget(self.srf_max_spinbox, max_row, 1)
        control_groupbox_layout.addWidget(self.srf_max_readback_label, max_row, 2)


class Worker(QThread):
    finished = pyqtSignal(str)
    progress = pyqtSignal(int)
    error = pyqtSignal(str)
    status = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.finished.connect(print)
        self.progress.connect(print)
        self.error.connect(print)
        self.status.connect(print)

    def terminate(self) -> None:
        self.error.emit("Thread termination requested")
        super().terminate()


def make_error_popup(title, message: str):
    popup = QMessageBox()
    popup.setIcon(QMessageBox.Critical)
    popup.setWindowTitle(title)
    popup.setText(message)
    popup.exec()


def make_rainbow(num_colors) -> List[List[int]]:
    colormap = plt.cm.hsv
    return colormap(np.linspace(0, 1, num_colors, endpoint=False), bytes=True)


def highlight_text(r, g, b, text):
    """
    taken from stack overflow
    https://stackoverflow.com/questions/70519979/printing-with-rgb-background
    """
    return f"\033[48;2;{r};{g};{b}m{text}\033[0m"


def get_dimensions(options: List):
    num_options = len(options)
    sqrt = np.sqrt(num_options)
    row_count = int(sqrt)
    col_count = int(np.ceil(sqrt))
    if row_count * col_count < num_options:
        col_count += 1
    return col_count


def make_sanity_check_popup(txt: str) -> QMessageBox:
    msg = QMessageBox()
    msg.setText("Are you sure?")
    msg.setInformativeText(txt)
    msg.setIcon(QMessageBox.Warning)
    msg.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)
    msg.setDefaultButton(QMessageBox.Cancel)

    # msg.setDetailedText("details")

    return msg


class CollapsibleGroupBox(QGroupBox):
    def __init__(self, title, content_layout, parent=None):
        super().__init__(title, parent)
        self.setCheckable(True)
        self.setChecked(False)  # Initially collapsed
        self.content_widget = QWidget()
        self.content_layout = content_layout
        self.content_widget.setLayout(self.content_layout)
        self.layout = QVBoxLayout(self)
        self.layout.addWidget(self.content_widget)
        self.toggled.connect(self.on_toggled)
        self.content_widget.setVisible(False)

    def on_toggled(self, checked):
        self.content_widget.setVisible(checked)
        self.adjustSize()


class MockWidget(QWidget):
    def __init__(self, **kwargs):
        super().__init__()
