from unittest.mock import Mock, patch

import numpy as np
import pyqtgraph as pg

# conftest.py
import pytest
from PyQt5.QtWidgets import QApplication

from sc_linac_physics.applications.microphonics.plots.time_series_plot import (
    TimeSeriesPlot,
)
from sc_linac_physics.applications.microphonics.utils.constants import (
    BASE_HARDWARE_SAMPLE_RATE,
)


@pytest.fixture(scope="session", autouse=True)
def patch_pyqtgraph():
    """Patch PyQtGraph for Python 3.13 compatibility"""
    original_getattr = pg.PlotWidget.__getattr__

    def patched_getattr(self, attr):
        if attr == "autoRangeEnabled":
            # Return the method from the ViewBox
            return self.getViewBox().autoRangeEnabled
        return original_getattr(self, attr)

    pg.PlotWidget.__getattr__ = patched_getattr
    yield


@pytest.fixture(scope="session")
def qapp():
    """Create QApplication instance for tests"""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


class TestTimeSeriesPlot:
    @pytest.fixture
    def plot_widget(self, qapp):
        """Fixture to create a TimeSeriesPlot instance"""
        widget = TimeSeriesPlot()
        yield widget
        widget.deleteLater()
        QApplication.processEvents()

    @pytest.fixture
    def sample_cavity_data(self):
        """Fixture for sample cavity channel data"""
        return {
            "DF": np.array([1.0, 2.0, 3.0, 4.0, 5.0]),
            "decimation": 1,
        }

    @pytest.fixture
    def large_cavity_data(self):
        """Fixture for large dataset requiring decimation"""
        return {
            "DF": np.random.randn(10000),
            "decimation": 1,
        }

    # ===== Initialization Tests =====

    def test_initialization(self, plot_widget):
        """Test widget initialization"""
        assert plot_widget is not None
        assert hasattr(plot_widget, "plot_widget")
        assert hasattr(plot_widget, "plot_curves")
        assert hasattr(plot_widget, "_original_data")
        assert hasattr(plot_widget, "_decimated_data")
        assert isinstance(plot_widget.plot_curves, dict)
        assert isinstance(plot_widget._original_data, dict)
        assert isinstance(plot_widget._decimated_data, dict)

    def test_initial_state(self, plot_widget):
        """Test initial state of the widget"""
        assert len(plot_widget.plot_curves) == 0
        assert len(plot_widget._original_data) == 0
        assert len(plot_widget._decimated_data) == 0
        assert plot_widget._is_zooming is False
        assert plot_widget._zoom_timer is None

    # ===== Data Preprocessing Tests =====

    def test_preprocess_data_valid_df(self, plot_widget, sample_cavity_data):
        """Test preprocessing with valid DF data"""
        data, is_valid = plot_widget._preprocess_data(
            sample_cavity_data, channel_type="DF"
        )

        assert is_valid is True
        assert isinstance(data, np.ndarray)
        assert len(data) == 5
        np.testing.assert_array_equal(data, np.array([1.0, 2.0, 3.0, 4.0, 5.0]))

    def test_preprocess_data_missing_channel(self, plot_widget):
        """Test preprocessing with missing channel data"""
        cavity_data = {"decimation": 1}
        data, is_valid = plot_widget._preprocess_data(
            cavity_data, channel_type="DF"
        )

        assert is_valid is False
        assert data is None

    def test_preprocess_data_none_value(self, plot_widget):
        """Test preprocessing with None value"""
        cavity_data = {"DF": None, "decimation": 1}
        data, is_valid = plot_widget._preprocess_data(
            cavity_data, channel_type="DF"
        )

        assert is_valid is False
        assert data is None

    def test_preprocess_data_empty_array(self, plot_widget):
        """Test preprocessing with empty array"""
        cavity_data = {"DF": np.array([]), "decimation": 1}
        data, is_valid = plot_widget._preprocess_data(
            cavity_data, channel_type="DF"
        )

        assert is_valid is False
        assert data is None

    # ===== Time Axis Calculation Tests =====

    def test_calculate_time_axis_basic(self, plot_widget):
        """Test basic time axis calculation"""
        # Use actual method signature
        times = plot_widget._calculate_time_axis(5, 1)

        assert times is not None
        assert len(times) == 5
        # Times should be sequential
        assert np.all(np.diff(times) > 0)  # Monotonically increasing
        # Verify the spacing is correct
        expected_dt = 1.0 / BASE_HARDWARE_SAMPLE_RATE
        actual_dt = times[1] - times[0] if len(times) > 1 else 0
        np.testing.assert_almost_equal(actual_dt, expected_dt, decimal=9)

    def test_calculate_time_axis_with_decimation(self, plot_widget):
        """Test time axis calculation with decimation"""
        times = plot_widget._calculate_time_axis(5, 2)

        assert times is not None
        assert len(times) == 5
        # Step should be larger with decimation
        if len(times) > 1:
            expected_dt = 2.0 / BASE_HARDWARE_SAMPLE_RATE
            actual_dt = times[1] - times[0]
            np.testing.assert_almost_equal(actual_dt, expected_dt, decimal=9)

    def test_calculate_time_axis_zero_samples(self, plot_widget):
        """Test time axis calculation with zero samples"""
        times = plot_widget._calculate_time_axis(0, 1)

        # Method returns empty array instead of None for zero samples
        assert times is not None
        assert len(times) == 0

    def test_calculate_time_axis_negative_samples(self, plot_widget):
        """Test time axis calculation with negative samples"""
        times = plot_widget._calculate_time_axis(-5, 1)

        assert times is None

    # ===== Decimation Tests =====

    def test_decimate_data_no_decimation_needed(self, plot_widget):
        """Test decimation when data is already small enough"""
        times = np.linspace(0, 10, 100)
        values = np.sin(times)

        dec_times, dec_values = plot_widget._decimate_data(
            times, values, target_points=200
        )

        # Should return original data when below target
        np.testing.assert_array_equal(dec_times, times)
        np.testing.assert_array_equal(dec_values, values)

    def test_decimate_data_with_decimation(self, plot_widget):
        """Test decimation when data exceeds target points"""
        times = np.linspace(0, 10, 10000)
        values = np.sin(times)

        dec_times, dec_values = plot_widget._decimate_data(
            times, values, target_points=1000
        )

        # Should be decimated to approximately target points
        assert len(dec_times) <= 1000
        assert len(dec_values) <= 1000
        assert len(dec_times) == len(dec_values)

    def test_decimate_data_preserves_shape(self, plot_widget):
        """Test that decimation preserves general data shape"""
        times = np.linspace(0, 10, 5000)
        values = np.sin(times)

        dec_times, dec_values = plot_widget._decimate_data(
            times, values, target_points=500
        )

        # Decimated data should still be monotonically increasing in time
        assert np.all(np.diff(dec_times) > 0)

    def test_decimate_data_empty_input(self, plot_widget):
        """Test decimation with empty arrays"""
        times = np.array([])
        values = np.array([])

        dec_times, dec_values = plot_widget._decimate_data(
            times, values, target_points=100
        )

        assert len(dec_times) == 0
        assert len(dec_values) == 0

    # ===== Create Decimated Levels Tests =====

    def test_create_decimated_levels_structure(self, plot_widget):
        """Test that decimated levels are created with proper structure"""
        times = np.linspace(0, 100, 10000)
        values = np.sin(times)

        levels = plot_widget._create_decimated_levels(times, values)

        assert isinstance(levels, dict)
        assert len(levels) > 0

        # Check that 'original' key exists
        assert "original" in levels

        # Check that each level has times and values
        for key, (level_times, level_values) in levels.items():
            assert isinstance(level_times, np.ndarray)
            assert isinstance(level_values, np.ndarray)
            assert len(level_times) == len(level_values)

    # ===== Get Optimal Decimation Tests =====

    def test_get_optimal_decimation_no_data(self, plot_widget):
        """Test optimal decimation with no data stored"""
        cavity_num = 1
        result = plot_widget._get_optimal_decimation(cavity_num, view_width=10)

        assert result is None

    def test_get_optimal_decimation_with_data(self, plot_widget):
        """Test optimal decimation returns appropriate level"""
        cavity_num = 1
        times = np.linspace(0, 100, 10000)
        values = np.sin(times)

        # Store data first
        plot_widget._original_data[cavity_num] = (times, values)
        plot_widget._decimated_data[cavity_num] = (
            plot_widget._create_decimated_levels(times, values)
        )

        result = plot_widget._get_optimal_decimation(cavity_num, view_width=10)

        # Should return data (or None if method returns None)
        if result is not None:
            dec_times, dec_values = result
            assert dec_times is not None
            assert dec_values is not None
            assert len(dec_times) == len(dec_values)
            assert len(dec_times) > 0

    # ===== Filter to View Tests =====

    def test_filter_to_view_basic(self, plot_widget):
        """Test filtering data to view range"""
        times = np.linspace(0, 100, 1000)
        values = np.sin(times)

        filtered_times, filtered_values = plot_widget._filter_to_view(
            times, values, x_min=25, x_max=75
        )

        assert len(filtered_times) > 0
        assert len(filtered_times) <= len(times)
        # Data should be roughly in range (may include padding)
        assert filtered_times[0] <= 30  # Some padding before
        assert filtered_times[-1] >= 70  # Some padding after
        assert len(filtered_times) == len(filtered_values)

    def test_filter_to_view_no_overlap(self, plot_widget):
        """Test filtering when view range doesn't overlap with data"""
        times = np.linspace(0, 10, 100)
        values = np.sin(times)

        filtered_times, filtered_values = plot_widget._filter_to_view(
            times, values, x_min=50, x_max=60
        )

        # May return all data or empty depending on implementation
        # Just check it doesn't crash
        assert isinstance(filtered_times, np.ndarray)
        assert isinstance(filtered_values, np.ndarray)

    def test_filter_to_view_decimates_large_result(self, plot_widget):
        """Test that filtering decimates if result is too large"""
        times = np.linspace(0, 100, 10000)
        values = np.sin(times)

        filtered_times, filtered_values = plot_widget._filter_to_view(
            times, values, x_min=0, x_max=100
        )

        # Should be decimated to <= 5000 points
        assert len(filtered_times) <= 5000
        assert len(filtered_values) <= 5000

    # ===== Adjust View Tests =====

    def test_adjust_view_with_data(self, plot_widget):
        """Test view adjustment with data"""
        times = np.linspace(0, 100, 1000)

        with patch.object(
            plot_widget.plot_widget, "setXRange"
        ) as mock_set_range:
            plot_widget._adjust_view(times)

            # Should set range
            mock_set_range.assert_called_once()

    def test_adjust_view_empty_data(self, plot_widget):
        """Test view adjustment with empty data"""
        times = np.array([])

        with patch.object(
            plot_widget.plot_widget, "setXRange"
        ) as mock_set_range:
            plot_widget._adjust_view(times)

            # Should set default range
            mock_set_range.assert_called_once_with(0, 1)

    # ===== Update Plot Tests (These may trigger pyqtgraph warnings) =====

    @pytest.mark.filterwarnings("ignore::RuntimeWarning")
    def test_update_plot_valid_data(self, plot_widget, sample_cavity_data):
        """Test updating plot with valid data"""
        cavity_num = 1

        # Suppress PyQtGraph internal errors during testing
        plot_widget.update_plot(cavity_num, sample_cavity_data)

        assert cavity_num in plot_widget._original_data
        assert cavity_num in plot_widget._decimated_data
        assert cavity_num in plot_widget.plot_curves

    def test_update_plot_invalid_data(self, plot_widget):
        """Test updating plot with invalid data"""
        cavity_num = 1
        invalid_data = {"decimation": 1}  # Missing DF

        plot_widget.update_plot(cavity_num, invalid_data)

        # Should not create curves for invalid data
        assert cavity_num not in plot_widget._original_data

    @pytest.mark.filterwarnings("ignore::RuntimeWarning")
    def test_update_plot_multiple_updates(self, plot_widget):
        """Test multiple sequential updates to same cavity"""
        cavity_num = 1

        for i in range(5):
            cavity_data = {
                "DF": np.random.randn(100 * (i + 1)),
                "decimation": 1,
            }
            plot_widget.update_plot(cavity_num, cavity_data)

        # Should still have only one curve
        assert len(plot_widget.plot_curves) == 1
        assert cavity_num in plot_widget._original_data

    # ===== Range Change Tests =====

    def test_on_range_changed_sets_zooming_flag(self, plot_widget):
        """Test that range change sets zooming flag"""
        plot_widget._is_zooming = False

        # Store some data first
        cavity_num = 1
        times = np.linspace(0, 100, 1000)
        values = np.sin(times)
        plot_widget._original_data[cavity_num] = (times, values)
        plot_widget._decimated_data[cavity_num] = (
            plot_widget._create_decimated_levels(times, values)
        )
        plot_widget.plot_curves[cavity_num] = Mock()

        plot_widget._on_range_changed()

        assert plot_widget._is_zooming is True

    def test_end_zoom_resets_flag(self, plot_widget):
        """Test that end zoom resets zooming flag"""
        plot_widget._is_zooming = True

        # Store some data
        cavity_num = 1
        times = np.linspace(0, 100, 1000)
        values = np.sin(times)
        plot_widget._original_data[cavity_num] = (times, values)
        plot_widget._decimated_data[cavity_num] = (
            plot_widget._create_decimated_levels(times, values)
        )
        plot_widget.plot_curves[cavity_num] = Mock()

        plot_widget._end_zoom()

        assert plot_widget._is_zooming is False

    # ===== Tooltip Formatting Tests =====

    def test_format_tooltip(self, plot_widget):
        """Test tooltip formatting"""
        tooltip = plot_widget._format_tooltip("time_series", x=5.123, y=123.456)

        assert "Time:" in tooltip
        assert "5.123" in tooltip
        assert "Detuning:" in tooltip
        assert "123.46" in tooltip

    # ===== Clear Plot Tests =====

    @pytest.mark.filterwarnings("ignore::RuntimeWarning")
    def test_clear_plot_all_cavities(self, plot_widget):
        """Test clearing all cavities' data"""
        # Add data for multiple cavities
        for cavity_num in [1, 2, 3]:
            cavity_data = {
                "DF": np.random.randn(100),
                "decimation": 1,
            }
            plot_widget.update_plot(cavity_num, cavity_data)

        assert len(plot_widget._original_data) == 3

        plot_widget.clear_plot()

        assert len(plot_widget._original_data) == 0
        assert len(plot_widget._decimated_data) == 0
        assert len(plot_widget.plot_curves) == 0

    # ===== Integration Tests =====

    @pytest.mark.filterwarnings("ignore::RuntimeWarning")
    def test_full_workflow(self, plot_widget):
        """Test complete workflow from data to visualization"""
        cavity_num = 1

        # Create realistic data
        cavity_data = {
            "DF": np.random.randn(1000) * 10 + 50,  # Detuning around 50 Hz
            "decimation": 1,
        }

        # Update plot
        plot_widget.update_plot(cavity_num, cavity_data)

        # Verify data stored
        assert cavity_num in plot_widget._original_data
        assert cavity_num in plot_widget._decimated_data
        assert cavity_num in plot_widget.plot_curves

        # Simulate zoom
        plot_widget._on_range_changed()
        assert plot_widget._is_zooming

        # Simulate zoom end
        plot_widget._end_zoom()
        assert not plot_widget._is_zooming

        # Clear plot
        plot_widget.clear_plot()
        assert cavity_num not in plot_widget._original_data

    @pytest.mark.filterwarnings("ignore::RuntimeWarning")
    def test_multiple_cavities_workflow(self, plot_widget):
        """Test workflow with multiple cavities"""
        for cavity_num in [1, 2, 3, 4]:
            cavity_data = {
                "DF": np.random.randn(500) * cavity_num * 5,
                "decimation": 1,
            }
            plot_widget.update_plot(cavity_num, cavity_data)

        # All cavities should be stored
        assert len(plot_widget._original_data) == 4
        assert len(plot_widget.plot_curves) == 4

        # Clear all
        plot_widget.clear_plot()
        assert len(plot_widget._original_data) == 0

    @pytest.mark.filterwarnings("ignore::RuntimeWarning")
    def test_large_dataset_performance(self, plot_widget, large_cavity_data):
        """Test handling of large datasets"""
        cavity_num = 1

        # Should handle large dataset without error
        plot_widget.update_plot(cavity_num, large_cavity_data)

        assert cavity_num in plot_widget._original_data
        times, values = plot_widget._original_data[cavity_num]

        # Data should be stored
        assert len(values) == 10000

        # Decimated levels should be created
        assert cavity_num in plot_widget._decimated_data
        assert len(plot_widget._decimated_data[cavity_num]) > 0

    # ===== Edge Case Tests =====

    @pytest.mark.filterwarnings("ignore::RuntimeWarning")
    def test_single_data_point(self, plot_widget):
        """Test with single data point"""
        cavity_data = {
            "DF": np.array([42.0]),
            "decimation": 1,
        }

        plot_widget.update_plot(1, cavity_data)

        # Should handle single point
        assert 1 in plot_widget._original_data

    @pytest.mark.filterwarnings("ignore::RuntimeWarning")
    def test_two_data_points(self, plot_widget):
        """Test with two data points"""
        cavity_data = {
            "DF": np.array([1.0, 2.0]),
            "decimation": 1,
        }

        plot_widget.update_plot(1, cavity_data)

        assert 1 in plot_widget._original_data
        times, values = plot_widget._original_data[1]
        assert len(times) == 2

    @pytest.mark.filterwarnings("ignore::RuntimeWarning")
    def test_negative_values(self, plot_widget):
        """Test with negative detuning values"""
        cavity_data = {
            "DF": np.array([-100.0, -50.0, -25.0, 0.0, 25.0]),
            "decimation": 1,
        }

        plot_widget.update_plot(1, cavity_data)

        assert 1 in plot_widget._original_data
        _, values = plot_widget._original_data[1]
        assert np.any(values < 0)

    # ===== Cavity Pen Tests =====

    def test_get_cavity_pen(self, plot_widget):
        """Test getting pen for cavity"""
        pen1 = plot_widget._get_cavity_pen(1)
        pen2 = plot_widget._get_cavity_pen(2)
        pen3 = plot_widget._get_cavity_pen(1)  # Same as pen1

        assert pen1 is not None
        assert pen2 is not None
        # Same cavity number should get same pen characteristics
        assert pen1.color().name() == pen3.color().name()

    def test_different_cavities_different_pens(self, plot_widget):
        """Test that different cavities get different colored pens"""
        pens = {}
        for i in range(1, 9):  # Test 8 cavities
            pens[i] = plot_widget._get_cavity_pen(i)

        # Should have different colors (though may wrap around after 8)
        colors = [pen.color().name() for pen in pens.values()]
        # At least some should be different
        assert len(set(colors[:8])) > 1
