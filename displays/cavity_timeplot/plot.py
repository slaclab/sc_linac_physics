from typing import Dict

from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QCheckBox
from lcls_tools.superconducting.sc_linac import MACHINE
from lcls_tools.superconducting.sc_linac_utils import ALL_CRYOMODULES
from timeplot import TimeplotGUI
from utils.qt import make_rainbow

class Plot(TimeplotGUI):
    def __init__(self, parent=None, args=None):
        super().__init__(parent=parent)

        # Initialize UI components
        self.cm_combobox.addItems(ALL_CRYOMODULES)
        self.plot.setShowLegend(True)

        # Connecting signals to slots
        self.suffix_line_edit.returnPressed.connect(self.update)
        self.cm_combobox.currentIndexChanged.connect(self.update)
        self.second_spinbox.valueChanged.connect(self.update_time)
        self.autoscale_checkbox.stateChanged.connect(self.update)
        self.ymin_spinbox.valueChanged.connect(self.update)
        self.ymax_spinbox.valueChanged.connect(self.update)

        # Map checkboxes to cavity numbers
        self.cavity_checkbox_map: Dict[QCheckBox, int] = {
            self.c1_checkbox: 1,
            self.c2_checkbox: 2,
            self.c3_checkbox: 3,
            self.c4_checkbox: 4,
            self.c5_checkbox: 5,
            self.c6_checkbox: 6,
            self.c7_checkbox: 7,
            self.c8_checkbox: 8,
        }
        # Connecting cavity checkboxes to update method
        for checkbox in self.cavity_checkbox_map.keys():
            checkbox.stateChanged.connect(self.update)

    @property
    def selected_cavities(self):
        selected_cavities = []
        for checkbox, cav_num in self.cavity_checkbox_map.items():
            if checkbox.isChecked():
                selected_cavities.append(cav_num)
        return selected_cavities

    def update_time(self):
        self.plot.setTimeSpan(self.second_spinbox.value())

    def update(self):
        """Updating the plot with selected cavities and settings."""
        self.plot.clearCurves()
        cm_obj = MACHINE.cryomodules[self.cm_combobox.currentText()]
        # Generating colors for each selected cavity
        colors = make_rainbow(len(self.selected_cavities))
        self._add_curves_to_plot(cm_obj, colors)
        self._update_plot_settings()

    def _add_curves_to_plot(self, cm_obj, colors):
        """Get data for each selected cavity."""
        for idx, cav_num in enumerate(self.selected_cavities):
            cavity = cm_obj.cavities[cav_num]
            r, g, b, alpha = colors[idx]
            rgb_color = QColor(r, g, b, alpha)
            self.plot.addYChannel(
                y_channel=cavity.pv_addr(self.suffix_line_edit.text()),
                useArchiveData=True,
                color=rgb_color,
            )

    def _update_plot_settings(self) -> None:
        """Update plot settings based on user input."""
        self.plot.setAutoRangeY(self.autoscale_checkbox.isChecked())
        self.plot.setMinYRange(self.ymin_spinbox.value())
        self.plot.setMaxYRange(self.ymax_spinbox.value())
        self.plot.showLegend()
