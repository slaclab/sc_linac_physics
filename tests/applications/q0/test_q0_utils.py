# test_q0_utils.py

import json
import os
import shutil
import tempfile
import unittest
import warnings
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import numpy as np
from matplotlib.axes import Axes
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg

# Import the modules to test
from sc_linac_physics.applications.q0.q0_utils import (
    DataRun,
    HeaterRun,
    ValveParams,
    DataError,
    Q0AbortError,
    RFError,
    CryoError,
    calc_q0,
    make_json_file,
    update_json_data,
    q0_hash,
    gen_axis,
    redraw_axis,
    round_for_printing,
    draw_and_show,
    DATETIME_FORMATTER,
    MIN_DS_LL,
    MAX_DS_LL,
    MIN_US_LL,
    VALVE_POS_TOL,
    HEATER_TOL,
    TARGET_LL_DIFF,
    AMPLITUDE_TOL,
    ARCHIVER_TIME_INTERVAL,
    INITIAL_CAL_HEAT_LOAD,
    NUM_CAL_STEPS,
    CAV_HEATER_RUN_LOAD,
    FULL_MODULE_CALIBRATION_LOAD,
    CAL_HEATER_DELTA,
    JT_SEARCH_TIME_RANGE,
    JT_SEARCH_OVERLAP_DELTA,
    DELTA_NEEDED_FOR_FLATNESS,
    JT_MANUAL_MODE_VALUE,
    JT_AUTO_MODE_VALUE,
    HEATER_MANUAL_VALUE,
    HEATER_SEQUENCER_VALUE,
    CRYO_ACCESS_VALUE,
    MINIMUM_HEATLOAD,
    JSON_START_KEY,
    JSON_END_KEY,
    JSON_LL_KEY,
    JSON_HEATER_RUN_KEY,
    JSON_RF_RUN_KEY,
    JSON_HEATER_READBACK_KEY,
    JSON_DLL_KEY,
    JSON_CAV_AMPS_KEY,
    JSON_AVG_PRESS_KEY,
    ERROR_MESSAGE,
    RUN_STATUS_MSSG,
)


class TestDataRun(unittest.TestCase):
    def setUp(self):
        self.data_run = DataRun(reference_heat=5.0)

    def test_initialization(self):
        """Test DataRun initialization"""
        self.assertEqual(self.data_run.ll_data, {})
        self.assertEqual(self.data_run.heater_readback_buffer, [])
        self.assertIsNone(self.data_run._dll_dt)
        self.assertIsNone(self.data_run._start_time)
        self.assertIsNone(self.data_run._end_time)
        self.assertIsNone(self.data_run._average_heat)
        self.assertEqual(self.data_run.reference_heat, 5.0)

    def test_average_heat_calculation(self):
        """Test average heat calculation"""
        self.data_run.heater_readback_buffer = [10.0, 12.0, 14.0, 16.0]
        expected_avg = np.mean([10.0, 12.0, 14.0, 16.0]) - 5.0
        self.assertEqual(self.data_run.average_heat, expected_avg)

    def test_average_heat_setter(self):
        """Test average heat setter"""
        self.data_run.average_heat = 15.5
        self.assertEqual(self.data_run.average_heat, 15.5)

    def test_start_time_property(self):
        """Test start time property getter and setter"""
        test_time = datetime(2023, 12, 25, 10, 30, 45)
        self.data_run.start_time = test_time
        expected_str = test_time.strftime(DATETIME_FORMATTER)
        self.assertEqual(self.data_run.start_time, expected_str)

    def test_start_time_none(self):
        """Test start time when not set"""
        self.assertIsNone(self.data_run.start_time)

    def test_end_time_property(self):
        """Test end time property getter and setter"""
        test_time = datetime(2023, 12, 25, 12, 30, 45)
        self.data_run.end_time = test_time
        expected_str = test_time.strftime(DATETIME_FORMATTER)
        self.assertEqual(self.data_run.end_time, expected_str)

    def test_end_time_none(self):
        """Test end time when not set"""
        self.assertIsNone(self.data_run.end_time)

    @patch("sc_linac_physics.applications.q0.q0_utils.USE_SIEGELSLOPES", True)
    @patch("sc_linac_physics.applications.q0.q0_utils.siegelslopes")
    def test_dll_dt_siegelslopes(self, mock_siegelslopes):
        """Test dll_dt calculation using siegelslopes"""
        mock_siegelslopes.return_value = (0.5, 10.0)
        self.data_run.ll_data = {1.0: 91.0, 2.0: 90.5, 3.0: 90.0}

        result = self.data_run.dll_dt
        self.assertEqual(result, 0.5)
        mock_siegelslopes.assert_called_once()

    @patch("sc_linac_physics.applications.q0.q0_utils.USE_SIEGELSLOPES", False)
    @patch("sc_linac_physics.applications.q0.q0_utils.linregress")
    def test_dll_dt_linregress(self, mock_linregress):
        """Test dll_dt calculation using linregress"""
        mock_linregress.return_value = (-0.3, 91.5, -0.95, 0.01, 0.05)
        self.data_run.ll_data = {1.0: 91.0, 2.0: 90.5, 3.0: 90.0}

        result = self.data_run.dll_dt
        self.assertEqual(result, -0.3)
        mock_linregress.assert_called_once()

    def test_dll_dt_setter(self):
        """Test dll_dt setter"""
        self.data_run.dll_dt = -0.25
        self.assertEqual(self.data_run.dll_dt, -0.25)


class TestHeaterRun(unittest.TestCase):
    def test_initialization(self):
        """Test HeaterRun initialization"""
        heater_run = HeaterRun(heat_load=50.0, reference_heat=8.0)
        self.assertEqual(heater_run.heat_load_des, 50.0)
        self.assertEqual(heater_run.reference_heat, 8.0)
        self.assertEqual(heater_run.ll_data, {})

    def test_inheritance(self):
        """Test that HeaterRun properly inherits from DataRun"""
        heater_run = HeaterRun(heat_load=50.0)

        # Should have all DataRun properties
        self.assertTrue(hasattr(heater_run, "ll_data"))
        self.assertTrue(hasattr(heater_run, "heater_readback_buffer"))
        self.assertTrue(hasattr(heater_run, "start_time"))
        self.assertTrue(hasattr(heater_run, "end_time"))
        self.assertTrue(hasattr(heater_run, "dll_dt"))
        self.assertTrue(hasattr(heater_run, "average_heat"))


class TestValveParams(unittest.TestCase):
    def test_valve_params_dataclass(self):
        """Test ValveParams dataclass"""
        params = ValveParams(
            refValvePos=75.5, refHeatLoadDes=40.0, refHeatLoadAct=38.5
        )
        self.assertEqual(params.refValvePos, 75.5)
        self.assertEqual(params.refHeatLoadDes, 40.0)
        self.assertEqual(params.refHeatLoadAct, 38.5)


class TestCalcQ0(unittest.TestCase):
    @patch("builtins.print")  # Suppress print output during tests
    def test_calc_q0_uncorrected(self, mock_print):
        """Test Q0 calculation without correction"""
        amplitude = 15.0
        rf_heat_load = 25.0
        avg_pressure = 1000.0
        cav_length = 0.7

        result = calc_q0(
            amplitude,
            rf_heat_load,
            avg_pressure,
            cav_length,
            use_correction=False,
        )

        expected = ((amplitude * 1e6) ** 2) / (1012 * rf_heat_load)
        self.assertAlmostEqual(result, expected, places=2)

    @patch("builtins.print")  # Suppress print output during tests
    def test_calc_q0_corrected(self, mock_print):
        """Test Q0 calculation with correction"""
        amplitude = 15.0
        rf_heat_load = 25.0
        avg_pressure = 1000.0
        cav_length = 0.7

        result = calc_q0(
            amplitude,
            rf_heat_load,
            avg_pressure,
            cav_length,
            use_correction=True,
        )

        # Test that correction is applied (result should be different from uncorrected)
        uncorrected = ((amplitude * 1e6) ** 2) / (1012 * rf_heat_load)
        self.assertNotEqual(result, uncorrected)
        self.assertIsInstance(result, float)

    @patch("builtins.print")
    def test_calc_q0_custom_r_over_q(self, mock_print):
        """Test Q0 calculation with custom R/Q value"""
        amplitude = 10.0
        rf_heat_load = 20.0
        avg_pressure = 1000.0
        cav_length = 0.7
        custom_r_over_q = 500

        result = calc_q0(
            amplitude,
            rf_heat_load,
            avg_pressure,
            cav_length,
            use_correction=False,
            r_over_q=custom_r_over_q,
        )

        expected = ((amplitude * 1e6) ** 2) / (custom_r_over_q * rf_heat_load)
        self.assertAlmostEqual(result, expected, places=2)

    def test_calc_q0_zero_heat_load(self):
        """Test Q0 calculation with zero heat load (should raise ValueError)"""
        with self.assertRaises(ValueError) as cm:
            calc_q0(15.0, 0.0, 1000.0, 0.7)
        self.assertIn("RF heat load must be positive", str(cm.exception))

    def test_calc_q0_negative_values(self):
        """Test Q0 calculation with negative values"""
        # The function validates that amplitude must be positive
        with self.assertRaises(ValueError) as cm:
            calc_q0(-15.0, 25.0, 1000.0, 0.7)
        self.assertIn("Amplitude must be positive", str(cm.exception))

        # Negative heat load should also raise an error
        with self.assertRaises(ValueError) as cm:
            calc_q0(15.0, -25.0, 1000.0, 0.7)
        self.assertIn("RF heat load must be positive", str(cm.exception))

        # Zero amplitude should raise error
        with self.assertRaises(ValueError) as cm:
            calc_q0(0.0, 25.0, 1000.0, 0.7)
        self.assertIn("Amplitude must be positive", str(cm.exception))

    @patch("builtins.print")
    def test_calc_q0_extreme_values(self, mock_print):
        """Test Q0 calculation with extreme values"""
        # Very small positive amplitude
        result = calc_q0(0.001, 1.0, 1000.0, 0.7)
        self.assertGreater(result, 0)

        # Very large amplitude
        result = calc_q0(100.0, 1.0, 1000.0, 0.7)
        self.assertGreater(result, 0)

    @patch("builtins.print")
    def test_calc_q0_input_validation(self, mock_print):
        """Test comprehensive input validation"""
        valid_args = (15.0, 25.0, 1000.0, 0.7)

        # Test valid case works
        result = calc_q0(*valid_args)
        self.assertIsInstance(result, float)
        self.assertGreater(result, 0)

        # Test edge case: very small positive values
        result = calc_q0(0.001, 0.001, 1000.0, 0.7)
        self.assertGreater(result, 0)


class TestFileOperations(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.temp_dir, "test_data.json")

    def tearDown(self):
        # Clean up temporary directory and all its contents
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_make_json_file_new_file(self):
        """Test creating a new JSON file"""
        make_json_file(self.test_file)

        self.assertTrue(os.path.exists(self.test_file))
        with open(self.test_file, "r") as f:
            data = json.load(f)
            self.assertEqual(data, {})

    def test_make_json_file_existing_file(self):
        """Test that existing file is not overwritten"""
        # Create file with initial data
        initial_data = {"test": "data"}
        with open(self.test_file, "w") as f:
            json.dump(initial_data, f)

        # Call make_json_file on existing file
        make_json_file(self.test_file)

        # Verify data is preserved
        with open(self.test_file, "r") as f:
            data = json.load(f)
            self.assertEqual(data, initial_data)

    def test_make_json_file_nested_directory(self):
        """Test creating JSON file in nested directory"""
        nested_path = os.path.join(
            self.temp_dir, "subdir", "nested", "test.json"
        )
        make_json_file(nested_path)

        self.assertTrue(os.path.exists(nested_path))
        with open(nested_path, "r") as f:
            data = json.load(f)
            self.assertEqual(data, {})

    def test_update_json_data_new_file(self):
        """Test updating JSON data in new file"""
        timestamp = "2023-12-25 10:30:00"
        test_data = {"temperature": 2.1, "pressure": 1000}

        update_json_data(self.test_file, timestamp, test_data)

        with open(self.test_file, "r") as f:
            data = json.load(f)
            self.assertEqual(data[timestamp], test_data)

    def test_update_json_data_existing_file(self):
        """Test updating JSON data in existing file"""
        # Create initial data
        initial_data = {"2023-12-24 10:00:00": {"temp": 2.0}}
        with open(self.test_file, "w") as f:
            json.dump(initial_data, f)

        # Update with new data
        timestamp = "2023-12-25 10:30:00"
        new_data = {"temperature": 2.1, "pressure": 1000}
        update_json_data(self.test_file, timestamp, new_data)

        # Verify both old and new data exist
        with open(self.test_file, "r") as f:
            data = json.load(f)
            self.assertEqual(len(data), 2)
            self.assertEqual(data[timestamp], new_data)
            self.assertEqual(data["2023-12-24 10:00:00"], {"temp": 2.0})

    def test_update_json_data_overwrite_existing_timestamp(self):
        """Test that updating with the same timestamp overwrites the data"""
        # Create initial data
        timestamp = "2023-12-25 10:30:00"
        initial_data = {timestamp: {"temp": 1.5}}
        with open(self.test_file, "w") as f:
            json.dump(initial_data, f)

        # Update with new data using same timestamp
        new_data = {"temperature": 2.1, "pressure": 1000}
        update_json_data(self.test_file, timestamp, new_data)

        # Verify data was overwritten
        with open(self.test_file, "r") as f:
            data = json.load(f)
            self.assertEqual(len(data), 1)
            self.assertEqual(data[timestamp], new_data)
            # Old data should be gone
            self.assertNotEqual(data[timestamp], {"temp": 1.5})


class TestQ0Hash(unittest.TestCase):
    def test_q0_hash_single_item(self):
        """Test hash function with single item"""
        test_value = "test_string"
        result = q0_hash([test_value])
        expected = hash(test_value)
        self.assertEqual(result, expected)

    def test_q0_hash_multiple_items(self):
        """Test hash function with multiple items"""
        test_values = ["string1", 42, 3.14]
        result = q0_hash(test_values)
        self.assertIsInstance(result, int)

        # Test that it's actually doing XOR operations
        expected = hash("string1") ^ hash(42) ^ hash(3.14)
        self.assertEqual(result, expected)

    def test_q0_hash_empty_list(self):
        """Test hash function with empty list"""
        # The corrected function returns 0 for empty lists
        result = q0_hash([])
        self.assertEqual(result, 0)

    def test_q0_hash_consistency(self):
        """Test that hash function returns consistent results"""
        test_values = [1, 2, 3]
        result1 = q0_hash(test_values.copy())
        result2 = q0_hash(test_values.copy())
        self.assertEqual(result1, result2)

    def test_q0_hash_with_none_values(self):
        """Test q0_hash with None values"""
        result = q0_hash([None, "test", None])
        expected = hash(None) ^ hash("test") ^ hash(None)
        self.assertEqual(result, expected)

    def test_q0_hash_two_items(self):
        """Test hash function with exactly two items"""
        test_values = ["item1", "item2"]
        result = q0_hash(test_values)
        expected = hash("item1") ^ hash("item2")
        self.assertEqual(result, expected)

    def test_q0_hash_order_independence(self):
        """Test that XOR hash is order-independent"""
        # XOR is commutative, so order shouldn't matter for pairs
        result1 = q0_hash(["a", "b"])
        result2 = q0_hash(["b", "a"])
        self.assertEqual(result1, result2)


class TestPlottingUtilities(unittest.TestCase):
    @patch("matplotlib.pyplot.figure")
    def test_gen_axis(self, mock_figure):
        """Test axis generation"""
        mock_fig = Mock()
        mock_ax = Mock(spec=Axes)
        mock_fig.add_subplot.return_value = mock_ax
        mock_figure.return_value = mock_fig

        title = "Test Title"
        xlabel = "X Label"
        ylabel = "Y Label"

        result = gen_axis(title, xlabel, ylabel)

        mock_figure.assert_called_once()
        mock_fig.add_subplot.assert_called_once_with(111)
        mock_ax.set_title.assert_called_once_with(title)
        mock_ax.set_xlabel.assert_called_once_with(xlabel)
        mock_ax.set_ylabel.assert_called_once_with(ylabel)
        self.assertEqual(result, mock_ax)

    def test_redraw_axis(self):
        """Test axis redrawing"""
        mock_canvas = Mock(spec=FigureCanvasQTAgg)
        mock_axes = Mock()
        mock_canvas.axes = mock_axes

        title = "New Title"
        xlabel = "New X Label"
        ylabel = "New Y Label"

        redraw_axis(mock_canvas, title, xlabel, ylabel)

        mock_axes.cla.assert_called_once()
        mock_canvas.draw_idle.assert_called_once()
        mock_axes.set_title.assert_called_once_with(title)
        mock_axes.set_xlabel.assert_called_once_with(xlabel)
        mock_axes.set_ylabel.assert_called_once_with(ylabel)

    @patch("matplotlib.pyplot.draw")
    @patch("matplotlib.pyplot.show")
    def test_draw_and_show(self, mock_show, mock_draw):
        """Test draw_and_show function"""
        draw_and_show()

        mock_draw.assert_called_once()
        mock_show.assert_called_once()


class TestUtilityFunctions(unittest.TestCase):
    def test_round_for_printing(self):
        """Test rounding function"""
        test_cases = [
            (3.14159265, 3.142),
            (2.0, 2.0),
            (1.9999, 2.0),
            (0.0001234, 0.0),
        ]

        for input_val, expected in test_cases:
            with self.subTest(input_val=input_val):
                result = round_for_printing(input_val)
                self.assertEqual(result, expected)

    def test_round_for_printing_array(self):
        """Test rounding function with numpy array"""
        input_array = np.array([1.23456, 2.34567, 3.45678])
        expected = np.array([1.235, 2.346, 3.457])
        result = round_for_printing(input_array)
        np.testing.assert_array_equal(result, expected)

    def test_round_for_printing_negative_numbers(self):
        """Test rounding function with negative numbers"""
        self.assertEqual(round_for_printing(-3.14159), -3.142)
        self.assertEqual(round_for_printing(-0.0001), -0.0)


class TestExceptions(unittest.TestCase):
    def test_data_error(self):
        """Test DataError exception"""
        with self.assertRaises(DataError):
            raise DataError("Test data error")

    def test_q0_abort_error(self):
        """Test Q0AbortError exception"""
        with self.assertRaises(Q0AbortError):
            raise Q0AbortError("Test Q0 abort error")

    def test_rf_error(self):
        """Test RFError exception"""
        with self.assertRaises(RFError):
            raise RFError("Test RF error")

        # Test docstring
        self.assertIn("RF Execution", RFError.__doc__)

    def test_cryo_error(self):
        """Test CryoError exception"""
        with self.assertRaises(CryoError):
            raise CryoError("Test cryo error")

        # Test docstring
        self.assertIn("Cryo Execution", CryoError.__doc__)


class TestConstants(unittest.TestCase):
    def test_liquid_level_constants(self):
        """Test liquid level constants are valid"""
        self.assertIsInstance(MIN_DS_LL, (int, float))
        self.assertIsInstance(MAX_DS_LL, (int, float))
        self.assertIsInstance(MIN_US_LL, (int, float))
        self.assertTrue(MIN_DS_LL < MAX_DS_LL)
        self.assertGreater(MIN_DS_LL, 0)
        self.assertLess(MAX_DS_LL, 100)

        # Test specific values
        self.assertEqual(MIN_DS_LL, 90)
        self.assertEqual(MAX_DS_LL, 93)
        self.assertEqual(MIN_US_LL, 66)

    def test_tolerance_constants(self):
        """Test tolerance constants are positive"""
        self.assertGreater(VALVE_POS_TOL, 0)
        self.assertGreater(HEATER_TOL, 0)
        self.assertGreater(AMPLITUDE_TOL, 0)

        # Test specific values
        self.assertEqual(VALVE_POS_TOL, 2)
        self.assertEqual(HEATER_TOL, 1.2)
        self.assertEqual(AMPLITUDE_TOL, 0.3)

    def test_time_constants(self):
        """Test time-related constants"""
        self.assertIsInstance(JT_SEARCH_TIME_RANGE, timedelta)
        self.assertIsInstance(JT_SEARCH_OVERLAP_DELTA, timedelta)
        self.assertIsInstance(DELTA_NEEDED_FOR_FLATNESS, timedelta)
        self.assertGreater(JT_SEARCH_TIME_RANGE.total_seconds(), 0)

        # Test specific values
        self.assertEqual(JT_SEARCH_TIME_RANGE, timedelta(hours=24))
        self.assertEqual(JT_SEARCH_OVERLAP_DELTA, timedelta(minutes=30))
        self.assertEqual(DELTA_NEEDED_FOR_FLATNESS, timedelta(hours=2))

    def test_heat_load_constants(self):
        """Test heat load constants"""
        self.assertGreater(INITIAL_CAL_HEAT_LOAD, 0)
        self.assertGreater(CAV_HEATER_RUN_LOAD, 0)
        self.assertGreater(FULL_MODULE_CALIBRATION_LOAD, 0)
        self.assertGreater(MINIMUM_HEATLOAD, 0)
        self.assertGreater(CAL_HEATER_DELTA, 0)

        # Test specific values
        self.assertEqual(INITIAL_CAL_HEAT_LOAD, 8)
        self.assertEqual(CAV_HEATER_RUN_LOAD, 24)
        self.assertEqual(FULL_MODULE_CALIBRATION_LOAD, 80)
        self.assertEqual(MINIMUM_HEATLOAD, 48)
        self.assertEqual(CAL_HEATER_DELTA, 8)

    def test_json_keys(self):
        """Test JSON key constants"""
        json_keys = [
            JSON_START_KEY,
            JSON_END_KEY,
            JSON_LL_KEY,
            JSON_HEATER_RUN_KEY,
            JSON_RF_RUN_KEY,
            JSON_HEATER_READBACK_KEY,
            JSON_DLL_KEY,
            JSON_CAV_AMPS_KEY,
            JSON_AVG_PRESS_KEY,
        ]

        for key in json_keys:
            self.assertIsInstance(key, str)
            self.assertGreater(len(key), 0)

        # Test that all keys are unique
        self.assertEqual(len(json_keys), len(set(json_keys)))

        # Test specific values
        self.assertEqual(JSON_START_KEY, "Start Time")
        self.assertEqual(JSON_END_KEY, "End Time")
        self.assertEqual(JSON_LL_KEY, "Liquid Level Data")

    def test_mode_value_constants(self):
        """Test mode value constants"""
        self.assertIsInstance(JT_MANUAL_MODE_VALUE, int)
        self.assertIsInstance(JT_AUTO_MODE_VALUE, int)
        self.assertIsInstance(HEATER_MANUAL_VALUE, int)
        self.assertIsInstance(HEATER_SEQUENCER_VALUE, int)
        self.assertIsInstance(CRYO_ACCESS_VALUE, int)

        # Test specific values
        self.assertEqual(JT_MANUAL_MODE_VALUE, 0)
        self.assertEqual(JT_AUTO_MODE_VALUE, 1)
        self.assertEqual(HEATER_MANUAL_VALUE, 0)
        self.assertEqual(HEATER_SEQUENCER_VALUE, 2)
        self.assertEqual(CRYO_ACCESS_VALUE, 1)

    def test_datetime_formatter(self):
        """Test datetime formatter constant"""
        self.assertIsInstance(DATETIME_FORMATTER, str)
        self.assertEqual(DATETIME_FORMATTER, "%m/%d/%y %H:%M:%S")

        # Test that it's a valid datetime format string
        test_time = datetime(2023, 12, 25, 14, 30, 45)
        formatted = test_time.strftime(DATETIME_FORMATTER)
        parsed = datetime.strptime(formatted, DATETIME_FORMATTER)
        self.assertEqual(test_time, parsed)

    def test_other_constants(self):
        """Test other constants"""
        self.assertIsInstance(ERROR_MESSAGE, str)
        self.assertIsInstance(RUN_STATUS_MSSG, str)
        self.assertIsInstance(TARGET_LL_DIFF, (int, float))
        self.assertIsInstance(ARCHIVER_TIME_INTERVAL, (int, float))
        self.assertIsInstance(NUM_CAL_STEPS, int)

        # Test specific values
        self.assertEqual(ERROR_MESSAGE, "Please provide valid input")
        self.assertEqual(TARGET_LL_DIFF, 4)
        self.assertEqual(ARCHIVER_TIME_INTERVAL, 1)
        self.assertEqual(NUM_CAL_STEPS, 7)


class TestIntegration(unittest.TestCase):
    """Integration tests that test multiple components working together"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        # Clean up temporary directory and all its contents
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    @patch("builtins.print")
    def test_full_data_run_workflow(self, mock_print):
        """Test a complete data run workflow"""
        # Create a data run
        data_run = DataRun(reference_heat=10.0)

        # Set up some test data
        start_time = datetime(2023, 12, 25, 10, 0, 0)
        end_time = datetime(2023, 12, 25, 12, 0, 0)
        data_run.start_time = start_time
        data_run.end_time = end_time

        # Add some liquid level data points
        data_run.ll_data = {1.0: 92.0, 2.0: 91.5, 3.0: 91.0, 4.0: 90.5}

        # Add heater readback data
        data_run.heater_readback_buffer = [45.0, 46.0, 44.0, 45.5]

        # Test that all properties work
        self.assertEqual(
            data_run.start_time, start_time.strftime(DATETIME_FORMATTER)
        )
        self.assertEqual(
            data_run.end_time, end_time.strftime(DATETIME_FORMATTER)
        )
        self.assertAlmostEqual(
            data_run.average_heat, np.mean([45.0, 46.0, 44.0, 45.5]) - 10.0
        )
        self.assertIsInstance(data_run.dll_dt, float)

    def test_heater_run_with_json_export(self):
        """Test heater run with JSON data export"""
        # Create heater run
        heater_run = HeaterRun(
            heat_load=50.0, reference_heat=8.0
        )  # Set up data
        heater_run.ll_data = {1.0: 92.0, 2.0: 91.0, 3.0: 90.0}
        heater_run.heater_readback_buffer = [58.0, 59.0, 57.0]

        # Create test data for JSON export
        timestamp = "2023-12-25 10:30:00"
        run_data = {
            JSON_HEATER_RUN_KEY: {
                "heat_load_des": heater_run.heat_load_des,
                "average_heat": heater_run.average_heat,
                "dll_dt": heater_run.dll_dt,
                "ll_data_points": len(heater_run.ll_data),
            }
        }

        # Export to JSON
        json_file = os.path.join(self.temp_dir, "heater_run.json")
        update_json_data(json_file, timestamp, run_data)

        # Verify JSON export
        with open(json_file, "r") as f:
            data = json.load(f)
            self.assertEqual(
                data[timestamp][JSON_HEATER_RUN_KEY]["heat_load_des"], 50.0
            )
            self.assertIn("average_heat", data[timestamp][JSON_HEATER_RUN_KEY])
            self.assertIn("dll_dt", data[timestamp][JSON_HEATER_RUN_KEY])

    @patch("builtins.print")
    def test_q0_calculation_with_real_data(self, mock_print):
        """Test Q0 calculation with realistic experimental data"""
        # Realistic values for a superconducting cavity
        amplitude = 16.0  # MV/m
        rf_heat_load = 12.5  # W
        avg_pressure = 31.0  # mbar
        cav_length = 0.7  # m

        # Calculate both corrected and uncorrected Q0
        q0_uncorrected = calc_q0(
            amplitude,
            rf_heat_load,
            avg_pressure,
            cav_length,
            use_correction=False,
        )
        q0_corrected = calc_q0(
            amplitude,
            rf_heat_load,
            avg_pressure,
            cav_length,
            use_correction=True,
        )

        # Verify results are in reasonable range for superconducting cavities
        self.assertGreater(
            q0_uncorrected, 1e9
        )  # Should be > 1E9 for good cavities
        self.assertLess(q0_uncorrected, 1e12)  # But not unrealistically high
        self.assertGreater(q0_corrected, 1e9)
        self.assertLess(q0_corrected, 1e12)

        # Corrected and uncorrected should be different
        self.assertNotEqual(q0_uncorrected, q0_corrected)


class TestErrorHandling(unittest.TestCase):
    """Test error handling and edge cases"""

    def test_data_run_empty_heater_buffer(self):
        """Test DataRun with empty heater buffer"""
        data_run = DataRun()

        # With empty heater buffer, np.mean([]) returns nan
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # Suppress the warning for testing
            result = data_run.average_heat
            # Result should be nan minus reference_heat (0 by default) = nan
            self.assertTrue(np.isnan(result))

    def test_data_run_no_ll_data(self):
        """Test DataRun with no liquid level data"""
        data_run = DataRun()
        # ll_data is empty dict

        # With empty data, different implementations might behave differently
        try:
            result = data_run.dll_dt
            # If no exception is raised, result might be nan, inf, or some other value
            # This is acceptable as long as it's a number
            self.assertIsInstance(result, (int, float, np.number))
        except (
            ValueError,
            KeyError,
            IndexError,
            TypeError,
            np.linalg.LinAlgError,
        ):
            # These exceptions are also acceptable for empty data
            pass

    def test_data_run_single_ll_point(self):
        """Test DataRun with single liquid level data point"""
        data_run = DataRun()
        data_run.ll_data = {1.0: 91.0}

        # With single point, behavior depends on the regression implementation
        try:
            result = data_run.dll_dt
            # If it works, result should be a number
            self.assertIsInstance(result, (int, float, np.number))
        except (ValueError, np.linalg.LinAlgError, RuntimeError, TypeError):
            # These exceptions are acceptable for insufficient data
            pass

    def test_data_run_two_different_ll_points(self):
        """Test DataRun with two different liquid level points"""
        data_run = DataRun()
        data_run.ll_data = {1.0: 91.0, 2.0: 90.0}

        # This should work fine - two points define a line
        result = data_run.dll_dt
        self.assertIsInstance(result, (int, float, np.number))
        # Should be negative slope (liquid level decreasing)
        self.assertLess(result, 0)
        self.assertAlmostEqual(result, -1.0, places=5)

    def test_data_run_constant_ll_values(self):
        """Test DataRun with constant liquid level values"""
        data_run = DataRun()
        # Different times but identical values
        data_run.ll_data = {1.0: 91.0, 2.0: 91.0, 3.0: 91.0}

        # This should give zero slope
        result = data_run.dll_dt
        self.assertAlmostEqual(result, 0.0, places=10)

    def test_json_file_permission_error(self):
        """Test handling of file permission errors"""
        # Create a real file that we can test permissions on
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as temp_file:
            temp_file.write('{"existing": "data"}')
            temp_filename = temp_file.name

        try:
            # Make the file read-only to simulate permission error
            os.chmod(temp_filename, 0o444)  # Read-only

            # This should raise a PermissionError when trying to write
            with self.assertRaises(PermissionError):
                update_json_data(temp_filename, "timestamp", {"data": "test"})

        except (OSError, AttributeError):
            # On some systems, chmod might not work as expected
            # or the OS might not respect the permissions
            self.skipTest("Cannot test file permissions on this system")

        finally:
            # Restore write permissions and clean up
            try:
                os.chmod(temp_filename, 0o644)
                os.unlink(temp_filename)
            except (OSError, FileNotFoundError):
                pass

    def test_json_file_permission_error_with_mock(self):
        """Test handling of file permission errors using mock"""
        # Mock just the file opening in update_json_data, after make_json_file succeeds
        with patch("sc_linac_physics.applications.q0.q0_utils.make_json_file"):
            with patch(
                "builtins.open", side_effect=PermissionError("File locked")
            ):
                with self.assertRaises(PermissionError):
                    update_json_data(
                        "some_file.json", "timestamp", {"data": "test"}
                    )

    def test_invalid_json_data(self):
        """Test handling of invalid JSON data"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as temp_file:
            temp_file.write("invalid json content {")
            temp_filename = temp_file.name

        try:
            with self.assertRaises(json.JSONDecodeError):
                update_json_data(temp_filename, "test", {"data": "test"})
        finally:
            os.unlink(temp_filename)

    def test_data_run_caching_behavior(self):
        """Test that DataRun properties are cached correctly"""
        data_run = DataRun(reference_heat=5.0)
        data_run.heater_readback_buffer = [10.0, 12.0]

        # First access should calculate
        first_result = data_run.average_heat
        expected = np.mean([10.0, 12.0]) - 5.0
        self.assertEqual(first_result, expected)

        # Modify buffer but cached value should remain
        data_run.heater_readback_buffer.append(20.0)
        second_result = data_run.average_heat
        self.assertEqual(second_result, first_result)  # Should be cached

        # Reset cache and get new value
        data_run._average_heat = None
        third_result = data_run.average_heat
        new_expected = np.mean([10.0, 12.0, 20.0]) - 5.0
        self.assertEqual(third_result, new_expected)
        self.assertNotEqual(third_result, first_result)

    def test_data_run_dll_dt_caching(self):
        """Test that dll_dt is cached correctly"""
        data_run = DataRun()
        data_run.ll_data = {
            1.0: 95.0,
            2.0: 90.0,
        }  # Simple case with clear slope of -5

        # First access should calculate and cache
        first_result = data_run.dll_dt
        self.assertIsInstance(first_result, (int, float, np.number))
        self.assertIsNotNone(data_run._dll_dt)  # Should be cached now
        self.assertAlmostEqual(first_result, -5.0, places=5)

        # Modify ll_data - this should not affect the cached result
        data_run.ll_data[3.0] = (
            100.0  # Add point that would create positive slope
        )

        # Access again - should return cached value, not recalculate
        second_result = data_run.dll_dt
        self.assertEqual(second_result, first_result)
        self.assertAlmostEqual(
            second_result, -5.0, places=5
        )  # Still the cached value

        # Reset cache manually
        data_run._dll_dt = None

        # Access again - should recalculate with new data
        third_result = data_run.dll_dt
        self.assertIsNotNone(data_run._dll_dt)

        # With points (1,95), (2,90), (3,100), the slope should be different
        self.assertNotEqual(third_result, first_result)
        # The new slope should be positive due to the (3,100) point
        self.assertGreater(third_result, first_result)

    def test_data_run_dll_dt_calculation_methods(self):
        """Test that both siegelslopes and linregress methods work"""
        data_run = DataRun()
        data_run.ll_data = {1.0: 92.0, 2.0: 91.0, 3.0: 90.0, 4.0: 89.0}

        # Test with siegelslopes
        with patch(
            "sc_linac_physics.applications.q0.q0_utils.USE_SIEGELSLOPES", True
        ):
            data_run._dll_dt = None  # Reset cache
            result_siegel = data_run.dll_dt
            self.assertIsInstance(result_siegel, (int, float, np.number))

        # Test with linregress
        with patch(
            "sc_linac_physics.applications.q0.q0_utils.USE_SIEGELSLOPES", False
        ):
            data_run._dll_dt = None  # Reset cache
            result_linregress = data_run.dll_dt
            self.assertIsInstance(result_linregress, (int, float, np.number))

        # Both methods should give similar results for this linear data
        self.assertAlmostEqual(result_siegel, result_linregress, places=3)
        self.assertAlmostEqual(result_siegel, -1.0, places=3)

    @patch("sc_linac_physics.applications.q0.q0_utils.USE_SIEGELSLOPES", True)
    @patch("sc_linac_physics.applications.q0.q0_utils.siegelslopes")
    def test_dll_dt_siegelslopes_error_handling(self, mock_siegelslopes):
        """Test dll_dt error handling with siegelslopes"""
        mock_siegelslopes.side_effect = ValueError("Not enough data points")
        data_run = DataRun()
        data_run.ll_data = {1.0: 91.0}

        with self.assertRaises(ValueError):
            _ = data_run.dll_dt

    @patch("sc_linac_physics.applications.q0.q0_utils.USE_SIEGELSLOPES", False)
    @patch("sc_linac_physics.applications.q0.q0_utils.linregress")
    def test_dll_dt_linregress_error_handling(self, mock_linregress):
        """Test dll_dt error handling with linregress"""
        mock_linregress.side_effect = ValueError("Not enough data points")
        data_run = DataRun()
        data_run.ll_data = {1.0: 91.0}

        with self.assertRaises(ValueError):
            _ = data_run.dll_dt


if __name__ == "__main__":
    # Create test suite
    test_suite = unittest.TestSuite()

    # Add test classes
    test_classes = [
        TestDataRun,
        TestHeaterRun,
        TestValveParams,
        TestCalcQ0,
        TestFileOperations,
        TestQ0Hash,
        TestPlottingUtilities,
        TestUtilityFunctions,
        TestExceptions,
        TestConstants,
        TestIntegration,
        TestErrorHandling,
    ]

    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)

    # Run tests with detailed output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)

    # Print summary
    print(f"\nRan {result.testsRun} tests")
    if result.failures:
        print(f"Failures: {len(result.failures)}")
        for test, traceback in result.failures:
            print(f"FAILED: {test}")
    if result.errors:
        print(f"Errors: {len(result.errors)}")
        for test, traceback in result.errors:
            print(f"ERROR: {test}")

    if result.wasSuccessful():
        print("All tests passed!")
    else:
        print("Some tests failed.")
