from caproto import ChannelType
from caproto.server import PVGroup, PvpropertyEnum, pvproperty


class MAGNETPVGroup(PVGroup):
    cm_magnet_ps: PvpropertyEnum = pvproperty(
        value=0,
        dtype=ChannelType.ENUM,
        name="STATMSG",
        enum_strings=(
            "Good",
            "BCON Warning",
            "Offline",
            "PAU Ctrl",
            "Turned Off",
            "Not Degaus'd",
            "Not Cal'd",
            "Feedback Ctrl",
            "PS Tripped",
            "DAC Error",
            "ADC Error",
            "Not Stdz'd",
            "Out-of-Tol",
            "Bad Ripple",
            "BAD BACT",
            "No Control",
        ),
    )
