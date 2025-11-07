from unittest.mock import patch, AsyncMock

import pytest
from caproto.server import PVGroup

from sc_linac_physics.utils.simulation.auto_setup_service import (
    AutoSetupPVGroup,
    AutoSetupCMPVGroup,
    AutoSetupLinacPVGroup,
    AutoSetupGlobalPVGroup,
    AutoSetupCavityPVGroup,
)

# Make sure pytest-asyncio is configured
pytest_plugins = ("pytest_asyncio",)


@pytest.fixture
def base_auto_setup():
    """Create a base AutoSetupPVGroup instance for testing."""
    return AutoSetupPVGroup("TEST:", ["arg1", "arg2"])


@pytest.fixture
def cm_auto_setup():
    """Create an AutoSetupCMPVGroup instance for testing."""
    return AutoSetupCMPVGroup("TEST:CM01:", "01")


@pytest.fixture
def linac_auto_setup():
    """Create an AutoSetupLinacPVGroup instance for testing."""
    return AutoSetupLinacPVGroup("TEST:L1B:", 1)


@pytest.fixture
def global_auto_setup():
    """Create an AutoSetupGlobalPVGroup instance for testing."""
    return AutoSetupGlobalPVGroup("TEST:SYS:")


@pytest.fixture
def cavity_auto_setup():
    """Create an AutoSetupCavityPVGroup instance for testing."""
    return AutoSetupCavityPVGroup("TEST:CM01:10:", "01", 1)


@pytest.fixture
def mock_subprocess():
    """Create a properly configured subprocess mock."""
    mock_process = AsyncMock()
    mock_process.wait = AsyncMock(return_value=0)
    mock_process.returncode = 0
    return mock_process


class TestAutoSetupPVGroupBase:
    """Test the base AutoSetupPVGroup class."""

    def test_inheritance(self, base_auto_setup):
        """Test that AutoSetupPVGroup inherits from PVGroup."""
        assert isinstance(base_auto_setup, PVGroup)
        assert isinstance(base_auto_setup, AutoSetupPVGroup)

    def test_initialization(self, base_auto_setup):
        """Test AutoSetupPVGroup initialization."""
        assert base_auto_setup.prefix == "TEST:AUTO:"
        assert base_auto_setup.script_args == ["arg1", "arg2"]

    def test_initialization_no_args(self):
        """Test AutoSetupPVGroup initialization without script args."""
        group = AutoSetupPVGroup("TEST:")
        assert group.prefix == "TEST:AUTO:"
        assert group.script_args is None

    def test_property_defaults(self, base_auto_setup):
        """Test default property values."""
        # Boolean enum properties should default to False (0)
        assert base_auto_setup.setup_start.value == 0
        assert base_auto_setup.setup_stop.value == 0
        assert base_auto_setup.setup_status.value == 0
        assert base_auto_setup.setup_timestamp.value == 0
        assert base_auto_setup.off_start.value == 0
        assert base_auto_setup.off_stop.value == 0
        assert base_auto_setup.off_status.value == 0
        assert base_auto_setup.off_timestamp.value == 0

        # Request properties with explicit defaults
        assert base_auto_setup.ssa_cal.value == 1  # True
        assert base_auto_setup.tune.value == 1  # True
        assert base_auto_setup.cav_char.value == 1  # True
        assert base_auto_setup.ramp.value == 1  # True

        # Abort should default to no request
        assert base_auto_setup.abort.value == 0

    def test_property_functionality(self, base_auto_setup):
        """Test that properties have correct functionality rather than exact types."""
        # Test that all properties have value attribute and can be accessed
        bool_like_props = [
            base_auto_setup.setup_start,
            base_auto_setup.setup_stop,
            base_auto_setup.setup_status,
            base_auto_setup.setup_timestamp,
            base_auto_setup.ssa_cal,
            base_auto_setup.off_start,
            base_auto_setup.off_stop,
            base_auto_setup.off_status,
            base_auto_setup.off_timestamp,
        ]

        for prop in bool_like_props:
            assert hasattr(prop, "value")
            assert isinstance(prop.value, (int, bool))
            assert hasattr(prop, "write")
            assert hasattr(prop, "pvname")

        # Test enum-like properties
        enum_like_props = [
            base_auto_setup.tune,
            base_auto_setup.cav_char,
            base_auto_setup.ramp,
            base_auto_setup.abort,
        ]

        for prop in enum_like_props:
            assert hasattr(prop, "value")
            assert isinstance(prop.value, (int, str))
            assert hasattr(prop, "write")
            assert hasattr(prop, "pvname")

        # Test char property
        assert hasattr(base_auto_setup.note, "value")
        assert isinstance(base_auto_setup.note.value, str)
        assert hasattr(base_auto_setup.note, "write")
        assert hasattr(base_auto_setup.note, "pvname")

    def test_pv_names(self, base_auto_setup):
        """Test that PV names are correctly set."""
        expected_names = {
            "SETUPSTRT": base_auto_setup.setup_start,
            "SETUPSTOP": base_auto_setup.setup_stop,
            "SETUPSTS": base_auto_setup.setup_status,
            "SETUPTS": base_auto_setup.setup_timestamp,
            "SETUP_SSAREQ": base_auto_setup.ssa_cal,
            "SETUP_TUNEREQ": base_auto_setup.tune,
            "SETUP_CHARREQ": base_auto_setup.cav_char,
            "SETUP_RAMPREQ": base_auto_setup.ramp,
            "OFFSTRT": base_auto_setup.off_start,
            "OFFSTOP": base_auto_setup.off_stop,
            "OFFSTS": base_auto_setup.off_status,
            "OFFTS": base_auto_setup.off_timestamp,
            "NOTE": base_auto_setup.note,
            "ABORT": base_auto_setup.abort,
        }

        for expected_name, prop in expected_names.items():
            assert expected_name in prop.pvname

    def test_abort_enum_strings(self, base_auto_setup):
        """Test abort property enum strings."""
        # Check if the property has enum_strings attribute
        if hasattr(base_auto_setup.abort, "enum_strings"):
            abort_strings = base_auto_setup.abort.enum_strings
            assert "No abort request" in abort_strings
            assert "Abort request" in abort_strings
            assert len(abort_strings) == 2

    def test_note_default_value(self, base_auto_setup):
        """Test note property default value."""
        expected_note = "This is as long of a sentence as I can type in order to test wrapping"
        assert base_auto_setup.note.value == expected_note

    def test_abstract_methods_not_implemented(self, base_auto_setup):
        """Test that abstract methods raise NotImplementedError."""
        with pytest.raises(NotImplementedError):
            base_auto_setup.trigger_setup_script()

        with pytest.raises(NotImplementedError):
            base_auto_setup.trigger_shutdown_script()

    def test_property_types_general(self, base_auto_setup):
        """Test that properties have expected caproto-like characteristics."""
        all_props = [
            base_auto_setup.setup_start,
            base_auto_setup.setup_stop,
            base_auto_setup.setup_status,
            base_auto_setup.setup_timestamp,
            base_auto_setup.ssa_cal,
            base_auto_setup.tune,
            base_auto_setup.cav_char,
            base_auto_setup.ramp,
            base_auto_setup.off_start,
            base_auto_setup.off_stop,
            base_auto_setup.off_status,
            base_auto_setup.off_timestamp,
            base_auto_setup.note,
            base_auto_setup.abort,
        ]

        for prop in all_props:
            # All properties should have these basic caproto characteristics
            assert hasattr(prop, "value")
            assert hasattr(prop, "pvname")
            assert hasattr(prop, "write")

            # Check that the property type makes sense
            type_name = type(prop).__name__
            assert any(
                x in type_name for x in ["Pvproperty", "Property", "Channel"]
            )


class TestAutoSetupPutterMethods:
    """Test putter methods for AutoSetupPVGroup."""

    @pytest.mark.asyncio
    async def test_setup_start_putter(self, base_auto_setup):
        """Test setup_start putter method."""
        with patch.object(
            base_auto_setup, "trigger_setup_script", new_callable=AsyncMock
        ) as mock_trigger:
            await base_auto_setup.setup_start.putter(None, 1)
            mock_trigger.assert_called_once()

    @pytest.mark.asyncio
    async def test_off_start_putter(self, base_auto_setup):
        """Test off_start putter method."""
        with patch.object(
            base_auto_setup, "trigger_shutdown_script", new_callable=AsyncMock
        ) as mock_trigger:
            await base_auto_setup.off_start.putter(None, 1)
            mock_trigger.assert_called_once()


class TestAutoSetupCMPVGroup:
    """Test AutoSetupCMPVGroup class."""

    def test_inheritance(self, cm_auto_setup):
        """Test that AutoSetupCMPVGroup inherits from AutoSetupPVGroup."""
        assert isinstance(cm_auto_setup, AutoSetupPVGroup)
        assert isinstance(cm_auto_setup, AutoSetupCMPVGroup)

    def test_initialization(self, cm_auto_setup):
        """Test AutoSetupCMPVGroup initialization."""
        assert cm_auto_setup.prefix == "TEST:CM01:AUTO:"
        assert cm_auto_setup.cm_name == "01"

    @pytest.mark.asyncio
    async def test_trigger_setup_script(self, cm_auto_setup, mock_subprocess):
        """Test CM setup script triggering."""
        with patch(
            "sc_linac_physics.utils.simulation.auto_setup_service.create_subprocess_exec",
            return_value=mock_subprocess,
        ) as mock_create:
            await cm_auto_setup.trigger_setup_script()

            mock_create.assert_called_once_with(
                "sc-setup-cm",
                "-cm=01",
            )

    @pytest.mark.asyncio
    async def test_trigger_shutdown_script(
        self, cm_auto_setup, mock_subprocess
    ):
        """Test CM shutdown script triggering."""
        with patch(
            "sc_linac_physics.utils.simulation.auto_setup_service.create_subprocess_exec",
            return_value=mock_subprocess,
        ) as mock_create:
            await cm_auto_setup.trigger_shutdown_script()

            mock_create.assert_called_once_with(
                "sc-setup-cm",
                "-cm=01",
                "-off",
            )

    @pytest.mark.asyncio
    async def test_setup_integration(self, cm_auto_setup):
        """Test integration of setup start with CM script."""
        with patch.object(
            cm_auto_setup, "trigger_setup_script", new_callable=AsyncMock
        ) as mock_trigger:
            await cm_auto_setup.setup_start.putter(None, 1)
            mock_trigger.assert_called_once()


class TestAutoSetupLinacPVGroup:
    """Test AutoSetupLinacPVGroup class."""

    def test_inheritance(self, linac_auto_setup):
        """Test that AutoSetupLinacPVGroup inherits from AutoSetupPVGroup."""
        assert isinstance(linac_auto_setup, AutoSetupPVGroup)
        assert isinstance(linac_auto_setup, AutoSetupLinacPVGroup)

    def test_initialization(self, linac_auto_setup):
        """Test AutoSetupLinacPVGroup initialization."""
        assert linac_auto_setup.prefix == "TEST:L1B:AUTO:"
        assert linac_auto_setup.linac_idx == 1

    @pytest.mark.asyncio
    async def test_trigger_setup_script(
        self, linac_auto_setup, mock_subprocess
    ):
        """Test linac setup script triggering."""
        with patch(
            "sc_linac_physics.utils.simulation.auto_setup_service.create_subprocess_exec",
            return_value=mock_subprocess,
        ) as mock_create:
            await linac_auto_setup.trigger_setup_script()

            mock_create.assert_called_once_with(
                "sc-setup-linac",
                "-l=1",
            )

    @pytest.mark.asyncio
    async def test_trigger_shutdown_script(
        self, linac_auto_setup, mock_subprocess
    ):
        """Test linac shutdown script triggering."""
        with patch(
            "sc_linac_physics.utils.simulation.auto_setup_service.create_subprocess_exec",
            return_value=mock_subprocess,
        ) as mock_create:
            await linac_auto_setup.trigger_shutdown_script()

            mock_create.assert_called_once_with(
                "sc-setup-linac",
                "-l=1",
                "-off",
            )

    def test_different_linac_indices(self):
        """Test AutoSetupLinacPVGroup with different linac indices."""
        test_cases = [0, 1, 2, 3]

        for idx in test_cases:
            group = AutoSetupLinacPVGroup(f"TEST:L{idx}:", idx)
            assert group.linac_idx == idx
            assert group.prefix == f"TEST:L{idx}:AUTO:"


class TestAutoSetupGlobalPVGroup:
    """Test AutoSetupGlobalPVGroup class."""

    def test_inheritance(self, global_auto_setup):
        """Test that AutoSetupGlobalPVGroup inherits from AutoSetupPVGroup."""
        assert isinstance(global_auto_setup, AutoSetupPVGroup)
        assert isinstance(global_auto_setup, AutoSetupGlobalPVGroup)

    def test_initialization(self, global_auto_setup):
        """Test AutoSetupGlobalPVGroup initialization."""
        assert global_auto_setup.prefix == "TEST:SYS:AUTO:"

    @pytest.mark.asyncio
    async def test_trigger_setup_script(
        self, global_auto_setup, mock_subprocess
    ):
        """Test global setup script triggering."""
        with patch(
            "sc_linac_physics.utils.simulation.auto_setup_service.create_subprocess_exec",
            return_value=mock_subprocess,
        ) as mock_create:
            await global_auto_setup.trigger_setup_script()

            mock_create.assert_called_once_with("sc-setup-all")

    @pytest.mark.asyncio
    async def test_trigger_shutdown_script(
        self, global_auto_setup, mock_subprocess
    ):
        """Test global shutdown script triggering."""
        with patch(
            "sc_linac_physics.utils.simulation.auto_setup_service.create_subprocess_exec",
            return_value=mock_subprocess,
        ) as mock_create:
            await global_auto_setup.trigger_shutdown_script()

            mock_create.assert_called_once_with(
                "sc-setup-all",
                "-off",
            )


class TestAutoSetupCavityPVGroup:
    """Test AutoSetupCavityPVGroup class."""

    def test_inheritance(self, cavity_auto_setup):
        """Test that AutoSetupCavityPVGroup inherits from AutoSetupPVGroup."""
        assert isinstance(cavity_auto_setup, AutoSetupPVGroup)
        assert isinstance(cavity_auto_setup, AutoSetupCavityPVGroup)

    def test_initialization(self, cavity_auto_setup):
        """Test AutoSetupCavityPVGroup initialization."""
        assert cavity_auto_setup.prefix == "TEST:CM01:10:AUTO:"
        assert cavity_auto_setup.cm_name == "01"
        assert cavity_auto_setup.cav_num == 1

    def test_additional_properties(self, cavity_auto_setup):
        """Test additional properties specific to cavity auto-setup."""
        # Test progress property
        assert hasattr(cavity_auto_setup, "progress")
        assert cavity_auto_setup.progress.value == 0.0

        # Test status property
        assert hasattr(cavity_auto_setup, "status")
        assert cavity_auto_setup.status.value == 0  # "Ready"

        # Test status message
        assert hasattr(cavity_auto_setup, "status_message")
        assert cavity_auto_setup.status_message.value == "Ready"

        # Test timestamp
        assert hasattr(cavity_auto_setup, "time_stamp")
        assert isinstance(cavity_auto_setup.time_stamp.value, str)

    def test_status_enum_strings(self, cavity_auto_setup):
        """Test status property enum strings."""
        if hasattr(cavity_auto_setup.status, "enum_strings"):
            status_strings = cavity_auto_setup.status.enum_strings
            assert "Ready" in status_strings
            assert "Running" in status_strings
            assert "Error" in status_strings
            assert len(status_strings) == 3

    def test_timestamp_format(self, cavity_auto_setup):
        """Test timestamp format."""
        timestamp = cavity_auto_setup.time_stamp.value
        # Should be in format MM/DD/YY HH:MM:SS.ffffff
        import re

        pattern = r"\d{2}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}\.\d+"
        assert re.match(
            pattern, timestamp
        ), f"Timestamp {timestamp} doesn't match expected format"

    def test_cavity_specific_pv_names(self, cavity_auto_setup):
        """Test PV names specific to cavity auto-setup."""
        assert "PROG" in cavity_auto_setup.progress.pvname
        assert "STATUS" in cavity_auto_setup.status.pvname
        assert "MSG" in cavity_auto_setup.status_message.pvname
        assert "TS" in cavity_auto_setup.time_stamp.pvname

    @pytest.mark.asyncio
    async def test_status_putter_with_int(self, cavity_auto_setup):
        """Test status putter with integer value."""
        with patch.object(
            cavity_auto_setup.status_sevr, "write", new_callable=AsyncMock
        ) as mock_write:
            await cavity_auto_setup.status.putter(None, 1)  # Running
            mock_write.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_status_putter_with_string(self, cavity_auto_setup):
        """Test status putter with string value."""
        with patch.object(
            cavity_auto_setup.status_sevr, "write", new_callable=AsyncMock
        ) as mock_write:
            await cavity_auto_setup.status.putter(None, "Error")
            mock_write.assert_called_once_with(
                2
            )  # Index of "Error" in enum list

    @pytest.mark.asyncio
    async def test_status_putter_all_values(self, cavity_auto_setup):
        """Test status putter with all possible values."""
        test_cases = [
            ("Ready", 0),
            ("Running", 1),
            ("Error", 2),
            (0, 0),
            (1, 1),
            (2, 2),
        ]

        for input_value, expected_output in test_cases:
            with patch.object(
                cavity_auto_setup.status_sevr, "write", new_callable=AsyncMock
            ) as mock_write:
                await cavity_auto_setup.status.putter(None, input_value)
                mock_write.assert_called_once_with(expected_output)

    @pytest.mark.asyncio
    async def test_trigger_setup_script(
        self, cavity_auto_setup, mock_subprocess
    ):
        """Test cavity setup script triggering."""
        with patch(
            "sc_linac_physics.utils.simulation.auto_setup_service.create_subprocess_exec",
            return_value=mock_subprocess,
        ) as mock_create:
            await cavity_auto_setup.trigger_setup_script()

            mock_create.assert_called_once_with(
                "sc-setup-cav",
                "-cm=01",
                "-cav=1",
            )

    @pytest.mark.asyncio
    async def test_trigger_shutdown_script(
        self, cavity_auto_setup, mock_subprocess
    ):
        """Test cavity shutdown script triggering."""
        with patch(
            "sc_linac_physics.utils.simulation.auto_setup_service.create_subprocess_exec",
            return_value=mock_subprocess,
        ) as mock_create:
            await cavity_auto_setup.trigger_shutdown_script()

            mock_create.assert_called_once_with(
                "sc-setup-cav",
                "-cm=01",
                "-cav=1",
                "-off",
            )

    def test_different_cavity_configurations(self):
        """Test AutoSetupCavityPVGroup with different CM and cavity numbers."""
        test_cases = [("01", 1), ("02", 8), ("H1", 4), ("25", 5)]

        for cm_name, cav_num in test_cases:
            group = AutoSetupCavityPVGroup(
                f"TEST:CM{cm_name}:{cav_num}0:", cm_name, cav_num
            )
            assert group.cm_name == cm_name
            assert group.cav_num == cav_num
            assert group.prefix == f"TEST:CM{cm_name}:{cav_num}0:AUTO:"


class TestSubprocessIntegration:
    """Test subprocess execution integration."""

    @pytest.mark.asyncio
    async def test_subprocess_error_handling(self):
        """Test subprocess execution with errors."""
        cm_group = AutoSetupCMPVGroup("TEST:", "01")

        # Mock subprocess that raises an exception
        with patch(
            "sc_linac_physics.utils.simulation.auto_setup_service.create_subprocess_exec",
            side_effect=OSError("Script not found"),
        ):
            with pytest.raises(OSError):
                await cm_group.trigger_setup_script()


class TestErrorHandling:
    """Test error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_invalid_status_string(self, cavity_auto_setup):
        """Test status putter with invalid string value."""
        with patch.object(
            cavity_auto_setup.status_sevr, "write", new_callable=AsyncMock
        ):
            with pytest.raises(ValueError):
                await cavity_auto_setup.status.putter(None, "InvalidStatus")

    def test_property_access(self, base_auto_setup):
        """Test that all properties are accessible."""
        properties = [
            "setup_start",
            "setup_stop",
            "setup_status",
            "setup_timestamp",
            "ssa_cal",
            "tune",
            "cav_char",
            "ramp",
            "off_start",
            "off_stop",
            "off_status",
            "off_timestamp",
            "note",
            "abort",
        ]

        for prop_name in properties:
            assert hasattr(base_auto_setup, prop_name)
            prop = getattr(base_auto_setup, prop_name)
            assert hasattr(prop, "value")
            assert hasattr(prop, "pvname")

    def test_cavity_additional_properties(self, cavity_auto_setup):
        """Test cavity-specific additional properties."""
        additional_props = [
            "progress",
            "status_sevr",
            "status",
            "status_message",
            "time_stamp",
        ]

        for prop_name in additional_props:
            assert hasattr(cavity_auto_setup, prop_name)
            if (
                prop_name != "status_sevr"
            ):  # SeverityProp might have different interface
                prop = getattr(cavity_auto_setup, prop_name)
                assert hasattr(prop, "value")


class TestIntegrationScenarios:
    """Test complete integration scenarios."""

    @pytest.mark.asyncio
    async def test_complete_setup_workflow(
        self, cm_auto_setup, mock_subprocess
    ):
        """Test a complete setup workflow."""
        with patch(
            "sc_linac_physics.utils.simulation.auto_setup_service.create_subprocess_exec",
            return_value=mock_subprocess,
        ) as mock_create:
            # Trigger setup
            await cm_auto_setup.setup_start.putter(None, 1)

            # Verify setup script was called
            assert mock_create.call_count == 1
            call_args = mock_create.call_args[0]
            assert "sc-setup-cm" in call_args
            assert "-cm=01" in call_args

    @pytest.mark.asyncio
    async def test_complete_shutdown_workflow(
        self, linac_auto_setup, mock_subprocess
    ):
        """Test a complete shutdown workflow."""
        with patch(
            "sc_linac_physics.utils.simulation.auto_setup_service.create_subprocess_exec",
            return_value=mock_subprocess,
        ) as mock_create:
            # Trigger shutdown
            await linac_auto_setup.off_start.putter(None, 1)

            # Verify shutdown script was called
            assert mock_create.call_count == 1
            call_args = mock_create.call_args[0]
            assert "sc-setup-linac" in call_args
            assert "-l=1" in call_args
            assert "-off" in call_args

    @pytest.mark.asyncio
    async def test_cavity_status_workflow(self, cavity_auto_setup):
        """Test cavity status update workflow."""
        with patch.object(
            cavity_auto_setup.status_sevr, "write", new_callable=AsyncMock
        ) as mock_write:
            # Test status progression
            await cavity_auto_setup.status.putter(None, "Running")
            mock_write.assert_called_with(1)

            await cavity_auto_setup.status.putter(None, "Error")
            mock_write.assert_called_with(2)

            await cavity_auto_setup.status.putter(None, "Ready")
            mock_write.assert_called_with(0)


class TestPropertyCharacteristics:
    """Test property characteristics and behavior."""

    def test_boolean_like_properties_behavior(self, base_auto_setup):
        """Test boolean-like properties behave correctly."""
        bool_props = [
            base_auto_setup.setup_start,
            base_auto_setup.setup_stop,
            base_auto_setup.ssa_cal,
            base_auto_setup.off_start,
        ]

        for prop in bool_props:
            # Should have integer-like values (0 or 1)
            assert isinstance(prop.value, (int, bool))
            assert prop.value in [0, 1, True, False]

    def test_property_write_capabilities(self, base_auto_setup):
        """Test that properties can be written to."""
        writeable_props = [
            base_auto_setup.setup_start,
            base_auto_setup.ssa_cal,
            base_auto_setup.tune,
            base_auto_setup.note,
        ]

        for prop in writeable_props:
            assert hasattr(prop, "write")
            assert callable(prop.write)

    def test_enum_like_properties_defaults(self, base_auto_setup):
        """Test enum-like properties have reasonable defaults."""
        enum_props = [
            (base_auto_setup.tune, 1),
            (base_auto_setup.cav_char, 1),
            (base_auto_setup.ramp, 1),
            (base_auto_setup.abort, 0),
        ]

        for prop, expected_default in enum_props:
            assert prop.value == expected_default


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
