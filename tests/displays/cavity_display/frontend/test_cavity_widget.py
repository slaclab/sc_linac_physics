import sys
from random import choice
from unittest import TestCase
from unittest.mock import MagicMock

from PyQt5.QtCore import Qt, QPoint, QRect, QSize
from PyQt5.QtWidgets import QApplication

from displays.cavity_display.frontend.cavity_widget import (
    CavityWidget,
    SHAPE_PARAMETER_DICT,
)

if not QApplication.instance():
    app = QApplication(sys.argv)
else:
    app = QApplication.instance()


class TestCavityWidget(TestCase):
    def setUp(self):
        self.cavity_widget: CavityWidget = CavityWidget()
        self.cavity_widget.clicked = MagicMock()
        self.cavity_widget.clicked.emit = MagicMock()
        self.test_str = "this is a test string"
        self.test_addr = "this is a test address"

    def tearDown(self) -> None:
        app.closeAllWindows()

    def test_mouse_release_event(self):
        event = MagicMock()
        event.button = MagicMock(return_value=Qt.LeftButton)
        q_point = QPoint(100, 200)
        rect = QRect(q_point, QSize(11, 16))
        self.cavity_widget.rect = MagicMock(return_value=rect)

        event.pos = MagicMock(return_value=q_point)
        self.cavity_widget.press_pos = MagicMock(return_value=q_point)
        self.cavity_widget.mouseReleaseEvent(event)
        self.cavity_widget.clicked.emit.assert_called()

    def test_cavity_text(self):
        self.cavity_widget.cavity_text = self.test_str
        self.assertEqual(self.cavity_widget.cavity_text, self.test_str)

    def test_description_channel(self):
        self.cavity_widget.description_channel = self.test_addr
        self.assertEqual(self.cavity_widget.description_channel, self.test_addr)

    def test_description_changed(self):
        self.cavity_widget.setToolTip = MagicMock()

        val = [ord(c) for c in self.test_str]
        self.cavity_widget.description_changed(val)
        self.cavity_widget.setToolTip.assert_called_with(self.test_str)

    def test_severity_channel(self):
        self.cavity_widget.severity_channel = self.test_addr
        self.assertEqual(self.cavity_widget.severity_channel, self.test_addr)

    def test_severity_channel_value_changed(self):
        key, shape_param_obj = choice(list(SHAPE_PARAMETER_DICT.items()))
        cavity_widget = CavityWidget()
        cavity_widget.change_shape = MagicMock()
        cavity_widget.severity_channel_value_changed(key)
        cavity_widget.change_shape.assert_called_with(shape_param_obj)

    def test_change_shape(self):
        key, shape_param_obj = choice(list(SHAPE_PARAMETER_DICT.items()))
        cavity_widget = CavityWidget()
        cavity_widget.brush.setColor = MagicMock()
        cavity_widget.update = MagicMock()
        cavity_widget.change_shape(shape_param_obj)
        cavity_widget.brush.setColor.assert_called_with(shape_param_obj.fillColor)
        self.assertEqual(cavity_widget.penColor, shape_param_obj.borderColor)
        self.assertEqual(cavity_widget.numberOfPoints, shape_param_obj.numPoints)
        self.assertEqual(cavity_widget.rotation, shape_param_obj.rotation)
        cavity_widget.update.assert_called()

    def test_underline(self):
        self.cavity_widget.underline = True
        self.assertTrue(self.cavity_widget.underline)

    def test_value_changed(self):
        cavity_widget = CavityWidget()
        cavity_widget.update = MagicMock()
        cavity_widget.value_changed(self.test_str)
        self.assertEqual(cavity_widget.cavity_text, self.test_str)
        cavity_widget.update.assert_called()
