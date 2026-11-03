"""Display of the H1/H2 stepper response curves, with newer runs on top.

Shows a cavity's packaged curve (microsteps from cold landing against real
detune) and, on request, the tuning runs archived since the curves were
fitted. Each run gets its actual / curve microsteps ratio; outside
RATIO_BAND suggests the curve needs refitting. Read-only; writes no PV.
"""

import threading
from datetime import datetime
from typing import Dict, List

import pyqtgraph as pg
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)
from pydm import Display

from sc_linac_physics.displays.hl_tuner_curves import runs as R

RUN_COLORS = ["#e69f00", "#56b4e9", "#009e73", "#f0e442", "#cc79a7"]


def cavity_label(prefix: str) -> str:
    """'H1 cav 1' for ``ACCL:L1B:H110:``."""
    return f"{prefix[-5:-3]} cav {prefix[-3]}"


class HLTunerCurvesDisplay(Display):
    # (cavity prefix, runs) or (cavity prefix, error message). Emitted from
    # the fetch thread; Qt runs the handler on the main thread.
    runs_ready = pyqtSignal(str, object)
    fetch_failed = pyqtSignal(str, str)

    def __init__(
        self, parent=None, args=None, macros=None, curves_csv=R.CURVES_CSV
    ):
        super().__init__(parent=parent, args=args, macros=macros)
        self.setWindowTitle("HL Tuner Curves")
        self.curves = R.load_curves(curves_csv)
        self.fetch_start = R.archive_end(curves_csv)
        self.runs: Dict[str, List[R.Run]] = {}

        self.cavity_combo = QComboBox()
        for prefix in self.curves:
            self.cavity_combo.addItem(cavity_label(prefix), prefix)
        self.fetch_button = QPushButton("Fetch new runs")
        self.status = QLabel()
        self.plot = pg.PlotWidget()
        self.plot.setLabel(
            "bottom", "Real detune (CHIRP:DF + FREQ_OFFSET)", "Hz"
        )
        self.plot.setLabel("left", "Microsteps from cold landing")
        self.plot.addLegend()
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(
            ["Run start", "Segments", "Actual / curve steps"]
        )

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Cavity:"))
        controls.addWidget(self.cavity_combo)
        controls.addWidget(self.fetch_button)
        controls.addWidget(self.status, stretch=1)
        layout = QVBoxLayout()
        layout.addLayout(controls)
        layout.addWidget(self.plot, stretch=3)
        layout.addWidget(self.table, stretch=1)
        self.setLayout(layout)

        self.cavity_combo.currentIndexChanged.connect(self.redraw)
        self.fetch_button.clicked.connect(self.fetch)
        self.runs_ready.connect(self._on_runs_ready)
        self.fetch_failed.connect(self._on_fetch_failed)
        self.redraw()

    @property
    def prefix(self) -> str:
        return self.cavity_combo.currentData()

    def fetch(self):
        """Fetch this cavity's runs since the curves' archive end.

        On a daemon thread: each PV is fetched a quarter at a time, and a
        failing query retries for minutes, so it can't run on the Qt main
        thread. Not QThread (outlived owners crashed test workers, #307,
        #308) and not an executor (joined at exit, so a stuck fetch would
        keep the display from quitting).
        """
        prefix = self.prefix
        self.fetch_button.setEnabled(False)
        self.status.setText(
            f"Fetching {cavity_label(prefix)} runs since"
            f" {self.fetch_start:%Y-%m-%d}..."
        )
        threading.Thread(
            target=self._fetch,
            args=(prefix, self.fetch_start, datetime.now()),
            daemon=True,
            name="hl-tuner-runs-fetch",
        ).start()

    def _fetch(self, prefix, start, end):
        """Runs on the fetch thread; hands the result to the main thread."""
        try:
            result = R.fetch_runs(prefix, start, end)
        except Exception as e:
            R.logger.error(f"HL tuner run fetch failed for {prefix}: {e}")
            try:
                self.fetch_failed.emit(prefix, str(e))
            except RuntimeError:  # the display was deleted mid-fetch
                pass
            return
        try:
            self.runs_ready.emit(prefix, result)
        except RuntimeError:
            pass

    def _on_runs_ready(self, prefix, runs):
        self.runs[prefix] = runs
        self.fetch_button.setEnabled(True)
        self.status.setText(f"{cavity_label(prefix)}: {len(runs)} new runs")
        self.redraw()

    def _on_fetch_failed(self, prefix, message):
        self.fetch_button.setEnabled(True)
        self.status.setText(f"{cavity_label(prefix)} fetch failed: {message}")

    def redraw(self):
        """Draw the selected cavity's curve and any runs fetched for it."""
        curve = self.curves[self.prefix]
        self.plot.clear()
        self.plot.plot(
            curve.real_detune_hz.to_numpy(),
            curve.usteps_from_cold.to_numpy(),
            pen=pg.mkPen("w", width=2),
            name="Packaged curve",
        )
        gaps = curve[~curve.covered]
        self.plot.plot(
            gaps.real_detune_hz.to_numpy(),
            gaps.usteps_from_cold.to_numpy(),
            pen=None,
            symbol="x",
            symbolBrush="r",
            symbolPen="r",
            name="No data (filled)",
        )
        runs = self.runs.get(self.prefix, [])
        self.table.setRowCount(len(runs))
        for row, run in enumerate(runs):
            ratio = R.step_ratio(run, curve)
            color = RUN_COLORS[row % len(RUN_COLORS)]
            x, y = R.overlay(run, curve)
            self.plot.plot(
                x,
                y,
                pen=pg.mkPen(color),
                symbol="o",
                symbolSize=5,
                symbolBrush=color,
                name=f"{run.start:%Y-%m-%d %H:%M}",
            )
            cells = [
                f"{run.start:%Y-%m-%d %H:%M}",
                str(len(run.segments)),
                "-" if ratio is None else f"{ratio:.2f}",
            ]
            for col, text in enumerate(cells):
                item = QTableWidgetItem(text)
                if (
                    col == 2
                    and ratio is not None
                    and not (R.RATIO_BAND[0] <= ratio <= R.RATIO_BAND[1])
                ):
                    item.setBackground(pg.mkColor("#c0392b"))
                    item.setToolTip(
                        f"Outside {R.RATIO_BAND[0]}-{R.RATIO_BAND[1]}:"
                        " curve may need refitting"
                    )
                self.table.setItem(row, col, item)
        self.table.resizeColumnsToContents()
