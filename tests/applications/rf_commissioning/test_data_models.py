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
    HighPowerRampData,
    CommissioningRecord,
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
    """Tests for PhaseCheckpoint dataclass."""

    def test_default_initialization(self):
        """Test checkpoint with defaults."""
        # UPDATED: PhaseCheckpoint now requires phase, timestamp, operator, step_name, success
        checkpoint = PhaseCheckpoint(
            phase=CommissioningPhase.COLD_LANDING,
            timestamp=datetime.now(),
            operator="TestOperator",
            step_name="test_step",
            success=True,
        )

        assert checkpoint.phase == CommissioningPhase.COLD_LANDING  # ADD
        assert checkpoint.operator == "TestOperator"
        assert checkpoint.step_name == "test_step"
        assert checkpoint.success is True
        assert checkpoint.notes == ""
        assert checkpoint.measurements == {}
        assert checkpoint.error_message is None

    def test_initialization_with_values(self):
        """Test checkpoint with all values."""
        timestamp = datetime.now()
        measurements = {"voltage": 12.5, "current": 2.3}

        checkpoint = PhaseCheckpoint(
            phase=CommissioningPhase.SSA_CAL,  # ADD
            timestamp=timestamp,
            operator="TestOperator",
            step_name="calibration",
            success=True,
            notes="Calibration successful",
            measurements=measurements,
            error_message=None,
        )

        assert checkpoint.phase == CommissioningPhase.SSA_CAL  # ADD
        assert checkpoint.timestamp == timestamp
        assert checkpoint.operator == "TestOperator"
        assert checkpoint.step_name == "calibration"
        assert checkpoint.success is True
        assert checkpoint.notes == "Calibration successful"
        assert checkpoint.measurements == measurements
        assert checkpoint.error_message is None

    def test_checkpoint_with_error(self):
        """Test checkpoint recording an error."""
        checkpoint = PhaseCheckpoint(
            phase=CommissioningPhase.COLD_LANDING,  # ADD
            timestamp=datetime.now(),
            operator="TestOperator",
            step_name="landing",
            success=False,
            notes="Failed to reach resonance",
            error_message="Timeout after 30 seconds",
        )

        assert checkpoint.phase == CommissioningPhase.COLD_LANDING  # ADD
        assert checkpoint.success is False
        assert checkpoint.error_message == "Timeout after 30 seconds"

    def test_to_dict(self):
        """Test serialization to dictionary."""
        timestamp = datetime(2024, 1, 15, 10, 30, 0)
        measurements = {"detune_hz": -143766}

        checkpoint = PhaseCheckpoint(
            phase=CommissioningPhase.COLD_LANDING,  # ADD
            timestamp=timestamp,
            operator="TestOperator",
            step_name="measure_detune",
            success=True,
            notes="Initial measurement",
            measurements=measurements,
        )

        result = checkpoint.to_dict()

        assert result["phase"] == "cold_landing"  # ADD
        assert result["timestamp"] == "2024-01-15T10:30:00"
        assert result["operator"] == "TestOperator"
        assert result["step_name"] == "measure_detune"
        assert result["success"] is True
        assert result["notes"] == "Initial measurement"
        assert result["measurements"] == measurements
        assert result["error_message"] is None


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


class TestHighPowerRampData:
    """Test HighPowerRampData data model."""

    def test_default_initialization(self):
        """Test default values."""
        ramp = HighPowerRampData()

        assert ramp.final_amplitude is None
        assert ramp.one_hour_complete is False
        assert isinstance(ramp.timestamp, datetime)
        assert ramp.notes == ""

    def test_with_data(self):
        """Test with complete data."""
        ramp = HighPowerRampData(
            final_amplitude=16.5,
            one_hour_complete=True,
        )

        assert ramp.final_amplitude == 16.5
        assert ramp.one_hour_complete is True

    def test_is_complete_true(self):
        """Test completion when both requirements met."""
        ramp = HighPowerRampData(
            final_amplitude=16.5,
            one_hour_complete=True,
        )

        assert ramp.is_complete is True

    def test_is_complete_missing_amplitude(self):
        """Test incomplete when missing final_amplitude."""
        ramp = HighPowerRampData(
            one_hour_complete=True,
        )

        assert ramp.is_complete is False

    def test_is_complete_hour_not_done(self):
        """Test incomplete when one hour not complete."""
        ramp = HighPowerRampData(
            final_amplitude=16.5,
            one_hour_complete=False,
        )

        assert ramp.is_complete is False

    def test_is_complete_both_missing(self):
        """Test incomplete when both missing."""
        ramp = HighPowerRampData()

        assert ramp.is_complete is False

    def test_to_dict(self):
        """Test serialization."""
        timestamp = datetime(2024, 1, 15, 10, 30)
        ramp = HighPowerRampData(
            final_amplitude=16.5,
            one_hour_complete=True,
            timestamp=timestamp,
            notes="Successful ramp",
        )

        result = ramp.to_dict()

        assert result["final_amplitude"] == 16.5
        assert result["one_hour_complete"] is True
        assert result["is_complete"] is True
        assert result["timestamp"] == "2024-01-15T10:30:00"
        assert result["notes"] == "Successful ramp"

    def test_to_dict_incomplete(self):
        """Test serialization when incomplete."""
        ramp = HighPowerRampData(final_amplitude=16.5)

        result = ramp.to_dict()

        assert result["final_amplitude"] == 16.5
        assert result["one_hour_complete"] is False
        assert result["is_complete"] is False


class TestCommissioningRecord:
    """Test CommissioningRecord data model."""

    def test_add_and_get_checkpoint(self):
        """Test adding and retrieving checkpoints."""
        record = CommissioningRecord(
            cavity_name="L1B_CM02_CAV3", cryomodule="02"
        )

        checkpoint = PhaseCheckpoint(
            phase=CommissioningPhase.COLD_LANDING,  # ADD
            timestamp=datetime.now(),
            operator="TestOperator",
            step_name="landing_complete",
            success=True,
            notes="Successfully landed",
        )

        # UPDATED API:
        record.add_checkpoint(checkpoint)  # CHANGED: removed phase argument

        # UPDATED API:
        retrieved_checkpoints = record.get_checkpoints(
            CommissioningPhase.COLD_LANDING
        )
        assert len(retrieved_checkpoints) == 1
        assert retrieved_checkpoints[0].step_name == "landing_complete"

        # Test get_latest_checkpoint
        latest = record.get_latest_checkpoint(CommissioningPhase.COLD_LANDING)
        assert latest is not None
        assert latest.step_name == "landing_complete"

    def test_multiple_checkpoints_per_phase(self):
        """Test that multiple checkpoints can be added for the same phase."""
        record = CommissioningRecord(
            cavity_name="L1B_CM02_CAV3", cryomodule="02"
        )

        # Add multiple checkpoints for the same phase
        checkpoint1 = PhaseCheckpoint(
            phase=CommissioningPhase.COLD_LANDING,
            timestamp=datetime.now(),
            operator="TestOperator",
            step_name="step1",
            success=True,
        )

        checkpoint2 = PhaseCheckpoint(
            phase=CommissioningPhase.COLD_LANDING,
            timestamp=datetime.now(),
            operator="TestOperator",
            step_name="step2",
            success=True,
        )

        record.add_checkpoint(checkpoint1)
        record.add_checkpoint(checkpoint2)

        # Get all checkpoints for the phase
        checkpoints = record.get_checkpoints(CommissioningPhase.COLD_LANDING)
        assert len(checkpoints) == 2
        assert checkpoints[0].step_name == "step1"
        assert checkpoints[1].step_name == "step2"

        # Get latest checkpoint
        latest = record.get_latest_checkpoint(CommissioningPhase.COLD_LANDING)
        assert latest.step_name == "step2"

    def test_get_checkpoints_all_phases(self):
        """Test getting all checkpoints across all phases."""
        record = CommissioningRecord(
            cavity_name="L1B_CM02_CAV3", cryomodule="02"
        )

        checkpoint1 = PhaseCheckpoint(
            phase=CommissioningPhase.COLD_LANDING,
            timestamp=datetime.now(),
            operator="TestOperator",
            step_name="landing",
            success=True,
        )

        checkpoint2 = PhaseCheckpoint(
            phase=CommissioningPhase.SSA_CAL,
            timestamp=datetime.now(),
            operator="TestOperator",
            step_name="calibration",
            success=True,
        )

        record.add_checkpoint(checkpoint1)
        record.add_checkpoint(checkpoint2)

        # Get all checkpoints (no phase filter)
        all_checkpoints = record.get_checkpoints()
        assert len(all_checkpoints) == 2
        assert all_checkpoints[0].phase == CommissioningPhase.COLD_LANDING
        assert all_checkpoints[1].phase == CommissioningPhase.SSA_CAL

    def test_get_checkpoints_empty(self):
        """Test getting checkpoints when none exist."""
        record = CommissioningRecord(
            cavity_name="L1B_CM02_CAV3", cryomodule="02"
        )

        checkpoints = record.get_checkpoints(CommissioningPhase.COLD_LANDING)
        assert len(checkpoints) == 0

        latest = record.get_latest_checkpoint(CommissioningPhase.COLD_LANDING)
        assert latest is None

    def test_to_dict_with_checkpoints(self):
        """Test serialization with phase history."""
        record = CommissioningRecord(
            cavity_name="L1B_CM02_CAV3", cryomodule="02"
        )

        checkpoint = PhaseCheckpoint(
            phase=CommissioningPhase.COLD_LANDING,  # ADD
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            operator="TestOperator",
            step_name="test_step",
            success=True,
            notes="Test checkpoint",
        )

        record.add_checkpoint(checkpoint)  # CHANGED: removed phase argument

        result = record.to_dict()

        # UPDATED: phase_history is now a list
        assert isinstance(result["phase_history"], list)
        assert len(result["phase_history"]) == 1
        assert result["phase_history"][0]["phase"] == "cold_landing"
        assert result["phase_history"][0]["step_name"] == "test_step"

    def test_to_dict_basic(self):
        """Test basic serialization."""
        start = datetime(2024, 1, 15, 10, 0)
        record = CommissioningRecord(
            cavity_name="CM01_CAV1",
            cryomodule="CM01",
            start_time=start,
        )

        result = record.to_dict()

        assert result["cavity_name"] == "CM01_CAV1"
        assert result["cryomodule"] == "CM01"
        assert result["start_time"] == "2024-01-15T10:00:00"
        assert result["end_time"] is None
        assert result["current_phase"] == "pre_checks"
        assert result["overall_status"] == "in_progress"
        assert result["is_complete"] is False

        # All phase data should be None
        assert result["piezo_pre_rf"] is None
        assert result["cold_landing"] is None
        assert result["ssa_characterization"] is None
        assert result["cavity_characterization"] is None
        assert result["piezo_with_rf"] is None
        assert result["high_power_ramp"] is None

    def test_to_dict_with_end_time(self):
        """Test serialization with end time."""
        start = datetime(2024, 1, 15, 10, 0)
        end = datetime(2024, 1, 15, 14, 30)

        record = CommissioningRecord(
            cavity_name="CM01_CAV1",
            cryomodule="CM01",
            start_time=start,
            end_time=end,
            current_phase=CommissioningPhase.COMPLETE,
            overall_status="complete",
        )

        result = record.to_dict()

        assert result["end_time"] == "2024-01-15T14:30:00"
        assert result["elapsed_time_hours"] == pytest.approx(4.5)
        assert result["current_phase"] == "complete"
        assert result["overall_status"] == "complete"
        assert result["is_complete"] is True

    def test_to_dict_with_data(self):
        """Test serialization with phase data."""
        record = CommissioningRecord(
            cavity_name="CM01_CAV1",
            cryomodule="CM01",
        )

        record.piezo_pre_rf = PiezoPreRFCheck(
            capacitance_a=1.5e-9,
            capacitance_b=1.6e-9,
            channel_a_passed=True,
            channel_b_passed=True,
        )
        record.cold_landing = ColdLandingData(
            initial_detune_hz=15000.0,
            steps_to_resonance=50,
            final_detune_hz=500.0,
        )

        result = record.to_dict()

        # Check nested data serialized correctly
        assert result["piezo_pre_rf"] is not None
        assert result["piezo_pre_rf"]["capacitance_a"] == 1.5e-9
        assert result["piezo_pre_rf"]["passed"] is True

        assert result["cold_landing"] is not None
        assert result["cold_landing"]["initial_detune_hz"] == 15000.0
        assert result["cold_landing"]["steps_to_resonance"] == 50
        assert result["cold_landing"]["is_complete"] is True

    def test_to_dict_with_phase_status(self):
        """Test serialization includes phase status."""
        record = CommissioningRecord(
            cavity_name="CM01_CAV1",
            cryomodule="CM01",
        )

        record.set_phase_status(
            CommissioningPhase.COLD_LANDING, PhaseStatus.COMPLETE
        )
        record.set_phase_status(
            CommissioningPhase.SSA_CAL, PhaseStatus.IN_PROGRESS
        )

        result = record.to_dict()

        assert "phase_status" in result
        assert result["phase_status"]["pre_checks"] == "in_progress"
        assert result["phase_status"]["cold_landing"] == "complete"
        assert result["phase_status"]["ssa_cal"] == "in_progress"

    def test_store_piezo_pre_rf(self):
        """Test storing piezo pre-RF check data."""
        record = CommissioningRecord(
            cavity_name="CM01_CAV1",
            cryomodule="CM01",
        )

        piezo_check = PiezoPreRFCheck(
            capacitance_a=1.5e-9,
            capacitance_b=1.6e-9,
            channel_a_passed=True,
            channel_b_passed=True,
        )

        record.piezo_pre_rf = piezo_check

        assert record.piezo_pre_rf is not None
        assert record.piezo_pre_rf.capacitance_a == 1.5e-9
        assert record.piezo_pre_rf.passed is True

    def test_store_cold_landing(self):
        """Test storing cold landing data."""
        record = CommissioningRecord(
            cavity_name="CM01_CAV1",
            cryomodule="CM01",
        )

        cold_landing = ColdLandingData(
            initial_detune_hz=15000.0,
            steps_to_resonance=50,
            final_detune_hz=500.0,
        )

        record.cold_landing = cold_landing

        assert record.cold_landing is not None
        assert record.cold_landing.initial_detune_khz == 15.0
        assert record.cold_landing.is_complete is True

    def test_store_ssa_characterization(self):
        """Test storing SSA characterization data."""
        record = CommissioningRecord(
            cavity_name="CM01_CAV1",
            cryomodule="CM01",
        )

        ssa_char = SSACharacterization(
            max_drive=0.65,
            initial_drive=0.8,
            num_attempts=1,
        )

        record.ssa_char = ssa_char

        assert record.ssa_char is not None
        assert record.ssa_char.max_drive_percent == 65.0
        assert record.ssa_char.succeeded_first_try is True

    def test_store_cavity_characterization(self):
        """Test storing cavity characterization data."""
        record = CommissioningRecord(
            cavity_name="CM01_CAV1",
            cryomodule="CM01",
        )

        cavity_char = CavityCharacterization(
            loaded_q=3.0e7,
            probe_q=1.5e9,
            scale_factor=2.5,
        )

        record.cavity_char = cavity_char

        assert record.cavity_char is not None
        assert record.cavity_char.loaded_q == 3.0e7
        assert record.cavity_char.is_complete is True

    def test_store_piezo_with_rf(self):
        """Test storing piezo with-RF test data."""
        record = CommissioningRecord(
            cavity_name="CM01_CAV1",
            cryomodule="CM01",
        )

        piezo_rf = PiezoWithRFTest(
            amplifier_gain_a=1.2,
            amplifier_gain_b=1.3,
            detune_gain=0.95,
        )

        record.piezo_with_rf = piezo_rf

        assert record.piezo_with_rf is not None
        assert record.piezo_with_rf.amplifier_gain_a == 1.2
        assert record.piezo_with_rf.is_complete is True

    def test_store_high_power_ramp(self):
        """Test storing high power ramp data."""
        record = CommissioningRecord(
            cavity_name="CM01_CAV1",
            cryomodule="CM01",
        )

        high_power = HighPowerRampData(
            final_amplitude=16.5,
            one_hour_complete=True,
        )

        record.high_power = high_power

        assert record.high_power is not None
        assert record.high_power.final_amplitude == 16.5
        assert record.high_power.is_complete is True

    def test_store_all_data(self):
        """Test storing all data types together."""
        record = CommissioningRecord(
            cavity_name="CM01_CAV1",
            cryomodule="CM01",
        )

        record.piezo_pre_rf = PiezoPreRFCheck(
            capacitance_a=1.5e-9,
            capacitance_b=1.6e-9,
            channel_a_passed=True,
            channel_b_passed=True,
        )
        record.cold_landing = ColdLandingData(
            initial_detune_hz=15000.0,
            steps_to_resonance=50,
            final_detune_hz=500.0,
        )
        record.ssa_char = SSACharacterization(
            max_drive=0.65,
            num_attempts=1,
        )
        record.cavity_char = CavityCharacterization(
            loaded_q=3.0e7,
            scale_factor=2.5,
        )
        record.piezo_with_rf = PiezoWithRFTest(
            amplifier_gain_a=1.2,
            amplifier_gain_b=1.3,
            detune_gain=0.95,
        )
        record.high_power = HighPowerRampData(
            final_amplitude=16.5,
            one_hour_complete=True,
        )

        # Verify all data stored
        assert record.piezo_pre_rf.passed is True
        assert record.cold_landing.is_complete is True
        assert record.ssa_char.is_complete is True
        assert record.cavity_char.is_complete is True
        assert record.piezo_with_rf.is_complete is True
        assert record.high_power.is_complete is True

    def test_set_phase_status(self):
        """Test setting phase status."""
        record = CommissioningRecord(
            cavity_name="CM01_CAV1",
            cryomodule="CM01",
        )

        record.set_phase_status(
            CommissioningPhase.COLD_LANDING, PhaseStatus.IN_PROGRESS
        )
        assert (
            record.get_phase_status(CommissioningPhase.COLD_LANDING)
            == PhaseStatus.IN_PROGRESS
        )

        record.set_phase_status(
            CommissioningPhase.COLD_LANDING, PhaseStatus.COMPLETE
        )
        assert (
            record.get_phase_status(CommissioningPhase.COLD_LANDING)
            == PhaseStatus.COMPLETE
        )

    def test_phase_status_initialization(self):
        """Test phase status initialized correctly."""
        record = CommissioningRecord(
            cavity_name="CM01_CAV1",
            cryomodule="CM01",
        )

        # PRE_CHECKS should start as IN_PROGRESS
        assert (
            record.get_phase_status(CommissioningPhase.PRE_CHECKS)
            == PhaseStatus.IN_PROGRESS
        )

        # All others should be NOT_STARTED
        for phase in CommissioningPhase:
            if phase != CommissioningPhase.PRE_CHECKS:
                assert record.get_phase_status(phase) == PhaseStatus.NOT_STARTED

    def test_is_complete_false_initially(self):
        """Test record is not complete initially."""
        record = CommissioningRecord(
            cavity_name="CM01_CAV1",
            cryomodule="CM01",
        )

        assert record.is_complete is False

    def test_is_complete_true_when_complete(self):
        """Test record is complete when phase is COMPLETE."""
        record = CommissioningRecord(
            cavity_name="CM01_CAV1",
            cryomodule="CM01",
            current_phase=CommissioningPhase.COMPLETE,
        )

        assert record.is_complete is True

    def test_elapsed_time_ongoing(self):
        """Test elapsed time calculation for ongoing commissioning."""
        start = datetime(2024, 1, 15, 10, 0)
        record = CommissioningRecord(
            cavity_name="CM01_CAV1",
            cryomodule="CM01",
            start_time=start,
        )

        # Elapsed time should be positive
        assert record.elapsed_time is not None
        assert record.elapsed_time > 0

    def test_elapsed_time_completed(self):
        """Test elapsed time for completed commissioning."""
        start = datetime(2024, 1, 15, 10, 0)
        end = datetime(2024, 1, 15, 14, 30)  # 4.5 hours later

        record = CommissioningRecord(
            cavity_name="CM01_CAV1",
            cryomodule="CM01",
            start_time=start,
            end_time=end,
        )

        assert record.elapsed_time == pytest.approx(4.5)
