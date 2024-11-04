from typing import Dict

import epics
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QLineEdit,
    QSpinBox, QCheckBox, QDoubleSpinBox, QSpacerItem, QSizePolicy
)
from lcls_tools.superconducting.sc_linac import MACHINE
from pydm import Display
from pydm.widgets import PyDMArchiverTimePlot

from utils.qt import make_rainbow
from utils.sc_linac.linac_utils import ALL_CRYOMODULES


class Plot(Display):
    def __init__(self, parent=None, args=None):
        # Initialize EPICS context before any CA operations
        if not hasattr(epics, '_ca_initialized'):
            epics.ca.initialize_libca()

        super().__init__(parent=parent)
        self.setWindowTitle("SRF Auto Plot")
        self.setup_ui()

        # Initialize UI components
        self.cm_combobox.addItems([""] + ALL_CRYOMODULES)
        self.plot.setShowLegend(True)

        # Using QTimer for delayed init of EPICS connections
        QTimer.singleShot(100, self.setup_connections)

    def setup_connections(self):
        """Setting up signal connections after a small delay to make sure EPICS is ready"""
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

    def setup_ui(self):
        self.verticalLayout = QVBoxLayout(self)

        # Top row
        self.horizontalLayout = QHBoxLayout()
        self.horizontalLayout.addWidget(QLabel("CM:"))
        self.cm_combobox = QComboBox()
        self.horizontalLayout.addWidget(self.cm_combobox)

        self.horizontalLayout.addWidget(QLabel("PV Suffix:"))
        self.suffix_line_edit = QLineEdit()
        self.horizontalLayout.addWidget(self.suffix_line_edit)

        self.horizontalLayout.addWidget(QLabel("Seconds:"))
        self.second_spinbox = QSpinBox()
        self.second_spinbox.setMaximum(6000)
        self.second_spinbox.setValue(600)
        self.horizontalLayout.addWidget(self.second_spinbox)

        self.autoscale_checkbox = QCheckBox("Auto Scale")
        self.autoscale_checkbox.setChecked(True)
        self.horizontalLayout.addWidget(self.autoscale_checkbox)

        self.horizontalLayout.addWidget(QLabel("Y Min"))
        self.ymin_spinbox = QDoubleSpinBox()
        self.ymin_spinbox.setRange(-500000, 500000)
        self.horizontalLayout.addWidget(self.ymin_spinbox)

        self.horizontalLayout.addWidget(QLabel("Y Max"))
        self.ymax_spinbox = QDoubleSpinBox()
        self.ymax_spinbox.setRange(-500000, 500000)
        self.horizontalLayout.addWidget(self.ymax_spinbox)

        self.verticalLayout.addLayout(self.horizontalLayout)

        # Middle row (Cavities)
        self.horizontalLayout_2 = QHBoxLayout()
        self.horizontalLayout_2.addItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        self.horizontalLayout_2.addWidget(QLabel("Cavities:"))

        self.c1_checkbox = QCheckBox("1")
        self.c2_checkbox = QCheckBox("2")
        self.c3_checkbox = QCheckBox("3")
        self.c4_checkbox = QCheckBox("4")
        self.c5_checkbox = QCheckBox("5")
        self.c6_checkbox = QCheckBox("6")
        self.c7_checkbox = QCheckBox("7")
        self.c8_checkbox = QCheckBox("8")

        for checkbox in [self.c1_checkbox, self.c2_checkbox, self.c3_checkbox, self.c4_checkbox,
                         self.c5_checkbox, self.c6_checkbox, self.c7_checkbox, self.c8_checkbox]:
            checkbox.setChecked(True)
            self.horizontalLayout_2.addWidget(checkbox)

        self.horizontalLayout_2.addItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        self.verticalLayout.addLayout(self.horizontalLayout_2)

        # Plot
        self.plot = PyDMArchiverTimePlot()
        self.plot.setTimeSpan(600)
        self.plot.setUpdatesAsynchronously(True)
        self.verticalLayout.addWidget(self.plot)

        self.setLayout(self.verticalLayout)

    def closeEvent(self, event):
        """Cleanup EPICS connections when closing"""
        try:
            epics.ca.finalize_libca()
        except:
            pass
        super().closeEvent(event)

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
        """Updating plot with selected cavities and settings."""
        try:
            self.plot.clearCurves()

            if not self.cm_combobox.currentText():
                return

            cm_obj = MACHINE.cryomodules[self.cm_combobox.currentText()]
            # Generating colors for each selected cavity
            colors = make_rainbow(len(self.selected_cavities))
            self._add_curves_to_plot(cm_obj, colors)
            self._update_plot_settings()
        except Exception as e:
            print(f"Error updating plot: {str(e)}")

    def _add_curves_to_plot(self, cm_obj, colors):
        """Getting data for each selected cavity."""
        try:
            for idx, cav_num in enumerate(self.selected_cavities):
                cavity = cm_obj.cavities[cav_num]
                r, g, b, alpha = colors[idx]
                rgb_color = QColor(r, g, b, alpha)
                self.plot.addYChannel(
                    y_channel=cavity.pv_addr(self.suffix_line_edit.text()),
                    useArchiveData=True,
                    color=rgb_color,
                )
        except Exception as e:
            print(f"Error adding curves: {str(e)}")

    def _update_plot_settings(self):
        """Updating plot settings based on user input."""
        self.plot.setAutoRangeY(self.autoscale_checkbox.isChecked())
        self.plot.setMinYRange(self.ymin_spinbox.value())
        self.plot.setMaxYRange(self.ymax_spinbox.value())
        self.plot.showLegend = True


if __name__ == '__main__':
    import sys
    from pydm import PyDMApplication

    app = PyDMApplication()
    window = Plot()
    window.show()
    sys.exit(app.exec_())
