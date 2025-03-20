from random import randint
from unittest.mock import MagicMock

import pytest

from applications.auto_setup.backend.setup_machine import SetupMachine


@pytest.fixture
def setup_linac():
    machine = SetupMachine()
    return machine.linacs[randint(0, 3)]


def test_pv_prefix(setup_linac):
    assert f"ACCL:{setup_linac.name}:1:" == setup_linac.pv_prefix


def test_clear_abort(setup_linac):
    for cm in setup_linac.cryomodules.values():
        cm.clear_abort = MagicMock()
    setup_linac.clear_abort()
    for cm in setup_linac.cryomodules.values():
        cm.clear_abort.assert_called()
