# test_q0_gui.py
import sys
from unittest.mock import Mock, patch

import pytest
from PyQt5.QtWidgets import QApplication, QMessageBox, QWidget

from sc_linac_physics.applications.q0.q0_gui import make_non_blocking_error_popup, Q0GUI


@pytest.fixture(autouse=True, scope="function")
def mock_q0_dependencies():
    """Mock heavy dependencies only for Q0 GUI tests."""
    with patch.dict(
        "sys.modules",
        {
            "lcls_tools": Mock(),
            "lcls_tools.common": Mock(),
            "lcls_tools.common.frontend": Mock(),
            "lcls_tools.common.frontend.display": Mock(),
            "lcls_tools.common.frontend.display.util": Mock(),
            "pyqtgraph": Mock(),
            "sc_linac_physics.applications.q0.q0_gui_utils": Mock(),
            "sc_linac_physics.applications.q0.q0_cavity": Mock(),
            "sc_linac_physics.applications.q0.q0_cryomodule": Mock(),
            "sc_linac_physics.applications.q0.q0_measurement_widget": Mock(),
            "sc_linac_physics.applications.q0.q0_utils": Mock(),
            "sc_linac_physics.utils.sc_linac.linac": Mock(),
            "sc_linac_physics.utils.sc_linac.linac_utils": Mock(),
        },
    ):
        # Setup the specific mocks that tests need
        mock_pydm = Mock()
        mock_pydm.Display = MockDisplay
        sys.modules["pydm"] = mock_pydm

        # Mock plot function
        mock_plot = Mock()
        sys.modules["pyqtgraph"].plot = mock_plot
        sys.modules["pyqtgraph"].PlotWidget = Mock()

        yield


class MockCavAmpControl:
    def __init__(self):
        self.groupbox = Mock()
        self.groupbox.setCheckable = Mock()
        self.groupbox.setTitle = Mock()
        self.groupbox.setChecked = Mock()
        self.groupbox.setLayout = Mock()

        self.desAmpSpinbox = Mock()
        self.desAmpSpinbox.setValue = Mock()
        self.desAmpSpinbox.setRange = Mock()

        self.aact_label = Mock()

    def connect(self, cavity):
        """Mock implementation of connect method"""
        # Store the cavity for potential assertions
        self.connected_cavity = cavity

        # Mock the title setting
        self.groupbox.setTitle(f"Cavity {cavity.number}")

        # Mock the online/offline logic
        if hasattr(cavity, "is_online") and not cavity.is_online:
            self.groupbox.setChecked(False)
            self.desAmpSpinbox.setRange(0, 0)
        else:
            self.groupbox.setChecked(True)
            max_amp = getattr(cavity, "ades_max", 16.6)
            desired_amp = min(16.6, max_amp)
            self.desAmpSpinbox.setValue(desired_amp)
            self.desAmpSpinbox.setRange(0, max_amp)

        # Mock channel assignment
        self.aact_label.channel = getattr(cavity, "aact_pv", "mock_aact_pv")


class MockDisplay(QWidget):
    """Mock Display class that maintains Qt widget behavior."""

    def __init__(self, parent=None, args=None):
        super().__init__(parent)


class MockMeasurementWidget(QWidget):
    """Mock Q0MeasurementWidget that behaves like a real QWidget."""

    def __init__(self):
        super().__init__()
        # Add all the attributes that the GUI expects
        self.cm_combobox = Mock()
        self.ll_avg_spinbox = Mock()
        self.new_cal_button = Mock()
        self.load_cal_button = Mock()
        self.show_cal_data_button = Mock()
        self.new_rf_button = Mock()
        self.load_rf_button = Mock()
        self.show_rf_button = Mock()
        self.setup_param_button = Mock()
        self.abort_rf_button = Mock()
        self.abort_cal_button = Mock()
        self.restore_cryo_button = Mock()

        # Mock spinboxes and labels
        self.ref_heat_spinbox = Mock()
        self.jt_pos_spinbox = Mock()
        self.ll_start_spinbox = Mock()
        self.start_heat_spinbox = Mock()
        self.end_heat_spinbox = Mock()
        self.num_cal_points_spinbox = Mock()
        self.ll_drop_spinbox = Mock()

        self.perm_byte = Mock()
        self.perm_label = Mock()
        self.jt_man_button = Mock()
        self.jt_auto_button = Mock()
        self.jt_mode_label = Mock()
        self.jt_setpoint_spinbox = Mock()
        self.jt_setpoint_readback = Mock()
        self.heater_man_button = Mock()
        self.heater_seq_button = Mock()
        self.heater_mode_label = Mock()
        self.heater_setpoint_spinbox = Mock()
        self.heater_readback_label = Mock()

        self.cal_status_label = Mock()
        self.rf_status_label = Mock()
        self.rf_groupbox = Mock()
        self.cavity_layout = Mock()

        # Mock value methods
        self.ref_heat_spinbox.value.return_value = 5.0
        self.jt_pos_spinbox.value.return_value = 50.0
        self.ll_start_spinbox.value.return_value = 85.0
        self.start_heat_spinbox.value.return_value = 2.0
        self.end_heat_spinbox.value.return_value = 10.0
        self.num_cal_points_spinbox.value.return_value = 5
        self.ll_drop_spinbox.value.return_value = 5.0
        self.ll_avg_spinbox.value.return_value = 10


# Mock the pydm module with our custom Display
mock_pydm = Mock()
mock_pydm.Display = MockDisplay
sys.modules["pydm"] = mock_pydm

# Mock plot function
mock_plot = Mock()
sys.modules["pyqtgraph"].plot = mock_plot
sys.modules["pyqtgraph"].PlotWidget = Mock()


@pytest.fixture
def qapp():
    """Create QApplication instance for testing."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app
    app.quit()


@pytest.fixture
def mock_cryomodule():
    """Create a mock cryomodule for testing."""
    mock_cm = Mock()
    mock_cm.name = "CM01"
    mock_cm.cryo_access_pv = "ACCL:L1B:0110:CRYO_ACCESS"
    mock_cm.jt_manual_select_pv = "ACCL:L1B:0110:JT_MAN_SEL"
    mock_cm.jt_auto_select_pv = "ACCL:L1B:0110:JT_AUTO_SEL"
    mock_cm.jt_mode_str_pv = "ACCL:L1B:0110:JT_MODE_STR"
    mock_cm.jt_man_pos_setpoint_pv = "ACCL:L1B:0110:JT_MAN_POS_SP"
    mock_cm.jt_valve_readback_pv = "ACCL:L1B:0110:JT_VALVE_RB"
    mock_cm.heater_manual_pv = "ACCL:L1B:0110:HTR_MAN"
    mock_cm.heater_sequencer_pv = "ACCL:L1B:0110:HTR_SEQ"
    mock_cm.heater_mode_string_pv = "ACCL:L1B:0110:HTR_MODE_STR"
    mock_cm.heater_setpoint_pv = "ACCL:L1B:0110:HTR_SP"
    mock_cm.heater_readback_pv = "ACCL:L1B:0110:HTR_RB"
    mock_cm.ll_buffer_size = 10
    mock_cm.abort_flag = False

    # Mock cavities
    mock_cm.cavities = {}
    for i in range(1, 9):
        cavity = Mock()
        cavity.number = i
        cavity.abort_flag = False
        cavity.mark_ready = Mock()
        mock_cm.cavities[i] = cavity

    # Mock calibration and measurement data
    mock_cm.calibration = None
    mock_cm.q0_measurement = None
    mock_cm.valveParams = None

    # Mock methods
    mock_cm.restore_cryo = Mock()
    mock_cm.shut_off = Mock()

    return mock_cm


class TestMakeNonBlockingErrorPopup:
    """Test the error popup function."""

    def test_creates_error_popup(self, qapp):
        """Test that error popup is created with correct properties."""
        with patch("sc_linac_physics.applications.q0.q0_gui.QMessageBox") as mock_messagebox_class:
            mock_popup = Mock()
            mock_messagebox_class.return_value = mock_popup

            # Mock the Critical constant properly
            mock_messagebox_class.Critical = QMessageBox.Critical

            result = make_non_blocking_error_popup("Test Title", "Test Message")

            mock_messagebox_class.assert_called_once()
            mock_popup.setIcon.assert_called_once_with(QMessageBox.Critical)
            mock_popup.setWindowTitle.assert_called_once_with("Test Title")
            mock_popup.setText.assert_called_once_with("Test Message")
            mock_popup.show.assert_called_once()
            assert result == mock_popup


class TestQ0GUIInitialization:
    """Test Q0GUI initialization."""

    @patch("sc_linac_physics.applications.q0.q0_gui.Q0MeasurementWidget")
    @patch("sc_linac_physics.applications.q0.q0_gui.Q0_CRYOMODULES", {})
    @patch("sc_linac_physics.applications.q0.q0_gui.ALL_CRYOMODULES", ["CM01", "CM02"])
    @patch("sc_linac_physics.applications.q0.q0_gui.q0_gui_utils")
    def test_gui_initialization(self, mock_q0_gui_utils, mock_widget_class, qapp):
        """Test that GUI initializes correctly."""
        # Return our custom mock widget that's a real QWidget
        mock_widget_class.return_value = MockMeasurementWidget()

        # Mock the cavity amplitude controls
        mock_q0_gui_utils.CavAmpControl = MockCavAmpControl

        gui = Q0GUI()

        # Test that the window title was set (since we're using real QWidget behavior)
        assert gui.windowTitle() == "Q0 Measurement"
        assert gui.selected_cm is None
        assert len(gui.cav_amp_controls) == 8
        gui.main_widget.cm_combobox.addItems.assert_called_once_with(["", "CM01", "CM02"])

    @patch("sc_linac_physics.applications.q0.q0_gui.Q0MeasurementWidget")
    @patch("sc_linac_physics.applications.q0.q0_gui.Q0_CRYOMODULES", {})
    @patch("sc_linac_physics.applications.q0.q0_gui.ALL_CRYOMODULES", ["CM01", "CM02"])
    @patch("sc_linac_physics.applications.q0.q0_gui.q0_gui_utils")
    def test_gui_widget_connections(self, mock_q0_gui_utils, mock_widget_class, qapp):
        """Test that GUI widget connections are set up correctly."""
        mock_widget = MockMeasurementWidget()
        mock_widget_class.return_value = mock_widget

        # Mock the cavity amplitude controls
        mock_q0_gui_utils.CavAmpControl = MockCavAmpControl

        Q0GUI()

        # Verify signal connections were made
        mock_widget.cm_combobox.currentTextChanged.connect.assert_called_once()
        mock_widget.new_cal_button.clicked.connect.assert_called_once()
        mock_widget.load_cal_button.clicked.connect.assert_called_once()
        mock_widget.new_rf_button.clicked.connect.assert_called_once()
        mock_widget.abort_rf_button.clicked.connect.assert_called_once()
        mock_widget.abort_cal_button.clicked.connect.assert_called_once()


class TestQ0GUIHelperMethods:
    """Test helper methods in Q0GUI."""

    @patch("sc_linac_physics.applications.q0.q0_gui.Q0MeasurementWidget")
    @patch("sc_linac_physics.applications.q0.q0_gui.Q0_CRYOMODULES", {})
    @patch("sc_linac_physics.applications.q0.q0_gui.ALL_CRYOMODULES", [])
    @patch("sc_linac_physics.applications.q0.q0_gui.q0_gui_utils")
    def test_require_cm_with_no_selection(self, mock_q0_gui_utils, mock_widget_class, qapp):
        """Test _require_cm when no cryomodule is selected."""
        mock_widget_class.return_value = MockMeasurementWidget()
        mock_q0_gui_utils.CavAmpControl = MockCavAmpControl

        gui = Q0GUI()

        with patch("sc_linac_physics.applications.q0.q0_gui.make_non_blocking_error_popup") as mock_popup:
            result = gui._require_cm()

            assert result is False
            mock_popup.assert_called_once_with("No Cryomodule Selected", "Please select a cryomodule first.")

    @patch("sc_linac_physics.applications.q0.q0_gui.Q0MeasurementWidget")
    @patch("sc_linac_physics.applications.q0.q0_gui.Q0_CRYOMODULES", {})
    @patch("sc_linac_physics.applications.q0.q0_gui.ALL_CRYOMODULES", [])
    @patch("sc_linac_physics.applications.q0.q0_gui.q0_gui_utils")
    def test_require_cm_with_selection(self, mock_q0_gui_utils, mock_widget_class, qapp, mock_cryomodule):
        """Test _require_cm when cryomodule is selected."""
        mock_widget_class.return_value = MockMeasurementWidget()
        mock_q0_gui_utils.CavAmpControl = MockCavAmpControl

        gui = Q0GUI()
        gui.selected_cm = mock_cryomodule

        result = gui._require_cm()
        assert result is True


class TestQ0GUICryomoduleSelection:
    """Test cryomodule selection functionality."""

    @patch("sc_linac_physics.applications.q0.q0_gui.Q0MeasurementWidget")
    @patch("sc_linac_physics.applications.q0.q0_gui.ALL_CRYOMODULES", ["CM01"])
    @patch("sc_linac_physics.applications.q0.q0_gui.Q0_CRYOMODULES", {})
    @patch("sc_linac_physics.applications.q0.q0_gui.q0_gui_utils")
    def test_update_cm_empty_selection(self, mock_q0_gui_utils, mock_widget_class, qapp):
        """Test updating to empty cryomodule selection."""
        mock_widget_class.return_value = MockMeasurementWidget()
        mock_q0_gui_utils.CavAmpControl = MockCavAmpControl

        gui = Q0GUI()
        gui.update_cm("")

        assert gui.selected_cm is None

    @patch("sc_linac_physics.applications.q0.q0_gui.Q0MeasurementWidget")
    @patch("sc_linac_physics.applications.q0.q0_gui.ALL_CRYOMODULES", ["CM01"])
    @patch("sc_linac_physics.applications.q0.q0_gui.q0_gui_utils")
    def test_update_cm_valid_selection(self, mock_q0_gui_utils, mock_widget_class, qapp, mock_cryomodule):
        """Test updating to valid cryomodule selection."""
        mock_widget = MockMeasurementWidget()
        mock_widget_class.return_value = mock_widget
        mock_q0_gui_utils.CavAmpControl = MockCavAmpControl

        # Setup mock cryomodule with cavities
        mock_cavity = Mock()
        mock_cavity.number = 1
        mock_cavity.is_online = True
        mock_cavity.ades_max = 20.0
        mock_cavity.aact_pv = "MOCK:CAV1:AACT"
        mock_cryomodule.cavities = {1: mock_cavity}

        # Add required PV attributes to mock_cryomodule
        mock_cryomodule.cryo_access_pv = "MOCK:CM01:CRYO_ACCESS"
        mock_cryomodule.jt_manual_select_pv = "MOCK:CM01:JT_MAN"
        mock_cryomodule.jt_auto_select_pv = "MOCK:CM01:JT_AUTO"
        # ... add other required PV attributes

        with patch("sc_linac_physics.applications.q0.q0_gui.Q0_CRYOMODULES", {"CM01": mock_cryomodule}):
            gui = Q0GUI()
            gui.update_cm("CM01")

            # Verify the cryomodule was selected
            assert gui.selected_cm == mock_cryomodule

            # Verify cavity control was connected
            cav_control = gui.cav_amp_controls[1]
            assert hasattr(cav_control, "connected_cavity")
            assert cav_control.connected_cavity == mock_cavity


class TestQ0GUICalibrationMethods:
    """Test calibration-related methods."""

    @patch("sc_linac_physics.applications.q0.q0_gui.Q0MeasurementWidget")
    @patch("sc_linac_physics.applications.q0.q0_gui.Q0_CRYOMODULES", {})
    @patch("sc_linac_physics.applications.q0.q0_gui.ALL_CRYOMODULES", [])
    @patch("sc_linac_physics.applications.q0.q0_gui.q0_gui_utils")
    def test_load_calibration_no_cm(self, mock_q0_gui_utils, mock_widget_class, qapp):
        """Test load_calibration without selected cryomodule."""
        mock_widget_class.return_value = MockMeasurementWidget()
        mock_q0_gui_utils.CavAmpControl = MockCavAmpControl

        gui = Q0GUI()

        with patch.object(gui, "_require_cm", return_value=False):
            gui.load_calibration()
            # Should return early without doing anything

    @patch("sc_linac_physics.applications.q0.q0_gui.Q0MeasurementWidget")
    @patch("sc_linac_physics.applications.q0.q0_gui.Q0_CRYOMODULES", {})
    @patch("sc_linac_physics.applications.q0.q0_gui.ALL_CRYOMODULES", [])
    @patch("sc_linac_physics.applications.q0.q0_gui.q0_gui_utils")
    def test_show_calibration_data_no_data(self, mock_q0_gui_utils, mock_widget_class, qapp, mock_cryomodule):
        """Test show_calibration_data with no calibration data."""
        mock_widget_class.return_value = MockMeasurementWidget()
        mock_q0_gui_utils.CavAmpControl = MockCavAmpControl

        gui = Q0GUI()
        gui.selected_cm = mock_cryomodule
        mock_cryomodule.calibration = None

        with patch("sc_linac_physics.applications.q0.q0_gui.make_non_blocking_error_popup") as mock_popup:
            gui.show_calibration_data()

            mock_popup.assert_called_once_with("No Calibration Data", "No calibration data available.")

    @patch("sc_linac_physics.applications.q0.q0_gui.Q0MeasurementWidget")
    @patch("sc_linac_physics.applications.q0.q0_gui.Q0_CRYOMODULES", {})
    @patch("sc_linac_physics.applications.q0.q0_gui.ALL_CRYOMODULES", [])
    @patch("sc_linac_physics.applications.q0.q0_gui.q0_gui_utils")
    def test_handle_cal_status(self, mock_q0_gui_utils, mock_widget_class, qapp):
        """Test calibration status handling."""
        mock_widget = MockMeasurementWidget()
        mock_widget_class.return_value = mock_widget
        mock_q0_gui_utils.CavAmpControl = MockCavAmpControl

        gui = Q0GUI()

        gui.handle_cal_status("Calibration in progress...")

        mock_widget.cal_status_label.setStyleSheet.assert_called_once_with("color: blue;")
        mock_widget.cal_status_label.setText.assert_called_once_with("Calibration in progress...")

    @patch("sc_linac_physics.applications.q0.q0_gui.Q0MeasurementWidget")
    @patch("sc_linac_physics.applications.q0.q0_gui.Q0_CRYOMODULES", {})
    @patch("sc_linac_physics.applications.q0.q0_gui.ALL_CRYOMODULES", [])
    @patch("sc_linac_physics.applications.q0.q0_gui.q0_gui_utils")
    def test_handle_cal_error(self, mock_q0_gui_utils, mock_widget_class, qapp):
        """Test calibration error handling."""
        mock_widget = MockMeasurementWidget()
        mock_widget_class.return_value = mock_widget
        mock_q0_gui_utils.CavAmpControl = MockCavAmpControl

        gui = Q0GUI()

        gui.handle_cal_error("Calibration failed!")

        mock_widget.cal_status_label.setStyleSheet.assert_called_once_with("color: red;")
        mock_widget.cal_status_label.setText.assert_called_once_with("Calibration failed!")


class TestQ0GUIQ0MeasurementMethods:
    """Test Q0 measurement-related methods."""

    @patch("sc_linac_physics.applications.q0.q0_gui.Q0MeasurementWidget")
    @patch("sc_linac_physics.applications.q0.q0_gui.Q0_CRYOMODULES", {})
    @patch("sc_linac_physics.applications.q0.q0_gui.ALL_CRYOMODULES", [])
    @patch("sc_linac_physics.applications.q0.q0_gui.q0_gui_utils")
    def test_desired_cavity_amplitudes(self, mock_q0_gui_utils, mock_widget_class, qapp):
        """Test getting desired cavity amplitudes."""
        mock_widget_class.return_value = MockMeasurementWidget()
        mock_q0_gui_utils.CavAmpControl = MockCavAmpControl

        gui = Q0GUI()

        # Setup mock controls with proper return values
        mock_controls = {}
        for i in range(1, 9):
            mock_control = Mock()
            mock_control.groupbox = Mock()
            mock_control.groupbox.isChecked.return_value = i <= 4  # First 4 checked
            mock_control.desAmpSpinbox.value.return_value = i * 5.0  # Different amplitudes
            mock_controls[i] = mock_control

        # Manually set the controls after initialization
        gui.cav_amp_controls = mock_controls

        amplitudes = gui.desiredCavityAmplitudes

        expected = {1: 5.0, 2: 10.0, 3: 15.0, 4: 20.0, 5: 0, 6: 0, 7: 0, 8: 0}
        assert amplitudes == expected

    @patch("sc_linac_physics.applications.q0.q0_gui.Q0MeasurementWidget")
    @patch("sc_linac_physics.applications.q0.q0_gui.Q0_CRYOMODULES", {})
    @patch("sc_linac_physics.applications.q0.q0_gui.ALL_CRYOMODULES", [])
    @patch("sc_linac_physics.applications.q0.q0_gui.q0_gui_utils")
    def test_kill_rf(self, mock_q0_gui_utils, mock_widget_class, qapp, mock_cryomodule):
        """Test RF kill functionality."""
        mock_widget_class.return_value = MockMeasurementWidget()
        mock_q0_gui_utils.CavAmpControl = MockCavAmpControl

        gui = Q0GUI()

        # Setup mock workers
        mock_setup_worker = Mock()
        mock_setup_worker.cryomodule = mock_cryomodule
        gui.q0_setup_worker = mock_setup_worker

        mock_ramp_worker = Mock()
        mock_ramp_worker.cavity = mock_cryomodule.cavities[1]
        gui.q0_ramp_workers[1] = mock_ramp_worker

        mock_meas_worker = Mock()
        mock_meas_worker.cryomodule = mock_cryomodule
        gui.q0_meas_worker = mock_meas_worker

        gui.kill_rf()

        assert mock_cryomodule.abort_flag is True
        assert mock_cryomodule.cavities[1].abort_flag is True


class TestQ0GUIControlMethods:
    """Test control-related methods."""

    @patch("sc_linac_physics.applications.q0.q0_gui.Q0MeasurementWidget")
    @patch("sc_linac_physics.applications.q0.q0_gui.Q0_CRYOMODULES", {})
    @patch("sc_linac_physics.applications.q0.q0_gui.ALL_CRYOMODULES", [])
    @patch("sc_linac_physics.applications.q0.q0_gui.q0_gui_utils")
    def test_restore_cryo_success(self, mock_q0_gui_utils, mock_widget_class, qapp, mock_cryomodule):
        """Test successful restore_cryo."""
        mock_widget_class.return_value = MockMeasurementWidget()
        mock_q0_gui_utils.CavAmpControl = MockCavAmpControl

        gui = Q0GUI()
        gui.selected_cm = mock_cryomodule

        gui.restore_cryo()

        mock_cryomodule.restore_cryo.assert_called_once()

    @patch("sc_linac_physics.applications.q0.q0_gui.Q0MeasurementWidget")
    @patch("sc_linac_physics.applications.q0.q0_gui.Q0_CRYOMODULES", {})
    @patch("sc_linac_physics.applications.q0.q0_gui.ALL_CRYOMODULES", [])
    @patch("sc_linac_physics.applications.q0.q0_gui.q0_gui_utils")
    def test_update_ll_buffer(self, mock_q0_gui_utils, mock_widget_class, qapp, mock_cryomodule):
        """Test updating liquid level buffer."""
        mock_widget_class.return_value = MockMeasurementWidget()
        mock_q0_gui_utils.CavAmpControl = MockCavAmpControl

        gui = Q0GUI()
        gui.selected_cm = mock_cryomodule

        gui.update_ll_buffer(20)

        assert mock_cryomodule.ll_buffer_size == 20


class TestQ0GUIWorkflowIntegration:
    """Test complete workflow integration."""

    @patch("sc_linac_physics.applications.q0.q0_gui.Q0MeasurementWidget")
    @patch("sc_linac_physics.applications.q0.q0_gui.Q0_CRYOMODULES", {})
    @patch("sc_linac_physics.applications.q0.q0_gui.ALL_CRYOMODULES", [])
    @patch("sc_linac_physics.applications.q0.q0_gui.CalibrationWorker")  # Patch the direct import
    @patch("sc_linac_physics.applications.q0.q0_gui.q0_gui_utils")
    def test_take_new_calibration_workflow(
        self, mock_q0_gui_utils, mock_calibration_worker, mock_widget_class, qapp, mock_cryomodule
    ):
        """Test the complete calibration workflow."""
        mock_widget = MockMeasurementWidget()
        mock_widget_class.return_value = mock_widget
        mock_q0_gui_utils.CavAmpControl = MockCavAmpControl

        # Mock the CalibrationWorker (directly imported)
        mock_cal_worker = Mock()
        mock_cal_worker.isRunning.return_value = False
        mock_calibration_worker.return_value = mock_cal_worker

        # Mock ValveParams
        with patch("sc_linac_physics.applications.q0.q0_gui.ValveParams") as mock_valve_params:
            gui = Q0GUI()
            gui.selected_cm = mock_cryomodule

            # Ensure cryomodule has required attributes
            mock_cryomodule.name = "01"

            gui.takeNewCalibration()

            # Verify ValveParams was created
            mock_valve_params.assert_called_once()

            # Verify CalibrationWorker was created and started
            mock_calibration_worker.assert_called_once()
            mock_cal_worker.start.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
