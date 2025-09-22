from random import randint
from unittest.mock import MagicMock

import pytest
from lcls_tools.common.controls.pyepics.utils import make_mock_pv

from sc_linac_physics.applications.tuning.tune_stepper import TuneStepper


@pytest.fixture
def stepper():
    yield TuneStepper(cavity=MagicMock())


def test_steps_cold_landing_pv_obj(stepper):
    stepper._steps_cold_landing_pv_obj = make_mock_pv()
    assert stepper.steps_cold_landing_pv_obj == stepper._steps_cold_landing_pv_obj


@pytest.mark.skip("Not currently using this functionality")
def test_nsteps_park_pv_obj():
    assert False


def test_nsteps_cold_pv_obj(stepper):
    stepper._nsteps_cold_pv_obj = make_mock_pv()
    assert stepper.nsteps_cold_pv_obj == stepper._nsteps_cold_pv_obj


def test_step_signed_pv_obj(stepper):
    stepper._step_signed_pv_obj = make_mock_pv()
    assert stepper.step_signed_pv_obj == stepper._step_signed_pv_obj


def test_move_to_cold_landing(stepper):
    stepper._nsteps_cold_pv_obj = make_mock_pv(get_val=randint(-10000, 500000))
    stepper.move = MagicMock()
    stepper.move_to_cold_landing()
    stepper.move.assert_called()


@pytest.mark.skip("Not currently using this function")
def test_park():
    assert False
