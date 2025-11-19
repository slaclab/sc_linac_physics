from random import choice, randint
from unittest.mock import MagicMock

import pytest
from lcls_tools.common.controls.pyepics.utils import (
    make_mock_pv,
    EPICS_INVALID_VAL,
    EPICS_NO_ALARM_VAL,
    EPICS_MINOR_VAL,
    EPICS_MAJOR_VAL,
)
from numpy import pi, exp, linspace

from sc_linac_physics.applications.quench_processing.quench_cavity import (
    QuenchCavity,
)
from sc_linac_physics.applications.quench_processing.quench_utils import (
    QUENCH_AMP_THRESHOLD,
    LOADED_Q_CHANGE_FOR_QUENCH,
    QUENCH_STABLE_TIME,
    RADIATION_LIMIT,
)
from sc_linac_physics.utils.sc_linac.linac_utils import (
    QuenchError,
    RF_MODE_SELA,
)
from tests.mock_utils import mock_func


@pytest.fixture
def cavity(monkeypatch):
    monkeypatch.setattr("time.sleep", mock_func)
    yield QuenchCavity(randint(1, 8), MagicMock())


def test_current_q_loaded_pv_obj(cavity):
    cavity._current_q_loaded_pv_obj = make_mock_pv()
    assert cavity._current_q_loaded_pv_obj == cavity.current_q_loaded_pv_obj


def test_quench_latch_pv_obj(cavity):
    cavity._quench_latch_pv_obj = make_mock_pv()
    assert cavity._quench_latch_pv_obj == cavity.quench_latch_pv_obj


def test_quench_latch_invalid(cavity):
    severity = choice(
        [
            EPICS_NO_ALARM_VAL,
            EPICS_MINOR_VAL,
            EPICS_MAJOR_VAL,
            EPICS_INVALID_VAL,
        ]
    )
    cavity._quench_latch_pv_obj = make_mock_pv(severity=severity)

    if severity == EPICS_INVALID_VAL:
        assert cavity.quench_latch_invalid
    else:
        assert not (cavity.quench_latch_invalid)


def test_quench_intlk_bypassed_true(cavity):
    cavity._quench_bypass_rbck_pv = make_mock_pv(get_val=1)
    assert cavity.quench_intlk_bypassed


def test_quench_intlk_bypassed_false(cavity):
    cavity._quench_bypass_rbck_pv = make_mock_pv(get_val=0)
    assert not (cavity.quench_intlk_bypassed)


def test_fault_waveform_pv_obj(cavity):
    cavity._fault_waveform_pv_obj = make_mock_pv()
    assert cavity._fault_waveform_pv_obj == cavity.fault_waveform_pv_obj


def test_fault_time_waveform_pv_obj(cavity):
    cavity._fault_time_waveform_pv_obj = make_mock_pv()
    assert (
        cavity._fault_time_waveform_pv_obj == cavity.fault_time_waveform_pv_obj
    )


def test_reset_interlocks(cavity):
    cavity._interlock_reset_pv_obj = make_mock_pv()
    cavity._quench_latch_pv_obj = make_mock_pv()
    cavity.reset_interlocks()
    cavity._interlock_reset_pv_obj.put.assert_called_with(1)


def test_walk_to_quench(cavity):
    # TODO test actual walking
    end_amp = randint(5, 21)
    cavity.reset_interlocks = MagicMock()
    cavity._quench_latch_pv_obj = make_mock_pv(get_val=0)
    cavity._ades_pv_obj = make_mock_pv(get_val=end_amp)
    cavity.check_abort = MagicMock()
    cavity.wait = MagicMock()
    cavity.walk_to_quench(end_amp=end_amp)

    cavity.wait.assert_not_called()
    cavity._ades_pv_obj.put.assert_not_called()


def test_is_quenched_true(cavity):
    cavity._quench_latch_pv_obj = make_mock_pv(get_val=1)
    assert cavity.is_quenched


def test_is_quenched_false(cavity):
    cavity._quench_latch_pv_obj = make_mock_pv(get_val=0)
    assert not (cavity.is_quenched)


def test_wait(cavity):
    cavity.check_abort = MagicMock()
    cavity._quench_latch_pv_obj = make_mock_pv(get_val=1)
    cavity.has_uncaught_quench = MagicMock()
    cavity.wait(1)
    cavity.check_abort.assert_called()


@pytest.mark.skip(reason="Need to mock quenching after a delay")
def test_wait_for_quench(cavity):
    cavity.wait_for_quench()


def test_check_abort_radiation(cavity):
    cavity.decarad = MagicMock()
    cavity.decarad.max_raw_dose = RADIATION_LIMIT + 1

    # Mock PV objects to avoid actual PV access
    cavity._aact_pv_obj = make_mock_pv(get_val=10.0)
    cavity._ades_pv_obj = make_mock_pv(get_val=15.0)

    with pytest.raises(QuenchError):
        cavity.check_abort()


def test_check_abort_quench(cavity):
    cavity.decarad = MagicMock()
    cavity.decarad.max_raw_dose = RADIATION_LIMIT
    cavity.has_uncaught_quench = MagicMock(return_value=True)

    # Mock PV objects to avoid actual PV access
    cavity._aact_pv_obj = make_mock_pv(get_val=10.0)
    cavity._ades_pv_obj = make_mock_pv(get_val=15.0)

    with pytest.raises(QuenchError):
        cavity.check_abort()


def test_has_uncaught_quench(cavity):
    cavity._rf_state_pv_obj = make_mock_pv(get_val=1)
    cavity._rf_mode_pv_obj = make_mock_pv(get_val=RF_MODE_SELA)

    amplitude = 16.6
    cavity._aact_pv_obj = make_mock_pv(get_val=QUENCH_AMP_THRESHOLD * amplitude)
    cavity._ades_pv_obj = make_mock_pv(get_val=amplitude)
    assert cavity.has_uncaught_quench()


def test_quench_process(cavity):
    # TODO test actual processing
    start_amp = randint(5, 15)
    end_amp = randint(15, 21)
    cavity.turn_off = MagicMock()
    cavity._ades_pv_obj = make_mock_pv(get_val=start_amp)
    cavity.set_sela_mode = MagicMock()
    cavity.turn_on = MagicMock()
    cavity._ades_max_pv_obj = make_mock_pv(get_val=start_amp)
    cavity._quench_latch_pv_obj = make_mock_pv()
    cavity.wait_for_quench = MagicMock(return_value=QUENCH_STABLE_TIME * 2)

    cavity.quench_process(start_amp=start_amp, end_amp=end_amp)
    cavity.turn_off.assert_called()
    cavity._ades_pv_obj.put.assert_called_with(min(5.0, start_amp))
    cavity.set_sela_mode.assert_called()
    cavity.turn_on.assert_called()
    cavity._ades_max_pv_obj.get.assert_called()
    cavity._ades_pv_obj.get.assert_called()


def test_validate_quench_false(cavity):
    time_data = linspace(-500e-3, 500e-3, num=500)
    amp_data = []
    for t in time_data:
        amp_data.append(16.6e6 * exp((-pi * cavity.frequency * t) / 4.5e7))

    cavity._fault_time_waveform_pv_obj = make_mock_pv(get_val=time_data)
    cavity._fault_waveform_pv_obj = make_mock_pv(get_val=amp_data)
    cavity._current_q_loaded_pv_obj = make_mock_pv(get_val=4.5e7)

    assert not (cavity.validate_quench())


def test_validate_quench_true(cavity):
    time_data = linspace(-500e-3, 500e-3, num=500)
    amp_data = []
    for t in time_data:
        amp_data.append(
            16.6e6
            * exp(
                (-pi * cavity.frequency * t)
                / (LOADED_Q_CHANGE_FOR_QUENCH * 0.5 * 4.5e7)
            )
        )

    cavity._fault_time_waveform_pv_obj = make_mock_pv(get_val=time_data)
    cavity._fault_waveform_pv_obj = make_mock_pv(get_val=amp_data)
    cavity._current_q_loaded_pv_obj = make_mock_pv(get_val=4.5e7)

    assert cavity.validate_quench()


def test_reset_quench_real(cavity):
    cavity.validate_quench = MagicMock(return_value=True)
    assert not cavity.reset_quench()


def test_reset_quench_fake(cavity):
    cavity.validate_quench = MagicMock(return_value=False)
    cavity.reset_interlocks = MagicMock()
    cavity._interlock_reset_pv_obj = make_mock_pv()
    cavity._rf_permit_pv_obj = make_mock_pv()
    assert cavity.reset_quench()
