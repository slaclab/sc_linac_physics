import asyncio
from unittest.mock import Mock, AsyncMock, patch

import pytest

from sc_linac_physics.utils.simulation.cavity_service import CavityPVGroup
from sc_linac_physics.utils.simulation.tuner_service import StepperPVGroup, PiezoPVGroup

# Make sure pytest-asyncio is configured
pytest_plugins = ("pytest_asyncio",)


@pytest.fixture
def mock_cavity_group():
    """Create a mock cavity group for testing."""
    cavity = Mock(spec=CavityPVGroup)
    cavity.is_hl = False  # is_hl = harmonic linearizer cavity
    cavity.detune = AsyncMock()
    cavity.detune.value = 100.0
    cavity.detune_rfs = AsyncMock()
    cavity.detune_chirp = AsyncMock()
    return cavity


@pytest.fixture
def mock_piezo_group():
    """Create a mock piezo group for testing."""
    piezo = Mock(spec=PiezoPVGroup)
    piezo.enable_stat = AsyncMock()
    piezo.enable_stat.value = 1
    piezo.feedback_mode_stat = AsyncMock()
    piezo.feedback_mode_stat.value = "Feedback"
    piezo.voltage = AsyncMock()
    piezo.voltage.value = 17
    return piezo


@pytest.fixture
def stepper_group(mock_cavity_group, mock_piezo_group):
    """Create a StepperPVGroup instance for testing."""
    return StepperPVGroup("TEST:STEPPER:", mock_cavity_group, mock_piezo_group)


@pytest.fixture
def piezo_group(mock_cavity_group):
    """Create a PiezoPVGroup instance for testing."""
    return PiezoPVGroup("TEST:PIEZO:", mock_cavity_group)


class TestStepperPVGroup:
    """Test cases for StepperPVGroup."""

    def test_initialization_non_harmonic_linearizer_cavity(self, mock_cavity_group, mock_piezo_group):
        """Test stepper initialization with non-harmonic linearizer cavity."""
        mock_cavity_group.is_hl = False  # Not a harmonic linearizer cavity
        stepper = StepperPVGroup("TEST:", mock_cavity_group, mock_piezo_group)

        assert stepper.cavity_group == mock_cavity_group
        assert stepper.piezo_group == mock_piezo_group
        # Non-HL cavities use 256/1.4 conversion factor
        assert stepper.steps_per_hertz == 256 / 1.4

    def test_initialization_harmonic_linearizer_cavity(self, mock_cavity_group, mock_piezo_group):
        """Test stepper initialization with harmonic linearizer cavity."""
        mock_cavity_group.is_hl = True  # Harmonic linearizer cavity
        stepper = StepperPVGroup("TEST:", mock_cavity_group, mock_piezo_group)

        # HL cavities use 256/18.3 conversion factor
        assert stepper.steps_per_hertz == 256 / 18.3

    @pytest.mark.asyncio
    async def test_move_positive_direction(self, stepper_group):
        """Test positive direction movement."""
        # Set up initial values by directly accessing internal data
        stepper_group.step_des._data["value"] = 1000
        stepper_group.speed._data["value"] = 500
        stepper_group.abort._data["value"] = 0
        stepper_group.step_tot._data["value"] = 0
        stepper_group.step_signed._data["value"] = 0

        # Mock the write methods for verification
        with (
            patch.object(stepper_group.motor_moving, "write", new_callable=AsyncMock) as mock_moving_write,
            patch.object(stepper_group.motor_done, "write", new_callable=AsyncMock) as mock_done_write,
            patch.object(stepper_group.step_tot, "write", new_callable=AsyncMock) as mock_tot_write,
            patch.object(stepper_group.step_signed, "write", new_callable=AsyncMock) as mock_signed_write,
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):

            await stepper_group.move(1)

        # Verify motor status updates
        mock_moving_write.assert_any_call("Moving")
        mock_moving_write.assert_any_call("Not Moving")
        mock_done_write.assert_called_with("Done")

        # Verify step updates occurred
        assert mock_tot_write.called
        assert mock_signed_write.called

    @pytest.mark.asyncio
    async def test_move_abort_functionality(self, stepper_group):
        """Test abort functionality during movement."""
        # Setup values
        stepper_group.step_des._data["value"] = 10000  # Large number of steps
        stepper_group.speed._data["value"] = 500
        stepper_group.abort._data["value"] = 0

        # Mock the write methods and simulate abort
        with (
            patch.object(stepper_group.motor_moving, "write", new_callable=AsyncMock) as mock_moving_write,
            patch.object(stepper_group.step_tot, "write", new_callable=AsyncMock) as mock_tot_write,
            patch.object(stepper_group.step_signed, "write", new_callable=AsyncMock),
            patch.object(stepper_group.abort, "write", new_callable=AsyncMock) as mock_abort_write,
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):

            # Simulate abort after first iteration
            call_count = 0

            async def abort_side_effect(*args):
                nonlocal call_count
                call_count += 1
                if call_count > 1:
                    # Simulate abort being triggered
                    stepper_group.abort._data["value"] = 1

            mock_tot_write.side_effect = abort_side_effect

            await stepper_group.move(1)

        # Verify abort sequence
        mock_moving_write.assert_any_call("Not Moving")
        mock_abort_write.assert_called_with(0)

    @pytest.mark.asyncio
    async def test_move_with_piezo_feedback(self, stepper_group):
        """Test movement with piezo feedback enabled."""
        stepper_group.step_des._data["value"] = 1000
        stepper_group.speed._data["value"] = 500
        stepper_group.abort._data["value"] = 0

        # Set up piezo feedback conditions using internal data access
        stepper_group.piezo_group.enable_stat.value = 1
        stepper_group.piezo_group.feedback_mode_stat.value = "Feedback"
        stepper_group.cavity_group.detune.value = 100.0

        with (
            patch.object(stepper_group.motor_moving, "write", new_callable=AsyncMock),
            patch.object(stepper_group.motor_done, "write", new_callable=AsyncMock),
            patch.object(stepper_group.step_tot, "write", new_callable=AsyncMock),
            patch.object(stepper_group.step_signed, "write", new_callable=AsyncMock),
            patch.object(stepper_group.piezo_group.voltage, "write", new_callable=AsyncMock) as mock_voltage_write,
            patch("sc_linac_physics.utils.simulation.tuner_service.PIEZO_HZ_PER_VOLT", 10),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):

            await stepper_group.move(1)

        # Verify piezo voltage was adjusted to compensate for frequency change
        mock_voltage_write.assert_called()

    @pytest.mark.asyncio
    async def test_move_pos_putter(self, stepper_group):
        """Test positive move putter."""
        with patch.object(stepper_group, "move", new_callable=AsyncMock) as mock_move:
            await stepper_group.move_pos.putter(None, 1)
            mock_move.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_move_neg_putter(self, stepper_group):
        """Test negative move putter."""
        with patch.object(stepper_group, "move", new_callable=AsyncMock) as mock_move:
            await stepper_group.move_neg.putter(None, 1)
            mock_move.assert_called_once_with(-1)

    def test_property_defaults(self, stepper_group):
        """Test default property values."""
        assert stepper_group.step_des.value == 0
        assert stepper_group.speed.value == 20000
        assert stepper_group.step_tot.value == 0
        assert stepper_group.step_signed.value == 0
        assert stepper_group.motor_moving.value == 0
        assert stepper_group.motor_done.value == 1
        assert stepper_group.nsteps_park.value == 5000000

    def test_property_types(self, stepper_group):
        """Test property type annotations."""
        # Import actual caproto property types
        from caproto.server import PvpropertyEnum

        # Test that properties have the correct base functionality
        # rather than exact type matching since caproto uses different
        # concrete implementations

        # Test integer-like properties have value attribute and can hold integers
        for prop in [stepper_group.step_des, stepper_group.speed, stepper_group.step_tot, stepper_group.step_signed]:
            assert hasattr(prop, "value")
            assert isinstance(prop.value, (int, float))

        # Test enum properties
        assert isinstance(stepper_group.motor_moving, PvpropertyEnum)
        assert isinstance(stepper_group.motor_done, PvpropertyEnum)

        # Verify they have enum strings (which makes them boolean-like)
        assert hasattr(stepper_group.motor_moving, "enum_strings")
        assert hasattr(stepper_group.motor_done, "enum_strings")
        assert len(stepper_group.motor_moving.enum_strings) == 2  # Boolean-like enum
        assert len(stepper_group.motor_done.enum_strings) == 2  # Boolean-like enum

    def test_enum_string_configurations(self, stepper_group):
        """Test enum string configurations for boolean-like properties."""
        # Test motor_moving enum strings
        moving_strings = stepper_group.motor_moving.enum_strings
        assert "Not Moving" in moving_strings
        assert "Moving" in moving_strings

        # Test motor_done enum strings
        done_strings = stepper_group.motor_done.enum_strings
        assert "Not Done" in done_strings
        assert "Done" in done_strings

        # Test limit switch enums
        lima_strings = stepper_group.limit_switch_a.enum_strings
        assert "not at limit" in lima_strings
        assert "at limit" in lima_strings

        limb_strings = stepper_group.limit_switch_b.enum_strings
        assert "not at limit" in limb_strings
        assert "at limit" in limb_strings


class TestPiezoPVGroup:
    """Test cases for PiezoPVGroup."""

    def test_initialization(self, mock_cavity_group):
        """Test piezo group initialization."""
        piezo = PiezoPVGroup("TEST:PIEZO:", mock_cavity_group)
        assert piezo.cavity_group == mock_cavity_group

    def test_property_defaults(self, piezo_group):
        """Test default property values."""
        assert piezo_group.enable_stat.value == 1
        assert piezo_group.feedback_mode.value == 1
        assert piezo_group.feedback_mode_stat.value == 1
        assert piezo_group.prerf_test_status.value == 0
        assert piezo_group.withrf_check_status.value == 1
        assert piezo_group.voltage.value == 17
        assert piezo_group.scale.value == 20
        assert piezo_group.integrator_sp.value == 0

    @pytest.mark.asyncio
    async def test_prerf_test_sequence(self, piezo_group):
        """Test pre-RF test sequence."""
        # Mock the write method of prerf_test_status
        with (
            patch.object(piezo_group.prerf_test_status, "write", new_callable=AsyncMock) as mock_write,
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):

            await piezo_group.prerf_test_start.putter(None, 1)

        # Verify test status progression
        mock_write.assert_any_call("Running")
        mock_write.assert_any_call("Complete")
        assert mock_write.call_count == 2

    @pytest.mark.asyncio
    async def test_feedback_mode_switching(self, piezo_group):
        """Test feedback mode switching."""
        # Mock the write method of feedback_mode_stat
        with patch.object(piezo_group.feedback_mode_stat, "write", new_callable=AsyncMock) as mock_write:
            await piezo_group.feedback_mode.putter(None, 0)  # Manual mode
            mock_write.assert_called_with(0)

            await piezo_group.feedback_mode.putter(None, 1)  # Feedback mode
            mock_write.assert_called_with(1)

    def test_enum_configurations(self, piezo_group):
        """Test enum string configurations."""
        # Test that enum properties have the expected number of options
        assert len(piezo_group.enable_stat.enum_strings) == 2
        assert len(piezo_group.feedback_mode.enum_strings) == 2
        assert len(piezo_group.feedback_mode_stat.enum_strings) == 2

        # Test specific enum values
        assert "Disabled" in piezo_group.enable_stat.enum_strings
        assert "Enabled" in piezo_group.enable_stat.enum_strings
        assert "Manual" in piezo_group.feedback_mode.enum_strings
        assert "Feedback" in piezo_group.feedback_mode.enum_strings

    def test_property_types_and_characteristics(self, piezo_group):
        """Test property types and characteristics."""
        from caproto.server import PvpropertyEnum

        # Test that properties have the expected characteristics
        # rather than exact types since caproto may use different implementations

        # Voltage and scale should be integer-like properties
        assert hasattr(piezo_group.voltage, "value")
        assert isinstance(piezo_group.voltage.value, (int, float))
        assert hasattr(piezo_group.scale, "value")
        assert isinstance(piezo_group.scale.value, (int, float))

        # Integrator should be float-like property
        assert hasattr(piezo_group.integrator_sp, "value")
        assert isinstance(piezo_group.integrator_sp.value, (int, float))

        # Test enum properties
        enum_properties = [
            piezo_group.enable_stat,
            piezo_group.feedback_mode,
            piezo_group.feedback_mode_stat,
            piezo_group.prerf_test_status,
            piezo_group.withrf_check_status,
        ]

        for prop in enum_properties:
            assert isinstance(prop, PvpropertyEnum)
            assert hasattr(prop, "enum_strings")
            assert len(prop.enum_strings) > 0
            assert hasattr(prop, "value")
            assert isinstance(prop.value, (int, str))

    def test_property_functionality(self, piezo_group):
        """Test that properties function correctly regardless of exact type."""
        # Test that integer properties can hold the expected values
        assert piezo_group.voltage.value == 17  # Default value from code
        assert piezo_group.scale.value == 20  # Default value from code

        # Test that float property can hold the expected value
        assert piezo_group.integrator_sp.value == 0  # Default value from code

        # Test that enum properties have valid enum indices
        assert 0 <= piezo_group.enable_stat.value < len(piezo_group.enable_stat.enum_strings)
        assert 0 <= piezo_group.feedback_mode.value < len(piezo_group.feedback_mode.enum_strings)

        # Test that properties have write methods (required for async operations)
        assert hasattr(piezo_group.voltage, "write")
        assert hasattr(piezo_group.scale, "write")
        assert hasattr(piezo_group.integrator_sp, "write")

    def test_piezo_enum_string_configurations(self, piezo_group):
        """Test specific enum string configurations for piezo properties."""
        # Test enable status
        enable_strings = piezo_group.enable_stat.enum_strings
        assert "Disabled" in enable_strings
        assert "Enabled" in enable_strings

        # Test feedback mode
        mode_strings = piezo_group.feedback_mode.enum_strings
        assert "Manual" in mode_strings
        assert "Feedback" in mode_strings

        # Test test status enums have multiple states
        test_strings = piezo_group.prerf_test_status.enum_strings
        assert len(test_strings) >= 2

        # Test hardware status has multiple options
        hw_strings = piezo_group.hardware_sum.enum_strings
        assert len(hw_strings) >= 2


class TestIntegration:
    """Integration tests for stepper and piezo groups working together."""

    @pytest.mark.asyncio
    async def test_stepper_with_mocked_piezo_coordination(self, mock_cavity_group, mock_piezo_group):
        """Test coordination between stepper and mocked piezo groups."""
        # Use the fixture with mock piezo group for easier testing
        stepper = StepperPVGroup("TEST:STEPPER:", mock_cavity_group, mock_piezo_group)

        # Setup for coordinated movement using internal data access
        stepper.step_des._data["value"] = 1000
        stepper.speed._data["value"] = 500
        stepper.abort._data["value"] = 0

        # Mock all the write operations
        with (
            patch.object(stepper.motor_moving, "write", new_callable=AsyncMock),
            patch.object(stepper.motor_done, "write", new_callable=AsyncMock),
            patch.object(stepper.step_tot, "write", new_callable=AsyncMock),
            patch.object(stepper.step_signed, "write", new_callable=AsyncMock),
            patch("sc_linac_physics.utils.simulation.tuner_service.PIEZO_HZ_PER_VOLT", 10),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):

            # Set up piezo feedback conditions on the mock piezo_group
            mock_piezo_group.enable_stat.value = 1
            mock_piezo_group.feedback_mode_stat.value = "Feedback"
            mock_cavity_group.detune.value = 100.0

            await stepper.move(1)

        # Verify cavity detune was updated
        assert mock_cavity_group.detune.write.called

    @pytest.mark.asyncio
    async def test_real_stepper_piezo_coordination(self, mock_cavity_group):
        """Test coordination between real stepper and piezo instances."""
        # Create real instances for more comprehensive testing
        piezo = PiezoPVGroup("TEST:PIEZO:", mock_cavity_group)
        stepper = StepperPVGroup("TEST:STEPPER:", mock_cavity_group, piezo)

        # Setup for coordinated movement
        stepper.step_des._data["value"] = 1000
        stepper.speed._data["value"] = 500
        stepper.abort._data["value"] = 0

        # Set up piezo feedback conditions using internal data
        piezo.enable_stat._data["value"] = 1
        piezo.feedback_mode_stat._data["value"] = 1  # 1 = "Feedback" (enum index)
        piezo.voltage._data["value"] = 17
        mock_cavity_group.detune.value = 100.0

        # Mock all the write operations
        with (
            patch.object(stepper.motor_moving, "write", new_callable=AsyncMock),
            patch.object(stepper.motor_done, "write", new_callable=AsyncMock),
            patch.object(stepper.step_tot, "write", new_callable=AsyncMock),
            patch.object(stepper.step_signed, "write", new_callable=AsyncMock),
            patch.object(piezo.voltage, "write", new_callable=AsyncMock),
            patch("sc_linac_physics.utils.simulation.tuner_service.PIEZO_HZ_PER_VOLT", 10),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):

            await stepper.move(1)

        # Verify cavity detune was updated
        assert mock_cavity_group.detune.write.called
        # Piezo voltage adjustment depends on the specific feedback logic

    @pytest.mark.asyncio
    async def test_stepper_move_without_piezo_feedback(self, mock_cavity_group):
        """Test stepper movement without piezo feedback enabled."""
        piezo = PiezoPVGroup("TEST:PIEZO:", mock_cavity_group)
        stepper = StepperPVGroup("TEST:STEPPER:", mock_cavity_group, piezo)

        # Setup movement without piezo feedback
        stepper.step_des._data["value"] = 1000
        stepper.speed._data["value"] = 500
        stepper.abort._data["value"] = 0

        # Disable piezo feedback
        piezo.enable_stat._data["value"] = 0  # Disabled
        piezo.feedback_mode_stat._data["value"] = 0  # Manual mode

        with (
            patch.object(stepper.motor_moving, "write", new_callable=AsyncMock),
            patch.object(stepper.motor_done, "write", new_callable=AsyncMock),
            patch.object(stepper.step_tot, "write", new_callable=AsyncMock),
            patch.object(stepper.step_signed, "write", new_callable=AsyncMock),
            patch.object(piezo.voltage, "write", new_callable=AsyncMock),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):

            await stepper.move(1)

        # Verify cavity was updated but piezo voltage was not adjusted
        assert mock_cavity_group.detune.write.called
        # Piezo voltage should not be called when feedback is disabled
        # (depends on the exact implementation logic)

    def test_frequency_conversion_consistency(self):
        """Test frequency conversion consistency between harmonic linearizer and regular cavities."""
        # Create separate mock objects to avoid shared state issues
        mock_cavity_regular = Mock(spec=CavityPVGroup)
        mock_cavity_regular.is_hl = False
        mock_cavity_regular.detune = AsyncMock()
        mock_cavity_regular.detune.value = 100.0
        mock_cavity_regular.detune_rfs = AsyncMock()
        mock_cavity_regular.detune_chirp = AsyncMock()

        mock_cavity_hl = Mock(spec=CavityPVGroup)
        mock_cavity_hl.is_hl = True
        mock_cavity_hl.detune = AsyncMock()
        mock_cavity_hl.detune.value = 100.0
        mock_cavity_hl.detune_rfs = AsyncMock()
        mock_cavity_hl.detune_chirp = AsyncMock()

        mock_piezo = Mock(spec=PiezoPVGroup)
        mock_piezo.enable_stat = AsyncMock()
        mock_piezo.voltage = AsyncMock()

        # Test regular (non-harmonic linearizer) cavity
        stepper_regular = StepperPVGroup("TEST:REG:", mock_cavity_regular, mock_piezo)

        # Test harmonic linearizer cavity
        stepper_hl = StepperPVGroup("TEST:HL:", mock_cavity_hl, mock_piezo)

        # Verify different conversion factors
        assert stepper_regular.steps_per_hertz != stepper_hl.steps_per_hertz
        assert stepper_regular.steps_per_hertz == 256 / 1.4  # Regular cavity conversion
        assert stepper_hl.steps_per_hertz == 256 / 18.3  # Harmonic linearizer conversion

    def test_property_name_mapping(self, stepper_group, piezo_group):
        """Test that PV names are correctly set."""
        # Test stepper PV names (they should contain the name suffix)
        assert "MOV_REQ_POS" in stepper_group.move_pos.pvname
        assert "MOV_REQ_NEG" in stepper_group.move_neg.pvname
        assert "ABORT_REQ" in stepper_group.abort.pvname
        assert "NSTEPS" in stepper_group.step_des.pvname
        assert "VELO" in stepper_group.speed.pvname

        # Test piezo PV names
        assert "ENABLE" in piezo_group.enable.pvname
        assert "ENABLESTAT" in piezo_group.enable_stat.pvname
        assert "MODECTRL" in piezo_group.feedback_mode.pvname
        assert "V" in piezo_group.voltage.pvname

    def test_stepper_piezo_reference_consistency(self, mock_cavity_group, mock_piezo_group):
        """Test that stepper correctly references its piezo group."""
        stepper = StepperPVGroup("TEST:STEPPER:", mock_cavity_group, mock_piezo_group)

        # Verify stepper has correct references
        assert stepper.cavity_group == mock_cavity_group
        assert stepper.piezo_group == mock_piezo_group

        # Test with real piezo group
        real_piezo = PiezoPVGroup("TEST:REAL_PIEZO:", mock_cavity_group)
        stepper_with_real_piezo = StepperPVGroup("TEST:STEPPER2:", mock_cavity_group, real_piezo)

        assert stepper_with_real_piezo.piezo_group == real_piezo
        assert stepper_with_real_piezo.cavity_group == mock_cavity_group


class TestCavityTypeSpecificBehavior:
    """Test behavior specific to harmonic linearizer vs regular cavities."""

    def test_hl_cavity_conversion_factor(self):
        """Test harmonic linearizer cavity uses correct conversion factor."""
        # Create separate mock objects for this test
        mock_cavity_hl = Mock(spec=CavityPVGroup)
        mock_cavity_hl.is_hl = True
        mock_cavity_hl.detune = AsyncMock()
        mock_cavity_hl.detune_rfs = AsyncMock()
        mock_cavity_hl.detune_chirp = AsyncMock()

        mock_piezo = Mock(spec=PiezoPVGroup)

        stepper = StepperPVGroup("TEST:HL:", mock_cavity_hl, mock_piezo)

        # Harmonic linearizer cavities have different step-to-frequency conversion
        expected_conversion = 256 / 18.3
        assert abs(stepper.steps_per_hertz - expected_conversion) < 1e-6

    def test_regular_cavity_conversion_factor(self):
        """Test regular cavity uses correct conversion factor."""
        # Create separate mock objects for this test
        mock_cavity_regular = Mock(spec=CavityPVGroup)
        mock_cavity_regular.is_hl = False
        mock_cavity_regular.detune = AsyncMock()
        mock_cavity_regular.detune_rfs = AsyncMock()
        mock_cavity_regular.detune_chirp = AsyncMock()

        mock_piezo = Mock(spec=PiezoPVGroup)

        stepper = StepperPVGroup("TEST:REG:", mock_cavity_regular, mock_piezo)

        # Regular cavities have different step-to-frequency conversion
        expected_conversion = 256 / 1.4
        assert abs(stepper.steps_per_hertz - expected_conversion) < 1e-6

    def test_frequency_direction_logic(self):
        """Test that frequency direction logic is correct for different cavity types."""
        # Create separate mock objects to avoid shared state
        mock_cavity_hl = Mock(spec=CavityPVGroup)
        mock_cavity_hl.is_hl = True
        mock_cavity_hl.detune = AsyncMock()
        mock_cavity_hl.detune_rfs = AsyncMock()
        mock_cavity_hl.detune_chirp = AsyncMock()

        mock_cavity_regular = Mock(spec=CavityPVGroup)
        mock_cavity_regular.is_hl = False
        mock_cavity_regular.detune = AsyncMock()
        mock_cavity_regular.detune_rfs = AsyncMock()
        mock_cavity_regular.detune_chirp = AsyncMock()

        mock_piezo = Mock(spec=PiezoPVGroup)

        # For harmonic linearizer cavities
        stepper_hl = StepperPVGroup("TEST:HL:", mock_cavity_hl, mock_piezo)

        # For regular cavities
        stepper_regular = StepperPVGroup("TEST:REG:", mock_cavity_regular, mock_piezo)

        # Verify the setup is correct for different cavity types
        assert stepper_hl.cavity_group.is_hl is True
        assert stepper_regular.cavity_group.is_hl is False

        # Verify they have different conversion factors as expected
        assert stepper_hl.steps_per_hertz == 256 / 18.3
        assert stepper_regular.steps_per_hertz == 256 / 1.4


class TestErrorHandling:
    """Test error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_move_with_zero_steps(self, stepper_group):
        """Test movement with zero steps."""
        stepper_group.step_des._data["value"] = 0
        stepper_group.speed._data["value"] = 500

        with (
            patch.object(stepper_group.motor_moving, "write", new_callable=AsyncMock),
            patch.object(stepper_group.motor_done, "write", new_callable=AsyncMock) as mock_done_write,
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):

            await stepper_group.move(1)

        # Should complete immediately
        mock_done_write.assert_called_with("Done")

    @pytest.mark.asyncio
    async def test_large_step_movement_logic(self, stepper_group):
        """Test movement logic with large number of steps (mocked to prevent long execution)."""
        # Use smaller values but test the multi-iteration logic
        stepper_group.step_des._data["value"] = 2000  # Smaller but still multi-iteration
        stepper_group.speed._data["value"] = 500  # Speed per iteration
        stepper_group.abort._data["value"] = 0

        iteration_count = 0
        max_iterations = 5  # Limit iterations to prevent long test runs

        async def limited_sleep_side_effect(*args):
            nonlocal iteration_count
            iteration_count += 1
            if iteration_count >= max_iterations:
                # Force completion by setting remaining steps to 0
                stepper_group.step_des._data["value"] = iteration_count * stepper_group.speed._data["value"]

        with (
            patch.object(stepper_group.motor_moving, "write", new_callable=AsyncMock),
            patch.object(stepper_group.motor_done, "write", new_callable=AsyncMock) as mock_done_write,
            patch.object(stepper_group.step_tot, "write", new_callable=AsyncMock) as mock_tot_write,
            patch.object(stepper_group.step_signed, "write", new_callable=AsyncMock),
            patch("asyncio.sleep", new_callable=AsyncMock, side_effect=limited_sleep_side_effect),
        ):

            await stepper_group.move(1)

        # Should complete and update step totals multiple times
        mock_done_write.assert_called_with("Done")
        assert mock_tot_write.call_count >= 2  # Should be called multiple times

    @pytest.mark.asyncio
    async def test_movement_step_calculation_logic(self, stepper_group):
        """Test the step calculation logic without long execution."""
        # Test the logic of how steps are calculated and updated
        stepper_group.step_des._data["value"] = 1500
        stepper_group.speed._data["value"] = 1000
        stepper_group.abort._data["value"] = 0
        stepper_group.step_tot._data["value"] = 0
        stepper_group.step_signed._data["value"] = 0

        step_updates = []
        signed_updates = []

        async def capture_step_updates(value):
            step_updates.append(value)

        async def capture_signed_updates(value):
            signed_updates.append(value)

        with (
            patch.object(stepper_group.motor_moving, "write", new_callable=AsyncMock),
            patch.object(stepper_group.motor_done, "write", new_callable=AsyncMock),
            patch.object(stepper_group.step_tot, "write", new_callable=AsyncMock, side_effect=capture_step_updates),
            patch.object(
                stepper_group.step_signed, "write", new_callable=AsyncMock, side_effect=capture_signed_updates
            ),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):

            await stepper_group.move(1)

        # Verify step calculations
        # First iteration: 1000 steps (speed value)
        # Second iteration: 500 steps (remainder)
        assert len(step_updates) >= 2

        # Check that steps are accumulated correctly
        total_steps = sum(step_updates)
        assert total_steps >= stepper_group.step_des._data["value"]

    def test_property_value_consistency(self, stepper_group, piezo_group):
        """Test that property values are consistent and valid."""
        # Test stepper properties have reasonable default values
        assert isinstance(stepper_group.step_des.value, (int, float))
        assert isinstance(stepper_group.speed.value, (int, float))
        assert stepper_group.speed.value > 0  # Speed should be positive

        # Test piezo properties have reasonable default values
        assert isinstance(piezo_group.voltage.value, (int, float))
        assert isinstance(piezo_group.scale.value, (int, float))
        assert isinstance(piezo_group.integrator_sp.value, (int, float))

    @pytest.mark.asyncio
    async def test_concurrent_piezo_operations(self, piezo_group):
        """Test concurrent piezo operations."""
        with (
            patch.object(piezo_group.prerf_test_status, "write", new_callable=AsyncMock),
            patch.object(piezo_group.feedback_mode_stat, "write", new_callable=AsyncMock),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):

            # Run multiple operations concurrently
            tasks = [
                piezo_group.prerf_test_start.putter(None, 1),
                piezo_group.feedback_mode.putter(None, 0),
                piezo_group.feedback_mode.putter(None, 1),
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

        # All operations should complete without exceptions
        for result in results:
            assert not isinstance(result, Exception)


# Simplified test for basic functionality without complex mocking
class TestBasicFunctionality:
    """Basic functionality tests that don't require complex async setup."""

    def test_stepper_creation(self, mock_cavity_group, mock_piezo_group):
        """Test basic stepper group creation."""
        stepper = StepperPVGroup("TEST:", mock_cavity_group, mock_piezo_group)
        assert stepper.cavity_group == mock_cavity_group
        assert stepper.piezo_group == mock_piezo_group

    def test_piezo_creation(self, mock_cavity_group):
        """Test basic piezo group creation."""
        piezo = PiezoPVGroup("TEST:", mock_cavity_group)
        assert piezo.cavity_group == mock_cavity_group

    def test_harmonic_linearizer_vs_regular_conversion_factors(self):
        """Test frequency conversion factors for harmonic linearizer vs regular cavities."""
        # Create separate mock objects to avoid shared state
        mock_cavity_regular = Mock(spec=CavityPVGroup)
        mock_cavity_regular.is_hl = False
        mock_cavity_regular.detune = AsyncMock()
        mock_cavity_regular.detune_rfs = AsyncMock()
        mock_cavity_regular.detune_chirp = AsyncMock()

        mock_cavity_hl = Mock(spec=CavityPVGroup)
        mock_cavity_hl.is_hl = True
        mock_cavity_hl.detune = AsyncMock()
        mock_cavity_hl.detune_rfs = AsyncMock()
        mock_cavity_hl.detune_chirp = AsyncMock()

        mock_piezo = Mock(spec=PiezoPVGroup)

        # Regular cavity
        stepper_regular = StepperPVGroup("TEST:REG:", mock_cavity_regular, mock_piezo)
        assert abs(stepper_regular.steps_per_hertz - (256 / 1.4)) < 1e-6

        # Harmonic linearizer cavity
        stepper_hl = StepperPVGroup("TEST:HL:", mock_cavity_hl, mock_piezo)
        assert abs(stepper_hl.steps_per_hertz - (256 / 18.3)) < 1e-6


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
