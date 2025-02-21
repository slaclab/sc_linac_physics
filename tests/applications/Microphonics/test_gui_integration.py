import sys
import tempfile
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QApplication

from applications.microphonics.components.components import ChannelSelectionGroup, PlotConfigGroup, StatisticsPanel
from applications.microphonics.gui.config_panel import ConfigPanel
from applications.microphonics.gui.main_window import MicrophonicsGUI

TEST_PLOT_CONFIGS = [
    ("FFT Analysis", "fft_group"),
    ("Histogram", "hist_group"),
    ("Spectrogram", "spec_group")
]


class MockResDataAcq:
    """Mock system that generates synthetic cavity data matching production patterns.
    Simulates DAC/DF signals, noise, and timing structures."""

    def __init__(self, base_path=None):
        """Set up mock system with output directory."""
        if base_path is None:
            self.base_path = Path("mock_microphonics_data")
        else:
            self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def generate_mock_data(self, cavity_nums, buffer_count=65, channels=None):
        """Generate synthetic cavity signals with realistic characteristics.
        Creates sinusoidal signals with noise and DAC/DF correlations."""
        if channels is None:
            channels = ["DAC", "DF"]

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        cavity_str = "_".join(map(str, cavity_nums))
        filename = f"res_CM01_cav{cavity_str}_c{buffer_count}_{timestamp}.dat"
        file_path = self.base_path / filename

        with open(file_path, "w") as f:
            # Add headers and configuration
            f.write(f"# {datetime.now().isoformat()}\n")

            for cavity in cavity_nums:
                f.write(f"# ## Cavity {cavity}\n")
                f.write("# wave_samp_per : 4\n")
                f.write("# wave_shift : 2\n")
                f.write("# chan_keep : 100\n")
                f.write("# chirp_en : 0\n")
                f.write("# chirp_acq_per : 0\n")

            # Add channel information
            channel_pvs = [
                f"ACCL:L3B:{1900 + cavity}:PZT:{ch}:WF"
                for cavity in cavity_nums
                for ch in channels
            ]
            f.write(f"\n# {' '.join(channel_pvs)}\n")
            f.write(f"# First buffer EPICS timestamp {datetime.now().isoformat()}\n#\n")

            # Generate data with proper signal characteristics
            num_points = 100
            for _ in range(buffer_count):
                for i in range(num_points):
                    values = []
                    for cavity in cavity_nums:
                        base = 5 * np.sin(2 * np.pi * i / num_points + cavity)
                        for ch in channels:
                            if ch == "DAC":
                                values.append(base + np.random.normal(0, 0.5))
                            else:  # DF follows DAC
                                values.append(base * 0.8 + np.random.normal(0, 0.3))
                    line = "  ".join(f"{v:8.5f}" for v in values)
                    f.write(f"{line}\n")

        return file_path


@pytest.fixture
def app():
    """Setup QApplication for testing."""
    app = QApplication(sys.argv)
    yield app
    app.quit()


@pytest.fixture
def mock_daq():
    """Create mock DAQ with temp directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield MockResDataAcq(base_path=temp_dir)


@pytest.fixture
def gui(qtbot, mock_daq):
    """Initialize GUI and handle cleanup."""
    gui = MicrophonicsGUI()
    qtbot.addWidget(gui)
    yield gui
    gui.close()
    gui.data_manager.stop_all()
    qtbot.waitUntil(lambda: not gui.data_manager.thread.isRunning(), timeout=5000)


def test_gui_initialization(gui):
    """Check core GUI components and plot widgets."""
    assert gui.plot_panel is not None
    assert gui.config_panel is not None
    assert gui.channel_selection is not None
    assert gui.status_panel is not None

    assert gui.plot_panel.plot_widgets["fft"] is not None
    assert gui.plot_panel.plot_widgets["histogram"] is not None
    assert gui.plot_panel.plot_widgets["time_series"] is not None
    assert gui.plot_panel.plot_widgets["spectrogram"] is not None


def test_cavity_selection(gui, qtbot):
    """Verify cavity selection and config updates."""
    # First set up proper UI state
    linac_button = gui.config_panel.linac_buttons["L1B"]
    qtbot.mouseClick(linac_button, Qt.LeftButton)
    qtbot.wait(100)  # Allow cryo buttons to update

    module_button = gui.config_panel.cryo_buttons["03"]
    qtbot.mouseClick(module_button, Qt.LeftButton)
    qtbot.wait(100)

    # Now select cavities
    cavity_nums = [1, 2]
    for num in cavity_nums:
        gui.config_panel.cavity_checks_a[num].setChecked(True)
        qtbot.wait(50)  # Allow validation

    config = gui.config_panel.get_config()
    assert config["cavities"][1] is True
    assert config["cavities"][2] is True
    assert config["cavities"][3] is False
    assert config["cavities"][4] is False


def test_channel_selection(gui):
    """Test channel selection defaults and visibility."""
    initial_channels = gui.channel_selection.get_selected_channels()
    assert initial_channels == ["DAC", "DF"]
    assert not gui.channel_selection.optional_group.isVisible()


def test_channel_selection_toggle(qtbot):
    widget = ChannelSelectionGroup()
    qtbot.addWidget(widget)
    widget.show()

    # Test toggle with both signal and state waiting
    with qtbot.waitSignal(widget.optional_toggle.stateChanged):
        widget.optional_toggle.setChecked(True)

    def check_visible():
        QApplication.processEvents()
        return widget.optional_group.isVisible()

    qtbot.waitUntil(check_visible, timeout=2000)
    assert widget.optional_group.isVisible()


@pytest.mark.parametrize("plot_type,expected_visible", TEST_PLOT_CONFIGS)
def test_plot_config_visibility(qtbot, plot_type, expected_visible):
    widget = PlotConfigGroup()
    qtbot.addWidget(widget)
    widget.show()
    QApplication.processEvents()  # Ensure initial state is set

    initial_text = widget.plot_type.currentText()

    # Only wait for signal if changing value
    if initial_text != plot_type:
        with qtbot.waitSignal(widget.plot_type.currentTextChanged, timeout=1000):
            widget.plot_type.setCurrentText(plot_type)
    else:
        widget.plot_type.setCurrentText(plot_type)
        widget.update_visible_settings(plot_type)

    # Verify visibility with better error reporting
    target_group = getattr(widget, expected_visible)
    try:
        qtbot.waitUntil(lambda: target_group.isVisible(), timeout=2000)
    except Exception as e:
        print(f"Failed waiting for {expected_visible} to become visible")
        print(f"Current state: {target_group.isVisible()}")
        raise e

    assert target_group.isVisible()


def test_measurement_flow(qtbot, gui, mock_daq, monkeypatch):
    """Test full measurement cycle with mock data."""
    try:
        # Setup measurement
        linac_button = gui.config_panel.linac_buttons["L1B"]
        qtbot.mouseClick(linac_button, Qt.LeftButton)
        qtbot.wait(100)

        module_button = gui.config_panel.cryo_buttons["02"]
        qtbot.mouseClick(module_button, Qt.LeftButton)
        qtbot.wait(100)

        cavity_nums = [1, 2]
        for num in cavity_nums:
            gui.config_panel.cavity_checks_a[num].setChecked(True)

        # Add active_acquisitions to AsyncDataManager bc it doesn't exist
        if not hasattr(gui.data_manager, 'active_acquisitions'):
            gui.data_manager.active_acquisitions = set()

        mock_file = mock_daq.generate_mock_data(
            cavity_nums=cavity_nums, buffer_count=5, channels=["DAC", "DF"]
        )

        signals_received = {'start_called': False, 'signal_count': 0}

        def handle_start_acquisition(chassis_id, config):
            signals_received['start_called'] = True
            gui.data_manager.active_acquisitions.add(chassis_id)
            QTimer.singleShot(50, lambda: gui.data_manager.acquisitionComplete.emit(chassis_id))

        def on_async_complete(chassis_id):
            signals_received['signal_count'] += 1
            if hasattr(gui.data_manager, 'active_acquisitions'):
                gui.data_manager.active_acquisitions.discard(chassis_id)

        # Connect signal handlers
        gui.data_manager.acquisitionComplete.connect(on_async_complete)
        monkeypatch.setattr(gui.data_manager, 'initiate_measurement',
                            lambda config: handle_start_acquisition("ACCL:L1B:0200:RESA", config))

        # Start measurement and wait for signal
        with qtbot.waitSignal(gui.data_manager.acquisitionComplete, timeout=5000):
            qtbot.mouseClick(gui.config_panel.start_button, Qt.LeftButton)
            qtbot.wait(200)

        print("\nDebug: Starting data generation and plotting...")

        original_method = gui.plot_panel.update_time_series

        def debug_update(cavity_num, times, values):
            print(f"\nDebug: update_time_series called for cavity {cavity_num}")
            print(f"- Values shape: {values.shape}")
            try:
                return original_method(cavity_num, times, values)
            except Exception as e:
                print(f"Error in update_time_series: {str(e)}")
                raise e

        # Apply monkeypatch directly to the instance
        monkeypatch.setattr(gui.plot_panel, 'update_time_series', debug_update)

        # Generate test data
        for cavity in cavity_nums:
            num_points = 100
            # Generate time array to match data length exactly
            times = np.linspace(0, (num_points - 1) / gui.plot_panel.SAMPLE_RATE, num_points)
            data = 4 * np.sin(2 * np.pi * np.arange(num_points) / num_points)

            print(f"\nDebug: Generated data for cavity {cavity}:")
            print(f"- Data shape: {data.shape}")
            print(f"- Time shape: {times.shape}")

            test_data = {
                "cavity": cavity,
                "channels": {
                    "DAC": data.copy(),
                    "DF": data.copy()
                }
            }

            # Send data and verify plot updates
            print(f"\nDebug: Sending data for cavity {cavity}")
            gui._handle_new_data("TEST:CHASSIS", test_data)
            qtbot.wait(200)

            # Check for curve creation
            print(f"\nDebug: Checking plot curves after cavity {cavity}")
            print(f"- Current plot curves: {list(gui.plot_panel.plot_curves.keys())}")

            if cavity in gui.plot_panel.plot_curves:
                curve = gui.plot_panel.plot_curves[cavity]
                print(f"- Curve data for cavity {cavity}:")
                if hasattr(curve, 'yData'):
                    print(f"  - Y data shape: {curve.yData.shape}")
                    print(f"  - Y data range: [{curve.yData.min():.2f}, {curve.yData.max():.2f}]")

        qtbot.wait(500)

        # Final curve verification
        print("\nDebug: Final plot curve state:")
        print(f"Number of curves: {len(gui.plot_panel.plot_curves)}")
        print(f"Cavity IDs present: {list(gui.plot_panel.plot_curves.keys())}")

        assert len(gui.plot_panel.plot_curves) >= len(cavity_nums), \
            f"Expected at least {len(cavity_nums)} curves, got {len(gui.plot_panel.plot_curves)}"

        qtbot.mouseClick(gui.config_panel.stop_button, Qt.LeftButton)
        qtbot.wait(100)

    except Exception as e:
        print(f"\nTest error: {str(e)}")
        print("\nStack trace:")
        import traceback
        traceback.print_exc()
        raise e


def test_plot_updates(gui):
    """Test plot updates with synthetic signals."""
    cavity_num = 1
    data = {
        "DAC": np.sin(np.linspace(0, 10 * np.pi, 1000)),
        "DF": np.cos(np.linspace(0, 10 * np.pi, 1000)),
    }

    gui.plot_panel.update_plots(cavity_num, data)


def test_error_handling(gui):
    """Verify error display and handling."""
    error_msg = "Test error message"
    gui._handle_error("TEST:CHASSIS", error_msg)


def test_status_updates(gui):
    """Check status panel updates."""
    cavity_num = 1
    status = "Running"
    progress = 50
    message = "Test status message"

    gui.status_panel.update_cavity_status(cavity_num, status, progress, message)

    cavity_status = gui.status_panel.get_cavity_status(cavity_num)
    assert cavity_status["status"] == status
    assert cavity_status["progress"] == progress
    assert cavity_status["message"] == message


def test_fft_calculation(gui):
    """Test FFT calculation accuracy and scaling"""
    # Generate 100Hz test signal
    t = np.linspace(0, 1, 2000)  # 1 second of data
    y = np.sin(2 * np.pi * 100 * t)
    freqs, amps = gui.plot_panel._calculate_fft(y)
    assert abs(freqs[np.argmax(amps)] - 100) < 0.1  # Peak at 100Hz
    assert abs(amps.max() - 1.0) < 0.01  # Proper 2/N scaling


def test_statistics_update(qtbot):
    panel = StatisticsPanel()
    qtbot.addWidget(panel)

    # Test initial state
    widgets = panel.stat_widgets[3]
    assert widgets['mean'].text() == "0.0"

    # Update with test data
    test_stats = {
        'mean': 12.3456,
        'std': 5.6789,
        'min': -8.912,
        'max': 25.123,
        'outliers': 3
    }
    panel.update_statistics(3, test_stats)

    # Verify formatted values
    assert widgets['mean'].text() == "12.35"  # Rounded to 2 decimals
    assert widgets['std'].text() == "5.68"
    assert widgets['min'].text() == "-8.91"
    assert widgets['max'].text() == "25.12"
    assert widgets['outliers'].text() == "3"


def test_config_invalid_cavities(qtbot):
    panel = ConfigPanel()
    qtbot.addWidget(panel)
    panel.show()
    QApplication.processEvents()

    # Setup valid base config without waiting for signals
    qtbot.mouseClick(panel.linac_buttons["L1B"], Qt.LeftButton)
    qtbot.wait(100)  # Wait for UI update

    qtbot.mouseClick(panel.cryo_buttons["03"], Qt.LeftButton)
    qtbot.wait(100)  # Wait for UI update

    # Block signals while setting invalid state
    try:
        panel.cavity_checks_a[4].blockSignals(True)
        panel.cavity_checks_b[5].blockSignals(True)
        panel.cavity_checks_a[4].setChecked(True)
        panel.cavity_checks_b[5].setChecked(True)

        # Force UI update
        QApplication.processEvents()

        # Verify without unblocking signals
        error = panel.validate_cavity_selection()
        assert error is not None  # First ensure we got an error
        assert "Cannot measure cavities from both racks" in error
    finally:
        # Ensure signals are always unblocked
        panel.cavity_checks_a[4].blockSignals(False)
        panel.cavity_checks_b[5].blockSignals(False)


def test_decimation_handling(gui):
    """Test frequency scaling with decimation"""
    # With decimation=4, 2000/4=500Hz sample rate
    # Should see max frequency at 250Hz (Nyquist)
    gui.plot_panel.current_decimation = 4
    noise = np.random.normal(0, 1, 2000)
    freqs, _ = gui.plot_panel._calculate_fft(noise)
    assert freqs[-1] == 250.0


def test_histogram_configuration(gui):
    """Test histogram binning and range configuration"""
    test_data = np.random.normal(0, 50, 10000)
    counts, bins = np.histogram(test_data, bins=140, range=(-200, 200))
    assert len(bins) == 141  # 140 bins = 141 edges
    assert bins[0] == -200 and bins[-1] == 200
    # Verify log mode is enabled for y-axis
    assert gui.plot_panel.plot_widgets['histogram'].getAxis('left').logMode is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
