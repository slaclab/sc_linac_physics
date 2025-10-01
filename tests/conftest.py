import os
import sys

import pytest
from qtpy.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt5")
# Optional: avoid any PyDM telemetry/tasks
os.environ.setdefault("PYDM_DISABLE_TELEMETRY", "1")


@pytest.fixture(scope="session", autouse=True)
def qapp_global():
    if not QApplication.instance():
        app = QApplication(sys.argv)
        yield app
        app.quit()
    else:
        yield QApplication.instance()
