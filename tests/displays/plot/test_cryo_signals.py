import sys
from unittest.mock import Mock, patch

import pytest
from qtpy.QtWidgets import QApplication, QDialog

from sc_linac_physics.displays.plot.cryo_signals import (
    LinacGroupedCryomodulePlotDisplay,
    GlobalAxisRangeDialog,
)
from sc_linac_physics.utils.sc_linac.linac import Machine


@pytest.fixture(scope="session")
def qapp():
    """Create QApplication instance for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


@pytest.fixture
def mock_machine():
    """Create a mock Machine object with linacs and cryomodules."""
    machine = Mock(spec=Machine)

    # Create mock linacs
    mock_linacs = []

    for linac_idx, linac_name in enumerate(["L0B", "L1B", "L2B", "L3B"]):
        linac = Mock()
        linac.name = linac_name
        linac.cryomodules = {}

        # Add different number of cryomodules per linac
        if linac_name == "L0B":
            cm_names = ["01"]
        elif linac_name == "L1B":
            cm_names = ["02", "03", "H1", "H2"]
        elif linac_name == "L2B":
            cm_names = [f"{i:02d}" for i in range(4, 16)]
        else:  # L3B
            cm_names = [f"{i:02d}" for i in range(16, 36)]

        for cm_name in cm_names:
            cm = Mock()
            cm.name = cm_name
            cm.jt_valve_readback_pv = f"CLIC:CM{cm_name}:3001:PVJT:ORBV"
            cm.ds_level_pv = f"CLL:CM{cm_name}:2301:DS:LVL"
            cm.us_level_pv = f"CLL:CM{cm_name}:2601:US:LVL"
            cm.heater_readback_pv = f"CPIC:CM{cm_name}:0000:EHCV:ORBV"
            cm.aact_mean_sum_pv = f"ACCL:{linac_name}:{cm_name}00:AACTMEANSUM"

            linac.cryomodules[cm_name] = cm

        mock_linacs.append(linac)

    machine.linacs = mock_linacs
    return machine


@pytest.fixture
def display(qapp, mock_machine):
    """Create LinacGroupedCryomodulePlotDisplay instance with mocked data."""
    with (
        patch(
            "sc_linac_physics.displays.plot.cryo_signals.Machine"
        ) as MockMachine,
        patch(
            "sc_linac_physics.displays.plot.embeddable_plots.PyDMArchiverTimePlot"
        ) as MockArchiverPlot,
    ):

        MockMachine.return_value = mock_machine

        # Create a mock archiver time plot that IS a QWidget
        def create_mock_archiver_plot(*args, **kwargs):
            """Factory function to create mock archiver plot."""
            from PyQt5.QtWidgets import QWidget

            # Create a real QWidget as the base
            mock_archiver = QWidget()

            # Mock plot item
            mock_plot_item = Mock()
            mock_plot_item.axes = {}
            mock_plot_item.curves = []
            mock_plot_item.update = Mock()

            # Add mock methods as attributes
            mock_archiver.getPlotItem = Mock(return_value=mock_plot_item)
            mock_archiver.addYChannel = Mock()
            mock_archiver.setTimeSpan = Mock()
            mock_archiver.setPlotTitle = Mock()
            mock_archiver.clearCurves = Mock()
            mock_archiver.removeYChannel = Mock()
            mock_archiver.update = Mock()
            mock_archiver.showLegend = True
            mock_archiver.updateMode = None

            return mock_archiver

        MockArchiverPlot.side_effect = create_mock_archiver_plot

        display = LinacGroupedCryomodulePlotDisplay()
        yield display
        display.close()


class TestLinacGroupedCryomodulePlotDisplayInitialization:
    """Test display initialization."""

    def test_display_creation(self, display):
        """Test that display is created successfully."""
        assert display is not None
        assert hasattr(display, "machine")
        assert hasattr(display, "cryomodule_plots")
        assert hasattr(display, "global_axis_settings")

    def test_default_axis_settings_initialized(self, display):
        """Test that default axis settings are initialized."""
        assert len(display.global_axis_settings) > 0

        # Check AACT default
        assert "aact_mean_sum_pv" in display.global_axis_settings
        assert (
            display.global_axis_settings["aact_mean_sum_pv"]["auto_scale"]
            is False
        )
        assert display.global_axis_settings["aact_mean_sum_pv"]["range"] == (
            0,
            144,
        )

        # Check level defaults
        assert "ds_level_pv" in display.global_axis_settings
        assert display.global_axis_settings["ds_level_pv"]["range"] == (
            80,
            100,
        )

        assert "us_level_pv" in display.global_axis_settings
        assert display.global_axis_settings["us_level_pv"]["range"] == (60, 80)

    def test_linac_selector_populated(self, display):
        """Test that linac selector is populated with linacs."""
        assert display.linac_combo.count() == 4
        assert display.linac_combo.itemText(0) == "L0B"
        assert display.linac_combo.itemText(1) == "L1B"
        assert display.linac_combo.itemText(2) == "L2B"
        assert display.linac_combo.itemText(3) == "L3B"

    def test_initial_linac_loaded(self, display):
        """Test that first linac is loaded initially."""
        assert display.current_linac_widget is not None
        assert len(display.cryomodule_plots) > 0


class TestGridDimensionsCalculation:
    """Test grid dimensions calculation."""

    def test_zero_items(self, display):
        """Test grid dimensions with zero items."""
        cols, rows = display._calculate_grid_dimensions(0)
        assert cols == 0
        assert rows == 0

    def test_one_item(self, display):
        """Test grid dimensions with one item."""
        cols, rows = display._calculate_grid_dimensions(1)
        assert cols == 1
        assert rows == 1

    def test_four_items(self, display):
        """Test grid dimensions with four items."""
        cols, rows = display._calculate_grid_dimensions(4)
        assert cols == 2
        assert rows == 2

    def test_twelve_items(self, display):
        """Test grid dimensions with twelve items."""
        cols, rows = display._calculate_grid_dimensions(12)
        assert cols == 4
        assert rows == 3

    def test_twenty_items(self, display):
        """Test grid dimensions with twenty items."""
        cols, rows = display._calculate_grid_dimensions(20)
        assert cols == 5
        assert rows == 4

    def test_grid_contains_all_items(self, display):
        """Test that grid dimensions can contain all items."""
        for num_items in range(1, 25):
            cols, rows = display._calculate_grid_dimensions(num_items)
            assert cols * rows >= num_items


class TestLinacSwitching:
    """Test linac switching functionality."""

    def test_switch_to_different_linac(self, display):
        """Test switching to a different linac."""
        # Switch to L1B (index 1)
        display.linac_combo.setCurrentIndex(1)

        # Should have different plots now (L1B has 4 CMs)
        assert len(display.cryomodule_plots) == 4

    def test_plots_cleared_on_switch(self, display):
        """Test that old plots are cleared when switching linacs."""
        # Get initial plot references
        initial_plot_keys = set(display.cryomodule_plots.keys())

        # Switch linac
        display.linac_combo.setCurrentIndex(1)

        # New plot keys should be different
        new_plot_keys = set(display.cryomodule_plots.keys())
        assert initial_plot_keys != new_plot_keys

    def test_widget_replaced_on_switch(self, display):
        """Test that widget is replaced when switching linacs."""
        initial_widget = display.current_linac_widget

        display.linac_combo.setCurrentIndex(1)

        assert display.current_linac_widget != initial_widget


class TestCryomodulePlotCreation:
    """Test cryomodule plot creation."""

    def test_plots_created_for_all_cryomodules(self, display):
        """Test that plots are created for all cryomodules in selected linac."""
        # L0B should have 1 cryomodule
        display.linac_combo.setCurrentIndex(0)
        assert len(display.cryomodule_plots) == 1

        # L1B should have 4 cryomodules
        display.linac_combo.setCurrentIndex(1)
        assert len(display.cryomodule_plots) == 4

    def test_plot_keys_include_linac_and_cm_names(self, display):
        """Test that plot keys include both linac and cryomodule names."""
        display.linac_combo.setCurrentIndex(0)  # L0B

        keys = list(display.cryomodule_plots.keys())
        assert len(keys) > 0

        linac_name, cm_name = keys[0]
        assert linac_name == "L0B"
        assert isinstance(cm_name, str)


class TestPVSelection:
    """Test PV selection and addition to plots."""

    def test_correct_pvs_added(self, display):
        """Test that correct PV types are added to plots."""
        # Check that SELECTED_PV_ATTRIBUTES are used
        assert len(display.SELECTED_PV_ATTRIBUTES) == 5
        assert "jt_valve_readback_pv" in display.SELECTED_PV_ATTRIBUTES
        assert "ds_level_pv" in display.SELECTED_PV_ATTRIBUTES
        assert "us_level_pv" in display.SELECTED_PV_ATTRIBUTES
        assert "heater_readback_pv" in display.SELECTED_PV_ATTRIBUTES
        assert "aact_mean_sum_pv" in display.SELECTED_PV_ATTRIBUTES


class TestGlobalAxisRangeDialog:
    """Test global axis range dialog."""

    def test_dialog_creation(self, display):
        """Test that dialog can be created."""
        dialog = GlobalAxisRangeDialog(display.SELECTED_PV_ATTRIBUTES, display)
        assert dialog is not None
        assert len(dialog.axis_controls) == 5

    def test_dialog_has_controls_for_all_pv_types(self, display):
        """Test that dialog has controls for all PV types."""
        dialog = GlobalAxisRangeDialog(display.SELECTED_PV_ATTRIBUTES, display)

        for pv_attr in display.SELECTED_PV_ATTRIBUTES:
            assert pv_attr in dialog.axis_controls
            assert "auto_check" in dialog.axis_controls[pv_attr]
            assert "y_min" in dialog.axis_controls[pv_attr]
            assert "y_max" in dialog.axis_controls[pv_attr]

    def test_auto_scale_toggles_inputs(self, display):
        """Test that auto-scale checkbox toggles input fields."""
        dialog = GlobalAxisRangeDialog(display.SELECTED_PV_ATTRIBUTES, display)

        controls = dialog.axis_controls["ds_level_pv"]
        auto_check = controls["auto_check"]
        y_min = controls["y_min"]
        y_max = controls["y_max"]

        # Initially auto-scale is checked, inputs should be disabled
        assert auto_check.isChecked() is True
        assert y_min.isEnabled() is False
        assert y_max.isEnabled() is False

        # Uncheck auto-scale, inputs should be enabled
        auto_check.setChecked(False)
        assert y_min.isEnabled() is True
        assert y_max.isEnabled() is True

    def test_get_settings_with_manual_range(self, display):
        """Test getting settings with manual range."""
        dialog = GlobalAxisRangeDialog(display.SELECTED_PV_ATTRIBUTES, display)

        controls = dialog.axis_controls["ds_level_pv"]
        controls["auto_check"].setChecked(False)
        controls["y_min"].setText("10")
        controls["y_max"].setText("90")

        settings = dialog.get_settings()

        assert settings["ds_level_pv"]["auto_scale"] is False
        assert settings["ds_level_pv"]["range"] == (10.0, 90.0)

    def test_get_settings_with_auto_scale(self, display):
        """Test getting settings with auto-scale."""
        dialog = GlobalAxisRangeDialog(display.SELECTED_PV_ATTRIBUTES, display)

        controls = dialog.axis_controls["ds_level_pv"]
        controls["auto_check"].setChecked(True)

        settings = dialog.get_settings()

        assert settings["ds_level_pv"]["auto_scale"] is True
        assert settings["ds_level_pv"]["range"] is None

    def test_invalid_range_reverts_to_auto(self, display):
        """Test that invalid range reverts to auto-scale."""
        dialog = GlobalAxisRangeDialog(display.SELECTED_PV_ATTRIBUTES, display)

        controls = dialog.axis_controls["ds_level_pv"]
        controls["auto_check"].setChecked(False)
        controls["y_min"].setText("100")
        controls["y_max"].setText("10")  # Invalid: min > max

        settings = dialog.get_settings()

        # Should revert to auto-scale
        assert settings["ds_level_pv"]["auto_scale"] is True


class TestGlobalAxisRangeApplication:
    """Test applying global axis ranges."""

    def test_open_dialog_with_defaults(self, display):
        """Test that dialog opens with default values."""
        with patch.object(
            GlobalAxisRangeDialog, "exec_", return_value=QDialog.Rejected
        ):
            display.open_global_axis_range_dialog()
            # Should not crash

    def test_apply_global_settings(self, display):
        """Test applying global axis settings."""
        settings = {
            "ds_level_pv": {"auto_scale": False, "range": (0, 100)},
            "us_level_pv": {"auto_scale": False, "range": (0, 100)},
        }

        display.apply_global_axis_settings(settings)

        assert display.global_axis_settings["ds_level_pv"]["range"] == (
            0,
            100,
        )
        assert display.global_axis_settings["us_level_pv"]["range"] == (
            0,
            100,
        )

    def test_settings_persist_across_linac_switch(self, display):
        """Test that settings persist when switching linacs."""
        # Set custom settings
        settings = {
            "ds_level_pv": {"auto_scale": False, "range": (20, 80)},
        }
        display.apply_global_axis_settings(settings)

        # Switch linac
        display.linac_combo.setCurrentIndex(1)

        # Settings should still be stored
        assert display.global_axis_settings["ds_level_pv"]["range"] == (
            20,
            80,
        )


class TestDefaultRanges:
    """Test default range configurations."""

    def test_default_ranges_defined(self, display):
        """Test that default ranges are defined."""
        assert hasattr(display, "DEFAULT_AXIS_RANGES")
        assert len(display.DEFAULT_AXIS_RANGES) > 0

    def test_aact_default_range(self, display):
        """Test AACT default range."""
        assert display.DEFAULT_AXIS_RANGES["aact_mean_sum_pv"] == (0, 144)

    def test_level_default_ranges(self, display):
        """Test level default ranges."""
        assert display.DEFAULT_AXIS_RANGES["ds_level_pv"] == (80, 100)
        assert display.DEFAULT_AXIS_RANGES["us_level_pv"] == (60, 80)

    def test_auto_scale_defaults(self, display):
        """Test that some PVs default to auto-scale."""
        assert display.DEFAULT_AXIS_RANGES["jt_valve_readback_pv"] is None
        assert display.DEFAULT_AXIS_RANGES["heater_readback_pv"] is None


class TestUIComponents:
    """Test UI component existence and behavior."""

    def test_linac_selector_exists(self, display):
        """Test that linac selector exists."""
        assert display.linac_combo is not None

    def test_content_container_exists(self, display):
        """Test that content container exists."""
        assert display.content_container is not None
        assert display.content_layout is not None

    def test_axis_range_button_exists(self, display):
        """Test that axis range configuration button exists."""
        # Find the button in the layout
        found_button = False
        for i in range(display.layout().count()):
            item = display.layout().itemAt(i)
            if item and hasattr(item, "layout"):
                layout = item.layout()
                if layout:
                    for j in range(layout.count()):
                        widget = layout.itemAt(j).widget()
                        if widget and hasattr(widget, "text"):
                            if "Configure Y-Axis Ranges" in widget.text():
                                found_button = True
                                break

        assert found_button


class TestMemoryManagement:
    """Test memory management and cleanup."""

    def test_old_widget_deleted_on_linac_switch(self, display):
        """Test that old widget is properly deleted."""
        initial_widget = display.current_linac_widget
        initial_widget_id = id(initial_widget)

        # Switch linac
        display.linac_combo.setCurrentIndex(1)

        # New widget should have different id
        new_widget_id = id(display.current_linac_widget)
        assert new_widget_id != initial_widget_id

    def test_plot_references_cleared_on_switch(self, display):
        """Test that plot references are cleared when switching."""
        initial_count = len(display.cryomodule_plots)

        # Switch linac
        display.linac_combo.setCurrentIndex(1)

        # Plot count should change (new linac has different number of CMs)
        new_count = len(display.cryomodule_plots)
        assert (
            new_count != initial_count or initial_count == 4
        )  # L0B->L1B both happen to have different counts


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
