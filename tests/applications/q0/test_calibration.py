import json
import os
import tempfile
from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from sc_linac_physics.applications.q0 import q0_utils
from sc_linac_physics.applications.q0.calibration import Calibration


@pytest.fixture
def mock_cryomodule():
    """Create a mock Q0Cryomodule object."""
    cryomodule = Mock()
    cryomodule.valveParams = q0_utils.ValveParams(
        refValvePos=50.0, refHeatLoadDes=100.0, refHeatLoadAct=98.5
    )
    return cryomodule


@pytest.fixture
def temp_files():
    """Create temporary files for testing."""
    calib_data_file = tempfile.NamedTemporaryFile(
        mode="w", delete=False, suffix=".json"
    )
    calib_idx_file = tempfile.NamedTemporaryFile(
        mode="w", delete=False, suffix=".json"
    )

    yield calib_data_file.name, calib_idx_file.name

    # Cleanup
    os.unlink(calib_data_file.name)
    os.unlink(calib_idx_file.name)


@pytest.fixture
def calibration(mock_cryomodule):
    """Create a Calibration instance for testing."""
    time_stamp = "2023-01-15 10:30:00"
    return Calibration(time_stamp, mock_cryomodule)


class TestCalibrationInit:
    """Test Calibration initialization."""

    def test_init_attributes(self, calibration, mock_cryomodule):
        """Test that initialization sets correct attributes."""
        assert calibration.time_stamp == "2023-01-15 10:30:00"
        assert calibration.cryomodule == mock_cryomodule
        assert calibration.heater_runs == []
        assert calibration._slope is None
        assert calibration.adjustment == 0


class TestLoadData:
    """Test loading calibration data from files."""

    @pytest.fixture
    def sample_calib_data(self):
        """Sample calibration data structure using the correct datetime format."""
        # q0_utils.DATETIME_FORMATTER is '%m/%d/%y %H:%M:%S'
        # So we need dates like '01/15/23 10:35:00'
        return {
            "2023-01-15 10:30:00": {
                "01/15/23 10:35:00": {
                    "Desired Heat Load": 50.0,
                    q0_utils.JSON_START_KEY: "01/15/23 10:35:00",
                    q0_utils.JSON_END_KEY: "01/15/23 10:45:00",
                    q0_utils.JSON_LL_KEY: {
                        "1673781300.0": 100.5,
                        "1673781360.0": 101.2,
                        "1673781420.0": 102.0,
                    },
                    q0_utils.JSON_HEATER_READBACK_KEY: 49.8,
                },
                "01/15/23 10:50:00": {
                    "Desired Heat Load": 75.0,
                    q0_utils.JSON_START_KEY: "01/15/23 10:50:00",
                    q0_utils.JSON_END_KEY: "01/15/23 11:00:00",
                    q0_utils.JSON_LL_KEY: {
                        "1673782200.0": 105.5,
                        "1673782260.0": 106.2,
                    },
                    q0_utils.JSON_HEATER_READBACK_KEY: 74.5,
                },
            }
        }

    @pytest.fixture
    def sample_calib_idx_data(self):
        """Sample calibration index data structure."""
        return {
            "2023-01-15 10:30:00": {
                "JT Valve Position": 55.0,
                "Total Reference Heater Setpoint": 110.0,
                "Total Reference Heater Readback": 108.5,
            }
        }

    def test_load_data_success(
        self, calibration, temp_files, sample_calib_data, sample_calib_idx_data
    ):
        """Test successful data loading."""
        calib_data_file, calib_idx_file = temp_files
        calibration.cryomodule.calib_data_file = calib_data_file
        calibration.cryomodule.calib_idx_file = calib_idx_file

        # Write sample data to files
        with open(calib_data_file, "w") as f:
            json.dump(sample_calib_data, f)

        with open(calib_idx_file, "w") as f:
            json.dump(sample_calib_idx_data, f)

        calibration.load_data()

        # Verify heater runs were loaded
        assert len(calibration.heater_runs) == 2

        # Verify first heater run
        run1 = calibration.heater_runs[0]
        assert run1.heat_load_des == 50.0
        assert run1.average_heat == 49.8
        assert len(run1.ll_data) == 3
        assert 1673781300.0 in run1.ll_data

        # Verify valve parameters were updated
        assert calibration.cryomodule.valveParams.refValvePos == 55.0
        assert calibration.cryomodule.valveParams.refHeatLoadDes == 110.0
        assert calibration.cryomodule.valveParams.refHeatLoadAct == 108.5

    def test_load_data_datetime_parsing(
        self, calibration, temp_files, sample_calib_data, sample_calib_idx_data
    ):
        """Test that datetime strings are properly parsed."""
        calib_data_file, calib_idx_file = temp_files
        calibration.cryomodule.calib_data_file = calib_data_file
        calibration.cryomodule.calib_idx_file = calib_idx_file

        with open(calib_data_file, "w") as f:
            json.dump(sample_calib_data, f)

        with open(calib_idx_file, "w") as f:
            json.dump(sample_calib_idx_data, f)

        calibration.load_data()

        run1 = calibration.heater_runs[0]
        assert isinstance(run1._start_time, datetime)
        assert isinstance(run1._end_time, datetime)
        assert run1._start_time.year == 2023
        assert run1._start_time.month == 1
        assert run1._start_time.day == 15

    def test_load_data_file_not_found(self, calibration):
        """Test handling of missing files."""
        calibration.cryomodule.calib_data_file = "/nonexistent/file.json"
        calibration.cryomodule.calib_idx_file = "/nonexistent/file2.json"

        with pytest.raises(FileNotFoundError):
            calibration.load_data()


class TestSaveData:
    """Test saving calibration data."""

    @pytest.fixture
    def calibration_with_runs(self, calibration):
        """Calibration with pre-populated heater runs."""
        run1 = q0_utils.HeaterRun(50.0)
        run1._start_time = datetime(2023, 1, 15, 10, 35, 0)
        run1._end_time = datetime(2023, 1, 15, 10, 45, 0)
        run1.ll_data = {1673781300.0: 100.5, 1673781360.0: 101.2}
        run1.average_heat = 49.8

        run2 = q0_utils.HeaterRun(75.0)
        run2._start_time = datetime(2023, 1, 15, 10, 50, 0)
        run2._end_time = datetime(2023, 1, 15, 11, 0, 0)
        run2.ll_data = {1673782200.0: 105.5}
        run2.average_heat = 74.5

        calibration.heater_runs = [run1, run2]
        return calibration

    @patch("sc_linac_physics.applications.q0.q0_utils.update_json_data")
    def test_save_data(self, mock_update_json, calibration_with_runs):
        """Test that save_data calls update_json_data with correct data."""
        calibration_with_runs.cryomodule.calib_data_file = "test_file.json"

        calibration_with_runs.save_data()

        # Verify update_json_data was called
        mock_update_json.assert_called_once()

        # Get the call arguments
        args = mock_update_json.call_args[0]
        assert args[0] == "test_file.json"
        assert args[1] == "2023-01-15 10:30:00"

        # Verify the data structure
        saved_data = args[2]
        assert len(saved_data) == 2

        # Check first run data
        first_key = list(saved_data.keys())[0]
        first_run_data = saved_data[first_key]
        assert "Desired Heat Load" in first_run_data
        assert q0_utils.JSON_HEATER_READBACK_KEY in first_run_data
        assert q0_utils.JSON_LL_KEY in first_run_data


class TestSaveResults:
    """Test saving calibration results."""

    @patch("sc_linac_physics.applications.q0.q0_utils.update_json_data")
    def test_save_results(self, mock_update_json, calibration):
        """Test that save_results saves correct data."""
        calibration.cryomodule.calib_idx_file = "test_idx_file.json"
        calibration._slope = 2.5
        calibration.adjustment = 1.2

        calibration.save_results()

        mock_update_json.assert_called_once()

        args = mock_update_json.call_args[0]
        assert args[0] == "test_idx_file.json"
        assert args[1] == "2023-01-15 10:30:00"

        saved_data = args[2]
        assert saved_data[q0_utils.JSON_START_KEY] == "2023-01-15 10:30:00"
        assert saved_data["Calculated Heat vs dll/dt Slope"] == 2.5
        assert saved_data["Calculated Adjustment"] == 1.2
        assert saved_data["JT Valve Position"] == 50.0
        assert saved_data["Total Reference Heater Setpoint"] == 100.0
        assert saved_data["Total Reference Heater Readback"] == 98.5


class TestDLLdtDheat:
    """Test the dLLdt_dheat property."""

    def test_slope_calculation(self, calibration):
        """Test slope calculation from heater runs."""
        # Create mock heater runs with known values
        run1 = Mock()
        run1.average_heat = 10.0
        run1.dll_dt = 5.0

        run2 = Mock()
        run2.average_heat = 20.0
        run2.dll_dt = 10.0

        run3 = Mock()
        run3.average_heat = 30.0
        run3.dll_dt = 15.0

        calibration.heater_runs = [run1, run2, run3]

        slope = calibration.dLLdt_dheat

        # With perfect linear data, slope should be 0.5
        assert slope is not None
        assert pytest.approx(slope, rel=1e-10) == 0.5

    def test_slope_caching(self, calibration):
        """Test that slope is calculated only once."""
        run1 = Mock()
        run1.average_heat = 10.0
        run1.dll_dt = 5.0

        run2 = Mock()
        run2.average_heat = 20.0
        run2.dll_dt = 10.0

        calibration.heater_runs = [run1, run2]

        # First call calculates
        slope1 = calibration.dLLdt_dheat

        # Second call should return cached value
        slope2 = calibration.dLLdt_dheat

        assert slope1 == slope2
        assert slope1 is not None

    def test_slope_with_identical_heat_values(self, calibration):
        """Test handling when all heat values are identical (raises ValueError)."""
        run1 = Mock()
        run1.average_heat = 10.0
        run1.dll_dt = 5.0

        run2 = Mock()
        run2.average_heat = 10.0  # Same heat
        run2.dll_dt = 10.0

        calibration.heater_runs = [run1, run2]

        # scipy.linregress raises ValueError for identical x values
        with pytest.raises(
            ValueError, match="Cannot calculate a linear regression"
        ):
            _ = calibration.dLLdt_dheat

    def test_adjustment_set_during_calculation(self, calibration):
        """Test that adjustment (intercept) is set during slope calculation."""
        run1 = Mock()
        run1.average_heat = 10.0
        run1.dll_dt = 7.0  # Intercept will be 2.0 if slope is 0.5

        run2 = Mock()
        run2.average_heat = 20.0
        run2.dll_dt = 12.0

        calibration.heater_runs = [run1, run2]

        slope = calibration.dLLdt_dheat

        assert slope is not None
        assert calibration.adjustment != 0


class TestGetHeat:
    """Test the get_heat method."""

    def test_get_heat_calculation(self, calibration):
        """Test heat calculation from dll_dt."""
        calibration._slope = 2.0
        calibration.adjustment = 1.0

        # heat = (dll_dt - adjustment) / slope
        # heat = (11.0 - 1.0) / 2.0 = 5.0
        heat = calibration.get_heat(11.0)

        assert pytest.approx(heat) == 5.0

    def test_get_heat_with_zero_adjustment(self, calibration):
        """Test heat calculation with zero adjustment."""
        calibration._slope = 0.5
        calibration.adjustment = 0

        heat = calibration.get_heat(10.0)

        assert pytest.approx(heat) == 20.0

    def test_get_heat_negative_result(self, calibration):
        """Test that negative heat can be calculated."""
        calibration._slope = 1.0
        calibration.adjustment = 10.0

        heat = calibration.get_heat(5.0)

        assert pytest.approx(heat) == -5.0


class TestIntegration:
    """Integration tests combining multiple methods."""

    def test_full_calibration_workflow(self, temp_files, mock_cryomodule):
        """Test a complete calibration workflow."""
        calib_data_file, calib_idx_file = temp_files
        mock_cryomodule.calib_data_file = calib_data_file
        mock_cryomodule.calib_idx_file = calib_idx_file

        # Initialize empty files
        with open(calib_data_file, "w") as f:
            json.dump({}, f)
        with open(calib_idx_file, "w") as f:
            json.dump({}, f)

        # Create calibration and add runs
        time_stamp = "2023-01-15 10:30:00"
        calibration = Calibration(time_stamp, mock_cryomodule)

        run1 = q0_utils.HeaterRun(50.0)
        run1._start_time = datetime(2023, 1, 15, 10, 35, 0)
        run1._end_time = datetime(2023, 1, 15, 10, 45, 0)
        run1.ll_data = {1673781300.0: 100.5}
        run1.average_heat = 49.8

        calibration.heater_runs = [run1]

        # Save data
        calibration.save_data()

        # Prepare the calib_idx_file with the required data for loading
        idx_data = {
            time_stamp: {
                "JT Valve Position": 55.0,
                "Total Reference Heater Setpoint": 110.0,
                "Total Reference Heater Readback": 108.5,
            }
        }
        with open(calib_idx_file, "w") as f:
            json.dump(idx_data, f)

        # Create new calibration and load data
        calibration2 = Calibration(time_stamp, mock_cryomodule)
        calibration2.load_data()

        # Verify loaded data matches
        assert len(calibration2.heater_runs) == 1
        assert calibration2.heater_runs[0].heat_load_des == 50.0
        assert calibration2.heater_runs[0].average_heat == 49.8
