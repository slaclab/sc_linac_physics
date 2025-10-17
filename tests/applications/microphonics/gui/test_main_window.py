import gc
from unittest.mock import Mock, patch, MagicMock

import pytest
from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtGui import QCloseEvent
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QWidget

from sc_linac_physics.applications.microphonics.gui.async_data_manager import (
    MeasurementConfig,
)
from sc_linac_physics.applications.microphonics.gui.main_window import (
    MicrophonicsGUI,
)


# Create a signal emitter class for testing
class SignalEmitter(QObject):
    dataLoaded = pyqtSignal(dict)
    loadError = pyqtSignal(str)


# Single QApplication instance for all tests
@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


class MockWidget(QWidget):
    """Base mock widget that can be added to layouts"""

    def __init__(self):
        super().__init__()
        self.mock = Mock()

    def __getattr__(self, name):
        return getattr(self.mock, name)


@pytest.fixture
def gui(qapp):
    """Create a fresh MicrophonicsGUI instance for each test."""
    with (
        patch(
            "sc_linac_physics.applications.microphonics.gui.main_window.AsyncDataManager"
        ) as mock_manager,
        patch(
            "sc_linac_physics.applications.microphonics.gui.main_window.StatisticsCalculator"
        ) as mock_stats,
        patch(
            "sc_linac_physics.applications.microphonics.gui.main_window.PlotPanel",
            return_value=MockWidget(),
        ) as mock_plot,
        patch(
            "sc_linac_physics.applications.microphonics.gui.main_window.StatusPanel",
            return_value=MockWidget(),
        ) as mock_status,
        patch(
            "sc_linac_physics.applications.microphonics.gui.main_window.ConfigPanel",
            return_value=MockWidget(),
        ) as mock_config,
        patch(
            "sc_linac_physics.applications.microphonics.gui.main_window.ChannelSelectionGroup",
            return_value=MockWidget(),
        ) as mock_channel,
        patch(
            "sc_linac_physics.applications.microphonics.gui.main_window.DataLoadingGroup",
            return_value=MockWidget(),
        ) as mock_data,
    ):
        # Create MicrophonicsGUI instance
        window = MicrophonicsGUI()
        window.show()
        QTest.qWaitForWindowExposed(window)

        # Store mock references for test access
        window._mocks = {
            "manager": mock_manager,
            "stats": mock_stats,
            "plot": mock_plot,
            "status": mock_status,
            "config": mock_config,
            "channel": mock_channel,
            "data": mock_data,
        }

        yield window

        # Cleanup
        window.close()
        window.deleteLater()
        QTest.qWait(1)
        gc.collect()


@pytest.fixture
def mock_data_manager():
    """Create a mock AsyncDataManager."""
    with patch(
        "sc_linac_physics.applications.microphonics.gui.main_window.AsyncDataManager"
    ) as mock:
        manager = Mock()
        mock.return_value = manager
        yield manager


@pytest.fixture
def mock_stats_calculator():
    """Create a mock StatisticsCalculator."""
    with patch(
        "sc_linac_physics.applications.microphonics.gui.main_window.StatisticsCalculator"
    ) as mock:
        calculator = Mock()
        mock.return_value = calculator
        yield calculator


def test_gui_initialization(gui):
    """Test basic GUI initialization."""
    assert gui.windowTitle() == "LCLS-II Microphonics Measurement"
    assert gui.minimumSize().width() == 1200
    assert gui.minimumSize().height() == 800
    assert not gui.measurement_running

    # Check that all required panels are mocked and initialized
    for panel in [
        "config_panel",
        "status_panel",
        "plot_panel",
        "channel_selection",
        "data_loading",
    ]:
        assert hasattr(gui, panel)
        assert getattr(gui, panel) is not None


def test_config_changed_handling(gui):
    """Test handling of configuration changes."""
    # Create a test configuration
    test_config = {
        "cavities": {1: True, 2: False, 3: True, 4: False},
        "linac": "L0B",
        "modules": [],
        "decimation": 2,
        "buffer_count": 1,
    }

    # Trigger config changed
    gui.on_config_changed(test_config)
    QTest.qWait(100)  # Give time for event processing

    # Verify status panel updates for active cavities
    status_calls = gui.status_panel.mock.update_cavity_status.call_args_list
    assert (
        len(status_calls) >= 2
    )  # Should be called at least for cavities 1 and 3
    called_cavities = [args[0][0] for args in status_calls]
    assert 1 in called_cavities
    assert 3 in called_cavities


def test_measurement_start_stop(gui):
    """Test measurement start and stop functionality."""
    # Setup mock configuration
    mock_config = {
        "cavities": {1: True, 2: False},
        "linac": "L0B",
        "modules": [{"base_channel": "ACCL:L0B:0100"}],
        "decimation": 2,
        "buffer_count": 1,
    }
    gui.config_panel.mock.get_config.return_value = mock_config

    # Mock channel selection
    gui.channel_selection.mock.get_selected_channels.return_value = [
        "DF",
        "FWD",
    ]

    # Start measurement
    gui.start_measurement()
    QTest.qWait(100)  # Give time for async operations

    # Verify state changes
    assert gui.measurement_running
    assert not gui.channel_selection.isEnabled()
    assert not gui.data_loading.isEnabled()

    # Verify data manager was called correctly
    expected_config = {
        "ACCL:L0B:0100:RESA": {
            "pv_base": "ca://ACCL:L0B:0100:RESA:",
            "config": MeasurementConfig(
                channels=["DF", "FWD"], decimation=2, buffer_count=1
            ),
            "cavities": [1],
        }
    }
    gui.data_manager.initiate_measurement.assert_called_with(expected_config)

    # Stop measurement
    gui.stop_measurement()
    QTest.qWait(100)  # Give time for cleanup

    # Verify final state
    assert not gui.measurement_running
    assert gui.channel_selection.isEnabled()
    assert gui.data_loading.isEnabled()
    gui.data_manager.stop_all.assert_called_once()


@pytest.fixture
def temp_data_file(tmp_path):
    """Create a temporary HDF5 file for testing."""
    test_file = tmp_path / "test_data.h5"
    test_file.touch()  # Create empty file
    return test_file


def test_data_loading_success(gui, temp_data_file):
    """Test successful data loading functionality."""
    # Setup mock data and statistics
    mock_df_data = Mock()
    mock_df_data.size = 100  # Simulate non-empty data
    mock_stats = {"rms": 1.0, "peak": 2.0}

    test_data = {"cavity_list": [1], "cavities": {1: {"DF": mock_df_data}}}

    # Configure mocks
    gui.stats_calculator = Mock()
    gui.stats_calculator.calculate_statistics.return_value = mock_stats
    gui.stats_calculator.convert_to_panel_format.return_value = mock_stats
    gui.status_panel = Mock()
    gui.message_box = Mock()

    # Configure data loader with success case
    gui.data_loader = Mock()
    gui.data_loader.load_file = Mock(return_value=test_data)

    # Test successful loading
    gui.load_data(temp_data_file)

    # Verify file loading
    gui.data_loader.load_file.assert_called_once_with(temp_data_file)

    # Call data handler directly since we're mocking the whole data_loader
    gui._handle_new_data("file", test_data)

    # Verify successful handling
    gui.stats_calculator.calculate_statistics.assert_called_with(mock_df_data)
    gui.status_panel.update_statistics.assert_called_once_with(1, mock_stats)
    assert gui.data_loading.isEnabled()


def test_data_loading_error(gui, temp_data_file):
    """Test error handling in data loading."""
    # Setup error case
    error_msg = "Test error"

    # Configure mocks
    gui.data_loader = Mock()
    gui._show_error_dialog = Mock()  # Mock the error dialog method
    gui.data_loading = Mock()

    # Configure error case
    def raise_error(*args):
        raise Exception(error_msg)

    gui.data_loader.load_file.side_effect = raise_error

    # Test error handling
    gui.load_data(temp_data_file)

    # Verify error handling
    expected_error = f"Failed to load data: {error_msg}"
    gui._show_error_dialog.assert_called_once_with("Error", expected_error)
    gui.data_loading.update_file_info.assert_called_once_with(
        "Error loading file"
    )

    # Verify file loading was attempted
    gui.data_loader.load_file.assert_called_once_with(temp_data_file)
    assert gui.data_loading.isEnabled()  # GUI should remain responsive


@pytest.mark.parametrize("source", ["measurement", "file"])
def test_handle_new_data(gui, mock_stats_calculator, source):
    """Test handling of new data from different sources."""
    # Create test data with numpy array-like behavior
    mock_df_data = MagicMock()
    mock_df_data.size = 100  # Simulate non-empty data

    test_data = {
        "cavity_list": [1, 2],
        "cavities": {1: {"DF": mock_df_data}, 2: {"DF": mock_df_data}},
    }

    # Mock statistics calculation
    mock_stats = {"rms": 1.0, "peak": 2.0}
    gui.stats_calculator.calculate_statistics.return_value = mock_stats
    gui.stats_calculator.convert_to_panel_format.return_value = mock_stats

    # Handle new data
    gui._handle_new_data(source, test_data)

    # Verify statistics calculation
    assert gui.stats_calculator.calculate_statistics.call_count == 2

    # Verify plot updates
    gui.plot_panel.update_plots.assert_called_once_with(test_data)


def test_split_chassis_config(gui):
    """Test chassis configuration splitting."""
    # Create test configuration
    test_config = {
        "cavities": {1: True, 2: True, 5: True, 6: True},
        "modules": [{"base_channel": "ACCL:L0B:0100"}],
        "decimation": 2,
        "buffer_count": 1,
    }

    # Mock channel selection
    gui.channel_selection.get_selected_channels = Mock(
        return_value=["DF", "FWD"]
    )

    # Get split configuration
    result = gui._split_chassis_config(test_config)

    # Verify results
    assert "ACCL:L0B:0100:RESA" in result
    assert "ACCL:L0B:0100:RESB" in result
    assert set(result["ACCL:L0B:0100:RESA"]["cavities"]) == {1, 2}
    assert set(result["ACCL:L0B:0100:RESB"]["cavities"]) == {5, 6}


def test_error_handling(gui):
    """Test error handling and message display."""
    # Test measurement start error
    gui.config_panel.mock.get_config.side_effect = Exception("Test error")
    gui.start_measurement()
    assert not gui.measurement_running

    # Test data processing error
    test_data = {"cavity_list": [1], "cavities": {1: {"DF": None}}}
    gui._handle_new_data("measurement", test_data)
    gui.status_panel.mock.update_cavity_status.assert_called_with(
        1, "Complete", 100, "No DF data for stats"
    )


def test_job_handling(gui):
    """Test job progress and completion handling."""
    # Setup initial state
    gui.measurement_running = True

    # Test handling progress for a specific rack and cavity
    chassis_id = "ACCL:L0B:0100"
    cavity_num = 1
    progress = 50

    # Call progress handler
    gui._handle_progress(chassis_id, cavity_num, progress)

    # Verify status update
    gui.status_panel.mock.update_cavity_status.assert_called_with(
        cavity_num, "Running", progress, "Buffer acquisition: 50%"
    )

    # Test completion
    test_data = {"cavity_list": [1], "cavities": {1: {"DF": MagicMock()}}}
    gui._handle_job_complete(test_data)
    assert not gui.measurement_running
    assert gui.channel_selection.isEnabled()
    assert gui.data_loading.isEnabled()


def test_cleanup(gui, mock_data_manager):
    """Test cleanup on window close."""
    # Ensure data_manager is set
    gui.data_manager = mock_data_manager

    # Create a close event
    close_event = QCloseEvent()

    # Trigger the close event
    gui.closeEvent(close_event)

    # Verify cleanup operations
    mock_data_manager.stop_all.assert_called_once()
