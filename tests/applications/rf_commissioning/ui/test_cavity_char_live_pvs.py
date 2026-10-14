"""Tests for the live PV readouts on the Cavity Characterization display."""

from unittest.mock import Mock

import pytest
from pydm.widgets import PyDMLabel
from PyQt5.QtWidgets import QWidget

from sc_linac_physics.applications.rf_commissioning.ui.builders import (
    CavityCharUI,
)
from sc_linac_physics.applications.rf_commissioning.ui.controllers.cavity_char_controller import (  # noqa: E501
    CavityCharController,
)

# Widget name -> the Cavity attribute holding the PV it shows.
LIVE_PVS = {
    "pydm_char_status": "characterization_status_pv",  # PROBECALSTS
    "pydm_char_timestamp": "char_timestamp_pv",  # PROBECALTS
    "pydm_loaded_q_new": "measured_loaded_q_pv",  # QLOADED_NEW
    "pydm_loaded_q_current": "current_q_loaded_pv",  # QLOADED
    "pydm_scale_new": "measured_scale_factor_pv",  # CAV:CAL_SCALEB_NEW
    "pydm_scale_current": "current_cavity_scale_pv",  # CAV:SCALER_SEL.B
    "pydm_probe_q_new": "measured_probe_q_pv",  # QPROBE_CALC2
    "pydm_drive_level": "drive_level_pv",  # SEL_ASET
    "pydm_rf_state": "rf_state_pv",  # RFSTATE
}


def test_live_readouts_are_pydm_labels(qapp_global):
    ui = CavityCharUI(QWidget(), callbacks={})
    ui.build()
    for name in LIVE_PVS:
        assert isinstance(ui.widgets[name], PyDMLabel), name


@pytest.fixture
def cavity():
    c = Mock()
    c.loaded_q_lower_limit = 3.0e7
    c.loaded_q_upper_limit = 7.0e7
    for attr in LIVE_PVS.values():
        setattr(c, attr, f"ACCL:L0B:0110:{attr}")
    return c


def test_selecting_a_cavity_points_each_readout_at_its_pv(cavity, monkeypatch):
    view = Mock()
    c = CavityCharController(view, Mock())
    monkeypatch.setattr(c, "_get_machine_cavity", lambda cm, cav: cavity)
    monkeypatch.setattr(
        "sc_linac_physics.applications.rf_commissioning.ui.controllers."
        "cavity_char_controller.resolve_cavity_selection",
        lambda v, cm, cav: ("01", "1"),
    )
    c.update_pv_addresses("01", "1")
    for widget, attr in LIVE_PVS.items():
        assert getattr(view, widget).channel == f"ca://ACCL:L0B:0110:{attr}"


def test_side_by_side_boxes_share_their_edges(qtbot):
    """Review and Push lines up with Live PVs; inputs end with Stored Data."""
    from PyQt5.QtWidgets import QGroupBox

    host = QWidget()
    qtbot.addWidget(host)
    host.setLayout(CavityCharUI(host, callbacks={}).build())
    host.resize(1300, 900)
    host.show()
    qtbot.waitExposed(host)

    boxes = {b.title(): b.geometry() for b in host.findChildren(QGroupBox)}
    review, live = boxes["Review and Push"], boxes["Live PVs"]
    assert (review.top(), review.bottom()) == (live.top(), live.bottom())
    assert (
        boxes["Cavity Characterization"].bottom()
        == boxes["Stored Data"].bottom()
    )
