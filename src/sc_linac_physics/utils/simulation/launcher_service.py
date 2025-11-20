import asyncio
from asyncio import create_subprocess_exec
from datetime import datetime

from caproto import ChannelType
from caproto.server import (
    PVGroup,
    pvproperty,
    PvpropertyChar,
    PvpropertyEnum,
    PvpropertyFloat,
)
from caproto.server.server import PVGroupMeta

from sc_linac_physics.utils.simulation.severity_prop import SeverityProp


class LauncherPVGroupMeta(PVGroupMeta):
    """Metaclass that adds launcher-specific PVs before PVGroup processes them"""

    def __new__(mcs, name, bases, namespace, **kwargs):
        # Check if this class has LAUNCHER_NAME set
        launcher_name = namespace.get("LAUNCHER_NAME")

        if launcher_name is not None:
            # Add dynamic properties to the namespace before the class is created

            # Start property
            async def _start_putter(obj, instance, value):
                await obj.trigger_start()
                return value

            start_prop = pvproperty(
                name=f"{launcher_name}STRT",
                dtype=ChannelType.ENUM,
                enum_strings=("Start", "Start"),
            ).putter(_start_putter)
            namespace["start"] = start_prop

            # Stop property
            async def _stop_putter(obj, instance, value):
                await obj.trigger_stop()
                return value

            stop_prop = pvproperty(
                name=f"{launcher_name}STOP",
                dtype=ChannelType.ENUM,
                enum_strings=("Stop", "Stop"),
            ).putter(_stop_putter)
            namespace["stop"] = stop_prop

            # Timestamp property
            namespace["timestamp"] = pvproperty(
                name=f"{launcher_name}TS",
                dtype=ChannelType.STRING,
                value="",
            )

            # Status property
            namespace["status"] = pvproperty(
                name=f"{launcher_name}STS",
                dtype=ChannelType.STRING,
                value="Ready",
            )

            # Add Setup-specific properties (SETUP is the most complex)
            if launcher_name == "SETUP":
                namespace["ssa_cal"] = pvproperty(
                    name=f"{launcher_name}_SSAREQ",
                    dtype=ChannelType.ENUM,
                    enum_strings=("False", "True"),
                    value=1,
                )
                namespace["tune"] = pvproperty(
                    name=f"{launcher_name}_TUNEREQ",
                    dtype=ChannelType.ENUM,
                    enum_strings=("False", "True"),
                    value=1,
                )
                namespace["cav_char"] = pvproperty(
                    name=f"{launcher_name}_CHARREQ",
                    dtype=ChannelType.ENUM,
                    enum_strings=("False", "True"),
                    value=1,
                )
                namespace["ramp"] = pvproperty(
                    name=f"{launcher_name}_RAMPREQ",
                    dtype=ChannelType.ENUM,
                    enum_strings=("False", "True"),
                    value=1,
                )

            # Handle OFF-specific init wrapping (only OFF needs the -off flag)
            if launcher_name == "OFF":
                original_init = namespace.get("__init__")
                if original_init is None:
                    # Find __init__ in base classes
                    for base in bases:
                        if hasattr(base, "__init__"):
                            original_init = base.__init__
                            break

                def new_init(self, *args, **kwargs):
                    original_init(self, *args, **kwargs)
                    self.extra_flags = ["-off"]

                namespace["__init__"] = new_init

        # Now let PVGroup's metaclass do its magic
        return super().__new__(mcs, name, bases, namespace, **kwargs)


class LauncherPVGroup(PVGroup, metaclass=LauncherPVGroupMeta):
    """Base class for all launcher types"""

    LAUNCHER_NAME = None

    note: PvpropertyChar = pvproperty(
        name="NOTE",
        value="This is as long of a sentence as I can type in order to test wrapping",
    )

    abort: PvpropertyEnum = pvproperty(
        name="ABORT",
        dtype=ChannelType.ENUM,
        enum_strings=("No abort request", "Abort request"),
    )

    def __init__(self, prefix: str):
        super().__init__(prefix + "AUTO:")
        self.subgroups = []

    @abort.putter
    async def _abort_putter(self, instance, value):
        await self.handle_abort()
        return value  # Keep the value that was written

    async def handle_abort(self):
        """Propagate abort to subgroups - applications detect the PV write"""
        for subgroup in self.subgroups:
            if hasattr(subgroup, "abort"):
                await subgroup.abort.write(1)

    async def trigger_start(self):
        """Override this in subclasses"""
        raise NotImplementedError

    async def trigger_stop(self):
        """Override this in subclasses"""
        raise NotImplementedError


class BaseScriptPVGroup(LauncherPVGroup):
    """Base class for script-based launchers"""

    def __init__(self, prefix: str, script_name: str, **script_args):
        super().__init__(prefix)
        self.script_name = script_name
        self.script_args = script_args
        self.extra_flags = []
        self.process = None

    def get_command_args(self):
        """Build command arguments from script name, args, and extra flags"""
        args = [self.script_name]
        for key, value in self.script_args.items():
            args.append(f"-{key}={value}")
        args.extend(self.extra_flags)
        return args

    async def trigger_start(self):
        if self.process and self.process.returncode is None:
            await self.status.write("Already running")
            return

        args = self.get_command_args()
        self.process = await create_subprocess_exec(*args)
        await self.timestamp.write(
            datetime.now().strftime("%m/%d/%y %H:%M:%S.%f")
        )
        await self.status.write("Running")
        asyncio.create_task(self._monitor_process())

    async def trigger_stop(self):
        if self.process:
            self.process.terminate()
            await self.process.wait()
        await self.timestamp.write(
            datetime.now().strftime("%m/%d/%y %H:%M:%S.%f")
        )
        await self.status.write("Stopped")

    async def _monitor_process(self):
        """Monitor process and update status when complete"""
        if self.process:
            returncode = await self.process.wait()
            await self.timestamp.write(
                datetime.now().strftime("%m/%d/%y %H:%M:%S.%f")
            )
            if returncode == 0:
                await self.status.write("Completed")
            else:
                await self.status.write(f"Failed (exit code: {returncode})")


class BaseCMPVGroup(BaseScriptPVGroup):
    """Base class for CM launchers"""

    def __init__(self, prefix: str, cm_name: str, cavity_groups=None):
        script_map = {
            "COLD": "sc-cold-cm",
            "PARK": "sc-park-cm",
        }
        script_name = script_map.get(self.LAUNCHER_NAME, "sc-setup-cm")
        super().__init__(prefix, script_name, cm=cm_name)
        self.cm_name = cm_name
        self.subgroups = cavity_groups or []


class BaseLinacPVGroup(BaseScriptPVGroup):
    """Base class for linac launchers"""

    def __init__(self, prefix: str, linac_idx: int, cm_groups=None):
        script_map = {
            "COLD": "sc-cold-linac",
            "PARK": "sc-park-linac",
        }
        script_name = script_map.get(self.LAUNCHER_NAME, "sc-setup-linac")
        super().__init__(prefix, script_name, l=linac_idx)
        self.linac_idx = linac_idx
        self.subgroups = cm_groups or []


class BaseGlobalPVGroup(BaseScriptPVGroup):
    """Base class for global launchers"""

    def __init__(self, prefix: str, linac_groups=None):
        script_map = {
            "COLD": "sc-cold-all",
            "PARK": "sc-park-all",
        }
        script_name = script_map.get(self.LAUNCHER_NAME, "sc-setup-all")
        super().__init__(prefix, script_name)
        self.subgroups = linac_groups or []


class BaseRackPVGroup(BaseScriptPVGroup):
    """Base class for rack launchers"""

    def __init__(
        self, prefix: str, cm_name: str, rack_name: str, rack_groups=None
    ):
        script_map = {
            "COLD": "sc-cold-rack",
            "PARK": "sc-park-rack",
        }
        script_name = script_map.get(self.LAUNCHER_NAME, "sc-setup-rack")
        # Use 'cm' and 'r' to match the script's short flags
        super().__init__(prefix, script_name, cm=cm_name, r=rack_name)
        self.cm_name = cm_name
        self.rack_name = rack_name
        self.subgroups = rack_groups or []


class BaseCavityPVGroup(BaseScriptPVGroup):
    """Base class for cavity launchers"""

    # Cavity-specific additional properties
    progress: PvpropertyFloat = pvproperty(
        name="PROG", value=0.0, dtype=ChannelType.FLOAT
    )
    status_sevr: SeverityProp = SeverityProp(name="STATUS", value=0)

    status_enum: PvpropertyEnum = pvproperty(
        name="STATUS",
        dtype=ChannelType.ENUM,
        enum_strings=("Ready", "Running", "Error"),
    )

    status_message: PvpropertyChar = pvproperty(name="MSG", value="Ready")

    time_stamp: PvpropertyChar = pvproperty(
        name="TS",
        value=datetime.now().strftime("%m/%d/%y %H:%M:%S.%f"),
        dtype=ChannelType.CHAR,
    )

    def __init__(self, prefix: str, cm_name: str, cav_num: int):
        script_map = {
            "COLD": "sc-cold-cav",
            "PARK": "sc-park-cav",
        }
        script_name = script_map.get(self.LAUNCHER_NAME, "sc-setup-cav")
        super().__init__(prefix, script_name, cm=cm_name, cav=cav_num)
        self.cm_name = cm_name
        self.cav_num = cav_num
        # Cavities don't have subgroups
        self.subgroups = []

    @status_enum.putter
    async def _status_enum_putter(self, instance, value):
        if isinstance(value, int):
            await self.status_sevr.write(value)
        else:
            await self.status_sevr.write(
                ["Ready", "Running", "Error"].index(value)
            )
        return value


# ============================================================================
# SETUP Launchers
# ============================================================================


class SetupCMPVGroup(BaseCMPVGroup):
    LAUNCHER_NAME = "SETUP"


class SetupLinacPVGroup(BaseLinacPVGroup):
    LAUNCHER_NAME = "SETUP"


class SetupGlobalPVGroup(BaseGlobalPVGroup):
    LAUNCHER_NAME = "SETUP"


class SetupCavityPVGroup(BaseCavityPVGroup):
    LAUNCHER_NAME = "SETUP"


class SetupRackPVGroup(BaseRackPVGroup):
    LAUNCHER_NAME = "SETUP"


# ============================================================================
# OFF Launchers
# ============================================================================


class OffCMPVGroup(BaseCMPVGroup):
    LAUNCHER_NAME = "OFF"


class OffLinacPVGroup(BaseLinacPVGroup):
    LAUNCHER_NAME = "OFF"


class OffGlobalPVGroup(BaseGlobalPVGroup):
    LAUNCHER_NAME = "OFF"


class OffCavityPVGroup(BaseCavityPVGroup):
    LAUNCHER_NAME = "OFF"


class OffRackPVGroup(BaseRackPVGroup):
    LAUNCHER_NAME = "OFF"


# ============================================================================
# COLD Launchers
# ============================================================================


class ColdCMPVGroup(BaseCMPVGroup):
    LAUNCHER_NAME = "COLD"


class ColdLinacPVGroup(BaseLinacPVGroup):
    LAUNCHER_NAME = "COLD"


class ColdGlobalPVGroup(BaseGlobalPVGroup):
    LAUNCHER_NAME = "COLD"


class ColdCavityPVGroup(BaseCavityPVGroup):
    LAUNCHER_NAME = "COLD"


class ColdRackPVGroup(BaseRackPVGroup):
    LAUNCHER_NAME = "COLD"


# ============================================================================
# PARK Launchers
# ============================================================================


class ParkCMPVGroup(BaseCMPVGroup):
    LAUNCHER_NAME = "PARK"


class ParkLinacPVGroup(BaseLinacPVGroup):
    LAUNCHER_NAME = "PARK"


class ParkGlobalPVGroup(BaseGlobalPVGroup):
    LAUNCHER_NAME = "PARK"


class ParkCavityPVGroup(BaseCavityPVGroup):
    LAUNCHER_NAME = "PARK"


class ParkRackPVGroup(BaseRackPVGroup):
    LAUNCHER_NAME = "PARK"
