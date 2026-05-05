"""Tests for RF commissioning phase tab selection."""

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
)
from sc_linac_physics.applications.rf_commissioning.ui.container.phase_specs import (
    build_default_phase_specs,
)


def test_default_phase_specs_hide_placeholder_tabs_for_beta() -> None:
    specs = build_default_phase_specs()

    assert [spec.phase for spec in specs] == [CommissioningPhase.PIEZO_PRE_RF]
    assert [spec.title for spec in specs] == ["Piezo Pre-RF"]


def test_default_phase_specs_can_include_all_placeholder_tabs() -> None:
    specs = build_default_phase_specs(include_placeholder_phases=True)

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
