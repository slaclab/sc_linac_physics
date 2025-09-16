from caproto import ChannelType
from caproto.server import (
    PVGroup,
    pvproperty,
    PvpropertyFloat,
)


class RFStationPVGroup(PVGroup):
    rfs: PvpropertyFloat = pvproperty(
        value=5.0, name="DAC_AMPLITUDE", dtype=ChannelType.FLOAT
    )
