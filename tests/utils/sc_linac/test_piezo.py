from random import randint
from unittest.mock import MagicMock, Mock

import pytest
from lcls_tools.common.controls.pyepics.utils import make_mock_pv

from tests.utils.mock_utils import mock_func
from utils.sc_linac.cavity import Cavity
from utils.sc_linac.linac_utils import (
    PIEZO_ENABLE_VALUE,
    PIEZO_DISABLE_VALUE,
    PIEZO_MANUAL_VALUE,
    PIEZO_FEEDBACK_VALUE,
)
from utils.sc_linac.piezo import Piezo


@pytest.fixture
def piezo(monkeypatch):
    monkeypatch.setattr("time.sleep", mock_func)
    cavity = Cavity(cavity_num=randint(1, 8), rack_object=MagicMock())
    yield Piezo(cavity)


def test_pv_prefix(piezo):
    assert piezo.pv_prefix == f"{piezo.cavity.pv_prefix}PZT:"


def test_voltage(piezo):
    val = randint(-50, 50)
    piezo._voltage_pv_obj = make_mock_pv(get_val=val)
    assert piezo.voltage == val


def test_bias_voltage(piezo):
    val = randint(-50, 50)
    piezo._bias_voltage_pv_obj = make_mock_pv(get_val=val)
    assert piezo.bias_voltage == val


def test_dc_setpoint(piezo):
    val = randint(-50, 50)
    piezo._dc_setpoint_pv_obj = make_mock_pv(get_val=val)
    assert piezo.dc_setpoint == val


def test_feedback_setpoint(piezo):
    val = randint(-50, 50)
    piezo._feedback_setpoint_pv_obj = make_mock_pv(get_val=val)
    assert piezo.feedback_setpoint == val


def test_is_enabled(piezo):
    piezo._enable_stat_pv_obj = make_mock_pv(get_val=PIEZO_ENABLE_VALUE)
    assert piezo.is_enabled


def test_is_not_enabled(piezo):
    piezo._enable_stat_pv_obj = make_mock_pv(get_val=PIEZO_DISABLE_VALUE)
    assert not piezo.is_enabled


def test_feedback_stat(piezo):
    stat = randint(0, 1)
    piezo._feedback_stat_pv_obj = make_mock_pv(get_val=stat)
    assert piezo.feedback_stat == stat


def test_in_manual(piezo):
    piezo._feedback_stat_pv_obj = make_mock_pv(get_val=PIEZO_MANUAL_VALUE)
    assert piezo.in_manual


def test_not_in_manual(piezo):
    piezo._feedback_stat_pv_obj = make_mock_pv(get_val=PIEZO_FEEDBACK_VALUE)
    assert not piezo.in_manual


def test_set_to_feedback(piezo):
    piezo._feedback_control_pv_obj = make_mock_pv()
    piezo.set_to_feedback()
    piezo._feedback_control_pv_obj.put.assert_called_with(PIEZO_FEEDBACK_VALUE)


def test_set_to_manual(piezo):
    piezo._feedback_control_pv_obj = make_mock_pv()
    piezo.set_to_manual()
    piezo._feedback_control_pv_obj.put.assert_called_with(PIEZO_MANUAL_VALUE)


class MockStatus:
    def __init__(self):
        self.num_calls = 0

    def mock_status(self, *args):
        if self.num_calls < 1:
            self.num_calls += 1
            return PIEZO_DISABLE_VALUE
        else:
            self.num_calls = 0
            return PIEZO_ENABLE_VALUE


def test_enable(piezo):
    piezo._bias_voltage_pv_obj = make_mock_pv()
    piezo._enable_stat_pv_obj = make_mock_pv()
    mock_status = MockStatus()
    piezo._enable_stat_pv_obj.get = mock_status.mock_status
    piezo.cavity.check_abort = make_mock_pv()
    piezo._enable_pv_obj = make_mock_pv()

    piezo.enable()
    piezo._bias_voltage_pv_obj.put.assert_called_with(25)
    piezo.cavity.check_abort.assert_called()
    piezo._enable_pv_obj.put.assert_called_with(PIEZO_ENABLE_VALUE)


def test_enable_feedback(piezo):
    piezo.enable = MagicMock()
    piezo._feedback_stat_pv_obj = make_mock_pv(get_val=PIEZO_MANUAL_VALUE)

    def set_feedback():
        piezo._feedback_stat_pv_obj = make_mock_pv(get_val=PIEZO_FEEDBACK_VALUE)

    piezo.set_to_feedback = Mock(side_effect=set_feedback)
    piezo.set_to_manual = MagicMock()

    piezo.enable_feedback()
    piezo.enable.assert_called()
    piezo.set_to_feedback.assert_called()


def test_disable_feedback(piezo):
    piezo.enable = MagicMock()
    piezo._feedback_stat_pv_obj = make_mock_pv(get_val=PIEZO_FEEDBACK_VALUE)

    def set_manual():
        piezo._feedback_stat_pv_obj = make_mock_pv(get_val=PIEZO_MANUAL_VALUE)

    piezo.set_to_manual = Mock(side_effect=set_manual)
    piezo.set_to_feedback = MagicMock()

    piezo.disable_feedback()
    piezo.enable.assert_called()
    piezo.set_to_manual.assert_called()


def test_hz_per_v(piezo):
    gain = randint(0, 40)
    piezo._hz_per_v_pv_obj = make_mock_pv(get_val=gain)
    assert piezo.hz_per_v == gain
