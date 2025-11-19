import builtins
import logging
import logging.handlers
import os
import subprocess
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch, Mock

import pyqtgraph as pg
import pytest
from qtpy.QtWidgets import QApplication


# ============================================================================
# Environment Setup (runs before imports)
# ============================================================================


def pytest_configure(config):
    """
    Pytest hook that runs before test collection.
    Sets up environment and mocks before any imports.
    """
    # Disable PyDM plugins and configure Qt
    os.environ.setdefault("PYDM_DATA_PLUGINS_DISABLED", "1")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("QT_API", "pyqt5")
    os.environ.setdefault("PYDM_DISABLE_TELEMETRY", "1")

    # Inject fake EPICS module
    _setup_fake_epics()


def _setup_fake_epics():
    """Create and inject fake EPICS module into sys.modules."""
    fake_epics = MagicMock()
    fake_epics.PV = FakeEPICS_PV

    fake_epics_ca = MagicMock()
    fake_epics_ca.CASeverityException = FakeCASeverityException
    fake_epics_ca.withInitialContext = fake_with_initial_context

    fake_epics.ca = fake_epics_ca

    sys.modules["epics"] = fake_epics
    sys.modules["epics.pv"] = fake_epics
    sys.modules["epics.ca"] = fake_epics_ca


# ============================================================================
# Fake EPICS Implementation
# ============================================================================


class FakeEPICS_PV:
    """Fake EPICS PV for testing - mimics the interface."""

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
        self.severity = 0
        self.auto_monitor = auto_monitor

        self.callbacks = {}
        self.connection_callbacks = []
        self._callback_counter = 0

        if callback:
            self.add_callback(callback)
        if connection_callback:
            self.connection_callbacks.append(connection_callback)
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

        # Trigger callbacks
        for cb in self.callbacks.values():
            try:
                cb(pvname=self.pvname, value=value, timestamp=None)
            except Exception:
                pass

        return self._put_return

    def add_callback(self, callback, index=None, **kwargs):
        """Add a callback function."""
        if index is None:
            index = self._callback_counter
            self._callback_counter += 1
        self.callbacks[index] = callback

        try:
            callback(pvname=self.pvname, value=self._get_value, timestamp=None)
        except Exception:
            pass

        return index

    def remove_callback(self, index):
        """Remove a specific callback."""
        self.callbacks.pop(index, None)

    def clear_callbacks(self):
        """Clear all callbacks - required by PyDM."""
        self.callbacks.clear()
        self.connection_callbacks.clear()

    def disconnect(self):
        """Disconnect the PV."""
        self._connected = False
        self.clear_callbacks()


class FakeCASeverityException(Exception):
    """Fake CASeverityException."""

    pass


def fake_with_initial_context(func):
    """Fake decorator for withInitialContext."""
    return func


# ============================================================================
# Logging Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def suppress_logging():
    """Suppress all logging output during tests."""
    logging.disable(logging.CRITICAL)
    yield
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
        pass

    def shouldRollover(self, record):
        return False

    def _open(self):
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

    for logger_name in list(logging.Logger.manager.loggerDict.keys()):
        logger = logging.getLogger(logger_name)
        logger.handlers.clear()
        logger.propagate = True

    yield

    sc_linac_physics.utils.logger._created_loggers.clear()


# ============================================================================
# Filesystem Mocking
# ============================================================================

_original_os_mkdir = os.mkdir
_original_open = builtins.open


def _is_log_path(path_str):
    """Check if path is related to logging."""
    return "log" in path_str.lower() or path_str.endswith(".log")


def _is_physics_path(path_str):
    """Check if path is under /home/physics."""
    return "/home/physics" in path_str


def _create_mock_file():
    """Create a mock file object for log files."""
    mock_file = Mock()
    mock_file.__enter__ = Mock(return_value=mock_file)
    mock_file.__exit__ = Mock(return_value=None)
    mock_file.write = Mock()
    mock_file.read = Mock(return_value="")
    mock_file.flush = Mock()
    mock_file.close = Mock()
    return mock_file


@pytest.fixture(autouse=True, scope="session")
def setup_test_environment(tmp_path_factory):
    """Set up test environment with redirected filesystem operations."""
    temp_physics = tmp_path_factory.mktemp("physics_home")

    def mock_os_mkdir(path, mode=0o777, *, dir_fd=None):
        path_str = str(path)

        # Ignore log directories
        if _is_log_path(path_str):
            return

        # Redirect /home/physics paths
        if _is_physics_path(path_str):
            new_path = temp_physics / path_str.replace("/home/physics/", "")
            new_path.parent.mkdir(parents=True, exist_ok=True)
            if not new_path.exists():
                return _original_os_mkdir(str(new_path), mode)
            return

        return _original_os_mkdir(path, mode, dir_fd=dir_fd)

    def mock_open(file, mode="r", *args, **kwargs):
        file_str = str(file)

        # Mock log files
        if _is_log_path(file_str):
            return _create_mock_file()

        # Redirect /home/physics paths
        if _is_physics_path(file_str):
            new_file = temp_physics / file_str.replace("/home/physics/", "")
            new_file.parent.mkdir(parents=True, exist_ok=True)
            return _original_open(new_file, mode, *args, **kwargs)

        return _original_open(file, mode, *args, **kwargs)

    # Apply mocks
    os.mkdir = mock_os_mkdir
    builtins.open = mock_open

    yield temp_physics

    # Restore originals
    os.mkdir = _original_os_mkdir
    builtins.open = _original_open


@pytest.fixture(autouse=True)
def prevent_log_file_creation():
    """Prevent log file creation by mocking Path operations."""
    original_path_mkdir = Path.mkdir
    original_path_open = Path.open

    def mock_mkdir(self, mode=0o777, parents=False, exist_ok=False):
        if _is_log_path(str(self)):
            return None
        return original_path_mkdir(
            self, mode=mode, parents=parents, exist_ok=exist_ok
        )

    def mock_open(self, mode="r", *args, **kwargs):
        if _is_log_path(str(self)):
            return _create_mock_file()
        return original_path_open(self, mode=mode, *args, **kwargs)

    with (
        patch.object(Path, "mkdir", mock_mkdir),
        patch.object(Path, "open", mock_open),
    ):
        yield


# ============================================================================
# Qt/GUI Fixtures
# ============================================================================


@pytest.fixture(scope="session", autouse=True)
def qapp_global():
    """Provide a global QApplication instance for all tests."""
    if not QApplication.instance():
        app = QApplication(sys.argv)
        yield app
        app.quit()
    else:
        yield QApplication.instance()


@pytest.fixture(scope="session", autouse=True)
def patch_pyqtgraph():
    """Patch PyQtGraph for Python 3.13 compatibility."""
    original_getattr = pg.PlotWidget.__getattr__

    def patched_getattr(self, attr):
        if attr == "autoRangeEnabled":
            return self.getViewBox().autoRangeEnabled
        return original_getattr(self, attr)

    pg.PlotWidget.__getattr__ = patched_getattr
    yield


@pytest.fixture
def mock_qt_app(monkeypatch):
    """Mock QApplication for GUI launchers."""

    class MockQApplication:
        def __init__(self, *args, **kwargs):
            pass

        def exec_(self):
            return 0

        def exec(self):
            return 0

    monkeypatch.setattr(
        "PyQt5.QtWidgets.QApplication", MockQApplication, raising=False
    )
    monkeypatch.setattr(
        "PyQt6.QtWidgets.QApplication", MockQApplication, raising=False
    )


# ============================================================================
# Installation & Script Fixtures
# ============================================================================


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
        "sc-linac",
        "sc-srf-home",
        "sc-cavity",
        "sc-faults",
        "sc-fcount",
        "sc-quench",
        "sc-setup",
        "sc-q0",
        "sc-tune",
        "sc-setup-all",
        "sc-setup-linac",
        "sc-setup-cm",
        "sc-setup-cav",
        "sc-watcher",
        "sc-sim",
    ]
