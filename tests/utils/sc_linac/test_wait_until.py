from unittest.mock import MagicMock

import pytest

from sc_linac_physics.utils.sc_linac import linac_utils
from sc_linac_physics.utils.sc_linac.linac_utils import wait_until


class Boom(Exception):
    pass


@pytest.fixture
def clock(monkeypatch):
    """Fake monotonic clock that advances only when sleep() is called."""
    now = [0.0]
    monkeypatch.setattr(linac_utils.time, "monotonic", lambda: now[0])

    def fake_sleep(seconds):
        now[0] += seconds

    monkeypatch.setattr(linac_utils.time, "sleep", fake_sleep)
    return now


def test_returns_without_polling_when_condition_already_true(clock):
    check_abort = MagicMock()
    wait_until(lambda: True, 10, "x", Boom, check_abort=check_abort)
    check_abort.assert_not_called()
    assert clock[0] == 0


def test_returns_once_condition_becomes_true(clock):
    results = iter([False, False, True])
    wait_until(lambda: next(results), 10, "x", Boom, poll_interval=1)
    assert clock[0] == 2


def test_raises_error_class_after_timeout(clock):
    with pytest.raises(Boom, match="Timed out after 3 s waiting for the SSA"):
        wait_until(lambda: False, 3, "the SSA", Boom, poll_interval=1)
    assert clock[0] == 3


def test_check_abort_and_on_poll_run_each_poll_in_order(clock):
    calls = []
    results = iter([False, False, True])
    wait_until(
        lambda: next(results),
        10,
        "x",
        Boom,
        check_abort=lambda: calls.append("abort"),
        on_poll=lambda: calls.append("poll"),
    )
    assert calls == ["abort", "poll", "abort", "poll"]


def test_abort_raised_from_check_abort_propagates(clock):
    def check_abort():
        raise linac_utils.CavityAbortError("abort")

    with pytest.raises(linac_utils.CavityAbortError):
        wait_until(lambda: False, 10, "x", Boom, check_abort=check_abort)
