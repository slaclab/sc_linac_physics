from unittest.mock import patch

import pytest
from PyQt5.QtWidgets import QWidget
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


@pytest.fixture
def display():
    """Create a CavityDisplayGUI instance with mocked sub-displays."""
    # Patch the sub-displays before importing CavityDisplayGUI
    with (
        patch(
            "sc_linac_physics.displays.cavity_display.frontend.fault_count_display.FaultCountDisplay",
            MockFaultCountDisplay,
        ),
        patch(
            "sc_linac_physics.displays.cavity_display.frontend.fault_decoder_display.DecoderDisplay", MockDecoderDisplay
        ),
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


def test_sub_displays_created(qtbot: QtBot, display):
    """Test that sub-displays are created."""
    qtbot.addWidget(display)

    # Check that the sub-displays exist
    assert hasattr(display, "decoder_window")
    assert hasattr(display, "fault_count_display")


def test_layout_structure(qtbot: QtBot, display):
    """Test that the layout structure is created correctly."""
    qtbot.addWidget(display)

    # Check basic layout elements
    assert hasattr(display, "vlayout")
    assert hasattr(display, "groupbox_vlayout")
    assert hasattr(display, "header")
    assert hasattr(display, "groupbox")
