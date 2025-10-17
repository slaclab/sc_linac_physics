import gc

import pytest
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QApplication

from sc_linac_physics.applications.microphonics.gui.async_data_manager import (
    BASE_HARDWARE_SAMPLE_RATE,
)
from sc_linac_physics.applications.microphonics.gui.config_panel import (
    ConfigPanel,
)


def pytest_configure(config):
    """Ensure we only create one QApplication instance for all tests."""
    if not hasattr(QtWidgets, "QApplication"):
        return
    if QApplication.instance() is None:
        QApplication([])


@pytest.fixture(autouse=True)
def cleanup_qt():
    """Clean up Qt objects after each test."""
    yield
    # Process any pending events
    QApplication.instance().processEvents()
    # Force garbage collection
    gc.collect()


@pytest.fixture
def config_panel():
    """Create a fresh ConfigPanel instance for each test."""
    panel = ConfigPanel()
    yield panel
    # Ensure proper cleanup
    panel.setParent(None)
    panel.deleteLater()
    QApplication.instance().processEvents()


def test_initial_state(config_panel):
    """Test initial state of the ConfigPanel."""
    # Check initial values
    assert config_panel.selected_linac is None
    assert config_panel.is_updating is False

    # Check default decimation value
    assert config_panel.decim_combo.currentText() == str(
        config_panel.DEFAULT_DECIMATION_VALUE
    )

    # Check default buffer count
    assert config_panel.buffer_spin.value() == config_panel.DEFAULT_BUFFER_COUNT

    # Check initial button states
    assert config_panel.start_button.isEnabled() is True
    assert config_panel.stop_button.isEnabled() is False


def test_linac_selection(config_panel):
    """Test linac selection functionality."""
    # Initially no linac should be selected
    assert config_panel.selected_linac is None

    # Select L0B
    config_panel.linac_buttons["L0B"].click()
    assert config_panel.selected_linac == "L0B"

    # Check that the correct cryomodules are shown
    assert len(config_panel.cryo_buttons) == len(
        config_panel.VALID_LINACS["L0B"]
    )
    assert "01" in config_panel.cryo_buttons


def test_cavity_selection(config_panel):
    """Test cavity selection functionality."""
    # Initially no cavities should be selected
    for cb in config_panel.cavity_checks_a.values():
        assert not cb.isChecked()
    for cb in config_panel.cavity_checks_b.values():
        assert not cb.isChecked()

    # Test select all in Rack A
    config_panel.select_all_a.click()
    for cb in config_panel.cavity_checks_a.values():
        assert cb.isChecked()

    # Test deselect all in Rack A
    config_panel.select_all_a.click()
    for cb in config_panel.cavity_checks_a.values():
        assert not cb.isChecked()


def test_decimation_settings(config_panel):
    """Test decimation settings and related calculations."""
    # Test each valid decimation value
    for decimation in config_panel.VALID_DECIMATION:
        config_panel.decim_combo.setCurrentText(str(decimation))

        # Check sampling rate calculation
        expected_rate = BASE_HARDWARE_SAMPLE_RATE / decimation
        displayed_rate = float(config_panel.label_sampling_rate.text())
        assert (
            abs(expected_rate - displayed_rate) < 0.1
        )  # Allow for floating point rounding

        # Check acquisition time calculation with default buffer count
        buffer_count = config_panel.DEFAULT_BUFFER_COUNT
        expected_time = (
            config_panel.BUFFER_LENGTH * decimation * buffer_count
        ) / BASE_HARDWARE_SAMPLE_RATE
        displayed_time = float(config_panel.label_acq_time.text())
        assert (
            abs(expected_time - displayed_time) < 0.01
        )  # Allow for floating point rounding


def test_measurement_control(config_panel):
    """Test measurement control functionality."""
    # Initially start should be enabled and stop disabled
    assert config_panel.start_button.isEnabled()
    assert not config_panel.stop_button.isEnabled()

    # Test setting measurement running
    config_panel.set_measurement_running(True)
    assert not config_panel.start_button.isEnabled()
    assert config_panel.stop_button.isEnabled()

    # Test setting measurement stopped
    config_panel.set_measurement_running(False)
    assert config_panel.start_button.isEnabled()
    assert not config_panel.stop_button.isEnabled()


def test_get_config(config_panel):
    """Test configuration retrieval."""
    # Select a linac and let the buttons update
    config_panel.linac_buttons["L0B"].click()
    # Wait for the UI to update
    config_panel.is_updating = False

    # Select a module from the available ones
    for mod_id, btn in config_panel.cryo_buttons.items():
        btn.click()  # Select the first available module
        break

    # Select some cavities
    config_panel.cavity_checks_a[1].setChecked(True)
    config_panel.cavity_checks_b[5].setChecked(True)

    # Set decimation and buffer count
    config_panel.decim_combo.setCurrentText("2")
    config_panel.buffer_spin.setValue(3)

    # Get config
    config = config_panel.get_config()

    # Verify config contents
    assert config["linac"] == "L0B"
    assert len(config["modules"]) == 1  # Should have one module selected
    assert config["cavities"][1] is True
    assert config["cavities"][5] is True
    assert config["decimation"] == 2
    assert config["buffer_count"] == 3


def test_validate_cavity_selection(config_panel):
    """Test cavity selection validation."""
    # Initially no cavities selected should give error
    assert config_panel.validate_cavity_selection() is not None

    # Select a cavity should pass validation
    config_panel.cavity_checks_a[1].setChecked(True)
    assert config_panel.validate_cavity_selection() is None

    # For bulk actions, no selection is allowed
    assert config_panel.validate_cavity_selection(is_bulk_action=True) is None


def test_signal_emission(config_panel):
    """Test that signals are emitted correctly."""
    # Setup signal trackers
    config_changed_count = 0
    measurement_started_count = 0
    measurement_stopped_count = 0
    decimation_changed_count = 0
    last_decimation = None

    # Keep track of connections for cleanup
    connections = []

    def on_config_changed(config):
        nonlocal config_changed_count
        config_changed_count += 1

    def on_measurement_started():
        nonlocal measurement_started_count
        measurement_started_count += 1

    def on_measurement_stopped():
        nonlocal measurement_stopped_count
        measurement_stopped_count += 1

    def on_decimation_changed(value):
        nonlocal decimation_changed_count, last_decimation
        decimation_changed_count += 1
        last_decimation = value

    # Connect signals and track connections
    connections.extend(
        [
            config_panel.configChanged.connect(on_config_changed),
            config_panel.measurementStarted.connect(on_measurement_started),
            config_panel.measurementStopped.connect(on_measurement_stopped),
            config_panel.decimationSettingChanged.connect(
                on_decimation_changed
            ),
        ]
    )

    # Change decimation
    config_panel.decim_combo.setCurrentText("4")
    assert decimation_changed_count == 1
    assert last_decimation == 4

    # Start measurement (need to select a cavity first)
    config_panel.cavity_checks_a[1].setChecked(True)
    config_panel.start_button.click()
    assert measurement_started_count == 1

    # Test measurement control
    config_panel.set_measurement_running(True)  # This enables the stop button
    config_panel.stop_button.click()
    assert (
        measurement_stopped_count == 1
    )  # Config should have changed multiple times
    assert config_changed_count > 0

    # Clean up signal connections
    for connection in connections:
        config_panel.configChanged.disconnect(connection)


def teardown_module():
    """Clean up after all tests in this module."""
    # Process any pending events
    app = QApplication.instance()
    if app:
        app.processEvents()
        # Give Qt time to clean up
        app.processEvents()
    # Force garbage collection
    gc.collect()
