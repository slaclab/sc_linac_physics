from random import randint, choice
from unittest.mock import MagicMock

import pytest
from sc_linac_physics.utils.epics import make_mock_pv

from sc_linac_physics.utils.sc_linac.cryomodule import Cryomodule
from sc_linac_physics.utils.sc_linac.linac_utils import (
    MAGNET_TRIM_VALUE,
    MAGNET_RESET_VALUE,
    MAGNET_ON_VALUE,
    MAGNET_OFF_VALUE,
    MAGNET_DEGAUSS_VALUE,
    ALL_CRYOMODULES_NO_HL,
    L1BHL,
)
from sc_linac_physics.utils.sc_linac.magnet import Magnet


@pytest.fixture
def cryomodule():
    linac = MagicMock()
    linac.magnet_class = Magnet
    linac.name = f"L{randint(0, 3)}B"
    yield Cryomodule(
        cryo_name=choice(ALL_CRYOMODULES_NO_HL), linac_object=linac
    )


@pytest.fixture
def hl():
    linac = MagicMock()
    linac.magnet_class = Magnet
    linac.name = "L1B"
    yield Cryomodule(cryo_name=choice(L1BHL), linac_object=linac)


def test_pv_prefix_quad(cryomodule):
    assert (
        cryomodule.quad.pv_prefix
        == f"QUAD:{cryomodule.linac.name}:{cryomodule.name}85:"
    )


def test_pv_prefix_quad_hl(hl):
    with pytest.raises(AttributeError):
        print(hl.quad)


def test_pv_prefix_xcor_hl(hl):
    with pytest.raises(AttributeError):
        print(hl.xcor)


def test_pv_prefix_ycor_hl(hl):
    with pytest.raises(AttributeError):
        print(hl.ycor)


def test_pv_prefix_xcor(cryomodule):
    assert (
        cryomodule.xcor.pv_prefix
        == f"XCOR:{cryomodule.linac.name}:{cryomodule.name}85:"
    )


def test_pv_prefix_ycor(cryomodule):
    assert (
        cryomodule.ycor.pv_prefix
        == f"YCOR:{cryomodule.linac.name}:{cryomodule.name}85:"
    )


def test_bdes(cryomodule):
    magnet = choice([cryomodule.quad, cryomodule.xcor, cryomodule.ycor])
    val = randint(-10, 10)
    magnet._bdes_pv_obj = make_mock_pv(get_val=val)
    assert magnet.bdes == val


def test_bdes_setter(cryomodule):
    magnet = choice([cryomodule.quad, cryomodule.xcor, cryomodule.ycor])
    val = randint(-10, 10)
    magnet._bdes_pv_obj = make_mock_pv()
    magnet._control_pv_obj = make_mock_pv()
    magnet.bdes = val
    magnet._bdes_pv_obj.put.assert_called_with(val)
    magnet._control_pv_obj.put.assert_called_with(MAGNET_TRIM_VALUE)


def test_reset(cryomodule):
    magnet = choice([cryomodule.quad, cryomodule.xcor, cryomodule.ycor])
    magnet._control_pv_obj = make_mock_pv()
    magnet.reset()
    magnet._control_pv_obj.put.assert_called_with(MAGNET_RESET_VALUE)


def test_turn_on(cryomodule):
    magnet = choice([cryomodule.quad, cryomodule.xcor, cryomodule.ycor])
    magnet._control_pv_obj = make_mock_pv()
    magnet.turn_on()
    magnet._control_pv_obj.put.assert_called_with(MAGNET_ON_VALUE)


def test_turn_off(cryomodule):
    magnet = choice([cryomodule.quad, cryomodule.xcor, cryomodule.ycor])
    magnet._control_pv_obj = make_mock_pv()
    magnet.turn_off()
    magnet._control_pv_obj.put.assert_called_with(MAGNET_OFF_VALUE)


def test_degauss(cryomodule):
    magnet = choice([cryomodule.quad, cryomodule.xcor, cryomodule.ycor])
    magnet._control_pv_obj = make_mock_pv()
    magnet.degauss()
    magnet._control_pv_obj.put.assert_called_with(MAGNET_DEGAUSS_VALUE)


def test_trim(cryomodule):
    magnet = choice([cryomodule.quad, cryomodule.xcor, cryomodule.ycor])
    magnet._control_pv_obj = make_mock_pv()
    magnet.trim()
    magnet._control_pv_obj.put.assert_called_with(MAGNET_TRIM_VALUE)


# The real CTRL enum states, the same on QUAD, XCOR and YCOR across L0B to
# L4B (caget on lcls-srv01, 2026-10-13). L4B QUADs label state 9 CALIB.
# Written out here, not derived from linac_utils, so a wrong constant
# can't pass by agreeing with itself.
CTRL_STATES = [
    "Ready",
    "TRIM",
    "PERTURB",
    "BCON_TO_BDES",
    "BACT_TO_BDES",
    "SAVE_BDES",
    "LOAD_BDES",
    "UNDO_BDES",
    "DAC_ZERO",
    "CALB",
    "STDZ",
    "RESET",
    "TURN_ON",
    "TURN_OFF",
    "DEGAUSS",
]


@pytest.mark.parametrize(
    "method, state",
    [
        ("trim", "TRIM"),
        ("reset", "RESET"),
        ("turn_on", "TURN_ON"),
        ("turn_off", "TURN_OFF"),
        ("degauss", "DEGAUSS"),
    ],
)
def test_ctrl_writes_the_matching_enum_state(cryomodule, method, state):
    magnet = cryomodule.quad
    magnet._control_pv_obj = make_mock_pv()
    getattr(magnet, method)()
    (written,), _ = magnet._control_pv_obj.put.call_args
    assert CTRL_STATES[written] == state
