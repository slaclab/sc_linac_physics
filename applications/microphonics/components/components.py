from pathlib import Path

from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtWidgets import (
    QVBoxLayout, QGroupBox, QLabel, QCheckBox, QPushButton,
    QGridLayout, QFileDialog
)


class ChannelSelectionGroup(QGroupBox):
    """
    UI component that lets people pick which data channels they want to measure.

    Component splits channels into two types:
    - Primary channels (DAC and DF): Always on and can't be turned off
    - Optional channels: Extra measurements users can toggle on/off as needed
    """

    def __init__(self, parent=None):
        super().__init__("Channel Selection", parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QGridLayout()

        # Primary channels section
        primary_label = QLabel("Primary Channels:")
        layout.addWidget(primary_label, 0, 0)

        self.dac_check = QCheckBox("DAC")
        self.dac_check.setChecked(True)
        self.dac_check.setEnabled(False)
        layout.addWidget(self.dac_check, 0, 1)

        self.df_check = QCheckBox("DF")
        self.df_check.setChecked(True)
        self.df_check.setEnabled(False)
        layout.addWidget(self.df_check, 0, 2)

        # Optional channels toggle
        self.optional_toggle = QCheckBox("Show Optional Channels")
        self.optional_toggle.stateChanged.connect(self._toggle_optional_channels)
        layout.addWidget(self.optional_toggle, 1, 0, 1, 3)

        # Optional channels section (initially hidden)
        self.optional_group = QGroupBox("Optional Channels")
        optional_layout = QGridLayout()

        # Keep track of optional channels
        self.optional_channels = {
            'AINEG': QCheckBox("AINEG"),
            'AVDIFF': QCheckBox("AVDIFF"),
            'AIPOS': QCheckBox("AIPOS"),
            'ADRV': QCheckBox("ADRV"),
            'BINEG': QCheckBox("BINEG"),
            'BVDIFF': QCheckBox("BVDIFF"),
            'BIPOS': QCheckBox("BIPOS"),
            'BDRV': QCheckBox("BDRV")
        }

        # Arrange optional channels
        row = 0
        col = 0
        for name, checkbox in self.optional_channels.items():
            optional_layout.addWidget(checkbox, row, col)
            col += 1
            if col > 2:
                col = 0
                row += 1

        self.optional_group.setLayout(optional_layout)
        layout.addWidget(self.optional_group, 2, 0, 1, 3)
        self.optional_group.hide()

        self.setLayout(layout)

    def _toggle_optional_channels(self, state):
        """This will show/hide the optional channels based on toggle state"""
        if state == Qt.Checked:
            self.optional_group.show()
        else:
            self.optional_group.hide()

    def get_selected_channels(self):
        """This will get a list of selected channel names"""
        channels = ['DAC', 'DF']
        for name, checkbox in self.optional_channels.items():
            if checkbox.isChecked():
                channels.append(name)
        return channels


class DataLoadingGroup(QGroupBox):
    """
    Component lets people load previously saved data files.
    """
    # Signal emitted when the load button is clicked and a file is selected
    fileSelected = pyqtSignal(Path)

    def __init__(self, parent=None):
        super().__init__("Data Loading", parent)
        self.setup_ui()

    def setup_ui(self):
        """Create the UI components"""
        layout = QVBoxLayout()

        # This creates load button
        self.load_button = QPushButton("Load Previous Data")
        self.load_button.clicked.connect(self._handle_button_click)
        layout.addWidget(self.load_button)

        # This creates info label
        self.file_info = QLabel("No file loaded")
        layout.addWidget(self.file_info)

        self.setLayout(layout)

    def _handle_button_click(self):
        """Handle the load button being clicked"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Previous Data",
            str(Path.home()),  # Want to start in users home directory
            "All Files (*);;Text Files (*.txt);;Data Files (*.dat)"
        )

        if file_path:
            path = Path(file_path)
            self.file_info.setText(f"Selected: {path.name}")
            self.fileSelected.emit(path)

    def update_file_info(self, status: str):
        """Update the file info label with a status message"""
        self.file_info.setText(status)
