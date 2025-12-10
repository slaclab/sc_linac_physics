"""
Centralized constants for Microphonics GUI application.
"""

import re
from pathlib import Path

from sc_linac_physics.utils.sc_linac.linac_utils import LINAC_CM_MAP

# HARDWARE & SAMPLING
BASE_HARDWARE_SAMPLE_RATE = 2000  # Hz - base sample rate from hardware
BUFFER_LENGTH = 16384  # samples per buffer
VALID_DECIMATION_VALUES = {1, 2, 4, 8}
DEFAULT_DECIMATION = 2
DEFAULT_BUFFER_COUNT = 1

# CAVITY CONFIGURATION
CAVITIES_PER_RACK = 4
RACK_A_CAVITIES = [1, 2, 3, 4]
RACK_B_CAVITIES = [5, 6, 7, 8]

# LINAC CONFIGURATION
VALID_LINACS = dict(zip(["L0B", "L1B", "L2B", "L3B"], LINAC_CM_MAP))

# FILE PATHS
DEFAULT_DATA_PATH = Path("/u1/lcls/physics/rf_lcls2/microphonics")
DEFAULT_SCRIPT_PATH = Path(
    "/usr/local/lcls/package/lcls2_llrf/srf/software/res_ctl/res_data_acq.py"
)

# DATA ACQUISITION
ACQ_COMPLETION_MARKERS = [
    "Restoring acquisition settings...",
    "Done",
]
ACQ_PROGRESS_REGEX = re.compile(r"Acquired\s+(\d+)\s+/\s+(\d+)\s+buffers")

# FILE PARSING
FILE_HEADER_MARKER = "# ACCL:"
FILE_COMMENT_MARKER = "#"
FILE_DECIMATION_KEY = "# wave_samp_per"

# STATISTICS
OUTLIER_THRESHOLD_STD_DEVS = 2.5
