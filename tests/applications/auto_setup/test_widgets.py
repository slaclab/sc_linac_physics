from PyQt5.QtWidgets import QWidget, QPushButton
from sc_linac_physics.applications.auto_setup.frontend.widgets import FlowLayout


def test_flow_layout_count(qtbot):
    container = QWidget()
    layout = FlowLayout(container)
    layout.addWidget(QPushButton("x"))
    assert layout.count() == 1


def test_flow_layout_item_at(qtbot):
    container = QWidget()
    layout = FlowLayout(container)
    layout.addWidget(QPushButton("x"))
    assert layout.itemAt(0) is not None
    assert layout.itemAt(1) is None


def test_flow_layout_take_at(qtbot):
    container = QWidget()
    layout = FlowLayout(container)
    layout.addWidget(QPushButton("x"))
    item = layout.takeAt(0)
    assert item is not None
    assert layout.count() == 0


def test_flow_layout_has_height_for_width(qtbot):
    layout = FlowLayout()
    assert layout.hasHeightForWidth() is True


def test_flow_layout_height_non_negative(qtbot):
    container = QWidget()
    layout = FlowLayout(container)
    btn = QPushButton("chip")
    btn.setFixedSize(60, 24)
    layout.addWidget(btn)
    assert layout.heightForWidth(400) >= 0
