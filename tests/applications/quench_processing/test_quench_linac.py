from random import choice, randint
from typing import Iterator
from unittest import TestCase, mock
from unittest.mock import MagicMock

from lcls_tools.common.controls.pyepics.utils import (
    make_mock_pv,
    EPICS_INVALID_VAL,
    EPICS_NO_ALARM_VAL,
    EPICS_MINOR_VAL,
    EPICS_MAJOR_VAL,
)
from numpy import pi, exp, linspace

from utils.sc_linac.linac_utils import QuenchError

mock_sleep = MagicMock()
with mock.patch("time.sleep", mock_sleep):
    from applications.quench_processing.quench_linac import (
        QUENCH_MACHINE,
        QuenchCavity,
        LOADED_Q_CHANGE_FOR_QUENCH,
    )


class TestQuenchCavity(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.non_hl_iterator: Iterator[QuenchCavity] = QUENCH_MACHINE.non_hl_iterator

    def setUp(self):
        self.cavity: QuenchCavity = next(self.non_hl_iterator)
        print(f"Testing {self.cavity}")

    def test_current_q_loaded_pv_obj(self):
        self.cavity._current_q_loaded_pv_obj = make_mock_pv()
        self.assertEqual(
            self.cavity._current_q_loaded_pv_obj, self.cavity.current_q_loaded_pv_obj
        )

    def test_quench_latch_pv_obj(self):
        self.cavity._quench_latch_pv_obj = make_mock_pv()
        self.assertEqual(
            self.cavity._quench_latch_pv_obj, self.cavity.quench_latch_pv_obj
        )

    def test_quench_latch_invalid(self):
        severity = choice(
            [
                EPICS_NO_ALARM_VAL,
                EPICS_MINOR_VAL,
                EPICS_MAJOR_VAL,
                EPICS_INVALID_VAL,
            ]
        )
        self.cavity._quench_latch_pv_obj = make_mock_pv(severity=severity)

        if severity == EPICS_INVALID_VAL:
            self.assertTrue(
                self.cavity.quench_latch_invalid,
                msg=f"{self.cavity} quench PV severity {severity} marked as valid",
            )
        else:
            self.assertFalse(
                self.cavity.quench_latch_invalid,
                msg=f"{self.cavity} quench PV severity {severity} marked as invalid",
            )

    def test_quench_intlk_bypassed_true(self):
        self.cavity._quench_bypass_rbck_pv = make_mock_pv(get_val=1)
        self.assertTrue(self.cavity.quench_intlk_bypassed)

    def test_quench_intlk_bypassed_false(self):
        self.cavity._quench_bypass_rbck_pv = make_mock_pv(get_val=0)
        self.assertFalse(self.cavity.quench_intlk_bypassed)

    def test_fault_waveform_pv_obj(self):
        self.cavity._fault_waveform_pv_obj = make_mock_pv()
        self.assertEqual(
            self.cavity._fault_waveform_pv_obj, self.cavity.fault_waveform_pv_obj
        )

    def test_fault_time_waveform_pv_obj(self):
        self.cavity._fault_time_waveform_pv_obj = make_mock_pv()
        self.assertEqual(
            self.cavity._fault_time_waveform_pv_obj,
            self.cavity.fault_time_waveform_pv_obj,
        )

    def test_reset_interlocks(self):
        self.cavity._interlock_reset_pv_obj = make_mock_pv()
        self.cavity.reset_interlocks()
        self.cavity._interlock_reset_pv_obj.put.assert_called_with(1)

    def test_walk_to_quench(self):
        # TODO test actual walking
        end_amp = randint(5, 21)
        self.cavity.reset_interlocks = MagicMock()
        self.cavity._quench_latch_pv_obj = make_mock_pv(get_val=0)
        self.cavity._ades_pv_obj = make_mock_pv(get_val=end_amp)
        self.cavity.check_abort = MagicMock()
        self.cavity.wait = MagicMock()
        self.cavity.walk_to_quench(end_amp=end_amp)

        self.cavity.wait.assert_not_called()
        self.cavity._ades_pv_obj.put.assert_not_called()

    def test_is_quenched_true(self):
        self.cavity._quench_latch_pv_obj = make_mock_pv(get_val=1)
        self.assertTrue(self.cavity.is_quenched)

    def test_is_quenched_false(self):
        self.cavity._quench_latch_pv_obj = make_mock_pv(get_val=0)
        self.assertFalse(self.cavity.is_quenched)

    def test_wait(self):
        self.cavity.check_abort = MagicMock()
        self.cavity.wait(1)
        self.cavity.check_abort.assert_called()
        mock_sleep.assert_called()

    def test_wait_for_quench(self):
        self.skipTest("Not yet implemented")

    def test_check_abort(self):
        self.cavity.decarad = MagicMock()
        self.cavity.decarad.max_avg_dose = randint(0, 100)
        if self.cavity.decarad.max_avg_dose > 50:
            self.assertRaises(QuenchError, self.cavity.check_abort)
        else:
            self.cavity.check_abort()

    def test_quench_process(self):
        # TODO test actual processing
        amp = randint(5, 21)
        self.cavity.turn_off = MagicMock()
        self.cavity._ades_pv_obj = make_mock_pv(get_val=amp)
        self.cavity.set_sela_mode = MagicMock()
        self.cavity.turn_on = MagicMock()
        self.cavity._ades_max_pv_obj = make_mock_pv(get_val=amp)

        self.cavity.quench_process(start_amp=amp, end_amp=amp)
        self.cavity.turn_off.assert_called()
        self.cavity._ades_pv_obj.put.assert_called_with(amp)
        self.cavity.set_sela_mode.assert_called()
        self.cavity.turn_on.assert_called()
        self.cavity._ades_max_pv_obj.get.assert_called()
        self.cavity._ades_pv_obj.get.assert_called()

    def test_validate_quench_false(self):
        time_data = linspace(-500e-3, 500e-3, num=500)
        amp_data = []
        for t in time_data:
            amp_data.append(16.6e6 * exp((-pi * self.cavity.frequency * t) / 4.5e7))

        self.cavity._fault_time_waveform_pv_obj = make_mock_pv(get_val=time_data)
        self.cavity._fault_waveform_pv_obj = make_mock_pv(get_val=amp_data)
        self.cavity._current_q_loaded_pv_obj = make_mock_pv(get_val=4.5e7)
        self.cavity.cryomodule.logger = MagicMock()

        self.assertFalse(self.cavity.validate_quench())

    def test_validate_quench_true(self):
        time_data = linspace(-500e-3, 500e-3, num=500)
        amp_data = []
        for t in time_data:
            amp_data.append(
                16.6e6
                * exp(
                    (-pi * self.cavity.frequency * t)
                    / (LOADED_Q_CHANGE_FOR_QUENCH * 0.5 * 4.5e7)
                )
            )

        self.cavity._fault_time_waveform_pv_obj = make_mock_pv(get_val=time_data)
        self.cavity._fault_waveform_pv_obj = make_mock_pv(get_val=amp_data)
        self.cavity._current_q_loaded_pv_obj = make_mock_pv(get_val=4.5e7)
        self.cavity.cryomodule.logger = MagicMock()

        self.assertTrue(self.cavity.validate_quench())
