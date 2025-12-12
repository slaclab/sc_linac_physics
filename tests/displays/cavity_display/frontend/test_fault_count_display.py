# "test_fault_count_display.py"
import sys
from datetime import datetime
from unittest.mock import Mock, patch

import pytest
from PyQt5.QtWidgets import QApplication

from sc_linac_physics.displays.cavity_display.backend.fault import FaultCounter
from sc_linac_physics.displays.cavity_display.frontend.fault_count_display import (
    FaultCountDisplay,
)


# Fixtures
@pytest.fixture(scope="session")
def qapp():
    """Create QApplication instance for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


@pytest.fixture
def mock_machine():
    """Mock the BackendMachine with basic structure."""
    with patch(
        "sc_linac_physics.displays.cavity_display.frontend.fault_count_display.BackendMachine"
    ) as mock:
        machine = Mock()
        cavity = Mock()
        cavity.cryomodule = "01"
        cavity.number = 1
        cavity.get_fault_counts = Mock(return_value={})

        cm = Mock()
        cm.cavities = {1: cavity}
        machine.cryomodules = {"01": cm}
        mock.return_value = machine
        yield mock


@pytest.fixture
def display(qapp, mock_machine):
    """Create display instance."""
    disp = FaultCountDisplay(lazy_fault_pvs=True)
    yield disp
    disp.close()


# Basic Initialization Tests
class TestInitialization:
    def test_window_title(self, display):
        assert display.windowTitle() == "Fault Count Display"

    def test_combo_boxes_populated(self, display):
        assert display.cm_combo_box.count() > 0
        assert display.cav_combo_box.count() == 9  # "" + 1-8
        assert display.hide_fault_combo_box.count() > 1

    def test_fault_list_created(self, display):
        """Test that fault list is populated from actual CSV."""
        # Use actual fault codes from the CSV
        assert "BCS" in display.fault_tlc_list
        assert "SSA" in display.fault_tlc_list
        assert "PPS" in display.fault_tlc_list
        # Test it's sorted and unique
        assert display.fault_tlc_list == sorted(display.fault_tlc_list)
        assert len(display.fault_tlc_list) == len(set(display.fault_tlc_list))

    def test_datetime_range_valid(self, display):
        start = display.start_selector.dateTime()
        end = display.end_selector.dateTime()
        assert start < end


# Cavity Selection Tests
class TestCavitySelection:
    def test_update_cavity_requires_both_selections(self, display):
        """Should not update if CM or cavity not selected."""
        display.cm_combo_box.setCurrentIndex(0)
        display.update_cavity()
        assert display.cavity is None

        display.cm_combo_box.setCurrentText("01")
        display.cav_combo_box.setCurrentIndex(0)
        display.update_cavity()
        assert display.cavity is None

    def test_valid_cavity_selection(self, display):
        """Should set cavity when both selections valid."""
        display.cm_combo_box.setCurrentText("01")
        display.cav_combo_box.setCurrentText("1")

        with patch.object(display, "update_plot"):
            display.update_cavity()
            assert display.cavity is not None
            assert display.cavity.cryomodule == "01"
            assert display.cavity.number == 1


# Data Processing Tests
class TestDataProcessing:
    @pytest.fixture
    def cavity_with_data(self):
        """Create mock cavity with sample fault data using real fault codes."""
        cavity = Mock()
        cavity.cryomodule = "01"
        cavity.number = 1
        cavity.get_fault_counts = Mock(
            return_value={
                "BCS": FaultCounter(
                    alarm_count=5, ok_count=10, invalid_count=2, warning_count=1
                ),
                "SSA": FaultCounter(
                    alarm_count=3, ok_count=15, invalid_count=1, warning_count=2
                ),
            }
        )
        return cavity

    def test_get_data_processes_counters(self, display, cavity_with_data):
        """Should extract data from FaultCounters correctly."""
        display.cavity = cavity_with_data
        display.get_data()

        assert len(display.y_data) == 2
        assert display.num_faults == [5, 3]
        assert display.num_invalids == [2, 1]
        assert display.num_warnings == [1, 2]

    def test_get_data_calls_cavity_method(self, display, cavity_with_data):
        """Should call get_fault_counts with datetime range."""
        display.cavity = cavity_with_data
        display.get_data()

        args = cavity_with_data.get_fault_counts.call_args[0]
        assert len(args) == 2
        assert all(isinstance(arg, datetime) for arg in args)

    def test_fault_filtering(self, display, cavity_with_data):
        """Should filter out selected fault type."""
        display.cavity = cavity_with_data
        display.hide_fault_combo_box.setCurrentText("BCS")
        display.get_data()

        assert "BCS" not in display.y_data
        assert "SSA" in display.y_data
        assert len(display.y_data) == 1

    def test_data_reset_on_get(self, display, cavity_with_data):
        """Should clear old data when getting new data."""
        display.cavity = cavity_with_data
        display.num_faults = [99, 88]

        display.get_data()

        assert display.num_faults != [99, 88]
        assert len(display.num_faults) == 2

    def test_empty_data_handling(self, display):
        """Should handle empty fault data."""
        display.cavity = Mock()
        display.cavity.get_fault_counts = Mock(return_value={})

        display.get_data()

        assert display.y_data == []
        assert display.num_faults == []


# Plot Update Tests
class TestPlotUpdates:
    def test_update_plot_requires_cavity(self, display):
        """Should return early if no cavity selected."""
        display.cavity = None

        with patch.object(display.plot_window, "clear") as mock_clear:
            display.update_plot()
            mock_clear.assert_not_called()

    def test_update_plot_clears_and_gets_data(self, display):
        """Should clear plot and get fresh data."""
        display.cavity = Mock()
        display.cavity.cryomodule = "01"
        display.cavity.number = 1
        display.cavity.get_fault_counts = Mock(
            return_value={
                "BCS": FaultCounter(
                    alarm_count=5, ok_count=10, invalid_count=2, warning_count=1
                ),
            }
        )

        with patch.object(display.plot_window, "clear") as mock_clear:
            with patch.object(display.plot_window, "addItem"):
                display.update_plot()
                mock_clear.assert_called_once()
                assert display.y_data is not None
                assert len(display.y_data) == 1

    def test_creates_three_bar_graphs(self, display):
        """Should create bars for faults, invalids, and warnings."""
        display.cavity = Mock()
        display.cavity.cryomodule = "01"
        display.cavity.number = 1
        display.cavity.get_fault_counts = Mock(
            return_value={
                "BCS": FaultCounter(
                    alarm_count=5, ok_count=10, invalid_count=2, warning_count=1
                ),
            }
        )

        with patch.object(display.plot_window, "addItem") as mock_add:
            display.update_plot()
            assert mock_add.call_count == 3

    def test_bar_colors_correct(self, display):
        """Should use correct colors for each bar type."""
        from sc_linac_physics.displays.cavity_display.frontend.cavity_widget import (
            RED_FILL_COLOR,
            PURPLE_FILL_COLOR,
            YELLOW_FILL_COLOR,
        )

        display.cavity = Mock()
        display.cavity.cryomodule = "01"
        display.cavity.number = 1
        display.cavity.get_fault_counts = Mock(
            return_value={
                "BCS": FaultCounter(
                    alarm_count=5, ok_count=10, invalid_count=2, warning_count=1
                ),
            }
        )

        with (
            patch(
                "sc_linac_physics.displays.cavity_display.frontend.fault_count_display.pg.BarGraphItem"
            ) as mock_bar,
            patch.object(display.plot_window, "addItem"),
        ):

            display.update_plot()

            calls = mock_bar.call_args_list
            assert len(calls) == 3
            assert calls[0][1]["brush"] == RED_FILL_COLOR
            assert calls[1][1]["brush"] == PURPLE_FILL_COLOR
            assert calls[2][1]["brush"] == YELLOW_FILL_COLOR

    def test_stacked_bar_positioning(self, display):
        """Should stack bars correctly."""
        display.cavity = Mock()
        display.cavity.cryomodule = "01"
        display.cavity.number = 1
        display.cavity.get_fault_counts = Mock(
            return_value={
                "BCS": FaultCounter(
                    alarm_count=5, ok_count=10, invalid_count=3, warning_count=2
                ),
            }
        )

        with (
            patch(
                "sc_linac_physics.displays.cavity_display.frontend.fault_count_display.pg.BarGraphItem"
            ) as mock_bar,
            patch.object(display.plot_window, "addItem"),
        ):

            display.update_plot()

            calls = mock_bar.call_args_list
            assert calls[0][1]["x0"] == 0
            assert calls[1][1]["x0"] == [5]
            assert calls[2][1]["x0"] == [8]


# Integration Tests
class TestIntegration:
    def test_full_workflow(self, display):
        """Test complete user workflow."""
        cavity = Mock()
        cavity.cryomodule = "01"
        cavity.number = 1
        cavity.get_fault_counts = Mock(
            return_value={
                "BCS": FaultCounter(
                    alarm_count=5, ok_count=10, invalid_count=2, warning_count=1
                ),
                "SSA": FaultCounter(
                    alarm_count=3, ok_count=15, invalid_count=1, warning_count=2
                ),
            }
        )
        display.machine.cryomodules["01"].cavities[1] = cavity

        display.cm_combo_box.setCurrentText("01")
        display.cav_combo_box.setCurrentText("1")
        display.update_cavity()

        with patch.object(display.plot_window, "addItem"):
            display.update_plot()

        assert len(display.y_data) == 2
        assert display.num_faults == [5, 3]

    def test_workflow_with_filtering(self, display):
        """Test workflow with fault filtering."""
        cavity = Mock()
        cavity.cryomodule = "01"
        cavity.number = 1
        cavity.get_fault_counts = Mock(
            return_value={
                "BCS": FaultCounter(
                    alarm_count=5, ok_count=10, invalid_count=2, warning_count=1
                ),
                "SSA": FaultCounter(
                    alarm_count=3, ok_count=15, invalid_count=1, warning_count=2
                ),
            }
        )
        display.cavity = cavity

        # Filter BCS
        display.hide_fault_combo_box.setCurrentText("BCS")

        with patch.object(display.plot_window, "addItem"):
            display.update_plot()

        assert "BCS" not in display.y_data
        assert "SSA" in display.y_data


# Parameterized Tests
@pytest.mark.parametrize(
    "fault_counts,expected_totals",
    [
        ({"BCS": FaultCounter(5, 10, 2, 1)}, ([5], [2], [1])),
        (
            {
                "BCS": FaultCounter(5, 10, 2, 1),
                "SSA": FaultCounter(3, 15, 1, 2),
            },
            ([5, 3], [2, 1], [1, 2]),
        ),
        ({}, ([], [], [])),
    ],
)
def test_various_fault_data(display, fault_counts, expected_totals):
    """Test processing of various fault data configurations."""
    display.cavity = Mock()
    display.cavity.get_fault_counts = Mock(return_value=fault_counts)

    display.get_data()

    assert display.num_faults == expected_totals[0]
    assert display.num_invalids == expected_totals[1]
    assert display.num_warnings == expected_totals[2]
