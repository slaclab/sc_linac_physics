from random import randint, choice
from unittest.mock import MagicMock

import pytest
from lcls_tools.common.controls.pyepics.utils import make_mock_pv

from sc_linac_physics.utils.sc_linac.cavity import Cavity
from sc_linac_physics.utils.sc_linac.linac_utils import (
    StepperAbortError,
    STEPPER_ON_LIMIT_SWITCH_VALUE,
    DEFAULT_STEPPER_MAX_STEPS,
    DEFAULT_STEPPER_SPEED,
    ALL_CRYOMODULES,
)
from sc_linac_physics.utils.sc_linac.stepper import StepperTuner
from tests.mock_utils import mock_func


@pytest.fixture
def stepper(monkeypatch):
    monkeypatch.setattr("time.sleep", mock_func)
    rack = MagicMock()
    rack.cryomodule.name = choice(ALL_CRYOMODULES)
    rack.cryomodule.linac.name = f"L{randint(0, 3)}B"
    cavity = Cavity(cavity_num=randint(1, 8), rack_object=rack)
    cavity.logger = MagicMock()  # Mock the logger

    yield StepperTuner(cavity=cavity)


def test_pv_prefix(stepper):
    assert stepper.pv_prefix == stepper.cavity.pv_prefix + "STEP:"


def test_hz_per_microstep(stepper):
    step_scale = randint(-5, 5)
    stepper._hz_per_microstep_pv_obj = make_mock_pv(get_val=step_scale)
    assert stepper.hz_per_microstep == abs(step_scale)


def test_check_abort(stepper):
    stepper.cavity.check_abort = MagicMock()

    stepper.abort = MagicMock()
    stepper.abort_flag = False
    try:
        stepper.check_abort()
        stepper.cavity.check_abort.assert_called()
    except StepperAbortError:
        assert False

    stepper.abort_flag = True
    with pytest.raises(StepperAbortError):
        stepper.check_abort()


def test_abort(stepper):
    stepper._abort_pv_obj = make_mock_pv()
    stepper.abort()
    stepper._abort_pv_obj.put.assert_called_with(1)


def test_move_positive(stepper):
    stepper._move_pos_pv_obj = make_mock_pv()
    stepper.move_positive()
    stepper._move_pos_pv_obj.put.assert_called_with(1, wait=False)


def test_move_negative(stepper):
    stepper._move_neg_pv_obj = make_mock_pv()
    stepper.move_negative()
    stepper._move_neg_pv_obj.put.assert_called_with(1, wait=False)


def test_step_des(stepper):
    step_des = randint(0, 10000000)
    stepper._step_des_pv_obj = make_mock_pv(get_val=step_des)
    assert stepper.step_des == step_des


def test_motor_moving(stepper):
    stepper._motor_moving_pv_obj = make_mock_pv(get_val=1)
    assert stepper.motor_moving

    stepper._motor_moving_pv_obj = make_mock_pv(get_val=0)
    assert not (stepper.motor_moving)


def test_reset_signed_steps(stepper):
    stepper._reset_signed_pv_obj = make_mock_pv()
    stepper.reset_signed_steps()
    stepper._reset_signed_pv_obj.put.assert_called_with(0)


def test_on_limit_switch_a(stepper):
    stepper._limit_switch_a_pv_obj = make_mock_pv(
        get_val=STEPPER_ON_LIMIT_SWITCH_VALUE
    )
    stepper._limit_switch_b_pv_obj = make_mock_pv(
        get_val=STEPPER_ON_LIMIT_SWITCH_VALUE + 1
    )
    assert stepper.on_limit_switch


def test_on_limit_switch_b(stepper):
    stepper._limit_switch_a_pv_obj = make_mock_pv(
        get_val=STEPPER_ON_LIMIT_SWITCH_VALUE + 1
    )
    stepper._limit_switch_b_pv_obj = make_mock_pv(
        get_val=STEPPER_ON_LIMIT_SWITCH_VALUE
    )
    assert stepper.on_limit_switch


def test_on_limit_switch_neither(stepper):
    stepper._limit_switch_a_pv_obj = make_mock_pv(
        get_val=STEPPER_ON_LIMIT_SWITCH_VALUE + 1
    )
    stepper._limit_switch_b_pv_obj = make_mock_pv(
        get_val=STEPPER_ON_LIMIT_SWITCH_VALUE + 1
    )
    assert not (stepper.on_limit_switch)


def test_max_steps(stepper):
    max_steps = randint(0, 10000000)
    stepper._max_steps_pv_obj = make_mock_pv(get_val=max_steps)
    assert stepper.max_steps == max_steps


def test_speed(stepper):
    speed = randint(0, 10000000)
    stepper._speed_pv_obj = make_mock_pv(get_val=speed)
    assert stepper.speed == speed


def test_restore_defaults(stepper):
    stepper._max_steps_pv_obj = make_mock_pv()
    stepper._speed_pv_obj = make_mock_pv()

    stepper.restore_defaults()
    stepper._max_steps_pv_obj.put.assert_called_with(DEFAULT_STEPPER_MAX_STEPS)
    stepper._speed_pv_obj.put.assert_called_with(DEFAULT_STEPPER_SPEED)


def test_move(stepper):
    num_steps = randint(-DEFAULT_STEPPER_MAX_STEPS, 0)
    stepper.check_abort = MagicMock()
    stepper._max_steps_pv_obj = make_mock_pv()
    stepper._speed_pv_obj = make_mock_pv()
    stepper._step_des_pv_obj = make_mock_pv()
    stepper.issue_move_command = MagicMock()
    stepper.restore_defaults = MagicMock()

    stepper.move(num_steps=num_steps)
    stepper.check_abort.assert_called()
    stepper._max_steps_pv_obj.put.assert_called_with(DEFAULT_STEPPER_MAX_STEPS)
    stepper._speed_pv_obj.put.assert_called_with(DEFAULT_STEPPER_SPEED)
    stepper._step_des_pv_obj.put.assert_called_with(abs(num_steps))
    stepper.issue_move_command.assert_called_with(num_steps, check_detune=True)
    stepper.restore_defaults.assert_called()


def test_issue_move_command(stepper):
    stepper.cavity.rack.cryomodule.is_harmonic_linearizer = False
    stepper.move_positive = MagicMock()
    stepper._motor_moving_pv_obj = make_mock_pv(get_val=0)
    stepper._limit_switch_a_pv_obj = make_mock_pv(get_val=0)
    stepper._limit_switch_b_pv_obj = make_mock_pv(get_val=0)

    stepper.issue_move_command(randint(1000, 10000))
    stepper.move_positive.assert_called()
    stepper._motor_moving_pv_obj.get.assert_called()
    stepper._limit_switch_a_pv_obj.get.assert_called()
    stepper._limit_switch_b_pv_obj.get.assert_called()


def test_issue_move_command_hl(stepper):
    stepper.cavity.rack.cryomodule.is_harmonic_linearizer = True
    stepper.move_negative = MagicMock()
    stepper._motor_moving_pv_obj = make_mock_pv(get_val=0)
    stepper._limit_switch_a_pv_obj = make_mock_pv(get_val=0)
    stepper._limit_switch_b_pv_obj = make_mock_pv(get_val=0)

    stepper.issue_move_command(randint(1000, 10000))
    stepper.move_negative.assert_called()
    stepper._motor_moving_pv_obj.get.assert_called()
    stepper._limit_switch_a_pv_obj.get.assert_called()
    stepper._limit_switch_b_pv_obj.get.assert_called()
