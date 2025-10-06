import os
from unittest.mock import AsyncMock, patch

import pytest

from sc_linac_physics.utils.simulation.auto_setup_service import (
    AutoSetupPVGroup,
    AutoSetupCMPVGroup,
    AutoSetupLinacPVGroup,
    AutoSetupGlobalPVGroup,
    AutoSetupCavityPVGroup,
)


class TestAutoSetupPVGroup:
    """Test the base AutoSetupPVGroup class."""

    def test_init_with_default_args(self):
        """Test initialization with default arguments."""
        group = AutoSetupPVGroup("TEST:")

        assert group.prefix == "TEST:AUTO:"
        assert group.launcher_dir == os.path.join(group.srf_root_dir, "applications/auto_setup/launcher")
        assert group.script_args is None

    def test_init_with_script_args(self):
        """Test initialization with custom script arguments."""
        script_args = ["--verbose", "--dry-run"]
        group = AutoSetupPVGroup("TEST:", script_args=script_args)

        assert group.script_args == script_args

    def test_custom_srf_root_dir(self):
        """Test that srf_root_dir uses the expected default path."""
        group = AutoSetupPVGroup("TEST:")

        # Since srf_root_dir is set at class definition time and uses os.getenv with a default,
        # we can test that it's either the environment variable or the default path
        expected_default = os.path.expanduser("~/sc_linac_physics")
        env_var = os.getenv("SRF_ROOT_DIR")

        if env_var:
            assert group.srf_root_dir == env_var
        else:
            assert group.srf_root_dir == expected_default

        # Test the launcher_dir construction
        expected_launcher_dir = os.path.join(group.srf_root_dir, "applications/auto_setup/launcher")
        assert group.launcher_dir == expected_launcher_dir


class TestAutoSetupCMPVGroup:
    """Test the Cryomodule PV Group."""

    def test_init(self):
        """Test initialization sets cm_name correctly."""
        group = AutoSetupCMPVGroup("TEST:", "CM01")

        assert group.cm_name == "CM01"
        assert group.prefix == "TEST:AUTO:"

    @pytest.mark.asyncio
    @patch("sc_linac_physics.utils.simulation.auto_setup_service.create_subprocess_exec")
    async def test_trigger_setup_script(self, mock_subprocess):
        """Test setup script execution with correct arguments."""
        mock_subprocess.return_value = AsyncMock()
        group = AutoSetupCMPVGroup("TEST:", "CM01")

        await group.trigger_setup_script()

        expected_script_path = os.path.join(group.launcher_dir, "srf_cm_setup_launcher.py")
        mock_subprocess.assert_called_once_with("python", expected_script_path, "-cm=CM01")

    @pytest.mark.asyncio
    @patch("sc_linac_physics.utils.simulation.auto_setup_service.create_subprocess_exec")
    async def test_trigger_shutdown_script(self, mock_subprocess):
        """Test shutdown script execution with correct arguments."""
        mock_subprocess.return_value = AsyncMock()
        group = AutoSetupCMPVGroup("TEST:", "CM01")

        await group.trigger_shutdown_script()

        expected_script_path = os.path.join(group.launcher_dir, "srf_cm_setup_launcher.py")
        mock_subprocess.assert_called_once_with("python", expected_script_path, "-cm=CM01", "-off")


class TestAutoSetupLinacPVGroup:
    """Test the Linac PV Group."""

    def test_init(self):
        """Test initialization sets linac_idx correctly."""
        group = AutoSetupLinacPVGroup("TEST:", 2)

        assert group.linac_idx == 2
        assert group.prefix == "TEST:AUTO:"

    @pytest.mark.asyncio
    @patch("sc_linac_physics.utils.simulation.auto_setup_service.create_subprocess_exec")
    async def test_trigger_setup_script(self, mock_subprocess):
        """Test setup script execution with correct arguments."""
        mock_subprocess.return_value = AsyncMock()
        group = AutoSetupLinacPVGroup("TEST:", 2)

        await group.trigger_setup_script()

        expected_script_path = os.path.join(group.launcher_dir, "srf_linac_setup_launcher.py")
        mock_subprocess.assert_called_once_with(
            "python", expected_script_path, "-cm=2"  # Note: This might be a bug in the original code
        )

    @pytest.mark.asyncio
    @patch("sc_linac_physics.utils.simulation.auto_setup_service.create_subprocess_exec")
    async def test_trigger_shutdown_script(self, mock_subprocess):
        """Test shutdown script execution with correct arguments."""
        mock_subprocess.return_value = AsyncMock()
        group = AutoSetupLinacPVGroup("TEST:", 2)

        await group.trigger_shutdown_script()

        expected_script_path = os.path.join(group.launcher_dir, "srf_linac_setup_launcher.py")
        mock_subprocess.assert_called_once_with(
            "python", expected_script_path, "-cm=2", "-off"  # Note: This might be a bug in the original code
        )


class TestAutoSetupGlobalPVGroup:
    """Test the Global PV Group."""

    def test_init(self):
        """Test initialization."""
        group = AutoSetupGlobalPVGroup("TEST:")

        assert group.prefix == "TEST:AUTO:"

    @pytest.mark.asyncio
    @patch("sc_linac_physics.utils.simulation.auto_setup_service.create_subprocess_exec")
    async def test_trigger_setup_script(self, mock_subprocess):
        """Test setup script execution with correct arguments."""
        mock_subprocess.return_value = AsyncMock()
        group = AutoSetupGlobalPVGroup("TEST:")

        await group.trigger_setup_script()

        expected_script_path = os.path.join(group.launcher_dir, "srf_global_setup_launcher.py")
        mock_subprocess.assert_called_once_with("python", expected_script_path)

    @pytest.mark.asyncio
    @patch("sc_linac_physics.utils.simulation.auto_setup_service.create_subprocess_exec")
    async def test_trigger_shutdown_script(self, mock_subprocess):
        """Test shutdown script execution with correct arguments."""
        mock_subprocess.return_value = AsyncMock()
        group = AutoSetupGlobalPVGroup("TEST:")

        await group.trigger_shutdown_script()

        expected_script_path = os.path.join(group.launcher_dir, "srf_global_setup_launcher.py")
        mock_subprocess.assert_called_once_with("python", expected_script_path, "-off")


class TestAutoSetupCavityPVGroup:
    """Test the Cavity PV Group with enhanced functionality."""

    def test_init(self):
        """Test initialization sets cavity parameters correctly."""
        group = AutoSetupCavityPVGroup("TEST:", "CM01", 3)

        assert group.cm_name == "CM01"
        assert group.cav_num == 3
        assert group.prefix == "TEST:AUTO:"

    def test_pv_initialization(self):
        """Test that all PVs are properly initialized."""
        group = AutoSetupCavityPVGroup("TEST:", "CM01", 3)

        # Check initial values
        assert group.progress.value == 0.0
        assert group.status.value == 0  # "Ready"
        assert group.status_message.value == "Ready"
        assert group.status_sevr.value == 0  # NO_ALARM

        # Check that timestamp is set to a reasonable value
        timestamp_str = group.time_stamp.value
        assert isinstance(timestamp_str, str)
        assert "/" in timestamp_str  # Basic format check
        assert ":" in timestamp_str  # Should have time component
        # Test that it follows the expected format pattern (MM/DD/YY HH:MM:SS.ssssss)
        import re

        timestamp_pattern = r"\d{2}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}\.\d{6}"
        assert re.match(timestamp_pattern, timestamp_str), f"Timestamp '{timestamp_str}' doesn't match expected format"

    @pytest.mark.asyncio
    async def test_status_putter_with_int(self):
        """Test status putter with integer value."""
        group = AutoSetupCavityPVGroup("TEST:", "CM01", 3)

        # Mock the severity PV write method
        group.status_sevr.write = AsyncMock()

        # Access the putter method directly
        status_putter = group.status.putter

        # Test with integer value
        await status_putter(group.status, 2)  # Error status

        group.status_sevr.write.assert_called_once_with(2)

    @pytest.mark.asyncio
    async def test_status_putter_with_string(self):
        """Test status putter with string value."""
        group = AutoSetupCavityPVGroup("TEST:", "CM01", 3)

        # Mock the severity PV write method
        group.status_sevr.write = AsyncMock()

        # Access the putter method directly
        status_putter = group.status.putter

        # Test with string value
        await status_putter(group.status, "Running")

        group.status_sevr.write.assert_called_once_with(1)  # Index of "Running"

    @pytest.mark.asyncio
    async def test_status_putter_with_invalid_string(self):
        """Test status putter with invalid string value raises ValueError."""
        group = AutoSetupCavityPVGroup("TEST:", "CM01", 3)

        # Mock the severity PV write method
        group.status_sevr.write = AsyncMock()

        # Access the putter method directly
        status_putter = group.status.putter

        # Test with invalid string value
        with pytest.raises(ValueError):
            await status_putter(group.status, "InvalidStatus")

    @pytest.mark.asyncio
    @patch("sc_linac_physics.utils.simulation.auto_setup_service.create_subprocess_exec")
    async def test_trigger_setup_script(self, mock_subprocess):
        """Test setup script execution with correct arguments."""
        mock_subprocess.return_value = AsyncMock()
        group = AutoSetupCavityPVGroup("TEST:", "CM01", 3)

        await group.trigger_setup_script()

        expected_script_path = os.path.join(group.launcher_dir, "srf_cavity_setup_launcher.py")
        mock_subprocess.assert_called_once_with("python", expected_script_path, "-cm=CM01", "-cav=3")

    @pytest.mark.asyncio
    @patch("sc_linac_physics.utils.simulation.auto_setup_service.create_subprocess_exec")
    async def test_trigger_shutdown_script(self, mock_subprocess):
        """Test shutdown script execution with correct arguments."""
        mock_subprocess.return_value = AsyncMock()
        group = AutoSetupCavityPVGroup("TEST:", "CM01", 3)

        await group.trigger_shutdown_script()

        expected_script_path = os.path.join(group.launcher_dir, "srf_cavity_setup_launcher.py")
        mock_subprocess.assert_called_once_with("python", expected_script_path, "-cm=CM01", "-cav=3", "-off")


class TestIntegration:
    """Integration tests for the auto setup system."""

    def test_hierarchy_inheritance(self):
        """Test that all classes properly inherit from their parents."""
        cavity_group = AutoSetupCavityPVGroup("TEST:", "CM01", 1)
        cm_group = AutoSetupCMPVGroup("TEST:", "CM01")
        linac_group = AutoSetupLinacPVGroup("TEST:", 1)
        global_group = AutoSetupGlobalPVGroup("TEST:")

        # All should inherit from AutoSetupPVGroup
        assert isinstance(cavity_group, AutoSetupPVGroup)
        assert isinstance(cm_group, AutoSetupPVGroup)
        assert isinstance(linac_group, AutoSetupPVGroup)
        assert isinstance(global_group, AutoSetupPVGroup)

        # All should have launcher_dir
        base_launcher_dir = os.path.join(cavity_group.srf_root_dir, "applications/auto_setup/launcher")
        assert cavity_group.launcher_dir == base_launcher_dir
        assert cm_group.launcher_dir == base_launcher_dir
        assert linac_group.launcher_dir == base_launcher_dir
        assert global_group.launcher_dir == base_launcher_dir

    @pytest.mark.asyncio
    @patch("sc_linac_physics.utils.simulation.auto_setup_service.create_subprocess_exec")
    async def test_all_groups_can_execute_scripts(self, mock_subprocess):
        """Test that all group types can execute their scripts without errors."""
        mock_subprocess.return_value = AsyncMock()

        groups = [
            AutoSetupCavityPVGroup("TEST:", "CM01", 1),
            AutoSetupCMPVGroup("TEST:", "CM01"),
            AutoSetupLinacPVGroup("TEST:", 1),
            AutoSetupGlobalPVGroup("TEST:"),
        ]

        for group in groups:
            # Test setup
            await group.trigger_setup_script()
            # Test shutdown
            await group.trigger_shutdown_script()

        # Should have been called twice per group (setup + shutdown)
        assert mock_subprocess.call_count == len(groups) * 2


class TestTimestampHandling:
    """Test timestamp handling in cavity group."""

    def test_timestamp_format(self):
        """Test that timestamp is formatted correctly."""
        # Create the group and test the timestamp format
        group = AutoSetupCavityPVGroup("TEST:", "CM01", 1)

        # Verify the timestamp follows the expected format
        timestamp_str = group.time_stamp.value
        assert isinstance(timestamp_str, str)

        # Test format pattern: MM/DD/YY HH:MM:SS.ssssss
        import re

        timestamp_pattern = r"\d{2}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}\.\d{6}"
        assert re.match(
            timestamp_pattern, timestamp_str
        ), f"Timestamp '{timestamp_str}' doesn't match expected format MM/DD/YY H :MM:SS.ssssss"

        # Test that we can parse it back to a datetime object
        from datetime import datetime

        try:
            parsed_time = datetime.strptime(timestamp_str, "%m/%d/%y %H:%M:%S.%f")
            assert isinstance(parsed_time, datetime)
        except ValueError as e:
            pytest.fail(f"Timestamp '{timestamp_str}' is not parseable: {e}")


if __name__ == "__main__":
    pytest.main([__file__])
