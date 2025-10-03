from random import randint, choice
from unittest.mock import MagicMock

import pytest
from lcls_tools.common.controls.pyepics.utils import make_mock_pv

from sc_linac_physics.utils.sc_linac.linac_utils import (
    HW_MODE_ONLINE_VALUE,
    RF_MODE_SELAP,
    HW_MODE_MAINTENANCE_VALUE,
    HW_MODE_OFFLINE_VALUE,
    HW_MODE_MAIN_DONE_VALUE,
    HW_MODE_READY_VALUE,
    RF_MODE_SELA,
    RF_MODE_SEL,
    RF_MODE_SEL_RAW,
    RF_MODE_PULSE,
    RF_MODE_CHIRP,
)
from tests.mock_utils import mock_func


@pytest.fixture
def cavity(monkeypatch):
    monkeypatch.setenv("SC_LINAC_DISABLE_FILE_LOGS", "1")
    # Ensure no real files/dirs/loggers are created
    monkeypatch.setattr("os.makedirs", mock_func)
    monkeypatch.setattr("lcls_tools.common.logger.logger.custom_logger", mock_func)
    monkeypatch.setattr("logging.FileHandler", mock_func)

    # Import after patching, so the module sees the patched handlers
    from sc_linac_physics.applications.sel_phase_optimizer.sel_phase_linac import SELCavity

    yield SELCavity(randint(1, 8), rack_object=MagicMock())


def test_sel_poff_pv_obj(cavity):
    cavity._sel_poff_pv_obj = make_mock_pv()
    assert cavity.sel_poff_pv_obj == cavity._sel_poff_pv_obj


def test_fit_chisquare_pv_obj(cavity):
    cavity._fit_chisqaure_pv_obj = make_mock_pv()
    assert cavity.fit_chisquare_pv_obj == cavity._fit_chisquare_pv_obj


def test_fit_slope_pv_obj(cavity):
    cavity._fit_slope_pv_obj = make_mock_pv()
    assert cavity.fit_slope_pv_obj == cavity._fit_slope_pv_obj


def test_fit_intercept_pv_obj(cavity):
    cavity._fit_intercept_pv_obj = make_mock_pv()
    assert cavity.fit_intercept_pv_obj == cavity._fit_intercept_pv_obj


def test_sel_phase_offset(cavity):
    offset = randint(0, 100)
    cavity._sel_poff_pv_obj = make_mock_pv(get_val=offset)
    assert cavity.sel_phase_offset == offset


def test_i_waveform(cavity):
    wf = [i for i in range(randint(1, 100))]
    cavity._i_waveform_pv = make_mock_pv(get_val=wf)
    assert cavity.i_waveform == wf


def test_q_waveform(cavity):
    wf = [i for i in range(randint(1, 100))]
    cavity._q_waveform_pv = make_mock_pv(get_val=wf)
    assert cavity.q_waveform == wf


def test_can_be_straightened(cavity):
    cavity._hw_mode_pv_obj = make_mock_pv(get_val=HW_MODE_ONLINE_VALUE)
    cavity._rf_state_pv_obj = make_mock_pv(get_val=1)
    cavity._rf_mode_pv_obj = make_mock_pv(get_val=RF_MODE_SELAP)
    cavity._aact_pv_obj = make_mock_pv(get_val=randint(5, 21))
    cavity._fit_chisquare_pv_obj = make_mock_pv()
    cavity._fit_slope_pv_obj = make_mock_pv()
    cavity._fit_intercept_pv_obj = make_mock_pv()
    assert cavity.can_be_straightened()


def test_cannot_be_straightened_hw_mode(cavity):
    cavity._hw_mode_pv_obj = make_mock_pv(
        get_val=choice(
            [
                HW_MODE_MAINTENANCE_VALUE,
                HW_MODE_OFFLINE_VALUE,
                HW_MODE_MAIN_DONE_VALUE,
                HW_MODE_READY_VALUE,
            ]
        )
    )
    cavity._rf_state_pv_obj = make_mock_pv(get_val=1)
    cavity._rf_mode_pv_obj = make_mock_pv(get_val=RF_MODE_SELAP)
    cavity._aact_pv_obj = make_mock_pv(get_val=randint(5, 21))
    assert not cavity.can_be_straightened()


def test_cannot_be_straightened_rf_state(cavity):
    cavity._hw_mode_pv_obj = make_mock_pv(get_val=HW_MODE_ONLINE_VALUE)
    cavity._rf_state_pv_obj = make_mock_pv(get_val=0)
    cavity._rf_mode_pv_obj = make_mock_pv(get_val=RF_MODE_SELAP)
    cavity._aact_pv_obj = make_mock_pv(get_val=randint(5, 21))
    assert not cavity.can_be_straightened()


def test_cannot_be_straightened_rf_mode(cavity):
    cavity._hw_mode_pv_obj = make_mock_pv(get_val=HW_MODE_ONLINE_VALUE)
    cavity._rf_state_pv_obj = make_mock_pv(get_val=1)
    cavity._rf_mode_pv_obj = make_mock_pv(
        get_val=choice([RF_MODE_SELA, RF_MODE_SEL, RF_MODE_SEL_RAW, RF_MODE_PULSE, RF_MODE_CHIRP])
    )
    cavity._aact_pv_obj = make_mock_pv(get_val=randint(5, 21))
    assert not cavity.can_be_straightened()


def test_cannot_be_straightened_aact(cavity):
    cavity._hw_mode_pv_obj = make_mock_pv(get_val=HW_MODE_ONLINE_VALUE)
    cavity._rf_state_pv_obj = make_mock_pv(get_val=1)
    cavity._rf_mode_pv_obj = make_mock_pv(get_val=RF_MODE_SELAP)
    cavity._aact_pv_obj = make_mock_pv(get_val=1)
    assert not cavity.can_be_straightened()


def test_should_not_straighten_iq_plot(cavity):
    cavity.can_be_straightened = MagicMock(return_value=False)
    assert cavity.straighten_iq_plot() == 0


def test_straighten_iq_plot(cavity):
    cavity.can_be_straightened = MagicMock(return_value=True)
    wf = [i for i in range(1, randint(2, 100))]
    cavity._i_waveform_pv = make_mock_pv(get_val=wf)
    cavity._q_waveform_pv = make_mock_pv(get_val=wf)
    cavity._sel_poff_pv_obj = make_mock_pv(get_val=randint(0, 360))
    cavity._fit_chisquare_pv_obj = make_mock_pv()
    cavity._fit_slope_pv_obj = make_mock_pv()
    cavity._fit_intercept_pv_obj = make_mock_pv()
    assert cavity.straighten_iq_plot() != 0
