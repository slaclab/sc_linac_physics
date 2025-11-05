import sys
from unittest.mock import Mock, patch

import pytest
from qtpy.QtWidgets import QApplication

from sc_linac_physics.displays.plot.plot import PVGroupArchiverDisplay
from sc_linac_physics.displays.plot.utils import (
    HierarchicalPVs,
    MachinePVs,
    LinacPVs,
    CryomodulePVs,
    RackPVs,
    CavityPVs,
    PVGroup,
)


@pytest.fixture(scope="session")
def qapp():
    """Create QApplication instance for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app
    # Don't quit the app here as it might be used by other tests


@pytest.fixture
def mock_machine():
    """Create a mock Machine object."""
    machine = Mock()
    machine.global_heater_feedback_pv = "CHTR:CM00:0:HTR_POWER_TOT"
    return machine


@pytest.fixture
def mock_pv_groups():
    """Create mock hierarchical PV groups."""
    pv_groups = HierarchicalPVs()

    # Machine PVs
    pv_groups.machine = MachinePVs()
    pv_groups.machine.pvs.pvs[("Machine", "global_heater_feedback_pv")] = [
        "CHTR:CM00:0:HTR_POWER_TOT"
    ]

    # Linac PVs
    for linac_name in ["L0B", "L1B", "L2B", "L3B"]:
        linac_pvs = LinacPVs(name=linac_name, pvs=PVGroup())
        linac_pvs.pvs.pvs[("Linac", "beamline_vacuum_pvs")] = [
            f"VGXX:{linac_name}:0198:COMBO_P"
        ]
        linac_pvs.pvs.pvs[("Linac", "aact_mean_sum_pv")] = [
            f"ACCL:{linac_name}:AACTMEANSUM"
        ]
        pv_groups.linacs[linac_name] = linac_pvs

    # Cryomodule PVs
    cm_pvs = CryomodulePVs(name="02", linac_name="L1B", pvs=PVGroup())
    cm_pvs.pvs.pvs[("Cryomodule", "ds_level_pv")] = ["CLL:CM02:2301:DS:LVL"]
    cm_pvs.pvs.pvs[("Cryomodule", "aact_mean_sum_pv")] = [
        "ACCL:L1B:02:AACTMEANSUM"
    ]
    pv_groups.cryomodules["02"] = cm_pvs

    # Rack PVs
    rack_pvs = RackPVs(
        rack_name="A", cryomodule_name="02", linac_name="L1B", pvs=PVGroup()
    )
    rack_pvs.pvs.pvs[("Cavity", "ades_pv")] = [
        "ACCL:L1B:0210:ADES",
        "ACCL:L1B:0220:ADES",
        "ACCL:L1B:0230:ADES",
        "ACCL:L1B:0240:ADES",
    ]
    pv_groups.racks[("02", "A")] = rack_pvs

    # Cavity PVs
    cavity_pvs = CavityPVs(
        number=1,
        rack_name="A",
        cryomodule_name="02",
        linac_name="L1B",
        pvs=PVGroup(),
    )
    cavity_pvs.pvs.pvs[("Cavity", "ades_pv")] = ["ACCL:L1B:0210:ADES"]
    cavity_pvs.pvs.pvs[("Cavity", "acon_pv")] = ["ACCL:L1B:0210:ACON"]
    cavity_pvs.pvs.pvs[("SSA", "status_pv")] = ["ACCL:L1B:0210:SSA_STATUS"]
    pv_groups.cavities[("02", 1)] = cavity_pvs

    return pv_groups


@pytest.fixture
def display(qapp, mock_machine, mock_pv_groups):
    """Create PVGroupArchiverDisplay instance with mocked data."""
    with (
        patch("sc_linac_physics.displays.plot.plot.Machine") as MockMachine,
        patch(
            "sc_linac_physics.displays.plot.plot.get_pvs_all_groupings"
        ) as mock_get_pvs,
    ):

        MockMachine.return_value = mock_machine
        mock_get_pvs.return_value = mock_pv_groups

        display = PVGroupArchiverDisplay()
        yield display
        display.close()


class TestPVGroupArchiverDisplayInitialization:
    """Test display initialization."""

    def test_display_creation(self, display):
        """Test that display is created successfully."""
        assert display is not None
        assert hasattr(display, "machine")
        assert hasattr(display, "pv_groups")
        assert hasattr(display, "plotted_pvs")

    def test_ui_components_exist(self, display):
        """Test that all UI components are created."""
        assert display.level_combo is not None
        assert display.object_combo is not None
        assert display.pv_type_list is not None
        assert display.filter_edit is not None
        assert display.plotted_list is not None
        assert display.time_plot is not None

    def test_initial_level_is_machine(self, display):
        """Test that initial level is Machine."""
        assert display.level_combo.currentText() == "Machine"

    def test_plotted_pvs_initially_empty(self, display):
        """Test that plotted PVs dict is initially empty."""
        assert len(display.plotted_pvs) == 0
        assert display.plotted_list.count() == 0


class TestHierarchyLevelSelection:
    """Test hierarchy level selection functionality."""

    def test_machine_level_populates_pvs(self, display):
        """Test that selecting Machine level populates PV types."""
        display.level_combo.setCurrentText("Machine")
        assert display.pv_type_list.count() > 0

    def test_linac_level_populates_objects(self, display):
        """Test that selecting Linac level populates linac objects."""
        display.level_combo.setCurrentText("Linac")
        assert display.object_combo.count() == 4  # L0B, L1B, L2B, L3B

    def test_cryomodule_level_populates_objects(self, display):
        """Test that selecting Cryomodule level populates cryomodule objects."""
        display.level_combo.setCurrentText("Cryomodule")
        assert display.object_combo.count() > 0

    def test_rack_level_populates_objects(self, display):
        """Test that selecting Rack level populates rack objects."""
        display.level_combo.setCurrentText("Rack")
        assert display.object_combo.count() > 0
        # Check format "CM## Rack X"
        if display.object_combo.count() > 0:
            assert "CM" in display.object_combo.itemText(0)
            assert "Rack" in display.object_combo.itemText(0)

    def test_cavity_level_populates_objects(self, display):
        """Test that selecting Cavity level populates cavity objects."""
        display.level_combo.setCurrentText("Cavity")
        assert display.object_combo.count() > 0
        # Check format "CM## Cavity #"
        if display.object_combo.count() > 0:
            assert "CM" in display.object_combo.itemText(0)
            assert "Cavity" in display.object_combo.itemText(0)


class TestPVTypeListPopulation:
    """Test PV type list population."""

    def test_machine_pvs_shown_with_source(self, display):
        """Test that Machine PVs are shown with source level."""
        display.level_combo.setCurrentText("Machine")

        # Find the machine PV
        found = False
        for i in range(display.pv_type_list.count()):
            item_text = display.pv_type_list.item(i).text()
            if (
                "Machine" in item_text
                and "global_heater_feedback_pv" in item_text
            ):
                found = True
                break
        assert found, "Machine-level PV not found in list"

    def test_linac_pvs_shown_with_source(self, display):
        """Test that Linac PVs are shown with source level."""
        display.level_combo.setCurrentText("Linac")
        display.object_combo.setCurrentText("L0B")

        # Check that PVs are shown with [Linac] prefix
        found_linac_pv = False
        for i in range(display.pv_type_list.count()):
            item_text = display.pv_type_list.item(i).text()
            if "[Linac]" in item_text:
                found_linac_pv = True
                break
        assert found_linac_pv, "Linac-level PV not found with correct prefix"

    def test_pv_count_shown_in_list(self, display):
        """Test that PV count is shown in the list."""
        display.level_combo.setCurrentText("Rack")
        if display.object_combo.count() > 0:
            display.object_combo.setCurrentIndex(0)

            # Check that count is shown (e.g., "(4 PVs)")
            if display.pv_type_list.count() > 0:
                item_text = display.pv_type_list.item(0).text()
                assert "PV" in item_text


class TestPVTypeFiltering:
    """Test PV type filtering functionality."""

    def test_filter_hides_non_matching_items(self, display):
        """Test that filtering hides non-matching items."""
        display.level_combo.setCurrentText("Cavity")
        if display.object_combo.count() > 0:
            display.object_combo.setCurrentIndex(0)

            initial_count = display.pv_type_list.count()
            if initial_count > 0:
                # Apply filter
                display.filter_edit.setText("ades")

                # Count visible items
                visible_count = sum(
                    1
                    for i in range(display.pv_type_list.count())
                    if not display.pv_type_list.item(i).isHidden()
                )

                # Should have fewer or equal visible items
                assert visible_count <= initial_count

    def test_filter_clear_shows_all_items(self, display):
        """Test that clearing filter shows all items."""
        display.level_combo.setCurrentText("Linac")
        display.object_combo.setCurrentText("L0B")

        initial_count = display.pv_type_list.count()

        # Apply then clear filter
        display.filter_edit.setText("ades")
        display.filter_edit.clear()

        # Count visible items
        visible_count = sum(
            1
            for i in range(display.pv_type_list.count())
            if not display.pv_type_list.item(i).isHidden()
        )

        assert visible_count == initial_count


class TestPVSelection:
    """Test PV selection functionality."""

    def test_select_all_selects_all_visible(self, display):
        """Test that Select All selects all visible items."""
        display.level_combo.setCurrentText("Linac")
        display.object_combo.setCurrentText("L0B")

        display.select_all_pv_types()

        selected_count = len(display.pv_type_list.selectedItems())
        visible_count = sum(
            1
            for i in range(display.pv_type_list.count())
            if not display.pv_type_list.item(i).isHidden()
        )

        assert selected_count == visible_count

    def test_select_none_clears_selection(self, display):
        """Test that Select None clears all selections."""
        display.level_combo.setCurrentText("Linac")
        display.object_combo.setCurrentText("L0B")

        display.select_all_pv_types()
        display.select_no_pv_types()

        assert len(display.pv_type_list.selectedItems()) == 0


class TestAddRemovePVs:
    """Test adding and removing PVs from plot."""

    def test_add_pvs_to_plot(self, display):
        """Test adding PVs to the plot."""
        display.level_combo.setCurrentText("Cavity")
        if display.object_combo.count() > 0:
            display.object_combo.setCurrentIndex(0)

            if display.pv_type_list.count() > 0:
                # Select first item
                display.pv_type_list.item(0).setSelected(True)

                initial_count = len(display.plotted_pvs)
                display.add_selected_pvs()

                assert len(display.plotted_pvs) > initial_count

    def test_add_pvs_updates_plotted_list(self, display):
        """Test that adding PVs updates the plotted list."""
        display.level_combo.setCurrentText("Cavity")
        if display.object_combo.count() > 0:
            display.object_combo.setCurrentIndex(0)

            if display.pv_type_list.count() > 0:
                display.pv_type_list.item(0).setSelected(True)

                initial_list_count = display.plotted_list.count()
                display.add_selected_pvs()

                assert display.plotted_list.count() > initial_list_count

    def test_remove_pvs_from_plot(self, display):
        """Test removing PVs from the plot."""
        # First add a PV
        display.level_combo.setCurrentText("Cavity")
        if display.object_combo.count() > 0:
            display.object_combo.setCurrentIndex(0)

            if display.pv_type_list.count() > 0:
                display.pv_type_list.item(0).setSelected(True)
                display.add_selected_pvs()

                # Now remove it
                if display.plotted_list.count() > 0:
                    display.plotted_list.item(0).setSelected(True)
                    initial_count = len(display.plotted_pvs)
                    display.remove_selected_pvs()

                    assert len(display.plotted_pvs) < initial_count

    def test_clear_all_pvs(self, display):
        """Test clearing all PVs from the plot."""
        # Add some PVs
        display.level_combo.setCurrentText("Cavity ")
        if display.object_combo.count() > 0:
            display.object_combo.setCurrentIndex(0)

            if display.pv_type_list.count() > 0:
                display.select_all_pv_types()
                display.add_selected_pvs()

                # Clear all
                display.clear_all_pvs()

                assert len(display.plotted_pvs) == 0
                assert display.plotted_list.count() == 0


class TestRainbowColors:
    """Test rainbow color generation."""

    def test_rainbow_color_generation(self, display):
        """Test that rainbow colors are generated correctly."""
        # Simulate having 10 PVs plotted
        for i in range(10):
            display.plotted_pvs[f"TEST:PV:{i}"] = True

        colors = [display._get_rainbow_color(i) for i in range(10)]

        # All colors should be unique (compare RGB values instead of QColor objects)
        rgb_values = [(c.red(), c.green(), c.blue()) for c in colors]
        assert len(set(rgb_values)) == len(
            rgb_values
        ), "Colors should be unique"

        # Colors should be valid QColors
        for color in colors:
            assert color.isValid()

    def test_rainbow_colors_span_spectrum(self, display):
        """Test that colors span the spectrum."""
        num_colors = 10

        # Simulate having PVs plotted
        for i in range(num_colors):
            display.plotted_pvs[f"TEST:PV:{i}"] = True

        colors = [display._get_rainbow_color(i) for i in range(num_colors)]

        # Check that we have variety in RGB values
        rgb_values = [(c.red(), c.green(), c.blue()) for c in colors]

        # Calculate color diversity by checking variance in each channel
        reds = [rgb[0] for rgb in rgb_values]
        greens = [rgb[1] for rgb in rgb_values]
        blues = [rgb[2] for rgb in rgb_values]

        # At least one channel should have significant variation
        red_range = max(reds) - min(reds)
        green_range = max(greens) - min(greens)
        blue_range = max(blues) - min(blues)

        # At least one channel should vary by more than 100 (out of 255)
        max_variation = max(red_range, green_range, blue_range)
        assert (
            max_variation > 100
        ), f"Colors should span spectrum, got max variation: {max_variation}"


class TestLegendControl:
    """Test legend control functionality."""

    def test_legend_initially_shown(self, display):
        """Test that legend is initially shown."""
        assert display.show_legend_check.isChecked()

    def test_legend_toggle(self, display):
        """Test toggling legend visibility."""
        # Test checkbox state changes
        initial_state = display.show_legend_check.isChecked()
        assert initial_state is True

        # Toggle off
        display.show_legend_check.setChecked(False)
        assert display.show_legend_check.isChecked() is False

        # Toggle back on
        display.show_legend_check.setChecked(True)
        assert display.show_legend_check.isChecked() is True


class TestPlotRegeneration:
    """Test plot regeneration functionality."""

    def test_regenerate_plot_called_on_add(self, display):
        """Test that plot is regenerated when PVs are added."""
        with patch.object(display, "_regenerate_plot") as mock_regen:
            display.level_combo.setCurrentText("Cavity")
            if display.object_combo.count() > 0:
                display.object_combo.setCurrentIndex(0)

                if display.pv_type_list.count() > 0:
                    display.pv_type_list.item(0).setSelected(True)
                    display.add_selected_pvs()

                    assert mock_regen.called

    def test_regenerate_plot_called_on_remove(self, display):
        """Test that plot is regenerated when PVs are removed."""
        # First add a PV
        display.level_combo.setCurrentText("Cavity")
        if display.object_combo.count() > 0:
            display.object_combo.setCurrentIndex(0)

            if display.pv_type_list.count() > 0:
                display.pv_type_list.item(0).setSelected(True)
                display.add_selected_pvs()

                # Now test remove
                with patch.object(display, "_regenerate_plot") as mock_regen:
                    if display.plotted_list.count() > 0:
                        display.plotted_list.item(0).setSelected(True)
                        display.remove_selected_pvs()

                        assert mock_regen.called


class TestInfoLabel:
    """Test info label updates."""

    def test_info_label_updates_on_add(self, display):
        """Test that info label updates when PVs are added."""
        display.level_combo.setCurrentText("Cavity")
        if display.object_combo.count() > 0:
            display.object_combo.setCurrentIndex(0)

            if display.pv_type_list.count() > 0:
                display.pv_type_list.item(0).setSelected(True)
                display.add_selected_pvs()

                # Check that label is updated
                assert display.info_label.text() != "0 PVs plotted"

    def test_info_label_shows_correct_count(self, display):
        """Test that info label shows correct PV count."""
        display.clear_all_pvs()
        assert "0 PV" in display.info_label.text()


class TestTimeRangeControl:
    """Test time range control functionality."""

    def test_time_range_options_available(self, display):
        """Test that time range options are available."""
        assert display.time_range_combo.count() > 0

    def test_time_range_change_updates_plot(self, display):
        """Test that changing time range updates the plot."""
        with patch.object(display.time_plot, "setTimeSpan") as mock_set_time:
            display.time_range_combo.setCurrentText("1 hour")
            display.on_time_range_changed("1 hour")

            mock_set_time.assert_called_once_with(3600)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
