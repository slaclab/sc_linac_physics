from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QGridLayout, QGroupBox, QLabel, QSpinBox, QDoubleSpinBox


class Q0UI:
    """
    This is the python equivalent of the q0.ui code file.
    This class makes all the widgets and sets their properties
    maintaining the same widget names & hierarchy from the orginal UI file.

    """

    def setupUi(self, Q0Measurement):
        """
        Set up the UI for the Q0UI widget.
        Args: Q0UI

        """
        # Setup main widget properties
        Q0Measurement.setObjectName("Q0Measurement")
        Q0Measurement.resize(884, 657)
        Q0Measurement.setWindowTitle("Q0 Measurement")

        # Create main grid layout
        self.gridLayout_3 = QGridLayout(Q0Measurement)
        self.gridLayout_3.setObjectName("gridLayout_3")

        # Create measurement settings group box
        self.groupBox = QGroupBox(Q0Measurement)
        self.groupBox.setObjectName("groupBox")
        font = QFont()
        font.setBold(True)
        font.setWeight(75)
        self.groupBox.setFont(font)
        self.groupBox.setTitle("Measurement Settings")

        # Create layout for the measurement settings
        self.gridLayout_6 = QGridLayout(self.groupBox)
        self.gridLayout_6.setObjectName("gridLayout_6")

        # Create labels and spin boxes for the measurement settings
        self.label_9 = QLabel(self.groupBox)
        self.label_9.setObjectName("label_9")
        self.label_9.setText("Starting liquid level:")
        self.gridLayout_6.addWidget(self.label_9, 0, 0, 1, 1)

        self.label_10 = QLabel(self.groupBox)
        self.label_10.setObjectName("label_10")
        self.label_10.setText("Desired liquid level drop:")
        self.label_10.setWordWrap(False)
        self.gridLayout_6.addWidget(self.label_10, 1, 0, 1, 1)

        self.ll_drop_spinbox = QDoubleSpinBox(self.groupBox)
        self.ll_drop_spinbox.setObjectName("ll_drop_spinbox")
        self.ll_drop_spinbox.setMinimum(1.0)
        self.ll_drop_spinbox.setMaximum(3.0)
        self.ll_drop_spinbox.setValue(3.0)
        self.gridLayout_6.addWidget(self.ll_drop_spinbox, 1, 1, 1, 1)

        self.ll_start_spinbox = QDoubleSpinBox(self.groupBox)
        self.ll_start_spinbox.setObjectName("ll_start_spinbox")
        self.ll_start_spinbox.setMinimum(90.0)
        self.ll_start_spinbox.setMaximum(93.0)
        self.ll_start_spinbox.setValue(93.0)
        self.gridLayout_6.addWidget(self.ll_start_spinbox, 0, 1, 1, 1)

        self.label_11 = QLabel(self.groupBox)
        self.label_11.setObjectName("label_11")
        self.label_11.setText("Number of liquid level points to average:")
        self.label_11.setWordWrap(True)
        self.gridLayout_6.addWidget(self.label_11, 2, 0, 1, 1)

        self.ll_avg_spinbox = QSpinBox(self.groupBox)
        self.ll_avg_spinbox.setObjectName("ll_avg_spinbox")
        self.ll_avg_spinbox.setValue(10)
        self.gridLayout_6.addWidget(self.ll_avg_spinbox, 2, 1, 1, 1)

        # Add Measurement Settings group box to the main layout
        self.gridLayout_3.addWidget(self.groupBox, 2, 1, 1, 1)

        # Create the Cryo Controls group box
        self.groupBox_3 = QGroupBox(Q0Measurement)
        self.groupBox_3.setObjectName("groupBox_3")
        self.groupBox_3.setFont(font)
        self.groupBox_3.setTitle("Cryo Controls")

        # Create layout for the Cryo Controls group box
        self.gridLayout_2 = QGridLayout(self.groupBox_3)
        self.gridLayout_2.setObjectName("gridLayout_2")

        # Create Heater group box
        self.groupBox_8 = QGroupBox(self.groupBox_3)
        self.groupBox_8.setObjectName("groupBox_8")
        self.groupBox_8.setTitle("Heater")

        # Create layout for the Heater group box
        self.gridLayout_10 = QGridLayout(self.groupBox_8)
        self.gridLayout_10.setObjectName("gridLayout_10")

        # Create controls for the Heater
