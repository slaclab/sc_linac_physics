import numpy as np
import h5py
import pyqtgraph as pg
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton

class H5Worker(QThread):
    dataReady = pyqtSignal(object, object)  # x, y

    def __init__(self, h5_path, x_path, y_path, start_idx=0, stop_idx=None, max_points=200_000):
        super().__init__()
        self.h5_path = h5_path
        self.x_path = x_path
        self.y_path = y_path
        self.start_idx = start_idx
        self.stop_idx = stop_idx
        self.max_points = max_points

    def run(self):
        import numpy as np
        import h5py

        with h5py.File(self.h5_path, "r") as f:
            xds = f[self.x_path]
            yds = f[self.y_path]

            i0 = self.start_idx
            i1 = self.stop_idx if self.stop_idx is not None else len(yds)

            x = xds[i0:i1]
            y = yds[i0:i1]

        n = len(y)
        if n > self.max_points:
            idx = np.linspace(0, n - 1, self.max_points).astype(int)
            x = x[idx]
            y = y[idx]

        self.dataReady.emit(x, y)

class Viewer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("H5 quick viewer")

        layout = QVBoxLayout(self)
        self.plot = pg.PlotWidget()
        self.curve = self.plot.plot(pen="y")
        self.plot.showGrid(x=True, y=True)
        layout.addWidget(self.plot)

        self.btn = QPushButton("Load & Plot")
        self.btn.clicked.connect(self.load)
        layout.addWidget(self.btn)

        self.worker = None

    def load(self):
        h5_path = "/path/to/quench_data_L0.h5"
        x_path = "/time"                 # change
        y_path = "/signals/current"      # change

        self.btn.setEnabled(False)

        self.worker = H5Worker(h5_path, x_path, y_path, start_idx=0, stop_idx=None)
        self.worker.dataReady.connect(self.update_plot)
        self.worker.start()

    def update_plot(self, x, y):
        self.curve.setData(x, y)
        # extra performance knobs:
        self.curve.setDownsampling(auto=True, method="peak")
        self.curve.setClipToView(True)

if __name__ == "__main__":
    app = QApplication([])
    v = Viewer()
    v.resize(900, 500)
    v.show()
    app.exec_()