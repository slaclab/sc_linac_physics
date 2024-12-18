from PyQt5 import QtCore
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QGroupBox, QVBoxLayout, QGridLayout
from edmbutton import PyDMEDMDisplayButton
from pydm.widgets import PyDMArchiverTimePlot

from applications.tuning.cavity_section import CavitySection
from utils.qt import make_rainbow
from utils.sc_linac.rack import Rack


class RackSection:
    def __init__(self, rack: Rack):
        self.detune_plot: PyDMArchiverTimePlot = PyDMArchiverTimePlot()
        self.detune_plot.addAxis(
            name="detune", orientation="left", plot_data_item=None, label="Detune (Hz)"
        )
        self.detune_plot.addAxis(
            name="steps", orientation="right", plot_data_item=None, label="Steps"
        )
        self.detune_plot.setTimeSpan(3600)
        self.detune_plot.setUpdatesAsynchronously(True)
        self.detune_plot.setPlotTitle("Cavity Detunes")
        self.rack = rack
        self.populate_detune_plot()
        rack_file = f"/usr/local/lcls/tools/edm/display/llrf/rf_srf_freq_scan_rack{rack.rack_name}.edl"
        self.edm_screen: PyDMEDMDisplayButton = PyDMEDMDisplayButton(filename=rack_file)
        self.edm_screen.setText("EDM Rack Screen")
        self.edm_screen.macros = list(rack.cavities.values())[0].edm_macro_string
        self.groupbox = QGroupBox(f"{rack}")
        layout = QVBoxLayout()
        self.groupbox.setLayout(layout)

        cav_layout = QGridLayout()

        for idx, cavity in enumerate(list(rack.cavities.values())):
            cav_layout.addWidget(CavitySection(cavity).groupbox, int(idx / 2), idx % 2)

        layout.addLayout(cav_layout)

        layout.addWidget(self.edm_screen)
        layout.addWidget(self.detune_plot)

    def populate_detune_plot(self):
        detune_pvs = []
        for cavity in self.rack.cavities.values():
            detune_pvs.append(
                (
                    cavity.detune_chirp_pv,
                    cavity.df_cold_pv,
                    cavity.stepper_tuner.step_signed_pv,
                )
            )
        colors = make_rainbow(len(detune_pvs))
        for idx, (detune_pv, df_cold_pv, step_pv) in enumerate(detune_pvs):
            r, g, b, alpha = colors[idx]
            rga_color = QColor(r, g, b, alpha)
            detune_curve = self.detune_plot.addYChannel(
                y_channel=detune_pv,
                useArchiveData=True,
                color=rga_color,
                yAxisName="detune",
            )
            detune_curve.setUpdatesAsynchronously(True)
            self.detune_plot.addLegendItem(
                detune_curve,
                detune_pv,
            )
            df_cold_curve = self.detune_plot.addYChannel(
                y_channel=df_cold_pv,
                useArchiveData=True,
                color=rga_color,
                lineStyle=QtCore.Qt.DashLine,
                yAxisName="detune",
            )
            df_cold_curve.setUpdatesAsynchronously(True)
            self.detune_plot.addLegendItem(
                df_cold_curve,
                df_cold_pv,
            )
            step_curve = self.detune_plot.addYChannel(
                y_channel=step_pv,
                useArchiveData=True,
                color=rga_color,
                lineStyle=QtCore.Qt.DotLine,
                yAxisName="steps",
            )
            self.detune_plot.addLegendItem(
                step_curve,
                step_pv,
            )
            step_curve.setUpdatesAsynchronously(True)

        self.detune_plot.setShowLegend(True)
