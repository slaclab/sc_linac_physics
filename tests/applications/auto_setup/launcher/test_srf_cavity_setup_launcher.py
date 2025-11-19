from random import randint, choice
from unittest.mock import MagicMock, patch

import pytest
from lcls_tools.common.controls.pyepics.utils import make_mock_pv

from sc_linac_physics.applications.auto_setup.backend.setup_cavity import (
    SetupCavity,
)
from sc_linac_physics.applications.auto_setup.launcher.srf_cavity_setup_launcher import (
    setup_cavity,
)
from sc_linac_physics.utils.sc_linac.linac_utils import (
    STATUS_READY_VALUE,
    STATUS_RUNNING_VALUE,
    STATUS_ERROR_VALUE,
)


@pytest.fixture
def mock_logger():
    """Mock logger to prevent file creation during tests."""
    return MagicMock()


@pytest.fixture
def cavity(mock_logger):
    with patch(
        "sc_linac_physics.utils.sc_linac.cavity.custom_logger"
    ) as mock_custom_logger:
        mock_custom_logger.return_value = mock_logger
        cavity = SetupCavity(cavity_num=randint(1, 8), rack_object=MagicMock())
        cavity.setup = MagicMock()
        cavity.shut_down = MagicMock()
        cavity._status_msg_pv_obj = make_mock_pv()
        cavity._status_pv_obj = make_mock_pv()
        yield cavity


def test_setup(cavity, mock_logger):
    args = MagicMock()
    args.shutdown = False
    cavity._status_pv_obj.get = MagicMock(
        return_value=choice([STATUS_READY_VALUE, STATUS_ERROR_VALUE])
    )
    setup_cavity(cavity, args, mock_logger)
    cavity.setup.assert_called()


def test_setup_running(cavity, mock_logger):
    args = MagicMock()
    args.shutdown = False
    cavity._status_pv_obj.get = MagicMock(return_value=STATUS_RUNNING_VALUE)
    setup_cavity(cavity, args, mock_logger)
    cavity.setup.assert_not_called()
    cavity.shut_down.assert_not_called()
    cavity._status_msg_pv_obj.put.assert_called_with(
        f"{cavity} script already running"
    )


def test_shutdown(cavity, mock_logger):
    args = MagicMock()
    args.shutdown = True
    cavity._status_pv_obj.get = MagicMock(
        return_value=choice([STATUS_READY_VALUE, STATUS_ERROR_VALUE])
    )
    setup_cavity(cavity, args, mock_logger)
    cavity.setup.assert_not_called()
    cavity.shut_down.assert_called()
