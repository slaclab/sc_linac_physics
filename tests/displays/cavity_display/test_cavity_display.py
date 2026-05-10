from unittest.mock import patch, MagicMock

import pytest
from PyQt5.QtWidgets import QVBoxLayout, QWidget
from pytestqt.qtbot import QtBot


@pytest.fixture(scope="module", autouse=True)
def disable_pydm_connections():
    """Disable PyDM data connections for all tests in this module."""
    import os

    os.environ["PYDM_DATA_PLUGINS_DISABLED"] = "1"

    import pydm.data_plugins

    original_plugin_for_address = pydm.data_plugins.plugin_for_address

    mock_plugin = MagicMock()
    mock_plugin.add_listener = MagicMock()
    mock_plugin.remove_listener = MagicMock()
    pydm.data_plugins.plugin_for_address = MagicMock(return_value=mock_plugin)

    yield

    pydm.data_plugins.plugin_for_address = original_plugin_for_address


# Mock classes for displays we want to prevent from opening
class MockFaultCountDisplay(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__()


class MockDecoderDisplay(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__()


class MockGUIMachine:
    def __init__(self, *args, **kwargs):
        self.top_half = QVBoxLayout()
        self.bottom_half = QVBoxLayout()


@pytest.fixture(scope="module")
def display(qapp):
    """Create one CavityDisplayGUI for the whole module — avoids rebuilding it
    for every test, which is expensive due to heavy PyDM/EPICS imports."""
    from sc_linac_physics.displays.cavity_display.cavity_display import (
        CavityDisplayGUI,
    )

    with (
        patch(
            "sc_linac_physics.displays.cavity_display.cavity_display.showDisplay",
            MagicMock(),
        ),
        patch(
            "sc_linac_physics.displays.cavity_display.frontend.fault_count_display.FaultCountDisplay",
            MockFaultCountDisplay,
        ),
        patch(
            "sc_linac_physics.displays.cavity_display.frontend.fault_decoder_display.DecoderDisplay",
            MockDecoderDisplay,
        ),
        patch(
            "sc_linac_physics.displays.cavity_display.frontend.gui_machine.GUIMachine",
            MockGUIMachine,
        ),
        patch.object(CavityDisplayGUI, "show"),
        patch.object(CavityDisplayGUI, "showMaximized"),
    ):
        qapp.processEvents()
        d = CavityDisplayGUI()
        qapp.processEvents()
        yield d
        d.close()
        d.deleteLater()
        qapp.processEvents()


@pytest.fixture
def mock_show_display(monkeypatch):
    """Mock the showDisplay function for tests that need to assert on calls."""
    mock = MagicMock()
    monkeypatch.setattr(
        "sc_linac_physics.displays.cavity_display.cavity_display.showDisplay",
        mock,
    )
    return mock


def test_launches(qtbot: QtBot, display):
    """Test that the application launches successfully."""
    assert display.windowTitle() == "SRF Cavity Display"


def test_header_buttons(qtbot: QtBot, display):
    """Test that header buttons are created correctly."""
    assert hasattr(display, "decoder_button")
    assert hasattr(display, "fault_count_button")

    assert display.decoder_button.text() == "Three Letter Code Decoder"
    assert display.fault_count_button.text() == "Fault Counter"

    assert (
        display.fault_count_button.toolTip()
        == "See fault history using archived data"
    )


def test_button_connections(qtbot: QtBot, display, mock_show_display):
    """Test that button connections work with our mocked showDisplay function."""
    assert display.decoder_button.receivers(display.decoder_button.clicked) > 0
    assert (
        display.fault_count_button.receivers(display.fault_count_button.clicked)
        > 0
    )

    display.decoder_button.clicked.emit()
    mock_show_display.assert_called_once_with(display.decoder_window)

    mock_show_display.reset_mock()

    display.fault_count_button.clicked.emit()
    mock_show_display.assert_called_once_with(display.fault_count_display)


def test_add_header_button(qtbot: QtBot, display, mock_show_display):
    """Test the add_header_button method directly."""
    from PyQt5.QtWidgets import QPushButton

    test_button = QPushButton("Test Button")
    test_display = QWidget()

    display.add_header_button(test_button, test_display)

    assert test_button.receivers(test_button.clicked) > 0
