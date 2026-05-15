"""Tests for RF commissioning phase tab selection."""

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
)
from sc_linac_physics.applications.rf_commissioning.ui.container.phase_specs import (
    build_default_phase_specs,
)


def test_default_phase_specs_includes_all_phases() -> None:
    specs = build_default_phase_specs()

    assert [spec.phase for spec in specs] == [
        CommissioningPhase.PIEZO_PRE_RF,
        CommissioningPhase.SSA_CHAR,
        CommissioningPhase.FREQUENCY_TUNING,
        CommissioningPhase.CAVITY_CHAR,
        CommissioningPhase.PIEZO_WITH_RF,
        CommissioningPhase.HIGH_POWER_RAMP,
        CommissioningPhase.MP_PROCESSING,
        CommissioningPhase.ONE_HOUR_RUN,
    ]


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
