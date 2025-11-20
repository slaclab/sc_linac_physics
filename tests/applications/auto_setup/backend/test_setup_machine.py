from unittest.mock import MagicMock, patch

import pytest

from sc_linac_physics.applications.auto_setup.backend.setup_machine import (
    SetupMachine,
)


@pytest.fixture
def setup_machine():
    with (
        patch(
            "sc_linac_physics.utils.sc_linac.cavity.custom_logger"
        ) as mock_cavity_logger,
        patch(
            "sc_linac_physics.applications.auto_setup.backend.setup_cavity.custom_logger"
        ) as mock_setup_logger,
    ):

        mock_cavity_logger.return_value = MagicMock()
        mock_setup_logger.return_value = MagicMock()

        yield SetupMachine()


def test_pv_prefix(setup_machine):
    assert "ACCL:SYS0:SC:" == setup_machine.pv_prefix


def test_clear_abort(setup_machine):
    for cm in setup_machine.cryomodules.values():
        cm.clear_abort = MagicMock()
    setup_machine.clear_abort()
    for cm in setup_machine.cryomodules.values():
        cm.clear_abort.assert_called()
