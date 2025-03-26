from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtWidgets import QGridLayout, QGroupBox, QLabel, QSpinBox, QDoubleSpinBox, QPushButton, QVBoxLayout, \
    QHBoxLayout, QSpacerItem, QSizePolicy, QComboBox
from pydm.widgets import PyDMSpinbox, PyDMLabel, PyDMPushButton, PyDMByteIndicator


class Q0UI:
    """
    Python implementation of the ui q0 file.
    This class makes all the widgets and maintains same widget names
    & hierarchy from the original UI file.

    """

    def __init__(self, parent=None):
        self.setupUi(parent)

    def setupUi(self, Q0Measurement):
        """
        Sets up UI for the Q0 Measurement widget.

        Args:
            Q0Measurement: The parent widget to apply the UI to
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

        # Add Heater group box to Cryo Controls layout
        self.gridLayout_2.addWidget(self.groupBox_8, 2, 3, 1, 1)

        # Create JT group box
        self.groupBox_4 = QGroupBox(self.groupBox_3)
        self.groupBox_4.setObjectName("groupBox_4")
        self.groupBox_4.setTitle("JT")

        # Create layout for JT group box
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

        # Add Cryo Controls group box to main layout
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
        self.label_8 = QLabel(self.groupBox_2)
        self.label_8.setObjectName("label_8")
        self.label_8.setText("Status:")
        self.label_8.setAlignment(Qt.AlignRight | Qt.AlignTrailing | Qt.AlignVCenter)
        self.gridLayout_4.addWidget(self.label_8, 5, 0, 1, 1)

        # Create Settings group box
        self.groupBox_5 = QGroupBox(self.groupBox_2)
        self.groupBox_5.setObjectName("groupBox_5")
        self.groupBox_5.setTitle("Settings")

        # Create layout for Settings group box
        self.gridLayout_7 = QGridLayout(self.groupBox_5)
        self.gridLayout_7.setObjectName("gridLayout_7")

        # Create controls for Settings
        self.label_12 = QLabel(self.groupBox_5)
        self.label_12.setObjectName("label_12")
        self.label_12.setText("Starting heater setpoint:")
        self.gridLayout_7.addWidget(self.label_12, 0, 0, 1, 1)

        self.label_13 = QLabel(self.groupBox_5)
        self.label_13.setObjectName("label_13")
        self.label_13.setText("End heater setpoint:")
        self.gridLayout_7.addWidget(self.label_13, 1, 0, 1, 1)

        self.label_14 = QLabel(self.groupBox_5)
        self.label_14.setObjectName("label_14")
        self.label_14.setText("Number of data points:")
        self.gridLayout_7.addWidget(self.label_14, 2, 0, 1, 1)

        self.start_heat_spinbox = QDoubleSpinBox(self.groupBox_5)
        self.start_heat_spinbox.setObjectName("start_heat_spinbox")
        self.start_heat_spinbox.setMinimum(75.0)
        self.start_heat_spinbox.setMaximum(130.0)
        self.start_heat_spinbox.setValue(130.0)
        self.gridLayout_7.addWidget(self.start_heat_spinbox, 0, 1, 1, 1)

        self.end_heat_spinbox = QDoubleSpinBox(self.groupBox_5)
        self.end_heat_spinbox.setObjectName("end_heat_spinbox")
        self.end_heat_spinbox.setMinimum(130.0)
        self.end_heat_spinbox.setMaximum(160.0)
        self.end_heat_spinbox.setValue(160.0)
        self.gridLayout_7.addWidget(self.end_heat_spinbox, 1, 1, 1, 1)

        self.num_cal_points_spinbox = QSpinBox(self.groupBox_5)
        self.num_cal_points_spinbox.setObjectName("num_cal_points_spinbox")
        self.num_cal_points_spinbox.setMaximum(20)
        self.num_cal_points_spinbox.setValue(5)
        self.gridLayout_7.addWidget(self.num_cal_points_spinbox, 2, 1, 1, 1)

        # Add Settings group box to Calibration layout
        self.gridLayout_4.addWidget(self.groupBox_5, 1, 1, 4, 1)

        # Create "Abort Calibration" button
        self.abort_cal_button = QPushButton(self.groupBox_2)
        self.abort_cal_button.setObjectName("abort_cal_button")
        self.abort_cal_button.setStyleSheet("color: rgb(252, 33, 37);")
        self.abort_cal_button.setText("Abort Calibration")
        self.gridLayout_4.addWidget(self.abort_cal_button, 4, 2, 1, 1)

        # Create "Show Calibration Data" button
        self.show_cal_data_button = QPushButton(self.groupBox_2)
        self.show_cal_data_button.setObjectName("show_cal_data_button")
        self.show_cal_data_button.setEnabled(False)
        self.show_cal_data_button.setText("Show Calibration Data")
        self.gridLayout_4.addWidget(self.show_cal_data_button, 3, 2, 1, 1)

        # Create "Take New Calibration" button
        self.new_cal_button = QPushButton(self.groupBox_2)
        self.new_cal_button.setObjectName("new_cal_button")
        self.new_cal_button.setText("Take New Calibration")
        self.gridLayout_4.addWidget(self.new_cal_button, 2, 2, 1, 1)

        # Create "Load Existing Calibration" button
        self.load_cal_button = QPushButton(self.groupBox_2)
        self.load_cal_button.setObjectName("load_cal_button")
        self.load_cal_button.setText("Load Existing Calibration")
        self.gridLayout_4.addWidget(self.load_cal_button, 1, 2, 1, 1)

        # Create calibration status label
        self.cal_status_label = QLabel(self.groupBox_2)
        self.cal_status_label.setObjectName("cal_status_label")
        self.cal_status_label.setText("")
        self.cal_status_label.setWordWrap(True)
        self.gridLayout_4.addWidget(self.cal_status_label, 5, 1, 1, 2)

        # Add Calibration group box to the main layout
        self.gridLayout_3.addWidget(self.groupBox_2, 4, 0, 1, 2)

        # Create RF Measurement group box
        self.rf_groupbox = QGroupBox(Q0Measurement)
        self.rf_groupbox.setObjectName("rf_groupbox")
        self.rf_groupbox.setEnabled(False)
        self.rf_groupbox.setFont(font)
        self.rf_groupbox.setTitle("RF Measurement")

        # Create layout for RF Measurement group box
        self.gridLayout_8 = QGridLayout(self.rf_groupbox)
        self.gridLayout_8.setObjectName("gridLayout_8")

        # Create controls for RF Measurement
        self.load_rf_button = QPushButton(self.rf_groupbox)
        self.load_rf_button.setObjectName("load_rf_button")
        self.load_rf_button.setText("Load Existing RF Measurement")
        self.gridLayout_8.addWidget(self.load_rf_button, 2, 0, 1, 1)

        self.new_rf_button = QPushButton(self.rf_groupbox)
        self.new_rf_button.setObjectName("new_rf_button")
        self.new_rf_button.setText("Take New RF Measurement")
        self.gridLayout_8.addWidget(self.new_rf_button, 2, 1, 1, 1)

        self.rf_cal_spinbox = QDoubleSpinBox(self.rf_groupbox)
        self.rf_cal_spinbox.setObjectName("rf_cal_spinbox")
        self.rf_cal_spinbox.setEnabled(False)
        self.rf_cal_spinbox.setMinimum(24.0)
        self.rf_cal_spinbox.setMaximum(112.0)
        self.rf_cal_spinbox.setValue(80.0)
        self.gridLayout_8.addWidget(self.rf_cal_spinbox, 1, 1, 1, 1)

        self.label_7 = QLabel(self.rf_groupbox)
        self.label_7.setObjectName("label_7")
        self.label_7.setText("Calibration Heat Load:")
        self.gridLayout_8.addWidget(self.label_7, 1, 0, 1, 1)

        self.label_15 = QLabel(self.rf_groupbox)
        self.label_15.setObjectName("label_15")
        self.label_15.setText("Status:")
        self.label_15.setAlignment(Qt.AlignRight | Qt.AlignTrailing | Qt.AlignVCenter)
        self.gridLayout_8.addWidget(self.label_15, 4, 0, 1, 1)

        self.show_rf_button = QPushButton(self.rf_groupbox)
        self.show_rf_button.setObjectName("show_rf_button")
        self.show_rf_button.setText("Show RF Data")
        self.gridLayout_8.addWidget(self.show_rf_button, 3, 0, 1, 1)

        self.abort_rf_button = QPushButton(self.rf_groupbox)
        self.abort_rf_button.setObjectName("abort_rf_button")
        self.abort_rf_button.setStyleSheet("color: rgb(252, 33, 37);")
        self.abort_rf_button.setText("Abort RF Measurement")
        self.gridLayout_8.addWidget(self.abort_rf_button, 3, 1, 1, 1)

        # Create Cavity Amplitudes group box
        self.groupBox_7 = QGroupBox(self.rf_groupbox)
        self.groupBox_7.setObjectName("groupBox_7")
        self.groupBox_7.setTitle("Cavity Amplitudes")

        # Create layout for Cavity Amplitudes group box
        self.verticalLayout = QVBoxLayout(self.groupBox_7)
        self.verticalLayout.setObjectName("verticalLayout")

        # Create cavity layout
        self.cavity_layout = QGridLayout()
        self.cavity_layout.setObjectName("cavity_layout")
        self.verticalLayout.addLayout(self.cavity_layout)

        # Add Cavity Amplitudes group box to RF Measurement layout
        self.gridLayout_8.addWidget(self.groupBox_7, 0, 0, 1, 2)

        # Create RF status label
        self.rf_status_label = QLabel(self.rf_groupbox)
        self.rf_status_label.setObjectName("rf_status_label")
        self.rf_status_label.setText("")
        self.rf_status_label.setWordWrap(True)
        self.gridLayout_8.addWidget(self.rf_status_label, 4, 1, 1, 1)

        # Add RF Measurement group box to main layout
        self.gridLayout_3.addWidget(self.rf_groupbox, 5, 0, 1, 2)

        # Create "Cryomodule:" selection layout
        self.horizontalLayout_4 = QHBoxLayout()
        self.horizontalLayout_4.setObjectName("horizontalLayout_4")

        # Add spacer to the layout
        self.horizontalSpacer_3 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.horizontalLayout_4.addItem(self.horizontalSpacer_3)

        # Create "Cryomodule:" label
        self.label_4 = QLabel(Q0Measurement)
        self.label_4.setObjectName("label_4")
        sizePolicy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label_4.sizePolicy().hasHeightForWidth())
        self.label_4.setSizePolicy(sizePolicy)
        self.label_4.setFont(font)
        self.label_4.setText("Cryomodule:")
        self.horizontalLayout_4.addWidget(self.label_4)

        # Create cryomodule combo box
        self.cm_combobox = QComboBox(Q0Measurement)
        self.cm_combobox.setObjectName("cm_combobox")
        self.cm_combobox.setFont(font)
        self.horizontalLayout_4.addWidget(self.cm_combobox)

        # Add spacer to layout
        self.horizontalSpacer_4 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.horizontalLayout_4.addItem(self.horizontalSpacer_4)

        # Create "Cryo Permission:" label
        self.label_3 = QLabel(Q0Measurement)
        self.label_3.setObjectName("label_3")
        self.label_3.setText("Cryo Permission:")
        self.horizontalLayout_4.addWidget(self.label_3)

        # Create cryo permission byte indicator
        self.perm_byte = PyDMByteIndicator(Q0Measurement)
        self.perm_byte.setObjectName("perm_byte")
        sizePolicy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.perm_byte.sizePolicy().hasHeightForWidth())
        self.perm_byte.setSizePolicy(sizePolicy)
        self.perm_byte.setToolTip("")
        self.perm_byte.setProperty("offColor", QColor(252, 33, 37))
        self.perm_byte.setProperty("showLabels", False)
        self.horizontalLayout_4.addWidget(self.perm_byte)

        # Create cryo permission label
        self.perm_label = PyDMLabel(Q0Measurement)
        self.perm_label.setObjectName("perm_label")
        self.perm_label.setToolTip("")
        self.perm_label.setProperty("alarmSensitiveContent", True)
        self.horizontalLayout_4.addWidget(self.perm_label)

        # Add spacer to layout
        self.horizontalSpacer_2 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.horizontalLayout_4.addItem(self.horizontalSpacer_2)

        # Add cryomodule selection layout to main layout
        self.gridLayout_3.addLayout(self.horizontalLayout_4, 1, 0, 1, 2)

        # Create top header label
        self.label_16 = QLabel(Q0Measurement)
        self.label_16.setObjectName("label_16")
        sizePolicy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label_16.sizePolicy().hasHeightForWidth())
        self.label_16.setSizePolicy(sizePolicy)
        self.label_16.setStyleSheet("background-color: rgb(175, 217, 248)")
        self.label_16.setText("")
        self.gridLayout_3.addWidget(self.label_16, 0, 0, 1, 2)
