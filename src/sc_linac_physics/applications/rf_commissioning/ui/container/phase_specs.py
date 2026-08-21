"""Phase tab metadata and builders for the multi-phase commissioning container."""

from dataclasses import dataclass

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
    PHASE_REGISTRY,
)
from sc_linac_physics.applications.rf_commissioning.ui.phase_display_base import (
    PhaseDisplayBase,
)
from sc_linac_physics.applications.rf_commissioning.ui.displays import (
    get_phase_display_class,
)


@dataclass(frozen=True)
class PhaseTabSpec:
    """Metadata for a phase tab."""

    title: str
    display_class: type[PhaseDisplayBase]
    phase: CommissioningPhase | None = None


DEFAULT_BETA_VISIBLE_PHASES: tuple[CommissioningPhase, ...] = tuple(
    CommissioningPhase
)


def build_default_phase_specs(
    *,
    visible_phases: (
        tuple[CommissioningPhase, ...] | list[CommissioningPhase] | None
    ) = None,
) -> list[PhaseTabSpec]:
    """Build phase tab specs from ``PHASE_REGISTRY``.

    All commissioning phases are shown by default. Pass ``visible_phases`` to
    restrict which phases appear, preserving registry order.
    """
    requested_phases = set(visible_phases or DEFAULT_BETA_VISIBLE_PHASES)

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
