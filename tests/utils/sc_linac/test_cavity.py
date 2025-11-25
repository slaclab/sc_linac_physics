from datetime import datetime, timedelta
from random import randint, choice
from unittest.mock import MagicMock, patch

import pytest
from lcls_tools.common.controls.pyepics.utils import (
    EPICS_INVALID_VAL,
    EPICS_NO_ALARM_VAL,
    make_mock_pv,
)

from sc_linac_physics.utils.sc_linac.cavity import Cavity
from sc_linac_physics.utils.sc_linac.linac import MACHINE
from sc_linac_physics.utils.sc_linac.linac_utils import (
    LOADED_Q_LOWER_LIMIT,
    LOADED_Q_LOWER_LIMIT_HL,
    LOADED_Q_UPPER_LIMIT,
    LOADED_Q_UPPER_LIMIT_HL,
    RF_MODE_CHIRP,
    RF_MODE_SEL,
    RF_MODE_SELA,
    RF_MODE_SELAP,
    CAVITY_SCALE_LOWER_LIMIT_HL,
    CAVITY_SCALE_UPPER_LIMIT_HL,
    CAVITY_SCALE_LOWER_LIMIT,
    CAVITY_SCALE_UPPER_LIMIT,
    CHARACTERIZATION_RUNNING_VALUE,
    CHARACTERIZATION_CRASHED_VALUE,
    HW_MODE_ONLINE_VALUE,
    HW_MODE_OFFLINE_VALUE,
    TUNE_CONFIG_RESONANCE_VALUE,
    DetuneError,
    NOMINAL_PULSED_ONTIME,
    CavityHWModeError,
    CavityAbortError,
    SAFE_PULSED_DRIVE_LEVEL,
    CavityFaultError,
    INTERLOCK_RESET_ATTEMPTS,
    CALIBRATION_COMPLETE_VALUE,
    CavityCharacterizationError,
    QuenchError,
    ALL_CRYOMODULES,
)
from sc_linac_physics.utils.sc_linac.piezo import Piezo
from tests.mock_utils import mock_func


@pytest.fixture
def cavity(monkeypatch):
    monkeypatch.setattr("time.sleep", mock_func)

    with patch(
        "sc_linac_physics.utils.sc_linac.cavity.custom_logger"
    ) as mock_logger:
        mock_logger.return_value = MagicMock()

        rack = make_rack(is_hl=False)
        cavity = Cavity(cavity_num=randint(1, 8), rack_object=rack)
        cavity.stepper_tuner.hz_per_microstep = 0.00540801
        cavity.piezo = Piezo(cavity)
        yield cavity


@pytest.fixture
def hl_cavity(monkeypatch):
    monkeypatch.setattr("time.sleep", mock_func)

    with patch(
        "sc_linac_physics.utils.sc_linac.cavity.custom_logger"
    ) as mock_logger:
        mock_logger.return_value = MagicMock()

        rack = make_rack(is_hl=True)
        cavity = Cavity(cavity_num=randint(1, 8), rack_object=rack)
        cavity.stepper_tuner.hz_per_microstep = 0.00540801
        cavity.piezo = Piezo(cavity)
        yield cavity


def make_rack(is_hl=False):
    rack = MagicMock()
    rack.cryomodule.name = choice(ALL_CRYOMODULES)
    rack.cryomodule.is_harmonic_linearizer = is_hl
    rack.cryomodule.linac.name = f"L{randint(0, 3)}B"
    return rack


def test_pv_prefix(cavity):
    assert (
        cavity.pv_prefix
        == f"ACCL:{cavity.linac.name}:{cavity.cryomodule.name}{cavity.number}0:"
    )


def test_loaded_q_limits(cavity):
    assert cavity.loaded_q_lower_limit == LOADED_Q_LOWER_LIMIT
    assert cavity.loaded_q_upper_limit == LOADED_Q_UPPER_LIMIT


def test_microsteps_per_hz(cavity):
    assert cavity.microsteps_per_hz == 1 / cavity.stepper_tuner.hz_per_microstep


def test_start_characterization(cavity):
    cavity._characterization_start_pv_obj = make_mock_pv()
    cavity.start_characterization()
    cavity._characterization_start_pv_obj.put.assert_called_with(1)


def test_cw_data_decimation(cavity):
    val = randint(0, 256)
    cavity._cw_data_decim_pv_obj = make_mock_pv(get_val=val)
    assert cavity.cw_data_decimation == val


def test_pulsed_data_decimation(cavity):
    val = randint(0, 256)
    cavity._pulsed_data_decim_pv_obj = make_mock_pv(get_val=val)
    assert cavity.pulsed_data_decimation == val


def test_rf_control(cavity):
    cavity._rf_control_pv_obj = make_mock_pv(get_val=1)
    assert cavity.rf_control == 1


def test_rf_mode(cavity):
    mode = randint(0, 6)
    cavity._rf_mode_pv_obj = make_mock_pv(get_val=mode)
    assert cavity.rf_mode == mode


def test_set_chirp_mode(cavity):
    cavity._rf_control_pv_obj = make_mock_pv()
    cavity._rf_mode_ctrl_pv_obj = make_mock_pv()
    cavity.set_chirp_mode()
    cavity._rf_mode_ctrl_pv_obj.put.assert_called_with(RF_MODE_CHIRP)


def test_set_sel_mode(cavity):
    cavity._rf_mode_ctrl_pv_obj = make_mock_pv()
    cavity.set_sel_mode()
    cavity._rf_mode_ctrl_pv_obj.put.assert_called_with(RF_MODE_SEL)


def test_set_sela_mode(cavity):
    cavity._rf_mode_ctrl_pv_obj = make_mock_pv()
    cavity.set_sela_mode()
    cavity._rf_mode_ctrl_pv_obj.put.assert_called_with(RF_MODE_SELA)


def test_set_selap_mode(cavity):
    cavity._rf_mode_ctrl_pv_obj = make_mock_pv()
    cavity.set_selap_mode()
    cavity._rf_mode_ctrl_pv_obj.put.assert_called_with(RF_MODE_SELAP)


def test_drive_level(cavity):
    val = randint(0, 100)
    cavity._drive_level_pv_obj = make_mock_pv(get_val=val)
    assert cavity.drive_level == val


def test_push_ssa_slope(cavity):
    cavity._push_ssa_slope_pv_obj = make_mock_pv()
    cavity.push_ssa_slope()
    cavity._push_ssa_slope_pv_obj.put.assert_called_with(1, wait=False)


def test_save_ssa_slope(cavity):
    cavity._save_ssa_slope_pv_obj = make_mock_pv()
    cavity.save_ssa_slope()
    cavity._save_ssa_slope_pv_obj.put.assert_called_with(1, wait=False)


def test_measured_loaded_q(cavity):
    val = randint(1, 5)
    cavity._measured_loaded_q_pv_obj = make_mock_pv(get_val=val)
    assert cavity.measured_loaded_q == val


def test_measured_loaded_q_in_tolerance(cavity):
    in_tol_val = randint(LOADED_Q_LOWER_LIMIT, LOADED_Q_UPPER_LIMIT)
    cavity._measured_loaded_q_pv_obj = make_mock_pv(get_val=in_tol_val)
    assert cavity.measured_loaded_q_in_tolerance


def test_measured_loaded_q_in_tolerance_hl(hl_cavity):
    in_tol_val = randint(LOADED_Q_LOWER_LIMIT_HL, LOADED_Q_UPPER_LIMIT_HL)
    hl_cavity._measured_loaded_q_pv_obj = make_mock_pv(get_val=in_tol_val)
    assert hl_cavity.measured_loaded_q_in_tolerance


def test_loaded_q_high(cavity):
    high_val = randint(LOADED_Q_UPPER_LIMIT, LOADED_Q_UPPER_LIMIT * 10)
    cavity._measured_loaded_q_pv_obj = make_mock_pv(get_val=high_val)
    assert not cavity.measured_loaded_q_in_tolerance


def test_loaded_q_high_hl(hl_cavity):
    high_val = randint(LOADED_Q_UPPER_LIMIT_HL, LOADED_Q_UPPER_LIMIT_HL * 10)
    hl_cavity._measured_loaded_q_pv_obj = make_mock_pv(get_val=high_val)
    assert not hl_cavity.measured_loaded_q_in_tolerance


def test_loaded_q_low(cavity):
    low_val = randint(0, LOADED_Q_LOWER_LIMIT)
    cavity._measured_loaded_q_pv_obj = make_mock_pv(get_val=low_val)
    assert not cavity.measured_loaded_q_in_tolerance


def test_loaded_q_low_hl(hl_cavity):
    low_val = randint(0, LOADED_Q_LOWER_LIMIT_HL)
    hl_cavity._measured_loaded_q_pv_obj = make_mock_pv(get_val=low_val)
    assert not hl_cavity.measured_loaded_q_in_tolerance


def test_push_loaded_q(cavity):
    cavity._push_loaded_q_pv_obj = make_mock_pv()
    cavity.push_loaded_q()
    cavity._push_loaded_q_pv_obj.put.assert_called_with(1, wait=False)


def test_measured_scale_factor(cavity):
    val = randint(CAVITY_SCALE_LOWER_LIMIT_HL, CAVITY_SCALE_UPPER_LIMIT_HL)
    cavity._measured_scale_factor_pv_obj = make_mock_pv(get_val=val)
    assert cavity.measured_scale_factor == val


def test_measured_scale_factor_in_tolerance_hl(hl_cavity):
    val = randint(CAVITY_SCALE_LOWER_LIMIT_HL, CAVITY_SCALE_UPPER_LIMIT_HL)
    hl_cavity._measured_scale_factor_pv_obj = make_mock_pv(get_val=val)
    assert hl_cavity.measured_scale_factor_in_tolerance


def test_measured_scale_factor_in_tolerance(cavity):
    val = randint(CAVITY_SCALE_LOWER_LIMIT, CAVITY_SCALE_UPPER_LIMIT)
    cavity._measured_scale_factor_pv_obj = make_mock_pv(get_val=val)
    assert cavity.measured_scale_factor_in_tolerance


def test_scale_factor_high(cavity):
    val = randint(CAVITY_SCALE_UPPER_LIMIT + 1, CAVITY_SCALE_UPPER_LIMIT * 2)
    cavity._measured_scale_factor_pv_obj = make_mock_pv(get_val=val)
    assert not cavity.measured_scale_factor_in_tolerance


def test_scale_factor_high_hl(hl_cavity):
    val = randint(
        CAVITY_SCALE_UPPER_LIMIT_HL + 1, CAVITY_SCALE_UPPER_LIMIT_HL * 2
    )
    hl_cavity._measured_scale_factor_pv_obj = make_mock_pv(get_val=val)
    assert not hl_cavity.measured_scale_factor_in_tolerance


def test_scale_factor_low(cavity):
    val = randint(0, CAVITY_SCALE_LOWER_LIMIT - 1)
    cavity._measured_scale_factor_pv_obj = make_mock_pv(get_val=val)
    assert not cavity.measured_scale_factor_in_tolerance


def test_scale_factor_low_hl(hl_cavity):
    val = randint(0, CAVITY_SCALE_LOWER_LIMIT_HL - 1)
    hl_cavity._measured_scale_factor_pv_obj = make_mock_pv(get_val=val)
    assert not hl_cavity.measured_scale_factor_in_tolerance


def test_push_scale_factor(cavity):
    cavity._push_scale_factor_pv_obj = make_mock_pv()
    cavity.push_scale_factor()
    cavity._push_scale_factor_pv_obj.put.assert_called_with(1, wait=False)


def test_characterization_status(cavity):
    val = randint(0, 3)
    cavity._characterization_status_pv_obj = make_mock_pv(get_val=val)
    assert cavity.characterization_status == val


def test_characterization_running(cavity):
    cavity._characterization_status_pv_obj = make_mock_pv(
        get_val=CHARACTERIZATION_RUNNING_VALUE,
    )
    assert cavity.characterization_running

    cavity._characterization_status_pv_obj = make_mock_pv(
        get_val=CHARACTERIZATION_CRASHED_VALUE,
    )
    assert not cavity.characterization_running


def test_characterization_crashed(cavity):
    cavity._characterization_status_pv_obj = make_mock_pv(
        get_val=CHARACTERIZATION_CRASHED_VALUE,
    )
    assert cavity.characterization_crashed

    cavity._characterization_status_pv_obj = make_mock_pv(
        get_val=CHARACTERIZATION_RUNNING_VALUE,
    )
    assert not cavity.characterization_crashed


def test_pulse_on_time(cavity):
    cavity._pulse_on_time_pv_obj = make_mock_pv(get_val=70)
    assert cavity.pulse_on_time == 70


def test_pulse_status(cavity):
    val = randint(0, 5)
    cavity._pulse_status_pv_obj = make_mock_pv(get_val=val)
    assert cavity.pulse_status == val


def test_rf_permit(cavity):
    cavity._rf_permit_pv_obj = make_mock_pv(get_val=1)
    assert cavity.rf_permit == 1


def test_rf_inhibited(cavity):
    cavity._rf_permit_pv_obj = make_mock_pv(get_val=1)
    assert not cavity.rf_inhibited

    cavity._rf_permit_pv_obj = make_mock_pv(get_val=0)
    assert cavity.rf_inhibited


def test_ades(cavity):
    val = randint(0, 21)
    cavity._ades_pv_obj = make_mock_pv(get_val=val)
    assert cavity.ades == val


def test_acon(cavity):
    val = randint(0, 21)
    cavity._acon_pv_obj = make_mock_pv(get_val=val)
    assert cavity.acon == val


def test_aact(cavity):
    val = randint(0, 21)
    cavity._aact_pv_obj = make_mock_pv(get_val=val)
    assert cavity.aact == val


def test_ades_max(cavity):
    val = randint(0, 21)
    cavity._ades_max_pv_obj = make_mock_pv(get_val=val)
    assert cavity.ades_max == val


def test_edm_macro_string(cavity):
    cavity = MACHINE.cryomodules["01"].cavities[1]
    assert cavity.edm_macro_string == "C=1,RFS=1A,R=A,CM=ACCL:L0B:01,ID=01,CH=1"


def test_edm_macro_string_rack_b(cavity):
    cav = MACHINE.cryomodules["01"].cavities[5]
    assert cav.edm_macro_string == "C=5,RFS=1B,R=B,CM=ACCL:L0B:01,ID=01,CH=1"


def test_cryo_edm_macro_string(cavity):
    assert (
        cavity.cryo_edm_macro_string
        == f"CM={cavity.cryomodule.name},AREA={cavity.linac.name}"
    )


def test_hw_mode(cavity):
    cavity._hw_mode_pv_obj = make_mock_pv(get_val=HW_MODE_ONLINE_VALUE)
    assert cavity.hw_mode == HW_MODE_ONLINE_VALUE


def test_is_online(cavity):
    cavity._hw_mode_pv_obj = make_mock_pv(get_val=HW_MODE_ONLINE_VALUE)
    assert cavity.is_online

    cavity._hw_mode_pv_obj = make_mock_pv(get_val=HW_MODE_OFFLINE_VALUE)
    assert not cavity.is_online


def test_chirp_freq_start(cavity):
    val = -200000
    cavity._chirp_freq_start_pv_obj = make_mock_pv(get_val=val)
    assert cavity.chirp_freq_start == val

    new_val = -400000
    cavity.chirp_freq_start = new_val
    cavity._chirp_freq_start_pv_obj.put.assert_called_with(new_val)


def test_chirp_freq_stop(cavity):
    val = 200000
    cavity._chirp_freq_stop_pv_obj = make_mock_pv(get_val=val)
    assert cavity.chirp_freq_stop == val

    new_val = 400000
    cavity.chirp_freq_stop = new_val
    cavity._chirp_freq_stop_pv_obj.put.assert_called_with(new_val)


def test_calculate_probe_q(cavity):
    cavity._calc_probe_q_pv_obj = make_mock_pv()
    cavity.calculate_probe_q()
    cavity._calc_probe_q_pv_obj.put.assert_called_with(1)


def test_set_chirp_range(cavity):
    cavity._chirp_freq_start_pv_obj = make_mock_pv()
    cavity._chirp_freq_stop_pv_obj = make_mock_pv()
    offset = randint(-400000, 0)
    cavity.set_chirp_range(offset)
    cavity._chirp_freq_start_pv_obj.put.assert_called_with(offset)
    cavity._chirp_freq_stop_pv_obj.put.assert_called_with(-offset)


def test_rf_state(cavity):
    cavity._rf_state_pv_obj = make_mock_pv(get_val=1)
    assert cavity.rf_state == 1


def test_is_on(cavity):
    cavity._rf_state_pv_obj = make_mock_pv(get_val=1)
    assert cavity.is_on

    cavity._rf_state_pv_obj = make_mock_pv(cavity.rf_state_pv, get_val=0)
    assert not cavity.is_on


def test_move_to_resonance_chirp(cavity):
    cavity._tune_config_pv_obj = make_mock_pv()

    cavity.setup_tuning = MagicMock()
    cavity._auto_tune = MagicMock()

    cavity.move_to_resonance(use_sela=False)
    cavity.setup_tuning.assert_called_with(use_sela=False)
    cavity._auto_tune.assert_called()
    cavity._tune_config_pv_obj.put.assert_called_with(
        TUNE_CONFIG_RESONANCE_VALUE
    )


def test_move_to_resonance_sela(cavity):
    cavity._tune_config_pv_obj = make_mock_pv()
    gain = randint(0, 40)
    cavity.piezo._hz_per_v_pv_obj = make_mock_pv(get_val=gain)

    cavity.setup_tuning = MagicMock()
    cavity._auto_tune = MagicMock()

    cavity.move_to_resonance(use_sela=True)
    cavity.setup_tuning.assert_called_with(use_sela=True)
    cavity._auto_tune.assert_called()
    cavity.piezo._hz_per_v_pv_obj.get.assert_called()
    cavity._tune_config_pv_obj.put.assert_called_with(
        TUNE_CONFIG_RESONANCE_VALUE
    )


def test_detune_best(cavity):
    val = randint(-400000, 400000)
    cavity._detune_best_pv_obj = make_mock_pv(get_val=val)
    assert cavity.detune_best == val


def test_detune_chirp(cavity):
    val = randint(-400000, 400000)
    cavity._detune_chirp_pv_obj = make_mock_pv(get_val=val)
    assert cavity.detune_chirp == val


def test_detune(cavity):
    cavity._rf_mode_pv_obj = make_mock_pv(get_val=RF_MODE_SELA)
    val = randint(-400000, 400000)
    cavity._detune_best_pv_obj = make_mock_pv(get_val=val)
    assert cavity.detune == val


def test_detune_in_chirp(cavity):
    cavity._rf_mode_pv_obj = make_mock_pv(get_val=RF_MODE_CHIRP)
    val = randint(-400000, 400000)
    cavity._detune_chirp_pv_obj = make_mock_pv(get_val=val)
    assert cavity.detune == val


def test_detune_invalid(cavity):
    cavity._detune_best_pv_obj = make_mock_pv(severity=EPICS_INVALID_VAL)
    cavity._rf_mode_pv_obj = make_mock_pv(get_val=RF_MODE_SELA)
    assert cavity.detune_invalid

    cavity._detune_best_pv_obj.severity = EPICS_NO_ALARM_VAL
    assert not cavity.detune_invalid


def test_detune_invalid_chirp(cavity):
    cavity._detune_chirp_pv_obj = make_mock_pv(severity=EPICS_INVALID_VAL)
    cavity._rf_mode_pv_obj = make_mock_pv(get_val=RF_MODE_CHIRP)
    assert cavity.detune_invalid

    cavity._detune_chirp_pv_obj.severity = EPICS_NO_ALARM_VAL
    assert not cavity.detune_invalid


def test__auto_tune_invalid(cavity):
    """
    TODO figure out how to test the guts when detune > tolerance
    """
    cavity._rf_mode_pv_obj = make_mock_pv(get_val=RF_MODE_CHIRP)
    cavity._detune_chirp_pv_obj = make_mock_pv(severity=EPICS_INVALID_VAL)

    # delta_hz_func argument is unnecessary
    with pytest.raises(DetuneError):
        cavity._auto_tune(mock_func)


class MockDetune:
    def __init__(self):
        self.num_calls = 0

    def mock_detune(self):
        self.num_calls += 1
        print(f"Mock detune called {self.num_calls}x")

        if self.num_calls > 1:
            return randint(-50, 50)

        else:
            return randint(500, 1000)


def test__auto_tune_out_of_tol(cavity):
    cavity._rf_mode_pv_obj = make_mock_pv(get_val=RF_MODE_CHIRP)
    cavity._detune_chirp_pv_obj = make_mock_pv(severity=EPICS_NO_ALARM_VAL)
    cavity.stepper_tuner.move = MagicMock()
    cavity._tune_config_pv_obj = make_mock_pv(get_val=HW_MODE_ONLINE_VALUE)
    mock_detune = MockDetune()
    cavity._auto_tune(delta_hz_func=mock_detune.mock_detune)
    cavity.stepper_tuner.move.assert_called()
    assert mock_detune.num_calls == 2


def test_check_detune(cavity):
    cavity._rf_mode_pv_obj = make_mock_pv(get_val=RF_MODE_CHIRP)
    cavity._detune_chirp_pv_obj = make_mock_pv(severity=EPICS_INVALID_VAL)
    cavity._chirp_freq_start_pv_obj = make_mock_pv(
        cavity.chirp_freq_start_pv, get_val=50000
    )
    cavity.find_chirp_range = MagicMock()
    cavity.check_detune()
    cavity.find_chirp_range.assert_called_with(50000 * 1.1)


def test_check_detune_sela(cavity):
    cavity._rf_mode_pv_obj = make_mock_pv(get_val=RF_MODE_SELA)
    cavity._detune_best_pv_obj = make_mock_pv(severity=EPICS_INVALID_VAL)
    with pytest.raises(DetuneError):
        cavity.check_detune()


def test_check_and_set_on_time(cavity):
    cavity._pulse_on_time_pv_obj = make_mock_pv(
        cavity.pulse_on_time_pv, NOMINAL_PULSED_ONTIME * 0.9
    )
    cavity.push_go_button = MagicMock()
    cavity.check_and_set_on_time()
    cavity._pulse_on_time_pv_obj.put.assert_called_with(NOMINAL_PULSED_ONTIME)
    cavity.push_go_button.assert_called()


def test_push_go_button(cavity):
    cavity._pulse_status_pv_obj = make_mock_pv(
        cavity.pulse_status_pv, get_val=2
    )
    cavity._pulse_go_pv_obj = make_mock_pv(cavity.pulse_go_pv)
    cavity.push_go_button()
    cavity._pulse_go_pv_obj.put.assert_called_with(1, wait=False)


def test_turn_on_not_online(cavity):
    for hw_status in range(1, 5):
        cavity._hw_mode_pv_obj = make_mock_pv(get_val=hw_status)
        with pytest.raises(CavityHWModeError):
            cavity.turn_on()


def test_turn_on(cavity):
    cavity._hw_mode_pv_obj = make_mock_pv(get_val=HW_MODE_ONLINE_VALUE)
    cavity.ssa.turn_on = MagicMock()
    cavity.reset_interlocks = MagicMock()
    cavity._rf_state_pv_obj = make_mock_pv(cavity.rf_state_pv, get_val=1)
    cavity._rf_control_pv_obj = make_mock_pv()

    cavity.turn_on()
    cavity.ssa.turn_on.assert_called()
    cavity.reset_interlocks.assert_called()
    cavity._rf_state_pv_obj.get.assert_called()
    cavity._rf_control_pv_obj.put.assert_called_with(1)


def test_turn_off(cavity):
    cavity._rf_control_pv_obj = make_mock_pv()
    cavity._rf_state_pv_obj = make_mock_pv(get_val=0)
    cavity.turn_off()
    cavity._rf_control_pv_obj.put.assert_called_with(0)
    cavity._rf_state_pv_obj.get.assert_called()


def test_setup_selap(cavity):
    cavity.setup_rf = MagicMock()
    cavity.set_selap_mode = MagicMock()
    cavity.setup_selap(5)
    cavity.setup_rf.assert_called_with(5)
    cavity.set_selap_mode.assert_called()


def test_setup_sela(cavity):
    cavity.setup_rf = MagicMock()
    cavity.set_sela_mode = MagicMock()
    cavity.setup_sela(5)
    cavity.setup_rf.assert_called_with(5)
    cavity.set_sela_mode.assert_called()


def test_check_abort(cavity):
    cavity.abort_flag = True
    cavity._rf_control_pv_obj = make_mock_pv()
    cavity._rf_state_pv_obj = make_mock_pv(get_val=0)
    with pytest.raises(CavityAbortError):
        cavity.check_abort()

    try:
        cavity.abort_flag = False
        cavity.check_abort()
    except CavityAbortError:
        assert False


def test_setup_rf(cavity):
    cavity.turn_off = MagicMock()
    cavity.ssa.calibrate = MagicMock()
    cavity._ades_max_pv_obj = make_mock_pv(get_val=21)
    cavity.ssa._saved_drive_max_pv_obj = make_mock_pv(get_val=0.8)
    cavity.move_to_resonance = MagicMock()
    cavity.characterize = MagicMock()
    cavity.calculate_probe_q = MagicMock()
    cavity.reset_data_decimation = MagicMock()
    cavity.check_abort = MagicMock()
    cavity._ades_pv_obj = make_mock_pv(get_val=5)
    cavity.set_sel_mode = MagicMock()
    cavity.piezo.enable_feedback = MagicMock()
    cavity.set_sela_mode = MagicMock()
    cavity.walk_amp = MagicMock()

    cavity.setup_rf(5)
    cavity.ssa.calibrate.assert_called()


def test_reset_data_decimation(cavity):
    cavity._cw_data_decim_pv_obj = make_mock_pv()
    cavity._pulsed_data_decim_pv_obj = make_mock_pv()
    cavity.reset_data_decimation()
    cavity._cw_data_decim_pv_obj.put.assert_called_with(255)
    cavity._pulsed_data_decim_pv_obj.put.assert_called_with(255)


def test_setup_tuning_sela(cavity):
    cavity.piezo.enable = MagicMock()
    cavity.piezo.enable_feedback = MagicMock()
    cavity.set_sela_mode = MagicMock()
    cavity.turn_on = MagicMock()

    cavity.setup_tuning(use_sela=True)
    cavity.piezo.enable.assert_called()
    cavity.piezo.enable_feedback.assert_called()
    cavity.turn_on.assert_called()


def test_setup_tuning_not_sela(cavity):
    cavity.piezo.enable = MagicMock()
    cavity.set_sela_mode = MagicMock()
    cavity.turn_on = MagicMock()
    cavity.piezo.disable_feedback = MagicMock()
    cavity.piezo._dc_setpoint_pv_obj = make_mock_pv()
    cavity._drive_level_pv_obj = make_mock_pv()
    cavity.set_chirp_mode = MagicMock()
    cavity.find_chirp_range = MagicMock()

    cavity.setup_tuning(use_sela=False)
    cavity.piezo.enable.assert_called()
    cavity.turn_on.assert_called()
    cavity.piezo._dc_setpoint_pv_obj.put.assert_called_with(0)
    cavity._drive_level_pv_obj.put.assert_called_with(SAFE_PULSED_DRIVE_LEVEL)
    cavity.set_chirp_mode.assert_called()
    cavity.find_chirp_range.assert_called()


def test_find_chirp_range_valid(cavity):
    cavity.set_chirp_range = MagicMock()
    cavity._rf_mode_pv_obj = make_mock_pv(get_val=RF_MODE_CHIRP)
    cavity._detune_chirp_pv_obj = make_mock_pv(severity=EPICS_NO_ALARM_VAL)

    cavity.find_chirp_range(50000)
    cavity.set_chirp_range.assert_called_with(50000)


def test_reset_interlocks(cavity):
    cavity._interlock_reset_pv_obj = make_mock_pv()
    cavity._rf_permit_pv_obj = make_mock_pv(get_val=0)
    with pytest.raises(CavityFaultError):
        cavity.reset_interlocks(attempt=INTERLOCK_RESET_ATTEMPTS)

    cavity._interlock_reset_pv_obj.put.assert_called_with(1)


def test_characterization_timestamp(cavity):
    cavity._char_timestamp_pv_obj = make_mock_pv(get_val="2024-04-11-15:17:17")
    assert cavity.characterization_timestamp == datetime(
        2024, 4, 11, 15, 17, 17
    )


def test_characterize(cavity):
    """
    TODO test characterization running
    """
    cavity.reset_interlocks = MagicMock()
    cavity._drive_level_pv_obj = make_mock_pv()
    char_time = (datetime.now() - timedelta(seconds=100)).strftime(
        "%Y-%m-%d-%H:%M:%S"
    )
    cavity._char_timestamp_pv_obj = make_mock_pv(get_val=char_time)
    cavity.finish_characterization = MagicMock()
    cavity.start_characterization = MagicMock()
    cavity._characterization_status_pv_obj = make_mock_pv(
        get_val=CALIBRATION_COMPLETE_VALUE
    )

    cavity.characterize()
    cavity.reset_interlocks.assert_called()
    cavity._drive_level_pv_obj.put.assert_called_with(SAFE_PULSED_DRIVE_LEVEL)
    cavity.start_characterization.assert_called()
    cavity.finish_characterization.assert_called()


def test_characterize_fail(cavity):
    cavity.reset_interlocks = MagicMock()
    cavity._drive_level_pv_obj = make_mock_pv()
    char_time = (datetime.now() - timedelta(seconds=100)).strftime(
        "%Y-%m-%d-%H:%M:%S"
    )
    cavity._char_timestamp_pv_obj = make_mock_pv(get_val=char_time)
    cavity.start_characterization = MagicMock()
    cavity._characterization_status_pv_obj = make_mock_pv(
        get_val=CHARACTERIZATION_CRASHED_VALUE
    )
    with pytest.raises(CavityCharacterizationError):
        cavity.characterize()
    cavity.reset_interlocks.assert_called()
    cavity._drive_level_pv_obj.put.assert_called_with(SAFE_PULSED_DRIVE_LEVEL)
    cavity.start_characterization.assert_called()


def test_characterize_recent(cavity):
    cavity.reset_interlocks = MagicMock()
    cavity._drive_level_pv_obj = make_mock_pv()
    char_time = (datetime.now() - timedelta(seconds=10)).strftime(
        "%Y-%m-%d-%H:%M:%S"
    )
    cavity._char_timestamp_pv_obj = make_mock_pv(get_val=char_time)
    cavity.finish_characterization = MagicMock()
    cavity._characterization_status_pv_obj = make_mock_pv(
        get_val=CALIBRATION_COMPLETE_VALUE
    )

    cavity.characterize()
    cavity.reset_interlocks.assert_called()
    cavity._drive_level_pv_obj.put.assert_called_with(SAFE_PULSED_DRIVE_LEVEL)
    cavity.finish_characterization.assert_called()


def test_finish_characterization(cavity):
    cavity._measured_loaded_q_pv_obj = make_mock_pv(
        get_val=randint(
            cavity.loaded_q_lower_limit,
            cavity.loaded_q_upper_limit,
        )
    )
    cavity.push_loaded_q = MagicMock()
    cavity._measured_scale_factor_pv_obj = make_mock_pv(
        get_val=randint(
            cavity.scale_factor_lower_limit,
            cavity.scale_factor_upper_limit,
        )
    )
    cavity.push_scale_factor = MagicMock()
    cavity.reset_data_decimation = MagicMock()
    cavity.piezo._feedback_setpoint_pv_obj = make_mock_pv()

    cavity.finish_characterization()
    cavity.push_loaded_q.assert_called()
    cavity.push_scale_factor.assert_called()
    cavity.reset_data_decimation.assert_called()
    cavity.piezo._feedback_setpoint_pv_obj.put.assert_called_with(0)


def test_walk_amp_quench(cavity):
    cavity._ades_pv_obj = make_mock_pv(get_val=0)
    cavity._quench_latch_pv_obj = make_mock_pv(get_val=1)
    cavity._ades_pv_obj = make_mock_pv(get_val=16)
    with pytest.raises(QuenchError):
        cavity.walk_amp(des_amp=16.6, step_size=0.1)


def test_walk_amp(cavity):
    cavity._quench_latch_pv_obj = make_mock_pv(get_val=0)
    cavity._ades_pv_obj = make_mock_pv(get_val=16.05)
    cavity.walk_amp(16.1, 0.1)
    cavity._ades_pv_obj.put.assert_called_with(16.1)


def test_is_offline(cavity):
    cavity._hw_mode_pv_obj = make_mock_pv(get_val=HW_MODE_OFFLINE_VALUE)
    assert cavity.is_offline
