from random import randint, choice
from unittest.mock import MagicMock

import pytest

from sc_linac_physics.utils.sc_linac.cryomodule import Cryomodule
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
    assert (
        cryomodule.pv_prefix
        == f"ACCL:{cryomodule.linac.name}:{cryomodule.name}00:"
    )


def test_num_cavities(cryomodule):
    assert len(cryomodule.cavities.keys()) == 8


def test_is_high_energy_covers_all_of_l4b():
    """LCLS-II-HE is exactly L4B, CM 37 through 59."""
    from sc_linac_physics.utils.sc_linac.linac import Machine
    from sc_linac_physics.utils.sc_linac.linac_utils import L4B

    machine = Machine()

    for name in L4B:
        assert machine.cryomodules[name].is_high_energy is True

    # 36 is skipped in the numbering: L3B ends at 35, L4B starts at 37.
    for name in ("01", "10", "35", "H1", "H2"):
        assert machine.cryomodules[name].is_high_energy is False


def test_harmonic_linearizer_and_high_energy_are_exclusive():
    """A cryomodule cannot be both, so the limit branches cannot collide."""
    from sc_linac_physics.utils.sc_linac.linac import Machine

    machine = Machine()
    for cm in machine.cryomodules.values():
        assert not (cm.is_harmonic_linearizer and cm.is_high_energy)
