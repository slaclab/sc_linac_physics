from caproto import ChannelType
from caproto.server import (
    PVGroup,
    PvpropertyEnum,
    PvpropertyFloat,
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
            "BAD Ripple",
            "BAD BACT",
            "No Control",
        ),
    )

    # The rest of the PVs Magnet (utils/sc_linac/magnet.py) names. Writes are
    # accepted and do nothing else: Magnet writes BDES and CTRL, and nothing
    # in this repo reads the others. CTRL, STATE and INTLKSUMY are the real
    # enums, from probes of QUAD:L0B:0185 on lcls-daemon0 (2026-10-13). The
    # sim starts healthy (Ready, ON, OK). The probed magnet read Ready, OFF,
    # FAULT at the time.
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
    control: PvpropertyEnum = pvproperty(
        value="Ready",
        name="CTRL",
        dtype=ChannelType.ENUM,
        enum_strings=(
            "Ready",
            "TRIM",
            "PERTURB",
            "BCON_TO_BDES",
            "BACT_TO_BDES",
            "SAVE_BDES",
            "LOAD_BDES",
            "UNDO_BDES",
            "DAC_ZERO",
            "CALB",
            "STDZ",
            "RESET",
            "TURN_ON",
            "TURN_OFF",
            "DEGAUSS",
        ),
    )
    ps_state: PvpropertyEnum = pvproperty(
        value="ON",
        name="STATE",
        dtype=ChannelType.ENUM,
        enum_strings=("OFF", "ON"),
    )
    interlock: PvpropertyEnum = pvproperty(
        value="OK",
        name="INTLKSUMY",
        dtype=ChannelType.ENUM,
        enum_strings=("OK", "FAULT"),
    )
