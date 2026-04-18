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


DEFAULT_BETA_VISIBLE_PHASES: tuple[CommissioningPhase, ...] = (
    CommissioningPhase.PIEZO_PRE_RF,
)


def build_default_phase_specs(
    *,
    include_placeholder_phases: bool = False,
    visible_phases: (
        tuple[CommissioningPhase, ...] | list[CommissioningPhase] | None
    ) = None,
) -> list[PhaseTabSpec]:
    """Build phase tab specs from ``PHASE_REGISTRY``.

    The RF commissioning app is still beta and only the Piezo Pre-RF phase is
    fully implemented end-to-end. To keep the default UI clean and simple, the
    default tab set includes only implemented phases.

    Set ``include_placeholder_phases=True`` to surface the placeholder tabs for
    development work, or pass ``visible_phases`` to explicitly control the tab
    list while preserving registry order.
    """
    requested_phases = (
        {phase for phase in PHASE_REGISTRY if PHASE_REGISTRY[phase].record_attr}
        if include_placeholder_phases
        else set(visible_phases or DEFAULT_BETA_VISIBLE_PHASES)
    )

    return [
        PhaseTabSpec(
            title=reg.display_label,
            display_class=get_phase_display_class(
                phase, reg.display_label, reg.record_attr, reg.data_model
            ),
            phase=phase,
        )
        for phase, reg in PHASE_REGISTRY.items()
        if reg.record_attr is not None and phase in requested_phases
    ]
