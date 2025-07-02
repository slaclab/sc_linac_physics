from caproto import ChannelType
from caproto.server import (
    PVGroup,
    pvproperty,
    PvpropertyFloat,
)


class RFStationPVGroup(PVGroup):
    rack_a_rfs1: PvpropertyFloat = pvproperty(
        value=5.0, name="RFS1A:DAC_AMPLITUDE", dtype=ChannelType.FLOAT
    )
    rack_a_rfs2: PvpropertyFloat = pvproperty(
        value=5.0, name="RFS2A:DAC_AMPLITUDE", dtype=ChannelType.FLOAT
    )
    rack_b_rfs1: PvpropertyFloat = pvproperty(
        value=5.0, name="RFS1B:DAC_AMPLITUDE", dtype=ChannelType.FLOAT
    )
    rack_b_rfs2: PvpropertyFloat = pvproperty(
        value=5.0, name="RFS2B:DAC_AMPLITUDE", dtype=ChannelType.FLOAT
    )

    @rack_a_rfs1.putter
    async def rack_a_rfs1(self, instance, value):
        await self.rack_a_rfs1.write(value)

    @rack_b_rfs1.putter
    async def rack_b_rfs1(self, instance, value):
        await self.rack_b_rfs1.write(value)

    @rack_a_rfs2.putter
    async def rack_a_rfs2(self, instance, value):
        await self.rack_a_rfs2.write(value)

    @rack_b_rfs2.putter
    async def rack_b_rfs2(self, instance, value):
        await self.rack_b_rfs2.write(value)
