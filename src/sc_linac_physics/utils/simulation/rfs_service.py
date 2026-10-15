from caproto import ChannelType
from caproto.server import (
    PVGroup,
    pvproperty,
    PvpropertyInteger,
)


class RFStationPVGroup(PVGroup):
    rfs: PvpropertyInteger = pvproperty(
        value=5, name="DAC_AMPLITUDE", dtype=ChannelType.LONG
    )
