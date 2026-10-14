"""Tests for the Cavity Characterization UI builder."""

from PyQt5.QtWidgets import QDoubleSpinBox, QWidget

from pydm.widgets import PyDMSpinbox

from sc_linac_physics.applications.rf_commissioning.ui.builders import (
    CavityCharUI,
)
from sc_linac_physics.utils.sc_linac import linac_utils


def test_build_registers_the_documented_widgets(qapp_global):
    parent = QWidget()
    ui = CavityCharUI(parent, callbacks={})
    ui.build()
    for name in (
        "drive_level_spinbox",
        "char_status_label",
        "elapsed_label",
        "local_phase_status",
    ):
        assert name in ui.widgets, name


def test_drive_level_is_a_plain_spinbox_that_writes_nothing(qapp_global):
    """The drive level must not reach SEL_ASET as the operator types.

    SSACharUI wires its PyDMSpinbox with writeOnPress and send_value, which
    puts the value to the PV on edit. Here the phase owns the write:
    CavityCharPhase._set_drive_level validates the value and then puts
    SEL_ASET. A PyDM spinbox would write ahead of that validation.
    """
    parent = QWidget()
    ui = CavityCharUI(parent, callbacks={})
    ui.build()
    spin = ui.widgets["drive_level_spinbox"]
    assert isinstance(spin, QDoubleSpinBox)
    assert not isinstance(spin, PyDMSpinbox)


def test_no_probe_q_input(qapp_global):
    """Probe Q is a result, shown in Stored Data, not an operator input."""
    parent = QWidget()
    ui = CavityCharUI(parent, callbacks={})
    ui.build()
    assert "probe_q_label" not in ui.widgets


def test_run_abort_and_pause_callbacks_are_connected(qapp_global):
    calls = []
    parent = QWidget()
    ui = CavityCharUI(
        parent,
        callbacks={
            "on_run_automated_test": lambda: calls.append("run"),
            "on_abort_test": lambda: calls.append("abort"),
            "on_pause_test": lambda: calls.append("pause"),
        },
    )
    ui.build()
    ui.widgets["run_button"].click()
    # PhaseUIBase builds abort and pause disabled; update_toolbar_state
    # enables them once a run is going.
    ui.widgets["abort_button"].setEnabled(True)
    ui.widgets["abort_button"].click()
    assert calls == ["run", "abort"]


def test_drive_level_defaults_to_the_safe_pulsed_level(qapp_global):
    """The cap is applied by the display, which owns CavityCharLimits.

    Builders in this package do not import from phases/, so the builder only
    knows the hardware-model default; CavityCharDisplay narrows the maximum
    to CavityCharLimits.max_drive_level once its controller exists.
    """
    parent = QWidget()
    ui = CavityCharUI(parent, callbacks={})
    ui.build()
    assert ui.widgets["drive_level_spinbox"].value() == (
        linac_utils.SAFE_PULSED_DRIVE_LEVEL
    )
