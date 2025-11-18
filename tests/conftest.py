import builtins
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pyqtgraph as pg
import pytest
from qtpy.QtWidgets import QApplication


# tests/conftest.py


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
        return self._put_return


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
    """Mock os.mkdir to ignore /home/physics paths"""
    path_str = str(path)
    if "/home/physics" in path_str:
        # Silently succeed for /home/physics paths
        return
    # For other paths, use original
    return _original_os_mkdir(path, mode, dir_fd=dir_fd)


def _mock_open(file, mode="r", *args, **kwargs):
    """Mock open to redirect /home/physics to /tmp"""
    file_str = str(file)
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
        if "/home/physics" in path_str:
            new_path = temp_physics / path_str.replace("/home/physics/", "")
            new_path.parent.mkdir(parents=True, exist_ok=True)
            if not new_path.exists():
                return _original_os_mkdir(str(new_path), mode)
            return
        return _original_os_mkdir(path, mode, dir_fd=dir_fd)

    def _better_open(file, mode="r", *args, **kwargs):
        file_str = str(file)
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
