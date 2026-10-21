"""Standard placeholder phase displays."""

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    HighPowerRampData,
    MPProcessingData,
    OneHourRunData,
)
from sc_linac_physics.applications.rf_commissioning.ui.builders import (
    GenericPhaseUI,
)

from .base_placeholder import BasePlaceholderDisplay

# FrequencyTuningDisplay used to live here as a GenericPhaseUI placeholder.
# The real one is in frequency_tuning.py (PR #270); the placeholder is gone.
# PiezoWithRFDisplay likewise moved to piezo_with_rf.py.


class HighPowerRampDisplay(BasePlaceholderDisplay):
    """Display for High Power Ramp phase."""

    UI_CLASS = GenericPhaseUI
    PHASE_NAME = "High Power Ramp"
    DATA_ATTR = "high_power_ramp"
    DATA_MODEL = HighPowerRampData


class HighPowerMPProcessingDisplay(BasePlaceholderDisplay):
    """Display for High Power MP Processing phase."""

    UI_CLASS = GenericPhaseUI
    PHASE_NAME = "MP Processing"
    DATA_ATTR = "mp_processing"
    DATA_MODEL = MPProcessingData


class HighPowerOneHourRunDisplay(BasePlaceholderDisplay):
    """Display for High Power One Hour Run phase."""

    UI_CLASS = GenericPhaseUI
    PHASE_NAME = "One Hour Run"
    DATA_ATTR = "one_hour_run"
    DATA_MODEL = OneHourRunData
