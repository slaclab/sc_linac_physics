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
        enum_strings=("ON", "OFF"),
    )

    # TODO figure out an appropriate number and set to 0 when turned off
    voltage_readback: PvpropertyFloat = pvproperty(
        value=24.0, name="HVMON", precision=1
    )


class DecaradHeadPVGroup(PVGroup):
    avg_dose_rate: PvpropertyFloat = pvproperty(
        value=0.0, name="GAMMAAVE", precision=1
    )
    # The 1 Hz reading the MP processing FE pause reads. Starts at the
    # background DECARAD_BACKGROUND_READING_RAW (8), not 0.
    raw_dose_rate: PvpropertyFloat = pvproperty(
        value=8.0, name="GAMMA_DOSE_RATE", precision=1
    )
