from unittest.mock import MagicMock, patch

import pytest

from sc_linac_physics.utils.epics import LazyPV


class Thing:
    status_pv_obj = LazyPV("status_pv")
    slow_pv_obj = LazyPV("slow_pv", connection_timeout=10.0)

    def __init__(self):
        self.status_pv = "TEST:STATUS"
        self.slow_pv = "TEST:SLOW"


@pytest.fixture
def pv_cls():
    with patch("sc_linac_physics.utils.epics.lazy.PV") as cls:
        cls.side_effect = lambda name, **kw: MagicMock(pvname=name, kw=kw)
        yield cls


def test_not_created_until_first_access(pv_cls):
    thing = Thing()
    pv_cls.assert_not_called()
    assert thing._status_pv_obj is None


def test_created_once_from_name_attr_and_cached(pv_cls):
    thing = Thing()
    first = thing.status_pv_obj
    assert thing.status_pv_obj is first
    assert thing._status_pv_obj is first
    pv_cls.assert_called_once_with("TEST:STATUS")


def test_pv_kwargs_passed_through(pv_cls):
    assert Thing().slow_pv_obj.kw == {"connection_timeout": 10.0}


def test_injected_mock_is_used(pv_cls):
    """Tests set _x_pv_obj directly; that must keep working."""
    thing = Thing()
    mock = MagicMock()
    thing._status_pv_obj = mock
    assert thing.status_pv_obj is mock
    pv_cls.assert_not_called()


def test_instances_do_not_share_pvs(pv_cls):
    a, b = Thing(), Thing()
    assert a.status_pv_obj is not b.status_pv_obj


def test_assigning_public_name_raises(pv_cls):
    with pytest.raises(AttributeError, match="read-only"):
        Thing().status_pv_obj = MagicMock()


def test_class_access_returns_descriptor():
    assert isinstance(Thing.status_pv_obj, LazyPV)
