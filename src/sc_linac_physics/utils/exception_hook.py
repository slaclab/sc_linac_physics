"""Turn uncaught exceptions into a logged traceback and an error popup.

Without a hook, PyQt5 calls qFatal() on an exception that escapes a Python
override of a Qt virtual, such as QThread.run(). That aborts the whole app,
mid-sequence. With sys.excepthook replaced, PyQt5 calls the hook and keeps
running.

Not pydm.exception.install(): its dispatcher is a QThread that lives for
the whole app, and this repo is moving off QThread (see Threading in
CLAUDE.md). It also leaves threading.excepthook alone, so exceptions in
plain Python threads would only reach stderr.
"""

import logging
import sys
import threading
import traceback
from typing import Optional

from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QMessageBox

logger = logging.getLogger(__name__)


class _Notifier(QObject):
    """Lives on the main thread. Emitting from any thread queues the popup
    to the main thread, which is the only thread allowed to build widgets."""

    exception_raised = pyqtSignal(str, str, str)  # title, message, details

    def __init__(self):
        super().__init__()
        self.exception_raised.connect(self._on_exception_raised)

    def _on_exception_raised(self, title: str, message: str, details: str):
        _show_popup(title, message, details)


_notifier: Optional[_Notifier] = None
# Popups are shown without blocking; keep a reference so they aren't
# garbage collected while on screen.
_open_popups = []


def install() -> None:
    """Install the hooks. Call once, on the main thread, after the
    QApplication exists. Calling again does nothing."""
    global _notifier
    if _notifier is None:
        _notifier = _Notifier()
    sys.excepthook = _sys_hook
    threading.excepthook = _threading_hook


def _sys_hook(exc_type, exc_value, exc_tb) -> None:
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return
    _report(exc_type, exc_value, exc_tb, threading.current_thread().name)


def _threading_hook(args: threading.ExceptHookArgs) -> None:
    if issubclass(args.exc_type, SystemExit):  # same as the default hook
        return
    thread_name = args.thread.name if args.thread else "unknown thread"
    _report(args.exc_type, args.exc_value, args.exc_traceback, thread_name)


def _report(exc_type, exc_value, exc_tb, thread_name: str) -> None:
    logger.error(
        "Uncaught exception in %s",
        thread_name,
        exc_info=(exc_type, exc_value, exc_tb),
    )
    if _notifier is None:
        return
    details = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    try:
        _notifier.exception_raised.emit(
            f"Unexpected error: {exc_type.__name__}",
            str(exc_value),
            details,
        )
    except RuntimeError:  # the QApplication is already gone
        pass


def _show_popup(title: str, message: str, details: str) -> None:
    popup = QMessageBox()
    popup.setIcon(QMessageBox.Critical)
    popup.setWindowTitle(title)
    popup.setText(message)
    popup.setDetailedText(details)
    popup.finished.connect(lambda _: _open_popups.remove(popup))
    _open_popups.append(popup)
    popup.show()
