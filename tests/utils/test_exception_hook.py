import sys
import threading
from unittest.mock import patch

import pytest

from sc_linac_physics.utils import exception_hook


@pytest.fixture
def restore_hooks():
    """Put back whatever hooks the test replaced."""
    old_sys, old_threading = sys.excepthook, threading.excepthook
    yield
    sys.excepthook, threading.excepthook = old_sys, old_threading
    exception_hook._notifier = None


@pytest.fixture
def popups(qapp):
    """Collect (title, message, details) per popup instead of showing it."""
    shown = []
    with patch.object(
        exception_hook,
        "_show_popup",
        side_effect=lambda *popup: shown.append(popup),
    ):
        yield shown


def _raise(exc):
    try:
        raise exc
    except BaseException:
        return sys.exc_info()


def test_install_replaces_both_hooks(qapp, restore_hooks):
    exception_hook.install()
    assert sys.excepthook is exception_hook._sys_hook
    assert threading.excepthook is exception_hook._threading_hook


def test_install_twice_keeps_one_notifier(qapp, restore_hooks):
    exception_hook.install()
    first = exception_hook._notifier
    exception_hook.install()
    assert exception_hook._notifier is first


def test_main_thread_exception_logs_and_shows_popup(
    qapp, qtbot, restore_hooks, popups
):
    exception_hook.install()
    error = ValueError("bad setpoint")
    with patch.object(exception_hook, "logger") as logger:
        sys.excepthook(*_raise(error))
    assert logger.error.call_args.kwargs["exc_info"][1] is error
    qtbot.waitUntil(lambda: bool(popups))
    title, message, details = popups[0]
    assert "ValueError" in title
    assert message == "bad setpoint"
    assert "Traceback" in details


def test_worker_thread_exception_reaches_main_thread_popup(
    qapp, qtbot, restore_hooks, popups
):
    """Python threads report through threading.excepthook, not sys's."""
    exception_hook.install()
    popup_threads = []
    exception_hook._show_popup.side_effect = lambda *popup: (
        popups.append(popup),
        popup_threads.append(threading.current_thread()),
    )

    def fail():
        raise RuntimeError("archiver timed out")

    thread = threading.Thread(target=fail)
    thread.start()
    thread.join()
    qtbot.waitUntil(lambda: bool(popups))
    assert "archiver timed out" in popups[0][1]
    assert popup_threads[0] is threading.main_thread()


def test_keyboard_interrupt_goes_to_default_hook(qapp, restore_hooks, popups):
    exception_hook.install()
    with patch.object(sys, "__excepthook__") as default:
        sys.excepthook(*_raise(KeyboardInterrupt()))
    default.assert_called_once()
    assert not popups


def test_popup_shows_details_and_is_released_on_close(qapp):
    exception_hook._show_popup("Unexpected error: X", "msg", "trace")
    popup = exception_hook._open_popups[-1]
    assert popup.isVisible()
    assert popup.text() == "msg"
    assert popup.detailedText() == "trace"
    popup.done(0)
    assert popup not in exception_hook._open_popups
