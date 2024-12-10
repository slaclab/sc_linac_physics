from PyQt5.QtWidgets import QWidget, QVBoxLayout, QMainWindow
from matplotlib.backends.backend_template import FigureCanvas
from matplotlib.figure import Figure


class PlotWidget(QWidget):
    """Widget for displaying measurement plots"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()
        self.figure = Figure(figsize=(8, 8))
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)

        # Create subplots for different visualizations
        self.axes = {
            'fft': self.figure.add_subplot(311, title='FFT Analysis'),
            'hist': self.figure.add_subplot(312, title='Histogram'),
            'spec': self.figure.add_subplot(313, title='Spectrogram')
        }

        # Set proper plot ranges following the requirements
        self.axes['fft'].set_xlim(0, 150)  # FFT up to 150Hz
        self.axes['hist'].set_xlim(-200, 200)  # -200 to 200 Hz range

        self.figure.tight_layout()
        self.setLayout(layout)


class MicrophonicsGUI(QMainWindow):
    """Main GUI window for microphonics measurements"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Microphonics Measurement GUI")

    def setup_ui(self):
        pass

    def update_cryomodule_list(self):
        """Update cryomodule list based on selected linac"""
        linac = self.linac_combo.currentText()
        self.cryo_combo.clear()

        # Using correct cryomodule ranges from hardware requirements
        ranges = {
            'L0B': ['01'],
            'L1B': ['02', '03', 'H1', 'H2'],
            'L2B': [f'{i:02d}' for i in range(4, 16)],
            'L3B': [f'{i:02d}' for i in range(16, 36)]
        }

        self.cryo_combo.addItems(ranges[linac])
        pass

    def update_cavity_list(self):
        """Update cavity checkboxes"""
        pass

    def get_selected_cavities(self) -> List[int]:
        """Get list of selected cavity numbers"""
        pass
