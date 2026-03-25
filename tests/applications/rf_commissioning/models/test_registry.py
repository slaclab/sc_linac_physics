"""Tests for RF commissioning phase registry."""

import pytest

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
)
from sc_linac_physics.applications.rf_commissioning.models.registry import (
    PhaseRegistration,
    create_phase_registry,
    validate_phase_registry_consistency,
)


class TestCreatePhaseRegistry:
    """Tests for registry construction."""

    def test_registry_contains_all_phases(self):
        registry = create_phase_registry()

        assert set(registry) == set(CommissioningPhase)
        assert all(
            isinstance(registration, PhaseRegistration)
            for registration in registry.values()
        )

    def test_complete_phase_is_terminal(self):
        registry = create_phase_registry()

        complete = registry[CommissioningPhase.COMPLETE]
        assert complete.record_attr is None
        assert complete.data_model is None
        assert complete.display_label == "Complete"
        assert complete.progress_label == "Complete"

    def test_registry_key_order_matches_declared_phase_order(self):
        """Guard against drift between declared workflow order and registry."""
        registry = create_phase_registry()

        assert list(registry.keys()) == CommissioningPhase.get_phase_order()


class TestValidatePhaseRegistryConsistency:
    """Tests for registry consistency validation checks."""

    def test_valid_registry_does_not_raise(self):
        registry = create_phase_registry()

        validate_phase_registry_consistency(
            phase_enum=CommissioningPhase,
            phase_order=CommissioningPhase.get_phase_order(),
            phase_registry=registry,
        )

    def test_duplicate_phase_in_order_raises(self):
        registry = create_phase_registry()
        phase_order = CommissioningPhase.get_phase_order() + [
            CommissioningPhase.PIEZO_PRE_RF
        ]

        with pytest.raises(ValueError, match="contains duplicates"):
            validate_phase_registry_consistency(
                phase_enum=CommissioningPhase,
                phase_order=phase_order,
                phase_registry=registry,
            )

    def test_missing_phase_from_order_raises(self):
        registry = create_phase_registry()
        phase_order = [
            phase
            for phase in CommissioningPhase.get_phase_order()
            if phase != CommissioningPhase.PI_MODE
        ]

        with pytest.raises(ValueError, match="is missing phases"):
            validate_phase_registry_consistency(
                phase_enum=CommissioningPhase,
                phase_order=phase_order,
                phase_registry=registry,
            )

    def test_missing_phase_from_registry_raises(self):
        registry = create_phase_registry()
        registry.pop(CommissioningPhase.HIGH_POWER)

        with pytest.raises(ValueError, match="missing phase registrations"):
            validate_phase_registry_consistency(
                phase_enum=CommissioningPhase,
                phase_order=CommissioningPhase.get_phase_order(),
                phase_registry=registry,
            )

    def test_unknown_registry_key_raises(self):
        registry = create_phase_registry()
        registry["not_a_phase"] = registry[CommissioningPhase.PIEZO_PRE_RF]

        with pytest.raises(ValueError, match="non-enum phase keys"):
            validate_phase_registry_consistency(
                phase_enum=CommissioningPhase,
                phase_order=CommissioningPhase.get_phase_order(),
                phase_registry=registry,
            )
