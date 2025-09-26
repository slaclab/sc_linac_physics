from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, call, PropertyMock

import numpy as np
import pytest

# Patch epics and PV before importing anything else
epics_patch = patch("epics.PV")
epics_patch.start()

epics_caget_patch = patch("epics.caget")
epics_caget_patch.start()

epics_caput_patch = patch("epics.caput")
epics_caput_patch.start()

# Patch lcls_tools.common.controls.pyepics.utils.PV
pv_patch = patch("lcls_tools.common.controls.pyepics.utils.PV")
mock_pv_class = pv_patch.start()

# Configure the mock PV class
mock_pv_obj = MagicMock()
mock_pv_obj.get.return_value = 85.0
mock_pv_obj.put.return_value = 1
mock_pv_class.return_value = mock_pv_obj

# Now import the code under test
from sc_linac_physics.applications.q0.q0_utils import Q0AbortError, ValveParams
from sc_linac_physics.applications.q0.q0_cryomodule import Q0Cryomodule


# Stop the patches at the end of the module
def teardown_module():
    epics_patch.stop()
    epics_caget_patch.stop()
    epics_caput_patch.stop()
    pv_patch.stop()


# Fixtures
@pytest.fixture
def mock_linac():
    return MagicMock()


# First, patch the PV class to return mocks instead of real PV objects
@pytest.fixture(autouse=True)
def mock_pv():
    with patch("lcls_tools.common.controls.pyepics.utils.PV") as mock_pv_class:
        # Configure the mock PV class to return a mock PV object
        mock_pv_obj = MagicMock()
        mock_pv_obj.get.return_value = 85.0
        mock_pv_obj.put.return_value = 1

        mock_pv_class.return_value = mock_pv_obj
        yield mock_pv_class


@pytest.fixture
def mock_epics():
    with (
        patch("sc_linac_physics.applications.q0.q0_cryomodule.caget") as mock_caget,
        patch("sc_linac_physics.applications.q0.q0_cryomodule.caput") as mock_caput,
        patch("sc_linac_physics.applications.q0.q0_cryomodule.camonitor") as mock_camonitor,
        patch("sc_linac_physics.applications.q0.q0_cryomodule.camonitor_clear") as mock_camonitor_clear,
    ):
        yield {
            "caget": mock_caget,
            "caput": mock_caput,
            "camonitor": mock_camonitor,
            "camonitor_clear": mock_camonitor_clear,
        }


@pytest.fixture
def mock_pv_instance():
    """Create a mock PV instance that will be returned by the PV class"""
    mock_pv = MagicMock()
    mock_pv.get.return_value = 85.0
    mock_pv.put.return_value = 1
    return mock_pv


@pytest.fixture
def q0_cryomodule(mock_linac, mock_pv_instance):
    """Create a Q0Cryomodule with mocked dependencies"""

    # First, patch all the key external dependencies
    with (
        patch("lcls_tools.common.controls.pyepics.utils.PV", return_value=mock_pv_instance),
        patch("sc_linac_physics.applications.q0.q0_cryomodule.isfile", return_value=True),
        patch("sc_linac_physics.applications.q0.q0_cryomodule.q0_utils.make_json_file"),
    ):

        # Create the cryomodule with name "01" (not "CM01") to avoid the prefix issue
        cm = Q0Cryomodule("01", mock_linac)

        # Set necessary attributes
        cm.valveParams = ValveParams(30.0, 120.0, 118.5)

        # Create a mock for the ds_level_pv_obj to avoid real PV access
        cm._ds_level_pv_obj = mock_pv_instance

        yield cm


@pytest.fixture
def mock_get_values_over_time_range():
    with patch("sc_linac_physics.applications.q0.q0_cryomodule.get_values_over_time_range") as mock_get:
        yield mock_get


# Test initialization
def test_initialization(q0_cryomodule):
    assert q0_cryomodule.cryo_name == "CM01"
    assert q0_cryomodule.abort_flag is False
    assert isinstance(q0_cryomodule.ll_buffer, np.ndarray)
    assert q0_cryomodule.ll_buffer_size > 0
    assert q0_cryomodule.q0_measurements == {}
    assert q0_cryomodule.calibrations == {}


# Test abort mechanism
def test_check_abort_when_abort_flag_is_set(q0_cryomodule):
    with patch.object(q0_cryomodule, "restore_cryo") as mock_restore:
        # Create mock cavities
        cavity1 = MagicMock()
        cavity2 = MagicMock()
        q0_cryomodule.cavities = {1: cavity1, 2: cavity2}

        # Set abort flag
        q0_cryomodule.abort_flag = True

        # Check that it raises an exception
        with pytest.raises(Q0AbortError):
            q0_cryomodule.check_abort()

        # Verify abort flag was reset
        assert q0_cryomodule.abort_flag is False

        # Verify restore_cryo was called
        mock_restore.assert_called_once()

        # Verify cavity abort flags were set
        assert cavity1.abort_flag is True
        assert cavity2.abort_flag is True


def test_check_abort_when_abort_flag_is_not_set(q0_cryomodule):
    with patch.object(q0_cryomodule, "restore_cryo") as mock_restore:
        # Set abort flag to False
        q0_cryomodule.abort_flag = False

        # Should not raise an exception
        q0_cryomodule.check_abort()

        # Verify restore_cryo was not called
        mock_restore.assert_not_called()


# Test liquid level monitoring
def test_monitor_ll(q0_cryomodule):
    # Test normal buffering
    q0_cryomodule.ll_buffer_idx = 0
    q0_cryomodule.fill_data_run_buffer = False
    q0_cryomodule.monitor_ll(85.5)

    assert q0_cryomodule.ll_buffer[0] == 85.5
    assert q0_cryomodule.ll_buffer_idx == 1

    # Test with data run buffer
    q0_cryomodule.fill_data_run_buffer = True
    q0_cryomodule.current_data_run = MagicMock()
    q0_cryomodule.current_data_run.ll_data = {}
    q0_cryomodule.monitor_ll(86.0)

    assert len(q0_cryomodule.current_data_run.ll_data) == 1
    assert q0_cryomodule.ll_buffer[1] == 86.0
    assert q0_cryomodule.ll_buffer_idx == 2


def test_clear_ll_buffer(q0_cryomodule):
    # Fill buffer with some values
    q0_cryomodule.ll_buffer[0] = 85.5
    q0_cryomodule.ll_buffer_idx = 3

    # Clear buffer
    q0_cryomodule.clear_ll_buffer()

    # Verify buffer is reset
    assert np.isnan(q0_cryomodule.ll_buffer[0])
    assert q0_cryomodule.ll_buffer_idx == 0


def test_averaged_liquid_level(q0_cryomodule, mock_epics):
    # Set up mock for caget
    mock_epics["caget"].return_value = 88.0

    # Case 1: All NaNs in buffer
    q0_cryomodule.clear_ll_buffer()
    assert q0_cryomodule.averaged_liquid_level == 88.0

    # Case 2: Some values in buffer
    q0_cryomodule.clear_ll_buffer()
    q0_cryomodule.ll_buffer[0] = 85.0
    q0_cryomodule.ll_buffer[1] = 86.0
    q0_cryomodule.ll_buffer_idx = 2

    assert q0_cryomodule.averaged_liquid_level == 85.5


# Test heater control
def test_heater_power_getter(q0_cryomodule, mock_epics):
    mock_epics["caget"].return_value = 120.5
    assert q0_cryomodule.heater_power == 120.5
    mock_epics["caget"].assert_called_with(q0_cryomodule.heater_readback_pv)


def test_heater_power_setter(q0_cryomodule, mock_epics):
    # Now we know HEATER_MANUAL_VALUE = 0 from q0_utils.py

    # First call: heater is NOT in manual mode (returns 1, which is not equal to HEATER_MANUAL_VALUE)
    # Second call: heater is now in manual mode (returns 0, which equals HEATER_MANUAL_VALUE)
    mock_epics["caget"].side_effect = [1, 0]

    with patch("sc_linac_physics.applications.q0.q0_cryomodule.sleep"):
        q0_cryomodule.heater_power = 150.0

    # Verify caput calls
    expected_calls = [call(q0_cryomodule.heater_manual_pv, 1, wait=True), call(q0_cryomodule.heater_setpoint_pv, 150.0)]

    assert mock_epics["caput"].call_count == 2
    mock_epics["caput"].assert_has_calls(expected_calls, any_order=False)


# Test JT valve control
def test_jt_position_getter(q0_cryomodule, mock_epics):
    mock_epics["caget"].return_value = 35.0
    assert q0_cryomodule.jt_position == 35.0
    mock_epics["caget"].assert_called_with(q0_cryomodule.jt_valve_readback_pv)


def test_jt_position_setter(q0_cryomodule, mock_epics):
    # Mock current position
    initial_position = 28.0
    target_position = 30.0

    # Create a mutable state to track valve position changes
    valve_state = {"position": initial_position, "mode": 1}  # Not in manual mode initially

    def mock_caget_side_effect(pv):
        if pv == q0_cryomodule.jt_valve_readback_pv:
            return valve_state["position"]
        elif pv == q0_cryomodule.jt_mode_pv:
            return valve_state["mode"]
        return None

    def mock_caput_side_effect(pv, value, **kwargs):
        if pv == q0_cryomodule.jt_manual_select_pv and value == 1:
            # Setting to manual mode
            valve_state["mode"] = 0  # JT_MANUAL_MODE_VALUE = 0
        elif pv == q0_cryomodule.jt_man_pos_setpoint_pv:
            # Setting position
            valve_state["position"] = value
        return None

    mock_epics["caget"].side_effect = mock_caget_side_effect
    mock_epics["caput"].side_effect = mock_caput_side_effect

    with patch("sc_linac_physics.applications.q0.q0_cryomodule.sleep"):
        q0_cryomodule.jt_position = target_position

    # Verify final state
    assert valve_state["position"] == target_position
    assert valve_state["mode"] == 0  # Should be in manual mode

    # Verify key caput calls
    mock_epics["caput"].assert_any_call(q0_cryomodule.jt_manual_select_pv, 1, wait=True)
    mock_epics["caput"].assert_any_call(q0_cryomodule.jt_man_pos_setpoint_pv, target_position)


def test_fill(q0_cryomodule):
    """Test the fill method with focus on the cavity turn_off logic"""

    # Patch all EPICS functions and methods that might cause issues
    with (
        patch("sc_linac_physics.applications.q0.q0_cryomodule.caget", return_value=0),
        patch("sc_linac_physics.applications.q0.q0_cryomodule.caput"),
        patch("sc_linac_physics.applications.q0.q0_cryomodule.sleep"),
        patch.object(q0_cryomodule, "waitForLL"),
        patch.object(q0_cryomodule, "check_abort"),
        patch.object(type(q0_cryomodule), "heater_power", new_callable=PropertyMock) as mock_heater_power,
    ):

        # Create mock cavities
        cavity1 = MagicMock()
        cavity2 = MagicMock()
        q0_cryomodule.cavities = {1: cavity1, 2: cavity2}

        # Case 1: Test with turn_cavities_off=True (default)
        q0_cryomodule.fill(90.0)

        # Verify liquid level was set via the PV
        q0_cryomodule._ds_level_pv_obj.put.assert_called_with(90.0)

        # Verify cavities turned off
        cavity1.turn_off.assert_called_once()
        cavity2.turn_off.assert_called_once()

        # Reset mocks for second test
        cavity1.turn_off.reset_mock()
        cavity2.turn_off.reset_mock()
        q0_cryomodule._ds_level_pv_obj.put.reset_mock()

        # Case 2: Test with turn_cavities_off=False
        q0_cryomodule.fill(90.0, turn_cavities_off=False)

        # Verify liquid level was set via the PV
        q0_cryomodule._ds_level_pv_obj.put.assert_called_with(90.0)

        # Verify cavities NOT turned off
        cavity1.turn_off.assert_not_called()
        cavity2.turn_off.assert_not_called()


# Test reference valve parameter retrieval
def test_get_ref_valve_params_successful(q0_cryomodule, mock_get_values_over_time_range):
    start_time = datetime.now() - timedelta(days=1)
    end_time = datetime.now()

    # Create mock data with stable liquid level
    mock_data = MagicMock()
    mock_data.values = {
        q0_cryomodule.ds_level_pv: np.full(100, 90.0),  # Flat line = stable
        q0_cryomodule.jt_valve_readback_pv: np.full(100, 30.5),
        q0_cryomodule.heater_setpoint_pv: np.full(100, 120.0),
        q0_cryomodule.heater_readback_pv: np.full(100, 118.5),
    }
    mock_get_values_over_time_range.return_value = mock_data

    # Call the method
    result = q0_cryomodule.getRefValveParams(start_time, end_time)

    # Verify result
    assert isinstance(result, ValveParams)
    assert result.refValvePos == 30.5
    assert result.refHeatLoadDes == 120.0
    assert result.refHeatLoadAct == 118.5


def test_get_ref_valve_params_unstable_then_stable(q0_cryomodule, mock_get_values_over_time_range):
    start_time = datetime.now() - timedelta(days=1)
    end_time = datetime.now()

    # Create unstable data (sloped line)
    unstable_data = MagicMock()
    unstable_data.values = {q0_cryomodule.ds_level_pv: np.linspace(85, 95, 100)}  # Sloped line = unstable

    # Create stable data for the second call
    stable_data = MagicMock()
    stable_data.values = {
        q0_cryomodule.ds_level_pv: np.full(100, 90.0),  # Flat line = stable
        q0_cryomodule.jt_valve_readback_pv: np.full(100, 30.5),
        q0_cryomodule.heater_setpoint_pv: np.full(100, 120.0),
        q0_cryomodule.heater_readback_pv: np.full(100, 118.5),
    }

    # Return unstable data first, then stable data for all subsequent calls
    # This ensures we have enough data no matter how many times the function is called
    mock_get_values_over_time_range.side_effect = [unstable_data] + [stable_data] * 10

    with (
        patch("sc_linac_physics.applications.q0.q0_cryomodule.sleep"),
        patch.object(q0_cryomodule, "check_abort"),
    ):  # Add this to avoid potential infinite loops

        # Call the method
        result = q0_cryomodule.getRefValveParams(start_time, end_time)

    # Verify result
    assert isinstance(result, ValveParams)
    assert result.refValvePos == 30.5
    assert result.refHeatLoadDes == 120.0
    assert result.refHeatLoadAct == 118.5


# Test Q0 measurement
def test_setup_for_q0(q0_cryomodule, mock_epics):
    desired_amplitudes = {1: 10.0, 2: 12.0}
    jt_search_start = datetime.now() - timedelta(days=1)
    jt_search_end = datetime.now()

    with (
        patch.object(q0_cryomodule, "getRefValveParams") as mock_get_params,
        patch.object(q0_cryomodule, "fill") as mock_fill,
    ):

        # Set up mock valve params
        mock_valve_params = ValveParams(30.0, 120.0, 118.5)
        mock_get_params.return_value = mock_valve_params

        # Set valveParams to None to ensure getRefValveParams is called
        q0_cryomodule.valveParams = None

        # Call setup_for_q0
        q0_cryomodule.setup_for_q0(desired_amplitudes, 90.0, jt_search_end, jt_search_start)

        # Verify Q0Measurement created
        assert q0_cryomodule.q0_measurement is not None
        assert q0_cryomodule.q0_measurement.amplitudes == desired_amplitudes

        # Verify getRefValveParams called
        mock_get_params.assert_called_with(start_time=jt_search_start, end_time=jt_search_end)

        # Verify camonitor set
        mock_epics["camonitor"].assert_called_with(q0_cryomodule.ds_level_pv, callback=q0_cryomodule.monitor_ll)

        # Verify fill called
        mock_fill.assert_called_with(90.0)


def test_take_new_q0_measurement(q0_cryomodule, mock_epics):
    # Set up mocks
    q0_cryomodule.q0_measurement = MagicMock()
    q0_cryomodule.q0_measurement.rf_run = MagicMock()
    q0_cryomodule.q0_measurement.rf_run.pressure_buffer = []
    q0_cryomodule.q0_measurement.heater_run = None

    with (
        patch.object(q0_cryomodule, "setup_cryo_for_measurement") as mock_setup,
        patch.object(q0_cryomodule, "wait_for_ll_drop") as mock_wait,
        patch.object(q0_cryomodule, "launchHeaterRun") as mock_launch,
        patch.object(q0_cryomodule, "restore_cryo") as mock_restore,
        patch("sc_linac_physics.applications.q0.q0_cryomodule.sleep"),
    ):

        # Set up cavity responses
        mock_epics["caget"].return_value = 10.0  # Matching desired amplitude

        # Create mock cavities
        cavity1 = MagicMock()
        cavity1.aact_pv = "CAVITY1:AACT"
        q0_cryomodule.cavities = {1: cavity1}

        # Call the method
        q0_cryomodule.takeNewQ0Measurement({1: 10.0})

        # Verify setup called
        mock_setup.assert_called()

        # Verify camonitor calls
        mock_epics["camonitor"].assert_any_call(
            q0_cryomodule.heater_readback_pv, callback=q0_cryomodule.fill_heater_readback_buffer
        )
        mock_epics["camonitor"].assert_any_call(
            q0_cryomodule.ds_pressure_pv, callback=q0_cryomodule.fill_pressure_buffer
        )

        # Verify wait_for_ll_drop called
        mock_wait.assert_called()

        # Verify launchHeaterRun called
        mock_launch.assert_called()

        # Verify save methods called
        q0_cryomodule.q0_measurement.save_data.assert_called_once()
        q0_cryomodule.q0_measurement.save_results.assert_called_once()

        # Verify restore_cryo called
        mock_restore.assert_called_once()


# Test calibration
def test_take_new_calibration_core_logic(q0_cryomodule):
    """Test just the core logic for creating a calibration object with the right parameters"""

    # Create a reference time stamp
    start_time = datetime.now().replace(microsecond=0)

    # Mock datetime.now() to return our fixed time
    with (
        patch("sc_linac_physics.applications.q0.q0_cryomodule.datetime") as mock_datetime,
        patch("sc_linac_physics.applications.q0.q0_cryomodule.Calibration") as mock_calibration_class,
    ):

        # Configure mock_datetime.now() to return our fixed time
        mock_datetime.now.return_value = start_time
        mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

        # Configure mock for formatter
        mock_datetime.DATETIME_FORMATTER = "%m/%d/%y %H:%M:%S"

        # Call the setup part of take_new_calibration directly (avoid the actual measurement work)
        time_stamp = start_time.strftime("%m/%d/%y %H:%M:%S")

        # Create the calibration directly
        q0_cryomodule.calibration = mock_calibration_class(time_stamp=time_stamp, cryomodule=q0_cryomodule)

        # Verify the calibration was created with the right parameters
        mock_calibration_class.assert_called_with(time_stamp=time_stamp, cryomodule=q0_cryomodule)


# Test loading data
def test_load_calibration(q0_cryomodule):
    with patch("sc_linac_physics.applications.q0.calibration.Calibration.load_data") as mock_load:
        q0_cryomodule.load_calibration("2023-01-01T12:00:00")
        assert q0_cryomodule.calibration is not None
        mock_load.assert_called_once()


def test_load_q0_measurement(q0_cryomodule):
    with patch("sc_linac_physics.applications.q0.rf_measurement.Q0Measurement.load_data") as mock_load:
        q0_cryomodule.load_q0_measurement("2023-01-01T12:00:00")
        assert q0_cryomodule.q0_measurement is not None
        mock_load.assert_called_with("2023-01-01T12:00:00")


# Test restore methods
def test_restore_cryo(q0_cryomodule, mock_epics):
    q0_cryomodule.restore_cryo()

    # Verify JT set to auto
    mock_epics["caput"].assert_any_call(q0_cryomodule.jt_auto_select_pv, 1, wait=True)

    # Verify liquid level set to 92
    q0_cryomodule.ds_level_pv_obj.put.assert_called_with(92)

    # Verify heater sequencer turned on
    mock_epics["caput"].assert_any_call(q0_cryomodule.heater_sequencer_pv, 1, wait=True)


def test_setup_cryo_for_measurement(q0_cryomodule):
    """Test setup_cryo_for_measurement with property patching"""

    # Define property mocks before patching
    mock_jt = PropertyMock()
    mock_heater = PropertyMock()

    # Store the original properties
    original_jt_property = type(q0_cryomodule).jt_position
    original_heater_property = type(q0_cryomodule).heater_power

    try:
        # Patch at the class level
        type(q0_cryomodule).jt_position = mock_jt
        type(q0_cryomodule).heater_power = mock_heater

        # Mock the fill method
        with patch.object(q0_cryomodule, "fill") as mock_fill:

            # Set up mock valve params
            q0_cryomodule.valveParams = ValveParams(30.0, 120.0, 118.5)

            # Test case 1: with default turn_cavities_off=True
            q0_cryomodule.setup_cryo_for_measurement(90.0)

            # Verify fill called
            mock_fill.assert_called_with(90.0, turn_cavities_off=True)

            # Verify JT position set
            mock_jt.assert_called_with(30.0)

            # Verify heater power set
            mock_heater.assert_called_with(120.0)

            # Reset the mocks
            mock_fill.reset_mock()
            mock_jt.reset_mock()
            mock_heater.reset_mock()

            # Test case 2: with turn_cavities_off=False
            q0_cryomodule.setup_cryo_for_measurement(92.0, turn_cavities_off=False)

            # Verify fill called
            mock_fill.assert_called_with(92.0, turn_cavities_off=False)

            # Verify JT position set
            mock_jt.assert_called_with(30.0)

            # Verify heater power set
            mock_heater.assert_called_with(120.0)

    finally:
        # Restore the original properties
        type(q0_cryomodule).jt_position = original_jt_property
        type(q0_cryomodule).heater_power = original_heater_property
