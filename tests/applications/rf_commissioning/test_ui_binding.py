from unittest.mock import patch

import pytest
from PyQt5.QtWidgets import QApplication, QWidget

from sc_linac_physics.applications.rf_commissioning.ui.phase_displays import (
    PiezoPreRFDisplay,
)
from sc_linac_physics.applications.rf_commissioning.ui import PiezoPreRFUI


@pytest.fixture
def qapp():
    """QApplication fixture."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_ui_builder_registers_widgets(qapp):
    parent = QWidget()
    ui = PiezoPreRFUI(parent, callbacks={})
    layout = ui.build()

    assert layout is not None
    for name in (
        "cm_spinbox",
        "cav_spinbox",
        "run_button",
        "save_button",
        "db_button",
        "pv_overall",
        "local_overall_result",
        "local_progress_bar",
    ):
        assert name in ui.widgets


def test_display_binds_widgets(qapp):
    class DummyController:
        def __init__(self, view, session):
            self.view = view

        def setup_pv_connections(self):
            pass

        def on_run_automated_test(self):
            pass

        def on_abort(self):
            pass

        def on_save_report(self):
            pass

        def on_view_database(self):
            pass

    with patch(
        "sc_linac_physics.applications.rf_commissioning.ui.phase_displays.PiezoPreRFController",
        DummyController,
    ):
        display = PiezoPreRFDisplay()
        assert display.cm_spinbox is not None
        assert display.cav_spinbox is not None
        assert display.pv_overall is not None
        assert display.local_progress_bar is not None
        assert display.run_button is not None
