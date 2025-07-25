import random
from random import choice, randint
from unittest.mock import MagicMock

import pytest
from lcls_tools.common.controls.pyepics.utils import make_mock_pv

from applications.auto_setup.backend.setup_cavity import SetupCavity
from applications.auto_setup.backend.setup_utils import (
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
from utils.sc_linac.rfstation import RFStation
from utils.sc_linac.ssa import SSA


@pytest.fixture
def cavity():
    cavity_num = randint(1, 8)
    rack: MagicMock = MagicMock()
    rack.rack_name = "A" if cavity_num <= 4 else "B"
    cavity = SetupCavity(cavity_num=cavity_num, rack_object=rack)
    cavity.ssa = SSA(cavity)
    cavity.rack.rfs1 = RFStation(num=1, rack_object=rack)
    cavity.rack.rfs2 = RFStation(num=2, rack_object=rack)
    yield cavity


def test_capture_acon(cavity):
    cavity._acon_pv_obj = make_mock_pv()
    ades = 16.6
    cavity._ades_pv_obj = make_mock_pv(get_val=ades)
    cavity.capture_acon()
    cavity._ades_pv_obj.get.assert_called()
    cavity._acon_pv_obj.put.assert_called_with(ades)


def test_status(cavity):
    status = choice([STATUS_READY_VALUE, STATUS_RUNNING_VALUE, STATUS_ERROR_VALUE])
    cavity._status_pv_obj = make_mock_pv(get_val=status)
    assert status == cavity.status


def test_script_is_running(cavity):
    cavity._status_pv_obj = make_mock_pv(get_val=STATUS_RUNNING_VALUE)
    assert cavity.script_is_running


def test_script_is_not_running(cavity):
    status = choice([STATUS_READY_VALUE, STATUS_ERROR_VALUE])
    cavity._status_pv_obj = make_mock_pv(get_val=status)
    assert not (cavity.script_is_running)


def test_progress(cavity):
    val = randint(0, 100)
    cavity._progress_pv_obj = make_mock_pv(get_val=val)
    assert val == cavity.progress


def test_status_message(cavity):
    tst_str = "this is a fake status"
    cavity._status_msg_pv_obj = make_mock_pv(get_val=tst_str)
    assert tst_str == cavity.status_message


def test_clear_abort(cavity):
    cavity._abort_pv_obj = make_mock_pv()
    cavity.clear_abort()
    cavity._abort_pv_obj.put.assert_called_with(0)


def test_request_abort(cavity):
    status = choice([STATUS_READY_VALUE, STATUS_RUNNING_VALUE, STATUS_ERROR_VALUE])
    cavity._status_pv_obj = make_mock_pv(get_val=status)
    cavity._status_msg_pv_obj = make_mock_pv()
    cavity._abort_pv_obj = make_mock_pv()

    cavity.trigger_abort()

    if status == STATUS_RUNNING_VALUE:
        cavity._abort_pv_obj.put.assert_called()

    cavity._status_msg_pv_obj.put.assert_called()


def test_check_abort(cavity):
    cavity._abort_pv_obj = make_mock_pv(get_val=True)
    cavity.clear_abort = MagicMock()
    with pytest.raises(CavityAbortError):
        cavity.check_abort()
    cavity.clear_abort.assert_called()


def test_shut_down(cavity):
    cavity.clear_abort = MagicMock()
    cavity._status_pv_obj = make_mock_pv(get_val=STATUS_READY_VALUE)
    cavity._status_msg_pv_obj = make_mock_pv()
    cavity._progress_pv_obj = make_mock_pv()
    cavity.turn_off = MagicMock()
    cavity.ssa.turn_off = MagicMock()

    cavity.shut_down()
    cavity._status_pv_obj.get.assert_called()
    cavity._status_pv_obj.put.assert_called_with(STATUS_READY_VALUE)
    cavity._status_msg_pv_obj.put.assert_called()
    cavity._progress_pv_obj.put.assert_called()
    cavity.turn_off.assert_called()
    cavity.ssa.turn_off.assert_called()


def test_request_ssa_cal_false(cavity):
    cavity._ssa_cal_requested_pv_obj = make_mock_pv(get_val=False)
    cavity._progress_pv_obj = make_mock_pv()
    cavity.check_abort = MagicMock()
    cavity._status_msg_pv_obj = make_mock_pv()
    cavity.turn_off = MagicMock()
    cavity.ssa.calibrate = MagicMock()

    cavity.request_ssa_cal()
    cavity._ssa_cal_requested_pv_obj.get.assert_called()
    cavity.turn_off.assert_not_called()
    cavity.ssa.calibrate.assert_not_called()
    cavity._progress_pv_obj.put.assert_called()
    cavity.check_abort.assert_called()


def test_request_ssa_cal_true(cavity):
    cavity._ssa_cal_requested_pv_obj = make_mock_pv(get_val=True)
    cavity._progress_pv_obj = make_mock_pv()
    cavity.check_abort = MagicMock()
    cavity._status_msg_pv_obj = make_mock_pv()
    cavity.turn_off = MagicMock()
    cavity.ssa.calibrate = MagicMock()
    cavity.ssa._saved_drive_max_pv_obj = make_mock_pv()
    cavity.rack.rfs1._dac_amp_pv_obj = make_mock_pv()
    cavity.rack.rfs2._dac_amp_pv_obj = make_mock_pv()

    cavity.request_ssa_cal()
    cavity._ssa_cal_requested_pv_obj.get.assert_called()
    cavity.turn_off.assert_called()
    cavity.ssa.calibrate.assert_called()
    cavity.ssa._saved_drive_max_pv_obj.get.assert_called()
    cavity._status_msg_pv_obj.put.assert_called()
    cavity._progress_pv_obj.put.assert_called()
    cavity.check_abort.assert_called()
    cavity.rack.rfs2._dac_amp_pv_obj.put.assert_called()
    cavity.rack.rfs1._dac_amp_pv_obj.put.assert_called()


def test_request_auto_tune_false(cavity):
    cavity._auto_tune_requested_pv_obj = make_mock_pv(get_val=False)
    cavity.move_to_resonance = MagicMock()
    cavity._progress_pv_obj = make_mock_pv()
    cavity.check_abort = MagicMock()

    cavity.request_auto_tune()
    cavity._auto_tune_requested_pv_obj.get.assert_called()
    cavity.move_to_resonance.assert_not_called()
    cavity._progress_pv_obj.put.assert_called()
    cavity.check_abort.assert_called()


def test_request_auto_tune_true(cavity):
    cavity._auto_tune_requested_pv_obj = make_mock_pv(get_val=True)
    cavity.move_to_resonance = MagicMock()
    cavity._progress_pv_obj = make_mock_pv()
    cavity.check_abort = MagicMock()
    cavity._status_msg_pv_obj = make_mock_pv()

    cavity.request_auto_tune()
    cavity._auto_tune_requested_pv_obj.get.assert_called()
    cavity.move_to_resonance.assert_called_with(use_sela=False)
    cavity._status_msg_pv_obj.put.assert_called()
    cavity._progress_pv_obj.put.assert_called()
    cavity.check_abort.assert_called()


def test_request_characterization_false(cavity):
    cavity._cav_char_requested_pv_obj = make_mock_pv(get_val=False)
    cavity._progress_pv_obj = make_mock_pv()
    cavity.check_abort = MagicMock()
    cavity.characterize = MagicMock()
    cavity._calc_probe_q_pv_obj = make_mock_pv()
    cavity._status_msg_pv_obj = make_mock_pv()

    cavity.request_characterization()
    cavity._cav_char_requested_pv_obj.get.assert_called()
    cavity.characterize.assert_not_called()
    cavity._calc_probe_q_pv_obj.put.assert_not_called()
    cavity._cav_char_requested_pv_obj.get.assert_called()
    cavity._progress_pv_obj.put.assert_called()
    cavity.check_abort.assert_called()


def test_request_characterization_true(cavity):
    cavity._cav_char_requested_pv_obj = make_mock_pv(get_val=True)
    cavity._progress_pv_obj = make_mock_pv()
    cavity.check_abort = MagicMock()
    cavity.characterize = MagicMock()
    cavity._calc_probe_q_pv_obj = make_mock_pv()
    cavity._status_msg_pv_obj = make_mock_pv()

    cavity.request_characterization()
    cavity._cav_char_requested_pv_obj.get.assert_called()
    cavity.characterize.assert_called()
    cavity._calc_probe_q_pv_obj.put.assert_called()
    cavity._cav_char_requested_pv_obj.get.assert_called()
    cavity._progress_pv_obj.put.assert_called()
    cavity.check_abort.assert_called()
    cavity._status_msg_pv_obj.put.assert_called()


def test_request_ramp_false(cavity):
    cavity._rf_ramp_requested_pv_obj = make_mock_pv(get_val=False)
    cavity.piezo.enable_feedback = MagicMock()
    cavity._ades_pv_obj = make_mock_pv()
    cavity.turn_on = MagicMock()
    cavity.set_sela_mode = MagicMock()
    cavity.walk_amp = MagicMock()
    cavity.move_to_resonance = MagicMock()
    cavity.set_selap_mode = MagicMock()

    cavity.request_ramp()
    cavity._rf_ramp_requested_pv_obj.get.assert_called()
    cavity.piezo.enable_feedback.assert_not_called()
    cavity._ades_pv_obj.put.assert_not_called()
    cavity.turn_on.assert_not_called()
    cavity.set_sela_mode.assert_not_called()
    cavity.walk_amp.assert_not_called()
    cavity.move_to_resonance.assert_not_called()
    cavity.set_selap_mode.assert_not_called()


def test_request_ramp_true(cavity):
    acon = random.uniform(5, 21)
    cavity._rf_ramp_requested_pv_obj = make_mock_pv(get_val=True)
    cavity.piezo.enable_feedback = MagicMock()
    cavity._ades_pv_obj = make_mock_pv()
    cavity.turn_on = MagicMock()
    cavity.set_sela_mode = MagicMock()
    cavity.walk_amp = MagicMock()
    cavity.move_to_resonance = MagicMock()
    cavity.set_selap_mode = MagicMock()
    cavity._status_msg_pv_obj = make_mock_pv()
    cavity._progress_pv_obj = make_mock_pv()
    cavity._rf_state_pv_obj = make_mock_pv(get_val=0)
    cavity._acon_pv_obj = make_mock_pv(get_val=acon)
    cavity.check_abort = MagicMock()
    cavity._rf_mode_pv_obj = make_mock_pv(get_val=RF_MODE_SELA)

    cavity.request_ramp()
    cavity._rf_ramp_requested_pv_obj.get.assert_called()
    cavity.piezo.enable_feedback.assert_called()
    cavity._acon_pv_obj.get.assert_called()
    cavity._ades_pv_obj.put.assert_called()
    cavity.turn_on.assert_called()
    cavity.set_sela_mode.assert_called()
    cavity.walk_amp.assert_called_with(acon, 0.1)
    cavity.move_to_resonance.assert_called_with(use_sela=True)
    cavity.set_selap_mode.assert_called()
    cavity._status_msg_pv_obj.put.assert_called()
    cavity._progress_pv_obj.put.assert_called()
    cavity.check_abort.assert_called()
    cavity._rf_mode_pv_obj.get.assert_called()


def test_setup_running(cavity):
    cavity._status_pv_obj = make_mock_pv(get_val=STATUS_RUNNING_VALUE)
    cavity._status_msg_pv_obj = make_mock_pv()
    cavity.request_ssa_cal = MagicMock()
    cavity.request_auto_tune = MagicMock()
    cavity.request_characterization = MagicMock()
    cavity.request_ramp = MagicMock()

    cavity.setup()
    cavity._status_pv_obj.get.assert_called()
    cavity.request_ssa_cal.assert_not_called()
    cavity.request_auto_tune.assert_not_called()
    cavity.request_characterization.assert_not_called()
    cavity.request_ramp.assert_not_called()


def test_setup_not_online(cavity):
    status = choice(
        [
            HW_MODE_MAINTENANCE_VALUE,
            HW_MODE_OFFLINE_VALUE,
            HW_MODE_MAIN_DONE_VALUE,
            HW_MODE_READY_VALUE,
        ]
    )
    cavity._status_pv_obj = make_mock_pv(get_val=STATUS_READY_VALUE)
    cavity._hw_mode_pv_obj = make_mock_pv(get_val=status)
    cavity._status_pv_obj = make_mock_pv()
    cavity._status_msg_pv_obj = make_mock_pv()
    cavity.request_ssa_cal = MagicMock()
    cavity.request_auto_tune = MagicMock()
    cavity.request_characterization = MagicMock()
    cavity.request_ramp = MagicMock()

    cavity.setup()
    cavity._status_pv_obj.get.assert_called()
    cavity._hw_mode_pv_obj.get.assert_called()
    cavity._status_pv_obj.put.assert_called_with(STATUS_ERROR_VALUE)
    cavity.request_ssa_cal.assert_not_called()
    cavity.request_auto_tune.assert_not_called()
    cavity.request_characterization.assert_not_called()
    cavity.request_ramp.assert_not_called()


def test_setup(cavity):
    cavity._status_pv_obj = make_mock_pv(get_val=STATUS_READY_VALUE)
    cavity._hw_mode_pv_obj = make_mock_pv(get_val=HW_MODE_ONLINE_VALUE)
    cavity._status_pv_obj = make_mock_pv()
    cavity._status_msg_pv_obj = make_mock_pv()
    cavity.request_ssa_cal = MagicMock()
    cavity.request_auto_tune = MagicMock()
    cavity.request_characterization = MagicMock()
    cavity.request_ramp = MagicMock()
    cavity.clear_abort = MagicMock()
    cavity._progress_pv_obj = make_mock_pv()
    cavity.turn_off = MagicMock()
    cavity.ssa.turn_on = MagicMock()
    cavity.reset_interlocks = MagicMock()

    cavity.setup()
    cavity._status_pv_obj.get.assert_called()
    cavity._hw_mode_pv_obj.get.assert_called()
    cavity.request_ssa_cal.assert_called()
    cavity.request_auto_tune.assert_called()
    cavity.request_characterization.assert_called()
    cavity.request_ramp.assert_called()
    cavity.clear_abort.assert_called()
    cavity.turn_off.assert_called()
    cavity.ssa.turn_on.assert_called()
    cavity.reset_interlocks.assert_called()
    cavity._status_pv_obj.put.assert_called_with(STATUS_READY_VALUE)
    cavity._progress_pv_obj.put.assert_called_with(100)
