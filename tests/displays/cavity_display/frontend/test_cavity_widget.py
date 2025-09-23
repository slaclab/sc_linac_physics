from random import choice
from unittest.mock import MagicMock

import pytest
from PyQt5.QtCore import Qt, QPoint, QRect, QSize
from pytestqt.qtbot import QtBot

from sc_linac_physics.displays.cavity_display.frontend.cavity_widget import CavityWidget, SHAPE_PARAMETER_DICT

test_str = "this is a test string"
test_addr = "this is a test address"


@pytest.fixture
def cavity_widget():
    cavity_widget: CavityWidget = CavityWidget()
    cavity_widget.clicked = MagicMock()
    cavity_widget.clicked.emit = MagicMock()
    return cavity_widget


def test_mouse_release_event(qtbot: QtBot, cavity_widget):
    qtbot.addWidget(cavity_widget)
    event = MagicMock()
    event.button = MagicMock(return_value=Qt.LeftButton)
    q_point = QPoint(100, 200)
    rect = QRect(q_point, QSize(11, 16))
    cavity_widget.rect = MagicMock(return_value=rect)

    event.pos = MagicMock(return_value=q_point)
    cavity_widget.press_pos = MagicMock(return_value=q_point)
    cavity_widget.mouseReleaseEvent(event)
    cavity_widget.clicked.emit.assert_called()


def test_cavity_text(qtbot: QtBot, cavity_widget):
    qtbot.addWidget(cavity_widget)
    cavity_widget.cavity_text = test_str
    assert cavity_widget.cavity_text == test_str


def test_description_channel(qtbot: QtBot, cavity_widget):
    qtbot.addWidget(cavity_widget)
    cavity_widget.description_channel = test_addr
    assert cavity_widget.description_channel == test_addr


def test_description_changed(qtbot: QtBot, cavity_widget):
    qtbot.addWidget(cavity_widget)
    cavity_widget.setToolTip = MagicMock()
    val = [ord(c) for c in test_str]
    cavity_widget.description_changed(val)
    cavity_widget.setToolTip.assert_called_with(test_str)


def test_severity_channel(qtbot: QtBot, cavity_widget):
    qtbot.addWidget(cavity_widget)
    cavity_widget.severity_channel = test_addr
    assert cavity_widget.severity_channel == test_addr


def test_severity_channel_value_changed(qtbot: QtBot, cavity_widget):
    qtbot.addWidget(cavity_widget)
    key, shape_param_obj = choice(list(SHAPE_PARAMETER_DICT.items()))
    cavity_widget.change_shape = MagicMock()
    cavity_widget.severity_channel_value_changed(key)
    cavity_widget.change_shape.assert_called_with(shape_param_obj)


def test_change_shape(qtbot: QtBot, cavity_widget):
    qtbot.addWidget(cavity_widget)
    key, shape_param_obj = choice(list(SHAPE_PARAMETER_DICT.items()))
    cavity_widget.brush.setColor = MagicMock()
    cavity_widget.update = MagicMock()
    cavity_widget.change_shape(shape_param_obj)
    cavity_widget.brush.setColor.assert_called_with(shape_param_obj.fillColor)
    assert cavity_widget.penColor == shape_param_obj.borderColor
    assert cavity_widget.numberOfPoints == shape_param_obj.numPoints
    assert cavity_widget.rotation == shape_param_obj.rotation
    cavity_widget.update.assert_called()


def test_underline(qtbot: QtBot, cavity_widget):
    qtbot.addWidget(cavity_widget)
    cavity_widget.underline = True
    assert cavity_widget.underline


def test_value_changed(qtbot: QtBot, cavity_widget):
    qtbot.addWidget(cavity_widget)
    cavity_widget = CavityWidget()
    cavity_widget.update = MagicMock()
    cavity_widget.value_changed(test_str)
    assert cavity_widget.cavity_text == test_str
    cavity_widget.update.assert_called()
