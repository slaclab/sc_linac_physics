import sys
from unittest.mock import Mock, patch

import numpy as np
import pytest
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

    def test_mouse_press_event_right_button(self, cavity_widget):
        """Test mouse press event with right button doesn't set press_pos."""
        event = QMouseEvent(
            QMouseEvent.MouseButtonPress,
            QPoint(10, 10),
            Qt.RightButton,
            Qt.RightButton,
            Qt.NoModifier,
        )
        cavity_widget.mousePressEvent(event)
        assert cavity_widget.press_pos is None

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

    def test_severity_channel_value_changed_invalid_value(self, cavity_widget):
        """Test severity channel handler with invalid value falls back to default."""
        with patch.object(cavity_widget, "change_shape") as mock_change_shape:
            cavity_widget.severity_channel_value_changed(999)  # Invalid value
            mock_change_shape.assert_called_with(SHAPE_PARAMETER_DICT[3])

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


class TestCavityWidgetShapeChanging:
    """Test shape changing functionality."""

    def test_change_shape(self, cavity_widget):
        """Test change_shape method."""
        test_params = ShapeParameters(
            fillColor=RED_FILL_COLOR,
            borderColor=BLACK_TEXT_COLOR,
            numPoints=6,
            rotation=45,
        )

        # Test without mocking update to avoid complications with multiple calls
        cavity_widget.change_shape(test_params)

        # Verify all properties were set correctly
        assert cavity_widget.brush.color() == RED_FILL_COLOR
        assert cavity_widget.penColor == BLACK_TEXT_COLOR
        assert cavity_widget.numberOfPoints == 6
        assert cavity_widget.rotation == 45

    def test_change_shape_calls_update_at_end(self, cavity_widget):
        """Test that change_shape calls update method."""
        test_params = ShapeParameters(
            fillColor=RED_FILL_COLOR,
            borderColor=BLACK_TEXT_COLOR,
            numPoints=6,
            rotation=45,
        )

        with patch.object(cavity_widget, "update") as mock_update:
            cavity_widget.change_shape(test_params)

            # Just verify that update was called - don't care about count
            # since property setters might also call update
            assert mock_update.called
            assert mock_update.call_count >= 1


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
    """Test drawing functionality - simplified version."""

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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
