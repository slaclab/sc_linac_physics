"""Tests for RF commissioning data models."""

from datetime import datetime

import pytest

from sc_linac_physics.applications.rf_commissioning import (
    CommissioningPhase,
    PhaseStatus,
    PhaseCheckpoint,
    PiezoPreRFCheck,
    ColdLandingData,
    SSACharacterization,
    CavityCharacterization,
    PiezoWithRFTest,
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


class TestPiezoPreRFCheck:
    """Test PiezoPreRFCheck data model."""

    def test_default_initialization(self):
        """Test default values."""
        check = PiezoPreRFCheck()

        assert check.capacitance_a is None
        assert check.capacitance_b is None
        assert check.channel_a_passed is False
        assert check.channel_b_passed is False
        assert isinstance(check.timestamp, datetime)
        assert check.notes == ""

    def test_both_channels_pass(self):
        """Test when both channels pass."""
        check = PiezoPreRFCheck(
            capacitance_a=1.5e-9,
            capacitance_b=1.6e-9,
            channel_a_passed=True,
            channel_b_passed=True,
        )

        assert check.passed is True
        assert "PASS" in check.status_description
        assert "1.500e-09F" in check.status_description
        assert "1.600e-09F" in check.status_description

    def test_channel_a_fails(self):
        """Test when channel A fails."""
        check = PiezoPreRFCheck(
            capacitance_a=5.0e-9,
            capacitance_b=1.6e-9,
            channel_a_passed=False,
            channel_b_passed=True,
        )

        assert check.passed is False
        assert "FAIL" in check.status_description
        assert "Ch A" in check.status_description

    def test_channel_b_fails(self):
        """Test when channel B fails."""
        check = PiezoPreRFCheck(
            capacitance_a=1.5e-9,
            capacitance_b=5.0e-9,
            channel_a_passed=True,
            channel_b_passed=False,
        )

        assert check.passed is False
        assert "FAIL" in check.status_description
        assert "Ch B" in check.status_description

    def test_both_channels_fail(self):
        """Test when both channels fail."""
        check = PiezoPreRFCheck(
            capacitance_a=5.0e-9,
            capacitance_b=6.0e-9,
            channel_a_passed=False,
            channel_b_passed=False,
        )

        assert check.passed is False
        assert "FAIL" in check.status_description
        assert "Ch A" in check.status_description
        assert "Ch B" in check.status_description

    def test_to_dict(self):
        """Test serialization."""
        timestamp = datetime(2024, 1, 15, 10, 30)
        check = PiezoPreRFCheck(
            capacitance_a=1.5e-9,
            capacitance_b=1.6e-9,
            channel_a_passed=True,
            channel_b_passed=True,
            timestamp=timestamp,
            notes="Good test",
        )

        result = check.to_dict()

        assert result["capacitance_a"] == 1.5e-9
        assert result["capacitance_b"] == 1.6e-9
        assert result["channel_a_passed"] is True
        assert result["channel_b_passed"] is True
        assert result["passed"] is True
        assert "PASS" in result["status_description"]
        assert result["timestamp"] == "2024-01-15T10:30:00"
        assert result["notes"] == "Good test"


class TestColdLandingData:
    """Test ColdLandingData data model."""

    def test_default_initialization(self):
        """Test default values."""
        data = ColdLandingData()

        assert data.initial_detune_hz is None
        assert data.initial_timestamp is None
        assert data.steps_to_resonance is None
        assert data.final_detune_hz is None
        assert data.final_timestamp is None
        assert data.notes == ""

    def test_detune_conversion(self):
        """Test Hz to kHz conversion."""
        data = ColdLandingData(
            initial_detune_hz=15000.0,
            final_detune_hz=500.0,
        )

        assert data.initial_detune_khz == 15.0
        assert data.final_detune_khz == 0.5

    def test_detune_conversion_none(self):
        """Test conversion when values are None."""
        data = ColdLandingData()

        assert data.initial_detune_khz is None
        assert data.final_detune_khz is None

    def test_is_complete_true(self):
        """Test completion when all required data present."""
        data = ColdLandingData(
            initial_detune_hz=15000.0,
            steps_to_resonance=50,
            final_detune_hz=500.0,
        )

        assert data.is_complete is True

    def test_is_complete_missing_initial(self):
        """Test incomplete when missing initial detune."""
        data = ColdLandingData(
            steps_to_resonance=50,
            final_detune_hz=500.0,
        )

        assert data.is_complete is False

    def test_is_complete_missing_steps(self):
        """Test incomplete when missing steps."""
        data = ColdLandingData(
            initial_detune_hz=15000.0,
            final_detune_hz=500.0,
        )

        assert data.is_complete is False

    def test_is_complete_missing_final(self):
        """Test incomplete when missing final detune."""
        data = ColdLandingData(
            initial_detune_hz=15000.0,
            steps_to_resonance=50,
        )

        assert data.is_complete is False

    def test_to_dict(self):
        """Test serialization."""
        initial_time = datetime(2024, 1, 15, 10, 30)
        final_time = datetime(2024, 1, 15, 11, 0)

        data = ColdLandingData(
            initial_detune_hz=15000.0,
            initial_timestamp=initial_time,
            steps_to_resonance=50,
            final_detune_hz=500.0,
            final_timestamp=final_time,
            notes="Tuned successfully",
        )

        result = data.to_dict()

        assert result["initial_detune_hz"] == 15000.0
        assert result["initial_detune_khz"] == 15.0
        assert result["initial_timestamp"] == "2024-01-15T10:30:00"
        assert result["steps_to_resonance"] == 50
        assert result["final_detune_hz"] == 500.0
        assert result["final_detune_khz"] == 0.5
        assert result["final_timestamp"] == "2024-01-15T11:00:00"
        assert result["is_complete"] is True
        assert result["notes"] == "Tuned successfully"

    def test_to_dict_with_none_timestamps(self):
        """Test serialization with None timestamps."""
        data = ColdLandingData(
            initial_detune_hz=15000.0,
        )

        result = data.to_dict()

        assert result["initial_timestamp"] is None
        assert result["final_timestamp"] is None


class TestSSACharacterization:
    """Test SSACharacterization data model."""

    def test_default_initialization(self):
        """Test default values."""
        ssa = SSACharacterization()

        assert ssa.max_drive is None
        assert ssa.initial_drive is None
        assert ssa.num_attempts == 0
        assert isinstance(ssa.timestamp, datetime)
        assert ssa.notes == ""

    def test_drive_percent_conversion(self):
        """Test drive to percentage conversion."""
        ssa = SSACharacterization(
            max_drive=0.65,
            initial_drive=0.8,
        )

        assert ssa.max_drive_percent == 65.0
        assert ssa.initial_drive_percent == 80.0

    def test_drive_percent_none(self):
        """Test percentage conversion with None values."""
        ssa = SSACharacterization()

        assert ssa.max_drive_percent is None
        assert ssa.initial_drive_percent is None

    def test_drive_reduction(self):
        """Test drive reduction calculation."""
        ssa = SSACharacterization(
            max_drive=0.65,
            initial_drive=0.8,
        )

        assert ssa.drive_reduction == pytest.approx(0.15)

    def test_drive_reduction_none(self):
        """Test drive reduction with None values."""
        ssa = SSACharacterization(max_drive=0.65)
        assert ssa.drive_reduction is None

        ssa = SSACharacterization(initial_drive=0.8)
        assert ssa.drive_reduction is None

        ssa = SSACharacterization()
        assert ssa.drive_reduction is None

    def test_succeeded_first_try(self):
        """Test first attempt success detection."""
        ssa = SSACharacterization(
            max_drive=0.65,
            num_attempts=1,
        )

        assert ssa.succeeded_first_try is True

    def test_multiple_attempts(self):
        """Test multiple attempts."""
        ssa = SSACharacterization(
            max_drive=0.65,
            num_attempts=3,
        )

        assert ssa.succeeded_first_try is False

    def test_is_complete_true(self):
        """Test completion when max_drive is set."""
        ssa = SSACharacterization(max_drive=0.65)

        assert ssa.is_complete is True

    def test_is_complete_false(self):
        """Test incomplete when max_drive is None."""
        ssa = SSACharacterization()

        assert ssa.is_complete is False

    def test_to_dict(self):
        """Test serialization."""
        timestamp = datetime(2024, 1, 15, 10, 30)
        ssa = SSACharacterization(
            max_drive=0.65,
            initial_drive=0.8,
            num_attempts=2,
            timestamp=timestamp,
            notes="Required adjustment",
        )

        result = ssa.to_dict()

        assert result["max_drive"] == 0.65
        assert result["max_drive_percent"] == 65.0
        assert result["initial_drive"] == 0.8
        assert result["initial_drive_percent"] == 80.0
        assert result["num_attempts"] == 2
        assert result["drive_reduction"] == pytest.approx(0.15)
        assert result["succeeded_first_try"] is False
        assert result["is_complete"] is True
        assert result["timestamp"] == "2024-01-15T10:30:00"
        assert result["notes"] == "Required adjustment"

    def test_to_dict_incomplete(self):
        """Test serialization when incomplete."""
        ssa = SSACharacterization(num_attempts=1)

        result = ssa.to_dict()

        assert result["max_drive"] is None
        assert result["max_drive_percent"] is None
        assert result["is_complete"] is False


class TestCavityCharacterization:
    """Test CavityCharacterization data model."""

    def test_default_initialization(self):
        """Test default values."""
        char = CavityCharacterization()

        assert char.loaded_q is None
        assert char.probe_q is None
        assert char.scale_factor is None
        assert isinstance(char.timestamp, datetime)
        assert char.notes == ""

    def test_with_data(self):
        """Test with all data."""
        char = CavityCharacterization(
            loaded_q=3.0e7,
            probe_q=1.5e9,
            scale_factor=2.5,
        )

        assert char.loaded_q == 3.0e7
        assert char.probe_q == 1.5e9
        assert char.scale_factor == 2.5

    def test_is_complete_true(self):
        """Test completion when required fields set."""
        char = CavityCharacterization(
            loaded_q=3.0e7,
            scale_factor=2.5,
        )

        assert char.is_complete is True

    def test_is_complete_without_probe_q(self):
        """Test completion without probe_q (optional)."""
        char = CavityCharacterization(
            loaded_q=3.0e7,
            scale_factor=2.5,
        )

        assert char.is_complete is True

    def test_is_complete_missing_loaded_q(self):
        """Test incomplete when missing loaded_q."""
        char = CavityCharacterization(
            scale_factor=2.5,
        )

        assert char.is_complete is False

    def test_is_complete_missing_scale_factor(self):
        """Test incomplete when missing scale_factor."""
        char = CavityCharacterization(
            loaded_q=3.0e7,
        )

        assert char.is_complete is False

    def test_is_complete_all_none(self):
        """Test incomplete when all None."""
        char = CavityCharacterization()

        assert char.is_complete is False

    def test_to_dict(self):
        """Test serialization."""
        timestamp = datetime(2024, 1, 15, 10, 30)
        char = CavityCharacterization(
            loaded_q=3.0e7,
            probe_q=1.5e9,
            scale_factor=2.5,
            timestamp=timestamp,
            notes="Excellent cavity",
        )

        result = char.to_dict()

        assert result["loaded_q"] == 3.0e7
        assert result["probe_q"] == 1.5e9
        assert result["scale_factor"] == 2.5
        assert result["is_complete"] is True
        assert result["timestamp"] == "2024-01-15T10:30:00"
        assert result["notes"] == "Excellent cavity"

    def test_to_dict_incomplete(self):
        """Test serialization when incomplete."""
        char = CavityCharacterization(loaded_q=3.0e7)

        result = char.to_dict()

        assert result["loaded_q"] == 3.0e7
        assert result["probe_q"] is None
        assert result["scale_factor"] is None
        assert result["is_complete"] is False


class TestPiezoWithRFTest:
    """Test PiezoWithRFTest data model."""

    def test_default_initialization(self):
        """Test default values."""
        test = PiezoWithRFTest()

        assert test.amplifier_gain_a is None
        assert test.amplifier_gain_b is None
        assert test.detune_gain is None
        assert isinstance(test.timestamp, datetime)
        assert test.notes == ""

    def test_with_data(self):
        """Test with all measurements."""
        test = PiezoWithRFTest(
            amplifier_gain_a=1.2,
            amplifier_gain_b=1.3,
            detune_gain=0.95,
        )

        assert test.amplifier_gain_a == 1.2
        assert test.amplifier_gain_b == 1.3
        assert test.detune_gain == 0.95

    def test_is_complete_true(self):
        """Test completion when all measurements present."""
        test = PiezoWithRFTest(
            amplifier_gain_a=1.2,
            amplifier_gain_b=1.3,
            detune_gain=0.95,
        )

        assert test.is_complete is True

    def test_is_complete_missing_amp_a(self):
        """Test incomplete when missing amplifier_gain_a."""
        test = PiezoWithRFTest(
            amplifier_gain_b=1.3,
            detune_gain=0.95,
        )

        assert test.is_complete is False

    def test_is_complete_missing_amp_b(self):
        """Test incomplete when missing amplifier_gain_b."""
        test = PiezoWithRFTest(
            amplifier_gain_a=1.2,
            detune_gain=0.95,
        )

        assert test.is_complete is False

    def test_is_complete_missing_detune(self):
        """Test incomplete when missing detune_gain."""
        test = PiezoWithRFTest(
            amplifier_gain_a=1.2,
            amplifier_gain_b=1.3,
        )

        assert test.is_complete is False

    def test_is_complete_all_none(self):
        """Test incomplete when all None."""
        test = PiezoWithRFTest()

        assert test.is_complete is False

    def test_to_dict(self):
        """Test serialization."""
        timestamp = datetime(2024, 1, 15, 10, 30)
        test = PiezoWithRFTest(
            amplifier_gain_a=1.2,
            amplifier_gain_b=1.3,
            detune_gain=0.95,
            timestamp=timestamp,
            notes="Good tuner response",
        )

        result = test.to_dict()

        assert result["amplifier_gain_a"] == 1.2
        assert result["amplifier_gain_b"] == 1.3
        assert result["detune_gain"] == 0.95
        assert result["is_complete"] is True
        assert result["timestamp"] == "2024-01-15T10:30:00"
        assert result["notes"] == "Good tuner response"

    def test_to_dict_incomplete(self):
        """Test serialization when incomplete."""
        test = PiezoWithRFTest(amplifier_gain_a=1.2)

        result = test.to_dict()

        assert result["amplifier_gain_a"] == 1.2
        assert result["amplifier_gain_b"] is None
        assert result["detune_gain"] is None
        assert result["is_complete"] is False
