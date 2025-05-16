from pathlib import Path

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QVBoxLayout, QGroupBox, QLabel, QPushButton,
    QGridLayout, QFileDialog, QCheckBox
)


class ChannelSelectionGroup(QGroupBox):
    """
    UI component that shows what data channels will be measured.

    Component splits channels into two types:
    - Primary channels (DF): Always on and can't be turned off
    """
    FIXED_CHANNELS = {
        'DF': {'label': "DF (Detune Frequency)", 'default_state': True, 'enabled': False}
    }

    def __init__(self, parent=None):
        super().__init__("Channel Selection", parent)
        # Dictionary stores the QCheckbox widgets, keyed by channel name
        self.channel_widgets = {}
        self.setup_ui()

    def setup_ui(self):
        layout = QGridLayout()
        self.setLayout(layout)
        current_row = 0

        # Create checkboxes for FIXED_CHANNELS
        if self.FIXED_CHANNELS:
            col_idx = 0
            for name, config in self.FIXED_CHANNELS.items():
                checkbox = QCheckBox(config['label'])
                checkbox.setChecked(config['default_state'])
                checkbox.setEnabled(config['enabled'])
                self.channel_widgets[name] = checkbox
                layout.addWidget(checkbox, current_row, col_idx)
                col_idx += 1
            if col_idx > 0:
                current_row += 1
                
        # Adding stretch to push all UI elements to the top.
        layout.setRowStretch(current_row, 1)

    def get_selected_channels(self):
        """This will get a list of selected channel names by reading current state
        of managed QCheckBox widgets."""
        channels = []
        for name, checkbox_widget in self.channel_widgets.items():
            if checkbox_widget.isChecked():
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
