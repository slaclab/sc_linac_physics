from random import randint, choice
from unittest.mock import MagicMock, patch

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


def test_set_hz_per_microstep_writes_calc_pv(stepper):
    # SCALE is derived (SCALE = SCALE_CALC.B / 256) and read-only, so the
    # writer must put Hz-per-full-step (value * 256) to SCALE_CALC.B and must
    # NOT write SCALE directly.
    calc_pv = make_mock_pv()
    scale_pv = make_mock_pv()
    stepper._hz_per_step_calc_pv_obj = calc_pv
    stepper._hz_per_microstep_pv_obj = scale_pv

    stepper.set_hz_per_microstep(0.005)

    calc_pv.put.assert_called_once_with(0.005 * 256)
    scale_pv.put.assert_not_called()


def test_step_signed_pv_obj_lazy_and_cached(stepper):
    assert stepper._step_signed_pv_obj is None
    mock_pv = make_mock_pv()
    with patch(
        "sc_linac_physics.utils.sc_linac.stepper.PV", return_value=mock_pv
    ) as pv_ctor:
        first = stepper.step_signed_pv_obj
        second = stepper.step_signed_pv_obj
    assert first is mock_pv
    assert second is mock_pv
    pv_ctor.assert_called_once_with(stepper.step_signed_pv)


def test_steps_cold_landing_pv_obj_lazy_and_cached(stepper):
    assert stepper._steps_cold_landing_pv_obj is None
    mock_pv = make_mock_pv()
    with patch(
        "sc_linac_physics.utils.sc_linac.stepper.PV", return_value=mock_pv
    ) as pv_ctor:
        first = stepper.steps_cold_landing_pv_obj
        second = stepper.steps_cold_landing_pv_obj
    assert first is mock_pv
    assert second is mock_pv
    pv_ctor.assert_called_once_with(stepper.steps_cold_landing_pv)


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


# --- Failed-move cleanup and abort ordering --------------------------------

from sc_linac_physics.utils.sc_linac.linac_utils import (  # noqa: E402
    CavityAbortError,
    DetuneError,
)


def _ready_to_move(stepper, motor_moving=1):
    """Mock every PV a move touches; return the shared write log."""
    writes = []

    def pv(name, get_val=0):
        mock = make_mock_pv(get_val=get_val)
        mock.put.side_effect = lambda value, *a, **k: writes.append(
            (name, value)
        )
        return mock

    stepper._max_steps_pv_obj = pv("NSTEPS.DRVH")
    stepper._speed_pv_obj = pv("VELO", get_val=DEFAULT_STEPPER_SPEED)
    stepper._step_des_pv_obj = pv("NSTEPS")
    stepper._abort_pv_obj = pv("ABORT_REQ")
    stepper._motor_moving_pv_obj = make_mock_pv(get_val=motor_moving)
    stepper.cavity.rack.cryomodule.is_harmonic_linearizer = False
    return writes


def test_failed_move_aborts_moving_motor_and_restores_limits(stepper):
    writes = _ready_to_move(stepper, motor_moving=1)
    stepper.issue_move_command = MagicMock(side_effect=DetuneError("bad"))

    with pytest.raises(DetuneError):
        stepper.move(1000, max_steps=5000, speed=40000)

    assert ("ABORT_REQ", 1) in writes
    assert writes[-2:] == [
        ("NSTEPS.DRVH", DEFAULT_STEPPER_MAX_STEPS),
        ("VELO", DEFAULT_STEPPER_SPEED),
    ]
    assert writes.index(("ABORT_REQ", 1)) < len(writes) - 2


def test_failed_move_skips_abort_when_motor_stopped(stepper):
    writes = _ready_to_move(stepper, motor_moving=0)
    stepper.issue_move_command = MagicMock(side_effect=DetuneError("bad"))

    with pytest.raises(DetuneError):
        stepper.move(1000)

    assert ("ABORT_REQ", 1) not in writes


def test_failed_move_without_limit_change_does_not_write_limits(stepper):
    writes = _ready_to_move(stepper, motor_moving=0)
    stepper.issue_move_command = MagicMock(side_effect=DetuneError("bad"))

    with pytest.raises(DetuneError):
        stepper.move(1000, change_limits=False)

    assert not any(name in ("NSTEPS.DRVH", "VELO") for name, _ in writes)


def test_stepper_abort_writes_abort_req_once(stepper):
    writes = _ready_to_move(stepper, motor_moving=1)

    def abort_mid_move(*args, **kwargs):
        stepper.abort_flag = True
        stepper.check_abort()

    stepper.issue_move_command = MagicMock(side_effect=abort_mid_move)

    with pytest.raises(StepperAbortError):
        stepper.move(1000)

    assert writes.count(("ABORT_REQ", 1)) == 1


def test_cavity_abort_writes_abort_req_before_rf_off(stepper):
    """Cavity.check_abort() turns RF off before raising; stop the motor first."""
    writes = _ready_to_move(stepper, motor_moving=1)
    stepper.cavity.turn_off = MagicMock(
        side_effect=lambda: writes.append(("RF", "off"))
    )

    def cavity_abort_mid_move(*args, **kwargs):
        stepper.cavity.abort_flag = True
        stepper.check_abort()

    stepper.issue_move_command = MagicMock(side_effect=cavity_abort_mid_move)

    with pytest.raises(CavityAbortError):
        stepper.move(1000)

    assert writes.count(("ABORT_REQ", 1)) == 1
    assert writes.index(("ABORT_REQ", 1)) < writes.index(("RF", "off"))


def test_split_move_failure_cleans_up_once(stepper):
    writes = _ready_to_move(stepper, motor_moving=1)
    calls = [0]

    def fail_on_second_segment(*args, **kwargs):
        calls[0] += 1
        if calls[0] == 2:
            raise DetuneError("bad")

    stepper.issue_move_command = MagicMock(side_effect=fail_on_second_segment)

    with pytest.raises(DetuneError):
        stepper.move(9000, max_steps=5000)

    assert writes.count(("ABORT_REQ", 1)) == 1
    assert writes.count(("VELO", DEFAULT_STEPPER_SPEED)) == 2  # set, restore


def test_cleanup_failure_does_not_mask_original_error(stepper):
    _ready_to_move(stepper, motor_moving=1)
    stepper._abort_pv_obj.put.side_effect = RuntimeError("ABORT_REQ down")
    stepper.issue_move_command = MagicMock(side_effect=DetuneError("bad"))

    with pytest.raises(DetuneError):
        stepper.move(1000)


def test_successful_move_does_not_abort(stepper):
    writes = _ready_to_move(stepper, motor_moving=0)
    stepper.issue_move_command = MagicMock()

    stepper.move(1000)

    assert ("ABORT_REQ", 1) not in writes


def test_failed_move_aborts_when_motor_moving_unreadable(stepper):
    """Unknown motor state is treated as unsafe: write ABORT_REQ."""
    writes = _ready_to_move(stepper)
    stepper._motor_moving_pv_obj.get.side_effect = RuntimeError("PV down")
    stepper.issue_move_command = MagicMock(side_effect=DetuneError("bad"))

    with pytest.raises(DetuneError):
        stepper.move(1000)

    assert ("ABORT_REQ", 1) in writes
