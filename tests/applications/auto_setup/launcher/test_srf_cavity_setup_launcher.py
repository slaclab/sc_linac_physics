from random import randint, choice
from unittest.mock import MagicMock

import pytest
from lcls_tools.common.controls.pyepics.utils import make_mock_pv

from applications.auto_setup.backend.setup_cavity import SetupCavity
from applications.auto_setup.backend.setup_utils import (
    STATUS_RUNNING_VALUE,
    STATUS_READY_VALUE,
    STATUS_ERROR_VALUE,
)
from applications.auto_setup.launcher.srf_cavity_setup_launcher import setup_cavity


@pytest.fixture
def cavity():
    cavity = SetupCavity(cavity_num=randint(1, 8), rack_object=MagicMock())
    cavity.setup = MagicMock()
    cavity.shut_down = MagicMock()
    cavity._status_msg_pv_obj = make_mock_pv()
    cavity._status_pv_obj = make_mock_pv()
    yield cavity


def test_setup(cavity):
    args = MagicMock()
    args.shutdown = False
    cavity._status_pv_obj.get = MagicMock(
        return_value=choice([STATUS_READY_VALUE, STATUS_ERROR_VALUE])
    )
    setup_cavity(cavity, args)
    cavity.setup.assert_called()


def test_setup_running(cavity):
    args = MagicMock()
    args.shutdown = False
    cavity._status_pv_obj.get = MagicMock(return_value=STATUS_RUNNING_VALUE)
    setup_cavity(cavity, args)
    cavity.setup.assert_not_called()
    cavity.shut_down.assert_not_called()
    cavity._status_msg_pv_obj.put.assert_called_with(f"{cavity} script already running")


def test_shutdown(cavity):
    args = MagicMock()
    args.shutdown = True
    cavity._status_pv_obj.get = MagicMock(
        return_value=choice([STATUS_READY_VALUE, STATUS_ERROR_VALUE])
    )
    setup_cavity(cavity, args)
    cavity.setup.assert_not_called()
    cavity.shut_down.assert_called()
