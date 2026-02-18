"""Tests for RF commissioning data models."""

from datetime import datetime

from sc_linac_physics.applications.rf_commissioning import (
    CommissioningPhase,
    PhaseStatus,
    PhaseCheckpoint,
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


class TestPhaseCheckpoint:
    """Test PhaseCheckpoint data model."""

    def test_default_initialization(self):
        """Test checkpoint with defaults."""
        checkpoint = PhaseCheckpoint()

        assert isinstance(checkpoint.timestamp, datetime)
        assert checkpoint.operator == ""
        assert checkpoint.notes == ""
        assert checkpoint.measurements == {}
        assert checkpoint.error_message == ""

    def test_with_data(self):
        """Test checkpoint with data."""
        timestamp = datetime(2024, 1, 15, 10, 30)
        measurements = {"detune_hz": 1000.0, "gradient_mv": 16.5}

        checkpoint = PhaseCheckpoint(
            timestamp=timestamp,
            operator="jdoe",
            notes="Completed successfully",
            measurements=measurements,
        )

        assert checkpoint.timestamp == timestamp
        assert checkpoint.operator == "jdoe"
        assert checkpoint.notes == "Completed successfully"
        assert checkpoint.measurements == measurements
        assert checkpoint.error_message == ""

    def test_to_dict(self):
        """Test serialization to dictionary."""
        timestamp = datetime(2024, 1, 15, 10, 30)
        measurements = {"detune_hz": 1000.0}

        checkpoint = PhaseCheckpoint(
            timestamp=timestamp,
            operator="jdoe",
            notes="Test note",
            measurements=measurements,
            error_message="",
        )

        result = checkpoint.to_dict()

        assert result["timestamp"] == "2024-01-15T10:30:00"
        assert result["operator"] == "jdoe"
        assert result["notes"] == "Test note"
        assert result["measurements"] == measurements
        assert result["error_message"] == ""

    def test_with_error(self):
        """Test checkpoint with error message."""
        checkpoint = PhaseCheckpoint(
            operator="jdoe",
            error_message="SSA tripped during ramp",
        )

        assert checkpoint.error_message == "SSA tripped during ramp"

        result = checkpoint.to_dict()
        assert result["error_message"] == "SSA tripped during ramp"
