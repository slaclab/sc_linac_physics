from random import choice, randint
from unittest import TestCase
from unittest.mock import MagicMock

from lcls_tools.common.controls.pyepics.utils import make_mock_pv

from applications.auto_setup.setup_cavity import SetupCavity
from applications.auto_setup.setup_linac import SETUP_MACHINE
from applications.auto_setup.setup_utils import (
    STATUS_READY_VALUE,
    STATUS_RUNNING_VALUE,
    STATUS_ERROR_VALUE,
)
from utils.sc_linac.linac_utils import CavityAbortError


class TestSetupCavity(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.all_iterator = SETUP_MACHINE.all_iterator

    def setUp(self):
        self.cavity: SetupCavity = next(self.all_iterator)
        print(f"Testing {self.cavity}")

    def test_capture_acon(self):
        self.cavity._acon_pv_obj = make_mock_pv()
        ades = 16.6
        self.cavity._ades_pv_obj = make_mock_pv(get_val=ades)
        self.cavity.capture_acon()
        self.cavity._ades_pv_obj.get.assert_called()
        self.cavity._acon_pv_obj.put.assert_called_with(ades)

    def test_status(self):
        status = choice([STATUS_READY_VALUE, STATUS_RUNNING_VALUE, STATUS_ERROR_VALUE])
        self.cavity._status_pv_obj = make_mock_pv(get_val=status)
        self.assertEqual(status, self.cavity.status)

    def test_script_is_running(self):
        self.cavity._status_pv_obj = make_mock_pv(get_val=STATUS_RUNNING_VALUE)
        self.assertTrue(self.cavity.script_is_running)

    def test_script_is_not_running(self):
        status = choice([STATUS_READY_VALUE, STATUS_ERROR_VALUE])
        self.cavity._status_pv_obj = make_mock_pv(get_val=status)
        self.assertFalse(self.cavity.script_is_running)

    def test_progress(self):
        val = randint(0, 100)
        self.cavity._progress_pv_obj = make_mock_pv(get_val=val)
        self.assertEqual(val, self.cavity.progress)

    def test_status_message(self):
        tst_str = "this is a fake status"
        self.cavity._status_msg_pv_obj = make_mock_pv(get_val=tst_str)
        self.assertEqual(tst_str, self.cavity.status_message)

    def test_clear_abort(self):
        self.cavity._abort_pv_obj = make_mock_pv()
        self.cavity.clear_abort()
        self.cavity._abort_pv_obj.put.assert_called_with(0)

    def test_request_abort(self):
        status = choice([STATUS_READY_VALUE, STATUS_RUNNING_VALUE, STATUS_ERROR_VALUE])
        print(status)
        self.cavity._status_pv_obj = make_mock_pv(get_val=status)
        self.cavity._status_msg_pv_obj = make_mock_pv()
        self.cavity._abort_pv_obj = make_mock_pv()

        self.cavity.request_abort()

        if status == STATUS_RUNNING_VALUE:
            self.cavity._abort_pv_obj.put.assert_called()

        self.cavity._status_msg_pv_obj.put.assert_called()

    def test_check_abort(self):
        self.cavity._abort_pv_obj = make_mock_pv(get_val=True)
        self.cavity.clear_abort = MagicMock()
        self.assertRaises(CavityAbortError, self.cavity.check_abort)
        self.cavity.clear_abort.assert_called()

    def test_shut_down(self):
        self.cavity.clear_abort = MagicMock()
        self.cavity._status_pv_obj = make_mock_pv(get_val=STATUS_READY_VALUE)
        self.cavity._status_msg_pv_obj = make_mock_pv()
        self.cavity._progress_pv_obj = make_mock_pv()
        self.cavity.turn_off = MagicMock()
        self.cavity.ssa.turn_off = MagicMock()

        self.cavity.shut_down()
        self.cavity._status_pv_obj.get.assert_called()
        self.cavity._status_pv_obj.put.assert_called_with(STATUS_READY_VALUE)
        self.cavity._status_msg_pv_obj.put.assert_called()
        self.cavity._progress_pv_obj.put.assert_called()
        self.cavity.turn_off.assert_called()
        self.cavity.ssa.turn_off.assert_called()

    def test_setup(self):
        self.skipTest("Not yet implemented")
