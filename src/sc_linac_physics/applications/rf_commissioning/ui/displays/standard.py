"""Standard placeholder phase displays."""

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    MPProcessingData,
    OneHourRunData,
    PiezoWithRFTest,
)
from sc_linac_physics.applications.rf_commissioning.ui.builders import (
    GenericPhaseUI,
)

from .base_placeholder import BasePlaceholderDisplay

# FrequencyTuningDisplay used to live here as a GenericPhaseUI placeholder.
# The real one is in frequency_tuning.py (PR #270); the placeholder is gone.


class PiezoWithRFDisplay(BasePlaceholderDisplay):
    """Display for Piezo with RF phase."""

    UI_CLASS = GenericPhaseUI
    PHASE_NAME = "Piezo with RF"
    DATA_ATTR = "piezo_with_rf"
    DATA_MODEL = PiezoWithRFTest


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
