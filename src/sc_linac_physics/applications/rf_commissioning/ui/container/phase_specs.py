"""Phase tab metadata and builders for the multi-phase commissioning container."""

from dataclasses import dataclass

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
    PHASE_REGISTRY,
)
from sc_linac_physics.applications.rf_commissioning.ui.phase_display_base import (
    PhaseDisplayBase,
)
from sc_linac_physics.applications.rf_commissioning.ui.phase_displays import (
    get_phase_display_class,
)


@dataclass(frozen=True)
class PhaseTabSpec:
    """Metadata for a phase tab."""

    title: str
    display_class: type[PhaseDisplayBase]
    phase: CommissioningPhase | None = None


def build_default_phase_specs() -> list[PhaseTabSpec]:
    """Build phase tab specs from ``PHASE_REGISTRY``.

    Any phase with a ``record_attr`` (i.e. not the terminal COMPLETE
    phase) gets a tab.  Phases registered in ``PHASE_DISPLAY_MAP`` get their
    specialised display class; all others get a generic placeholder screen
    generated automatically by ``get_phase_display_class``.
    """
    return [
        PhaseTabSpec(
            title=reg.display_label,
            display_class=get_phase_display_class(
                phase, reg.display_label, reg.record_attr, reg.data_model
            ),
            phase=phase,
        )
        for phase, reg in PHASE_REGISTRY.items()
        if reg.record_attr is not None
    ]
