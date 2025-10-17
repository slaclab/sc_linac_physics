from caproto import ChannelType
from caproto.server import PVGroup, pvproperty, PvpropertyEnum, PvpropertyFloat


class DecaradPVGroup(PVGroup):
    hv_ctrl: PvpropertyEnum = pvproperty(
        value=0,
        name="HVCTRL",
        dtype=ChannelType.ENUM,
        enum_strings=("On", "Off"),
    )
    hv_status: PvpropertyEnum = pvproperty(
        value=0,
        name="HVSTATUS",
        dtype=ChannelType.ENUM,
        enum_strings=("On", "Off"),
    )

    # TODO figure out an appropriate number and set to 0 when turned off
    voltage_readback: PvpropertyFloat = pvproperty(
        value=24.0, name="HVMON", precision=1
    )


class DecaradHeadPVGroup(PVGroup):
    avg_dose_rate: PvpropertyFloat = pvproperty(
        value=0.0, name="GAMMAAVE", precision=1
    )
