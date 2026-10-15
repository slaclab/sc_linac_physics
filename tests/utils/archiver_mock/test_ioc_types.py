from types import SimpleNamespace
from unittest.mock import patch

import pytest

from sc_linac_physics.utils.archiver_mock import ioc_types


@pytest.fixture(autouse=True)
def fresh():
    ioc_types.reset()
    yield
    ioc_types.reset()


def _response(type_name):
    return SimpleNamespace(data_type=SimpleNamespace(name=type_name))


@pytest.mark.parametrize(
    "type_name, kind",
    [
        ("CTRL_ENUM", "ENUM"),
        ("CTRL_LONG", "INT"),
        ("CTRL_DOUBLE", "FLOAT"),
        ("CTRL_STRING", None),
    ],
)
def test_kind_from_ioc_type(type_name, kind):
    with patch("caproto.sync.client.read", return_value=_response(type_name)):
        assert ioc_types.ioc_kind("SIM:PV") == kind


def test_stops_asking_after_no_answer():
    with patch("caproto.sync.client.read", side_effect=TimeoutError) as read:
        assert ioc_types.ioc_kind("SIM:A") is None
        assert ioc_types.ioc_kind("SIM:B") is None
    assert read.call_count == 1


def test_reset_asks_again():
    with patch("caproto.sync.client.read", side_effect=TimeoutError):
        ioc_types.ioc_kind("SIM:A")
    ioc_types.reset()
    with patch("caproto.sync.client.read", return_value=_response("CTRL_ENUM")):
        assert ioc_types.ioc_kind("SIM:A") == "ENUM"
