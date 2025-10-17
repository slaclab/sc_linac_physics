from random import randint, uniform, choice
from unittest.mock import MagicMock

import pytest
from lcls_tools.common.controls.pyepics.utils import make_mock_pv

from sc_linac_physics.utils.sc_linac.cavity import Cavity
from sc_linac_physics.utils.sc_linac.linac_utils import (
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
    ALL_CRYOMODULES,
    CavityAbortError,
)
from sc_linac_physics.utils.sc_linac.ssa import SSA
from tests.mock_utils import mock_func


@pytest.fixture
def ssa(monkeypatch):
    monkeypatch.setattr("time.sleep", mock_func)
    rack = MagicMock()
    rack.cryomodule.name = choice(ALL_CRYOMODULES)
    rack.cryomodule.linac.name = f"L{randint(0, 3)}B"
    cavity = Cavity(cavity_num=randint(1, 8), rack_object=rack)
    yield SSA(cavity=cavity)


def test_pv_prefix(ssa):
    assert (
        ssa.pv_prefix
        == f"ACCL:{ssa.cavity.linac.name}:{ssa.cavity.cryomodule.name}{ssa.cavity.number}0:SSA:"
    )


def test_pv_addr(ssa):
    suffix = "test"
    assert ssa.pv_addr(suffix) == f"{ssa.pv_prefix}{suffix}"


def test_status_message(ssa):
    ssa._status_pv_obj = make_mock_pv(get_val=SSA_STATUS_ON_VALUE)
    assert ssa.status_message == SSA_STATUS_ON_VALUE


def test_is_on(ssa):
    status = randint(0, 11)
    ssa._status_pv_obj = make_mock_pv(get_val=status)
    if status == SSA_STATUS_ON_VALUE:
        assert ssa.is_on
    else:
        assert not ssa.is_on


def test_is_resetting(ssa):
    status = randint(0, 11)
    ssa._status_pv_obj = make_mock_pv(get_val=status)
    if status == SSA_STATUS_RESETTING_FAULTS_VALUE:
        assert ssa.is_resetting
    else:
        assert not ssa.is_resetting


def test_is_faulted(ssa):
    status = randint(0, 11)
    ssa._status_pv_obj = make_mock_pv(get_val=status)
    if status in [
        SSA_STATUS_FAULTED_VALUE,
        SSA_STATUS_FAULT_RESET_FAILED_VALUE,
    ]:
        assert ssa.is_faulted
    else:
        assert not ssa.is_faulted


def test_max_fwd_pwr(ssa):
    pwr = randint(2000, 4000)
    ssa._max_fwd_pwr_pv_obj = make_mock_pv(get_val=pwr)
    assert ssa.max_fwd_pwr == pwr


def test_drive_max_saved(ssa):
    drive = uniform(0.5, 1)
    ssa._saved_drive_max_pv_obj = make_mock_pv(get_val=drive)
    assert ssa.drive_max == drive


def test_drive_max_not_saved(ssa):
    ssa.cavity.cryomodule.is_harmonic_linearizer = False
    ssa._saved_drive_max_pv_obj = make_mock_pv(get_val=None)
    assert ssa.drive_max == 0.8


def test_drive_max_not_saved_hl(ssa):
    ssa.cavity.cryomodule.is_harmonic_linearizer = True
    ssa._saved_drive_max_pv_obj = make_mock_pv(get_val=None)
    assert ssa.drive_max == 1


def test_calibrate_low_drive(ssa):
    with pytest.raises(SSACalibrationError):
        ssa.calibrate(uniform(0, 0.3))


def test_calibrate(ssa):
    ssa.run_calibration = MagicMock()
    ssa._drive_max_setpoint_pv_obj = make_mock_pv()
    drive = uniform(0.5, 1)
    ssa.calibrate(drive)
    ssa._drive_max_setpoint_pv_obj.put.assert_called_with(drive)
    ssa.run_calibration.assert_called()


def test_ps_volt_setpoint2_pv_obj(ssa):
    ssa._ps_volt_setpoint2_pv_obj = make_mock_pv()
    assert ssa.ps_volt_setpoint2_pv_obj == ssa._ps_volt_setpoint2_pv_obj


def test_ps_volt_setpoint1_pv_obj(ssa):
    ssa._ps_volt_setpoint1_pv_obj = make_mock_pv()
    assert ssa.ps_volt_setpoint1_pv_obj == ssa._ps_volt_setpoint1_pv_obj


def test_turn_on_pv_obj(ssa):
    ssa._turn_on_pv_obj = make_mock_pv()
    assert ssa.turn_on_pv_obj == ssa._turn_on_pv_obj


def test_turn_off_pv_obj(ssa):
    ssa._turn_off_pv_obj = make_mock_pv()
    assert ssa.turn_off_pv_obj == ssa._turn_off_pv_obj


def test_reset_pv_obj(ssa):
    ssa._reset_pv_obj = make_mock_pv()
    assert ssa.reset_pv_obj == ssa._reset_pv_obj


def test_reset(ssa):
    ssa._status_pv_obj = make_mock_pv(get_val=SSA_STATUS_FAULTED_VALUE)
    ssa._reset_pv_obj = make_mock_pv()
    ssa.cavity.check_abort = MagicMock()
    ssa.wait_while_resetting = MagicMock()
    with pytest.raises(SSAFaultError):
        ssa.reset()
    ssa._reset_pv_obj.put.assert_called_with(1)
    ssa.cavity.check_abort.assert_called()
    ssa.wait_while_resetting.assert_called()


def test_start_calibration(ssa):
    ssa._calibration_start_pv_obj = make_mock_pv()
    ssa.start_calibration()
    ssa._calibration_start_pv_obj.put.assert_called_with(1)


def test_calibration_status(ssa):
    status = randint(0, 2)
    ssa._calibration_status_pv_obj = make_mock_pv(get_val=status)
    assert ssa.calibration_status == status


def test_calibration_running(ssa):
    status = randint(0, 2)
    ssa._calibration_status_pv_obj = make_mock_pv(get_val=status)
    if status == SSA_CALIBRATION_RUNNING_VALUE:
        assert ssa.calibration_running
    else:
        assert not ssa.calibration_running


def test_calibration_crashed(ssa):
    status = randint(0, 2)
    ssa._calibration_status_pv_obj = make_mock_pv(get_val=status)
    if status == SSA_CALIBRATION_CRASHED_VALUE:
        assert ssa.calibration_crashed
    else:
        assert not ssa.calibration_crashed


def test_cal_result_status_pv_obj(ssa):
    ssa._cal_result_status_pv_obj = make_mock_pv()
    assert ssa.cal_result_status_pv_obj == ssa._cal_result_status_pv_obj


def test_calibration_result_good(ssa):
    status = randint(0, 2)
    ssa._cal_result_status_pv_obj = make_mock_pv(get_val=status)
    if status == SSA_RESULT_GOOD_STATUS_VALUE:
        assert ssa.calibration_result_good
    else:
        assert not ssa.calibration_result_good


def test_run_calibration(ssa):
    ssa.reset = MagicMock()
    ssa.turn_on = MagicMock()
    ssa.cavity.reset_interlocks = MagicMock()
    ssa.start_calibration = MagicMock()
    ssa._calibration_status_pv_obj = make_mock_pv(get_val=1)

    ssa._cal_result_status_pv_obj = make_mock_pv(
        get_val=SSA_RESULT_GOOD_STATUS_VALUE
    )
    ssa._max_fwd_pwr_pv_obj = make_mock_pv(
        get_val=ssa.fwd_power_lower_limit * 2
    )
    ssa._measured_slope_pv_obj = make_mock_pv(
        get_val=uniform(SSA_SLOPE_LOWER_LIMIT, SSA_SLOPE_UPPER_LIMIT)
    )
    ssa.cavity.push_ssa_slope = MagicMock()

    ssa.run_calibration()

    ssa.reset.assert_called()
    ssa.turn_on.assert_called()
    ssa.cavity.reset_interlocks.assert_called()
    ssa.start_calibration.assert_called()
    ssa.cavity.push_ssa_slope.assert_called()


def test_run_calibration_crashed(ssa):
    ssa.reset = MagicMock()
    ssa.turn_on = MagicMock()
    ssa.cavity.reset_interlocks = MagicMock()
    ssa.start_calibration = MagicMock()
    ssa._calibration_status_pv_obj = make_mock_pv(
        get_val=SSA_CALIBRATION_CRASHED_VALUE
    )
    with pytest.raises(SSACalibrationError):
        ssa.run_calibration()


def test_run_calibration_bad_result(ssa):
    ssa.reset = MagicMock()
    ssa.turn_on = MagicMock()
    ssa.cavity.reset_interlocks = MagicMock()
    ssa.start_calibration = MagicMock()
    ssa._calibration_status_pv_obj = make_mock_pv(get_val=1)
    ssa._cal_result_status_pv_obj = make_mock_pv(get_val=1)
    with pytest.raises(SSACalibrationError):
        ssa.run_calibration()


def test_run_calibration_low_fwd_pwr(ssa):
    ssa.reset = MagicMock()
    ssa.turn_on = MagicMock()
    ssa.cavity.reset_interlocks = MagicMock()
    ssa.start_calibration = MagicMock()
    ssa._calibration_status_pv_obj = make_mock_pv(get_val=1)
    ssa._cal_result_status_pv_obj = make_mock_pv(
        get_val=SSA_RESULT_GOOD_STATUS_VALUE
    )
    ssa._max_fwd_pwr_pv_obj = make_mock_pv(
        get_val=ssa.fwd_power_lower_limit / 2
    )
    with pytest.raises(SSACalibrationToleranceError):
        ssa.run_calibration()


def test_run_calibration_bad_slope(ssa):
    ssa.reset = MagicMock()
    ssa.turn_on = MagicMock()
    ssa.cavity.reset_interlocks = MagicMock()
    ssa.start_calibration = MagicMock()
    ssa._calibration_status_pv_obj = make_mock_pv(get_val=1)
    ssa._cal_result_status_pv_obj = make_mock_pv(
        get_val=SSA_RESULT_GOOD_STATUS_VALUE
    )
    ssa._max_fwd_pwr_pv_obj = make_mock_pv(
        get_val=ssa.fwd_power_lower_limit * 2
    )
    ssa._measured_slope_pv_obj = make_mock_pv(get_val=SSA_SLOPE_LOWER_LIMIT / 2)
    with pytest.raises(SSACalibrationToleranceError):
        ssa.run_calibration()


def test_measured_slope(ssa):
    slope = uniform(SSA_SLOPE_LOWER_LIMIT, SSA_SLOPE_UPPER_LIMIT)
    ssa._measured_slope_pv_obj = make_mock_pv(get_val=slope)
    assert ssa.measured_slope == slope


def test_measured_slope_in_tolerance(ssa):
    slope = uniform(SSA_SLOPE_LOWER_LIMIT, SSA_SLOPE_UPPER_LIMIT)
    ssa._measured_slope_pv_obj = make_mock_pv(get_val=slope)
    assert ssa.measured_slope_in_tolerance


def test_measured_slope_low(ssa):
    slope = SSA_SLOPE_LOWER_LIMIT / 2
    ssa._measured_slope_pv_obj = make_mock_pv(get_val=slope)
    assert not ssa.measured_slope_in_tolerance


def test_measured_slope_high(ssa):
    slope = SSA_SLOPE_UPPER_LIMIT * 2
    ssa._measured_slope_pv_obj = make_mock_pv(get_val=slope)
    assert not ssa.measured_slope_in_tolerance


def test_wait_while_resetting(ssa):
    ssa.cavity.abort_flag = True
    ssa.cavity.turn_off = MagicMock()
    ssa._status_pv_obj = make_mock_pv(get_val=SSA_STATUS_RESETTING_FAULTS_VALUE)
    with pytest.raises(CavityAbortError):
        ssa.wait_while_resetting()
