import json
from datetime import datetime
from unittest.mock import Mock, patch, mock_open

import numpy as np
import pytest

from sc_linac_physics.applications.q0.rf_measurement import Q0Measurement
from sc_linac_physics.applications.q0.rf_run import RFRun


# First, let's create a utility to get the actual format
def get_actual_datetime_format():
    """Get the actual datetime format from q0_utils"""
    from sc_linac_physics.applications.q0 import q0_utils

    return q0_utils.DATETIME_FORMATTER


@pytest.fixture
def datetime_format():
    """Provide the actual datetime format used by the application"""
    return get_actual_datetime_format()


@pytest.fixture
def valid_timestamp(datetime_format):
    """Generate a valid timestamp in the correct format"""
    test_datetime = datetime(2023, 10, 1, 12, 0, 0)
    return test_datetime.strftime(datetime_format)


@pytest.fixture
def invalid_timestamp(datetime_format):
    """Generate an invalid timestamp in the wrong format"""
    # If format uses %m/%d/%y, return ISO format; if ISO, return US format
    if "%Y-%m-%d" in datetime_format:
        return "10/01/23 12:00:00"
    else:
        return "2023-10-01 12:00:00"


@pytest.fixture
def mock_cryomodule():
    """Mock cryomodule with required attributes"""
    mock_cm = Mock()
    mock_cm.name = "01"
    mock_cm.q0_data_file = "/tmp/test_q0_data.json"
    mock_cm.q0_idx_file = "/tmp/test_q0_index.json"

    # Mock calibration
    mock_calibration = Mock()
    mock_calibration.time_stamp = "2023-10-01 10:00:00"
    mock_calibration.get_heat.return_value = 50.0
    mock_cm.calibration = mock_calibration

    # Mock cavities
    mock_cavity = Mock()
    mock_cavity.length = 1.038  # meters
    mock_cavity.r_over_q = 1036.0  # ohms
    mock_cm.cavities = {1: mock_cavity}

    return mock_cm


@pytest.fixture
def sample_amplitudes():
    """Sample cavity amplitudes"""
    return {1: 16.5, 2: 16.5, 3: 16.5, 4: 16.5, 5: 16.5, 6: 16.5, 7: 16.5, 8: 16.5}


@pytest.fixture
def sample_measurement_data(datetime_format):
    """Sample measurement data with correct datetime format"""
    test_datetime = datetime(2023, 10, 1, 12, 0, 0)
    heater_start = datetime(2023, 10, 1, 11, 0, 0)
    heater_end = datetime(2023, 10, 1, 11, 30, 0)
    rf_start = datetime(2023, 10, 1, 12, 0, 0)
    rf_end = datetime(2023, 10, 1, 12, 30, 0)

    return {
        test_datetime.strftime(datetime_format): {
            "Heater Run": {
                "Start Time": heater_start.strftime(datetime_format),
                "End Time": heater_end.strftime(datetime_format),
                "LL Data": {"0.0": 95.0, "1800.0": 91.0},
                "Heater Readback": 40.0,
                "dLL/dt": -0.002,
            },
            "RF Run": {
                "Start Time": rf_start.strftime(datetime_format),
                "End Time": rf_end.strftime(datetime_format),
                "LL Data": {"0.0": 95.0, "1800.0": 88.0},
                "Heater Readback": 60.0,
                "Average Pressure": 16.2,
                "dLL/dt": -0.004,
                "Cavity Amplitudes": {
                    "1": 16.5,
                    "2": 16.5,
                    "3": 16.5,
                    "4": 16.5,
                    "5": 16.5,
                    "6": 16.5,
                    "7": 16.5,
                    "8": 16.5,
                },
            },
        }
    }


@pytest.fixture
def setup_complete_measurement(mock_cryomodule, sample_amplitudes):
    """Fixture to create a measurement with all required components set up"""

    def _setup(amplitudes=None):
        if amplitudes is None:
            amplitudes = sample_amplitudes

        measurement = Q0Measurement(mock_cryomodule)
        measurement.start_time = datetime(2023, 10, 1, 12, 0, 0)
        measurement.amplitudes = amplitudes
        measurement.heater_run_heatload = 40.0

        # Setup heater run data
        measurement.heater_run.dll_dt = -0.002
        measurement.heater_run.average_heat = 40.0
        measurement.heater_run.start_time = datetime(2023, 10, 1, 11, 0, 0)
        measurement.heater_run.end_time = datetime(2023, 10, 1, 11, 30, 0)
        measurement.heater_run.ll_data = {0.0: 95.0, 1800.0: 91.0}

        # Setup RF run data
        measurement.rf_run.dll_dt = -0.004
        measurement.rf_run.avg_pressure = 16.2
        measurement.rf_run.start_time = datetime(2023, 10, 1, 12, 0, 0)
        measurement.rf_run.end_time = datetime(2023, 10, 1, 12, 30, 0)
        measurement.rf_run.ll_data = {0.0: 95.0, 1800.0: 88.0}
        measurement.rf_run.average_heat = 60.0

        return measurement

    return _setup


class TestQ0MeasurementInitialization:
    """Test Q0Measurement initialization"""

    def test_initialization(self, mock_cryomodule):
        """Test basic initialization"""
        measurement = Q0Measurement(mock_cryomodule)

        assert measurement.cryomodule == mock_cryomodule
        assert measurement.heater_run is None
        assert measurement.rf_run is None
        assert measurement._raw_heat is None
        assert measurement._adjustment is None
        assert measurement._heat_load is None
        assert measurement._q0 is None
        assert measurement._start_time is None
        assert measurement._amplitudes is None
        assert measurement._heater_run_heatload is None


class TestAmplitudesPropertyValidation:
    """Test amplitudes property with validation"""

    def test_amplitudes_valid_input(self, mock_cryomodule, sample_amplitudes):
        """Test amplitudes setter with valid input"""
        measurement = Q0Measurement(mock_cryomodule)

        measurement.amplitudes = sample_amplitudes

        assert measurement.amplitudes == sample_amplitudes
        assert isinstance(measurement.rf_run, RFRun)
        assert measurement.rf_run.amplitudes == sample_amplitudes

    def test_amplitudes_invalid_type(self, mock_cryomodule):
        """Test amplitudes setter with invalid type"""
        measurement = Q0Measurement(mock_cryomodule)

        with pytest.raises(TypeError, match="Amplitudes must be a dictionary"):
            measurement.amplitudes = [16.5, 16.5, 16.5]

    def test_amplitudes_empty_dict(self, mock_cryomodule):
        """Test amplitudes setter with empty dictionary"""
        measurement = Q0Measurement(mock_cryomodule)

        with pytest.raises(ValueError, match="Amplitudes dictionary cannot be empty"):
            measurement.amplitudes = {}

    def test_amplitudes_invalid_cavity_number_type(self, mock_cryomodule):
        """Test amplitudes setter with non-integer cavity numbers"""
        measurement = Q0Measurement(mock_cryomodule)

        with pytest.raises(TypeError, match="Cavity number must be integer"):
            measurement.amplitudes = {"1": 16.5, "2": 16.5}

    def test_amplitudes_invalid_amplitude_type(self, mock_cryomodule):
        """Test amplitudes setter with non-numeric amplitudes"""
        measurement = Q0Measurement(mock_cryomodule)

        with pytest.raises(TypeError, match="Amplitude must be numeric"):
            measurement.amplitudes = {1: "16.5", 2: 16.5}

    def test_amplitudes_negative_values(self, mock_cryomodule):
        """Test amplitudes setter with negative amplitudes"""
        measurement = Q0Measurement(mock_cryomodule)

        with pytest.raises(ValueError, match="Amplitude cannot be negative"):
            measurement.amplitudes = {1: -16.5, 2: 16.5}

    def test_amplitudes_resets_calculated_properties(self, mock_cryomodule, sample_amplitudes):
        """Test that setting amplitudes resets calculated properties"""
        measurement = Q0Measurement(mock_cryomodule)

        # Set some calculated properties
        measurement._raw_heat = 50.0
        measurement._adjustment = 2.0
        measurement._heat_load = 52.0
        measurement._q0 = 1.2e10

        # Set amplitudes should reset these
        measurement.amplitudes = sample_amplitudes

        assert measurement._raw_heat is None
        assert measurement._adjustment is None
        assert measurement._heat_load is None
        assert measurement._q0 is None


class TestStartTimeProperty:
    """Test start_time property"""

    def test_start_time_setter_getter(self, mock_cryomodule, datetime_format):
        """Test start_time setter and getter"""
        measurement = Q0Measurement(mock_cryomodule)
        test_time = datetime(2023, 10, 1, 12, 0, 0)

        measurement.start_time = test_time

        expected_string = test_time.strftime(datetime_format)
        assert measurement.start_time == expected_string

    def test_start_time_immutable_after_set(self, mock_cryomodule, datetime_format):
        """Test that start_time cannot be changed once set"""
        measurement = Q0Measurement(mock_cryomodule)

        first_time = datetime(2023, 10, 1, 12, 0, 0)
        second_time = datetime(2023, 10, 2, 12, 0, 0)

        measurement.start_time = first_time
        first_expected = first_time.strftime(datetime_format)

        measurement.start_time = second_time  # Should not change

        assert measurement.start_time == first_expected


class TestLoadDataMethod:
    """Test load_data method with improved error handling"""

    def test_load_data_invalid_timestamp_format(self, mock_cryomodule):
        """Test load_data with completely invalid timestamp format"""
        measurement = Q0Measurement(mock_cryomodule)

        with pytest.raises(ValueError, match="Invalid timestamp format"):
            measurement.load_data("invalid-timestamp")

    def test_load_data_wrong_timestamp_format(self, mock_cryomodule, invalid_timestamp):
        """Test load_data with wrong but valid timestamp format"""
        measurement = Q0Measurement(mock_cryomodule)

        # The timestamp format is wrong, so it should fail at datetime parsing
        with pytest.raises(ValueError, match="Invalid timestamp format"):
            measurement.load_data(invalid_timestamp)

    def test_load_data_file_not_found(self, mock_cryomodule, valid_timestamp):
        """Test load_data when file doesn't exist"""
        measurement = Q0Measurement(mock_cryomodule)

        with patch("builtins.open", side_effect=FileNotFoundError()):
            with pytest.raises(FileNotFoundError, match="Q0 data file not found"):
                measurement.load_data(valid_timestamp)

    def test_load_data_invalid_json(self, mock_cryomodule, valid_timestamp):
        """Test load_data with invalid JSON"""
        measurement = Q0Measurement(mock_cryomodule)

        with patch("builtins.open", mock_open(read_data="invalid json")):
            with pytest.raises(ValueError, match="Invalid JSON in Q0 data file"):
                measurement.load_data(valid_timestamp)

    def test_load_data_timestamp_not_found(self, mock_cryomodule, valid_timestamp, datetime_format):
        """Test load_data when timestamp is not in data"""
        measurement = Q0Measurement(mock_cryomodule)

        # Create data with a different timestamp
        different_datetime = datetime(2023, 10, 2, 12, 0, 0)
        different_timestamp = different_datetime.strftime(datetime_format)
        data = {different_timestamp: {}}

        with patch("builtins.open", mock_open(read_data=json.dumps(data))):
            with pytest.raises(KeyError, match="No data found for timestamp"):
                measurement.load_data(valid_timestamp)

    def test_load_data_missing_required_fields(self, mock_cryomodule, valid_timestamp):
        """Test load_data with missing required fields"""
        measurement = Q0Measurement(mock_cryomodule)

        # Data missing required keys
        incomplete_data = {valid_timestamp: {"Heater Run": {}}}  # Missing required fields

        with patch("builtins.open", mock_open(read_data=json.dumps(incomplete_data))):
            with patch("sc_linac_physics.applications.q0.q0_utils.JSON_HEATER_RUN_KEY", "Heater Run"):
                with pytest.raises(ValueError, match="Missing required data field"):
                    measurement.load_data(valid_timestamp)

    def test_load_data_success(self, mock_cryomodule, valid_timestamp, sample_measurement_data):
        """Test successful data loading"""
        measurement = Q0Measurement(mock_cryomodule)

        with patch("builtins.open", mock_open(read_data=json.dumps(sample_measurement_data))):
            with patch.object(measurement, "_load_heater_run_data") as mock_load_heater:
                with patch.object(measurement, "_load_rf_run_data") as mock_load_rf:
                    with patch.object(measurement, "save_data") as mock_save:
                        with patch("sc_linac_physics.applications.q0.q0_utils.JSON_HEATER_RUN_KEY", "Heater Run"):
                            with patch(
                                "sc_linac_physics.applications.q0.q0_utils.JSON_RF_RUN_KEY", "RF Run"
                            ):  # Fixed: removed trailing space
                                measurement.load_data(valid_timestamp)

        assert measurement.start_time == valid_timestamp
        mock_load_heater.assert_called_once()
        mock_load_rf.assert_called_once()
        mock_save.assert_called_once()


class TestLoadHelperMethods:
    """Test _load_heater_run_data and _load_rf_run_data methods"""

    def test_load_heater_run_data(self, mock_cryomodule, datetime_format):
        """Test _load_heater_run_data method"""
        measurement = Q0Measurement(mock_cryomodule)

        heater_start = datetime(2023, 10, 1, 11, 0, 0)
        heater_end = datetime(2023, 10, 1, 11, 30, 0)

        heater_data = {
            "Heater Run": {
                "Start Time": heater_start.strftime(datetime_format),
                "End Time": heater_end.strftime(datetime_format),
                "LL Data": {"0.0": 95.0, "1800.0": 91.0},
                "Heater Readback": 40.0,
                "dLL/dt": -0.002,
            }
        }

        with patch("sc_linac_physics.applications.q0.q0_utils.JSON_HEATER_RUN_KEY", "Heater Run"):
            with patch("sc_linac_physics.applications.q0.q0_utils.JSON_HEATER_READBACK_KEY", "Heater Readback"):
                with patch("sc_linac_physics.applications.q0.q0_utils.JSON_START_KEY", "Start Time"):
                    with patch("sc_linac_physics.applications.q0.q0_utils.JSON_END_KEY", "End Time"):
                        with patch("sc_linac_physics.applications.q0.q0_utils.JSON_LL_KEY", "LL Data"):
                            measurement._load_heater_run_data(heater_data)

        assert measurement.heater_run_heatload == 40.0
        assert measurement.heater_run.average_heat == 40.0
        assert measurement.heater_run.ll_data == {0.0: 95.0, 1800.0: 91.0}

    def test_load_rf_run_data(self, mock_cryomodule, datetime_format):
        """Test _load_rf_run_data method"""
        measurement = Q0Measurement(mock_cryomodule)

        rf_start = datetime(2023, 10, 1, 12, 0, 0)
        rf_end = datetime(2023, 10, 1, 12, 30, 0)

        rf_data = {
            "RF Run": {
                "Start Time": rf_start.strftime(datetime_format),
                "End Time": rf_end.strftime(datetime_format),
                "LL Data": {"0.0": 95.0, "1800.0": 88.0},
                "Heater Readback": 60.0,
                "Average Pressure": 16.2,
                "dLL/dt": -0.004,
                "Cavity Amplitudes": {"1": 16.5, "2": 16.5, "3": 16.5, "4": 16.5},
            }
        }

        with patch("sc_linac_physics.applications.q0.q0_utils.JSON_RF_RUN_KEY", "RF Run"):
            with patch("sc_linac_physics.applications.q0.q0_utils.JSON_CAV_AMPS_KEY", "Cavity Amplitudes"):
                with patch("sc_linac_physics.applications.q0.q0_utils.JSON_START_KEY", "Start Time"):
                    with patch("sc_linac_physics.applications.q0.q0_utils.JSON_END_KEY", "End Time"):
                        with patch(
                            "sc_linac_physics.applications.q0.q0_utils.JSON_HEATER_READBACK_KEY", "Heater Readback"
                        ):
                            with patch("sc_linac_physics.applications.q0.q0_utils.JSON_LL_KEY", "LL Data"):
                                with patch(
                                    "sc_linac_physics.applications.q0.q0_utils.JSON_AVG_PRESS_KEY", "Average Pressure"
                                ):
                                    measurement._load_rf_run_data(rf_data)

        assert measurement.amplitudes == {1: 16.5, 2: 16.5, 3: 16.5, 4: 16.5}
        assert measurement.rf_run.average_heat == 60.0
        assert measurement.rf_run.avg_pressure == 16.2
        assert measurement.rf_run.ll_data == {0.0: 95.0, 1800.0: 88.0}


class TestSaveDataMethod:
    """Test save_data method"""

    @patch("sc_linac_physics.applications.q0.q0_utils.make_json_file")
    @patch("sc_linac_physics.applications.q0.q0_utils.update_json_data")
    def test_save_data(self, mock_update_json, mock_make_json, setup_complete_measurement):
        """Test data saving"""
        measurement = setup_complete_measurement()

        measurement.save_data()

        mock_make_json.assert_called_once_with(measurement.cryomodule.q0_data_file)
        mock_update_json.assert_called_once()


class TestSaveResultsMethod:
    """Test save_results method"""

    @patch("sc_linac_physics.applications.q0.q0_utils.update_json_data")
    def test_save_results(self, mock_update_json, setup_complete_measurement):
        """Test saving measurement results"""
        measurement = setup_complete_measurement()

        # Mock calculated properties
        measurement._heat_load = 57.0
        measurement._raw_heat = 55.0
        measurement._adjustment = 2.0
        measurement._q0 = 1.2e10

        measurement.save_results()

        mock_update_json.assert_called_once()
        call_args = mock_update_json.call_args

        assert call_args[0][0] == measurement.cryomodule.q0_idx_file
        saved_data = call_args[0][2]
        assert saved_data["Calculated Adjusted Heat Load"] == 57.0
        assert saved_data["Calculated Raw Heat Load"] == 55.0
        assert saved_data["Calculated Adjustment"] == 2.0
        assert saved_data["Calculated Q0"] == 1.2e10


class TestCalculatedProperties:
    """Test calculated properties (raw_heat, adjustment, heat_load, q0)"""

    def test_raw_heat_calculation_and_caching(self, setup_complete_measurement):
        """Test raw heat calculation and caching"""
        measurement = setup_complete_measurement()
        measurement.cryomodule.calibration.get_heat.return_value = 55.0

        # First call should calculate
        raw_heat = measurement.raw_heat
        assert raw_heat == 55.0
        measurement.cryomodule.calibration.get_heat.assert_called_with(-0.004)

        # Second call should use cached value
        raw_heat_2 = measurement.raw_heat
        assert raw_heat_2 == 55.0
        assert measurement.cryomodule.calibration.get_heat.call_count == 1

    def test_adjustment_calculation(self, setup_complete_measurement):
        """Test adjustment calculation"""
        measurement = setup_complete_measurement()

        def mock_get_heat(dll_dt):
            if dll_dt == -0.002:
                return 38.0
            return 55.0

        measurement.cryomodule.calibration.get_heat.side_effect = mock_get_heat

        adjustment = measurement.adjustment
        assert adjustment == 2.0  # 40.0 - 38.0

    def test_heat_load_calculation(self, setup_complete_measurement):
        """Test heat load calculation"""
        measurement = setup_complete_measurement()

        # Mock the calibration to return specific values
        def mock_get_heat(dll_dt):
            if dll_dt == -0.002:  # heater run
                return 38.0
            elif dll_dt == -0.004:  # rf run
                return 55.0
            return 0.0

        measurement.cryomodule.calibration.get_heat.side_effect = mock_get_heat

        heat_load = measurement.heat_load
        # raw_heat (55.0) + adjustment (40.0 - 38.0 = 2.0) = 57.0
        assert heat_load == 57.0

    @patch("sc_linac_physics.applications.q0.q0_utils.calc_q0")
    def test_q0_calculation(self, mock_calc_q0, setup_complete_measurement, sample_amplitudes):
        """Test Q0 calculation"""
        measurement = setup_complete_measurement()

        # Mock the calibration for heat calculations
        def mock_get_heat(dll_dt):
            if dll_dt == -0.002:
                return 38.0
            elif dll_dt == -0.004:
                return 55.0
            return 0.0

        measurement.cryomodule.calibration.get_heat.side_effect = mock_get_heat
        mock_calc_q0.return_value = 1.2e10

        q0_value = measurement.q0

        expected_effective_amp = np.sqrt(sum(amp**2 for amp in sample_amplitudes.values()))

        mock_calc_q0.assert_called_once_with(
            amplitude=expected_effective_amp,
            rf_heat_load=57.0,  # 55.0 + 2.0
            avg_pressure=16.2,
            cav_length=measurement.cryomodule.cavities[1].length,
            r_over_q=measurement.cryomodule.cavities[1].r_over_q,
        )

        assert q0_value == 1.2e10


class TestEdgeCases:
    """Test edge cases and error conditions"""

    def test_q0_calculation_missing_cavity(self, setup_complete_measurement):
        """Test Q0 calculation when cavity is missing"""
        measurement = setup_complete_measurement()

        # Remove cavity
        measurement.cryomodule.cavities = {}

        # Mock calibration for other calculations
        measurement.cryomodule.calibration.get_heat.side_effect = lambda x: 50.0

        with pytest.raises(KeyError):
            _ = measurement.q0

    def test_effective_amplitude_calculation_edge_cases(self, setup_complete_measurement):
        """Test effective amplitude calculation with edge cases"""
        # Test with zero amplitudes
        zero_amplitudes = {1: 0.0, 2: 0.0}
        measurement = setup_complete_measurement(amplitudes=zero_amplitudes)

        # Mock calibration
        measurement.cryomodule.calibration.get_heat.side_effect = lambda x: 50.0

        with patch("sc_linac_physics.applications.q0.q0_utils.calc_q0") as mock_calc_q0:
            mock_calc_q0.return_value = 0.0
            _ = measurement.q0

            call_args = mock_calc_q0.call_args[1]
            assert call_args["amplitude"] == 0.0

    def test_property_access_without_required_data(self, mock_cryomodule):
        """Test accessing properties without required data"""
        measurement = Q0Measurement(mock_cryomodule)

        # Should raise AttributeError when rf_run is None
        with pytest.raises(AttributeError):
            _ = measurement.raw_heat

        with pytest.raises(AttributeError):
            _ = measurement.adjustment

    def test_property_access_with_missing_heater_run(self, mock_cryomodule, sample_amplitudes):
        """Test accessing adjustment property without heater_run"""
        measurement = Q0Measurement(mock_cryomodule)
        measurement.amplitudes = sample_amplitudes  # This creates rf_run
        measurement.rf_run.dll_dt = -0.004

        # heater_run is still None
        with pytest.raises(AttributeError):
            _ = measurement.adjustment


class TestIntegration:
    """Integration tests"""

    def test_full_measurement_workflow(self, setup_complete_measurement):
        """Test complete measurement workflow"""
        measurement = setup_complete_measurement()

        # Mock calibration responses
        def mock_get_heat(dll_dt):
            if dll_dt == -0.002:
                return 38.0  # heater run
            elif dll_dt == -0.004:
                return 55.0  # rf run
            return 0.0

        measurement.cryomodule.calibration.get_heat.side_effect = mock_get_heat

        with patch("sc_linac_physics.applications.q0.q0_utils.calc_q0", return_value=1.2e10):
            # Test all calculations work together
            assert measurement.raw_heat == 55.0
            assert measurement.adjustment == 2.0
            assert measurement.heat_load == 57.0
            assert measurement.q0 == 1.2e10

    def test_property_reset_integration(self, setup_complete_measurement):
        """Test that property reset works correctly in integration"""
        measurement = setup_complete_measurement()

        measurement.cryomodule.calibration.get_heat.side_effect = lambda x: 50.0

        # Calculate some properties
        with patch("sc_linac_physics.applications.q0.q0_utils.calc_q0", return_value=1.0e10):
            _ = measurement.raw_heat
            _ = measurement.adjustment
            _ = measurement.heat_load
            _ = measurement.q0

        # Change amplitudes - should reset calculated properties
        new_amplitudes = {1: 20.0, 2: 20.0, 3: 20.0, 4: 20.0}
        measurement.amplitudes = new_amplitudes

        # Properties should be reset
        assert measurement._raw_heat is None
        assert measurement._adjustment is None
        assert measurement._heat_load is None
        assert measurement._q0 is None

    def test_calculation_dependency_chain(self, setup_complete_measurement):
        """Test that property calculations trigger in the correct order"""
        measurement = setup_complete_measurement()

        call_order = []

        def track_get_heat(dll_dt):
            call_order.append(dll_dt)
            if dll_dt == -0.002:
                return 38.0
            elif dll_dt == -0.004:
                return 55.0
            return 0.0

        measurement.cryomodule.calibration.get_heat.side_effect = track_get_heat

        with patch("sc_linac_physics.applications.q0.q0_utils.calc_q0", return_value=1.2e10):
            # Accessing q0 should trigger the calculation chain
            _ = measurement.q0

        # Should have called get_heat for both RF run (-0.004) and heater run (-0.002)
        assert -0.004 in call_order  # for raw_heat calculation
        assert -0.002 in call_order  # for adjustment calculation


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
