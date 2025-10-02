import pytest

from sc_linac_physics.utils.sc_linac.linac import Machine
from sc_linac_physics.utils.sc_linac.linac_utils import (
    BEAMLINE_VACUUM_INFIXES,
    INSULATING_VACUUM_CRYOMODULES,
    LINAC_CM_MAP,
)


@pytest.fixture
def machine():
    yield Machine()


def test_names(machine):
    for i in range(4):
        linac = machine.linacs[i]
        assert linac.name == f"L{i}B"


def test_crymodules(machine):
    for i in range(4):
        linac = machine.linacs[i]
        for cm_name in LINAC_CM_MAP[i]:
            assert cm_name in linac.cryomodules.keys()


def test_beamline_vacuum_pvs(machine):
    for i in range(4):
        linac = machine.linacs[i]
        for infix in BEAMLINE_VACUUM_INFIXES[i]:
            assert f"VGXX:{linac.name}:{infix}:COMBO_P" in linac.beamline_vacuum_pvs


def test_insulating_vacuum_pvs(machine):
    for i in range(4):
        linac = machine.linacs[i]
        for cm in INSULATING_VACUUM_CRYOMODULES[i]:
            assert f"VGXX:{linac.name}:{cm}96:COMBO_P" in linac.insulating_vacuum_pvs
