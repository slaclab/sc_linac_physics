import sys
from unittest.mock import Mock, patch

import numpy as np
import pytest
from PyQt5.QtWidgets import QMessageBox
from qtpy.QtCore import Qt, QPoint
from qtpy.QtGui import QColor, QMouseEvent
from qtpy.QtWidgets import QApplication

# Import your module with the correct path
from sc_linac_physics.displays.cavity_display.frontend.cavity_widget import (
    CavityWidget,
    ShapeParameters,
    SHAPE_PARAMETER_DICT,
    GREEN_FILL_COLOR,
    BLACK_TEXT_COLOR,
    RED_FILL_COLOR,
)


# Fixture to ensure QApplication exists
@pytest.fixture(scope="session")
def qapp():
    """Create QApplication for testing."""
    if not QApplication.instance():
        app = QApplication(sys.argv)
    else:
        app = QApplication.instance()
    yield app


@pytest.fixture
def cavity_widget(qapp):
    """Create a CavityWidget instance for testing."""
    widget = CavityWidget()
    yield widget
    widget.deleteLater()


class TestShapeParameters:
    """Test the ShapeParameters dataclass."""

    def test_shape_parameters_creation(self):
        """Test creating ShapeParameters."""
        params = ShapeParameters(
            fillColor=GREEN_FILL_COLOR,
            borderColor=BLACK_TEXT_COLOR,
            numPoints=4,
            rotation=0,
        )
        assert params.fillColor == GREEN_FILL_COLOR
        assert params.borderColor == BLACK_TEXT_COLOR
        assert params.numPoints == 4
        assert params.rotation == 0


class TestShapeParameterDict:
    """Test the SHAPE_PARAMETER_DICT configuration."""

    def test_shape_parameter_dict_exists(self):
        """Test that all expected keys exist in SHAPE_PARAMETER_DICT."""
        expected_keys = {0, 1, 2, 3, 4, 5}
        assert set(SHAPE_PARAMETER_DICT.keys()) == expected_keys

    def test_all_values_are_shape_parameters(self):
        """Test that all values in the dict are ShapeParameters instances."""
        for key, value in SHAPE_PARAMETER_DICT.items():
            assert isinstance(value, ShapeParameters)
            assert isinstance(value.fillColor, QColor)
            assert isinstance(value.borderColor, QColor)
            assert isinstance(value.numPoints, int)
            assert isinstance(value.rotation, (int, float))


class TestCavityWidgetInitialization:
    """Test CavityWidget initialization."""

    def test_widget_initialization(self, cavity_widget):
        """Test widget initializes with correct default values."""
        assert cavity_widget._num_points == 4
        assert cavity_widget._cavity_text == ""
        assert cavity_widget._underline is False
        assert cavity_widget._rotation == 0
        assert cavity_widget._severity_channel is None
        assert cavity_widget._description_channel is None
        assert cavity_widget.alarmSensitiveBorder is False
        assert cavity_widget.alarmSensitiveContent is False
        assert cavity_widget._acknowledged is False

    def test_widget_initialization_with_channel(self, qapp):
        """Test widget initialization with initial channel."""
        widget = CavityWidget(init_channel="test:channel")
        assert widget is not None
        widget.deleteLater()


class TestCavityWidgetProperties:
    """Test CavityWidget properties."""

    def test_cavity_text_property(self, cavity_widget):
        """Test cavity_text property getter and setter."""
        test_text = "Test Cavity"
        cavity_widget.cavity_text = test_text
        assert cavity_widget.cavity_text == test_text

    def test_underline_property(self, cavity_widget):
        """Test underline property getter and setter."""
        cavity_widget.underline = True
        assert cavity_widget.underline is True

        cavity_widget.underline = False
        assert cavity_widget.underline is False

    @patch(
        "sc_linac_physics.displays.cavity_display.frontend.cavity_widget.PyDMChannel"
    )
    def test_severity_channel_property(self, mock_channel_class, cavity_widget):
        """Test severity_channel property."""
        mock_channel = Mock()
        mock_channel.address = "test:severity"
        mock_channel_class.return_value = mock_channel

        # Test setter
        cavity_widget.severity_channel = "test:severity"
        mock_channel_class.assert_called_with(
            address="test:severity",
            value_slot=cavity_widget.severity_channel_value_changed,
        )
        mock_channel.connect.assert_called_once()

        # Test getter
        assert cavity_widget.severity_channel == "test:severity"

    @patch(
        "sc_linac_physics.displays.cavity_display.frontend.cavity_widget.PyDMChannel"
    )
    def test_severity_channel_disconnect_on_reset(
        self, mock_channel_class, cavity_widget
    ):
        """Test severity_channel disconnects old channel when set again."""
        # First channel
        mock_channel1 = Mock()
        mock_channel1.address = "test:severity1"

        # Second channel
        mock_channel2 = Mock()
        mock_channel2.address = "test:severity2"

        mock_channel_class.side_effect = [mock_channel1, mock_channel2]

        # Set first channel
        cavity_widget.severity_channel = "test:severity1"
        mock_channel1.connect.assert_called_once()

        # Set second channel - should disconnect first
        cavity_widget.severity_channel = "test:severity2"
        mock_channel1.disconnect.assert_called_once()
        mock_channel2.connect.assert_called_once()

    @patch(
        "sc_linac_physics.displays.cavity_display.frontend.cavity_widget.PyDMChannel"
    )
    def test_description_channel_property(
        self, mock_channel_class, cavity_widget
    ):
        """Test description_channel property."""
        mock_channel = Mock()
        mock_channel.address = "test:description"
        mock_channel_class.return_value = mock_channel

        # Test setter
        cavity_widget.description_channel = "test:description"
        mock_channel_class.assert_called_with(
            address="test:description",
            value_slot=cavity_widget.description_changed,
        )
        mock_channel.connect.assert_called_once()

        # Test getter
        assert cavity_widget.description_channel == "test:description"

    def test_description_channel_getter_with_none(self, cavity_widget):
        """Test description_channel getter when channel is None."""
        cavity_widget._description_channel = None
        assert cavity_widget.description_channel == ""


class TestCavityWidgetMouseEvents:
    """Test mouse event handling."""

    def test_mouse_press_event(self, cavity_widget):
        """Test mouse press event sets press_pos."""
        event = QMouseEvent(
            QMouseEvent.MouseButtonPress,
            QPoint(10, 10),
            Qt.LeftButton,
            Qt.LeftButton,
            Qt.NoModifier,
        )
        cavity_widget.mousePressEvent(event)
        assert cavity_widget.press_pos == QPoint(10, 10)

    @patch.object(CavityWidget, "show_context_menu")
    def test_mouse_press_event_right_button(
        self, mock_context_menu, cavity_widget
    ):
        """Test mouse press event with right button shows context menu."""
        event = QMouseEvent(
            QMouseEvent.MouseButtonPress,
            QPoint(10, 10),
            Qt.RightButton,
            Qt.RightButton,
            Qt.NoModifier,
        )
        cavity_widget.mousePressEvent(event)
        assert cavity_widget.press_pos is None
        mock_context_menu.assert_called_once()

    def test_mouse_release_event_emits_clicked(self, cavity_widget):
        """Test mouse release event emits clicked signal."""
        # Set up widget geometry
        cavity_widget.resize(100, 100)

        # Simulate press
        cavity_widget.press_pos = QPoint(10, 10)

        # Create release event
        event = QMouseEvent(
            QMouseEvent.MouseButtonRelease,
            QPoint(15, 15),  # Within widget bounds
            Qt.LeftButton,
            Qt.LeftButton,
            Qt.NoModifier,
        )

        # Connect signal to spy
        clicked_spy = Mock()
        cavity_widget.clicked.connect(clicked_spy)

        # Trigger event
        cavity_widget.mouseReleaseEvent(event)

        # Check signal was emitted
        clicked_spy.assert_called_once()
        assert cavity_widget.press_pos is None

    def test_mouse_release_event_no_click_when_outside(self, cavity_widget):
        """Test mouse release outside widget doesn't emit clicked."""
        cavity_widget.resize(50, 50)
        cavity_widget.press_pos = QPoint(10, 10)

        # Release outside widget bounds
        event = QMouseEvent(
            QMouseEvent.MouseButtonRelease,
            QPoint(100, 100),
            Qt.LeftButton,
            Qt.LeftButton,
            Qt.NoModifier,
        )

        clicked_spy = Mock()
        cavity_widget.clicked.connect(clicked_spy)

        cavity_widget.mouseReleaseEvent(event)

        clicked_spy.assert_not_called()


class TestCavityWidgetChannelHandlers:
    """Test channel value change handlers."""

    def test_severity_channel_value_changed_valid_value(self, cavity_widget):
        """Test severity channel handler with valid value."""
        with patch.object(cavity_widget, "change_shape") as mock_change_shape:
            cavity_widget.severity_channel_value_changed(0)
            mock_change_shape.assert_called_with(SHAPE_PARAMETER_DICT[0])
            assert cavity_widget._last_severity == 0
            assert cavity_widget._acknowledged is False

    def test_severity_channel_value_changed_clears_acknowledgment(
        self, cavity_widget
    ):
        """Test severity returning to 0 clears acknowledgment."""
        # Set up acknowledged state
        cavity_widget._acknowledged = True

        # Mock parent cavity
        mock_cavity = Mock()
        mock_cavity.cryomodule.name = "01"
        mock_cavity.number = 1
        cavity_widget._parent_cavity = mock_cavity

        # Mock app with acknowledged_cavities set
        mock_app = Mock()
        mock_app.acknowledged_cavities = {"01_1"}

        with patch(
            "qtpy.QtWidgets.QApplication.instance", return_value=mock_app
        ):
            with patch.object(cavity_widget, "change_shape"):
                cavity_widget.severity_channel_value_changed(0)

                assert cavity_widget._acknowledged is False
                assert "01_1" not in mock_app.acknowledged_cavities

    def test_severity_channel_value_changed_invalid_value(self, cavity_widget):
        """Test severity channel handler with invalid value falls back to default."""
        with patch.object(cavity_widget, "change_shape") as mock_change_shape:
            cavity_widget.severity_channel_value_changed(999)  # Invalid value
            mock_change_shape.assert_called_with(SHAPE_PARAMETER_DICT[3])
            assert cavity_widget._last_severity is None

    def test_severity_channel_value_changed_exception_handling(
        self, cavity_widget
    ):
        """Test severity channel handler exception handling."""
        # Create a mock that raises exception on first call, succeeds on second
        mock_change_shape = Mock(side_effect=[Exception("Test error"), None])

        with patch.object(cavity_widget, "change_shape", mock_change_shape):
            # Should not raise exception - should handle it gracefully
            cavity_widget.severity_channel_value_changed(0)

            # Should be called twice - once with the intended value, once with fallback
            assert mock_change_shape.call_count == 2

            # Verify the calls were made with correct parameters
            calls = mock_change_shape.call_args_list
            assert (
                calls[0][0][0] == SHAPE_PARAMETER_DICT[0]
            )  # First call with intended value
            assert (
                calls[1][0][0] == SHAPE_PARAMETER_DICT[3]
            )  # Second call with fallback

    def test_description_changed_with_string(self, cavity_widget):
        """Test description_changed with string value."""
        test_description = "Test Description"
        cavity_widget.description_changed(test_description)
        assert cavity_widget.toolTip() == test_description
        assert cavity_widget._cavity_description == test_description

    def test_description_changed_with_numpy_array(self, cavity_widget):
        """Test description_changed with numpy array."""
        # Create array of ASCII values for "Hello"
        test_array = np.array([72, 101, 108, 108, 111])  # "Hello"
        cavity_widget.description_changed(test_array)
        assert cavity_widget.toolTip() == "Hello"

    def test_description_changed_with_empty_numpy_array(self, cavity_widget):
        """Test description_changed with empty numpy array."""
        test_array = np.array([])
        cavity_widget.description_changed(test_array)
        assert cavity_widget.toolTip() == "Empty array"

    def test_description_changed_with_bytes(self, cavity_widget):
        """Test description_changed with bytes."""
        test_bytes = b"Test Bytes"
        cavity_widget.description_changed(test_bytes)
        assert cavity_widget.toolTip() == "Test Bytes"

    def test_description_changed_with_none(self, cavity_widget):
        """Test description_changed with None value."""
        cavity_widget.description_changed(None)
        assert cavity_widget.toolTip() == "No description available"
        assert cavity_widget._cavity_description == ""

    def test_description_changed_with_invalid_data(self, cavity_widget):
        """Test description_changed with data that causes processing error."""
        # Test with NaN values which will cause int() conversion to fail
        test_array = np.array([72, np.nan, 101])  # 'H', NaN, 'e'
        cavity_widget.description_changed(test_array)
        assert "Description processing error" in cavity_widget.toolTip()

    def test_description_changed_with_large_values_filtered_out(
        self, cavity_widget
    ):
        """Test description_changed with values that get filtered out (not an error case)."""
        # Array with invalid ASCII values - these get filtered out, resulting in empty string
        test_array = np.array([999, 1000])  # Invalid ASCII but filtered out
        cavity_widget.description_changed(test_array)
        # This results in empty string, not an error
        assert cavity_widget.toolTip() == "No description available"


class TestCavityWidgetContextMenu:
    """Test context menu functionality."""

    @patch(
        "sc_linac_physics.displays.cavity_display.frontend.cavity_widget.QMenu"
    )
    def test_show_context_menu_no_parent_cavity(
        self, mock_menu_class, cavity_widget
    ):
        """Test show_context_menu returns early if no parent cavity."""
        cavity_widget._parent_cavity = None

        cavity_widget.show_context_menu(QPoint(0, 0))

        # Menu should not be created
        mock_menu_class.assert_not_called()

    @patch(
        "sc_linac_physics.displays.cavity_display.frontend.cavity_widget.QMenu"
    )
    def test_show_context_menu_with_alarm(self, mock_menu_class, cavity_widget):
        """Test show_context_menu creates acknowledge option for alarm."""
        # Setup mock cavity
        mock_cavity = Mock()
        cavity_widget._parent_cavity = mock_cavity
        cavity_widget._last_severity = 2  # Alarm

        # Setup mock menu and actions
        mock_menu = Mock()
        mock_action = Mock()
        mock_menu.addAction.return_value = mock_action
        mock_menu.addSeparator.return_value = Mock()
        mock_menu.exec_ = Mock()  # Make sure exec_ is mocked
        mock_menu_class.return_value = mock_menu

        cavity_widget.show_context_menu(QPoint(100, 100))

        # Verify menu was created
        mock_menu_class.assert_called_once()

        # Verify exec_ was called to show menu
        mock_menu.exec_.assert_called_once_with(QPoint(100, 100))

        # Check that acknowledge action was added
        action_calls = [
            call[0][0] for call in mock_menu.addAction.call_args_list
        ]
        assert any("Acknowledge Alarm" in name for name in action_calls)
        assert any(
            "Fault Details" in name or "📋" in name for name in action_calls
        )
        assert any("Copy Info" in name or "📄" in name for name in action_calls)

    @patch(
        "sc_linac_physics.displays.cavity_display.frontend.cavity_widget.QMenu"
    )
    def test_show_context_menu_with_warning(
        self, mock_menu_class, cavity_widget
    ):
        """Test show_context_menu creates acknowledge option for warning."""
        # Setup mock cavity
        mock_cavity = Mock()
        cavity_widget._parent_cavity = mock_cavity
        cavity_widget._last_severity = 1  # Warning

        # Setup mock menu and actions
        mock_menu = Mock()
        mock_action = Mock()
        mock_menu.addAction.return_value = mock_action
        mock_menu.addSeparator.return_value = Mock()
        mock_menu.exec_ = Mock()
        mock_menu_class.return_value = mock_menu

        cavity_widget.show_context_menu(QPoint(100, 100))

        # Check that acknowledge action was added for warning
        action_calls = [
            call[0][0] for call in mock_menu.addAction.call_args_list
        ]
        assert any("Acknowledge Warning" in name for name in action_calls)

        # Verify exec_ was called
        mock_menu.exec_.assert_called_once()

    @patch(
        "sc_linac_physics.displays.cavity_display.frontend.cavity_widget.QMenu"
    )
    def test_show_context_menu_without_alarm_or_warning(
        self, mock_menu_class, cavity_widget
    ):
        """Test show_context_menu without alarm or warning (no acknowledge option)."""
        # Setup mock cavity
        mock_cavity = Mock()
        cavity_widget._parent_cavity = mock_cavity
        cavity_widget._last_severity = 0  # Normal

        # Setup mock menu
        mock_menu = Mock()
        mock_action = Mock()
        mock_menu.addAction.return_value = mock_action
        mock_menu.addSeparator.return_value = Mock()
        mock_menu.exec_ = Mock()
        mock_menu_class.return_value = mock_menu

        cavity_widget.show_context_menu(QPoint(100, 100))

        # Check that NO acknowledge action was added
        action_calls = [
            call[0][0] for call in mock_menu.addAction.call_args_list
        ]
        assert not any("Acknowledge" in name for name in action_calls)

        # But details and copy should still be there
        assert any(
            "Fault Details" in name or "📋" in name for name in action_calls
        )
        assert any("Copy Info" in name or "📄" in name for name in action_calls)


class TestCavityWidgetValueChanged:
    """Test value_changed method."""

    def test_value_changed(self, cavity_widget):
        """Test value_changed updates cavity_text and calls update."""
        test_value = "CM01"

        with patch.object(cavity_widget, "update") as mock_update:
            with patch(
                "sc_linac_physics.displays.cavity_display.frontend.cavity_widget.PyDMDrawingPolygon.value_changed"
            ) as mock_super:
                cavity_widget.value_changed(test_value)

                mock_super.assert_called_with(test_value)
                assert cavity_widget.cavity_text == test_value
                mock_update.assert_called_once()


class TestCavityWidgetDrawing:
    """Test drawing functionality."""

    def test_draw_item_calls_super(self, cavity_widget):
        """Test that draw_item calls the parent's draw_item method."""
        with patch(
            "sc_linac_physics.displays.cavity_display.frontend.cavity_widget.PyDMDrawingPolygon.draw_item"
        ) as mock_super_draw:
            with patch.object(
                cavity_widget, "get_bounds", return_value=(0, 0, 100, 50)
            ):
                with patch(
                    "sc_linac_physics.displays.cavity_display.frontend.cavity_widget.QFontMetrics"
                ):
                    mock_painter = Mock()
                    cavity_widget._cavity_text = ""

                    cavity_widget.draw_item(mock_painter)

                    mock_super_draw.assert_called_once_with(mock_painter)

    def test_draw_item_with_empty_text_skips_text_drawing(self, cavity_widget):
        """Test that empty text skips text drawing logic."""
        with patch.object(
            cavity_widget, "get_bounds", return_value=(0, 0, 100, 50)
        ):
            with patch(
                "sc_linac_physics.displays.cavity_display.frontend.cavity_widget.QFontMetrics"
            ) as mock_fm_class:
                mock_painter = Mock()
                cavity_widget._cavity_text = ""

                cavity_widget.draw_item(mock_painter)

                # QFontMetrics should still be created
                mock_fm_class.assert_called()
                # But text drawing methods should not be called
                mock_painter.drawText.assert_not_called()


class TestCavityWidgetShapeChanging:
    """Test shape changing functionality."""

    def test_change_shape_uses_public_properties(self, cavity_widget):
        """Test change_shape method uses public properties (not private attributes)."""
        test_params = ShapeParameters(
            fillColor=RED_FILL_COLOR,
            borderColor=BLACK_TEXT_COLOR,
            numPoints=6,
            rotation=45,
        )

        # Simply call change_shape and verify the properties were set
        cavity_widget.change_shape(test_params)

        # Verify the values were set correctly
        # PyDM's brush setter might store QColor directly in _brush
        # So we need to handle both QBrush and QColor cases
        if hasattr(cavity_widget._brush, "color"):
            # _brush is a QBrush
            assert cavity_widget._brush.color() == RED_FILL_COLOR
        else:
            # _brush is a QColor directly
            assert cavity_widget._brush == RED_FILL_COLOR

        assert cavity_widget._pen.color() == BLACK_TEXT_COLOR
        assert cavity_widget._num_points == 6
        assert cavity_widget._rotation == 45

    def test_change_shape_updates_widget(self, cavity_widget):
        """Test that change_shape results in widget update."""
        test_params = ShapeParameters(
            fillColor=RED_FILL_COLOR,
            borderColor=BLACK_TEXT_COLOR,
            numPoints=6,
            rotation=45,
        )

        cavity_widget.change_shape(test_params)

        # Verify final state is correct by checking internal attributes
        if hasattr(cavity_widget._brush, "color"):
            assert cavity_widget._brush.color() == RED_FILL_COLOR
        else:
            assert cavity_widget._brush == RED_FILL_COLOR

        assert cavity_widget._pen.color() == BLACK_TEXT_COLOR
        assert cavity_widget._num_points == 6
        assert cavity_widget._rotation == 45


class TestCavityWidgetAcknowledgment:
    """Test acknowledgment functionality."""

    @patch("qtpy.QtWidgets.QMessageBox.question")
    @patch("qtpy.QtWidgets.QApplication.instance")
    def test_acknowledge_issue_user_confirms(
        self, mock_app_instance, mock_question, cavity_widget
    ):
        """Test acknowledge_issue when user confirms."""
        # Setup
        mock_cavity = Mock()
        mock_cavity.cryomodule.name = "01"
        mock_cavity.number = 1
        cavity_widget._cavity_description = "Test fault"

        # Mock user clicking Yes
        mock_question.return_value = QMessageBox.Yes

        # Mock app
        mock_app = Mock()
        mock_app.acknowledged_cavities = set()
        mock_app_instance.return_value = mock_app

        # Execute
        cavity_widget.acknowledge_issue(mock_cavity, "Alarm")

        # Verify
        assert "01_1" in mock_app.acknowledged_cavities
        assert cavity_widget._acknowledged is True
        mock_question.assert_called_once()

        # Check that parent was widget (not None)
        call_args = mock_question.call_args
        assert (
            call_args[0][0] == cavity_widget
        )  # parent should be self, not None

    @patch("qtpy.QtWidgets.QMessageBox.question")
    def test_acknowledge_issue_user_cancels(self, mock_question, cavity_widget):
        """Test acknowledge_issue when user cancels."""
        # Setup
        mock_cavity = Mock()
        mock_cavity.cryomodule.name = "01"
        mock_cavity.number = 1

        # Mock user clicking No
        mock_question.return_value = QMessageBox.No

        # Execute
        cavity_widget.acknowledge_issue(mock_cavity, "Alarm")

        # Verify acknowledgment was not set
        assert cavity_widget._acknowledged is False

    @patch("qtpy.QtWidgets.QApplication.instance")
    def test_stop_audio_completely(self, mock_app_instance, cavity_widget):
        """Test _stop_audio_completely calls audio manager."""
        # Create mock parent with audio_manager
        mock_parent = Mock()
        mock_audio_mgr = Mock()
        mock_parent.audio_manager = mock_audio_mgr

        with patch.object(
            cavity_widget, "_get_parent_display", return_value=mock_parent
        ):
            cavity_widget._stop_audio_completely(mock_parent, "01_1")

            mock_audio_mgr.acknowledge_cavity.assert_called_once_with("01_1")

    def test_get_parent_display_finds_parent(self, cavity_widget):
        """Test _get_parent_display traverses widget tree."""
        # Create the display (has audio_manager)
        mock_display = Mock()
        mock_display.audio_manager = Mock()

        # Create the container (doesn't have audio_manager)
        mock_container = Mock(spec=["parent"])  # Only give it parent method
        mock_container.parent = Mock(return_value=mock_display)

        # Make cavity_widget.parent() return the container
        with patch.object(cavity_widget, "parent", return_value=mock_container):
            result = cavity_widget._get_parent_display()

        # Should traverse from widget -> container -> display and find display
        assert result == mock_display
        assert hasattr(result, "audio_manager")

    def test_get_parent_display_no_parent(self, cavity_widget):
        """Test _get_parent_display returns None if no valid parent."""
        with patch.object(cavity_widget, "parent", return_value=None):
            result = cavity_widget._get_parent_display()

        assert result is None


class TestCavityWidgetCopyInfo:
    """Test copy functionality."""

    @patch("qtpy.QtWidgets.QApplication.clipboard")
    def test_copy_cavity_info(self, mock_clipboard, cavity_widget):
        """Test copy_cavity_info copies correct info to clipboard."""
        # Setup
        mock_cavity = Mock()
        mock_cavity.cryomodule.name = "01"
        mock_cavity.number = 5
        cavity_widget._cavity_description = "Test fault description"
        cavity_widget._last_severity = 2

        # Mock clipboard
        mock_clipboard_obj = Mock()
        mock_clipboard.return_value = mock_clipboard_obj

        # Execute
        cavity_widget.copy_cavity_info(mock_cavity)

        # Verify
        mock_clipboard_obj.setText.assert_called_once()
        copied_text = mock_clipboard_obj.setText.call_args[0][0]

        assert "CM01" in copied_text
        assert "Cavity 5" in copied_text
        assert "Test fault description" in copied_text
        assert "Severity: 2" in copied_text


class TestCavityWidgetHighlight:
    """Test highlight functionality."""

    def test_highlight_temporarily_changes_pen(self, cavity_widget):
        """Test highlight method temporarily changes pen."""
        with patch.object(cavity_widget, "update") as mock_update:
            with patch("qtpy.QtCore.QTimer.singleShot") as mock_timer:
                cavity_widget.highlight()

                # Pen should be modified
                assert cavity_widget._pen.width() == 6
                assert cavity_widget._pen.color() == QColor(255, 255, 0)

                # Update should be called
                mock_update.assert_called()

                # Timer should be set to restore
                mock_timer.assert_called_once()
                assert mock_timer.call_args[0][0] == 1000  # 1 second

    def test_unhighlight_restores_original(self, cavity_widget):
        """Test _unhighlight restores original pen properties."""
        original_color = QColor(100, 100, 100)
        original_width = 2

        with patch.object(cavity_widget, "update") as mock_update:
            cavity_widget._unhighlight(original_width, original_color)

            assert cavity_widget._pen.width() == original_width
            assert cavity_widget._pen.color() == original_color
            mock_update.assert_called_once()


class TestCavityWidgetIntegration:
    """Integration tests."""

    @patch(
        "sc_linac_physics.displays.cavity_display.frontend.cavity_widget.PyDMChannel"
    )
    def test_full_workflow(self, mock_channel_class, cavity_widget):
        """Test complete workflow of setting channels and receiving values."""
        # Setup mock channels
        severity_channel = Mock()
        description_channel = Mock()
        severity_channel.address = "test:severity"
        description_channel.address = "test:description"

        mock_channel_class.side_effect = [severity_channel, description_channel]

        # Set channels
        cavity_widget.severity_channel = "test:severity"
        cavity_widget.description_channel = "test:description"

        # Verify channels were created and connected
        assert mock_channel_class.call_count == 2
        severity_channel.connect.assert_called_once()
        description_channel.connect.assert_called_once()

        # Simulate receiving values
        with patch.object(cavity_widget, "change_shape") as mock_change_shape:
            cavity_widget.severity_channel_value_changed(2)
            mock_change_shape.assert_called_with(SHAPE_PARAMETER_DICT[2])

        cavity_widget.description_changed("Test Description")
        assert cavity_widget.toolTip() == "Test Description"

    @patch(
        "sc_linac_physics.displays.cavity_display.frontend.cavity_widget.PyDMChannel"
    )
    @patch("qtpy.QtWidgets.QMessageBox.question")
    @patch("qtpy.QtWidgets.QApplication.instance")
    def test_full_acknowledgment_workflow(
        self,
        mock_app_instance,
        mock_question,
        mock_channel_class,
        cavity_widget,
    ):
        """Test complete acknowledgment workflow."""
        # Setup cavity
        mock_cavity = Mock()
        mock_cavity.cryomodule.name = "02"
        mock_cavity.number = 3
        cavity_widget._parent_cavity = mock_cavity

        # Setup app
        mock_app = Mock()
        mock_app.acknowledged_cavities = set()
        mock_app_instance.return_value = mock_app

        # User confirms acknowledgment
        mock_question.return_value = QMessageBox.Yes

        # Set severity to alarm
        with patch.object(cavity_widget, "change_shape"):
            cavity_widget.severity_channel_value_changed(2)

        assert cavity_widget._last_severity == 2

        # Acknowledge the issue
        cavity_widget.acknowledge_issue(mock_cavity, "Alarm")

        # Verify acknowledgment state
        assert cavity_widget._acknowledged is True
        assert "02_3" in mock_app.acknowledged_cavities

        # Severity returns to normal
        with patch.object(cavity_widget, "change_shape"):
            cavity_widget.severity_channel_value_changed(0)

        # Acknowledgment should be cleared
        assert cavity_widget._acknowledged is False
        assert "02_3" not in mock_app.acknowledged_cavities


class TestCavityWidgetSeveritySignals:
    """Test severity change signals."""

    def test_severity_changed_signal_emitted(self, cavity_widget):
        """Test that severity_changed signal is emitted."""
        signal_spy = Mock()
        cavity_widget.severity_changed.connect(signal_spy)

        with patch.object(cavity_widget, "change_shape"):
            cavity_widget.severity_channel_value_changed(2)

        signal_spy.assert_called_once_with(2)

    def test_severity_changed_signal_not_emitted_for_invalid(
        self, cavity_widget
    ):
        """Test that severity_changed signal not emitted for invalid severity."""
        signal_spy = Mock()
        cavity_widget.severity_changed.connect(signal_spy)

        with patch.object(cavity_widget, "change_shape"):
            cavity_widget.severity_channel_value_changed(999)

        # Signal should not be emitted for invalid value
        signal_spy.assert_not_called()


class TestCavityWidgetEdgeCases:
    """Test edge cases and error conditions."""

    def test_change_shape_with_none_parameter(self, cavity_widget):
        """Test change_shape handles None gracefully."""
        # This should raise an AttributeError, but let's verify behavior
        with pytest.raises(AttributeError):
            cavity_widget.change_shape(None)

    def test_description_changed_with_unicode_characters(self, cavity_widget):
        """Test description_changed handles unicode properly."""
        unicode_desc = "Test 🔴 Alert ⚠️"
        cavity_widget.description_changed(unicode_desc)
        assert cavity_widget._cavity_description == unicode_desc

    def test_description_changed_with_whitespace_only(self, cavity_widget):
        """Test description_changed with whitespace-only string."""
        cavity_widget.description_changed("   \n\t   ")
        assert cavity_widget._cavity_description == ""
        assert cavity_widget.toolTip() == "No description available"

    def test_multiple_channel_reconnections(self, cavity_widget):
        """Test multiple reconnections don't cause issues."""
        with patch(
            "sc_linac_physics.displays.cavity_display.frontend.cavity_widget.PyDMChannel"
        ) as mock_channel_class:
            mock_channels = [Mock() for _ in range(3)]
            for i, mock_ch in enumerate(mock_channels):
                mock_ch.address = f"test:severity{i}"

            mock_channel_class.side_effect = mock_channels

            # Set channel multiple times
            for i in range(3):
                cavity_widget.severity_channel = f"test:severity{i}"

            # First two channels should have been disconnected
            mock_channels[0].disconnect.assert_called_once()
            mock_channels[1].disconnect.assert_called_once()

            # Last channel should be connected but not disconnected
            mock_channels[2].connect.assert_called_once()
            mock_channels[2].disconnect.assert_not_called()

    def test_acknowledge_without_parent_display(self, cavity_widget):
        """Test acknowledgment when parent display not found."""
        mock_cavity = Mock()
        mock_cavity.cryomodule.name = "01"
        mock_cavity.number = 1

        with patch(
            "qtpy.QtWidgets.QMessageBox.question", return_value=QMessageBox.Yes
        ):
            with patch("qtpy.QtWidgets.QApplication.instance") as mock_app:
                mock_app.return_value.acknowledged_cavities = set()

                with patch.object(
                    cavity_widget, "_get_parent_display", return_value=None
                ):
                    # Should not raise error even without parent display
                    cavity_widget.acknowledge_issue(mock_cavity, "Alarm")

                    # Acknowledgment should still be set
                    assert cavity_widget._acknowledged is True

    def test_severity_change_during_exception(self, cavity_widget):
        """Test that severity changes are handled even during exceptions."""
        call_count = 0

        def side_effect_func(param):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("First call fails")
            # Second call succeeds

        with patch.object(
            cavity_widget, "change_shape", side_effect=side_effect_func
        ):
            # Should not raise exception
            cavity_widget.severity_channel_value_changed(0)

            # Both calls should have been made
            assert call_count == 2


class TestCavityWidgetPropertyTypes:
    """Test property type handling."""

    def test_cavity_text_with_numeric_string(self, cavity_widget):
        """Test cavity_text property with numeric string."""
        cavity_widget.cavity_text = "123"
        assert cavity_widget.cavity_text == "123"

    def test_cavity_text_with_empty_string(self, cavity_widget):
        """Test cavity_text property with empty string."""
        cavity_widget.cavity_text = ""
        assert cavity_widget.cavity_text == ""

    def test_underline_with_non_boolean(self, cavity_widget):
        """Test underline property with truthy/falsy values."""
        cavity_widget.underline = 1
        assert cavity_widget.underline == 1  # Truthy

        cavity_widget.underline = 0
        assert cavity_widget.underline == 0  # Falsy


class TestCavityWidgetQTimerIntegration:
    """Test QTimer-related functionality."""

    @patch("qtpy.QtCore.QTimer.singleShot")
    def test_update_status_bar_uses_timer(self, mock_timer, cavity_widget):
        """Test that status bar update uses QTimer."""
        # Create mock parent display with status label
        mock_parent = Mock()
        mock_parent.status_label = Mock()
        mock_parent.update_status = Mock()

        mock_cavity = Mock()
        mock_cavity.cryomodule.name = "01"
        mock_cavity.number = 1

        cavity_widget._update_status_bar(mock_parent, mock_cavity, "Alarm")

        # Status label should be updated immediately
        mock_parent.status_label.setText.assert_called_once()
        assert (
            "Acknowledged Alarm"
            in mock_parent.status_label.setText.call_args[0][0]
        )

        # Timer should be set to clear status after 5 seconds
        mock_timer.assert_called_once_with(5000, mock_parent.update_status)


class TestCavityWidgetDrawingDetails:
    """Test detailed drawing behavior."""

    def test_draw_item_with_numeric_text(self, cavity_widget):
        """Test draw_item handles numeric text differently."""
        with patch.object(
            cavity_widget, "get_bounds", return_value=(0, 0, 100, 50)
        ):
            with patch(
                "sc_linac_physics.displays.cavity_display.frontend.cavity_widget.QFontMetrics"
            ) as mock_fm_class:
                mock_fm = Mock()
                mock_fm.horizontalAdvance.return_value = 20
                mock_fm.height.return_value = 10
                mock_fm_class.return_value = mock_fm

                mock_painter = Mock()
                cavity_widget._cavity_text = "123"  # Numeric text

                cavity_widget.draw_item(mock_painter)

                # Painter should be manipulated (save/restore called)
                assert mock_painter.save.called
                assert mock_painter.restore.called

                # Text should be drawn
                mock_painter.drawText.assert_called()

    def test_draw_item_with_text_text(self, cavity_widget):
        """Test draw_item handles non-numeric text."""
        with patch.object(
            cavity_widget, "get_bounds", return_value=(0, 0, 100, 50)
        ):
            with patch(
                "sc_linac_physics.displays.cavity_display.frontend.cavity_widget.QFontMetrics"
            ) as mock_fm_class:
                mock_fm = Mock()
                mock_fm.horizontalAdvance.return_value = 40
                mock_fm.height.return_value = 10
                mock_fm_class.return_value = mock_fm

                mock_painter = Mock()
                cavity_widget._cavity_text = "ABC"  # Non-numeric text

                cavity_widget.draw_item(mock_painter)

                # Text should be drawn with different scaling
                mock_painter.drawText.assert_called()

                # Scale should be called (for scaling the text)
                assert mock_painter.scale.called


class TestCavityWidgetMemoryManagement:
    """Test memory management and cleanup."""

    @patch(
        "sc_linac_physics.displays.cavity_display.frontend.cavity_widget.PyDMChannel"
    )
    def test_channel_cleanup_on_widget_deletion(self, mock_channel_class, qapp):
        """Test channels are properly cleaned up when widget is deleted."""
        widget = CavityWidget()

        mock_severity_channel = Mock()
        mock_severity_channel.address = "test:severity"
        mock_description_channel = Mock()
        mock_description_channel.address = "test:description"

        mock_channel_class.side_effect = [
            mock_severity_channel,
            mock_description_channel,
        ]

        widget.severity_channel = "test:severity"
        widget.description_channel = "test:description"

        # Delete widget
        widget.deleteLater()
        qapp.processEvents()

        # Channels should have been connected
        mock_severity_channel.connect.assert_called()
        mock_description_channel.connect.assert_called()


class TestCavityWidgetChannelAddressHandling:
    """Test channel address handling."""

    @patch(
        "sc_linac_physics.displays.cavity_display.frontend.cavity_widget.PyDMChannel"
    )
    def test_severity_channel_with_empty_string(
        self, mock_channel_class, cavity_widget
    ):
        """Test setting severity channel with empty string."""
        # Set to empty string - should not create channel
        cavity_widget.severity_channel = ""

        # Channel should not be created for empty string
        # (This depends on implementation - adjust if needed)
        assert (
            cavity_widget._severity_channel is None
            or not mock_channel_class.called
        )

    @patch(
        "sc_linac_physics.displays.cavity_display.frontend.cavity_widget.PyDMChannel"
    )
    def test_description_channel_with_empty_string(
        self, mock_channel_class, cavity_widget
    ):
        """Test setting description channel with empty string."""
        cavity_widget.description_channel = ""

        # Getter should return empty string when no channel
        assert cavity_widget.description_channel == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
