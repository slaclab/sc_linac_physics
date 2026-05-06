"""Standard placeholder phase displays."""

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CavityCharacterization,
    FrequencyTuningData,
    HighPowerRampData,
    MPProcessingData,
    OneHourRunData,
    PiezoWithRFTest,
    SSACharacterization,
)
from sc_linac_physics.applications.rf_commissioning.ui.builders import (
    CavityCharUI,
    FrequencyTuningUI,
    HighPowerUI,
    PiezoWithRFUI,
    SSACharUI,
)

from .base_placeholder import BasePlaceholderDisplay


class FrequencyTuningDisplay(BasePlaceholderDisplay):
    """Display for Frequency Tuning phase (combines cold landing and pi-mode)."""

    UI_CLASS = FrequencyTuningUI
    PHASE_NAME = "Frequency Tuning"
    DATA_ATTR = "frequency_tuning"
    DATA_MODEL = FrequencyTuningData


class SSACharDisplay(BasePlaceholderDisplay):
    """Display for SSA Characterization phase."""

    UI_CLASS = SSACharUI
    PHASE_NAME = "SSA Characterization"
    DATA_ATTR = "ssa_char"
    DATA_MODEL = SSACharacterization


class CavityCharDisplay(BasePlaceholderDisplay):
    """Display for Cavity Characterization phase."""

    UI_CLASS = CavityCharUI
    PHASE_NAME = "Cavity Characterization"
    DATA_ATTR = "cavity_char"
    DATA_MODEL = CavityCharacterization


class PiezoWithRFDisplay(BasePlaceholderDisplay):
    """Display for Piezo with RF phase."""

    UI_CLASS = PiezoWithRFUI
    PHASE_NAME = "Piezo with RF"
    DATA_ATTR = "piezo_with_rf"
    DATA_MODEL = PiezoWithRFTest


class HighPowerRampDisplay(BasePlaceholderDisplay):
    """Display for High Power Ramp phase."""

    UI_CLASS = HighPowerUI
    PHASE_NAME = "High Power Ramp"
    DATA_ATTR = "high_power_ramp"
    DATA_MODEL = HighPowerRampData


class HighPowerMPProcessingDisplay(BasePlaceholderDisplay):
    """Display for High Power MP Processing phase."""

    UI_CLASS = HighPowerUI
    PHASE_NAME = "MP Processing"
    DATA_ATTR = "mp_processing"
    DATA_MODEL = MPProcessingData


class HighPowerOneHourRunDisplay(BasePlaceholderDisplay):
    """Display for High Power One Hour Run phase."""

    UI_CLASS = HighPowerUI
    PHASE_NAME = "One Hour Run"
    DATA_ATTR = "one_hour_run"
    DATA_MODEL = OneHourRunData
