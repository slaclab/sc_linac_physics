from pathlib import Path

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QVBoxLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QGridLayout,
    QCheckBox,
    QFileDialog,
)


class ChannelSelectionGroup(QGroupBox):
    """
    UI component that shows what data channels will be measured.
    - Primary channel (DF): Always on and can't be turned off
    """

    FIXED_CHANNELS = {
        "DF": {
            "label": "DF (Detune Frequency)",
            "default_state": True,
            "enabled": False,
        }
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
        # Create checkboxes
        for col_idx, (name, config) in enumerate(self.FIXED_CHANNELS.items()):
            checkbox = QCheckBox(config["label"])
            checkbox.setChecked(config["default_state"])
            checkbox.setEnabled(config["enabled"])
            self.channel_widgets[name] = checkbox
            layout.addWidget(checkbox, current_row, col_idx)

        if self.FIXED_CHANNELS:
            current_row += 1

        # Adding stretch to push all UI elements to the top.
        layout.setRowStretch(current_row, 1)

    def get_selected_channels(self):
        """This will get a list of selected channel names by reading current state
        of managed QCheckBox widgets."""
        return [name for name, checkbox in self.channel_widgets.items() if checkbox.isChecked()]


class DataLoadingGroup(QGroupBox):
    """
    Component lets people load previously saved data files.
    """

    PREFERRED_DEFAULT_DATA_PATH = Path("/u1/lcls/physics/rf_lcls2/microphonics")
    # Signal emitted when the load button is clicked and a file is selected
    file_selected = pyqtSignal(Path)

    def __init__(self, parent=None):
        super().__init__("Data Loading", parent)
        self.setup_ui()

    def setup_ui(self):
        """Create the UI components"""
        layout = QVBoxLayout()

        # Load button
        self.load_button = QPushButton("Load Previous Data")
        self.load_button.clicked.connect(self._show_file_dialog)
        layout.addWidget(self.load_button)

        # Info label
        self.file_info_label = QLabel("No file loaded")
        layout.addWidget(self.file_info_label)

        self.setLayout(layout)

    def _get_start_directory(self) -> str:
        """Figures the best starting directory for the file dialog."""
        if self.PREFERRED_DEFAULT_DATA_PATH.is_dir():
            return str(self.PREFERRED_DEFAULT_DATA_PATH)

        home_path = Path.home()
        if home_path.is_dir():
            return str(home_path)

        # Last resort, use current working directory.
        return "."

    def _show_file_dialog(self):
        """Opens file dialog to let user select data file."""
        start_directory = self._get_start_directory()

        file_filters = "All Files (*);;Text Files (*.txt);;Data Files (*.dat)"

        file_path_str, _ = QFileDialog.getOpenFileName(self, "Load Previous Data", start_directory, file_filters)

        if file_path_str:
            file_path = Path(file_path_str)
            self.file_info_label.setText(f"Selected: {file_path.name}")
            self.file_selected.emit(file_path)

    def update_file_info(self, status: str):
        """Update the file info label with a status message"""
        self.file_info_label.setText(status)
