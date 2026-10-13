from caproto import ChannelType
from caproto.server import (
    PVGroup,
    PvpropertyEnum,
    PvpropertyFloat,
    PvpropertyInteger,
    pvproperty,
)


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

    # The rest of the PVs Magnet (utils/sc_linac/magnet.py) names. Writes are
    # accepted and do nothing else. In this repo, Magnet writes BDES and CTRL
    # (CTRL values: linac_utils.MAGNET_*_VALUE), and nothing reads the
    # others.
    # CHECK: the real field types of CTRL, STATE and INTLKSUMY. They're
    # served as integers here.
    bdes: PvpropertyFloat = pvproperty(
        value=0.0, name="BDES", dtype=ChannelType.FLOAT
    )
    bact: PvpropertyFloat = pvproperty(
        value=0.0, name="BACT", dtype=ChannelType.FLOAT
    )
    ides: PvpropertyFloat = pvproperty(
        value=0.0, name="IDES", dtype=ChannelType.FLOAT
    )
    iact: PvpropertyFloat = pvproperty(
        value=0.0, name="IACT", dtype=ChannelType.FLOAT
    )
    control: PvpropertyInteger = pvproperty(
        value=0, name="CTRL", dtype=ChannelType.INT
    )
    ps_state: PvpropertyInteger = pvproperty(
        value=0, name="STATE", dtype=ChannelType.INT
    )
    interlock: PvpropertyInteger = pvproperty(
        value=0, name="INTLKSUMY", dtype=ChannelType.INT
    )
