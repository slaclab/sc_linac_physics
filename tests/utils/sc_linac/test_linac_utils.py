from random import randint

from sc_linac_physics.utils.sc_linac.linac_utils import stepper_tol_factor


def test_stepper_tol_factor_low():
    assert stepper_tol_factor(randint(-10000, 0)) == 5


def test_stepper_tol_factor_high():
    assert stepper_tol_factor(randint(int(50e6) + 1, int(50e6 * 2))) == 1.01


def test_stepper_tol_factor():
    assert 1.01 <= stepper_tol_factor(randint(10000, int(50e6))) <= 5
