from asyncio import create_subprocess_exec
from datetime import datetime

from caproto import ChannelType
from caproto.server import (
    pvproperty,
    PvpropertyEnum,
    PvpropertyFloat,
    PvpropertyChar,
)

from sc_linac_physics.utils.simulation.launcher_service import LauncherPVGroup
from sc_linac_physics.utils.simulation.severity_prop import SeverityProp


class CavityPVGroup(LauncherPVGroup):
    progress: PvpropertyFloat = pvproperty(
        name="PROG", value=0.0, dtype=ChannelType.FLOAT
    )
    status_sevr: SeverityProp = SeverityProp(name="STATUS", value=0)
    status: PvpropertyEnum = pvproperty(
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
        super().__init__(prefix)
        self.cm_name: str = cm_name
        self.cav_num: int = cav_num

    @status.putter
    async def status(self, instance, value):
        if isinstance(value, int):
            await self.status_sevr.write(value)
        else:
            await self.status_sevr.write(
                ["Ready", "Running", "Error"].index(value)
            )

    async def trigger_setup_script(self):
        await create_subprocess_exec(
            "sc-setup-cav",
            f"-cm={self.cm_name}",
            f"-cav={self.cav_num}",
        )

    async def trigger_shutdown_script(self):
        await create_subprocess_exec(
            "sc-setup-cav",
            f"-cm={self.cm_name}",
            f"-cav={self.cav_num}",
            "-off",
        )
