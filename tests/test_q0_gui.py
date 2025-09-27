import sys
from unittest.mock import Mock, patch

import pytest
from PyQt5.QtWidgets import QApplication

from sc_linac_physics.applications.q0.q0_gui import Q0GUI


@pytest.fixture(scope="session")
def qapp():
    if not QApplication.instance():
        app = QApplication(sys.argv)
    else:
        app = QApplication.instance()
    yield app


@pytest.fixture(autouse=True)
def mock_everything():
    """Mock everything including EPICS calls that might be used in workers."""
    with (
        patch("pydm.Display"),
        patch("pydm.widgets.PyDMLabel"),
        patch("pydm.widgets.PyDMSpinbox"),
        patch("pydm.widgets.PyDMPushButton"),
        patch("pydm.widgets.PyDMByteIndicator"),
        patch("pydm.data_plugins.establish_connection"),
        patch("epics.caget", return_value=1),
        patch("epics.caput"),
        patch("epics.camonitor"),
        patch("epics.camonitor_clear"),
        patch("epics.get_pv"),
        patch("epics.pv.get_pv"),
        patch("epics.PV"),
        patch("sc_linac_physics.utils.sc_linac.linac.Machine"),
        patch("sc_linac_physics.utils.sc_linac.linac_utils.ALL_CRYOMODULES", []),
    ):
        yield


@pytest.fixture
def q0_gui(qapp):
    """Create Q0GUI instance."""
    gui = Q0GUI()
    return gui


@pytest.fixture
def mock_cryomodule():
    """Create a properly mocked cryomodule."""
    mock_cm = Mock()
    mock_cm.name = "01"
    mock_cm.cryo_access_pv = "CRYO:CM01:0:CAS_ACCESS"

    # Mock valve params - start as None but allow setting
    mock_cm.valveParams = None

    mock_cm.restore_cryo = Mock()
    mock_cm.q0_measurement = None
    mock_cm.calibration = None

    return mock_cm


class TestQ0GUI:
    """Tests for Q0GUI functionality."""

    def test_initialization(self, q0_gui):
        """Test basic initialization."""
        assert q0_gui.windowTitle() == "Q0 Measurement"
        assert q0_gui.selected_cm is None

    def test_widget_default_values(self, q0_gui):
        """Test that widget default values match the widget code."""
        # Based on the Q0MeasurementWidget code:
        assert q0_gui.main_widget.ref_heat_spinbox.value() == 48.0  # setValue(48.0)
        assert q0_gui.main_widget.jt_pos_spinbox.value() == 40.0  # setValue(40.0)
        assert q0_gui.main_widget.ll_start_spinbox.value() == 93.0  # setValue(93.0)
        assert q0_gui.main_widget.start_heat_spinbox.value() == 130.0  # setValue(130.0)
        assert q0_gui.main_widget.end_heat_spinbox.value() == 160.0  # setValue(160.0)
        assert q0_gui.main_widget.num_cal_points_spinbox.value() == 5  # setValue(5)
        assert q0_gui.main_widget.ll_drop_spinbox.value() == 3.0  # setValue(3.0)
        assert q0_gui.main_widget.ll_avg_spinbox.value() == 10  # setValue(10)
        assert q0_gui.main_widget.rf_cal_spinbox.value() == 80.0  # setValue(80.0)

    def test_status_handlers(self, q0_gui):
        """Test status message handlers."""
        # Test calibration status
        q0_gui.handle_cal_status("Test message")
        assert q0_gui.main_widget.cal_status_label.text() == "Test message"
        assert "color: blue" in q0_gui.main_widget.cal_status_label.styleSheet()

        # Test calibration error
        q0_gui.handle_cal_error("Error message")
        assert q0_gui.main_widget.cal_status_label.text() == "Error message"
        assert "color: red" in q0_gui.main_widget.cal_status_label.styleSheet()

    def test_require_cm_method_works(self, q0_gui, mock_cryomodule):
        """Test that _require_cm method works correctly."""
        # Without cryomodule
        q0_gui.selected_cm = None
        with patch("sc_linac_physics.applications.q0.q0_gui.make_non_blocking_error_popup"):
            result = q0_gui._require_cm()
            assert result is False

        # With cryomodule
        q0_gui.selected_cm = mock_cryomodule
        result = q0_gui._require_cm()
        assert result is True

    def test_takeNewCalibration_without_cm_shows_error(self, q0_gui):
        """Test takeNewCalibration without cryomodule shows error popup."""
        q0_gui.selected_cm = None

        with patch("sc_linac_physics.applications.q0.q0_gui.make_non_blocking_error_popup") as mock_popup:
            q0_gui.takeNewCalibration()
            mock_popup.assert_called_once_with("No Cryomodule Selected", "Please select a cryomodule first.")

    def test_takeNewCalibration_sets_valve_params(self, q0_gui, mock_cryomodule):
        """Test that takeNewCalibration sets valve parameters correctly."""
        q0_gui.selected_cm = mock_cryomodule

        with patch("sc_linac_physics.applications.q0.q0_gui.CalibrationWorker") as mock_worker_class:
            mock_worker = Mock()
            mock_worker_class.return_value = mock_worker

            q0_gui.takeNewCalibration()

            # Check that valveParams were set correctly using widget default values
            valve_params = mock_cryomodule.valveParams
            assert valve_params is not None
            assert valve_params.refHeatLoadDes == 48.0  # ref_heat_spinbox default
            assert valve_params.refValvePos == 40.0  # jt_pos_spinbox default
            assert valve_params.refHeatLoadAct == 48.0  # ref_heat_spinbox default

            # Worker should be assigned
            assert q0_gui.calibration_worker == mock_worker

            # Worker should be started
            mock_worker.start.assert_called_once()

    def test_takeNewCalibration_worker_creation_params(self, q0_gui, mock_cryomodule):
        """Test that CalibrationWorker is created with correct parameters."""
        q0_gui.selected_cm = mock_cryomodule

        with patch("sc_linac_physics.applications.q0.q0_gui.CalibrationWorker") as mock_worker_class:
            mock_worker = Mock()
            mock_worker_class.return_value = mock_worker

            q0_gui.takeNewCalibration()

            # Verify CalibrationWorker was called with widget default values
            mock_worker_class.assert_called_once_with(
                cryomodule=mock_cryomodule,
                jt_search_start=None,
                jt_search_end=None,
                desired_ll=93.0,  # ll_start_spinbox default
                heat_start=130.0,  # start_heat_spinbox default
                heat_end=160.0,  # end_heat_spinbox default
                num_cal_steps=5,  # num_cal_points_spinbox default
                ll_drop=3.0,  # ll_drop_spinbox default
            )

    def test_takeNewCalibration_connects_signals(self, q0_gui, mock_cryomodule):
        """Test that takeNewCalibration connects worker signals correctly."""
        q0_gui.selected_cm = mock_cryomodule

        with patch("sc_linac_physics.applications.q0.q0_gui.CalibrationWorker") as mock_worker_class:
            mock_worker = Mock()
            mock_worker_class.return_value = mock_worker

            q0_gui.takeNewCalibration()

            # Check that signals were connected
            mock_worker.status.connect.assert_called()
            mock_worker.finished.connect.assert_called()
            mock_worker.error.connect.assert_called()

    def test_kill_calibration(self, q0_gui):
        """Test killing calibration process."""
        mock_worker = Mock()
        mock_worker.cryomodule = Mock()
        q0_gui.calibration_worker = mock_worker

        q0_gui.kill_calibration()
        assert mock_worker.cryomodule.abort_flag is True

    def test_kill_rf(self, q0_gui):
        """Test killing RF processes."""
        # Setup workers
        q0_gui.q0_setup_worker = Mock()
        q0_gui.q0_setup_worker.cryomodule = Mock()

        q0_gui.q0_ramp_workers[1] = Mock()
        q0_gui.q0_ramp_workers[1].cavity = Mock()

        q0_gui.q0_meas_worker = Mock()
        q0_gui.q0_meas_worker.cryomodule = Mock()

        q0_gui.kill_rf()

        assert q0_gui.q0_setup_worker.cryomodule.abort_flag is True
        assert q0_gui.q0_ramp_workers[1].cavity.abort_flag is True
        assert q0_gui.q0_meas_worker.cryomodule.abort_flag is True

    def test_restore_cryo_with_cm(self, q0_gui, mock_cryomodule):
        """Test restore_cryo with a cryomodule selected."""
        q0_gui.selected_cm = mock_cryomodule
        q0_gui.restore_cryo()
        mock_cryomodule.restore_cryo.assert_called_once()

    def test_restore_cryo_without_cm_shows_error(self, q0_gui):
        """Test restore_cryo without cryomodule shows error popup."""
        q0_gui.selected_cm = None

        with patch("sc_linac_physics.applications.q0.q0_gui.make_non_blocking_error_popup") as mock_popup:
            q0_gui.restore_cryo()
            mock_popup.assert_called_once_with("No Cryomodule Selected", "Please select a cryomodule first.")

    def test_take_new_q0_measurement_sets_valve_params(self, q0_gui, mock_cryomodule):
        """Test that take_new_q0_measurement sets valve parameters correctly."""
        q0_gui.selected_cm = mock_cryomodule

        with patch("sc_linac_physics.applications.q0.q0_gui.q0_gui_utils.Q0SetupWorker") as mock_worker_class:
            mock_worker = Mock()
            mock_worker_class.return_value = mock_worker

            q0_gui.take_new_q0_measurement()

            # Should have set valveParams with widget default values
            valve_params = mock_cryomodule.valveParams
            assert valve_params is not None
            assert valve_params.refHeatLoadDes == 48.0  # ref_heat_spinbox default
            assert valve_params.refValvePos == 40.0  # jt_pos_spinbox default
            assert valve_params.refHeatLoadAct == 48.0  # ref_heat_spinbox default

            # Worker should be assigned and started
            assert q0_gui.q0_setup_worker == mock_worker
            mock_worker.start.assert_called_once()

    def test_take_new_q0_measurement_without_cm_shows_error(self, q0_gui):
        """Test take_new_q0_measurement without cryomodule shows error popup."""
        q0_gui.selected_cm = None

        with patch("sc_linac_physics.applications.q0.q0_gui.make_non_blocking_error_popup") as mock_popup:
            q0_gui.take_new_q0_measurement()
            mock_popup.assert_called_once_with("No Cryomodule Selected", "Please select a cryomodule first.")

    def test_setup_for_cryo_params_with_cm(self, q0_gui, mock_cryomodule):
        """Test setup_for_cryo_params with cryomodule."""
        q0_gui.selected_cm = mock_cryomodule

        with patch("sc_linac_physics.applications.q0.q0_gui.q0_gui_utils.CryoParamSetupWorker") as mock_worker_class:
            mock_worker = Mock()
            mock_worker_class.return_value = mock_worker

            q0_gui.setup_for_cryo_params()

            # Should use widget default values
            mock_worker_class.assert_called_once_with(
                mock_cryomodule,
                heater_setpoint=48.0,  # ref_heat_spinbox default
                jt_setpoint=40.0,  # jt_pos_spinbox default
            )

            assert q0_gui.cryo_param_setup_worker == mock_worker
            mock_worker.start.assert_called_once()

    def test_setup_for_cryo_params_without_cm_shows_error(self, q0_gui):
        """Test setup_for_cryo_params without cryomodule shows error popup."""
        q0_gui.selected_cm = None

        with patch("sc_linac_physics.applications.q0.q0_gui.make_non_blocking_error_popup") as mock_popup:
            q0_gui.setup_for_cryo_params()
            mock_popup.assert_called_once_with("No Cryomodule Selected", "Please select a cryomodule first.")

    def test_desired_cavity_amplitudes(self, q0_gui):
        """Test desiredCavityAmplitudes method."""
        amplitudes = q0_gui.desiredCavityAmplitudes

        assert isinstance(amplitudes, dict)
        assert len(amplitudes) == 8

        # All should be 0 by default (unchecked)
        for i in range(1, 9):
            assert i in amplitudes
            assert amplitudes[i] == 0

    def test_update_cryo_params_with_cm(self, q0_gui, mock_cryomodule):
        """Test update_cryo_params with cryomodule."""
        # Setup mock valve params
        mock_valve_params = Mock()
        mock_valve_params.refHeatLoadDes = 75.0
        mock_valve_params.refValvePos = 42.0
        mock_cryomodule.valveParams = mock_valve_params

        q0_gui.selected_cm = mock_cryomodule
        q0_gui.update_cryo_params()

        # Should update the spinbox values
        assert q0_gui.main_widget.ref_heat_spinbox.value() == 75.0
        assert q0_gui.main_widget.jt_pos_spinbox.value() == 42.0

    def test_update_cryo_params_without_cm(self, q0_gui):
        """Test update_cryo_params without cryomodule - should not crash."""
        q0_gui.selected_cm = None
        q0_gui.update_cryo_params()  # Should not crash

    def test_update_ll_buffer_with_cm(self, q0_gui, mock_cryomodule):
        """Test updating liquid level buffer with cryomodule."""
        q0_gui.selected_cm = mock_cryomodule
        q0_gui.update_ll_buffer(25)
        # Should not crash - the mock will handle the attribute assignment

    def test_update_ll_buffer_without_cm(self, q0_gui):
        """Test updating liquid level buffer without cryomodule."""
        q0_gui.selected_cm = None
        q0_gui.update_ll_buffer(25)  # Should not crash


class TestQ0GUIWorkerManagement:
    """Test worker initialization and management."""

    def test_worker_initialization(self, q0_gui):
        """Test that workers are initially None."""
        assert q0_gui.calibration_worker is None
        assert q0_gui.q0_setup_worker is None
        assert q0_gui.q0_meas_worker is None
        assert q0_gui.cryo_param_setup_worker is None

        # Test ramp workers
        for i in range(1, 9):
            assert q0_gui.q0_ramp_workers[i] is None

    def test_cavity_controls_exist(self, q0_gui):
        """Test that cavity amplitude controls are created."""
        assert hasattr(q0_gui, "cav_amp_controls")
        assert len(q0_gui.cav_amp_controls) == 8

        # Test that each control exists
        for i in range(1, 9):
            assert i in q0_gui.cav_amp_controls
            assert q0_gui.cav_amp_controls[i] is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
