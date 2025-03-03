from pathlib import Path

from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtWidgets import (
    QVBoxLayout, QGroupBox, QLabel, QCheckBox, QPushButton,
    QGridLayout, QFileDialog, QApplication
)


class ChannelSelectionGroup(QGroupBox):
    """
    UI component that lets people pick which data channels they want to measure.

    Component splits channels into two types:
    - Primary channels (DAC and DF): Always on and can't be turned off
    - Optional channels: Extra measurements users can toggle on/off as needed
    """
    # Signal tells other parts of the program when the channel selection changes
    channelsChanged = pyqtSignal(list)

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
            checkbox.stateChanged.connect(self._on_channel_changed)
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

        # Force layout update
        self.layout().activate()
        self.updateGeometry()
        QApplication.processEvents()

    def _on_channel_changed(self):
        """This will handle channel selection changes"""
        self.channelsChanged.emit(self.get_selected_channels())

    def get_selected_channels(self):
        """This will get a list of selected channel names"""
        channels = ['DAC', 'DF']
        for name, checkbox in self.optional_channels.items():
            if checkbox.isChecked():
                channels.append(name)
        return channels


class StatisticsPanel(QGroupBox):
    """
    Panel shows important numbers about your data for each cavity.
    """

    def __init__(self, parent=None):
        super().__init__("Statistical Analysis", parent)
        self.setup_ui()

    def setup_ui(self):
        """
        Creates a tableish like display where each row represents 1 cavity
        and each column shows a different stat measurement.
        """
        layout = QGridLayout()

        # This creates the header row with labels for each stat
        headers = ["Cavity", "Mean", "Std Dev", "Min", "Max", "Outliers"]
        for col, header in enumerate(headers):
            label = QLabel(header)
            label.setStyleSheet("font-weight: bold")
            layout.addWidget(label, 0, col)

        # This creates rows for each cavity
        self.stat_widgets = {}
        for row in range(1, 9):  # 8 cavities
            cavity_label = QLabel(f"Cavity {row}")
            layout.addWidget(cavity_label, row, 0)

            # This creates spots for each stat
            self.stat_widgets[row] = {
                'mean': QLabel("0.0"),
                'std': QLabel("0.0"),
                'min': QLabel("0.0"),
                'max': QLabel("0.0"),
                'outliers': QLabel("0")
            }

            # Adding each stat label to the right spot in the grid
            for col, (key, widget) in enumerate(self.stat_widgets[row].items(), 1):
                layout.addWidget(widget, row, col)

        self.setLayout(layout)

    def update_statistics(self, cavity_num, stats):
        """
        Updates the numbers shown for a specific cavity.

        Args:
            cavity_num: Which cavity we're updating (1-8)
            stats: A dictionary with new values for each statistic
                  (mean, std dev, min, max, outliers)
        """
        if cavity_num in self.stat_widgets:
            widgets = self.stat_widgets[cavity_num]
            # Updating each number, w/ formatting to 2 decimal places for easier readability
            widgets['mean'].setText(f"{stats['mean']:.2f}")
            widgets['std'].setText(f"{stats['std']:.2f}")
            widgets['min'].setText(f"{stats['min']:.2f}")
            widgets['max'].setText(f"{stats['max']:.2f}")
            widgets['outliers'].setText(str(stats['outliers']))


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
