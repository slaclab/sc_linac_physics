import sys
from pathlib import Path

QUENCH_AMP_THRESHOLD = 0.7
LOADED_Q_CHANGE_FOR_QUENCH = 0.6
MAX_WAIT_TIME_FOR_QUENCH = 30
QUENCH_STABLE_TIME = 30 * 60
MAX_QUENCH_RETRIES = 100
DECARAD_SETTLE_TIME = 3
RADIATION_LIMIT = 2

if sys.platform == "darwin":  # macOS
    BASE_LOG_DIR = Path.home() / "logs" / "quench"
else:  # Linux (production)
    BASE_LOG_DIR = Path("/home/physics/srf/logfiles/quench")
