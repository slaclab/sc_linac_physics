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
            start_prop = pvproperty(
                name=f"{launcher_name}STRT",
                dtype=ChannelType.ENUM,
                enum_strings=("Start", "Start"),
            )

            @start_prop.putter
            async def handle_start(self, instance, value):
                await self.trigger_start()
                return value

            namespace["start"] = start_prop

            # Stop property
            stop_prop = pvproperty(
                name=f"{launcher_name}STOP",
                dtype=ChannelType.ENUM,
                enum_strings=("Stop", "Stop"),
            )

            @stop_prop.putter
            async def handle_stop(self, instance, value):
                await self.trigger_stop()
                return value

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

            # Add Setup-specific properties
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

            # Handle OFF-specific init wrapping
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

    def get_command_args(self):
        """Build command arguments from script name, args, and extra flags"""
        args = [self.script_name]
        for key, value in self.script_args.items():
            args.append(f"-{key}={value}")
        args.extend(self.extra_flags)
        return args

    async def trigger_start(self):
        args = self.get_command_args()
        await create_subprocess_exec(*args)

    async def trigger_stop(self):
        await self.status.write("Stopped")


class BaseCMPVGroup(BaseScriptPVGroup):
    """Base class for CM launchers"""

    def __init__(self, prefix: str, cm_name: str):
        super().__init__(prefix, "sc-setup-cm", cm=cm_name)
        self.cm_name = cm_name


class SetupCMPVGroup(BaseCMPVGroup):
    LAUNCHER_NAME = "SETUP"


class OffCMPVGroup(BaseCMPVGroup):
    LAUNCHER_NAME = "OFF"


class BaseLinacPVGroup(BaseScriptPVGroup):
    """Base class for linac launchers"""

    def __init__(self, prefix: str, linac_idx: int):
        super().__init__(prefix, "sc-setup-linac", l=linac_idx)
        self.linac_idx = linac_idx


class SetupLinacPVGroup(BaseLinacPVGroup):
    LAUNCHER_NAME = "SETUP"


class OffLinacPVGroup(BaseLinacPVGroup):
    LAUNCHER_NAME = "OFF"


class BaseGlobalPVGroup(BaseScriptPVGroup):
    """Base class for global launchers"""

    def __init__(self, prefix: str):
        super().__init__(prefix, "sc-setup-all")


class SetupGlobalPVGroup(BaseGlobalPVGroup):
    LAUNCHER_NAME = "SETUP"


class OffGlobalPVGroup(BaseGlobalPVGroup):
    LAUNCHER_NAME = "OFF"


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
        super().__init__(prefix, "sc-setup-cavity", cm=cm_name, cav=cav_num)
        self.cm_name = cm_name
        self.cav_num = cav_num

    @status_enum.putter
    async def status_enum(self, instance, value):
        if isinstance(value, int):
            await self.status_sevr.write(value)
        else:
            await self.status_sevr.write(
                ["Ready", "Running", "Error"].index(value)
            )
        return value


class SetupCavityPVGroup(BaseCavityPVGroup):
    LAUNCHER_NAME = "SETUP"


class OffCavityPVGroup(BaseCavityPVGroup):
    LAUNCHER_NAME = "OFF"
