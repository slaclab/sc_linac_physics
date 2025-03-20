from unittest.mock import MagicMock

import pytest

from applications.auto_setup.backend.setup_machine import SetupMachine


@pytest.fixture
def setup_machine():
    yield SetupMachine()


def test_pv_prefix(setup_machine):
    assert "ACCL:SYS0:SC:" == setup_machine.pv_prefix


def test_clear_abort(setup_machine):
    for cm in setup_machine.cryomodules.values():
        cm.clear_abort = MagicMock()
    setup_machine.clear_abort()
    for cm in setup_machine.cryomodules.values():
        cm.clear_abort.assert_called()
