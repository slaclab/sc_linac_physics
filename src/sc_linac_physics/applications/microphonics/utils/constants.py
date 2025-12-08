"""
Centralized constants for Microphonics GUI application.
"""

import re
from pathlib import Path

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
VALID_LINACS = {
    "L0B": ["01"],
    "L1B": ["02", "03", "H1", "H2"],
    "L2B": [f"{i:02d}" for i in range(4, 16)],
    "L3B": [f"{i:02d}" for i in range(16, 36)],
}

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
