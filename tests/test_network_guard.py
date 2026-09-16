"""Tests for the outbound-network guard in tests/conftest.py.

The guard exists because a test that escapes its mocks and reaches the network
does not fail — it blocks on a connect with no timeout. The fault heatmap tests
did exactly that, querying lcls-archapp for every one of 480 real cavities and
turning a missing mock into an 80-minute CI job that looked hung rather than
broken.

These tests pin the guard's behavior so it cannot be weakened without a
deliberate change: it must block outbound traffic, leave loopback alone, and
be escapable only through the explicit marker.
"""

import socket

import pytest

from tests import conftest

# TEST-NET-1 (RFC 5737), reserved for documentation and guaranteed never to be
# a real host, so this test can never accidentally reach something.
_UNROUTABLE = ("192.0.2.1", 80)


def test_outbound_connection_is_blocked():
    with pytest.raises(conftest.NetworkAccessBlocked):
        socket.create_connection(_UNROUTABLE)


def test_blocked_message_names_the_address():
    with pytest.raises(conftest.NetworkAccessBlocked) as exc:
        socket.create_connection(_UNROUTABLE)
    assert "192.0.2.1" in str(exc.value)


def test_guard_is_not_an_exception_subclass():
    """Must derive from BaseException so `except Exception` cannot eat it.

    FaultDataFetcher._fetch_single_cavity wraps its archiver call in a broad
    `except Exception` that converts any failure into an error result. A guard
    caught by that handler lets the test pass while testing nothing.
    """
    assert issubclass(conftest.NetworkAccessBlocked, BaseException)
    assert not issubclass(conftest.NetworkAccessBlocked, Exception)


def test_guard_is_installed_by_default():
    assert socket.socket.connect is conftest._guarded_connect
    assert socket.socket.connect_ex is conftest._guarded_connect_ex


def test_loopback_is_left_alone():
    """Loopback must stay usable — caproto and PyDM legitimately use it.

    Port 1 on loopback is closed, so this should surface as an ordinary socket
    error rather than a guard rejection.
    """
    with pytest.raises(OSError):
        socket.create_connection(("127.0.0.1", 1), timeout=0.1)


@pytest.mark.parametrize(
    "address",
    [
        ("127.0.0.1", 5064),
        ("localhost", 8080),
        ("::1", 80),
        ("", 0),
        "/tmp/some.sock",
        None,
    ],
)
def test_addresses_the_guard_permits(address):
    assert conftest._is_loopback(address) is True


@pytest.mark.parametrize(
    "address",
    [
        ("192.0.2.1", 80),
        ("134.79.151.24", 80),
        ("8.8.8.8", 53),
    ],
)
def test_addresses_the_guard_rejects(address):
    assert conftest._is_loopback(address) is False


@pytest.mark.allow_network
def test_allow_network_marker_restores_the_real_connect():
    assert socket.socket.connect is conftest._original_socket_connect
