from random import randint, choice
from unittest.mock import MagicMock

import pytest
from lcls_tools.common.controls.pyepics.utils import make_mock_pv

from sc_linac_physics.applications.tuning.tune_cavity import TuneCavity
from sc_linac_physics.applications.tuning.tune_stepper import TuneStepper
from sc_linac_physics.utils.sc_linac.linac_utils import (
    TUNE_CONFIG_COLD_VALUE,
    TUNE_CONFIG_PARKED_VALUE,
    TUNE_CONFIG_OTHER_VALUE,
    TUNE_CONFIG_RESONANCE_VALUE,
    HW_MODE_OFFLINE_VALUE,
    HW_MODE_MAIN_DONE_VALUE,
    CavityHWModeError,
    HW_MODE_READY_VALUE,
    HW_MODE_MAINTENANCE_VALUE,
    HW_MODE_ONLINE_VALUE,
)
from sc_linac_physics.utils.sc_linac.ssa import SSA


@pytest.fixture
def cavity():
    cavity = TuneCavity(cavity_num=randint(1, 8), rack_object=MagicMock())
    cavity.ssa = SSA(cavity)
    cavity.stepper_tuner = TuneStepper(cavity)
    cavity.stepper_tuner.reset_signed_steps = MagicMock()
    cavity.turn_off = MagicMock()
    cavity.ssa.turn_off = MagicMock()
    yield cavity


def test_hw_mode_str(cavity):
    cavity._hw_mode_pv_obj = make_mock_pv()
    cavity.hw_mode_str
    cavity._hw_mode_pv_obj.get.assert_called_with(as_string=True)


def test_df_cold_pv_obj(cavity):
    cavity._df_cold_pv_obj = make_mock_pv()
    assert cavity.df_cold_pv_obj == cavity._df_cold_pv_obj


@pytest.mark.skip(reason="This function is not currently being used")
def test_park(cavity):
    assert False


def test_move_to_cold_landing_already_cold(cavity):
    cavity._tune_config_pv_obj = make_mock_pv(get_val=TUNE_CONFIG_COLD_VALUE)
    cavity.detune_with_rf = MagicMock()
    cavity.detune_no_rf = MagicMock()

    cavity.move_to_cold_landing()

    cavity._tune_config_pv_obj.get.assert_called()
    cavity.turn_off.assert_called()
    cavity.ssa.turn_off.assert_called()
    cavity.detune_with_rf.assert_not_called()
    cavity.detune_no_rf.assert_not_called()
    cavity._tune_config_pv_obj.put.assert_not_called()


def test_move_to_cold_landing_freq(cavity):
    cavity._tune_config_pv_obj = make_mock_pv(
        get_val=choice(
            [
                TUNE_CONFIG_RESONANCE_VALUE,
                TUNE_CONFIG_PARKED_VALUE,
                TUNE_CONFIG_OTHER_VALUE,
            ]
        )
    )
    cavity.detune_with_rf = MagicMock()
    cavity.detune_no_rf = MagicMock()

    cavity.move_to_cold_landing(use_rf=True)

    cavity._tune_config_pv_obj.get.assert_called()
    cavity.turn_off.assert_not_called()
    cavity.ssa.turn_off.assert_not_called()
    cavity.detune_with_rf.assert_called()
    cavity.detune_no_rf.assert_not_called()
    cavity._tune_config_pv_obj.put.assert_called_with(TUNE_CONFIG_COLD_VALUE)


def test_move_to_cold_landing_steps(cavity):
    cavity._tune_config_pv_obj = make_mock_pv(
        get_val=choice(
            [
                TUNE_CONFIG_RESONANCE_VALUE,
                TUNE_CONFIG_PARKED_VALUE,
                TUNE_CONFIG_OTHER_VALUE,
            ]
        )
    )
    cavity.detune_with_rf = MagicMock()
    cavity.detune_no_rf = MagicMock()

    cavity.move_to_cold_landing(use_rf=False)

    cavity._tune_config_pv_obj.get.assert_called()
    cavity.turn_off.assert_not_called()
    cavity.ssa.turn_off.assert_not_called()
    cavity.detune_with_rf.assert_not_called()
    cavity.detune_no_rf.assert_called()
    cavity._tune_config_pv_obj.put.assert_called_with(TUNE_CONFIG_COLD_VALUE)


def test_detune_no_rf_error(cavity):
    cavity._hw_mode_pv_obj = make_mock_pv(
        get_val=choice([HW_MODE_OFFLINE_VALUE, HW_MODE_MAIN_DONE_VALUE])
    )
    with pytest.raises(CavityHWModeError):
        cavity.detune_no_rf()


def test_detune_no_rf(cavity):
    cavity._hw_mode_pv_obj = make_mock_pv(
        get_val=choice(
            [HW_MODE_ONLINE_VALUE, HW_MODE_MAINTENANCE_VALUE, HW_MODE_READY_VALUE]
        )
    )
    cavity.check_resonance = MagicMock()
    cavity.stepper_tuner.move_to_cold_landing = MagicMock()

    cavity.detune_no_rf()
    cavity.check_resonance.assert_called()
    cavity.stepper_tuner.move_to_cold_landing.assert_called()


def test_detune_with_rf_error(cavity):
    cavity._hw_mode_pv_obj = make_mock_pv(
        get_val=choice(
            [HW_MODE_OFFLINE_VALUE, HW_MODE_MAIN_DONE_VALUE, HW_MODE_READY_VALUE]
        )
    )
    cavity.setup_tuning = MagicMock()
    cavity.stepper_tuner.move_to_cold_landing = MagicMock()

    with pytest.raises(CavityHWModeError):
        cavity.detune_with_rf()

    cavity.setup_tuning.assert_not_called()
    cavity.turn_off.assert_not_called()
    cavity.ssa.turn_off.assert_not_called()


def test_detune_with_rf_cold_not_saved(cavity):
    cavity._hw_mode_pv_obj = make_mock_pv(
        get_val=choice([HW_MODE_ONLINE_VALUE, HW_MODE_MAINTENANCE_VALUE])
    )
    cavity.setup_tuning = MagicMock()
    cavity._df_cold_pv_obj = make_mock_pv(get_val=None)
    cavity.detune_by_steps = MagicMock()
    cavity._tune_config_pv_obj = make_mock_pv()

    cavity.detune_with_rf()

    cavity.setup_tuning.assert_not_called()
    cavity.turn_off.assert_called()
    cavity.ssa.turn_off.assert_called()
    cavity.detune_by_steps.assert_called()
    cavity._tune_config_pv_obj.put.assert_called_with(TUNE_CONFIG_COLD_VALUE)


def test_detune_with_rf_cold_saved(cavity):
    cavity._hw_mode_pv_obj = make_mock_pv(
        get_val=choice([HW_MODE_ONLINE_VALUE, HW_MODE_MAINTENANCE_VALUE])
    )
    cavity.setup_tuning = MagicMock()
    cavity._df_cold_pv_obj = make_mock_pv(get_val=randint(50000, 200000))
    cavity.detune_by_steps = MagicMock()
    cavity._tune_config_pv_obj = make_mock_pv()
    cavity._auto_tune = MagicMock()

    cavity.detune_with_rf()

    cavity.setup_tuning.assert_called()
    cavity.turn_off.assert_called()
    cavity.ssa.turn_off.assert_called()
    cavity.detune_by_steps.assert_not_called()
    cavity._tune_config_pv_obj.put.assert_called_with(TUNE_CONFIG_COLD_VALUE)
    cavity._auto_tune.assert_called()


def test_check_resonance(cavity):
    val = choice(
        [
            TUNE_CONFIG_RESONANCE_VALUE,
            TUNE_CONFIG_COLD_VALUE,
            TUNE_CONFIG_PARKED_VALUE,
            TUNE_CONFIG_OTHER_VALUE,
        ]
    )
    cavity._tune_config_pv_obj = make_mock_pv(get_val=val)
    if val != TUNE_CONFIG_RESONANCE_VALUE:
        with pytest.raises(CavityHWModeError):
            cavity.check_resonance()
    else:
        cavity.check_resonance()
