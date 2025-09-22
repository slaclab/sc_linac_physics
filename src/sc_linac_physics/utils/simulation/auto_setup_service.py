import os
from asyncio import create_subprocess_exec
from datetime import datetime
from typing import List

from caproto import ChannelType
from caproto.server import (
    PVGroup,
    PvpropertyBoolEnum,
    pvproperty,
    PvpropertyEnum,
    PvpropertyFloat,
    PvpropertyChar,
)

from sc_linac_physics.utils.simulation.severity_prop import SeverityProp


class AutoSetupPVGroup(PVGroup):
    srf_root_dir = os.getenv("SRF_ROOT_DIR", "/")
    launcher_dir = os.path.join(srf_root_dir, "applications/auto_setup/launcher")

    setup_start: PvpropertyBoolEnum = pvproperty(name="SETUPSTRT")
    setup_stop: PvpropertyBoolEnum = pvproperty(name="SETUPSTOP")
    setup_status: PvpropertyBoolEnum = pvproperty(name="SETUPSTS")
    setup_timestamp: PvpropertyBoolEnum = pvproperty(name="SETUPTS")

    ssa_cal: PvpropertyBoolEnum = pvproperty(name="SETUP_SSAREQ", value=True)
    tune: PvpropertyEnum = pvproperty(name="SETUP_TUNEREQ", value=True)
    cav_char: PvpropertyEnum = pvproperty(name="SETUP_CHARREQ", value=True)
    ramp: PvpropertyEnum = pvproperty(name="SETUP_RAMPREQ", value=True)

    off_start: PvpropertyBoolEnum = pvproperty(name="OFFSTRT")
    off_stop: PvpropertyBoolEnum = pvproperty(name="OFFSTOP")
    off_status: PvpropertyBoolEnum = pvproperty(name="OFFSTS")
    off_timestamp: PvpropertyBoolEnum = pvproperty(name="OFFTS")

    note: PvpropertyChar = pvproperty(
        name="NOTE",
        value="This is as long of a "
        "sentence as I can type "
        "in order to test wrapping",
    )

    abort: PvpropertyEnum = pvproperty(
        name="ABORT",
        dtype=ChannelType.ENUM,
        enum_strings=("No abort request", "Abort request"),
    )

    def __init__(self, prefix: str, script_args: List[str] = None):
        super().__init__(prefix + "AUTO:")
        self.script_args = script_args

    def trigger_setup_script(self):
        raise NotImplementedError

    def trigger_shutdown_script(self):
        raise NotImplementedError

    @setup_start.putter
    async def setup_start(self, instance, value):
        await self.trigger_setup_script()

    @off_start.putter
    async def off_start(self, instance, value):
        await self.trigger_shutdown_script()


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
    status_message: PvpropertyChar = pvproperty(
        name="MSG", value="Ready", dtype=ChannelType.CHAR
    )

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
