from datetime import datetime, timedelta
from random import randint
from unittest import TestCase
from unittest.mock import MagicMock

from lcls_tools.common.controls.pyepics.utils import (
    EPICS_INVALID_VAL,
    EPICS_NO_ALARM_VAL,
    make_mock_pv,
)

from utils.sc_linac.cavity import Cavity
from utils.sc_linac.linac import MACHINE
from utils.sc_linac.linac_utils import (
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
)


class TestCavity(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.non_hl_iterator = MACHINE.non_hl_iterator
        cls.hl_iterator = MACHINE.hl_iterator

        cls.hz_per_microstep = 0.00540801
        cls.measured_loaded_q = 4.41011e07

    def setUp(self):
        self.non_hl_cavity: Cavity = next(self.non_hl_iterator)
        self.detune_calls = 0

    def test_pv_prefix(self):
        cavity = MACHINE.cryomodules["01"].cavities[1]
        self.assertEqual(cavity.pv_prefix, "ACCL:L0B:0110:")

    def test_loaded_q_limits(self):
        self.assertEqual(self.non_hl_cavity.loaded_q_lower_limit, LOADED_Q_LOWER_LIMIT)
        self.assertEqual(self.non_hl_cavity.loaded_q_upper_limit, LOADED_Q_UPPER_LIMIT)

    def test_microsteps_per_hz(self):
        self.non_hl_cavity.stepper_tuner._hz_per_microstep_pv_obj = make_mock_pv(
            get_val=self.hz_per_microstep
        )
        self.assertEqual(
            self.non_hl_cavity.microsteps_per_hz, 1 / self.hz_per_microstep
        )

    def test_start_characterization(self):
        self.non_hl_cavity._characterization_start_pv_obj = make_mock_pv()
        self.non_hl_cavity.start_characterization()
        self.non_hl_cavity._characterization_start_pv_obj.put.assert_called_with(1)

    def test_cw_data_decimation(self):
        val = randint(0, 256)
        self.non_hl_cavity._cw_data_decim_pv_obj = make_mock_pv(get_val=val)
        self.assertEqual(self.non_hl_cavity.cw_data_decimation, val)

    def test_pulsed_data_decimation(self):
        val = randint(0, 256)
        self.non_hl_cavity._pulsed_data_decim_pv_obj = make_mock_pv(get_val=val)
        self.assertEqual(self.non_hl_cavity.pulsed_data_decimation, val)

    def test_rf_control(self):
        self.non_hl_cavity._rf_control_pv_obj = make_mock_pv(get_val=1)
        self.assertEqual(self.non_hl_cavity.rf_control, 1)

    def test_rf_mode(self):
        mode = randint(0, 6)
        self.non_hl_cavity._rf_mode_pv_obj = make_mock_pv(get_val=mode)
        self.assertEqual(self.non_hl_cavity.rf_mode, mode)

    def test_set_chirp_mode(self):
        self.non_hl_cavity._rf_control_pv_obj = make_mock_pv()
        self.non_hl_cavity._rf_mode_ctrl_pv_obj = make_mock_pv()
        self.non_hl_cavity.set_chirp_mode()
        self.non_hl_cavity._rf_mode_ctrl_pv_obj.put.assert_called_with(RF_MODE_CHIRP)

    def test_set_sel_mode(self):
        self.non_hl_cavity._rf_mode_ctrl_pv_obj = make_mock_pv()
        self.non_hl_cavity.set_sel_mode()
        self.non_hl_cavity._rf_mode_ctrl_pv_obj.put.assert_called_with(RF_MODE_SEL)

    def test_set_sela_mode(self):
        self.non_hl_cavity._rf_mode_ctrl_pv_obj = make_mock_pv()
        self.non_hl_cavity.set_sela_mode()
        self.non_hl_cavity._rf_mode_ctrl_pv_obj.put.assert_called_with(RF_MODE_SELA)

    def test_set_selap_mode(self):
        self.non_hl_cavity._rf_mode_ctrl_pv_obj = make_mock_pv()
        self.non_hl_cavity.set_selap_mode()
        self.non_hl_cavity._rf_mode_ctrl_pv_obj.put.assert_called_with(
            RF_MODE_SELAP, use_caput=False
        )

    def test_drive_level(self):
        val = randint(0, 100)
        self.non_hl_cavity._drive_level_pv_obj = make_mock_pv(get_val=val)
        self.assertEqual(self.non_hl_cavity.drive_level, val)

    def test_push_ssa_slope(self):
        self.non_hl_cavity._push_ssa_slope_pv_obj = make_mock_pv()
        self.non_hl_cavity.push_ssa_slope()
        self.non_hl_cavity._push_ssa_slope_pv_obj.put.assert_called_with(1)

    def test_save_ssa_slope(self):
        self.non_hl_cavity._save_ssa_slope_pv_obj = make_mock_pv()
        self.non_hl_cavity.save_ssa_slope()
        self.non_hl_cavity._save_ssa_slope_pv_obj.put.assert_called_with(1)

    def test_measured_loaded_q(self):
        self.non_hl_cavity._measured_loaded_q_pv_obj = make_mock_pv(
            get_val=self.measured_loaded_q
        )
        self.assertEqual(self.non_hl_cavity.measured_loaded_q, self.measured_loaded_q)

    def test_measured_loaded_q_in_tolerance(self):
        in_tol_val = randint(LOADED_Q_LOWER_LIMIT, LOADED_Q_UPPER_LIMIT)
        self.non_hl_cavity._measured_loaded_q_pv_obj = make_mock_pv(get_val=in_tol_val)
        self.assertTrue(
            self.non_hl_cavity.measured_loaded_q_in_tolerance,
            msg=f"loaded q {in_tol_val} should be in tolerance",
        )

    def test_measured_loaded_q_in_tolerance_hl(self):
        in_tol_val = randint(LOADED_Q_LOWER_LIMIT_HL, LOADED_Q_UPPER_LIMIT_HL)
        hl_cavity: Cavity = next(self.hl_iterator)
        hl_cavity._measured_loaded_q_pv_obj = make_mock_pv(get_val=in_tol_val)
        self.assertTrue(
            hl_cavity.measured_loaded_q_in_tolerance,
            msg=f"loaded q {in_tol_val} should be in tolerance",
        )

    def test_loaded_q_high(self):
        high_val = randint(LOADED_Q_UPPER_LIMIT, LOADED_Q_UPPER_LIMIT * 10)
        self.non_hl_cavity._measured_loaded_q_pv_obj = make_mock_pv(get_val=high_val)
        self.assertFalse(
            self.non_hl_cavity.measured_loaded_q_in_tolerance,
            msg=f"loaded q {high_val} should be out of tolerance",
        )

    def test_loaded_q_high_hl(self):
        high_val = randint(LOADED_Q_UPPER_LIMIT_HL, LOADED_Q_UPPER_LIMIT_HL * 10)
        hl_cavity: Cavity = next(self.hl_iterator)
        hl_cavity._measured_loaded_q_pv_obj = make_mock_pv(get_val=high_val)
        self.assertFalse(
            hl_cavity.measured_loaded_q_in_tolerance,
            msg=f"loaded q {high_val} should be out of tolerance",
        )

    def test_loaded_q_low(self):
        low_val = randint(0, LOADED_Q_LOWER_LIMIT)
        self.non_hl_cavity._measured_loaded_q_pv_obj = make_mock_pv(get_val=low_val)
        self.assertFalse(
            self.non_hl_cavity.measured_loaded_q_in_tolerance,
            msg=f"loaded q {low_val} should be out of tolerance",
        )

    def test_loaded_q_low_hl(self):
        low_val = randint(0, LOADED_Q_LOWER_LIMIT_HL)
        hl_cavity: Cavity = next(self.hl_iterator)
        hl_cavity._measured_loaded_q_pv_obj = make_mock_pv(get_val=low_val)
        self.assertFalse(
            hl_cavity.measured_loaded_q_in_tolerance,
            msg=f"loaded q {low_val} should be out of tolerance",
        )

    def test_push_loaded_q(self):
        self.non_hl_cavity._push_loaded_q_pv_obj = make_mock_pv()
        self.non_hl_cavity.push_loaded_q()
        self.non_hl_cavity._push_loaded_q_pv_obj.put.assert_called_with(1)

    def test_measured_scale_factor(self):
        val = randint(CAVITY_SCALE_LOWER_LIMIT_HL, CAVITY_SCALE_UPPER_LIMIT_HL)
        self.non_hl_cavity._measured_scale_factor_pv_obj = make_mock_pv(get_val=val)
        self.assertEqual(self.non_hl_cavity.measured_scale_factor, val)

    def test_measured_scale_factor_in_tolerance_hl(self):
        val = randint(CAVITY_SCALE_LOWER_LIMIT_HL, CAVITY_SCALE_UPPER_LIMIT_HL)
        hl_cavity: Cavity = next(self.hl_iterator)
        hl_cavity._measured_scale_factor_pv_obj = make_mock_pv(get_val=val)
        self.assertTrue(
            hl_cavity.measured_scale_factor_in_tolerance,
            f"scale factor {val} not in tol for {hl_cavity}",
        )

    def test_measured_scale_factor_in_tolerance(self):
        val = randint(CAVITY_SCALE_LOWER_LIMIT, CAVITY_SCALE_UPPER_LIMIT)
        self.non_hl_cavity._measured_scale_factor_pv_obj = make_mock_pv(get_val=val)
        self.assertTrue(self.non_hl_cavity.measured_scale_factor_in_tolerance)

    def test_scale_factor_high(self):
        val = randint(CAVITY_SCALE_UPPER_LIMIT, CAVITY_SCALE_UPPER_LIMIT * 2)
        self.non_hl_cavity._measured_scale_factor_pv_obj = make_mock_pv(get_val=val)
        self.assertFalse(self.non_hl_cavity.measured_scale_factor_in_tolerance)

    def test_scale_factor_high_hl(self):
        val = randint(CAVITY_SCALE_UPPER_LIMIT_HL + 1, CAVITY_SCALE_UPPER_LIMIT_HL * 2)
        hl_cavity: Cavity = next(self.hl_iterator)
        hl_cavity._measured_scale_factor_pv_obj = make_mock_pv(get_val=val)
        self.assertFalse(hl_cavity.measured_scale_factor_in_tolerance)

    def test_scale_factor_low(self):
        val = randint(0, CAVITY_SCALE_LOWER_LIMIT - 1)
        self.non_hl_cavity._measured_scale_factor_pv_obj = make_mock_pv(get_val=val)
        self.assertFalse(self.non_hl_cavity.measured_scale_factor_in_tolerance)

    def test_scale_factor_low_hl(self):
        val = randint(0, CAVITY_SCALE_LOWER_LIMIT_HL - 1)
        hl_cavity: Cavity = next(self.hl_iterator)
        hl_cavity._measured_scale_factor_pv_obj = make_mock_pv(get_val=val)
        self.assertFalse(hl_cavity.measured_scale_factor_in_tolerance)

    def test_push_scale_factor(self):
        self.non_hl_cavity._push_scale_factor_pv_obj = make_mock_pv()
        self.non_hl_cavity.push_scale_factor()
        self.non_hl_cavity._push_scale_factor_pv_obj.put.assert_called_with(1)

    def test_characterization_status(self):
        val = randint(0, 3)
        self.non_hl_cavity._characterization_status_pv_obj = make_mock_pv(get_val=val)
        self.assertEqual(self.non_hl_cavity.characterization_status, val)

    def test_characterization_running(self):
        self.non_hl_cavity._characterization_status_pv_obj = make_mock_pv(
            get_val=CHARACTERIZATION_RUNNING_VALUE,
        )
        self.assertTrue(
            self.non_hl_cavity.characterization_running,
        )

        self.non_hl_cavity._characterization_status_pv_obj = make_mock_pv(
            get_val=CHARACTERIZATION_CRASHED_VALUE,
        )
        self.assertFalse(
            self.non_hl_cavity.characterization_running,
        )

    def test_characterization_crashed(self):
        self.non_hl_cavity._characterization_status_pv_obj = make_mock_pv(
            get_val=CHARACTERIZATION_CRASHED_VALUE,
        )
        self.assertTrue(
            self.non_hl_cavity.characterization_crashed,
        )

        self.non_hl_cavity._characterization_status_pv_obj = make_mock_pv(
            get_val=CHARACTERIZATION_RUNNING_VALUE,
        )
        self.assertFalse(
            self.non_hl_cavity.characterization_crashed,
        )

    def test_pulse_on_time(self):
        self.non_hl_cavity._pulse_on_time_pv_obj = make_mock_pv(get_val=70)
        self.assertEqual(self.non_hl_cavity.pulse_on_time, 70)

    def test_pulse_status(self):
        val = randint(0, 5)
        self.non_hl_cavity._pulse_status_pv_obj = make_mock_pv(get_val=val)
        self.assertEqual(self.non_hl_cavity.pulse_status, val)

    def test_rf_permit(self):
        self.non_hl_cavity._rf_permit_pv_obj = make_mock_pv(get_val=1)
        self.assertEqual(self.non_hl_cavity.rf_permit, 1)

    def test_rf_inhibited(self):
        self.non_hl_cavity._rf_permit_pv_obj = make_mock_pv(get_val=1)
        self.assertFalse(self.non_hl_cavity.rf_inhibited)

        self.non_hl_cavity._rf_permit_pv_obj = make_mock_pv(get_val=0)
        self.assertTrue(self.non_hl_cavity.rf_inhibited)

    def test_ades(self):
        val = randint(0, 21)
        self.non_hl_cavity._ades_pv_obj = make_mock_pv(get_val=val)
        self.assertEqual(self.non_hl_cavity.ades, val)

    def test_acon(self):
        val = randint(0, 21)
        self.non_hl_cavity._acon_pv_obj = make_mock_pv(get_val=val)
        self.assertEqual(self.non_hl_cavity.acon, val)

    def test_aact(self):
        val = randint(0, 21)
        self.non_hl_cavity._aact_pv_obj = make_mock_pv(get_val=val)
        self.assertEqual(self.non_hl_cavity.aact, val)

    def test_ades_max(self):
        val = randint(0, 21)
        self.non_hl_cavity._ades_max_pv_obj = make_mock_pv(get_val=val)
        self.assertEqual(self.non_hl_cavity.ades_max, val)

    def test_edm_macro_string(self):
        cavity = MACHINE.cryomodules["01"].cavities[1]
        self.assertEqual(
            cavity.edm_macro_string, "C=1,RFS=1A,R=A,CM=ACCL:L0B:01,ID=01,CH=1"
        )

    def test_edm_macro_string_rack_b(self):
        cav = MACHINE.cryomodules["01"].cavities[5]
        self.assertEqual(
            cav.edm_macro_string, "C=5,RFS=1B,R=B,CM=ACCL:L0B:01,ID=01,CH=1"
        )

    def test_hw_mode(self):
        self.non_hl_cavity._hw_mode_pv_obj = make_mock_pv(get_val=HW_MODE_ONLINE_VALUE)
        self.assertEqual(self.non_hl_cavity.hw_mode, HW_MODE_ONLINE_VALUE)

    def test_is_online(self):
        self.non_hl_cavity._hw_mode_pv_obj = make_mock_pv(get_val=HW_MODE_ONLINE_VALUE)
        self.assertTrue(self.non_hl_cavity.is_online)

        self.non_hl_cavity._hw_mode_pv_obj = make_mock_pv(get_val=HW_MODE_OFFLINE_VALUE)
        self.assertFalse(self.non_hl_cavity.is_online)

    def test_chirp_freq_start(self):
        val = -200000
        self.non_hl_cavity._chirp_freq_start_pv_obj = make_mock_pv(get_val=val)
        self.assertEqual(self.non_hl_cavity.chirp_freq_start, val)

        new_val = -400000
        self.non_hl_cavity.chirp_freq_start = new_val
        self.non_hl_cavity._chirp_freq_start_pv_obj.put.assert_called_with(new_val)

    def test_chirp_freq_stop(self):
        val = 200000
        self.non_hl_cavity._freq_stop_pv_obj = make_mock_pv(get_val=val)
        self.assertEqual(self.non_hl_cavity.chirp_freq_stop, val)

        new_val = 400000
        self.non_hl_cavity.chirp_freq_stop = new_val
        self.non_hl_cavity._freq_stop_pv_obj.put.assert_called_with(new_val)

    def test_calculate_probe_q(self):
        self.non_hl_cavity._calc_probe_q_pv_obj = make_mock_pv()
        self.non_hl_cavity.calculate_probe_q()
        self.non_hl_cavity._calc_probe_q_pv_obj.put.assert_called_with(1)

    def test_set_chirp_range(self):
        self.non_hl_cavity._chirp_freq_start_pv_obj = make_mock_pv()
        self.non_hl_cavity._freq_stop_pv_obj = make_mock_pv()
        offset = randint(-400000, 0)
        self.non_hl_cavity.set_chirp_range(offset)
        self.non_hl_cavity._chirp_freq_start_pv_obj.put.assert_called_with(offset)
        self.non_hl_cavity._freq_stop_pv_obj.put.assert_called_with(-offset)

    def test_rf_state(self):
        self.non_hl_cavity._rf_state_pv_obj = make_mock_pv(get_val=1)
        self.assertEqual(self.non_hl_cavity.rf_state, 1)

    def test_is_on(self):
        self.non_hl_cavity._rf_state_pv_obj = make_mock_pv(get_val=1)
        self.assertTrue(self.non_hl_cavity.is_on)

        self.non_hl_cavity._rf_state_pv_obj = make_mock_pv(
            self.non_hl_cavity.rf_state_pv, get_val=0
        )
        self.assertFalse(self.non_hl_cavity.is_on)

    def mock_detune(self):
        """
        Ham-fisted way of having the cavity report as detuned the first loop
        and tuned the second
        """
        self.detune_calls += 1
        print(f"Mock detune called {self.detune_calls}x")

        if self.detune_calls > 1:
            return randint(-50, 50)

        else:
            return randint(500, 1000)

    def test_move_to_resonance(self):
        self.non_hl_cavity._tune_config_pv_obj = make_mock_pv()

        self.non_hl_cavity.setup_tuning = MagicMock()
        self.non_hl_cavity._auto_tune = MagicMock()

        self.non_hl_cavity.move_to_resonance()
        self.non_hl_cavity.setup_tuning.assert_called()
        self.non_hl_cavity._auto_tune.assert_called()
        self.non_hl_cavity._tune_config_pv_obj.put.assert_called_with(
            TUNE_CONFIG_RESONANCE_VALUE
        )

    def test_detune_best(self):
        val = randint(-400000, 400000)
        self.non_hl_cavity._detune_best_pv_obj = make_mock_pv(get_val=val)
        self.assertEqual(self.non_hl_cavity.detune_best, val)

    def test_detune_chirp(self):
        val = randint(-400000, 400000)
        self.non_hl_cavity._detune_chirp_pv_obj = make_mock_pv(get_val=val)
        self.assertEqual(self.non_hl_cavity.detune_chirp, val)

    def test_detune(self):
        self.non_hl_cavity._rf_mode_pv_obj = make_mock_pv(get_val=RF_MODE_SELA)
        val = randint(-400000, 400000)
        self.non_hl_cavity._detune_best_pv_obj = make_mock_pv(get_val=val)
        self.assertEqual(self.non_hl_cavity.detune, val)

    def test_detune_in_chirp(self):
        self.non_hl_cavity._rf_mode_pv_obj = make_mock_pv(get_val=RF_MODE_CHIRP)
        val = randint(-400000, 400000)
        self.non_hl_cavity._detune_chirp_pv_obj = make_mock_pv(get_val=val)
        self.assertEqual(self.non_hl_cavity.detune, val)

    def test_detune_invalid(self):
        self.non_hl_cavity._detune_best_pv_obj = make_mock_pv(
            severity=EPICS_INVALID_VAL
        )
        self.non_hl_cavity._rf_mode_pv_obj = make_mock_pv(get_val=RF_MODE_SELA)
        self.assertTrue(self.non_hl_cavity.detune_invalid)

        self.non_hl_cavity._detune_best_pv_obj.severity = EPICS_NO_ALARM_VAL
        self.assertFalse(self.non_hl_cavity.detune_invalid)

    def test_detune_invalid_chirp(self):
        self.non_hl_cavity._detune_chirp_pv_obj = make_mock_pv(
            severity=EPICS_INVALID_VAL
        )
        self.non_hl_cavity._rf_mode_pv_obj = make_mock_pv(get_val=RF_MODE_CHIRP)
        self.assertTrue(self.non_hl_cavity.detune_invalid)

        self.non_hl_cavity._detune_chirp_pv_obj.severity = EPICS_NO_ALARM_VAL
        self.assertFalse(self.non_hl_cavity.detune_invalid)

    def test__auto_tune_invalid(self):
        """
        TODO figure out how to test the guts when detune > tolerance
        """
        self.non_hl_cavity._rf_mode_pv_obj = make_mock_pv(get_val=RF_MODE_CHIRP)
        self.non_hl_cavity._detune_chirp_pv_obj = make_mock_pv(
            severity=EPICS_INVALID_VAL
        )

        # delta_hz_func argument is unnecessary
        self.assertRaises(DetuneError, self.non_hl_cavity._auto_tune, None)

    def test__auto_tune_out_of_tol(self):
        self.non_hl_cavity._rf_mode_pv_obj = make_mock_pv(get_val=RF_MODE_CHIRP)
        self.non_hl_cavity._detune_chirp_pv_obj = make_mock_pv(
            severity=EPICS_NO_ALARM_VAL
        )
        self.non_hl_cavity.stepper_tuner.move = MagicMock()
        self.non_hl_cavity.stepper_tuner._hz_per_microstep_pv_obj = make_mock_pv(
            get_val=self.hz_per_microstep
        )
        self.non_hl_cavity._tune_config_pv_obj = make_mock_pv(
            get_val=HW_MODE_ONLINE_VALUE
        )

        self.detune_calls = 0
        self.non_hl_cavity._auto_tune(delta_hz_func=self.mock_detune)
        self.non_hl_cavity.stepper_tuner.move.assert_called()
        self.assertEqual(self.detune_calls, 2)

    def test_check_detune(self):
        self.non_hl_cavity._rf_mode_pv_obj = make_mock_pv(get_val=RF_MODE_CHIRP)
        self.non_hl_cavity._detune_chirp_pv_obj = make_mock_pv(
            severity=EPICS_INVALID_VAL
        )
        self.non_hl_cavity._chirp_freq_start_pv_obj = make_mock_pv(
            self.non_hl_cavity.chirp_freq_start_pv, get_val=50000
        )
        self.non_hl_cavity.find_chirp_range = MagicMock()
        self.non_hl_cavity.check_detune()
        self.non_hl_cavity.find_chirp_range.assert_called_with(50000 * 1.1)

    def test_check_detune_sela(self):
        self.non_hl_cavity._rf_mode_pv_obj = make_mock_pv(get_val=RF_MODE_SELA)
        self.non_hl_cavity._detune_best_pv_obj = make_mock_pv(
            severity=EPICS_INVALID_VAL
        )
        self.assertRaises(DetuneError, self.non_hl_cavity.check_detune)

    def test_check_and_set_on_time(self):
        self.non_hl_cavity._pulse_on_time_pv_obj = make_mock_pv(
            self.non_hl_cavity.pulse_on_time_pv, NOMINAL_PULSED_ONTIME * 0.9
        )
        self.non_hl_cavity.push_go_button = MagicMock()
        self.non_hl_cavity.check_and_set_on_time()
        self.non_hl_cavity._pulse_on_time_pv_obj.put.assert_called_with(
            NOMINAL_PULSED_ONTIME
        )
        self.non_hl_cavity.push_go_button.assert_called()

    def test_push_go_button(self):
        self.non_hl_cavity._pulse_status_pv_obj = make_mock_pv(
            self.non_hl_cavity.pulse_status_pv, get_val=2
        )
        self.non_hl_cavity._pulse_go_pv_obj = make_mock_pv(
            self.non_hl_cavity.pulse_go_pv
        )
        self.non_hl_cavity.push_go_button()
        self.non_hl_cavity._pulse_go_pv_obj.put.assert_called_with(1)

    def test_turn_on_not_online(self):
        for hw_status in range(1, 5):
            self.non_hl_cavity._hw_mode_pv_obj = make_mock_pv(get_val=hw_status)
            self.assertRaises(CavityHWModeError, self.non_hl_cavity.turn_on)

    def test_turn_on(self):
        self.non_hl_cavity._hw_mode_pv_obj = make_mock_pv(get_val=HW_MODE_ONLINE_VALUE)
        self.non_hl_cavity.ssa.turn_on = MagicMock()
        self.non_hl_cavity.reset_interlocks = MagicMock()
        self.non_hl_cavity._rf_state_pv_obj = make_mock_pv(
            self.non_hl_cavity.rf_state_pv, get_val=1
        )
        self.non_hl_cavity._rf_control_pv_obj = make_mock_pv()

        self.non_hl_cavity.turn_on()
        self.non_hl_cavity.ssa.turn_on.assert_called()
        self.non_hl_cavity.reset_interlocks.assert_called()
        self.non_hl_cavity._rf_state_pv_obj.get.assert_called()
        self.non_hl_cavity._rf_control_pv_obj.put.assert_called_with(1)

    def test_turn_off(self):
        self.non_hl_cavity._rf_control_pv_obj = make_mock_pv()
        self.non_hl_cavity._rf_state_pv_obj = make_mock_pv(get_val=0)
        self.non_hl_cavity.turn_off()
        self.non_hl_cavity._rf_control_pv_obj.put.assert_called_with(0)
        self.non_hl_cavity._rf_state_pv_obj.get.assert_called()

    def test_setup_selap(self):
        self.non_hl_cavity.setup_rf = MagicMock()
        self.non_hl_cavity.set_selap_mode = MagicMock()
        self.non_hl_cavity.setup_selap(5)
        self.non_hl_cavity.setup_rf.assert_called_with(5)
        self.non_hl_cavity.set_selap_mode.assert_called()

    def test_setup_sela(self):
        self.non_hl_cavity.setup_rf = MagicMock()
        self.non_hl_cavity.set_sela_mode = MagicMock()
        self.non_hl_cavity.setup_sela(5)
        self.non_hl_cavity.setup_rf.assert_called_with(5)
        self.non_hl_cavity.set_sela_mode.assert_called()

    def test_check_abort(self):
        self.non_hl_cavity.abort_flag = True
        self.non_hl_cavity._rf_control_pv_obj = make_mock_pv()
        self.non_hl_cavity._rf_state_pv_obj = make_mock_pv(get_val=0)
        self.assertRaises(CavityAbortError, self.non_hl_cavity.check_abort)

        try:
            self.non_hl_cavity.abort_flag = False
            self.non_hl_cavity.check_abort()
        except CavityAbortError:
            self.fail("Cavity abort error raised when flag not set")

    def test_setup_rf(self):
        self.non_hl_cavity.turn_off = MagicMock()
        self.non_hl_cavity.ssa.calibrate = MagicMock()
        self.non_hl_cavity._ades_max_pv_obj = make_mock_pv(get_val=21)
        self.non_hl_cavity.ssa._saved_drive_max_pv_obj = make_mock_pv(get_val=0.8)
        self.non_hl_cavity.move_to_resonance = MagicMock()
        self.non_hl_cavity.characterize = MagicMock()
        self.non_hl_cavity.calculate_probe_q = MagicMock()
        self.non_hl_cavity.reset_data_decimation = MagicMock()
        self.non_hl_cavity.check_abort = MagicMock()
        self.non_hl_cavity._ades_pv_obj = make_mock_pv(get_val=5)
        self.non_hl_cavity.set_sel_mode = MagicMock()
        self.non_hl_cavity.piezo.enable_feedback = MagicMock()
        self.non_hl_cavity.set_sela_mode = MagicMock()
        self.non_hl_cavity.walk_amp = MagicMock()

        self.non_hl_cavity.setup_rf(5)
        self.non_hl_cavity.ssa.calibrate.assert_called()

    def test_reset_data_decimation(self):
        self.non_hl_cavity._cw_data_decim_pv_obj = make_mock_pv()
        self.non_hl_cavity._pulsed_data_decim_pv_obj = make_mock_pv()
        self.non_hl_cavity.reset_data_decimation()
        self.non_hl_cavity._cw_data_decim_pv_obj.put.assert_called_with(255)
        self.non_hl_cavity._pulsed_data_decim_pv_obj.put.assert_called_with(255)

    def test_setup_tuning_sela(self):
        self.non_hl_cavity.piezo.enable = MagicMock()
        self.non_hl_cavity.piezo.enable_feedback = MagicMock()
        self.non_hl_cavity.set_sela_mode = MagicMock()
        self.non_hl_cavity.turn_on = MagicMock()

        self.non_hl_cavity.setup_tuning(use_sela=True)
        self.non_hl_cavity.piezo.enable.assert_called()
        self.non_hl_cavity.piezo.enable_feedback.assert_called()
        self.non_hl_cavity.turn_on.assert_called()

    def test_setup_tuning_not_sela(self):
        self.non_hl_cavity.piezo.enable = MagicMock()
        self.non_hl_cavity.set_sela_mode = MagicMock()
        self.non_hl_cavity.turn_on = MagicMock()
        self.non_hl_cavity.piezo.disable_feedback = MagicMock()
        self.non_hl_cavity.piezo._dc_setpoint_pv_obj = make_mock_pv()
        self.non_hl_cavity._drive_level_pv_obj = make_mock_pv()
        self.non_hl_cavity.set_chirp_mode = MagicMock()
        self.non_hl_cavity.find_chirp_range = MagicMock()

        self.non_hl_cavity.setup_tuning(use_sela=False)
        self.non_hl_cavity.piezo.enable.assert_called()
        self.non_hl_cavity.turn_on.assert_called()
        self.non_hl_cavity.piezo._dc_setpoint_pv_obj.put.assert_called_with(0)
        self.non_hl_cavity._drive_level_pv_obj.put.assert_called_with(
            SAFE_PULSED_DRIVE_LEVEL
        )
        self.non_hl_cavity.set_chirp_mode.assert_called()
        self.non_hl_cavity.find_chirp_range.assert_called()

    def test_find_chirp_range_valid(self):
        self.non_hl_cavity.set_chirp_range = MagicMock()
        self.non_hl_cavity._rf_mode_pv_obj = make_mock_pv(get_val=RF_MODE_CHIRP)
        self.non_hl_cavity._detune_chirp_pv_obj = make_mock_pv(
            severity=EPICS_NO_ALARM_VAL
        )

        self.non_hl_cavity.find_chirp_range(50000)
        self.non_hl_cavity.set_chirp_range.assert_called_with(50000)

    def test_reset_interlocks(self):
        self.non_hl_cavity._interlock_reset_pv_obj = make_mock_pv()
        self.non_hl_cavity._rf_permit_pv_obj = make_mock_pv(get_val=0)
        self.assertRaises(
            CavityFaultError,
            self.non_hl_cavity.reset_interlocks,
            attempt=INTERLOCK_RESET_ATTEMPTS,
        )
        self.non_hl_cavity._interlock_reset_pv_obj.put.assert_called_with(1)

    def test_characterization_timestamp(self):
        self.non_hl_cavity._char_timestamp_pv_obj = make_mock_pv(
            get_val="2024-04-11-15:17:17"
        )
        self.assertEqual(
            self.non_hl_cavity.characterization_timestamp,
            datetime(2024, 4, 11, 15, 17, 17),
        )

    def test_characterize(self):
        """
        TODO test characterization running
        """
        self.non_hl_cavity.reset_interlocks = MagicMock()
        self.non_hl_cavity._drive_level_pv_obj = make_mock_pv()
        char_time = (datetime.now() - timedelta(seconds=100)).strftime(
            "%Y-%m-%d-%H:%M:%S"
        )
        self.non_hl_cavity._char_timestamp_pv_obj = make_mock_pv(get_val=char_time)
        self.non_hl_cavity.finish_characterization = MagicMock()
        self.non_hl_cavity.start_characterization = MagicMock()
        self.non_hl_cavity._characterization_status_pv_obj = make_mock_pv(
            get_val=CALIBRATION_COMPLETE_VALUE
        )

        self.non_hl_cavity.characterize()
        self.non_hl_cavity.reset_interlocks.assert_called()
        self.non_hl_cavity._drive_level_pv_obj.put.assert_called_with(
            SAFE_PULSED_DRIVE_LEVEL
        )
        self.non_hl_cavity.start_characterization.assert_called()
        self.non_hl_cavity.finish_characterization.assert_called()

    def test_characterize_fail(self):
        self.non_hl_cavity.reset_interlocks = MagicMock()
        self.non_hl_cavity._drive_level_pv_obj = make_mock_pv()
        char_time = (datetime.now() - timedelta(seconds=100)).strftime(
            "%Y-%m-%d-%H:%M:%S"
        )
        self.non_hl_cavity._char_timestamp_pv_obj = make_mock_pv(get_val=char_time)
        self.non_hl_cavity.start_characterization = MagicMock()
        self.non_hl_cavity._characterization_status_pv_obj = make_mock_pv(
            get_val=CHARACTERIZATION_CRASHED_VALUE
        )

        self.assertRaises(CavityCharacterizationError, self.non_hl_cavity.characterize)
        self.non_hl_cavity.reset_interlocks.assert_called()
        self.non_hl_cavity._drive_level_pv_obj.put.assert_called_with(
            SAFE_PULSED_DRIVE_LEVEL
        )
        self.non_hl_cavity.start_characterization.assert_called()

    def test_characterize_recent(self):
        self.non_hl_cavity.reset_interlocks = MagicMock()
        self.non_hl_cavity._drive_level_pv_obj = make_mock_pv()
        char_time = (datetime.now() - timedelta(seconds=10)).strftime(
            "%Y-%m-%d-%H:%M:%S"
        )
        self.non_hl_cavity._char_timestamp_pv_obj = make_mock_pv(get_val=char_time)
        self.non_hl_cavity.finish_characterization = MagicMock()
        self.non_hl_cavity._characterization_status_pv_obj = make_mock_pv(
            get_val=CALIBRATION_COMPLETE_VALUE
        )

        self.non_hl_cavity.characterize()
        self.non_hl_cavity.reset_interlocks.assert_called()
        self.non_hl_cavity._drive_level_pv_obj.put.assert_called_with(
            SAFE_PULSED_DRIVE_LEVEL
        )
        self.non_hl_cavity.finish_characterization.assert_called()

    def test_finish_characterization(self):
        self.non_hl_cavity._measured_loaded_q_pv_obj = make_mock_pv(
            get_val=randint(
                self.non_hl_cavity.loaded_q_lower_limit,
                self.non_hl_cavity.loaded_q_upper_limit,
            )
        )
        self.non_hl_cavity.push_loaded_q = MagicMock()
        self.non_hl_cavity._measured_scale_factor_pv_obj = make_mock_pv(
            get_val=randint(
                self.non_hl_cavity.scale_factor_lower_limit,
                self.non_hl_cavity.scale_factor_upper_limit,
            )
        )
        self.non_hl_cavity.push_scale_factor = MagicMock()
        self.non_hl_cavity.reset_data_decimation = MagicMock()
        self.non_hl_cavity.piezo._feedback_setpoint_pv_obj = make_mock_pv()

        self.non_hl_cavity.finish_characterization()
        self.non_hl_cavity.push_loaded_q.assert_called()
        self.non_hl_cavity.push_scale_factor.assert_called()
        self.non_hl_cavity.reset_data_decimation.assert_called()
        self.non_hl_cavity.piezo._feedback_setpoint_pv_obj.put.assert_called_with(0)

    def test_walk_amp_quench(self):
        self.non_hl_cavity._ades_pv_obj = make_mock_pv(get_val=0)
        self.non_hl_cavity._quench_latch_pv_obj = make_mock_pv(get_val=1)
        self.non_hl_cavity._ades_pv_obj = make_mock_pv(get_val=16)
        self.assertRaises(QuenchError, self.non_hl_cavity.walk_amp, 16.6, 0.1)

    def test_walk_amp(self):
        self.non_hl_cavity._quench_latch_pv_obj = make_mock_pv(get_val=0)
        self.non_hl_cavity._ades_pv_obj = make_mock_pv(get_val=16.05)
        self.non_hl_cavity.walk_amp(16.1, 0.1)
        self.non_hl_cavity._ades_pv_obj.put.assert_called_with(16.1)

    def test_is_offline(self):
        self.non_hl_cavity._hw_mode_pv_obj = make_mock_pv(get_val=HW_MODE_OFFLINE_VALUE)
        self.assertTrue(self.non_hl_cavity.is_offline)
