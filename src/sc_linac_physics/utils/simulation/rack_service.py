from asyncio import sleep

from caproto import ChannelType
from caproto.server import PVGroup, pvproperty, PvpropertyDouble

from sc_linac_physics.utils.simulation.severity_prop import SeverityProp

_FSCAN_STAT_SEARCH = 3
_FSCAN_STAT_DONE = 5


class RACKPVGroup(PVGroup):
    # HWINITSUM and FREQSUM are doubles on lcls-srv01 (2026-10-14), not
    # enums. Nothing here reads their labels.
    hwi = pvproperty(value=0.0, name="HWINITSUM", dtype=ChannelType.DOUBLE)
    fro = pvproperty(value=0.0, name="FREQSUM", dtype=ChannelType.DOUBLE)
    fscan_freq_start = pvproperty(value=0, name="FSCAN:FREQ_START")
    fscan_freq_stop = pvproperty(value=0, name="FSCAN:FREQ_STOP")
    fscan_thresh = pvproperty(
        value=0.0, name="FSCAN:RMS_THRESH", dtype=ChannelType.DOUBLE
    )
    fscan_overlap = pvproperty(
        value=0.0, name="FSCAN:MODE_OVERLAP", dtype=ChannelType.DOUBLE
    )
    fscan_start = pvproperty(
        value=0,
        name="FSCAN:START",
        dtype=ChannelType.ENUM,
        enum_strings=("", ""),
    )
    fscan_stat = pvproperty(
        value=0,
        name="FSCAN:STAT",
        dtype=ChannelType.ENUM,
        enum_strings=(
            "Await request",
            "No cav selected",
            "Bad range",
            "Search in progress",
            "Shift mode",
            "Scan done",
            "Scan aborted",
            "Freq restore fail",
        ),
    )
    prl = SeverityProp(value=0, name="PRLSUM")
    pjt: PvpropertyDouble = pvproperty(
        value=0, name="PRLJITSUM", dtype=ChannelType.DOUBLE
    )

    @fscan_start.putter
    async def fscan_start(self, instance, value):
        # Blank enum labels: the putter can't tell a 0 from a 1, so any put
        # starts a scan. START reads back 0 afterwards.
        await self.fscan_stat.write(_FSCAN_STAT_SEARCH)
        await sleep(3)
        await self.fscan_stat.write(_FSCAN_STAT_DONE)
        return 0
