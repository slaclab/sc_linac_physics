from random import randint
from unittest import TestCase
from unittest.mock import MagicMock, Mock

from lcls_tools.common.controls.pyepics.utils import make_mock_pv

from utils.sc_linac.linac import MACHINE
from utils.sc_linac.linac_utils import (
    PIEZO_ENABLE_VALUE,
    PIEZO_DISABLE_VALUE,
    PIEZO_MANUAL_VALUE,
    PIEZO_FEEDBACK_VALUE,
)
from utils.sc_linac.piezo import Piezo


class TestPiezo(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.non_hl_iterator = MACHINE.non_hl_iterator

    def setUp(self):
        self.piezo: Piezo = next(self.non_hl_iterator).piezo
        print(f"Testing {self.piezo}")
        self.num_calls = 0

    def test_pv_prefix(self):
        piezo = MACHINE.cryomodules["01"].cavities[1].piezo
        self.assertEqual(piezo.pv_prefix, "ACCL:L0B:0110:PZT:")

    def test_voltage(self):
        val = randint(-50, 50)
        self.piezo._voltage_pv_obj = make_mock_pv(get_val=val)
        self.assertEqual(self.piezo.voltage, val)

    def test_bias_voltage(self):
        val = randint(-50, 50)
        self.piezo._bias_voltage_pv_obj = make_mock_pv(get_val=val)
        self.assertEqual(self.piezo.bias_voltage, val)

    def test_dc_setpoint(self):
        val = randint(-50, 50)
        self.piezo._dc_setpoint_pv_obj = make_mock_pv(get_val=val)
        self.assertEqual(self.piezo.dc_setpoint, val)

    def test_feedback_setpoint(self):
        val = randint(-50, 50)
        self.piezo._feedback_setpoint_pv_obj = make_mock_pv(get_val=val)
        self.assertEqual(self.piezo.feedback_setpoint, val)

    def test_is_enabled(self):
        self.piezo._enable_stat_pv_obj = make_mock_pv(get_val=PIEZO_ENABLE_VALUE)
        self.assertTrue(self.piezo.is_enabled)

    def test_is_not_enabled(self):
        self.piezo._enable_stat_pv_obj = make_mock_pv(get_val=PIEZO_DISABLE_VALUE)
        self.assertFalse(self.piezo.is_enabled)

    def test_feedback_stat(self):
        stat = randint(0, 1)
        self.piezo._feedback_stat_pv_obj = make_mock_pv(get_val=stat)
        self.assertEqual(self.piezo.feedback_stat, stat)

    def test_in_manual(self):
        self.piezo._feedback_stat_pv_obj = make_mock_pv(get_val=PIEZO_MANUAL_VALUE)
        self.assertTrue(self.piezo.in_manual)

    def test_not_in_manual(self):
        self.piezo._feedback_stat_pv_obj = make_mock_pv(get_val=PIEZO_FEEDBACK_VALUE)
        self.assertFalse(self.piezo.in_manual)

    def test_set_to_feedback(self):
        self.piezo._feedback_control_pv_obj = make_mock_pv()
        self.piezo.set_to_feedback()
        self.piezo._feedback_control_pv_obj.put.assert_called_with(PIEZO_FEEDBACK_VALUE)

    def test_set_to_manual(self):
        self.piezo._feedback_control_pv_obj = make_mock_pv()
        self.piezo.set_to_manual()
        self.piezo._feedback_control_pv_obj.put.assert_called_with(PIEZO_MANUAL_VALUE)

    def mock_status(self):
        if self.num_calls < 1:
            self.num_calls += 1
            return PIEZO_DISABLE_VALUE
        else:
            self.num_calls = 0
            return PIEZO_ENABLE_VALUE

    def test_enable(self):
        self.piezo._bias_voltage_pv_obj = make_mock_pv()
        self.piezo._enable_stat_pv_obj = make_mock_pv()
        self.piezo._enable_stat_pv_obj.get = self.mock_status
        self.piezo.cavity.check_abort = make_mock_pv()
        self.piezo._enable_pv_obj = make_mock_pv()

        self.piezo.enable()
        self.piezo._bias_voltage_pv_obj.put.assert_called_with(25)
        self.piezo.cavity.check_abort.assert_called()
        self.piezo._enable_pv_obj.put.assert_called_with(PIEZO_ENABLE_VALUE)

    def test_enable_feedback(self):
        self.piezo.enable = MagicMock()
        self.piezo._feedback_stat_pv_obj = make_mock_pv(get_val=PIEZO_MANUAL_VALUE)

        def set_feedback():
            self.piezo._feedback_stat_pv_obj = make_mock_pv(
                get_val=PIEZO_FEEDBACK_VALUE
            )

        self.piezo.set_to_feedback = Mock(side_effect=set_feedback)
        self.piezo.set_to_manual = MagicMock()

        self.piezo.enable_feedback()
        self.piezo.enable.assert_called()
        self.piezo.set_to_feedback.assert_called()

    def test_disable_feedback(self):
        self.piezo.enable = MagicMock()
        self.piezo._feedback_stat_pv_obj = make_mock_pv(get_val=PIEZO_FEEDBACK_VALUE)

        def set_manual():
            self.piezo._feedback_stat_pv_obj = make_mock_pv(get_val=PIEZO_MANUAL_VALUE)

        self.piezo.set_to_manual = Mock(side_effect=set_manual)
        self.piezo.set_to_feedback = MagicMock()

        self.piezo.disable_feedback()
        self.piezo.enable.assert_called()
        self.piezo.set_to_manual.assert_called()
