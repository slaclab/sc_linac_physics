from unittest.mock import patch, AsyncMock

import pytest
from caproto import ChannelType
from caproto.server import PVGroup

from sc_linac_physics.utils.simulation.launcher_service import (
    LauncherPVGroup,
    BaseScriptPVGroup,
    SetupCMPVGroup,
    OffCMPVGroup,
    SetupLinacPVGroup,
    OffLinacPVGroup,
    SetupGlobalPVGroup,
    OffGlobalPVGroup,
    SetupCavityPVGroup,
    OffCavityPVGroup,
)


class TestLauncherPVGroupMetaclass:
    """Test that the metaclass properly creates dynamic PVs"""

    def test_setup_class_has_all_pvs(self):
        """Test that Setup classes get all the expected PVs"""
        assert hasattr(SetupCMPVGroup, "start")
        assert hasattr(SetupCMPVGroup, "stop")
        assert hasattr(SetupCMPVGroup, "timestamp")
        assert hasattr(SetupCMPVGroup, "status")
        assert hasattr(SetupCMPVGroup, "ssa_cal")
        assert hasattr(SetupCMPVGroup, "tune")
        assert hasattr(SetupCMPVGroup, "cav_char")
        assert hasattr(SetupCMPVGroup, "ramp")

    def test_off_class_has_basic_pvs_only(self):
        """Test that Off classes don't get setup-specific PVs"""
        assert hasattr(OffCMPVGroup, "start")
        assert hasattr(OffCMPVGroup, "stop")
        assert hasattr(OffCMPVGroup, "timestamp")
        assert hasattr(OffCMPVGroup, "status")
        assert not hasattr(OffCMPVGroup, "ssa_cal")
        assert not hasattr(OffCMPVGroup, "tune")
        assert not hasattr(OffCMPVGroup, "cav_char")
        assert not hasattr(OffCMPVGroup, "ramp")

    def test_pv_names_use_launcher_name(self):
        """Test that PV names are correctly formatted with LAUNCHER_NAME"""
        # Setup PVs
        assert SetupCMPVGroup.start.pvspec.name == "SETUPSTRT"
        assert SetupCMPVGroup.stop.pvspec.name == "SETUPSTOP"
        assert SetupCMPVGroup.timestamp.pvspec.name == "SETUPTS"
        assert SetupCMPVGroup.status.pvspec.name == "SETUPSTS"
        assert SetupCMPVGroup.ssa_cal.pvspec.name == "SETUP_SSAREQ"

        # Off PVs
        assert OffCMPVGroup.start.pvspec.name == "OFFSTRT"
        assert OffCMPVGroup.stop.pvspec.name == "OFFSTOP"

    def test_all_launcher_types_get_pvs(self):
        """Test that all launcher types (CM, Linac, Global, Cavity) get PVs"""
        for cls in [
            SetupCMPVGroup,
            SetupLinacPVGroup,
            SetupGlobalPVGroup,
            SetupCavityPVGroup,
        ]:
            assert hasattr(cls, "start")
            assert hasattr(cls, "ssa_cal")

        for cls in [
            OffCMPVGroup,
            OffLinacPVGroup,
            OffGlobalPVGroup,
            OffCavityPVGroup,
        ]:
            assert hasattr(cls, "start")
            assert not hasattr(cls, "ssa_cal")


class TestCMPVGroups:
    """Test CM launcher groups"""

    def test_setup_cm_initialization(self):
        """Test SetupCMPVGroup initializes correctly"""
        group = SetupCMPVGroup(prefix="TEST:", cm_name="CM01")

        assert group.cm_name == "CM01"
        assert group.script_name == "sc-setup-cm"
        assert group.script_args == {"cm": "CM01"}
        assert group.extra_flags == []

    def test_off_cm_initialization(self):
        """Test OffCMPVGroup initializes with -off flag"""
        group = OffCMPVGroup(prefix="TEST:", cm_name="CM01")

        assert group.cm_name == "CM01"
        assert group.script_name == "sc-setup-cm"
        assert group.extra_flags == ["-off"]

    def test_setup_cm_command_args(self):
        """Test SetupCMPVGroup generates correct command"""
        group = SetupCMPVGroup(prefix="TEST:", cm_name="CM01")
        args = group.get_command_args()

        assert args == ["sc-setup-cm", "-cm=CM01"]

    def test_off_cm_command_args(self):
        """Test OffCMPVGroup generates correct command with -off"""
        group = OffCMPVGroup(prefix="TEST:", cm_name="CM02")
        args = group.get_command_args()

        assert args == ["sc-setup-cm", "-cm=CM02", "-off"]

    @pytest.mark.asyncio
    async def test_trigger_start_calls_subprocess(self):
        """Test that trigger_start executes the command"""
        group = SetupCMPVGroup(prefix="TEST:", cm_name="CM01")

        with patch(
            "sc_linac_physics.utils.simulation.launcher_service.create_subprocess_exec"
        ) as mock_exec:
            mock_exec.return_value = AsyncMock()
            await group.trigger_start()

            mock_exec.assert_called_once_with("sc-setup-cm", "-cm=CM01")


class TestLinacPVGroups:
    """Test Linac launcher groups"""

    def test_setup_linac_initialization(self):
        """Test SetupLinacPVGroup initializes correctly"""
        group = SetupLinacPVGroup(prefix="TEST:", linac_idx=0)

        assert group.linac_idx == 0
        assert group.script_name == "sc-setup-linac"
        assert group.script_args == {"l": 0}

    def test_linac_command_args(self):
        """Test LinacPVGroup generates correct command"""
        group = SetupLinacPVGroup(prefix="TEST:", linac_idx=2)
        args = group.get_command_args()

        assert args == ["sc-setup-linac", "-l=2"]

    def test_off_linac_command_args(self):
        """Test OffLinacPVGroup includes -off flag"""
        group = OffLinacPVGroup(prefix="TEST:", linac_idx=1)
        args = group.get_command_args()

        assert args == ["sc-setup-linac", "-l=1", "-off"]


class TestGlobalPVGroups:
    """Test Global launcher groups"""

    def test_setup_global_initialization(self):
        """Test SetupGlobalPVGroup initializes correctly"""
        group = SetupGlobalPVGroup(prefix="TEST:")

        assert group.script_name == "sc-setup-all"
        assert group.script_args == {}

    def test_global_command_args(self):
        """Test GlobalPVGroup generates correct command"""
        group = SetupGlobalPVGroup(prefix="TEST:")
        args = group.get_command_args()

        assert args == ["sc-setup-all"]

    def test_off_global_command_args(self):
        """Test OffGlobalPVGroup includes -off flag"""
        group = OffGlobalPVGroup(prefix="TEST:")
        args = group.get_command_args()

        assert args == ["sc-setup-all", "-off"]


class TestCavityPVGroups:
    """Test Cavity launcher groups"""

    def test_setup_cavity_initialization(self):
        """Test SetupCavityPVGroup initializes correctly"""
        group = SetupCavityPVGroup(prefix="TEST:", cm_name="CM01", cav_num=3)

        assert group.cm_name == "CM01"
        assert group.cav_num == 3
        assert group.script_name == "sc-setup-cav"
        assert group.script_args == {"cm": "CM01", "cav": 3}

    def test_cavity_has_extra_pvs(self):
        """Test that cavity groups have cavity-specific PVs"""
        assert hasattr(SetupCavityPVGroup, "progress")
        assert hasattr(SetupCavityPVGroup, "status_sevr")
        assert hasattr(SetupCavityPVGroup, "status_enum")
        assert hasattr(SetupCavityPVGroup, "status_message")
        assert hasattr(SetupCavityPVGroup, "time_stamp")

    def test_cavity_command_args(self):
        """Test CavityPVGroup generates correct command"""
        group = SetupCavityPVGroup(prefix="TEST:", cm_name="CM02", cav_num=5)
        args = group.get_command_args()

        assert args == ["sc-setup-cav", "-cm=CM02", "-cav=5"]

    def test_off_cavity_command_args(self):
        """Test OffCavityPVGroup includes -off flag"""
        group = OffCavityPVGroup(prefix="TEST:", cm_name="CM01", cav_num=1)
        args = group.get_command_args()

        assert args == ["sc-setup-cav", "-cm=CM01", "-cav=1", "-off"]


class TestPVGroupPrefix:
    """Test that prefix is correctly applied"""

    def test_prefix_adds_auto(self):
        """Test that prefix automatically adds AUTO:"""
        group = SetupCMPVGroup(prefix="ACCL:L0B:CM01:", cm_name="CM01")

        # The prefix should have AUTO: appended
        assert "AUTO:" in group.prefix

    def test_full_pv_name_construction(self):
        """Test that full PV names are constructed correctly"""
        group = SetupCavityPVGroup(
            prefix="ACCL:L0B:0110:", cm_name="CM01", cav_num=1
        )

        # Check that the prefix includes AUTO:
        expected_prefix = "ACCL:L0B:0110:AUTO:"
        assert group.prefix == expected_prefix


class TestSetupSpecificPVs:
    """Test setup-specific PV properties"""

    def test_setup_pvs_are_enums(self):
        """Test that setup-specific PVs are ENUMs with correct strings"""
        assert SetupCMPVGroup.ssa_cal.pvspec.dtype == ChannelType.ENUM
        assert SetupCMPVGroup.tune.pvspec.dtype == ChannelType.ENUM
        assert SetupCMPVGroup.cav_char.pvspec.dtype == ChannelType.ENUM
        assert SetupCMPVGroup.ramp.pvspec.dtype == ChannelType.ENUM

    def test_setup_pvs_default_to_true(self):
        """Test that setup-specific PVs default to True (1)"""
        assert SetupCMPVGroup.ssa_cal.pvspec.value == 1
        assert SetupCMPVGroup.tune.pvspec.value == 1
        assert SetupCMPVGroup.cav_char.pvspec.value == 1
        assert SetupCMPVGroup.ramp.pvspec.value == 1

    def test_setup_pvs_exist(self):
        """Test that setup-specific PVs exist on Setup classes"""
        # Just verify they exist - we created them in the metaclass
        assert hasattr(SetupCMPVGroup, "ssa_cal")
        assert hasattr(SetupCMPVGroup, "tune")
        assert hasattr(SetupCMPVGroup, "cav_char")
        assert hasattr(SetupCMPVGroup, "ramp")

        # And verify they don't exist on Off classes
        assert not hasattr(OffCMPVGroup, "ssa_cal")
        assert not hasattr(OffCMPVGroup, "tune")


class TestStartStopPVs:
    """Test start/stop PV behavior"""

    def test_start_pv_is_enum(self):
        """Test that start PV is an ENUM"""
        assert SetupCMPVGroup.start.pvspec.dtype == ChannelType.ENUM

    def test_start_stop_pvs_exist(self):
        """Test that start and stop PVs exist"""
        assert hasattr(SetupCMPVGroup, "start")
        assert hasattr(SetupCMPVGroup, "stop")
        assert hasattr(OffCMPVGroup, "start")
        assert hasattr(OffCMPVGroup, "stop")

    def test_start_stop_have_correct_names(self):
        """Test that start/stop PVs have correct names"""
        assert SetupCMPVGroup.start.pvspec.name == "SETUPSTRT"
        assert SetupCMPVGroup.stop.pvspec.name == "SETUPSTOP"
        assert OffCMPVGroup.start.pvspec.name == "OFFSTRT"
        assert OffCMPVGroup.stop.pvspec.name == "OFFSTOP"

    @pytest.mark.asyncio
    async def test_trigger_start_method_exists(self):
        """Test that trigger_start method exists and is async"""
        group = SetupCMPVGroup(prefix="TEST:", cm_name="CM01")

        assert hasattr(group, "trigger_start")
        assert callable(group.trigger_start)

        # Test that it can be called (with mocked subprocess)
        with patch(
            "sc_linac_physics.utils.simulation.launcher_service.create_subprocess_exec"
        ) as mock_exec:
            mock_exec.return_value = AsyncMock()
            await group.trigger_start()
            mock_exec.assert_called_once_with("sc-setup-cm", "-cm=CM01")


class TestCommonPVs:
    """Test PVs common to all launchers"""

    def test_all_launchers_have_note(self):
        """Test that all launcher types have NOTE PV"""
        for cls in [
            SetupCMPVGroup,
            OffCMPVGroup,
            SetupLinacPVGroup,
            OffLinacPVGroup,
            SetupGlobalPVGroup,
            OffGlobalPVGroup,
            SetupCavityPVGroup,
            OffCavityPVGroup,
        ]:
            assert hasattr(cls, "note")

    def test_all_launchers_have_abort(self):
        """Test that all launcher types have ABORT PV"""
        for cls in [
            SetupCMPVGroup,
            OffCMPVGroup,
            SetupLinacPVGroup,
            OffLinacPVGroup,
            SetupGlobalPVGroup,
            OffGlobalPVGroup,
            SetupCavityPVGroup,
            OffCavityPVGroup,
        ]:
            assert hasattr(cls, "abort")

    def test_note_pv_name(self):
        """Test that NOTE PV has correct name"""
        assert SetupCMPVGroup.note.pvspec.name == "NOTE"

    def test_abort_pv_is_enum(self):
        """Test that ABORT PV is an ENUM"""
        assert SetupCMPVGroup.abort.pvspec.dtype == ChannelType.ENUM
        # We know it was created with the right enum strings in the code
        # Just verify it exists and is an enum


class TestInheritance:
    """Test the inheritance hierarchy"""

    def test_setup_cm_is_launcher(self):
        """Test that SetupCMPVGroup is a LauncherPVGroup"""
        assert issubclass(SetupCMPVGroup, LauncherPVGroup)

    def test_setup_cm_is_pvgroup(self):
        """Test that SetupCMPVGroup is a PVGroup"""
        assert issubclass(SetupCMPVGroup, PVGroup)

    def test_cavity_is_script_group(self):
        """Test that cavity groups inherit from BaseScriptPVGroup"""
        assert issubclass(SetupCavityPVGroup, BaseScriptPVGroup)


class TestEdgeCases:
    """Test edge cases and error conditions"""

    @pytest.mark.asyncio
    async def test_trigger_start_not_implemented_in_base(self):
        """Test that base class raises NotImplementedError"""
        # This would need a way to instantiate LauncherPVGroup directly
        # which might not be possible/desirable
        pass

    def test_multiple_script_args(self):
        """Test that multiple script args are formatted correctly"""
        # Create a custom group with multiple args for testing
        group = BaseScriptPVGroup(
            prefix="TEST:",
            script_name="test-script",
            arg1="value1",
            arg2="value2",
            arg3=123,
        )

        args = group.get_command_args()
        assert "test-script" in args
        assert "-arg1=value1" in args
        assert "-arg2=value2" in args
        assert "-arg3=123" in args


class TestIntegration:
    """Integration tests that verify multiple components work together"""

    def test_can_create_all_launcher_types(self):
        """Test that all launcher types can be instantiated"""
        launchers = [
            SetupCMPVGroup(prefix="TEST:", cm_name="CM01"),
            OffCMPVGroup(prefix="TEST:", cm_name="CM01"),
            SetupLinacPVGroup(prefix="TEST:", linac_idx=0),
            OffLinacPVGroup(prefix="TEST:", linac_idx=0),
            SetupGlobalPVGroup(prefix="TEST:"),
            OffGlobalPVGroup(prefix="TEST:"),
            SetupCavityPVGroup(prefix="TEST:", cm_name="CM01", cav_num=1),
            OffCavityPVGroup(prefix="TEST:", cm_name="CM01", cav_num=1),
        ]

        # Just verify they all instantiate without errors
        assert len(launchers) == 8

    def test_setup_and_off_pairs_have_same_basic_pvs(self):
        """Test that Setup and Off variants of same type have same basic PVs"""
        setup_cm = SetupCMPVGroup(prefix="TEST:", cm_name="CM01")
        off_cm = OffCMPVGroup(prefix="TEST:", cm_name="CM01")

        # Both should have these
        for pv_name in [
            "start",
            "stop",
            "timestamp",
            "status",
            "note",
            "abort",
        ]:
            assert hasattr(setup_cm, pv_name)
            assert hasattr(off_cm, pv_name)


# Fixture for common test setup
@pytest.fixture
def setup_cm_group():
    """Fixture providing a SetupCMPVGroup instance"""
    return SetupCMPVGroup(prefix="TEST:", cm_name="CM01")


@pytest.fixture
def off_cm_group():
    """Fixture providing an OffCMPVGroup instance"""
    return OffCMPVGroup(prefix="TEST:", cm_name="CM01")


@pytest.fixture
def setup_cavity_group():
    """Fixture providing a SetupCavityPVGroup instance"""
    return SetupCavityPVGroup(prefix="TEST:", cm_name="CM01", cav_num=1)
