from datetime import datetime, timedelta
from random import randint, choice
from unittest.mock import MagicMock

import pytest
from PyQt5.QtCore import QDateTime
from pytestqt.qtbot import QtBot

from sc_linac_physics.displays.cavity_display.backend.backend_machine import (
    BackendMachine,
)
from sc_linac_physics.displays.cavity_display.backend.fault import FaultCounter
from sc_linac_physics.displays.cavity_display.frontend.fault_count_display import (
    FaultCountDisplay,
)

non_hl_iterator = BackendMachine(lazy_fault_pvs=True).non_hl_iterator


@pytest.fixture
def window():
    yield FaultCountDisplay(lazy_fault_pvs=True)


def test_get_data_no_data(qtbot: QtBot, window):
    qtbot.addWidget(window)

    start = datetime.now().replace(microsecond=0) - timedelta(days=1)
    start_qt = QDateTime.fromSecsSinceEpoch(int(start.timestamp()))

    end = datetime.now().replace(microsecond=0)
    end_qt = QDateTime.fromSecsSinceEpoch(int(end.timestamp()))

    window.start_selector.setDateTime(start_qt)
    window.end_selector.setDateTime(end_qt)

    window.cavity = next(non_hl_iterator)
    window.cavity.get_fault_counts = MagicMock()
    window.get_data()
    window.cavity.get_fault_counts.assert_called_with(start, end)
    assert window.y_data == []
    assert window.num_faults == []
    assert window.num_invalids == []


def test_get_data(qtbot: QtBot, window):
    qtbot.addWidget(window)

    q_dt = QDateTime.fromSecsSinceEpoch(int(datetime.now().timestamp()))
    window.start_selector.setDateTime(q_dt)
    window.end_selector.setDateTime(q_dt)

    window.cavity = next(non_hl_iterator)
    faults = randint(0, 100)
    invalids = randint(0, 100)
    tlc = choice(FaultCountDisplay.fault_tlc_list)
    result = {tlc: FaultCounter(alarm_count=faults, invalid_count=invalids)}
    window.cavity.get_fault_counts = MagicMock(return_value=result)
    window.get_data()
    window.cavity.get_fault_counts.assert_called()
    assert window.y_data == [tlc]
    assert window.num_faults == [faults]
    assert window.num_invalids == [invalids]


def test_get_data_with_tlc_omitted(qtbot: QtBot, window):
    qtbot.addWidget(window)

    q_dt = QDateTime.fromSecsSinceEpoch(int(datetime.now().timestamp()))
    window.start_selector.setDateTime(q_dt)
    window.end_selector.setDateTime(q_dt)

    tlc = choice(FaultCountDisplay.fault_tlc_list)
    window.hide_fault_combo_box.setCurrentText(tlc)

    window.cavity = next(non_hl_iterator)
    faults = randint(0, 100)
    invalids = randint(0, 100)
    result = {tlc: FaultCounter(alarm_count=faults, invalid_count=invalids)}
    window.cavity.get_fault_counts = MagicMock(return_value=result)
    window.get_data()
    window.cavity.get_fault_counts.assert_called()
    assert window.y_data == []
    assert window.num_faults == []
    assert window.num_invalids == []


def test_update_plot(qtbot: QtBot, window):
    # TODO test the actual plot contents

    qtbot.addWidget(window)

    window.cavity = next(non_hl_iterator)
    window.plot_window.clear = MagicMock()

    faults = randint(0, 100)
    invalids = randint(0, 100)
    tlc = choice(FaultCountDisplay.fault_tlc_list)
    result = {tlc: FaultCounter(alarm_count=faults, invalid_count=invalids)}
    window.cavity.get_fault_counts = MagicMock(return_value=result)

    window.update_plot()
    window.plot_window.clear.assert_called()
    window.cavity.get_fault_counts.assert_called()
