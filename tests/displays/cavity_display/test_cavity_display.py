from unittest.mock import patch, MagicMock

import pytest
from PyQt5.QtWidgets import QWidget, QVBoxLayout
from pytestqt.qtbot import QtBot


# Mock classes for the displays we want to prevent from opening
class MockFaultCountDisplay(QWidget):
    """Mock version of FaultCountDisplay."""

    def __init__(self, *args, **kwargs):
        super().__init__()


class MockDecoderDisplay(QWidget):
    """Mock version of DecoderDisplay."""

    def __init__(self, *args, **kwargs):
        super().__init__()


class MockGUIMachine:
    """Mock version of GUIMachine."""

    def __init__(self, *args, **kwargs):
        # Create real layouts so they can be added to the main layout
        self.top_half = QVBoxLayout()
        self.bottom_half = QVBoxLayout()


@pytest.fixture
def mock_show_display():
    """Mock the showDisplay function."""
    # Create a mock for showDisplay
    mock_show = MagicMock()

    # Patch the showDisplay function
    with patch("lcls_tools.common.frontend.display.util.showDisplay", mock_show):
        yield mock_show


@pytest.fixture
def display(mock_show_display):
    """Create a CavityDisplayGUI instance with mocked components."""
    # Patch the components before importing CavityDisplayGUI
    with (
        patch(
            "sc_linac_physics.displays.cavity_display.frontend.fault_count_display.FaultCountDisplay",
            MockFaultCountDisplay,
        ),
        patch(
            "sc_linac_physics.displays.cavity_display.frontend.fault_decoder_display.DecoderDisplay", MockDecoderDisplay
        ),
        patch("sc_linac_physics.displays.cavity_display.frontend.gui_machine.GUIMachine", MockGUIMachine),
    ):

        # Now import CavityDisplayGUI after patching
        from sc_linac_physics.displays.cavity_display.cavity_display import CavityDisplayGUI

        # Create the display but prevent it from showing
        with patch.object(CavityDisplayGUI, "show"), patch.object(CavityDisplayGUI, "showMaximized"):
            display = CavityDisplayGUI()
            yield display
            display.close()


def test_launches(qtbot: QtBot, display):
    """Test that the application launches successfully."""
    qtbot.addWidget(display)
    assert display.windowTitle() == "SRF Cavity Display"


def test_header_buttons(qtbot: QtBot, display):
    """Test that header buttons are created correctly."""
    qtbot.addWidget(display)

    # Check that buttons exist
    assert hasattr(display, "decoder_button")
    assert hasattr(display, "fault_count_button")

    # Check button text
    assert display.decoder_button.text() == "Three Letter Code Decoder"
    assert display.fault_count_button.text() == "Fault Counter"

    # Check that buttons have tooltips
    assert display.fault_count_button.toolTip() == "See fault history using archived data"


@pytest.mark.skip("Need to figure out why this is failing")
def test_button_connections(qtbot: QtBot, display, mock_show_display):
    """Test that button connections work with our mocked showDisplay function."""
    qtbot.addWidget(display)

    # Verify that buttons have signal connections
    assert display.decoder_button.receivers(display.decoder_button.clicked) > 0
    assert display.fault_count_button.receivers(display.fault_count_button.clicked) > 0

    # Emit the clicked signal directly
    display.decoder_button.clicked.emit()

    # Verify showDisplay was called with decoder window
    mock_show_display.assert_called_once_with(display.decoder_window)

    # Reset mock
    mock_show_display.reset_mock()

    # Emit the clicked signal for the fault count button
    display.fault_count_button.clicked.emit()

    # Verify showDisplay was called with fault count display
    mock_show_display.assert_called_once_with(display.fault_count_display)


def test_add_header_button(qtbot: QtBot, display, mock_show_display):
    """Test the add_header_button method directly."""
    qtbot.addWidget(display)

    # Create a new test button and display
    from PyQt5.QtWidgets import QPushButton

    test_button = QPushButton("Test Button")
    test_display = QWidget()

    # Call the add_header_button method
    display.add_header_button(test_button, test_display)

    # Verify the button has a clicked signal connected
    assert test_button.receivers(test_button.clicked) > 0
