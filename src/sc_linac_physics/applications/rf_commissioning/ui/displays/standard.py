"""Standard placeholder phase displays."""

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    OneHourRunData,
)
from sc_linac_physics.applications.rf_commissioning.ui.builders import (
    GenericPhaseUI,
)

from .base_placeholder import BasePlaceholderDisplay

# FrequencyTuningDisplay used to live here as a GenericPhaseUI placeholder.
# The real one is in frequency_tuning.py (PR #270); the placeholder is gone.
# PiezoWithRFDisplay likewise moved to piezo_with_rf.py, and the MP
# processing placeholder to mp_processing.py (MPProcessingDisplay).


class HighPowerOneHourRunDisplay(BasePlaceholderDisplay):
    """Display for High Power One Hour Run phase."""

    UI_CLASS = GenericPhaseUI
    PHASE_NAME = "One Hour Run"
    DATA_ATTR = "one_hour_run"
    DATA_MODEL = OneHourRunData
