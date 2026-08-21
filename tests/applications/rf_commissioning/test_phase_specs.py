"""Tests for RF commissioning phase tab selection."""

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
)
from sc_linac_physics.applications.rf_commissioning.ui.container.phase_specs import (
    build_default_phase_specs,
)


def test_default_phase_specs_shows_all_phases() -> None:
    specs = build_default_phase_specs()

    phases = [spec.phase for spec in specs]
    assert CommissioningPhase.PIEZO_PRE_RF in phases
    assert CommissioningPhase.SSA_CHAR in phases
    assert CommissioningPhase.FREQUENCY_TUNING in phases
    assert len(phases) == len(
        [p for p in CommissioningPhase if p != CommissioningPhase.COMPLETE]
    )


def test_default_phase_specs_accept_custom_visible_phase_subset() -> None:
    specs = build_default_phase_specs(
        visible_phases=(
            CommissioningPhase.FREQUENCY_TUNING,
            CommissioningPhase.PIEZO_PRE_RF,
        )
    )

    assert [spec.phase for spec in specs] == [
        CommissioningPhase.PIEZO_PRE_RF,
        CommissioningPhase.FREQUENCY_TUNING,
    ]
