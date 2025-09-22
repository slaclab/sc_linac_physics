from caproto import ChannelType
from caproto.server import pvproperty


class SeverityProp(pvproperty):
    def __init__(self, name, value, **cls_kwargs):
        super().__init__(
            name=name + ".SEVR",
            value=value,
            dtype=ChannelType.ENUM,
            enum_strings=("NO_ALARM", "MINOR", "MAJOR", "INVALID"),
            **cls_kwargs,
        )
