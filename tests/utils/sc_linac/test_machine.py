import pytest

from sc_linac_physics.utils.sc_linac.linac import Machine, Linac
from sc_linac_physics.utils.sc_linac.linac_utils import ALL_CRYOMODULES


@pytest.fixture
def machine():
    yield Machine()


def test_num_linacs(machine):
    assert len(machine.linacs) == 5


def test_linac_names(machine):
    for i in range(4):
        linac: Linac = machine.linacs[i]
        assert linac.name == f"L{i}B"


def test_cryomodules(machine):
    for cm_name in ALL_CRYOMODULES:
        assert cm_name in machine.cryomodules
