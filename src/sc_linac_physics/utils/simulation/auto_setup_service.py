import os
from asyncio import create_subprocess_exec
from datetime import datetime
from typing import List

from caproto import ChannelType
from caproto.server import (
    PvpropertyBoolEnum,
    pvproperty,
    PvpropertyEnum,
    PvpropertyFloat,
    PvpropertyChar,
)

from utils.simulation.launcher_pv_group import LauncherPVGroup
from utils.simulation.severity_prop import SeverityProp


class AutoSetupPVGroup(LauncherPVGroup):

    def __init__(self, prefix: str, script_args: List[str] = None):
        self.launcher_dir = os.path.join(
            self.srf_root_dir, "applications/auto_setup/launcher"
        )
        super().__init__(prefix + "AUTO:")
        self.script_args = script_args


class AutoSetupCMPVGroup(AutoSetupPVGroup):
    def __init__(self, prefix: str, cm_name: str):
        super().__init__(prefix)
        self.cm_name: str = cm_name

    async def trigger_setup_script(self):
        await create_subprocess_exec(
            "python",
            os.path.join(self.launcher_dir, "srf_cm_setup_launcher.py"),
            f"-cm={self.cm_name}",
        )

    async def trigger_shutdown_script(self):
        await create_subprocess_exec(
            "python",
            os.path.join(self.launcher_dir, "srf_cm_setup_launcher.py"),
            f"-cm={self.cm_name}",
            "-off",
        )


class AutoSetupLinacPVGroup(AutoSetupPVGroup):
    def __init__(self, prefix: str, linac_idx: int):
        super().__init__(prefix)
        self.linac_idx: int = linac_idx

    async def trigger_setup_script(self):
        await create_subprocess_exec(
            "python",
            os.path.join(self.launcher_dir, "srf_linac_setup_launcher.py"),
            f"-cm={self.linac_idx}",
        )

    async def trigger_shutdown_script(self):
        await create_subprocess_exec(
            "python",
            os.path.join(self.launcher_dir, "srf_linac_setup_launcher.py"),
            f"-cm={self.linac_idx}",
            "-off",
        )


class AutoSetupGlobalPVGroup(AutoSetupPVGroup):
    def __init__(self, prefix: str):
        super().__init__(prefix)

    async def trigger_setup_script(self):
        await create_subprocess_exec(
            "python",
            os.path.join(self.launcher_dir, "srf_global_setup_launcher.py"),
        )

    async def trigger_shutdown_script(self):
        await create_subprocess_exec(
            "python",
            os.path.join(self.launcher_dir, "srf_global_setup_launcher.py"),
            "-off",
        )


class AutoSetupCavityPVGroup(AutoSetupPVGroup):
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
    setup_stop: PvpropertyBoolEnum = pvproperty(name="SETUPSTOP")

    ssa_cal: PvpropertyBoolEnum = pvproperty(name="SETUP_SSAREQ")
    tune: PvpropertyEnum = pvproperty(name="SETUP_TUNEREQ")
    cav_char: PvpropertyEnum = pvproperty(name="SETUP_CHARREQ")
    ramp: PvpropertyEnum = pvproperty(name="SETUP_RAMPREQ")

    def __init__(self, prefix: str, cm_name: str, cav_num: int):
        super().__init__(prefix)
        self.cm_name: str = cm_name
        self.cav_num: int = cav_num

    @status.putter
    async def status(self, instance, value):
        if isinstance(value, int):
            await self.status_sevr.write(value)
        else:
            await self.status_sevr.write(["Ready", "Running", "Error"].index(value))

    async def trigger_setup_script(self):
        await create_subprocess_exec(
            "python",
            os.path.join(self.launcher_dir, "srf_cavity_setup_launcher.py"),
            f"-cm={self.cm_name}",
            f"-cav={self.cav_num}",
        )

    async def trigger_shutdown_script(self):
        await create_subprocess_exec(
            "python",
            os.path.join(self.launcher_dir, "srf_cavity_setup_launcher.py"),
            f"-cm={self.cm_name}",
            f"-cav={self.cav_num}",
            "-off",
        )
