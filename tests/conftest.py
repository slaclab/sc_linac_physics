import os
import sys

import pyqtgraph as pg
import pytest
from qtpy.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt5")
# Optional: avoid any PyDM telemetry/tasks
os.environ.setdefault("PYDM_DISABLE_TELEMETRY", "1")


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
