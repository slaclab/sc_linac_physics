"""Phase display registry and lookup helpers."""

from typing import cast

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
)
from sc_linac_physics.applications.rf_commissioning.ui.builders import (
    GenericPhaseUI,
)

from .base_placeholder import BasePlaceholderDisplay
from .piezo_pre_rf import PiezoPreRFDisplay
from .standard import (
    CavityCharDisplay,
    FrequencyTuningDisplay,
    HighPowerMPProcessingDisplay,
    HighPowerOneHourRunDisplay,
    HighPowerRampDisplay,
    PiezoWithRFDisplay,
    SSACharDisplay,
)

PHASE_DISPLAY_MAP: dict[CommissioningPhase, type[BasePlaceholderDisplay]] = {
    CommissioningPhase.PIEZO_PRE_RF: PiezoPreRFDisplay,
    CommissioningPhase.FREQUENCY_TUNING: FrequencyTuningDisplay,
    CommissioningPhase.SSA_CHAR: SSACharDisplay,
    CommissioningPhase.CAVITY_CHAR: CavityCharDisplay,
    CommissioningPhase.PIEZO_WITH_RF: PiezoWithRFDisplay,
    CommissioningPhase.HIGH_POWER_RAMP: HighPowerRampDisplay,
    CommissioningPhase.MP_PROCESSING: HighPowerMPProcessingDisplay,
    CommissioningPhase.ONE_HOUR_RUN: HighPowerOneHourRunDisplay,
}


def get_phase_display_class(
    phase: CommissioningPhase,
    display_label: str,
    record_attr: str,
    data_model,
) -> type[BasePlaceholderDisplay]:
    """Return a display class for *phase*, creating a generic one if needed."""
    if phase in PHASE_DISPLAY_MAP:
        return PHASE_DISPLAY_MAP[phase]

    class_name = (
        "".join(word.capitalize() for word in phase.value.split("_"))
        + "Display"
    )
    return cast(
        type[BasePlaceholderDisplay],
        type(
            class_name,
            (BasePlaceholderDisplay,),
            {
                "UI_CLASS": GenericPhaseUI,
                "PHASE_NAME": display_label,
                "DATA_ATTR": record_attr or "",
                "DATA_MODEL": data_model,
            },
        ),
    )
