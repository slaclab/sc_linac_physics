from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QLineEdit,
    QSpinBox, QCheckBox, QDoubleSpinBox, QSpacerItem, QSizePolicy
)
from pydm.widgets import PyDMArchiverTimePlot
from pydm import Display

class TimeplotGUI(Display):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setWindowTitle("SRF Auto Plot")
        self.setup_ui()

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

