import types

import numpy as np
import pytest
from PyQt5.QtCore import Qt, QObject, pyqtSignal, QThread, QTimer
from PyQt5.QtWidgets import QMessageBox

from applications.microphonics.gui.async_data_manager import AsyncDataManager
from applications.microphonics.gui.main_window import MicrophonicsGUI


# Mock DAQ manager that simulates the behavior of real hardware
# Handles data acquisition, error states, and signal emission for testing
class MockDataAcquisitionManager(QObject):
    # Signals for tracking acquisition lifecycle events
    acquisitionProgress = pyqtSignal(str, int, int)
    acquisitionError = pyqtSignal(str, str)
    acquisitionComplete = pyqtSignal(str)
    dataReceived = pyqtSignal(str, dict)

    def __init__(self):
        super().__init__()
        # Tracks ongoing acquisition processes by chassis ID
        self.active_processes = {}

    def start_acquisition(self, chassis_id: str, config: dict):
        """Start acquisition process"""
        try:
            # Make sure we have valid cavities to work with
            cavities = config.get('cavities', [])
            if not cavities:
                raise ValueError("No cavities specified")

            # Prevent selection across CM boundaries -> this causes hardware issues
            low_cm = any(c <= 4 for c in cavities)
            high_cm = any(c > 4 for c in cavities)
            if low_cm and high_cm:
                raise ValueError("ERROR: Cavity selection crosses half-CM")

            # Set up tracking info for this acquisition process
            process_info = {
                'process': True,  # Mock process object
                'output_dir': "/mock/path",
                'filename': f"mock_data_{chassis_id}.dat",
                'decimation': config.get('decimation', 1),
                'last_read': None
            }
            self.active_processes[chassis_id] = process_info

            # Generate and emit mock data for each selected cavity
            for cav in cavities:
                self._emit_cavity_data(chassis_id, cav)
                self.acquisitionProgress.emit(chassis_id, cav, 100)

            # Clean up after successful acquisition
            if chassis_id in self.active_processes:
                del self.active_processes[chassis_id]
            self.acquisitionComplete.emit(chassis_id)

        except Exception as e:
            # Handle failures
            if chassis_id in self.active_processes:
                del self.active_processes[chassis_id]
            self.acquisitionError.emit(chassis_id, str(e))

    def _emit_cavity_data(self, chassis_id: str, cavity_num: int):
        """Emit test data matching production format"""
        # Generate mock values that resemble real cavity measurements
        values = np.array([
            1.34000, 0.24400, -0.36400, -0.95200, -1.41600
        ])
        data = {
            'cavity': cavity_num,
            'channels': {
                'DAC': values.copy(),
                'DF': values.copy()
            }
        }
        self.dataReceived.emit(chassis_id, data)

    def stop_acquisition(self, chassis_id: str):
        """Stop acquisition"""
        # Remove the specified acquisition from tracking
        if chassis_id in self.active_processes:
            del self.active_processes[chassis_id]

    def stop_all(self):
        """Stop all acquisitions"""
        # Clean shutdown of all active processes
        for chassis_id in list(self.active_processes.keys()):
            self.stop_acquisition(chassis_id)


# Test fixture that replaces the real DAQ manager with our mock version
@pytest.fixture
def mock_daq(monkeypatch):
    """Create mock data acquisition manager"""
    mock_manager = MockDataAcquisitionManager()

    def mock_init(self):
        # Initialize base QObject functionality
        super(AsyncDataManager, self).__init__()

        # Set up threading infrastructure
        self.thread = QThread()
        self.data_manager = mock_manager

        # Wire up all the signal handlers
        self.data_manager.acquisitionProgress.connect(self.acquisitionProgress)
        self.data_manager.acquisitionComplete.connect(self.acquisitionComplete)
        self.data_manager.acquisitionError.connect(self.acquisitionError)
        self.data_manager.dataReceived.connect(self.dataReceived)

        # Move DAQ operations to separate thread
        self.data_manager.moveToThread(self.thread)
        self.thread.start()

        # Hook up validation methods
        self._validate_chassis_config = types.MethodType(AsyncDataManager._validate_chassis_config, self)
        self._validate_all_configs = types.MethodType(AsyncDataManager._validate_all_configs, self)

        # Track active acquisitions
        self.active_acquisitions = set()

    monkeypatch.setattr(
        'applications.microphonics.gui.async_data_manager.AsyncDataManager.__init__',
        mock_init
    )
    return mock_manager


# Creates a fresh GUI instance for each test
@pytest.fixture
def gui(qtbot, mock_daq):
    """Setup GUI with mock data manager"""
    gui = MicrophonicsGUI()
    qtbot.addWidget(gui)
    return gui


def test_data_acquisition_flow(qtbot, gui):
    """Test complete acquisition flow matching production script"""
    # Set up the GUI exactly like the production environment
    linac_button = gui.config_panel.linac_buttons["L1B"]
    qtbot.mouseClick(linac_button, Qt.LeftButton)
    qtbot.wait(100)

    module_button = gui.config_panel.cryo_buttons["03"]
    qtbot.mouseClick(module_button, Qt.LeftButton)
    qtbot.wait(100)

    # Select the first 4 cavities -> matches typical production usage
    for cavity in range(1, 5):
        gui.config_panel.cavity_checks_a[cavity].setChecked(True)
        qtbot.wait(50)

    # Configure acquisition parameters to match production values
    gui.config_panel.decim_combo.setCurrentText("1")
    gui.config_panel.buffer_spin.setValue(65)

    # Start acquisition and wait for completion
    with qtbot.waitSignal(
            gui.data_manager.acquisitionComplete,
            timeout=2000
    ) as blocker:
        qtbot.mouseClick(gui.config_panel.start_button, Qt.LeftButton)
        qtbot.wait(300)  # Let events process

    # Verify everything completed successfully
    assert blocker.signal_triggered, "Acquisition complete signal not received"
    assert len(gui.plot_panel.plot_curves) > 0, "No plot curves were created"

    # Check the final state of each cavity
    for cavity in range(1, 5):
        status = gui.status_panel.get_cavity_status(cavity)

        # Make sure nothing errored out
        assert status['status'] != "Error", f"Cavity {cavity} reported error state"
        assert status['progress'] == 100, f"Cavity {cavity} did not complete (progress: {status['progress']})"

        # Verify we got good plot data
        assert cavity in gui.plot_panel.plot_curves, f"Missing plot data for cavity {cavity}"
        plot_data = gui.plot_panel.plot_curves[cavity].getData()
        assert plot_data is not None and len(plot_data[0]) > 0, f"Empty plot data for cavity {cavity}"

    # Check final GUI state
    assert not gui.measurement_running, "Measurement still marked as running after completion"
    assert gui.config_panel.start_button.isEnabled(), "Start button not re-enabled after completion"
    assert not gui.config_panel.stop_button.isEnabled(), "Stop button still enabled after completion"


def test_production_error_cases(qtbot, gui, qapp):
    """Test error handling for invalid configurations"""
    # Set up a valid base configuration first
    linac_button = gui.config_panel.linac_buttons["L1B"]
    qtbot.mouseClick(linac_button, Qt.LeftButton)
    qtbot.wait(100)

    module_button = gui.config_panel.cryo_buttons["03"]
    qtbot.mouseClick(module_button, Qt.LeftButton)
    qtbot.wait(100)

    # Helper to find and close error dialogs
    def close_dialog():
        """Find and close any visible error dialogs"""
        for w in qapp.topLevelWidgets():
            if isinstance(w, QMessageBox) and w.isVisible():
                ok_button = w.button(QMessageBox.Ok)
                ok_button.click()
                return True
        return False

    # Set up automatic dialog closure
    QTimer.singleShot(500, close_dialog)

    # Try to select cavities that cross CM boundary -> should trigger error
    gui.config_panel.cavity_checks_a[1].setChecked(True)
    qtbot.wait(50)
    gui.config_panel.cavity_checks_b[5].setChecked(True)
    qtbot.wait(50)

    # Make sure error dialog appeared and was dealt
    qtbot.waitUntil(close_dialog, timeout=2000)

    # Verify the GUI ended up in the right state
    assert not gui.config_panel.cavity_checks_b[5].isChecked()
    assert gui.config_panel.cavity_checks_a[1].isChecked()

    # Double check the final configuration
    config = gui.config_panel.get_config()
    assert config['cavities'][5] is False
    assert config['cavities'][1] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
