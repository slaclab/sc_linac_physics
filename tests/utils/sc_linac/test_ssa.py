from random import randint, uniform
from unittest import TestCase
from unittest.mock import MagicMock

from lcls_tools.common.controls.pyepics.utils import make_mock_pv

from utils.sc_linac.linac import MACHINE
from utils.sc_linac.linac_utils import (
    SSA_STATUS_ON_VALUE,
    SSA_STATUS_RESETTING_FAULTS_VALUE,
    SSA_STATUS_FAULTED_VALUE,
    SSA_STATUS_FAULT_RESET_FAILED_VALUE,
    SSACalibrationError,
    SSAFaultError,
    SSA_CALIBRATION_RUNNING_VALUE,
    SSA_CALIBRATION_CRASHED_VALUE,
    SSA_RESULT_GOOD_STATUS_VALUE,
    SSA_SLOPE_LOWER_LIMIT,
    SSA_SLOPE_UPPER_LIMIT,
    SSACalibrationToleranceError,
)
from utils.sc_linac.ssa import SSA


class TestSSA(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.non_hl_iterator = MACHINE.non_hl_iterator
        cls.hl_iterator = MACHINE.hl_iterator

    def setUp(self):
        self.ssa: SSA = next(self.non_hl_iterator).ssa
        print(f"Testing {self.ssa}")

    def test_pv_prefix(self):
        ssa = MACHINE.cryomodules["01"].cavities[1].ssa
        self.assertEqual(ssa.pv_prefix, "ACCL:L0B:0110:SSA:")

    def test_pv_addr(self):
        ssa = MACHINE.cryomodules["01"].cavities[1].ssa
        suffix = "test"
        self.assertEqual(ssa.pv_addr(suffix), f"ACCL:L0B:0110:SSA:{suffix}")

    def test_status_message(self):
        self.ssa._status_pv_obj = make_mock_pv(get_val=SSA_STATUS_ON_VALUE)
        self.assertEqual(self.ssa.status_message, SSA_STATUS_ON_VALUE)

    def test_is_on(self):
        status = randint(0, 11)
        self.ssa._status_pv_obj = make_mock_pv(get_val=status)
        if status == SSA_STATUS_ON_VALUE:
            self.assertTrue(self.ssa.is_on)
        else:
            self.assertFalse(self.ssa.is_on)

    def test_is_resetting(self):
        status = randint(0, 11)
        self.ssa._status_pv_obj = make_mock_pv(get_val=status)
        if status == SSA_STATUS_RESETTING_FAULTS_VALUE:
            self.assertTrue(self.ssa.is_resetting)
        else:
            self.assertFalse(self.ssa.is_resetting)

    def test_is_faulted(self):
        status = randint(0, 11)
        self.ssa._status_pv_obj = make_mock_pv(get_val=status)
        if status in [
            SSA_STATUS_FAULTED_VALUE,
            SSA_STATUS_FAULT_RESET_FAILED_VALUE,
        ]:
            self.assertTrue(self.ssa.is_faulted)
        else:
            self.assertFalse(self.ssa.is_faulted)

    def test_max_fwd_pwr(self):
        pwr = randint(2000, 4000)
        self.ssa._max_fwd_pwr_pv_obj = make_mock_pv(get_val=pwr)
        self.assertEqual(self.ssa.max_fwd_pwr, pwr)

    def test_drive_max_saved(self):
        drive = uniform(0.5, 1)
        self.ssa._saved_drive_max_pv_obj = make_mock_pv(get_val=drive)
        self.assertEqual(self.ssa.drive_max, drive)

    def test_drive_max_not_saved(self):
        self.ssa._saved_drive_max_pv_obj = make_mock_pv(get_val=None)
        self.assertEqual(self.ssa.drive_max, 0.8)

    def test_drive_max_not_saved_hl(self):
        ssa_hl = next(self.hl_iterator).ssa
        ssa_hl._saved_drive_max_pv_obj = make_mock_pv(get_val=None)
        self.assertEqual(ssa_hl.drive_max, 1)

    def test_calibrate_low_drive(self):
        self.assertRaises(SSACalibrationError, self.ssa.calibrate, uniform(0, 0.3))

    def test_calibrate(self):
        self.ssa.run_calibration = MagicMock()
        self.ssa._drive_max_setpoint_pv_obj = make_mock_pv()
        drive = uniform(0.5, 1)
        self.ssa.calibrate(drive)
        self.ssa._drive_max_setpoint_pv_obj.put.assert_called_with(drive)
        self.ssa.run_calibration.assert_called()

    def test_ps_volt_setpoint2_pv_obj(self):
        self.ssa._ps_volt_setpoint2_pv_obj = make_mock_pv()
        self.assertEqual(
            self.ssa.ps_volt_setpoint2_pv_obj, self.ssa._ps_volt_setpoint2_pv_obj
        )

    def test_ps_volt_setpoint1_pv_obj(self):
        self.ssa._ps_volt_setpoint1_pv_obj = make_mock_pv()
        self.assertEqual(
            self.ssa.ps_volt_setpoint1_pv_obj, self.ssa._ps_volt_setpoint1_pv_obj
        )

    def test_turn_on_pv_obj(self):
        self.ssa._turn_on_pv_obj = make_mock_pv()
        self.assertEqual(self.ssa.turn_on_pv_obj, self.ssa._turn_on_pv_obj)

    def test_turn_off_pv_obj(self):
        self.ssa._turn_off_pv_obj = make_mock_pv()
        self.assertEqual(self.ssa.turn_off_pv_obj, self.ssa._turn_off_pv_obj)

    def test_reset_pv_obj(self):
        self.ssa._reset_pv_obj = make_mock_pv()
        self.assertEqual(self.ssa.reset_pv_obj, self.ssa._reset_pv_obj)

    def test_reset(self):
        self.ssa._status_pv_obj = make_mock_pv(get_val=SSA_STATUS_FAULTED_VALUE)
        self.ssa._reset_pv_obj = make_mock_pv()
        self.assertRaises(SSAFaultError, self.ssa.reset)
        self.ssa._reset_pv_obj.put.assert_called_with(1)

    def test_start_calibration(self):
        self.ssa._calibration_start_pv_obj = make_mock_pv()
        self.ssa.start_calibration()
        self.ssa._calibration_start_pv_obj.put.assert_called_with(1)

    def test_calibration_status(self):
        status = randint(0, 2)
        self.ssa._calibration_status_pv_obj = make_mock_pv(get_val=status)
        self.assertEqual(self.ssa.calibration_status, status)

    def test_calibration_running(self):
        status = randint(0, 2)
        self.ssa._calibration_status_pv_obj = make_mock_pv(get_val=status)
        if status == SSA_CALIBRATION_RUNNING_VALUE:
            self.assertTrue(self.ssa.calibration_running)
        else:
            self.assertFalse(self.ssa.calibration_running)

    def test_calibration_crashed(self):
        status = randint(0, 2)
        self.ssa._calibration_status_pv_obj = make_mock_pv(get_val=status)
        if status == SSA_CALIBRATION_CRASHED_VALUE:
            self.assertTrue(self.ssa.calibration_crashed)
        else:
            self.assertFalse(self.ssa.calibration_crashed)

    def test_cal_result_status_pv_obj(self):
        self.ssa._cal_result_status_pv_obj = make_mock_pv()
        self.assertEqual(
            self.ssa.cal_result_status_pv_obj, self.ssa._cal_result_status_pv_obj
        )

    def test_calibration_result_good(self):
        status = randint(0, 2)
        self.ssa._cal_result_status_pv_obj = make_mock_pv(get_val=status)
        if status == SSA_RESULT_GOOD_STATUS_VALUE:
            self.assertTrue(self.ssa.calibration_result_good)
        else:
            self.assertFalse(self.ssa.calibration_result_good)

    def test_run_calibration(self):
        self.ssa.reset = MagicMock()
        self.ssa.turn_on = MagicMock()
        self.ssa.cavity.reset_interlocks = MagicMock()
        self.ssa.start_calibration = MagicMock()
        self.ssa._calibration_status_pv_obj = make_mock_pv(get_val=1)

        self.ssa._cal_result_status_pv_obj = make_mock_pv(
            get_val=SSA_RESULT_GOOD_STATUS_VALUE
        )
        self.ssa._max_fwd_pwr_pv_obj = make_mock_pv(
            get_val=self.ssa.fwd_power_lower_limit * 2
        )
        self.ssa._measured_slope_pv_obj = make_mock_pv(
            get_val=uniform(SSA_SLOPE_LOWER_LIMIT, SSA_SLOPE_UPPER_LIMIT)
        )
        self.ssa.cavity.push_ssa_slope = MagicMock()

        self.ssa.run_calibration()

        self.ssa.reset.assert_called()
        self.ssa.turn_on.assert_called()
        self.ssa.cavity.reset_interlocks.assert_called()
        self.ssa.start_calibration.assert_called()
        self.ssa.cavity.push_ssa_slope.assert_called()

    def test_run_calibration_crashed(self):
        self.ssa.reset = MagicMock()
        self.ssa.turn_on = MagicMock()
        self.ssa.cavity.reset_interlocks = MagicMock()
        self.ssa.start_calibration = MagicMock()
        self.ssa._calibration_status_pv_obj = make_mock_pv(
            get_val=SSA_CALIBRATION_CRASHED_VALUE
        )
        self.assertRaises(SSACalibrationError, self.ssa.run_calibration)

    def test_run_calibration_bad_result(self):
        self.ssa.reset = MagicMock()
        self.ssa.turn_on = MagicMock()
        self.ssa.cavity.reset_interlocks = MagicMock()
        self.ssa.start_calibration = MagicMock()
        self.ssa._calibration_status_pv_obj = make_mock_pv(get_val=1)
        self.ssa._cal_result_status_pv_obj = make_mock_pv(get_val=1)
        self.assertRaises(SSACalibrationError, self.ssa.run_calibration)

    def test_run_calibration_low_fwd_pwr(self):
        self.ssa.reset = MagicMock()
        self.ssa.turn_on = MagicMock()
        self.ssa.cavity.reset_interlocks = MagicMock()
        self.ssa.start_calibration = MagicMock()
        self.ssa._calibration_status_pv_obj = make_mock_pv(get_val=1)
        self.ssa._cal_result_status_pv_obj = make_mock_pv(
            get_val=SSA_RESULT_GOOD_STATUS_VALUE
        )
        self.ssa._max_fwd_pwr_pv_obj = make_mock_pv(
            get_val=self.ssa.fwd_power_lower_limit / 2
        )
        self.assertRaises(SSACalibrationToleranceError, self.ssa.run_calibration)

    def test_run_calibration_bad_slope(self):
        self.ssa.reset = MagicMock()
        self.ssa.turn_on = MagicMock()
        self.ssa.cavity.reset_interlocks = MagicMock()
        self.ssa.start_calibration = MagicMock()
        self.ssa._calibration_status_pv_obj = make_mock_pv(get_val=1)
        self.ssa._cal_result_status_pv_obj = make_mock_pv(
            get_val=SSA_RESULT_GOOD_STATUS_VALUE
        )
        self.ssa._max_fwd_pwr_pv_obj = make_mock_pv(
            get_val=self.ssa.fwd_power_lower_limit * 2
        )
        self.ssa._measured_slope_pv_obj = make_mock_pv(
            get_val=SSA_SLOPE_LOWER_LIMIT / 2
        )
        self.assertRaises(SSACalibrationToleranceError, self.ssa.run_calibration)

    def test_measured_slope(self):
        slope = uniform(SSA_SLOPE_LOWER_LIMIT, SSA_SLOPE_UPPER_LIMIT)
        self.ssa._measured_slope_pv_obj = make_mock_pv(get_val=slope)
        self.assertEqual(self.ssa.measured_slope, slope)

    def test_measured_slope_in_tolerance(self):
        slope = uniform(SSA_SLOPE_LOWER_LIMIT, SSA_SLOPE_UPPER_LIMIT)
        self.ssa._measured_slope_pv_obj = make_mock_pv(get_val=slope)
        self.assertTrue(self.ssa.measured_slope_in_tolerance)

    def test_measured_slope_low(self):
        slope = SSA_SLOPE_LOWER_LIMIT / 2
        self.ssa._measured_slope_pv_obj = make_mock_pv(get_val=slope)
        self.assertFalse(self.ssa.measured_slope_in_tolerance)

    def test_measured_slope_high(self):
        slope = SSA_SLOPE_UPPER_LIMIT * 2
        self.ssa._measured_slope_pv_obj = make_mock_pv(get_val=slope)
        self.assertFalse(self.ssa.measured_slope_in_tolerance)
