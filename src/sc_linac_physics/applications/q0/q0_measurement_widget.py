from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtWidgets import (
    QWidget,
    QGridLayout,
    QGroupBox,
    QLabel,
    QSpinBox,
    QDoubleSpinBox,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QSpacerItem,
    QSizePolicy,
    QComboBox,
)
from pydm.widgets import PyDMSpinbox, PyDMLabel, PyDMPushButton, PyDMByteIndicator


class Q0MeasurementWidget(QWidget):
    """
    Made UI for Q0 Measurement, and focused on important
    properties and layout.
    """

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QGridLayout(self)
        main_layout.setSpacing(10)

        # Top Banner
        self.label_16 = QLabel()
        self.label_16.setStyleSheet("background-color: rgb(175, 217, 248)")
        self.label_16.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        main_layout.addWidget(self.label_16, 0, 0, 1, 2)  # Row 0

        # Cryomodule Selection
        cm_select_layout = self._create_cm_selection_layout()
        main_layout.addLayout(cm_select_layout, 1, 0, 1, 2)  # Row 1

        # Cryo Controls
        self.groupBox_3 = self._create_cryo_controls_group()
        main_layout.addWidget(self.groupBox_3, 2, 0)  # Row 2, Col 0

        # Measurement Settings
        self.groupBox = self._create_measurement_settings_group()
        main_layout.addWidget(self.groupBox, 2, 1)  # Row 2, Col 1

        # Calibration
        self.groupBox_2 = self._create_calibration_group()
        main_layout.addWidget(self.groupBox_2, 4, 0, 1, 2)  # Row 4, span 2 columns

        # RF Measurement
        self.rf_groupbox = self._create_rf_measurement_group()
        main_layout.addWidget(self.rf_groupbox, 5, 0, 1, 2)  # Row 5, span 2 columns

        # Adjust row/column stretch factors if needed
        main_layout.setRowStretch(5, 1)  # Stretch the last row (RF)
        main_layout.setColumnStretch(0, 1)
        main_layout.setColumnStretch(1, 1)

    def _create_cm_selection_layout(self):
        layout = QHBoxLayout()
        bold_font = QFont()
        bold_font.setBold(True)

        layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        label_4 = QLabel("Cryomodule:")
        label_4.setFont(bold_font)
        label_4.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        self.cm_combobox = QComboBox()
        self.cm_combobox.setFont(bold_font)

        layout.addWidget(label_4)
        layout.addWidget(self.cm_combobox)
        layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        label_3 = QLabel("Cryo Permission:")
        self.perm_byte = PyDMByteIndicator()
        self.perm_byte.setProperty("offColor", QColor(252, 33, 37))
        self.perm_byte.setProperty("showLabels", False)
        self.perm_byte.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        self.perm_label = PyDMLabel()
        self.perm_label.setProperty("alarmSensitiveContent", True)

        layout.addWidget(label_3)
        layout.addWidget(self.perm_byte)
        layout.addWidget(self.perm_label)
        layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        return layout

    def _create_cryo_controls_group(self):
        groupbox = QGroupBox("Cryo Controls")
        groupbox_font = QFont()
        groupbox_font.setBold(True)
        groupbox.setFont(groupbox_font)
        layout = QGridLayout(groupbox)

        # JT Sub Group
        jt_groupbox = QGroupBox("JT")
        jt_layout = QGridLayout(jt_groupbox)

        self.jt_man_button = PyDMPushButton("Manual")
        self.jt_man_button.setProperty("pressValue", "1")
        self.jt_auto_button = PyDMPushButton("Auto")
        self.jt_auto_button.setProperty("pressValue", "1")
        self.jt_mode_label = PyDMLabel()
        self.jt_mode_label.setProperty("alarmSensitiveContent", True)

        label_6 = QLabel("Setpoint:")
        self.jt_setpoint_spinbox = PyDMSpinbox()
        self.jt_setpoint_spinbox.setMinimum(5.0)
        self.jt_setpoint_spinbox.setMaximum(70.0)
        self.jt_setpoint_spinbox.setProperty("showUnits", True)
        self.jt_setpoint_spinbox.setProperty("precisionFromPV", True)  #
        self.jt_setpoint_readback = PyDMLabel()
        self.jt_setpoint_readback.setProperty("showUnits", True)
        self.jt_setpoint_readback.setProperty("alarmSensitiveContent", True)

        jt_layout.addWidget(self.jt_man_button, 0, 0)
        jt_layout.addWidget(self.jt_auto_button, 0, 1)
        jt_layout.addWidget(self.jt_mode_label, 0, 2)
        jt_layout.addWidget(label_6, 1, 0)
        jt_layout.addWidget(self.jt_setpoint_spinbox, 1, 1)
        jt_layout.addWidget(self.jt_setpoint_readback, 1, 2)

        # Heater Sub Group
        heater_groupbox = QGroupBox("Heater")
        heater_layout = QGridLayout(heater_groupbox)

        self.heater_man_button = PyDMPushButton("Manual")
        self.heater_man_button.setProperty("pressValue", "1")
        self.heater_seq_button = PyDMPushButton("Sequencer")
        self.heater_seq_button.setProperty("pressValue", "1")
        self.heater_mode_label = PyDMLabel()
        self.heater_mode_label.setProperty("alarmSensitiveContent", True)

        label_5 = QLabel("Setpoint:")
        self.heater_setpoint_spinbox = PyDMSpinbox()
        self.heater_setpoint_spinbox.setMaximum(160.0)
        self.heater_setpoint_spinbox.setSingleStep(10.0)
        self.heater_setpoint_spinbox.setProperty("showUnits", True)
        self.heater_setpoint_spinbox.setProperty("precisionFromPV", True)
        self.heater_readback_label = PyDMLabel()
        self.heater_readback_label.setProperty("showUnits", True)
        self.heater_readback_label.setProperty("alarmSensitiveContent", True)

        heater_layout.addWidget(self.heater_man_button, 0, 0)
        heater_layout.addWidget(self.heater_seq_button, 0, 1)
        heater_layout.addWidget(self.heater_mode_label, 0, 2)
        heater_layout.addWidget(label_5, 1, 0)
        heater_layout.addWidget(self.heater_setpoint_spinbox, 1, 1)
        heater_layout.addWidget(self.heater_readback_label, 1, 2)

        # Restore Button
        self.restore_cryo_button = QPushButton("Restore Cryo to Standard Values")

        # Add sub groups and button to main Cryo Controls layout
        layout.addWidget(jt_groupbox, 0, 0, 1, 2)  # JT covers first 2 columns in row 0
        layout.addWidget(heater_groupbox, 0, 2)  # Heater is in 3rd column row 0
        layout.addWidget(self.restore_cryo_button, 1, 0, 1, 3)  # Covering all columns in row 1

        return groupbox

    def _create_measurement_settings_group(self):
        groupbox = QGroupBox("Measurement Settings")
        groupbox_font = QFont()
        groupbox_font.setBold(True)
        groupbox.setFont(groupbox_font)
        layout = QGridLayout(groupbox)

        label_9 = QLabel("Starting liquid level:")
        self.ll_start_spinbox = QDoubleSpinBox()
        self.ll_start_spinbox.setMinimum(90.0)
        self.ll_start_spinbox.setMaximum(93.0)
        self.ll_start_spinbox.setValue(93.0)

        label_10 = QLabel("Desired liquid level drop:")
        self.ll_drop_spinbox = QDoubleSpinBox()
        self.ll_drop_spinbox.setMinimum(1.0)
        self.ll_drop_spinbox.setMaximum(3.0)
        self.ll_drop_spinbox.setValue(3.0)

        label_11 = QLabel("Number of liquid level points to average:")
        label_11.setWordWrap(True)
        self.ll_avg_spinbox = QSpinBox()
        self.ll_avg_spinbox.setValue(10)
        # Min/max are default (0-99)

        layout.addWidget(label_9, 0, 0)
        layout.addWidget(self.ll_start_spinbox, 0, 1)
        layout.addWidget(label_10, 1, 0)
        layout.addWidget(self.ll_drop_spinbox, 1, 1)
        layout.addWidget(label_11, 2, 0)
        layout.addWidget(self.ll_avg_spinbox, 2, 1)

        return groupbox

    def _create_calibration_group(self):
        groupbox = QGroupBox("Calibration")
        groupbox_font = QFont()
        groupbox_font.setBold(True)
        groupbox.setFont(groupbox_font)
        layout = QGridLayout(groupbox)

        # Reference Parameters Sub Group
        self.manual_cryo_groupbox = QGroupBox("Reference Parameters")
        ref_layout = QGridLayout(self.manual_cryo_groupbox)

        self.setup_param_button = QPushButton("Set Up for New Parameters")
        self.setup_param_button.setToolTip("Sets the heater to manual at 48 so that the JT can settle")

        label_1 = QLabel("JT Valve Position")
        self.jt_pos_spinbox = QDoubleSpinBox()
        self.jt_pos_spinbox.setValue(40.0)  # Default min/max

        label_2 = QLabel("Electric Heat Load Offset")
        self.ref_heat_spinbox = QDoubleSpinBox()
        self.ref_heat_spinbox.setValue(48.0)

        ref_layout.addWidget(self.setup_param_button, 0, 0, 1, 2)
        ref_layout.addWidget(label_1, 1, 0)
        ref_layout.addWidget(self.jt_pos_spinbox, 1, 1)
        ref_layout.addWidget(label_2, 2, 0)
        ref_layout.addWidget(self.ref_heat_spinbox, 2, 1)

        # Settings Sub Group
        settings_groupbox = QGroupBox("Settings")
        settings_layout = QGridLayout(settings_groupbox)

        label_12 = QLabel("Starting heater setpoint:")
        self.start_heat_spinbox = QDoubleSpinBox()
        self.start_heat_spinbox.setRange(75.0, 130.0)  # Use setRange for min/max
        self.start_heat_spinbox.setValue(130.0)

        label_13 = QLabel("End heater setpoint:")
        self.end_heat_spinbox = QDoubleSpinBox()
        self.end_heat_spinbox.setRange(130.0, 160.0)
        self.end_heat_spinbox.setValue(160.0)

        label_14 = QLabel("Number of data points:")
        self.num_cal_points_spinbox = QSpinBox()
        self.num_cal_points_spinbox.setMaximum(20)
        self.num_cal_points_spinbox.setValue(5)

        settings_layout.addWidget(label_12, 0, 0)
        settings_layout.addWidget(self.start_heat_spinbox, 0, 1)
        settings_layout.addWidget(label_13, 1, 0)
        settings_layout.addWidget(self.end_heat_spinbox, 1, 1)
        settings_layout.addWidget(label_14, 2, 0)
        settings_layout.addWidget(self.num_cal_points_spinbox, 2, 1)

        # Calibration Buttons
        self.load_cal_button = QPushButton("Load Existing Calibration")
        self.new_cal_button = QPushButton("Take New Calibration")
        self.show_cal_data_button = QPushButton("Show Calibration Data")
        self.show_cal_data_button.setEnabled(False)  # Keep non default enabled state
        self.abort_cal_button = QPushButton("Abort Calibration")
        self.abort_cal_button.setStyleSheet("color: rgb(252, 33, 37);")  # Keep specific style

        # Status Labels
        label_8 = QLabel("Status:")
        label_8.setAlignment(Qt.AlignRight | Qt.AlignVCenter)  # Keep non default alignment
        self.cal_status_label = QLabel()  # Text set dynamically
        self.cal_status_label.setWordWrap(True)

        # Add items to Calibration layout
        layout.addWidget(self.manual_cryo_groupbox, 0, 0, 4, 1)  # Row 0, Col 0, Span 4 rows, 1 col
        layout.addWidget(settings_groupbox, 0, 1, 4, 1)  # Row 0, Col 1, Span 4 rows, 1 col

        layout.addWidget(self.load_cal_button, 0, 2)  # Row 0, Col 2
        layout.addWidget(self.new_cal_button, 1, 2)  # Row 1, Col 2
        layout.addWidget(self.show_cal_data_button, 2, 2)  # Row 2, Col 2
        layout.addWidget(self.abort_cal_button, 3, 2)  # Row 3, Col 2

        layout.addWidget(label_8, 4, 0)  # Row 4, Col 0
        layout.addWidget(self.cal_status_label, 4, 1, 1, 2)  # Row 4, Col 1, Span 1 row, 2 cols

        return groupbox

    def _create_rf_measurement_group(self):
        groupbox = QGroupBox("RF Measurement")
        groupbox_font = QFont()
        groupbox_font.setBold(True)
        groupbox.setFont(groupbox_font)
        groupbox.setEnabled(False)
        layout = QGridLayout(groupbox)

        # Cavity Amplitudes Sub Group
        cav_amp_groupbox = QGroupBox("Cavity Amplitudes")
        cav_amp_v_layout = QVBoxLayout(cav_amp_groupbox)
        self.cavity_layout = QGridLayout()
        cav_amp_v_layout.addLayout(self.cavity_layout)

        # Other RF Controls
        label_7 = QLabel("Calibration Heat Load:")
        self.rf_cal_spinbox = QDoubleSpinBox()
        self.rf_cal_spinbox.setEnabled(False)
        self.rf_cal_spinbox.setRange(24.0, 112.0)
        self.rf_cal_spinbox.setValue(80.0)

        self.load_rf_button = QPushButton("Load Existing RF Measurement")
        self.new_rf_button = QPushButton("Take New RF Measurement")
        self.show_rf_button = QPushButton("Show RF Data")
        self.abort_rf_button = QPushButton("Abort RF Measurement")
        self.abort_rf_button.setStyleSheet("color: rgb(252, 33, 37);")

        label_15 = QLabel("Status:")
        label_15.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.rf_status_label = QLabel()
        self.rf_status_label.setWordWrap(True)

        # Add items to RF Measurement layout
        layout.addWidget(cav_amp_groupbox, 0, 0, 1, 2)  # Row 0, span 2 cols

        layout.addWidget(label_7, 1, 0)
        layout.addWidget(self.rf_cal_spinbox, 1, 1)

        layout.addWidget(self.load_rf_button, 2, 0)
        layout.addWidget(self.new_rf_button, 2, 1)

        layout.addWidget(self.show_rf_button, 3, 0)
        layout.addWidget(self.abort_rf_button, 3, 1)

        layout.addWidget(label_15, 4, 0)
        layout.addWidget(self.rf_status_label, 4, 1)

        return groupbox
