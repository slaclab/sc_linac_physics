from unittest.mock import MagicMock

import pytest
from numpy.random import choice

from applications.auto_setup.backend.setup_cryomodule import SetupCryomodule
from applications.auto_setup.backend.setup_machine import SetupMachine


@pytest.fixture
def setup_cryomodule() -> SetupCryomodule:
    machine = SetupMachine()
    return choice(list(machine.cryomodules.values()))


def test_clear_abort(setup_cryomodule):
    for cavity in setup_cryomodule.cavities.values():
        cavity.clear_abort = MagicMock()
    setup_cryomodule.clear_abort()
    for cavity in setup_cryomodule.cavities.values():
        cavity.clear_abort.assert_called()
