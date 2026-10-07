import re
from pathlib import Path
from sc_linac_physics.utils.platform_paths import get_field_emission_dir
from sc_linac_physics.utils.sc_linac.linac_utils import LINAC_CM_DICT

# Default File Paths
_DATA_DIR = Path(__file__).resolve().parent

# Runs known to git. The data for each is fetched from the archiver and kept,
# one file per run, in a shared directory outside the package.
RUN_LIST_PATH = _DATA_DIR / "field_emission_runs.csv"
RUN_CACHE_DIR = get_field_emission_dir() / "runs"
# Runs operators add from the display, same columns as RUN_LIST_PATH
ADDED_RUNS_PATH = get_field_emission_dir() / "added_runs.csv"

# Linac Configuration
VALID_LINACS = {0, 1, 2, 3}  # to include linac 4B when ready
VALID_CMS_BY_LINAC = {key: LINAC_CM_DICT[key] for key in VALID_LINACS}
VALID_CMS_LIST = [cm for linac in VALID_CMS_BY_LINAC.values() for cm in linac]

CAVITIES = 8  # number of cavities in cryomodule
CAV_RANGE = list(range(1, CAVITIES + 1))

# Decarad Readouts
RAD_CHANNELS = 10  # number of decarad channels
RAD_CHAN_RANGE = list(range(1, RAD_CHANNELS + 1))
RAD_READ_TYPES = ["average", "instant"]

# Date Formatting
H5_DATE_FORMAT = "%Y-%m-%d_%H%M"  # run cache file names
DISPLAY_DATE_FORMAT = "%A, %B %d, %Y"
STANDARD_DATE_FORMAT = "%m/%d/%y %H:%M"

# Measurements
AMPLITUDE_THRESHOLD = 4  # below this MVoltage, the cavity is considered off

# Plotting
NUM_FIT_POINTS = 250  # how many data points in fit line
NUM_FIT_ITERATIONS = 5500  # how many tries scipy curve fit takes to converge

# Regex Patterns
ELOG_PATTERN = re.compile(
    r"https://mccelog\.slac\.stanford\.edu"
    r"/elog/wbin/elog_item\.php\?elog_id=\d+"
)
