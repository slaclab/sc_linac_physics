import os
import subprocess
import sys
from unittest.mock import patch

import pyqtgraph as pg

# tests/conftest.py
import pytest
from qtpy.QtWidgets import QApplication


@pytest.fixture(autouse=True, scope="session")
def mock_physics_home(tmp_path_factory):
    """Replace /home/physics with a temporary directory for all tests"""
    temp_physics = tmp_path_factory.mktemp("physics_home")

    # Store the original function before patching
    original_expanduser = os.path.expanduser

    # Mock it in any modules that might use it
    with patch("os.path.expanduser") as mock_expand:

        def side_effect(path):
            if "/home/physics" in path:
                return str(temp_physics / path.replace("/home/physics/", ""))
            # Call the original function directly (not via __wrapped__)
            return original_expanduser(path)

        mock_expand.side_effect = side_effect
        yield temp_physics


# Disable PyDM data plugins before importing any PyDM modules
os.environ.setdefault("PYDM_DATA_PLUGINS_DISABLED", "1")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt5")
# Optional: avoid any PyDM telemetry/tasks
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

    Issue: PyQtGraph's PlotDataItem tries to call view.autoRangeEnabled()
    on PlotWidget, but PlotWidget doesn't have this method directly.
    It needs to be accessed via getViewBox().autoRangeEnabled().

    This is a known compatibility issue with Python 3.13.
    TODO: Remove this patch when upgrading to PyQtGraph 0.14+ or
    when downgrading to Python 3.11/3.12.
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
