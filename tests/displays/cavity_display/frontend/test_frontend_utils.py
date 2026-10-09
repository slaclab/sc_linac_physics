from unittest.mock import Mock

from PyQt5.QtWidgets import QLabel

from sc_linac_physics.displays.cavity_display.frontend.utils import EnumLabel
from sc_linac_physics.utils.epics import PVInvalidError


def _label(qtbot, faulted):
    fault = Mock(pv="TEST:FAULT")
    fault.is_currently_faulted = faulted
    code_label = QLabel()
    label = EnumLabel(fault=fault, code_label=code_label)
    qtbot.addWidget(label)
    qtbot.addWidget(code_label)
    return label


def test_invalid_fault_pv_shows_invalid(qtbot):
    """Fault.is_currently_faulted raises our PVInvalidError; it must be caught."""
    label = _label(qtbot, Mock(side_effect=PVInvalidError("TEST:FAULT")))

    label.value_changed(0)

    assert label.text() == "INVALID"


def test_faulted_and_ok(qtbot):
    label = _label(qtbot, Mock(return_value=True))
    label.value_changed(1)
    assert label.text() == "FAULTED"

    label.fault.is_currently_faulted = Mock(return_value=False)
    label.value_changed(0)
    assert label.text() == "OK"
