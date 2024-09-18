from random import randint
from unittest import TestCase
from unittest.mock import MagicMock

from lcls_tools.common.controls.pyepics.utils import make_mock_pv

from utils.sc_linac.linac import MACHINE
from utils.sc_linac.linac_utils import (
    StepperAbortError,
    STEPPER_ON_LIMIT_SWITCH_VALUE,
    DEFAULT_STEPPER_MAX_STEPS,
    DEFAULT_STEPPER_SPEED,
)
from utils.sc_linac.stepper import StepperTuner


class TestStepperTuner(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.non_hl_iterator = MACHINE.non_hl_iterator
        cls.hl_iterator = MACHINE.hl_iterator
        cls.step_scale = -0.00589677

    def setUp(self):
        self.stepper: StepperTuner = next(self.non_hl_iterator).stepper_tuner
        print(f"Testing {self.stepper}")

    def test_pv_prefix(self):
        self.assertEqual(
            self.stepper.pv_prefix, self.stepper.cavity.pv_prefix + "STEP:"
        )

    def test_hz_per_microstep(self):
        self.stepper._hz_per_microstep_pv_obj = make_mock_pv(get_val=self.step_scale)
        self.assertEqual(self.stepper.hz_per_microstep, abs(self.step_scale))

    def test_check_abort(self):
        self.stepper.cavity.check_abort = MagicMock()

        self.stepper.abort = MagicMock()
        self.stepper.abort_flag = False
        try:
            self.stepper.check_abort()
            self.stepper.cavity.check_abort.assert_called()
        except StepperAbortError:
            self.fail(f"{self.stepper} abort called unexpectedly")

        self.stepper.abort_flag = True
        self.assertRaises(
            StepperAbortError,
            self.stepper.check_abort,
        )

    def test_abort(self):
        self.stepper._abort_pv_obj = make_mock_pv()
        self.stepper.abort()
        self.stepper._abort_pv_obj.put.assert_called_with(1)

    def test_move_positive(self):
        self.stepper._move_pos_pv_obj = make_mock_pv()
        self.stepper.move_positive()
        self.stepper._move_pos_pv_obj.put.assert_called_with(1)

    def test_move_negative(self):
        self.stepper._move_neg_pv_obj = make_mock_pv()
        self.stepper.move_negative()
        self.stepper._move_neg_pv_obj.put.assert_called_with(1)

    def test_step_des(self):
        step_des = randint(0, 10000000)
        self.stepper._step_des_pv_obj = make_mock_pv(get_val=step_des)
        self.assertEqual(self.stepper.step_des, step_des)

    def test_motor_moving(self):
        self.stepper._motor_moving_pv_obj = make_mock_pv(get_val=1)
        self.assertTrue(self.stepper.motor_moving)

        self.stepper._motor_moving_pv_obj = make_mock_pv(get_val=0)
        self.assertFalse(self.stepper.motor_moving)

    def test_reset_signed_steps(self):
        self.stepper._reset_signed_pv_obj = make_mock_pv()
        self.stepper.reset_signed_steps()
        self.stepper._reset_signed_pv_obj.put.assert_called_with(0)

    def test_on_limit_switch_a(self):
        self.stepper._limit_switch_a_pv_obj = make_mock_pv(
            get_val=STEPPER_ON_LIMIT_SWITCH_VALUE
        )
        self.stepper._limit_switch_b_pv_obj = make_mock_pv(
            get_val=STEPPER_ON_LIMIT_SWITCH_VALUE + 1
        )
        self.assertTrue(self.stepper.on_limit_switch)

    def test_on_limit_switch_b(self):
        self.stepper._limit_switch_a_pv_obj = make_mock_pv(
            get_val=STEPPER_ON_LIMIT_SWITCH_VALUE + 1
        )
        self.stepper._limit_switch_b_pv_obj = make_mock_pv(
            get_val=STEPPER_ON_LIMIT_SWITCH_VALUE
        )
        self.assertTrue(self.stepper.on_limit_switch)

    def test_on_limit_switch_neither(self):
        self.stepper._limit_switch_a_pv_obj = make_mock_pv(
            get_val=STEPPER_ON_LIMIT_SWITCH_VALUE + 1
        )
        self.stepper._limit_switch_b_pv_obj = make_mock_pv(
            get_val=STEPPER_ON_LIMIT_SWITCH_VALUE + 1
        )
        self.assertFalse(self.stepper.on_limit_switch)

    def test_max_steps(self):
        max_steps = randint(0, 10000000)
        self.stepper._max_steps_pv_obj = make_mock_pv(get_val=max_steps)
        self.assertEqual(self.stepper.max_steps, max_steps)

    def test_speed(self):
        speed = randint(0, 10000000)
        self.stepper._speed_pv_obj = make_mock_pv(get_val=speed)
        self.assertEqual(self.stepper.speed, speed)

    def test_restore_defaults(self):
        self.stepper._max_steps_pv_obj = make_mock_pv()
        self.stepper._speed_pv_obj = make_mock_pv()

        self.stepper.restore_defaults()
        self.stepper._max_steps_pv_obj.put.assert_called_with(DEFAULT_STEPPER_MAX_STEPS)
        self.stepper._speed_pv_obj.put.assert_called_with(DEFAULT_STEPPER_SPEED)

    def test_move(self):
        num_steps = randint(-DEFAULT_STEPPER_MAX_STEPS, 0)
        self.stepper.check_abort = MagicMock()
        self.stepper._max_steps_pv_obj = make_mock_pv()
        self.stepper._speed_pv_obj = make_mock_pv()
        self.stepper._step_des_pv_obj = make_mock_pv()
        self.stepper.issue_move_command = MagicMock()
        self.stepper.restore_defaults = MagicMock()

        self.stepper.move(num_steps=num_steps)
        self.stepper.check_abort.assert_called()
        self.stepper._max_steps_pv_obj.put.assert_called_with(DEFAULT_STEPPER_MAX_STEPS)
        self.stepper._speed_pv_obj.put.assert_called_with(DEFAULT_STEPPER_SPEED)
        self.stepper._step_des_pv_obj.put.assert_called_with(abs(num_steps))
        self.stepper.issue_move_command.assert_called_with(num_steps, check_detune=True)
        self.stepper.restore_defaults.assert_called()

    def test_issue_move_command(self):
        self.stepper.move_positive = MagicMock()
        self.stepper._motor_moving_pv_obj = make_mock_pv(get_val=0)
        self.stepper._limit_switch_a_pv_obj = make_mock_pv(get_val=0)
        self.stepper._limit_switch_b_pv_obj = make_mock_pv(get_val=0)

        self.stepper.issue_move_command(randint(1000, 10000))
        self.stepper.move_positive.assert_called()
        self.stepper._motor_moving_pv_obj.get.assert_called()
        self.stepper._limit_switch_a_pv_obj.get.assert_called()
        self.stepper._limit_switch_b_pv_obj.get.assert_called()
