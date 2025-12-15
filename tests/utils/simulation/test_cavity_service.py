from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sc_linac_physics.utils.simulation.cavity_service import CavityPVGroup

# Make sure pytest-asyncio is configured
pytest_plugins = ("pytest_asyncio",)


@pytest.fixture
def mock_cm_group():
    """Create a mock cryomodule group for cavity testing."""
    cm_group = MagicMock()
    cm_group.total_power = 0.0
    cm_group.heater = MagicMock()
    cm_group.heater.mode.value = 2  # SEQUENCER mode
    cm_group.heater.setpoint = MagicMock()
    cm_group.heater.setpoint.value = 0.0
    cm_group.heater.setpoint.write = AsyncMock()
    return cm_group


@pytest.fixture
def regular_cavity(mock_cm_group):
    """Create a regular (non-harmonic linearizer) cavity for testing."""
    return CavityPVGroup("TEST:CAV:", isHL=False, cm_group=mock_cm_group)


@pytest.fixture
def hl_cavity(mock_cm_group):
    """Create a harmonic linearizer cavity for testing."""
    return CavityPVGroup("TEST:HL:", isHL=True, cm_group=mock_cm_group)


class TestCavityPVGroupInitialization:
    """Test cavity initialization and basic properties."""

    def test_regular_cavity_initialization(self, regular_cavity):
        """Test initialization of regular cavity."""
        assert regular_cavity.is_hl is False
        assert regular_cavity.length == 1.038
        assert regular_cavity.frequency == 1.3e9
        assert regular_cavity.prefix == "TEST:CAV:"

    def test_hl_cavity_initialization(self, hl_cavity):
        """Test initialization of harmonic linearizer cavity."""
        assert hl_cavity.is_hl is True
        assert hl_cavity.length == 0.346
        assert hl_cavity.frequency == 3.9e9
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
