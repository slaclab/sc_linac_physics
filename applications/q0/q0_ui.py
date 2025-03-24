from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QGridLayout, QGroupBox, QLabel, QSpinBox, QDoubleSpinBox, QPushButton
from pydm.widgets import PyDMSpinbox, PyDMLabel, PyDMPushButton


class Q0UI:
    """
    This is the python = of the q0.ui code file.
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

        # Create labels and spin boxes for measurement settings
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

        # Add Measurement Settings group box to main layout
        self.gridLayout_3.addWidget(self.groupBox, 2, 1, 1, 1)

        # Create Cryo Controls group box
        self.groupBox_3 = QGroupBox(Q0Measurement)
        self.groupBox_3.setObjectName("groupBox_3")
        self.groupBox_3.setFont(font)
        self.groupBox_3.setTitle("Cryo Controls")

        # Create layout for Cryo Controls group box
        self.gridLayout_2 = QGridLayout(self.groupBox_3)
        self.gridLayout_2.setObjectName("gridLayout_2")

        # Create Heater group box
        self.groupBox_8 = QGroupBox(self.groupBox_3)
        self.groupBox_8.setObjectName("groupBox_8")
        self.groupBox_8.setTitle("Heater")

        # Create layout for Heater group box
        self.gridLayout_10 = QGridLayout(self.groupBox_8)
        self.gridLayout_10.setObjectName("gridLayout_10")

        # Create layout for the Heater group box
        self.gridLayout_10 = QGridLayout(self.groupBox_8)
        self.gridLayout_10.setObjectName("gridLayout_10")

        # Create controls for Heater
        self.heater_setpoint_spinbox = PyDMSpinbox(self.groupBox_8)
        self.heater_setpoint_spinbox.setObjectName("heater_setpoint_spinbox")
        self.heater_setpoint_spinbox.setToolTip("")
        self.heater_setpoint_spinbox.setMaximum(160.0)
        self.heater_setpoint_spinbox.setSingleStep(10.0)
        self.heater_setpoint_spinbox.setProperty("showUnits", True)
        self.heater_setpoint_spinbox.setProperty("precisionFromPV", True)
        self.heater_setpoint_spinbox.setProperty("alarmSensitiveContent", False)
        self.heater_setpoint_spinbox.setProperty("alarmSensitiveBorder", False)
        self.heater_setpoint_spinbox.setProperty("channel", "")
        self.heater_setpoint_spinbox.setProperty("precision", 0)
        self.heater_setpoint_spinbox.setProperty("showStepExponent", False)
        self.heater_setpoint_spinbox.setProperty("writeOnPress", False)
        self.gridLayout_10.addWidget(self.heater_setpoint_spinbox, 1, 1, 1, 2)

        self.heater_readback_label = PyDMLabel(self.groupBox_8)
        self.heater_readback_label.setObjectName("heater_readback_label")
        self.heater_readback_label.setToolTip("")
        self.heater_readback_label.setProperty("showUnits", True)
        self.heater_readback_label.setProperty("alarmSensitiveContent", True)
        self.gridLayout_10.addWidget(self.heater_readback_label, 1, 3, 1, 1)

        self.heater_seq_button = PyDMPushButton(self.groupBox_8)
        self.heater_seq_button.setObjectName("heater_seq_button")
        self.heater_seq_button.setToolTip("")
        self.heater_seq_button.setText("Sequencer")
        self.heater_seq_button.setProperty("alarmSensitiveContent", False)
        self.heater_seq_button.setProperty("alarmSensitiveBorder", False)
        self.heater_seq_button.setProperty("channel", "")
        self.heater_seq_button.setProperty("passwordProtected", False)
        self.heater_seq_button.setProperty("password", "")
        self.heater_seq_button.setProperty("protectedPassword", "")
        self.heater_seq_button.setProperty("showConfirmDialog", False)
        self.heater_seq_button.setProperty("confirmMessage", "Are you sure you want to proceed?")
        self.heater_seq_button.setProperty("pressValue", "1")
        self.heater_seq_button.setProperty("releaseValue", "None")
        self.heater_seq_button.setProperty("relativeChange", False)
        self.heater_seq_button.setProperty("writeWhenRelease", False)
        self.gridLayout_10.addWidget(self.heater_seq_button, 0, 1, 1, 1)

        self.heater_mode_label = PyDMLabel(self.groupBox_8)
        self.heater_mode_label.setObjectName("heater_mode_label")
        self.heater_mode_label.setToolTip("")
        self.heater_mode_label.setProperty("alarmSensitiveContent", True)
        self.gridLayout_10.addWidget(self.heater_mode_label, 0, 3, 1, 1)

        self.label_5 = QLabel(self.groupBox_8)
        self.label_5.setObjectName("label_5")
        self.label_5.setText("Setpoint:")
        self.gridLayout_10.addWidget(self.label_5, 1, 0, 1, 1)

        self.heater_man_button = PyDMPushButton(self.groupBox_8)
        self.heater_man_button.setObjectName("heater_man_button")
        self.heater_man_button.setToolTip("")
        self.heater_man_button.setText("Manual")
        self.heater_man_button.setProperty("alarmSensitiveContent", False)
        self.heater_man_button.setProperty("alarmSensitiveBorder", False)
        self.heater_man_button.setProperty("channel", "")
        self.heater_man_button.setProperty("passwordProtected", False)
        self.heater_man_button.setProperty("password", "")
        self.heater_man_button.setProperty("protectedPassword", "")
        self.heater_man_button.setProperty("showConfirmDialog", False)
        self.heater_man_button.setProperty("confirmMessage", "Are you sure you want to proceed?")
        self.heater_man_button.setProperty("pressValue", "1")
        self.heater_man_button.setProperty("releaseValue", "None")
        self.heater_man_button.setProperty("relativeChange", False)
        self.heater_man_button.setProperty("writeWhenRelease", False)
        self.gridLayout_10.addWidget(self.heater_man_button, 0, 0, 1, 1)

        # Add Heater group box to the Cryo Controls layout
        self.gridLayout_2.addWidget(self.groupBox_8, 2, 3, 1, 1)

        # Create JT group box
        self.groupBox_4 = QGroupBox(self.groupBox_3)
        self.groupBox_4.setObjectName("groupBox_4")
        self.groupBox_4.setTitle("JT")

        # Create layout for the JT group box
        self.gridLayout_5 = QGridLayout(self.groupBox_4)
        self.gridLayout_5.setObjectName("gridLayout_5")

        # Create controls for JT
        self.label_6 = QLabel(self.groupBox_4)
        self.label_6.setObjectName("label_6")
        self.label_6.setText("Setpoint:")
        self.gridLayout_5.addWidget(self.label_6, 1, 0, 1, 1)

        self.jt_mode_label = PyDMLabel(self.groupBox_4)
        self.jt_mode_label.setObjectName("jt_mode_label")
        self.jt_mode_label.setToolTip("")
        self.jt_mode_label.setProperty("alarmSensitiveContent", True)
        self.gridLayout_5.addWidget(self.jt_mode_label, 0, 2, 1, 1)

        self.jt_setpoint_spinbox = PyDMSpinbox(self.groupBox_4)
        self.jt_setpoint_spinbox.setObjectName("jt_setpoint_spinbox")
        self.jt_setpoint_spinbox.setToolTip("")
        self.jt_setpoint_spinbox.setMinimum(5.0)
        self.jt_setpoint_spinbox.setMaximum(70.0)
        self.jt_setpoint_spinbox.setProperty("showUnits", True)
        self.jt_setpoint_spinbox.setProperty("precisionFromPV", True)
        self.jt_setpoint_spinbox.setProperty("alarmSensitiveContent", False)
        self.jt_setpoint_spinbox.setProperty("alarmSensitiveBorder", False)
        self.jt_setpoint_spinbox.setProperty("channel", "")
        self.jt_setpoint_spinbox.setProperty("precision", 0)
        self.jt_setpoint_spinbox.setProperty("showStepExponent", False)
        self.jt_setpoint_spinbox.setProperty("writeOnPress", False)
        self.gridLayout_5.addWidget(self.jt_setpoint_spinbox, 1, 1, 1, 1)

        self.jt_setpoint_readback = PyDMLabel(self.groupBox_4)
        self.jt_setpoint_readback.setObjectName("jt_setpoint_readback")
        self.jt_setpoint_readback.setToolTip("")
        self.jt_setpoint_readback.setProperty("showUnits", True)
        self.jt_setpoint_readback.setProperty("alarmSensitiveContent", True)
        self.gridLayout_5.addWidget(self.jt_setpoint_readback, 1, 2, 1, 1)

        self.jt_man_button = PyDMPushButton(self.groupBox_4)
        self.jt_man_button.setObjectName("jt_man_button")
        self.jt_man_button.setToolTip("")
        self.jt_man_button.setText("Manual")
        self.jt_man_button.setProperty("alarmSensitiveContent", False)
        self.jt_man_button.setProperty("alarmSensitiveBorder", False)
        self.jt_man_button.setProperty("channel", "")
        self.jt_man_button.setProperty("passwordProtected", False)
        self.jt_man_button.setProperty("password", "")
        self.jt_man_button.setProperty("protectedPassword", "")
        self.jt_man_button.setProperty("showConfirmDialog", False)
        self.jt_man_button.setProperty("confirmMessage", "Are you sure you want to proceed?")
        self.jt_man_button.setProperty("pressValue", "1")
        self.jt_man_button.setProperty("releaseValue", "None")
        self.jt_man_button.setProperty("relativeChange", False)
        self.jt_man_button.setProperty("writeWhenRelease", False)
        self.gridLayout_5.addWidget(self.jt_man_button, 0, 0, 1, 1)

        self.jt_auto_button = PyDMPushButton(self.groupBox_4)
        self.jt_auto_button.setObjectName("jt_auto_button")
        self.jt_auto_button.setToolTip("")
        self.jt_auto_button.setText("Auto")
        self.jt_auto_button.setProperty("alarmSensitiveContent", False)
        self.jt_auto_button.setProperty("alarmSensitiveBorder", False)
        self.jt_auto_button.setProperty("channel", "")
        self.jt_auto_button.setProperty("passwordProtected", False)
        self.jt_auto_button.setProperty("password", "")
        self.jt_auto_button.setProperty("protectedPassword", "")
        self.jt_auto_button.setProperty("showConfirmDialog", False)
        self.jt_auto_button.setProperty("confirmMessage", "Are you sure you want to proceed?")
        self.jt_auto_button.setProperty("pressValue", "1")
        self.jt_auto_button.setProperty("releaseValue", "None")
        self.jt_auto_button.setProperty("relativeChange", False)
        self.jt_auto_button.setProperty("writeWhenRelease", False)
        self.gridLayout_5.addWidget(self.jt_auto_button, 0, 1, 1, 1)

        # Add JT group box to Cryo Controls layout
        self.gridLayout_2.addWidget(self.groupBox_4, 2, 1, 1, 2)

        # Add "Restore Cryo to Standard Values" button
        self.restore_cryo_button = QPushButton(self.groupBox_3)
        self.restore_cryo_button.setObjectName("restore_cryo_button")
        self.restore_cryo_button.setText("Restore Cryo to Standard Values")
        self.gridLayout_2.addWidget(self.restore_cryo_button, 3, 1, 1, 3)

        # Add Cryo Controls group box to the main layout
        self.gridLayout_3.addWidget(self.groupBox_3, 2, 0, 1, 1)

        # Create Calibration group box
        self.groupBox_2 = QGroupBox(Q0Measurement)
        self.groupBox_2.setObjectName("groupBox_2")
        self.groupBox_2.setFont(font)
        self.groupBox_2.setTitle("Calibration")

        # Create layout for Calibration group box
        self.gridLayout_4 = QGridLayout(self.groupBox_2)
        self.gridLayout_4.setObjectName("gridLayout_4")

        # Create Reference Parameters group box
        self.manual_cryo_groupbox = QGroupBox(self.groupBox_2)
        self.manual_cryo_groupbox.setObjectName("manual_cryo_groupbox")
        self.manual_cryo_groupbox.setTitle("Reference Parameters")
        self.manual_cryo_groupbox.setCheckable(False)
        self.manual_cryo_groupbox.setChecked(False)

        # Create layout for Reference Parameters group box
        self.gridLayout = QGridLayout(self.manual_cryo_groupbox)
        self.gridLayout.setObjectName("gridLayout")

        # Create controls for Reference Parameters
        self.jt_pos_spinbox = QDoubleSpinBox(self.manual_cryo_groupbox)
        self.jt_pos_spinbox.setObjectName("jt_pos_spinbox")
        self.jt_pos_spinbox.setValue(40.0)
        self.gridLayout.addWidget(self.jt_pos_spinbox, 1, 1, 1, 1)

        self.label_2 = QLabel(self.manual_cryo_groupbox)
        self.label_2.setObjectName("label_2")
        self.label_2.setText("Electric Heat Load Offset")
        self.gridLayout.addWidget(self.label_2, 2, 0, 1, 1)

        self.label = QLabel(self.manual_cryo_groupbox)
        self.label.setObjectName("label")
        self.label.setText("JT Valve Position")
        self.gridLayout.addWidget(self.label, 1, 0, 1, 1)

        self.ref_heat_spinbox = QDoubleSpinBox(self.manual_cryo_groupbox)
        self.ref_heat_spinbox.setObjectName("ref_heat_spinbox")
        self.ref_heat_spinbox.setValue(48.0)
        self.gridLayout.addWidget(self.ref_heat_spinbox, 2, 1, 1, 1)

        self.setup_param_button = QPushButton(self.manual_cryo_groupbox)
        self.setup_param_button.setObjectName("setup_param_button")
        self.setup_param_button.setEnabled(True)
        self.setup_param_button.setToolTip("Sets the heater to manual at 48 so that the JT can settle")
        self.setup_param_button.setText("Set Up for New Parameters")
        self.gridLayout.addWidget(self.setup_param_button, 0, 0, 1, 2)

        # Add Reference Parameters group box to Calibration layout
        self.gridLayout_4.addWidget(self.manual_cryo_groupbox, 1, 0, 4, 1)

        # Create label for status
        