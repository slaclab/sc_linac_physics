"""Tests for RF commissioning data models."""

from sc_linac_physics.applications.rf_commissioning import (
    CommissioningPhase,
    PhaseStatus,
)


class TestEnums:
    """Test enum definitions."""

    def test_commissioning_phase_values(self):
        """Test all commissioning phases are defined."""
        expected_phases = [
            "pre_checks",
            "cold_landing",
            "ssa_cal",
            "coarse_tune",
            "characterization",
            "low_power_rf",
            "fine_tune",
            "high_power_ramp",
            "operational",
            "complete",
        ]

        actual_phases = [phase.value for phase in CommissioningPhase]
        assert actual_phases == expected_phases

    def test_phase_status_values(self):
        """Test all phase statuses are defined."""
        expected_statuses = [
            "not_started",
            "in_progress",
            "complete",
            "failed",
            "skipped",
        ]

        actual_statuses = [status.value for status in PhaseStatus]
        assert actual_statuses == expected_statuses

    def test_commissioning_phase_access(self):
        """Test accessing phases by name."""
        assert CommissioningPhase.PRE_CHECKS.value == "pre_checks"
        assert CommissioningPhase.COLD_LANDING.value == "cold_landing"
        assert CommissioningPhase.COMPLETE.value == "complete"

    def test_phase_status_access(self):
        """Test accessing statuses by name."""
        assert PhaseStatus.NOT_STARTED.value == "not_started"
        assert PhaseStatus.IN_PROGRESS.value == "in_progress"
        assert PhaseStatus.COMPLETE.value == "complete"
        assert PhaseStatus.FAILED.value == "failed"
