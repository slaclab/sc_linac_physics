import random
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
from utils.sc_linac.linac_utils import (
    CavityAbortError,
    RF_MODE_SELA,
    HW_MODE_MAINTENANCE_VALUE,
    HW_MODE_OFFLINE_VALUE,
    HW_MODE_MAIN_DONE_VALUE,
    HW_MODE_READY_VALUE,
    HW_MODE_ONLINE_VALUE,
)


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

    def test_request_ssa_cal_false(self):
        self.cavity._ssa_cal_requested_pv_obj = make_mock_pv(get_val=False)
        self.cavity._progress_pv_obj = make_mock_pv()
        self.cavity.check_abort = MagicMock()
        self.cavity._status_msg_pv_obj = make_mock_pv()
        self.cavity.turn_off = MagicMock()
        self.cavity.ssa.calibrate = MagicMock()

        self.cavity.request_ssa_cal()
        self.cavity._ssa_cal_requested_pv_obj.get.assert_called()
        self.cavity.turn_off.assert_not_called()
        self.cavity.ssa.calibrate.assert_not_called()
        self.cavity._progress_pv_obj.put.assert_called()
        self.cavity.check_abort.assert_called()

    def test_request_ssa_cal_true(self):
        self.cavity._ssa_cal_requested_pv_obj = make_mock_pv(get_val=True)
        self.cavity._progress_pv_obj = make_mock_pv()
        self.cavity.check_abort = MagicMock()
        self.cavity._status_msg_pv_obj = make_mock_pv()
        self.cavity.turn_off = MagicMock()
        self.cavity.ssa.calibrate = MagicMock()
        self.cavity.ssa._saved_drive_max_pv_obj = make_mock_pv()

        self.cavity.request_ssa_cal()
        self.cavity._ssa_cal_requested_pv_obj.get.assert_called()
        self.cavity.turn_off.assert_called()
        self.cavity.ssa.calibrate.assert_called()
        self.cavity.ssa._saved_drive_max_pv_obj.get.assert_called()
        self.cavity._status_msg_pv_obj.put.assert_called()
        self.cavity._progress_pv_obj.put.assert_called()
        self.cavity.check_abort.assert_called()

    def test_request_auto_tune_false(self):
        self.cavity._auto_tune_requested_pv_obj = make_mock_pv(get_val=False)
        self.cavity.move_to_resonance = MagicMock()
        self.cavity._progress_pv_obj = make_mock_pv()
        self.cavity.check_abort = MagicMock()

        self.cavity.request_auto_tune()
        self.cavity._auto_tune_requested_pv_obj.get.assert_called()
        self.cavity.move_to_resonance.assert_not_called()
        self.cavity._progress_pv_obj.put.assert_called()
        self.cavity.check_abort.assert_called()

    def test_request_auto_tune_true(self):
        self.cavity._auto_tune_requested_pv_obj = make_mock_pv(get_val=True)
        self.cavity.move_to_resonance = MagicMock()
        self.cavity._progress_pv_obj = make_mock_pv()
        self.cavity.check_abort = MagicMock()
        self.cavity._status_msg_pv_obj = make_mock_pv()

        self.cavity.request_auto_tune()
        self.cavity._auto_tune_requested_pv_obj.get.assert_called()
        self.cavity.move_to_resonance.assert_called_with(use_sela=False)
        self.cavity._status_msg_pv_obj.put.assert_called()
        self.cavity._progress_pv_obj.put.assert_called()
        self.cavity.check_abort.assert_called()

    def test_request_characterization_false(self):
        self.cavity._cav_char_requested_pv_obj = make_mock_pv(get_val=False)
        self.cavity._progress_pv_obj = make_mock_pv()
        self.cavity.check_abort = MagicMock()
        self.cavity.characterize = MagicMock()
        self.cavity._calc_probe_q_pv_obj = make_mock_pv()
        self.cavity._status_msg_pv_obj = make_mock_pv()

        self.cavity.request_characterization()
        self.cavity._cav_char_requested_pv_obj.get.assert_called()
        self.cavity.characterize.assert_not_called()
        self.cavity._calc_probe_q_pv_obj.put.assert_not_called()
        self.cavity._cav_char_requested_pv_obj.get.assert_called()
        self.cavity._progress_pv_obj.put.assert_called()
        self.cavity.check_abort.assert_called()

    def test_request_characterization_true(self):
        self.cavity._cav_char_requested_pv_obj = make_mock_pv(get_val=True)
        self.cavity._progress_pv_obj = make_mock_pv()
        self.cavity.check_abort = MagicMock()
        self.cavity.characterize = MagicMock()
        self.cavity._calc_probe_q_pv_obj = make_mock_pv()
        self.cavity._status_msg_pv_obj = make_mock_pv()

        self.cavity.request_characterization()
        self.cavity._cav_char_requested_pv_obj.get.assert_called()
        self.cavity.characterize.assert_called()
        self.cavity._calc_probe_q_pv_obj.put.assert_called()
        self.cavity._cav_char_requested_pv_obj.get.assert_called()
        self.cavity._progress_pv_obj.put.assert_called()
        self.cavity.check_abort.assert_called()
        self.cavity._status_msg_pv_obj.put.assert_called()

    def test_request_ramp_false(self):
        self.cavity._rf_ramp_requested_pv_obj = make_mock_pv(get_val=False)
        self.cavity.piezo.enable_feedback = MagicMock()
        self.cavity._ades_pv_obj = make_mock_pv()
        self.cavity.turn_on = MagicMock()
        self.cavity.set_sela_mode = MagicMock()
        self.cavity.walk_amp = MagicMock()
        self.cavity.move_to_resonance = MagicMock()
        self.cavity.set_selap_mode = MagicMock()

        self.cavity.request_ramp()
        self.cavity._rf_ramp_requested_pv_obj.get.assert_called()
        self.cavity.piezo.enable_feedback.assert_not_called()
        self.cavity._ades_pv_obj.put.assert_not_called()
        self.cavity.turn_on.assert_not_called()
        self.cavity.set_sela_mode.assert_not_called()
        self.cavity.walk_amp.assert_not_called()
        self.cavity.move_to_resonance.assert_not_called()
        self.cavity.set_selap_mode.assert_not_called()

    def test_request_ramp_true(self):
        acon = random.uniform(5, 21)
        self.cavity._rf_ramp_requested_pv_obj = make_mock_pv(get_val=True)
        self.cavity.piezo.enable_feedback = MagicMock()
        self.cavity._ades_pv_obj = make_mock_pv()
        self.cavity.turn_on = MagicMock()
        self.cavity.set_sela_mode = MagicMock()
        self.cavity.walk_amp = MagicMock()
        self.cavity.move_to_resonance = MagicMock()
        self.cavity.set_selap_mode = MagicMock()
        self.cavity._status_msg_pv_obj = make_mock_pv()
        self.cavity._progress_pv_obj = make_mock_pv()
        self.cavity._rf_state_pv_obj = make_mock_pv(get_val=0)
        self.cavity._acon_pv_obj = make_mock_pv(get_val=acon)
        self.cavity.check_abort = MagicMock()
        self.cavity._rf_mode_pv_obj = make_mock_pv(get_val=RF_MODE_SELA)

        self.cavity.request_ramp()
        self.cavity._rf_ramp_requested_pv_obj.get.assert_called()
        self.cavity.piezo.enable_feedback.assert_called()
        self.cavity._acon_pv_obj.get.assert_called()
        self.cavity._ades_pv_obj.put.assert_called()
        self.cavity.turn_on.assert_called()
        self.cavity.set_sela_mode.assert_called()
        self.cavity.walk_amp.assert_called_with(acon, 0.1)
        self.cavity.move_to_resonance.assert_called_with(use_sela=True)
        self.cavity.set_selap_mode.assert_called()
        self.cavity._status_msg_pv_obj.put.assert_called()
        self.cavity._progress_pv_obj.put.assert_called()
        self.cavity.check_abort.assert_called()
        self.cavity._rf_mode_pv_obj.get.assert_called()

    def test_setup_running(self):
        self.cavity._status_pv_obj = make_mock_pv(get_val=STATUS_RUNNING_VALUE)
        self.cavity._status_msg_pv_obj = make_mock_pv()
        self.cavity.request_ssa_cal = MagicMock()
        self.cavity.request_auto_tune = MagicMock()
        self.cavity.request_characterization = MagicMock()
        self.cavity.request_ramp = MagicMock()

        self.cavity.setup()
        self.cavity._status_pv_obj.get.assert_called()
        self.cavity.request_ssa_cal.assert_not_called()
        self.cavity.request_auto_tune.assert_not_called()
        self.cavity.request_characterization.assert_not_called()
        self.cavity.request_ramp.assert_not_called()

    def test_setup_not_online(self):
        status = choice(
            [
                HW_MODE_MAINTENANCE_VALUE,
                HW_MODE_OFFLINE_VALUE,
                HW_MODE_MAIN_DONE_VALUE,
                HW_MODE_READY_VALUE,
            ]
        )
        self.cavity._status_pv_obj = make_mock_pv(get_val=STATUS_READY_VALUE)
        self.cavity._hw_mode_pv_obj = make_mock_pv(get_val=status)
        self.cavity._status_pv_obj = make_mock_pv()
        self.cavity._status_msg_pv_obj = make_mock_pv()
        self.cavity.request_ssa_cal = MagicMock()
        self.cavity.request_auto_tune = MagicMock()
        self.cavity.request_characterization = MagicMock()
        self.cavity.request_ramp = MagicMock()

        self.cavity.setup()
        self.cavity._status_pv_obj.get.assert_called()
        self.cavity._hw_mode_pv_obj.get.assert_called()
        self.cavity._status_pv_obj.put.assert_called_with(STATUS_ERROR_VALUE)
        self.cavity.request_ssa_cal.assert_not_called()
        self.cavity.request_auto_tune.assert_not_called()
        self.cavity.request_characterization.assert_not_called()
        self.cavity.request_ramp.assert_not_called()

    def test_setup(self):
        self.cavity._status_pv_obj = make_mock_pv(get_val=STATUS_READY_VALUE)
        self.cavity._hw_mode_pv_obj = make_mock_pv(get_val=HW_MODE_ONLINE_VALUE)
        self.cavity._status_pv_obj = make_mock_pv()
        self.cavity._status_msg_pv_obj = make_mock_pv()
        self.cavity.request_ssa_cal = MagicMock()
        self.cavity.request_auto_tune = MagicMock()
        self.cavity.request_characterization = MagicMock()
        self.cavity.request_ramp = MagicMock()
        self.cavity.clear_abort = MagicMock()
        self.cavity._progress_pv_obj = make_mock_pv()
        self.cavity.turn_off = MagicMock()
        self.cavity.ssa.turn_on = MagicMock()
        self.cavity.reset_interlocks = MagicMock()

        self.cavity.setup()
        self.cavity._status_pv_obj.get.assert_called()
        self.cavity._hw_mode_pv_obj.get.assert_called()
        self.cavity.request_ssa_cal.assert_called()
        self.cavity.request_auto_tune.assert_called()
        self.cavity.request_characterization.assert_called()
        self.cavity.request_ramp.assert_called()
        self.cavity.clear_abort.assert_called()
        self.cavity.turn_off.assert_called()
        self.cavity.ssa.turn_on.assert_called()
        self.cavity.reset_interlocks.assert_called()
        self.cavity._status_pv_obj.put.assert_called_with(STATUS_READY_VALUE)
        self.cavity._progress_pv_obj.put.assert_called_with(100)
