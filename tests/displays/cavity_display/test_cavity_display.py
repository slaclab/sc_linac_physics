from unittest.mock import patch, MagicMock

import pytest

from sc_linac_physics.displays.cavity_display.cavity_display import CavityDisplayGUI


class TestCavityDisplayGUI:
    """Test suite for the CavityDisplayGUI application."""

    @pytest.fixture
    def display(self):
        """Create a CavityDisplayGUI instance with mocked components."""
        # Mock the sub-displays to prevent them from creating actual connections
        with (
            patch(
                "sc_linac_physics.displays.cavity_display.frontend.fault_count_display.FaultCountDisplay"
            ) as mock_fault_count,
            patch(
                "sc_linac_physics.displays.cavity_display.frontend.fault_decoder_display.DecoderDisplay"
            ) as mock_decoder,
            patch("sc_linac_physics.displays.cavity_display.frontend.gui_machine.GUIMachine") as mock_gui_machine,
        ):

            # Configure return values
            mock_fault_count.return_value = MagicMock()
            mock_decoder.return_value = MagicMock()
            mock_gui_machine.return_value = MagicMock()
            mock_gui_machine.return_value.top_half = MagicMock()
            mock_gui_machine.return_value.bottom_half = MagicMock()

            # Mock showDisplay function
            with patch("lcls_tools.common.frontend.display.util.showDisplay") as _:
                gui = CavityDisplayGUI()
                yield gui
                # Ensure cleanup
                gui.close()

    def test_launches(self, qtbot, display):
        """Test that the application launches successfully."""
        qtbot.addWidget(display)
        assert display.windowTitle() == "SRF Cavity Display"

    def test_header_buttons(self, qtbot, display):
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

    def test_gui_machine_integration(self, qtbot, display):
        """Test that the GUI machine is integrated correctly."""
        qtbot.addWidget(display)

        # Verify GUI machine layouts are added to the main layout
        assert display.gui_machine.top_half in display.groupbox_vlayout.children()
        assert display.gui_machine.bottom_half in display.groupbox_vlayout.children()

    @pytest.mark.parametrize(
        "window_attr,button_attr,button_text",
        [
            ("decoder_window", "decoder_button", "Three Letter Code Decoder"),
            ("fault_count_display", "fault_count_button", "Fault Counter"),
        ],
    )
    def test_sub_windows_creation(self, qtbot, display, window_attr, button_attr, button_text):
        """Test that sub-windows are created correctly."""
        qtbot.addWidget(display)

        # Check that the window attribute exists
        assert hasattr(display, window_attr)

        # Check that the corresponding button exists and has correct text
        assert hasattr(display, button_attr)
        assert getattr(display, button_attr).text() == button_text
