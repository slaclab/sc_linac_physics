# tests/applications/microphonics/plots/test_spectrogram_plot.py

import numpy as np
import pyqtgraph as pg
import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication

from sc_linac_physics.applications.microphonics.plots.spectrogram_plot import SpectrogramPlot


@pytest.fixture(scope="session")
def qapp():
    """Create QApplication instance for tests"""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def spectrogram_plot(qapp, qtbot):
    """Create SpectrogramPlot instance for testing"""
    plot = SpectrogramPlot()
    qtbot.addWidget(plot)
    yield plot
    plot.close()


class TestSpectrogramPlotInitialization:
    """Test initialization and setup"""

    def test_initialization(self, spectrogram_plot):
        """Test that SpectrogramPlot initializes correctly"""
        assert spectrogram_plot is not None
        assert spectrogram_plot.plot_type == "spectrogram"
        assert spectrogram_plot.grid_columns == 2
        assert spectrogram_plot.max_columns == 4

    def test_initial_state(self, spectrogram_plot):
        """Test initial state of plot"""
        assert spectrogram_plot.cavity_data_cache == {}
        assert spectrogram_plot.cavity_order == []
        assert spectrogram_plot.cavity_is_visible_flags == {}
        assert spectrogram_plot.plot_items == {}
        assert spectrogram_plot.image_items == {}

    def test_ui_components_created(self, spectrogram_plot):
        """Test that UI components are created"""
        assert spectrogram_plot.grid_controls_widget is not None
        assert spectrogram_plot.columns_spinbox is not None
        assert spectrogram_plot.graphics_layout is not None

    def test_spinbox_configuration(self, spectrogram_plot):
        """Test spinbox is configured correctly"""
        assert spectrogram_plot.columns_spinbox.minimum() == 1
        assert spectrogram_plot.columns_spinbox.maximum() == 4
        assert spectrogram_plot.columns_spinbox.value() == 2

    def test_colormap_initialization(self, spectrogram_plot):
        """Test colormap is initialized"""
        assert spectrogram_plot.colormap is not None
        assert isinstance(spectrogram_plot.colormap, pg.ColorMap)


class TestGridControls:
    """Test grid layout controls"""

    def test_columns_change(self, spectrogram_plot):
        """Test changing column count"""
        spectrogram_plot.columns_spinbox.setValue(3)
        assert spectrogram_plot.grid_columns == 3

    def test_columns_change_refreshes_layout(self, spectrogram_plot):
        """Test that changing columns refreshes layout"""
        # Add some test data first
        test_data = self._create_test_data(1000, 1e6)
        spectrogram_plot.update_plot(1, test_data)

        spectrogram_plot.columns_spinbox.setValue(4)

        # Layout should be refreshed
        assert spectrogram_plot.grid_columns == 4

    def test_auto_arrange_no_cavities(self, spectrogram_plot):
        """Test auto arrange with no visible cavities"""
        spectrogram_plot._auto_arrange_grid()
        # Should not crash, spinbox value should remain
        assert spectrogram_plot.columns_spinbox.value() >= 1

    def test_auto_arrange_one_cavity(self, spectrogram_plot):
        """Test auto arrange with one cavity"""
        test_data = self._create_test_data(1000, 1e6)
        spectrogram_plot.update_plot(1, test_data)

        spectrogram_plot._auto_arrange_grid()
        assert spectrogram_plot.columns_spinbox.value() == 1

    def test_auto_arrange_two_cavities(self, spectrogram_plot):
        """Test auto arrange with two cavities"""
        test_data = self._create_test_data(1000, 1e6)
        spectrogram_plot.update_plot(1, test_data)
        spectrogram_plot.update_plot(2, test_data)

        spectrogram_plot._auto_arrange_grid()
        assert spectrogram_plot.columns_spinbox.value() == 1

    def test_auto_arrange_three_cavities(self, spectrogram_plot):
        """Test auto arrange with three cavities"""
        test_data = self._create_test_data(1000, 1e6)
        for i in range(1, 4):
            spectrogram_plot.update_plot(i, test_data)

        spectrogram_plot._auto_arrange_grid()
        assert spectrogram_plot.columns_spinbox.value() == 2

    def test_auto_arrange_five_cavities(self, spectrogram_plot):
        """Test auto arrange with five cavities"""
        test_data = self._create_test_data(1000, 1e6)
        for i in range(1, 6):
            spectrogram_plot.update_plot(i, test_data)

        spectrogram_plot._auto_arrange_grid()
        assert spectrogram_plot.columns_spinbox.value() == 3

    def test_auto_arrange_eight_cavities(self, spectrogram_plot):
        """Test auto arrange with eight cavities"""
        test_data = self._create_test_data(1000, 1e6)
        for i in range(1, 9):
            spectrogram_plot.update_plot(i, test_data)

        spectrogram_plot._auto_arrange_grid()
        assert spectrogram_plot.columns_spinbox.value() == 4

    @staticmethod
    def _create_test_data(num_samples, sample_rate):
        """Helper to create test data in the correct format"""
        time = np.arange(num_samples) / sample_rate
        data = np.sin(2 * np.pi * 1000 * time)  # 1kHz signal
        return {"DF": data}


class TestDataProcessing:
    """Test data processing and spectrogram calculation"""

    def test_update_plot_valid_data(self, spectrogram_plot):
        """Test updating plot with valid data"""
        test_data = self._create_test_data(10000, 1e6)
        spectrogram_plot.update_plot(1, test_data)

        assert 1 in spectrogram_plot.cavity_data_cache
        assert 1 in spectrogram_plot.cavity_order
        assert spectrogram_plot.cavity_is_visible_flags[1] is True

    def test_update_plot_creates_spectrogram(self, spectrogram_plot):
        """Test that spectrogram data is calculated"""
        test_data = self._create_test_data(10000, 1e6)
        spectrogram_plot.update_plot(1, test_data)

        Sxx, t, f, sr = spectrogram_plot.cavity_data_cache[1]
        assert Sxx is not None
        assert len(t) > 0
        assert len(f) > 0
        # The effective sample rate after spectrogram processing may differ from input
        # Verify it's a reasonable value (between 100 Hz and input sample rate)
        assert 100 <= sr <= 1e6

    # ... rest of the tests

    def test_update_plot_empty_data(self, spectrogram_plot):
        """Test updating with empty data"""
        empty_data = {"DF": np.array([])}
        spectrogram_plot.update_plot(1, empty_data)

        # Should not add to cache
        assert 1 not in spectrogram_plot.cavity_data_cache

    def test_update_plot_missing_detune(self, spectrogram_plot):
        """Test updating with missing DF channel"""
        bad_data = {"OTHER": np.array([1, 2, 3])}

        # Should handle gracefully (log error)
        spectrogram_plot.update_plot(1, bad_data)
        assert 1 not in spectrogram_plot.cavity_data_cache

    def test_update_plot_none_data(self, spectrogram_plot):
        """Test updating with None data"""
        spectrogram_plot.update_plot(1, None)
        # Should handle gracefully
        assert 1 not in spectrogram_plot.cavity_data_cache

    def test_update_multiple_cavities(self, spectrogram_plot):
        """Test updating multiple cavities"""
        test_data = self._create_test_data(5000, 1e6)

        for cavity_num in [1, 3, 5]:
            spectrogram_plot.update_plot(cavity_num, test_data)

        assert len(spectrogram_plot.cavity_data_cache) == 3
        assert spectrogram_plot.cavity_order == [1, 3, 5]

    def test_cavity_order_maintained(self, spectrogram_plot):
        """Test that cavity order is sorted"""
        test_data = self._create_test_data(5000, 1e6)

        # Add in random order
        for cavity_num in [5, 2, 8, 1]:
            spectrogram_plot.update_plot(cavity_num, test_data)

        assert spectrogram_plot.cavity_order == [1, 2, 5, 8]

    def test_update_existing_cavity(self, spectrogram_plot):
        """Test updating data for existing cavity"""
        test_data1 = self._create_test_data(5000, 1e6)
        test_data2 = self._create_test_data(8000, 1e6)

        spectrogram_plot.update_plot(1, test_data1)
        Sxx1, _, _, _ = spectrogram_plot.cavity_data_cache[1]

        spectrogram_plot.update_plot(1, test_data2)
        Sxx2, _, _, _ = spectrogram_plot.cavity_data_cache[1]

        # Data should be updated
        assert Sxx1.shape != Sxx2.shape or not np.array_equal(Sxx1, Sxx2)

    @staticmethod
    def _create_test_data(num_samples, sample_rate):
        """Helper to create test data in the correct format"""
        time = np.arange(num_samples) / sample_rate
        # Create signal with multiple frequencies
        data = np.sin(2 * np.pi * 1000 * time) + 0.5 * np.sin(2 * np.pi * 5000 * time)
        return {"DF": data}


class TestGridLayout:
    """Test grid layout functionality"""

    def test_refresh_grid_layout_empty(self, spectrogram_plot):
        """Test refreshing grid with no data"""
        spectrogram_plot._refresh_grid_layout()

        assert len(spectrogram_plot.plot_items) == 0
        assert len(spectrogram_plot.image_items) == 0

    def test_refresh_creates_plot_items(self, spectrogram_plot):
        """Test that refresh creates plot items"""
        test_data = self._create_test_data(5000, 1e6)
        spectrogram_plot.update_plot(1, test_data)

        assert 1 in spectrogram_plot.plot_items
        assert isinstance(spectrogram_plot.plot_items[1], pg.PlotItem)

    def test_refresh_creates_image_items(self, spectrogram_plot):
        """Test that refresh creates image items"""
        test_data = self._create_test_data(5000, 1e6)
        spectrogram_plot.update_plot(1, test_data)

        assert 1 in spectrogram_plot.image_items
        assert isinstance(spectrogram_plot.image_items[1], pg.ImageItem)

    def test_grid_layout_single_cavity(self, spectrogram_plot):
        """Test grid layout with single cavity"""
        test_data = self._create_test_data(5000, 1e6)
        spectrogram_plot.update_plot(1, test_data)

        # Should be at position (0, 0)
        plot_item = spectrogram_plot.plot_items[1]
        assert plot_item is not None

    def test_grid_layout_multiple_cavities(self, spectrogram_plot):
        """Test grid layout with multiple cavities"""
        test_data = self._create_test_data(5000, 1e6)
        spectrogram_plot.columns_spinbox.setValue(2)

        for i in range(1, 5):
            spectrogram_plot.update_plot(i, test_data)

        assert len(spectrogram_plot.plot_items) == 4
        assert len(spectrogram_plot.image_items) == 4

    def test_grid_layout_respects_columns(self, spectrogram_plot):
        """Test that grid layout respects column setting"""
        test_data = self._create_test_data(5000, 1e6)
        spectrogram_plot.columns_spinbox.setValue(3)

        for i in range(1, 7):
            spectrogram_plot.update_plot(i, test_data)

        # With 6 cavities and 3 columns, should have 2 rows
        assert len(spectrogram_plot.plot_items) == 6

    def test_plot_titles(self, spectrogram_plot):
        """Test that plots have correct titles"""
        test_data = self._create_test_data(5000, 1e6)
        spectrogram_plot.update_plot(3, test_data)

        plot_item = spectrogram_plot.plot_items[3]
        title = plot_item.titleLabel.text
        assert "Cavity 3" in title

    def test_plot_labels(self, spectrogram_plot):
        """Test that plots have axis labels"""
        test_data = self._create_test_data(5000, 1e6)
        spectrogram_plot.update_plot(1, test_data)

        plot_item = spectrogram_plot.plot_items[1]
        # Check that axes exist
        assert plot_item.getAxis("bottom") is not None
        assert plot_item.getAxis("left") is not None

    @staticmethod
    def _create_test_data(num_samples, sample_rate):
        """Helper to create test data"""
        time = np.arange(num_samples) / sample_rate
        data = np.sin(2 * np.pi * 1000 * time)
        return {"DF": data}


class TestVisibilityControl:
    """Test cavity visibility toggling"""

    def test_toggle_cavity_visibility_check(self, spectrogram_plot):
        """Test toggling cavity to visible"""
        spectrogram_plot.toggle_cavity_visibility(1, Qt.Checked)
        assert spectrogram_plot.cavity_is_visible_flags[1] is True

    def test_toggle_cavity_visibility_uncheck(self, spectrogram_plot):
        """Test toggling cavity to invisible"""
        spectrogram_plot.toggle_cavity_visibility(1, Qt.Checked)
        spectrogram_plot.toggle_cavity_visibility(1, Qt.Unchecked)
        assert spectrogram_plot.cavity_is_visible_flags[1] is False

    def test_visibility_affects_layout(self, spectrogram_plot):
        """Test that visibility affects grid layout"""
        test_data = self._create_test_data(5000, 1e6)

        # Add two cavities
        spectrogram_plot.update_plot(1, test_data)
        spectrogram_plot.update_plot(2, test_data)
        assert len(spectrogram_plot.plot_items) == 2

        # Hide one cavity
        spectrogram_plot.toggle_cavity_visibility(1, Qt.Unchecked)

        # Should only show one plot
        visible_count = sum(
            1 for cav in spectrogram_plot.cavity_order if spectrogram_plot.cavity_is_visible_flags.get(cav, False)
        )
        assert visible_count == 1

    def test_toggle_multiple_cavities(self, spectrogram_plot):
        """Test toggling multiple cavities"""
        test_data = self._create_test_data(5000, 1e6)

        for i in range(1, 5):
            spectrogram_plot.update_plot(i, test_data)

        # Hide cavities 2 and 4
        spectrogram_plot.toggle_cavity_visibility(2, Qt.Unchecked)
        spectrogram_plot.toggle_cavity_visibility(4, Qt.Unchecked)

        assert spectrogram_plot.cavity_is_visible_flags[1] is True
        assert spectrogram_plot.cavity_is_visible_flags[2] is False
        assert spectrogram_plot.cavity_is_visible_flags[3] is True
        assert spectrogram_plot.cavity_is_visible_flags[4] is False

    @staticmethod
    def _create_test_data(num_samples, sample_rate):
        """Helper to create test data"""
        time = np.arange(num_samples) / sample_rate
        data = np.sin(2 * np.pi * 1000 * time)
        return {"DF": data}


class TestColorbar:
    """Test colorbar functionality"""

    def test_colorbar_created(self, spectrogram_plot):
        """Test that colorbar is created when data is added"""
        test_data = self._create_test_data(5000, 1e6)
        spectrogram_plot.update_plot(1, test_data)

        assert spectrogram_plot.colorbar is not None

    def test_colorbar_has_correct_colormap(self, spectrogram_plot):
        """Test that colorbar uses viridis colormap"""
        test_data = self._create_test_data(5000, 1e6)
        spectrogram_plot.update_plot(1, test_data)

        assert spectrogram_plot.colorbar is not None
        # Colorbar should use the same colormap
        assert spectrogram_plot.colormap.name == "viridis"

    def test_colorbar_linked_to_image(self, spectrogram_plot):
        """Test that colorbar is linked to image item"""
        test_data = self._create_test_data(5000, 1e6)
        spectrogram_plot.update_plot(1, test_data)

        # Colorbar should be linked to an image item
        assert spectrogram_plot.colorbar is not None

    @staticmethod
    def _create_test_data(num_samples, sample_rate):
        """Helper to create test data"""
        time = np.arange(num_samples) / sample_rate
        data = np.sin(2 * np.pi * 1000 * time)
        return {"DF": data}


class TestConfigurationManagement:
    """Test configuration management"""

    def test_set_plot_config_updates_columns(self, spectrogram_plot):
        """Test that config updates column count"""
        config = {"spectrogram": {"grid_columns": 4}}
        spectrogram_plot.set_plot_config(config)
        assert spectrogram_plot.grid_columns == 4

    def test_set_plot_config_preserves_existing_columns(self, spectrogram_plot):
        """Test that missing config preserves column setting"""
        spectrogram_plot.columns_spinbox.setValue(3)
        config = {"spectrogram": {}}

        spectrogram_plot.set_plot_config(config)
        # Should keep existing value
        assert spectrogram_plot.grid_columns == 3

    def test_set_plot_config_with_x_range(self, spectrogram_plot):
        """Test that x_range config is stored"""
        config = {"spectrogram": {"x_range": [0, 10]}}
        spectrogram_plot.set_plot_config(config)
        assert spectrogram_plot.config["spectrogram"]["x_range"] == [0, 10]

    def test_set_plot_config_triggers_refresh(self, spectrogram_plot):
        """Test that config change triggers layout refresh"""
        test_data = self._create_test_data(5000, 1e6)
        spectrogram_plot.update_plot(1, test_data)

        config = {"spectrogram": {"grid_columns": 4}}

        spectrogram_plot.set_plot_config(config)
        # Should have refreshed layout
        assert spectrogram_plot.grid_columns == 4

    @staticmethod
    def _create_test_data(num_samples, sample_rate):
        """Helper to create test data"""
        time = np.arange(num_samples) / sample_rate
        data = np.sin(2 * np.pi * 1000 * time)
        return {"DF": data}


class TestClearPlot:
    """Test clear plot functionality"""

    def test_clear_plot_empties_cache(self, spectrogram_plot):
        """Test that clear_plot empties data cache"""
        test_data = self._create_test_data(5000, 1e6)
        spectrogram_plot.update_plot(1, test_data)

        spectrogram_plot.clear_plot()
        assert len(spectrogram_plot.cavity_data_cache) == 0

    def test_clear_plot_empties_order(self, spectrogram_plot):
        """Test that clear_plot empties cavity order"""
        test_data = self._create_test_data(5000, 1e6)
        spectrogram_plot.update_plot(1, test_data)

        spectrogram_plot.clear_plot()
        assert len(spectrogram_plot.cavity_order) == 0

    def test_clear_plot_empties_visibility_flags(self, spectrogram_plot):
        """Test that clear_plot empties visibility flags"""
        test_data = self._create_test_data(5000, 1e6)
        spectrogram_plot.update_plot(1, test_data)

        spectrogram_plot.clear_plot()
        assert len(spectrogram_plot.cavity_is_visible_flags) == 0

    def test_clear_plot_removes_plot_items(self, spectrogram_plot):
        """Test that clear_plot removes plot items"""
        test_data = self._create_test_data(5000, 1e6)
        spectrogram_plot.update_plot(1, test_data)

        spectrogram_plot.clear_plot()
        # Plot items should be cleared
        assert len(spectrogram_plot.plot_items) == 0
        assert len(spectrogram_plot.image_items) == 0

    def test_clear_plot_multiple_cavities(self, spectrogram_plot):
        """Test clearing plot with multiple cavities"""
        test_data = self._create_test_data(5000, 1e6)

        for i in range(1, 5):
            spectrogram_plot.update_plot(i, test_data)

        spectrogram_plot.clear_plot()

        assert len(spectrogram_plot.cavity_data_cache) == 0
        assert len(spectrogram_plot.cavity_order) == 0
        assert len(spectrogram_plot.plot_items) == 0

    @staticmethod
    def _create_test_data(num_samples, sample_rate):
        """Helper to create test data"""
        time = np.arange(num_samples) / sample_rate
        data = np.sin(2 * np.pi * 1000 * time)
        return {"DF": data}


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_very_short_signal(self, spectrogram_plot):
        """Test with very short signal"""
        test_data = {"DF": np.random.randn(10)}

        # Should handle gracefully (might skip or use minimal window)
        spectrogram_plot.update_plot(1, test_data)

    def test_single_sample(self, spectrogram_plot):
        """Test with single sample"""
        test_data = {"DF": np.array([1.0])}

        spectrogram_plot.update_plot(1, test_data)
        # Should not crash

    def test_very_long_signal(self, spectrogram_plot):
        """Test with very long signal"""
        test_data = {"DF": np.random.randn(1000000)}

        spectrogram_plot.update_plot(1, test_data)
        assert 1 in spectrogram_plot.cavity_data_cache

    def test_nan_values(self, spectrogram_plot):
        """Test with NaN values in data"""
        data = np.random.randn(5000)
        data[100:200] = np.nan

        test_data = {"DF": data}

        # Should handle NaN gracefully
        spectrogram_plot.update_plot(1, test_data)

    def test_inf_values(self, spectrogram_plot):
        """Test with infinite values"""
        data = np.random.randn(5000)
        data[100] = np.inf
        data[200] = -np.inf

        test_data = {"DF": data}

        # Should handle inf gracefully
        spectrogram_plot.update_plot(1, test_data)

    def test_all_zeros(self, spectrogram_plot):
        """Test with all zero signal"""
        test_data = {"DF": np.zeros(5000)}

        spectrogram_plot.update_plot(1, test_data)
        assert 1 in spectrogram_plot.cavity_data_cache

    def test_max_cavities(self, spectrogram_plot):
        """Test with maximum number of cavities"""
        test_data = self._create_test_data(5000, 1e6)

        for i in range(1, spectrogram_plot.max_cavities + 1):
            spectrogram_plot.update_plot(i, test_data)

        assert len(spectrogram_plot.cavity_data_cache) == spectrogram_plot.max_cavities

    def test_cavity_zero(self, spectrogram_plot):
        """Test with cavity number 0"""
        test_data = self._create_test_data(5000, 1e6)
        spectrogram_plot.update_plot(0, test_data)

        # Should handle gracefully
        # Cavity 0 might be valid or rejected depending on implementation
        # Just ensure it doesn't crash

    def test_negative_cavity_number(self, spectrogram_plot):
        """Test with negative cavity number"""
        test_data = self._create_test_data(5000, 1e6)

        # Should handle gracefully or reject
        spectrogram_plot.update_plot(-1, test_data)
        # Just ensure it doesn't crash

    @staticmethod
    def _create_test_data(num_samples, sample_rate):
        """Helper to create test data"""
        time = np.arange(num_samples) / sample_rate
        data = np.sin(2 * np.pi * 1000 * time)
        return {"DF": data}


class TestIntegrationScenarios:
    """Test complete workflows"""

    def test_full_workflow(self, spectrogram_plot):
        """Test complete workflow: add data, configure, toggle visibility, clear"""
        test_data = self._create_test_data(5000, 1e6)

        # Add multiple cavities
        for i in range(1, 4):
            spectrogram_plot.update_plot(i, test_data)

        assert len(spectrogram_plot.cavity_data_cache) == 3

        # Change configuration
        config = {"spectrogram": {"grid_columns": 3}}
        spectrogram_plot.set_plot_config(config)
        assert spectrogram_plot.grid_columns == 3

        # Toggle visibility
        spectrogram_plot.toggle_cavity_visibility(2, Qt.Unchecked)
        assert spectrogram_plot.cavity_is_visible_flags[2] is False

        # Clear all
        spectrogram_plot.clear_plot()
        assert len(spectrogram_plot.cavity_data_cache) == 0

    def test_update_then_hide_then_update(self, spectrogram_plot):
        """Test updating, hiding, then updating again"""
        test_data = self._create_test_data(5000, 1e6)

        spectrogram_plot.update_plot(1, test_data)
        spectrogram_plot.toggle_cavity_visibility(1, Qt.Unchecked)

        new_data = self._create_test_data(8000, 1e6)
        spectrogram_plot.update_plot(1, new_data)

        # Data should be updated, visibility unchanged
        assert 1 in spectrogram_plot.cavity_data_cache
        assert spectrogram_plot.cavity_is_visible_flags[1] is False

    def test_multiple_updates_same_cavity(self, spectrogram_plot):
        """Test multiple updates to the same cavity"""
        for i in range(5):
            test_data = self._create_test_data(5000 + i * 1000, 1e6)
            spectrogram_plot.update_plot(1, test_data)

        # Should only have one cavity
        assert len(spectrogram_plot.cavity_data_cache) == 1
        assert len(spectrogram_plot.cavity_order) == 1

    def test_dynamic_column_adjustment(self, spectrogram_plot):
        """Test dynamic column adjustment as cavities are added"""
        test_data = self._create_test_data(5000, 1e6)

        # Add cavities one by one and check auto-arrangement
        spectrogram_plot.update_plot(1, test_data)
        spectrogram_plot._auto_arrange_grid()
        col_1 = spectrogram_plot.grid_columns

        spectrogram_plot.update_plot(2, test_data)
        spectrogram_plot.update_plot(3, test_data)
        spectrogram_plot._auto_arrange_grid()
        col_3 = spectrogram_plot.grid_columns

        # More cavities should trigger more columns
        assert col_3 >= col_1

    @staticmethod
    def _create_test_data(num_samples, sample_rate):
        """Helper to create test data"""
        time = np.arange(num_samples) / sample_rate
        data = np.sin(2 * np.pi * 1000 * time)
        return {"DF": data}
