import os

from caproto import ChannelType
from caproto.server import (
    PVGroup,
    PvpropertyBoolEnum,
    pvproperty,
    PvpropertyEnum,
    PvpropertyChar,
)


class LauncherPVGroup(PVGroup):
    srf_root_dir = os.getenv("SRF_ROOT_DIR", os.path.expanduser("~/sc_linac_physics"))

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
        value="This is as long of a " "sentence as I can type " "in order to test wrapping",
    )

    abort: PvpropertyEnum = pvproperty(
        name="ABORT",
        dtype=ChannelType.ENUM,
        enum_strings=("No abort request", "Abort request"),
    )

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
