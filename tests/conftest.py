import builtins
import logging
import logging.handlers
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, Mock

import pyqtgraph as pg
import pytest
from qtpy.QtWidgets import QApplication


@pytest.fixture(autouse=True)
def suppress_logging():
    """Suppress all logging output during tests."""
    # Disable all logging output
    logging.disable(logging.CRITICAL)
    yield
    # Re-enable logging after test
    logging.disable(logging.NOTSET)


class MockHandler:
    """A mock handler that mimics logging.Handler without creating files."""

    def __init__(self, *args, **kwargs):
        import threading

        self.level = logging.NOTSET
        self.filters = []
        self.lock = threading.RLock()
        self._name = None
        self.formatter = None
        self.stream = None
        self._builtin_open = open
        self.baseFilename = "/dev/null"
        self.mode = "a"

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self._name = value

    def setLevel(self, level):
        self.level = level

    def setFormatter(self, formatter):
        self.formatter = formatter

    def addFilter(self, filter):
        self.filters.append(filter)

    def removeFilter(self, filter):
        if filter in self.filters:
            self.filters.remove(filter)

    def filter(self, record):
        return True

    def close(self):
        with self.lock:
            self.stream = None

    def emit(self, record):
        # Don't actually write anything
        pass

    def shouldRollover(self, record):
        # Never rollover in tests
        return False

    def _open(self):
        # Return a mock file object instead of opening a real file
        from io import StringIO

        return StringIO()

    def handle(self, record):
        return True

    def flush(self):
        pass

    def format(self, record):
        return ""

    def acquire(self):
        self.lock.acquire()

    def release(self):
        self.lock.release()

    def handleError(self, record):
        pass

    def createLock(self):
        pass

    def set_name(self, name):
        self._name = name

    def __repr__(self):
        return f"<MockHandler at {id(self)}>"


@pytest.fixture(autouse=True)
def mock_log_files():
    """Prevent actual log file creation in all tests."""
    # Mock both RotatingFileHandler and regular FileHandler
    with (
        patch("logging.handlers.RotatingFileHandler", MockHandler),
        patch("logging.FileHandler", MockHandler),
    ):
        yield


@pytest.fixture(autouse=True)
def clear_logger_cache():
    """Clear logger cache between tests to avoid state pollution."""
    import sc_linac_physics.utils.logger

    sc_linac_physics.utils.logger._created_loggers.clear()

    # Also clear all handlers from existing loggers
    for logger_name in list(logging.Logger.manager.loggerDict.keys()):
        logger = logging.getLogger(logger_name)
        logger.handlers.clear()
        logger.propagate = True

    yield

    sc_linac_physics.utils.logger._created_loggers.clear()


@pytest.fixture(autouse=True)
def prevent_log_file_creation():
    """Prevent log file creation by mocking Path operations for log files."""
    original_path_mkdir = Path.mkdir
    original_path_open = Path.open

    def mock_mkdir(self, mode=0o777, parents=False, exist_ok=False):
        # If it's a logs directory, pretend it was created
        if "log" in str(self).lower():
            return None
        return original_path_mkdir(
            self, mode=mode, parents=parents, exist_ok=exist_ok
        )

    def mock_open(self, mode="r", *args, **kwargs):
        # If it's a log file, return a mock file object
        if "log" in str(self).lower() or str(self).endswith(".log"):
            mock_file = Mock()
            mock_file.__enter__ = Mock(return_value=mock_file)
            mock_file.__exit__ = Mock(return_value=None)
            mock_file.write = Mock()
            mock_file.read = Mock(return_value="")
            mock_file.flush = Mock()
            mock_file.close = Mock()
            return mock_file
        return original_path_open(self, mode=mode, *args, **kwargs)

    with (
        patch.object(Path, "mkdir", mock_mkdir),
        patch.object(Path, "open", mock_open),
    ):
        yield


class FakeEPICS_PV:
    """Fake EPICS PV for testing - mimics the interface"""

    def __init__(
        self,
        pvname,
        connection_timeout=None,
        callback=None,
        form="time",
        verbose=False,
        auto_monitor=True,
        count=None,
        connection_callback=None,
        access_callback=None,
    ):
        self.pvname = pvname
        self._connected = True
        self._get_value = 42.0
        self._put_return = 1
        self.severity = 0  # EPICS_NO_ALARM_VAL
        self.auto_monitor = auto_monitor

        # Add callback storage
        self.callbacks = {}
        self.connection_callbacks = []
        self._callback_counter = 0

        # Store callbacks if provided
        if callback:
            self.add_callback(callback)
        if connection_callback:
            self.connection_callbacks.append(connection_callback)
            # Trigger connection callback immediately
            connection_callback(pvname=pvname, conn=True, pv=self)

    @property
    def connected(self):
        return self._connected

    def wait_for_connection(self, timeout=None):
        return self._connected

    def get(
        self,
        count=None,
        as_string=False,
        as_numpy=True,
        timeout=None,
        with_ctrlvars=False,
        use_monitor=None,
    ):
        return self._get_value

    def put(
        self,
        value,
        wait=True,
        timeout=None,
        use_complete=False,
        callback=None,
        callback_data=None,
    ):
        self._get_value = value

        # Trigger callbacks when value changes
        for cb in self.callbacks.values():
            try:
                cb(pvname=self.pvname, value=value, timestamp=None)
            except Exception:
                pass  # Silently ignore callback errors in tests

        return self._put_return

    def add_callback(self, callback, index=None, **kwargs):
        """Add a callback function"""
        if index is None:
            index = self._callback_counter
            self._callback_counter += 1
        self.callbacks[index] = callback

        # Immediately trigger callback with current value
        try:
            callback(pvname=self.pvname, value=self._get_value, timestamp=None)
        except Exception:
            pass  # Silently ignore callback errors

        return index

    def remove_callback(self, index):
        """Remove a specific callback"""
        if index in self.callbacks:
            del self.callbacks[index]

    def clear_callbacks(self):
        """Clear all callbacks - REQUIRED by PyDM when disconnecting"""
        self.callbacks.clear()
        self.connection_callbacks.clear()

    def disconnect(self):
        """Disconnect the PV"""
        self._connected = False
        self.clear_callbacks()


# Create fake epics exceptions
class FakeCASeverityException(Exception):
    """Fake CASeverityException"""

    pass


def fake_with_initial_context(func):
    """Fake decorator for withInitialContext"""
    return func


def pytest_configure(config):
    """
    Pytest hook that runs before test collection.
    Inject our fake EPICS module into sys.modules before any test imports happen.
    """
    # Create a fake epics module with all necessary attributes
    fake_epics = MagicMock()
    fake_epics.PV = FakeEPICS_PV

    # Create fake epics.ca submodule
    fake_epics_ca = MagicMock()
    fake_epics_ca.CASeverityException = FakeCASeverityException
    fake_epics_ca.withInitialContext = fake_with_initial_context

    # Set up the ca attribute
    fake_epics.ca = fake_epics_ca

    # Inject into sys.modules
    sys.modules["epics"] = fake_epics
    sys.modules["epics.pv"] = fake_epics
    sys.modules["epics.ca"] = fake_epics_ca


# Mock filesystem operations BEFORE any imports that might use them
_original_os_mkdir = os.mkdir
_original_open = open


def _mock_os_mkdir(path, mode=0o777, *, dir_fd=None):
    """Mock os.mkdir to ignore /home/physics paths and log directories"""
    path_str = str(path)
    if "/home/physics" in path_str or "log" in path_str.lower():
        # Silently succeed for /home/physics paths and log directories
        return
    # For other paths, use original
    return _original_os_mkdir(path, mode, dir_fd=dir_fd)


def _mock_open(file, mode="r", *args, **kwargs):
    """Mock open to redirect /home/physics to /tmp and ignore log files"""
    file_str = str(file)

    # If it's a log file, return a mock
    if "log" in file_str.lower() or file_str.endswith(".log"):
        mock_file = Mock()
        mock_file.__enter__ = Mock(return_value=mock_file)
        mock_file.__exit__ = Mock(return_value=None)
        mock_file.write = Mock()
        mock_file.read = Mock(return_value="")
        mock_file.flush = Mock()
        mock_file.close = Mock()
        return mock_file

    if "/home/physics" in file_str:
        # Create a temp directory structure
        import tempfile

        temp_base = Path(tempfile.gettempdir()) / "test_physics"
        new_file = temp_base / file_str.replace("/home/physics/", "")
        new_file.parent.mkdir(parents=True, exist_ok=True)
        return _original_open(new_file, mode, *args, **kwargs)
    return _original_open(file, mode, *args, **kwargs)


# Apply mocks immediately
os.mkdir = _mock_os_mkdir
builtins.open = _mock_open


@pytest.fixture(autouse=True, scope="session")
def setup_test_environment(tmp_path_factory):
    """Set up test environment with redirected filesystem operations"""
    temp_physics = tmp_path_factory.mktemp("physics_home")

    # Update mocks to use the proper temp directory
    def _better_os_mkdir(path, mode=0o777, *, dir_fd=None):
        path_str = str(path)
        if "log" in path_str.lower():
            # Silently succeed for log paths
            return
        if "/home/physics" in path_str:
            new_path = temp_physics / path_str.replace("/home/physics/", "")
            new_path.parent.mkdir(parents=True, exist_ok=True)
            if not new_path.exists():
                return _original_os_mkdir(str(new_path), mode)
            return
        return _original_os_mkdir(path, mode, dir_fd=dir_fd)

    def _better_open(file, mode="r", *args, **kwargs):
        file_str = str(file)

        # Mock log files
        if "log" in file_str.lower() or file_str.endswith(".log"):
            mock_file = Mock()
            mock_file.__enter__ = Mock(return_value=mock_file)
            mock_file.__exit__ = Mock(return_value=None)
            mock_file.write = Mock()
            mock_file.read = Mock(return_value="")
            mock_file.flush = Mock()
            mock_file.close = Mock()
            return mock_file

        if "/home/physics" in file_str:
            new_file = temp_physics / file_str.replace("/home/physics/", "")
            new_file.parent.mkdir(parents=True, exist_ok=True)
            return _original_open(new_file, mode, *args, **kwargs)
        return _original_open(file, mode, *args, **kwargs)

    os.mkdir = _better_os_mkdir
    builtins.open = _better_open

    yield temp_physics

    # Restore originals
    os.mkdir = _original_os_mkdir
    builtins.open = _original_open


# Disable PyDM data plugins before importing any PyDM modules
os.environ.setdefault("PYDM_DATA_PLUGINS_DISABLED", "1")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt5")
os.environ.setdefault("PYDM_DISABLE_TELEMETRY", "1")


@pytest.fixture(scope="session")
def ensure_installed():
    """Ensure package is installed in editable mode."""
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "-e", "."],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


@pytest.fixture
def all_script_names():
    """List of all expected console script names."""
    return [
        # Main CLI
        "sc-linac",
        # Display Launchers
        "sc-srf-home",
        "sc-cavity",
        "sc-faults",
        "sc-fcount",
        # Application Launchers
        "sc-quench",
        "sc-setup",
        "sc-q0",
        "sc-tune",
        # Setup CLI
        "sc-setup-all",
        "sc-setup-linac",
        "sc-setup-cm",
        "sc-setup-cav",
        # Watcher
        "sc-watcher",
        # Simulation
        "sc-sim",
    ]


@pytest.fixture
def mock_qt_app(monkeypatch):
    """Mock QApplication for GUI launchers."""

    class MockQApplication:
        def __init__(self, *args, **kwargs):
            pass

        def exec_(self):
            return 0

        def exec(self):  # Qt6
            return 0

    monkeypatch.setattr(
        "PyQt5.QtWidgets.QApplication", MockQApplication, raising=False
    )
    monkeypatch.setattr(
        "PyQt6.QtWidgets.QApplication", MockQApplication, raising=False
    )


@pytest.fixture(scope="session", autouse=True)
def patch_pyqtgraph():
    """
    Patch PyQtGraph for Python 3.13 compatibility.
    """
    original_getattr = pg.PlotWidget.__getattr__

    def patched_getattr(self, attr):
        if attr == "autoRangeEnabled":
            return self.getViewBox().autoRangeEnabled
        return original_getattr(self, attr)

    pg.PlotWidget.__getattr__ = patched_getattr
    yield


@pytest.fixture(scope="session", autouse=True)
def qapp_global():
    if not QApplication.instance():
        app = QApplication(sys.argv)
        yield app
        app.quit()
    else:
        yield QApplication.instance()
