from random import choice
from unittest.mock import MagicMock, call

import pytest
from PyQt5.QtGui import QColor
from pytestqt.qtbot import QtBot

from sc_linac_physics.applications.quench_processing.quench_gui import QuenchGUI
from sc_linac_physics.applications.quench_processing.quench_worker import (
    QuenchWorker,
)
from sc_linac_physics.utils.qt import make_rainbow
from sc_linac_physics.utils.sc_linac.decarad import Decarad


@pytest.fixture
def gui(monkeypatch):
    from PyQt5.QtWidgets import QWidget
    from unittest.mock import MagicMock

    # Mock QuenchCryomodule BEFORE any imports that use it
    class MockQuenchCryomodule:
        def __init__(self, cryo_name, linac_object):
            self.name = cryo_name
            self.linac = linac_object
            self.logger = MagicMock()
            # Add any other attributes your tests need
            self.cavities = {}
            for i in range(1, 9):  # Assuming 8 cavities per cryomodule
                self.cavities[i] = MagicMock()

    # Patch it everywhere it might be used
    monkeypatch.setattr(
        "sc_linac_physics.applications.quench_processing.quench_cryomodule.QuenchCryomodule",
        MockQuenchCryomodule,
    )
    monkeypatch.setattr(
        "sc_linac_physics.applications.quench_processing.quench_gui.QuenchCryomodule",
        MockQuenchCryomodule,
    )

    # Mock the file handler to prevent any file operations
    def mock_file_handler(*args, **kwargs):
        handler = MagicMock()
        handler.setFormatter = MagicMock()
        return handler

    monkeypatch.setattr("logging.FileHandler", mock_file_handler)

    # Minimal dummy to avoid pyqtgraph/PyDM internals during tests
    class DummyWaveformPlot(QWidget):
        def __init__(self, *a, **k):
            super().__init__()

        def clearCurves(self, *a, **k):
            pass

        def addYChannel(self, *a, **k):
            pass

        def removeChannel(self, *a, **k):
            pass

    # Patch the symbol actually used by QuenchGUI.__init__
    import sc_linac_physics.applications.quench_processing.quench_gui as gui_mod

    monkeypatch.setattr(
        gui_mod, "PyDMWaveformPlot", DummyWaveformPlot, raising=False
    )

    # Now construct the GUI safely
    g = QuenchGUI()
    g.rf_controls = MagicMock()
    g.status_label.setText = MagicMock()
    g.status_label.setStyleSheet = MagicMock()
    g.start_button.setEnabled = MagicMock()

    # Mock the Machine and its components
    g.current_cm = MagicMock()
    g.current_cm.name = "01"
    g.cm_combobox.currentText = MagicMock(return_value="01")

    g.current_cav = MagicMock()
    g.current_cav.number = 1
    g.cav_combobox.currentText = MagicMock(return_value="1")

    g.current_decarad = MagicMock()
    g.decarad_combobox.currentText = MagicMock(return_value="1")

    return g


def test_handle_status(qtbot: QtBot, gui):
    qtbot.addWidget(gui)
    msg = "Testing handle status"
    gui.handle_status(msg)
    gui.status_label.setStyleSheet.assert_called_with("color: blue;")
    gui.status_label.setText.assert_called_with(msg)


def test_handle_error(qtbot, gui):
    qtbot.addWidget(gui)
    msg = "Testing handle error"
    gui.handle_error(msg)
    gui.status_label.setStyleSheet.assert_called_with("color: red;")
    gui.status_label.setText.assert_called_with(msg)
    gui.start_button.setEnabled.assert_called_with(True)


def test_handle_finished(qtbot, gui):
    qtbot.addWidget(gui)
    msg = "Testing handle finished"
    gui.handle_finished(msg)
    gui.status_label.setStyleSheet.assert_called_with("color: green;")
    gui.status_label.setText.assert_called_with(msg)
    gui.start_button.setEnabled.assert_called_with(True)


def test_process(qtbot, gui):
    qtbot.addWidget(gui)
    gui.current_decarad = Decarad(choice([1, 2]))
    gui.make_quench_worker = MagicMock()
    gui.quench_worker = MagicMock()
    gui.process()
    gui.start_button.setEnabled.assert_called_with(False)
    assert gui.current_cav.decarad == gui.current_decarad
    gui.make_quench_worker.assert_called()
    gui.quench_worker.start.assert_called()


def test_make_quench_worker(qtbot: QtBot, gui):
    qtbot.addWidget(gui)
    gui.quench_worker = None
    gui.make_quench_worker()
    assert isinstance(gui.quench_worker, QuenchWorker)


def test_clear_connections(qtbot: QtBot, gui):
    qtbot.addWidget(gui)
    signal = MagicMock()
    gui.clear_connections(signal)
    signal.disconnect.assert_called()


def test_clear_all_connections(qtbot: QtBot, gui):
    qtbot.addWidget(gui)
    gui.rf_controls = MagicMock()
    gui.clear_connections = MagicMock()
    gui.clear_all_connections()


def test_update_timeplot(qtbot: QtBot, gui):
    qtbot.addWidget(gui)
    gui.update_cm = MagicMock()
    gui.amp_rad_timeplot = MagicMock()
    gui.update_decarad = MagicMock()
    gui.update_timeplot()
    gui.amp_rad_timeplot.clearCurves.assert_called()
    gui.amp_rad_timeplot.addYChannel.assert_called()

    colors = make_rainbow(num_colors=11)
    channels = [gui.current_cav.aact_pv] + [
        head.raw_dose_rate_pv for head in gui.current_decarad.heads.values()
    ]
    axes = ["Amplitude"] + ["Radiation" for _ in range(10)]
    calls = []
    for channel, (r, g, b, a), axis in zip(channels, colors, axes):
        calls.append(
            call(
                y_channel=channel,
                useArchiveData=True,
                color=QColor(r, g, b, a),
                yAxisName=axis,
            )
        )
    gui.amp_rad_timeplot.addYChannel.assert_has_calls(calls, any_order=True)


def test_update_decarad(qtbot: QtBot, gui):
    qtbot.addWidget(gui)
    gui.update_timeplot = MagicMock()
    gui.clear_connections = MagicMock()
    gui.decarad_on_button.clicked = MagicMock()
    gui.decarad_off_button.clicked = MagicMock()
    gui.decarad_combobox.currentText = MagicMock(return_value="1")

    gui.update_decarad()

    assert gui.current_decarad == Decarad(1)
    gui.update_timeplot.assert_called()
    gui.clear_connections.assert_called()
    gui.decarad_on_button.clicked.connect.assert_called_with(
        gui.current_decarad.turn_on
    )
    gui.decarad_off_button.clicked.connect.assert_called_with(
        gui.current_decarad.turn_off
    )
    assert (
        gui.current_decarad.power_status_pv
        == gui.decarad_status_readback.channel
    )
    assert (
        gui.current_decarad.voltage_readback_pv
        == gui.decarad_voltage_readback.channel
    )


def test_update_cm(qtbot: QtBot, gui):
    qtbot.addWidget(gui)
    gui.clear_all_connections = MagicMock()
    gui.update_timeplot = MagicMock()
    gui.waveform_updater.updatePlot = MagicMock()
    gui.start_button = MagicMock()
    gui.abort_button = MagicMock()

    gui.update_cm()
    gui.clear_all_connections.assert_called()
    gui.update_timeplot.assert_called()
    gui.waveform_updater.updatePlot.assert_called()
    cavity = gui.current_cav
    gui.rf_controls.ssa_on_button.clicked.connect.assert_called_with(
        cavity.ssa.turn_on
    )
    gui.rf_controls.ssa_off_button.clicked.connect.assert_called_with(
        cavity.ssa.turn_off
    )
    assert gui.rf_controls.ssa_readback_label.channel == cavity.ssa.status_pv

    assert gui.rf_controls.rf_mode_combobox.channel == cavity.rf_mode_ctrl_pv
    assert gui.rf_controls.rf_mode_readback_label.channel == cavity.rf_mode_pv
    gui.rf_controls.rf_on_button.clicked.connect.assert_called_with(
        cavity.turn_on
    )
    gui.rf_controls.rf_off_button.clicked.connect.assert_called_with(
        cavity.turn_off
    )
    assert (
        gui.rf_controls.rf_status_readback_label.channel == cavity.rf_state_pv
    )

    assert gui.rf_controls.ades_spinbox.channel == cavity.ades_pv
    assert gui.rf_controls.aact_readback_label.channel == cavity.aact_pv
    assert gui.rf_controls.srf_max_spinbox.channel == cavity.srf_max_pv
    assert gui.rf_controls.srf_max_readback_label.channel == cavity.srf_max_pv

    gui.start_button.clicked.connect.assert_called_with(gui.process)
    gui.abort_button.clicked.connect.assert_called_with(cavity.request_abort)
