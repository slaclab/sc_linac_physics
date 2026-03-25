"""Progress indicator helpers for the multi-phase commissioning container."""

from sc_linac_physics.applications.rf_commissioning import CommissioningPhase
from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    PHASE_REGISTRY,
)


def build_progress_phases() -> list[tuple[str, CommissioningPhase]]:
    """Return ordered ``(label, phase)`` tuples for the progress indicator."""
    return [
        (PHASE_REGISTRY[phase].progress_label, phase)
        for phase in CommissioningPhase.get_phase_order()
    ]
