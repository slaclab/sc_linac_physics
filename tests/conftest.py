import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt5")
# Optional: avoid any PyDM telemetry/tasks
os.environ.setdefault("PYDM_DISABLE_TELEMETRY", "1")
