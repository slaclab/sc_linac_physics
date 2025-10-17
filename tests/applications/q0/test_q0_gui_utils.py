import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, mock_open

import pytest
from PyQt5.QtWidgets import QApplication

# Import the classes to test
from sc_linac_physics.applications.q0.q0_gui_utils import (
    CryoParamSetupWorker,
    Q0Worker,
    Q0SetupWorker,
    CavityRampWorker,
    CalibrationWorker,
    CavAmpControl,
    Q0Options,
    CalibrationOptions,
)


# Test fixtures
@pytest.fixture
def mock_cryomodule():
    """Mock Q0Cryomodule for testing"""
    mock_cm = Mock()
    mock_cm.name = "01"
    mock_cm.cryo_access_pv = "ACCL:L1B:01:CRYO_ACCESS"
    mock_cm.jt_auto_select_pv = "ACCL:L1B:01:JT_AUTO"
    mock_cm.q0_idx_file = "/tmp/test_q0_index.json"
    mock_cm.calib_idx_file = "/tmp/test_calib_index.json"

    # Mock Q0 measurement
    mock_q0_measurement = Mock()
    mock_q0_measurement.q0 = 1.2e10
    mock_cm.q0_measurement = mock_q0_measurement

    # Mock calibration
    mock_calibration = Mock()
    mock_calibration.dLLdt_dheat = 0.15
    mock_cm.calibration = mock_calibration

    return mock_cm


@pytest.fixture
def mock_cavity():
    """Mock Q0Cavity for testing"""
    mock_cav = Mock()
    mock_cav.number = 1
    mock_cav.is_online = True
    mock_cav.ades_max = 21.0
    mock_cav.aact_pv = "ACCL:L1B:0110:AACT"
    return mock_cav


@pytest.fixture
def qapp():
    """QApplication fixture for GUI tests"""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class TestCryoParamSetupWorker:
    """Test CryoParamSetupWorker functionality"""

    @patch("sc_linac_physics.applications.q0.q0_gui_utils.caget")
    @patch("sc_linac_physics.applications.q0.q0_gui_utils.caput")
    def test_successful_setup(self, mock_caput, mock_caget, mock_cryomodule):
        # Arrange
        mock_caget.return_value = 1  # Assuming CRYO_ACCESS_VALUE is 1
        with patch(
            "sc_linac_physics.applications.q0.q0_utils.CRYO_ACCESS_VALUE", 1
        ):
            worker = CryoParamSetupWorker(
                mock_cryomodule, heater_setpoint=50, jt_setpoint=40
            )

            # Mock signals
            worker.status = Mock()
            worker.error = Mock()
            worker.finished = Mock()

            # Act
            worker.run()

            # Assert
            worker.status.emit.assert_called_with(
                "Checking for required cryo permissions"
            )
            worker.finished.emit.assert_called_with(
                "Cryo setup for new reference parameters in ~1 hour"
            )
            assert mock_cryomodule.heater_power == 50
            assert mock_cryomodule.jt_position == 40
            mock_caput.assert_called_with(
                mock_cryomodule.jt_auto_select_pv, 1, wait=True
            )

    @patch("sc_linac_physics.applications.q0.q0_gui_utils.caget")
    def test_insufficient_permissions(self, mock_caget, mock_cryomodule):
        # Arrange
        mock_caget.return_value = 0  # No access
        with patch(
            "sc_linac_physics.applications.q0.q0_utils.CRYO_ACCESS_VALUE", 1
        ):
            worker = CryoParamSetupWorker(mock_cryomodule)
            worker.error = Mock()

            # Act
            worker.run()

            # Assert
            worker.error.emit.assert_called_with(
                "Required cryo permissions not granted - call cryo ops"
            )


class TestQ0Worker:
    """Test Q0Worker functionality"""

    @patch("sc_linac_physics.applications.q0.q0_gui_utils.caget")
    def test_successful_q0_measurement(self, mock_caget, mock_cryomodule):
        # Arrange
        mock_caget.return_value = 1
        with patch(
            "sc_linac_physics.applications.q0.q0_utils.CRYO_ACCESS_VALUE", 1
        ):
            worker = Q0Worker(
                mock_cryomodule,
                jt_search_start=datetime.now(),
                jt_search_end=datetime.now() + timedelta(hours=1),
                desired_ll=95.0,
                ll_drop=4.0,
                desired_amplitudes=[
                    16.5,
                    16.5,
                    16.5,
                    16.5,
                    16.5,
                    16.5,
                    16.5,
                    16.5,
                ],
            )

            # Mock signals
            worker.status = Mock()
            worker.error = Mock()
            worker.finished = Mock()

            # Act
            worker.run()

            # Assert
            worker.status.emit.assert_called_with("Taking new Q0 Measurement")
            mock_cryomodule.takeNewQ0Measurement.assert_called_once()
            worker.finished.emit.assert_called_with(
                f"Recorded Q0: {mock_cryomodule.q0_measurement.q0:.2e}"
            )

    @patch("sc_linac_physics.applications.q0.q0_gui_utils.caget")
    def test_q0_measurement_with_cavity_abort(
        self, mock_caget, mock_cryomodule
    ):
        # Arrange
        from sc_linac_physics.utils.sc_linac.linac_utils import CavityAbortError

        mock_caget.return_value = 1
        mock_cryomodule.takeNewQ0Measurement.side_effect = CavityAbortError(
            "Cavity aborted"
        )

        with patch(
            "sc_linac_physics.applications.q0.q0_utils.CRYO_ACCESS_VALUE", 1
        ):
            worker = Q0Worker(
                mock_cryomodule,
                jt_search_start=datetime.now(),
                jt_search_end=datetime.now() + timedelta(hours=1),
                desired_ll=95.0,
                ll_drop=4.0,
                desired_amplitudes=[16.5] * 8,
            )

            worker.error = Mock()

            # Act
            worker.run()

            # Assert
            worker.error.emit.assert_called_with("Cavity aborted")


class TestCavityRampWorker:
    """Test CavityRampWorker functionality"""

    def test_successful_cavity_ramp(self, mock_cavity):
        # Arrange
        worker = CavityRampWorker(mock_cavity, des_amp=16.5)
        worker.status = Mock()
        worker.error = Mock()
        worker.finished = Mock()

        # Act
        worker.run()

        # Assert
        worker.status.emit.assert_called_with(
            f"Ramping Cavity {mock_cavity.number} to 16.5"
        )
        mock_cavity.setup_rf.assert_called_with(16.5)
        worker.finished.emit.assert_called_with(
            f"Cavity {mock_cavity.number} ramped up to 16.5"
        )

    def test_cavity_ramp_with_error(self, mock_cavity):
        # Arrange
        from sc_linac_physics.utils.sc_linac.linac_utils import CavityAbortError

        mock_cavity.setup_rf.side_effect = CavityAbortError("RF setup failed")
        worker = CavityRampWorker(mock_cavity, des_amp=16.5)
        worker.error = Mock()

        # Act
        worker.run()

        # Assert
        worker.error.emit.assert_called_with("RF setup failed")


class TestCalibrationWorker:
    """Test CalibrationWorker functionality"""

    @patch("sc_linac_physics.applications.q0.q0_gui_utils.caget")
    def test_successful_calibration(self, mock_caget, mock_cryomodule):
        # Arrange
        mock_caget.return_value = 1
        with patch(
            "sc_linac_physics.applications.q0.q0_utils.CRYO_ACCESS_VALUE", 1
        ):
            worker = CalibrationWorker(
                mock_cryomodule,
                jt_search_start=datetime.now(),
                jt_search_end=datetime.now() + timedelta(hours=1),
                desired_ll=95.0,
                num_cal_steps=5,
                ll_drop=4.0,
                heat_start=40,
                heat_end=112,
            )

            worker.status = Mock()
            worker.finished = Mock()

            # Act
            worker.run()

            # Assert
            worker.status.emit.assert_called_with("Taking new calibration")
            mock_cryomodule.take_new_calibration.assert_called_once()
            worker.finished.emit.assert_called_with("Calibration Loaded")


class TestCavAmpControl:
    """Test CavAmpControl GUI component"""

    def test_cavity_control_initialization(self, qapp):
        # Arrange & Act
        control = CavAmpControl()

        # Assert
        assert control.groupbox is not None
        assert control.groupbox.isCheckable()
        assert control.desAmpSpinbox is not None
        assert control.aact_label is not None

    def test_connect_online_cavity(self, qapp, mock_cavity):
        # Arrange
        control = CavAmpControl()

        # Act
        control.connect(mock_cavity)

        # Assert
        assert control.groupbox.title() == f"Cavity {mock_cavity.number}"
        assert control.groupbox.isChecked()
        assert control.desAmpSpinbox.value() == 16.6  # min(16.6, 21.0)
        assert control.desAmpSpinbox.maximum() == mock_cavity.ades_max
        assert control.aact_label.channel == mock_cavity.aact_pv

    def test_connect_offline_cavity(self, qapp, mock_cavity):
        # Arrange
        mock_cavity.is_online = False
        control = CavAmpControl()

        # Act
        control.connect(mock_cavity)

        # Assert
        assert not control.groupbox.isChecked()
        assert control.desAmpSpinbox.maximum() == 0


class TestQ0Options:
    """Test Q0Options GUI component"""

    def test_q0_options_initialization(self, qapp, mock_cryomodule):
        # Arrange
        test_q0_data = {
            "2023-10-01 12:00:00": {
                "Cavity Amplitudes": [
                    16.5,
                    16.5,
                    16.5,
                    16.5,
                    16.5,
                    16.5,
                    16.5,
                    16.5,
                ]
            },
            "2023-10-02 12:00:00": {
                "Cavity Amplitudes": [
                    17.0,
                    17.0,
                    17.0,
                    17.0,
                    17.0,
                    17.0,
                    17.0,
                    17.0,
                ]
            },
        }

        with patch(
            "builtins.open", mock_open(read_data=json.dumps(test_q0_data))
        ):
            with patch(
                "sc_linac_physics.utils.qt.get_dimensions", return_value=2
            ):
                # Act
                options = Q0Options(mock_cryomodule)

                # Assert
                assert (
                    options.main_groupbox.title()
                    == f"Q0 Measurements for CM{mock_cryomodule.name}"
                )
                assert options.cryomodule == mock_cryomodule

    def test_load_q0_measurement(self, qapp, mock_cryomodule):
        # Arrange
        test_q0_data = {
            "2023-10-01 12:00:00": {"Cavity Amplitudes": [16.5] * 8}
        }

        with patch(
            "builtins.open", mock_open(read_data=json.dumps(test_q0_data))
        ):
            with patch(
                "sc_linac_physics.utils.qt.get_dimensions", return_value=1
            ):
                options = Q0Options(mock_cryomodule)
                options.q0_loaded_signal = Mock()

                # Act
                options.load_q0("2023-10-01 12:00:00")

                # Assert
                mock_cryomodule.load_q0_measurement.assert_called_with(
                    time_stamp="2023-10-01 12:00:00"
                )
                options.q0_loaded_signal.emit.assert_called_once()


class TestCalibrationOptions:
    """Test CalibrationOptions GUI component"""

    def test_calibration_options_initialization(self, qapp, mock_cryomodule):
        # Arrange
        test_cal_data = {
            "2023-10-01 12:00:00": {"slope": 0.15},
            "2023-10-02 12:00:00": {"slope": 0.16},
        }

        with patch(
            "builtins.open", mock_open(read_data=json.dumps(test_cal_data))
        ):
            with patch(
                "sc_linac_physics.utils.qt.get_dimensions", return_value=2
            ):
                # Act
                options = CalibrationOptions(mock_cryomodule)

                # Assert
                assert (
                    options.main_groupbox.title()
                    == f"Calibrations for CM{mock_cryomodule.name}"
                )
                assert options.cryomodule == mock_cryomodule

    def test_load_calibration(self, qapp, mock_cryomodule):
        # Arrange
        test_cal_data = {"2023-10-01 12:00:00": {"slope": 0.15}}

        with patch(
            "builtins.open", mock_open(read_data=json.dumps(test_cal_data))
        ):
            with patch(
                "sc_linac_physics.utils.qt.get_dimensions", return_value=1
            ):
                options = CalibrationOptions(mock_cryomodule)
                options.cal_loaded_signal = Mock()

                # Act
                options.load_calibration("2023-10-01 12:00:00")

                # Assert
                mock_cryomodule.load_calibration.assert_called_with(
                    time_stamp="2023-10-01 12:00:00"
                )
                options.cal_loaded_signal.emit.assert_called_once()


class TestIntegration:
    """Integration tests for worker coordination"""

    @patch("sc_linac_physics.applications.q0.q0_gui_utils.caget")
    def test_complete_q0_workflow(self, mock_caget, mock_cryomodule):
        """Test a complete Q0 measurement workflow"""
        # Arrange
        mock_caget.return_value = 1
        with patch(
            "sc_linac_physics.applications.q0.q0_utils.CRYO_ACCESS_VALUE", 1
        ):
            # Step 1: Setup cryo parameters
            setup_worker = CryoParamSetupWorker(mock_cryomodule)
            setup_worker.status = Mock()
            setup_worker.finished = Mock()
            setup_worker.run()

            # Step 2: Setup for Q0
            q0_setup_worker = Q0SetupWorker(
                mock_cryomodule,
                jt_search_start=datetime.now(),
                jt_search_end=datetime.now() + timedelta(hours=1),
                desired_ll=95.0,
                ll_drop=4.0,
                desired_amplitudes=[16.5] * 8,
            )
            q0_setup_worker.status = Mock()
            q0_setup_worker.finished = Mock()
            q0_setup_worker.run()

            # Step 3: Take Q0 measurement
            q0_worker = Q0Worker(
                mock_cryomodule,
                jt_search_start=datetime.now(),
                jt_search_end=datetime.now() + timedelta(hours=1),
                desired_ll=95.0,
                ll_drop=4.0,
                desired_amplitudes=[16.5] * 8,
            )
            q0_worker.status = Mock()
            q0_worker.finished = Mock()
            q0_worker.run()

            # Assert workflow completed successfully
            setup_worker.finished.emit.assert_called_once()
            q0_setup_worker.finished.emit.assert_called_once()
            q0_worker.finished.emit.assert_called_once()


class TestErrorHandling:
    """Test various error conditions"""

    def test_file_not_found_error(self, qapp, mock_cryomodule):
        """Test handling of missing configuration files"""
        with patch(
            "builtins.open", side_effect=FileNotFoundError("File not found")
        ):
            # Should not raise exception, should handle gracefully
            try:
                Q0Options(mock_cryomodule)
                # If we get here, error was handled gracefully
                assert True
            except FileNotFoundError:
                pytest.fail("FileNotFoundError should be handled gracefully")

    def test_json_decode_error(self, qapp, mock_cryomodule):
        """Test handling of corrupted JSON files"""
        with patch("builtins.open", mock_open(read_data="invalid json")):
            try:
                Q0Options(mock_cryomodule)
                assert True
            except json.JSONDecodeError:
                pytest.fail("JSONDecodeError should be handled gracefully")


# Performance tests
class TestPerformance:
    """Performance and timing tests"""

    def test_worker_timeout(self, mock_cryomodule):
        """Test that workers complete within reasonable time"""
        import time

        worker = CryoParamSetupWorker(mock_cryomodule)
        worker.status = Mock()
        worker.error = Mock()
        worker.finished = Mock()

        start_time = time.time()
        with patch(
            "sc_linac_physics.applications.q0.q0_gui_utils.caget",
            return_value=0,
        ):  # No permissions
            worker.run()
        end_time = time.time()

        # Should complete quickly when permissions denied
        assert end_time - start_time < 1.0


# Fixtures for test data
@pytest.fixture
def sample_q0_data():
    """Sample Q0 measurement data for testing"""
    return {
        "2023-10-01 12:00:00": {
            "Cavity Amplitudes": [
                16.5,
                16.5,
                16.5,
                16.5,
                16.5,
                16.5,
                16.5,
                16.5,
            ],
            "Q0": 1.2e10,
            "LL": 95.0,
        }
    }


@pytest.fixture
def sample_calibration_data():
    """Sample calibration data for testing"""
    return {
        "2023-10-01 12:00:00": {
            "slope": 0.15,
            "intercept": 2.5,
            "heat_points": [40, 60, 80, 100, 112],
        }
    }


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
