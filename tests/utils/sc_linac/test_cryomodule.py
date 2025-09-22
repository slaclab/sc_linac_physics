from random import randint, choice
from unittest.mock import MagicMock

import pytest

from sc_linac_physics.utils import Cryomodule
from sc_linac_physics.utils.sc_linac.linac_utils import ALL_CRYOMODULES, L1BHL
from sc_linac_physics.utils.sc_linac.rack import Rack


@pytest.fixture
def cryomodule():
    linac = MagicMock()
    linac.name = f"L{randint(0, 3)}B"
    linac.rack_class = Rack
    yield Cryomodule(cryo_name=choice(ALL_CRYOMODULES), linac_object=linac)


def test_is_harmonic_linearizer_true(cryomodule):
    if cryomodule.name in L1BHL:
        assert cryomodule.is_harmonic_linearizer
    else:
        assert not cryomodule.is_harmonic_linearizer


def test_pv_prefix(cryomodule):
    assert cryomodule.pv_prefix == f"ACCL:{cryomodule.linac.name}:{cryomodule.name}00:"


def test_num_cavities(cryomodule):
    assert len(cryomodule.cavities.keys()) == 8
