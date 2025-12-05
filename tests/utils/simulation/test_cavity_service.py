from unittest.mock import AsyncMock, patch

import pytest

from sc_linac_physics.utils.simulation.cavity_service import CavityPVGroup

# Make sure pytest-asyncio is configured
pytest_plugins = ("pytest_asyncio",)


@pytest.fixture
def regular_cavity():
    """Create a regular (non-harmonic linearizer) cavity for testing."""
    return CavityPVGroup("TEST:CAV:", isHL=False)


@pytest.fixture
def hl_cavity():
    """Create a harmonic linearizer cavity for testing."""
    return CavityPVGroup("TEST:HL:", isHL=True)


class TestCavityPVGroupInitialization:
    """Test cavity initialization and basic properties."""

    def test_regular_cavity_initialization(self, regular_cavity):
        """Test initialization of regular cavity."""
        assert regular_cavity.is_hl is False
        assert regular_cavity.length == 1.038
        assert regular_cavity.prefix == "TEST:CAV:"

    def test_hl_cavity_initialization(self, hl_cavity):
        """Test initialization of harmonic linearizer cavity."""
        assert hl_cavity.is_hl is True
        assert hl_cavity.length == 0.346
        assert hl_cavity.prefix == "TEST:HL:"

    def test_default_property_values(self, regular_cavity):
        """Test default values of cavity properties."""
        assert regular_cavity.acon.value == 16.6
        assert regular_cavity.ades.value == 16.6
        assert regular_cavity.aact.value == 16.6
        assert regular_cavity.gdes.value == 16.0
        assert regular_cavity.pdes.value == 0.0
        assert regular_cavity.rf_state_des.value == 1  # On
        assert regular_cavity.rf_mode_des.value == 4  # Pulse
        assert regular_cavity.rfPermit.value == 1  # RF allow
        assert regular_cavity.parked.value == 0  # Not parked

    def test_property_types_and_functionality(self, regular_cavity):
        """Test that properties have correct functionality rather than exact types."""
        # Test that float-like properties work correctly
        float_like_props = [
            regular_cavity.acon,
            regular_cavity.ades,
            regular_cavity.gdes,
            regular_cavity.pdes,
            regular_cavity.sel_aset,
        ]
        for prop in float_like_props:
            assert hasattr(prop, "value")
            assert isinstance(prop.value, (int, float))
            assert hasattr(prop, "write")  # Should be writable

        # Test read-only float-like properties
        ro_float_props = [
            regular_cavity.aact,
            regular_cavity.amean,
            regular_cavity.gact,
        ]
        for prop in ro_float_props:
            assert hasattr(prop, "value")
            assert isinstance(prop.value, (int, float))
            # Check if it's read-only by type name
            type_name = type(prop).__name__
            assert "RO" in type_name or "ReadOnly" in type_name

        # Test enum properties
        enum_props = [
            regular_cavity.rf_state_des,
            regular_cavity.rf_mode_des,
            regular_cavity.rfPermit,
            regular_cavity.parked,
        ]
        for prop in enum_props:
            assert hasattr(prop, "enum_strings")
            assert len(prop.enum_strings) > 0
            assert hasattr(prop, "value")
            assert isinstance(prop.value, (int, str))

        # Test integer properties
        int_props = [
            regular_cavity.detune,
            regular_cavity.detune_rfs,
            regular_cavity.detune_chirp,
            regular_cavity.chirp_start,
            regular_cavity.chirp_stop,
        ]
        for prop in int_props:
            assert hasattr(prop, "value")
            assert isinstance(prop.value, (int, float))

        # Test string properties
        string_props = [regular_cavity.cudStatus, regular_cavity.probe_cal_time]
        for prop in string_props:
            assert hasattr(prop, "value")
            assert isinstance(prop.value, str)

    def test_enum_configurations(self, regular_cavity):
        """Test enum string configurations."""
        # RF State
        assert "Off" in regular_cavity.rf_state_des.enum_strings
        assert "On" in regular_cavity.rf_state_des.enum_strings

        # RF Mode
        rf_modes = regular_cavity.rf_mode_des.enum_strings
        assert "SELAP" in rf_modes
        assert "SELA" in rf_modes
        assert "SEL" in rf_modes
        assert "Pulse" in rf_modes
        assert "Chirp" in rf_modes

        # RF Permit
        assert "RF inhibit" in regular_cavity.rfPermit.enum_strings
        assert "RF allow" in regular_cavity.rfPermit.enum_strings

    def test_random_values_within_range(self, regular_cavity):
        """Test that random values are within expected ranges."""
        # Detune values should be in range
        assert -10000 <= regular_cavity.detune.value <= 10000
        assert regular_cavity.detune.value == regular_cavity.detune_rfs.value
        assert regular_cavity.detune.value == regular_cavity.detune_chirp.value

        # DF_COLD should be in range
        assert -10000 <= regular_cavity.df_cold.value <= 200000

        # Q0 should be in expected range
        assert 2.5e10 <= regular_cavity.q0.value <= 3.5e10

    def test_pv_names(self, regular_cavity):
        """Test that PV names are correctly set."""
        assert "ACON" in regular_cavity.acon.pvname
        assert "ADES" in regular_cavity.ades.pvname
        assert "AACT" in regular_cavity.aact.pvname
        assert "GDES" in regular_cavity.gdes.pvname
        assert "GACT" in regular_cavity.gact.pvname
        assert "PDES" in regular_cavity.pdes.pvname
        assert "RFCTRL" in regular_cavity.rf_state_des.pvname
        assert "DFBEST" in regular_cavity.detune.pvname


class TestAmplitudeControl:
    """Test amplitude control functionality."""

    @pytest.mark.asyncio
    async def test_ades_putter_updates_readbacks(self, regular_cavity):
        """Test that setting ADES updates AACT and AMEAN."""
        new_amplitude = 20.0

        with (
            patch.object(
                regular_cavity.aact, "write", new_callable=AsyncMock
            ) as mock_aact,
            patch.object(
                regular_cavity.amean, "write", new_callable=AsyncMock
            ) as mock_amean,
            patch.object(
                regular_cavity.gdes, "write", new_callable=AsyncMock
            ) as mock_gdes,
        ):
            await regular_cavity.ades.putter(None, new_amplitude)

        # Verify amplitude readbacks are updated
        mock_aact.assert_called_once_with(new_amplitude)
        mock_amean.assert_called_once_with(new_amplitude)

        # Verify gradient is updated (amplitude / length)
        expected_gradient = new_amplitude / regular_cavity.length
        mock_gdes.assert_called_once_with(expected_gradient, verify_value=False)

    @pytest.mark.asyncio
    async def test_ades_putter_different_cavity_lengths(self, hl_cavity):
        """Test amplitude to gradient conversion for different cavity types."""
        new_amplitude = 10.0

        with (
            patch.object(hl_cavity.aact, "write", new_callable=AsyncMock),
            patch.object(hl_cavity.amean, "write", new_callable=AsyncMock),
            patch.object(
                hl_cavity.gdes, "write", new_callable=AsyncMock
            ) as mock_gdes,
        ):
            await hl_cavity.ades.putter(None, new_amplitude)

        # For HL cavity, length = 0.346
        expected_gradient = new_amplitude / 0.346
        mock_gdes.assert_called_once_with(expected_gradient, verify_value=False)


class TestGradientControl:
    """Test gradient control functionality."""

    @pytest.mark.asyncio
    async def test_gdes_putter_updates_readbacks(self, regular_cavity):
        """Test that setting GDES updates GACT and ADES."""
        new_gradient = 25.0

        with (
            patch.object(
                regular_cavity.gact, "write", new_callable=AsyncMock
            ) as mock_gact,
            patch.object(
                regular_cavity.ades, "write", new_callable=AsyncMock
            ) as mock_ades,
        ):
            await regular_cavity.gdes.putter(None, new_gradient)

        # Verify gradient readback is updated
        mock_gact.assert_called_once_with(new_gradient)

        # Verify amplitude is updated (gradient * length)
        expected_amplitude = new_gradient * regular_cavity.length
        mock_ades.assert_called_once_with(expected_amplitude)

    @pytest.mark.asyncio
    async def test_gdes_putter_different_cavity_lengths(self, hl_cavity):
        """Test gradient to amplitude conversion for different cavity types."""
        new_gradient = 30.0

        with (
            patch.object(hl_cavity.gact, "write", new_callable=AsyncMock),
            patch.object(
                hl_cavity.ades, "write", new_callable=AsyncMock
            ) as mock_ades,
        ):
            await hl_cavity.gdes.putter(None, new_gradient)

        # For HL cavity, length = 0.346
        expected_amplitude = new_gradient * 0.346
        mock_ades.assert_called_once_with(expected_amplitude)

    @pytest.mark.asyncio
    async def test_gdes_putter_no_amplitude_update_if_same(
        self, regular_cavity
    ):
        """Test that amplitude is not updated if it's already correct."""
        # Set up cavity so aact already matches expected amplitude
        gradient = 20.0
        regular_cavity.aact._data["value"] = gradient * regular_cavity.length

        with (
            patch.object(regular_cavity.gact, "write", new_callable=AsyncMock),
            patch.object(
                regular_cavity.ades, "write", new_callable=AsyncMock
            ) as mock_ades,
        ):
            await regular_cavity.gdes.putter(None, gradient)

        # ades.write should not be called since aact already matches
        mock_ades.assert_not_called()


class TestPhaseControl:
    """Test phase control functionality."""

    @pytest.mark.asyncio
    async def test_pdes_putter_updates_readbacks(self, regular_cavity):
        """Test that setting PDES updates PACT and PMEAN."""
        new_phase = 45.0

        with (
            patch.object(
                regular_cavity.pact, "write", new_callable=AsyncMock
            ) as mock_pact,
            patch.object(
                regular_cavity.pmean, "write", new_callable=AsyncMock
            ) as mock_pmean,
        ):
            await regular_cavity.pdes.putter(None, new_phase)

        mock_pact.assert_called_once_with(new_phase)
        mock_pmean.assert_called_once_with(new_phase)

    @pytest.mark.asyncio
    async def test_pdes_putter_phase_wrapping(self, regular_cavity):
        """Test that phase values wrap around at 360 degrees."""
        test_cases = [
            (370.0, 10.0),  # 370 -> 10
            (720.0, 0.0),  # 720 -> 0
            (-10.0, 350.0),  # -10 -> 350
            (359.5, 359.5),  # No change needed
        ]

        for input_phase, expected_phase in test_cases:
            with (
                patch.object(
                    regular_cavity.pact, "write", new_callable=AsyncMock
                ) as mock_pact,
                patch.object(
                    regular_cavity.pmean, "write", new_callable=AsyncMock
                ) as mock_pmean,
            ):
                await regular_cavity.pdes.putter(None, input_phase)

            mock_pact.assert_called_once_with(expected_phase)
            mock_pmean.assert_called_once_with(expected_phase)


class TestRFStateControl:
    """Test RF state control functionality."""

    @pytest.mark.asyncio
    async def test_rf_state_des_putter_off(self, regular_cavity):
        """Test turning RF off."""
        with patch.object(
            regular_cavity, "power_off", new_callable=AsyncMock
        ) as mock_power_off:
            await regular_cavity.rf_state_des.putter(None, "Off")
            mock_power_off.assert_called_once()

    @pytest.mark.asyncio
    async def test_rf_state_des_putter_on(self, regular_cavity):
        """Test turning RF on."""
        with patch.object(
            regular_cavity, "power_on", new_callable=AsyncMock
        ) as mock_power_on:
            await regular_cavity.rf_state_des.putter(None, "On")
            mock_power_on.assert_called_once()

    @pytest.mark.asyncio
    async def test_power_off_method(self, regular_cavity):
        """Test the power_off method."""
        with (
            patch.object(
                regular_cavity.amean, "write", new_callable=AsyncMock
            ) as mock_amean,
            patch.object(
                regular_cavity.aact, "write", new_callable=AsyncMock
            ) as mock_aact,
            patch.object(
                regular_cavity.gact, "write", new_callable=AsyncMock
            ) as mock_gact,
            patch.object(
                regular_cavity.rf_state_act, "write", new_callable=AsyncMock
            ) as mock_rf_state,
        ):
            await regular_cavity.power_off()

        mock_amean.assert_called_once_with(0)
        mock_aact.assert_called_once_with(0)
        mock_gact.assert_called_once_with(0)
        mock_rf_state.assert_called_once_with("Off")

    @pytest.mark.asyncio
    async def test_power_on_method(self, regular_cavity):
        """Test the power_on method."""
        # Set some setpoint values
        regular_cavity.ades._data["value"] = 20.0
        regular_cavity.gdes._data["value"] = 25.0

        with (
            patch.object(
                regular_cavity.aact, "write", new_callable=AsyncMock
            ) as mock_aact,
            patch.object(
                regular_cavity.amean, "write", new_callable=AsyncMock
            ) as mock_amean,
            patch.object(
                regular_cavity.gact, "write", new_callable=AsyncMock
            ) as mock_gact,
            patch.object(
                regular_cavity.rf_state_act, "write", new_callable=AsyncMock
            ) as mock_rf_state,
        ):
            await regular_cavity.power_on()

        mock_aact.assert_called_once_with(20.0)
        mock_amean.assert_called_once_with(20.0)
        mock_gact.assert_called_once_with(25.0)
        mock_rf_state.assert_called_once_with("On")


class TestRFModeControl:
    """Test RF mode control functionality."""

    @pytest.mark.asyncio
    async def test_rf_mode_des_putter(self, regular_cavity):
        """Test that setting RF mode desired updates actual mode."""
        new_mode = 2  # SEL mode

        with patch.object(
            regular_cavity.rf_mode_act, "write", new_callable=AsyncMock
        ) as mock_mode_act:
            await regular_cavity.rf_mode_des.putter(None, new_mode)

        mock_mode_act.assert_called_once_with(new_mode)


class TestInterlockSystem:
    """Test interlock and safety system functionality."""

    @pytest.mark.asyncio
    async def test_quench_latch_putter(self, regular_cavity):
        """Test quench latch behavior."""
        with (
            patch.object(
                regular_cavity.aact, "write", new_callable=AsyncMock
            ) as mock_aact,
            patch.object(
                regular_cavity.amean, "write", new_callable=AsyncMock
            ) as mock_amean,
        ):
            await regular_cavity.quench_latch.putter(None, 1)  # Fault

        # Quench should zero the amplitude
        mock_aact.assert_called_once_with(0)
        mock_amean.assert_called_once_with(0)

    @pytest.mark.asyncio
    async def test_interlock_reset_putter(self, regular_cavity):
        """Test interlock reset functionality."""
        # Set up cavity with some setpoint values
        regular_cavity.ades._data["value"] = 18.0

        with (
            patch.object(
                regular_cavity.quench_latch, "write", new_callable=AsyncMock
            ) as mock_quench,
            patch.object(
                regular_cavity.aact, "write", new_callable=AsyncMock
            ) as mock_aact,
            patch.object(
                regular_cavity.amean, "write", new_callable=AsyncMock
            ) as mock_amean,
        ):
            await regular_cavity.interlock_reset.putter(None, 1)  # Reset

        # Should clear quench latch and restore amplitude
        mock_quench.assert_called_once_with(0)
        mock_aact.assert_called_once_with(18.0)
        mock_amean.assert_called_once_with(18.0)


class TestCalibrationAndMaintenance:
    """Test calibration and maintenance functionality."""

    @pytest.mark.asyncio
    async def test_probe_cal_start_putter(self, regular_cavity):
        """Test probe calibration start."""
        with (
            patch.object(
                regular_cavity.probe_cal_time, "write", new_callable=AsyncMock
            ) as mock_time,
            patch.object(
                regular_cavity.probe_cal_start, "write", new_callable=AsyncMock
            ) as mock_start,
            patch(
                "sc_linac_physics.utils.simulation.cavity_service.datetime"
            ) as mock_datetime,
        ):
            mock_datetime.now.return_value.strftime.return_value = (
                "2023-12-01-14:30:00"
            )

            await regular_cavity.probe_cal_start.putter(None, 1)

        # Should update timestamp and reset start flag
        mock_time.assert_called_once_with("2023-12-01-14:30:00")
        mock_start.assert_called_once_with(0)

    @pytest.mark.asyncio
    async def test_probe_cal_start_putter_no_action_for_zero(
        self, regular_cavity
    ):
        """Test that probe calibration doesn't start for value 0."""
        with (
            patch.object(
                regular_cavity.probe_cal_time, "write", new_callable=AsyncMock
            ) as mock_time,
            patch.object(
                regular_cavity.probe_cal_start, "write", new_callable=AsyncMock
            ) as mock_start,
        ):
            await regular_cavity.probe_cal_start.putter(None, 0)

        # Should not update anything
        mock_time.assert_not_called()
        mock_start.assert_not_called()

    def test_default_timestamp_format(self, regular_cavity):
        """Test that default probe calibration timestamp has correct format."""
        timestamp = regular_cavity.probe_cal_time.value
        # Should be in format YYYY-MM-DD-HH:MM:SS
        assert (
            len(timestamp.split("-")) == 4
        )  # YYYY-MM-DD-HH:MM:SS has 4 parts split by '-'
        assert ":" in timestamp  # Should contain time separator


class TestChannelTypeSpecifications:
    """Test channel type specifications and data consistency."""

    def test_property_functionality(self, regular_cavity):
        """Test that properties function correctly regardless of exact caproto type."""
        # Test float-like properties
        float_props = [
            regular_cavity.acon,
            regular_cavity.ades,
            regular_cavity.aact,
            regular_cavity.gdes,
            regular_cavity.pdes,
            regular_cavity.sel_aset,
        ]
        for prop in float_props:
            assert hasattr(prop, "value")
            assert isinstance(prop.value, (int, float))
            assert hasattr(prop, "write")

        # Test integer properties
        int_props = [
            regular_cavity.detune,
            regular_cavity.detune_rfs,
            regular_cavity.detune_chirp,
            regular_cavity.chirp_start,
            regular_cavity.chirp_stop,
        ]
        for prop in int_props:
            assert hasattr(prop, "value")
            assert isinstance(prop.value, (int, float))

        # Test string properties
        string_props = [regular_cavity.cudStatus, regular_cavity.probe_cal_time]
        for prop in string_props:
            assert isinstance(prop.value, str)

    def test_precision_settings(self, regular_cavity):
        """Test that precision is set correctly for float properties."""
        # Properties with precision should have the precision attribute
        assert hasattr(regular_cavity.acon, "precision")
        assert hasattr(regular_cavity.ades, "precision")
        # Check that precision values are reasonable
        assert isinstance(regular_cavity.acon.precision, int)
        assert isinstance(regular_cavity.ades.precision, int)

    def test_read_only_property_characteristics(self, regular_cavity):
        """Test that read-only properties behave correctly."""
        # Test read-only properties by checking their type names
        ro_props = [
            (regular_cavity.aact, "aact"),
            (regular_cavity.amean, "amean"),
            (regular_cavity.gact, "gact"),
            (regular_cavity.pact, "pact"),
            (regular_cavity.rf_mode_act, "rf_mode_act"),
        ]

        for prop, name in ro_props:
            # Check if it's a read-only type by examining the class name
            class_name = type(prop).__name__
            # Read-only properties typically have 'RO' in their class name
            is_readonly_type = "RO" in class_name or "ReadOnly" in class_name

            # All these properties should be read-only based on the original definition
            assert (
                is_readonly_type
            ), f"{name} should be read-only (type: {class_name})"

    def test_enum_string_consistency(self, regular_cavity):
        """Test that enum properties have consistent string configurations."""
        enum_props = [
            (regular_cavity.rf_state_des, ["Off", "On"]),
            (regular_cavity.rf_state_act, ["Off", "On"]),
            (regular_cavity.rfPermit, ["RF inhibit", "RF allow"]),
            (regular_cavity.parked, ["Not parked", "Parked"]),
            (regular_cavity.rf_ready_for_beam, ["Not Ready", "Ready"]),
        ]

        for prop, expected_strings in enum_props:
            assert hasattr(prop, "enum_strings")
            for expected_string in expected_strings:
                assert expected_string in prop.enum_strings

    def test_default_enum_values(self, regular_cavity):
        """Test that enum properties have sensible default values."""
        # RF should default to On (1)
        assert regular_cavity.rf_state_des.value == 1
        assert regular_cavity.rf_state_act.value == 1

        # RF mode should default to Pulse (4)
        assert regular_cavity.rf_mode_des.value == 4

        # RF permit should default to allow (1)
        assert regular_cavity.rfPermit.value == 1

        # Should not be parked by default (0)
        assert regular_cavity.parked.value == 0

    def test_channel_type_consistency(self, regular_cavity):
        """Test that channel types are consistent with their usage."""
        # Enum properties should have enum_strings
        enum_properties = [
            regular_cavity.rf_state_des,
            regular_cavity.rf_mode_des,
            regular_cavity.rf_state_act,
            regular_cavity.rf_mode_act,
            regular_cavity.rfPermit,
            regular_cavity.parked,
            regular_cavity.cudSevr,
            regular_cavity.tune_config,
        ]

        for prop in enum_properties:
            assert hasattr(prop, "enum_strings")
            assert isinstance(prop.enum_strings, (list, tuple))
            assert len(prop.enum_strings) > 0


class TestEdgeCasesAndErrorHandling:
    """Test edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_zero_amplitude_handling(self, regular_cavity):
        """Test handling of zero amplitude values."""
        with (
            patch.object(
                regular_cavity.aact, "write", new_callable=AsyncMock
            ) as mock_aact,
            patch.object(
                regular_cavity.amean, "write", new_callable=AsyncMock
            ) as mock_amean,
            patch.object(
                regular_cavity.gdes, "write", new_callable=AsyncMock
            ) as mock_gdes,
        ):
            await regular_cavity.ades.putter(None, 0.0)

        mock_aact.assert_called_once_with(0.0)
        mock_amean.assert_called_once_with(0.0)
        mock_gdes.assert_called_once_with(
            0.0, verify_value=False
        )  # 0.0 / length = 0.0

    @pytest.mark.asyncio
    async def test_negative_phase_wrapping(self, regular_cavity):
        """Test handling of negative phase values."""
        with patch.object(
            regular_cavity.pact, "write", new_callable=AsyncMock
        ) as mock_pact:
            await regular_cavity.pdes.putter(None, -45.0)

        # -45 % 360 = 315
        mock_pact.assert_called_once_with(315.0)

    @pytest.mark.asyncio
    async def test_large_amplitude_values(self, regular_cavity):
        """Test handling of large amplitude values."""
        large_amplitude = 100.0

        with (
            patch.object(regular_cavity.aact, "write", new_callable=AsyncMock),
            patch.object(regular_cavity.amean, "write", new_callable=AsyncMock),
            patch.object(
                regular_cavity.gdes, "write", new_callable=AsyncMock
            ) as mock_gdes,
        ):
            await regular_cavity.ades.putter(None, large_amplitude)

        expected_gradient = large_amplitude / regular_cavity.length
        mock_gdes.assert_called_once_with(expected_gradient, verify_value=False)

    def test_cavity_length_consistency(self):
        """Test that cavity lengths are consistent with cavity type."""
        regular = CavityPVGroup("REG:", isHL=False)
        hl = CavityPVGroup("HL:", isHL=True)

        assert regular.length > hl.length  # Regular cavities are longer
        assert regular.length == 1.038
        assert hl.length == 0.346

    def test_random_value_consistency(self):
        """Test that random values are consistent within single instance."""
        cavity = CavityPVGroup("TEST:", isHL=False)

        # All detune values should be the same (set from same random value)
        assert cavity.detune.value == cavity.detune_rfs.value
        assert cavity.detune.value == cavity.detune_chirp.value

        # Values should be within expected ranges
        assert -10000 <= cavity.detune.value <= 10000
        assert -10000 <= cavity.df_cold.value <= 200000
        assert 2.5e10 <= cavity.q0.value <= 3.5e10


class TestIntegrationScenarios:
    """Test complete operational scenarios."""

    @pytest.mark.asyncio
    async def test_startup_sequence(self, regular_cavity):
        """Test a typical cavity startup sequence."""
        # 1. Set amplitude setpoint
        with (
            patch.object(regular_cavity.aact, "write", new_callable=AsyncMock),
            patch.object(regular_cavity.amean, "write", new_callable=AsyncMock),
            patch.object(regular_cavity.gdes, "write", new_callable=AsyncMock),
        ):
            await regular_cavity.ades.putter(None, 20.0)

        # 2. Set phase setpoint
        with (
            patch.object(regular_cavity.pact, "write", new_callable=AsyncMock),
            patch.object(regular_cavity.pmean, "write", new_callable=AsyncMock),
        ):
            await regular_cavity.pdes.putter(None, 15.0)

        # 3. Turn on RF
        with patch.object(
            regular_cavity, "power_on", new_callable=AsyncMock
        ) as mock_power_on:
            await regular_cavity.rf_state_des.putter(None, "On")
            mock_power_on.assert_called_once()

    @pytest.mark.asyncio
    async def test_fault_and_recovery_sequence(self, regular_cavity):
        """Test fault condition and recovery."""
        # Set initial setpoints
        regular_cavity.ades._data["value"] = 20.0

        # 1. Simulate quench fault
        with (
            patch.object(
                regular_cavity.aact, "write", new_callable=AsyncMock
            ) as mock_aact1,
            patch.object(
                regular_cavity.amean, "write", new_callable=AsyncMock
            ) as mock_amean1,
        ):
            await regular_cavity.quench_latch.putter(None, 1)

        mock_aact1.assert_called_once_with(0)
        mock_amean1.assert_called_once_with(0)

        # 2. Reset interlocks
        with (
            patch.object(
                regular_cavity.quench_latch, "write", new_callable=AsyncMock
            ) as mock_quench,
            patch.object(
                regular_cavity.aact, "write", new_callable=AsyncMock
            ) as mock_aact2,
            patch.object(
                regular_cavity.amean, "write", new_callable=AsyncMock
            ) as mock_amean2,
        ):
            await regular_cavity.interlock_reset.putter(None, 1)

        mock_quench.assert_called_once_with(0)
        mock_aact2.assert_called_once_with(20.0)
        mock_amean2.assert_called_once_with(20.0)

    @pytest.mark.asyncio
    async def test_mode_change_sequence(self, regular_cavity):
        """Test changing RF mode."""
        # Change from default (Pulse=4) to SEL (2)
        with patch.object(
            regular_cavity.rf_mode_act, "write", new_callable=AsyncMock
        ) as mock_mode:
            await regular_cavity.rf_mode_des.putter(None, 2)
            mock_mode.assert_called_once_with(2)

    @pytest.mark.asyncio
    async def test_amplitude_gradient_coordination(self, regular_cavity):
        """Test coordination between amplitude and gradient setpoints."""
        # Setting amplitude should update gradient
        with (
            patch.object(regular_cavity.aact, "write", new_callable=AsyncMock),
            patch.object(regular_cavity.amean, "write", new_callable=AsyncMock),
            patch.object(
                regular_cavity.gdes, "write", new_callable=AsyncMock
            ) as mock_gdes,
        ):
            await regular_cavity.ades.putter(
                None, 20.76
            )  # Should give gradient of 20.0

        expected_gradient = 20.76 / regular_cavity.length
        mock_gdes.assert_called_once_with(expected_gradient, verify_value=False)

        # Setting gradient should update amplitude
        with (
            patch.object(regular_cavity.gact, "write", new_callable=AsyncMock),
            patch.object(
                regular_cavity.ades, "write", new_callable=AsyncMock
            ) as mock_ades,
        ):
            await regular_cavity.gdes.putter(None, 25.0)

        expected_amplitude = 25.0 * regular_cavity.length
        mock_ades.assert_called_once_with(expected_amplitude)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
