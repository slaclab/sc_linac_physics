from caproto import ChannelType
from caproto.server import (
    PVGroup,
    PvpropertyEnum,
    pvproperty,
    PvpropertyInteger,
    PvpropertyDouble,
)

from sc_linac_physics.utils.simulation.severity_prop import SeverityProp


class CavFaultPVGroup(PVGroup):
    prl_fault: SeverityProp = SeverityProp(name="PRLSUM", value=0)
    cryo_summary: PvpropertyEnum = pvproperty(
        value=0, name="CRYO_LTCH", dtype=ChannelType.ENUM, enum_strings=("Ok", "Fault")
    )
    res_link_latch: PvpropertyEnum = pvproperty(
        value=0,
        name="RESLINK_LTCH",
        dtype=ChannelType.ENUM,
        enum_strings=("OK", "Fault"),
    )
    pll_latch: PvpropertyEnum = pvproperty(
        value=0, name="PLL_LTCH", dtype=ChannelType.ENUM, enum_strings=("Ok", "Fault")
    )
    pll_fault: PvpropertyEnum = pvproperty(
        value=0, name="PLL_FLT", dtype=ChannelType.ENUM, enum_strings=("Ok", "Fault")
    )
    ioc_watchdog_latch: PvpropertyEnum = pvproperty(
        value=0,
        name="IOCWDOG_LTCH",
        dtype=ChannelType.ENUM,
        enum_strings=("OK", "Fault"),
    )
    coupler_temp1_latch: PvpropertyEnum = pvproperty(
        value=0,
        name="CPLRTEMP1_LTCH",
        dtype=ChannelType.ENUM,
        enum_strings=("Ok", "Fault"),
    )
    coupler_temp2_latch: PvpropertyEnum = pvproperty(
        value=0,
        name="CPLRTEMP2_LTCH",
        dtype=ChannelType.ENUM,
        enum_strings=("Ok", "Faulted"),
    )
    stepper_temp_latch: PvpropertyEnum = pvproperty(
        value=0,
        name="STEPTEMP_LTCH",
        dtype=ChannelType.ENUM,
        enum_strings=("Ok", "Fault"),
    )
    res_chas_sum: PvpropertyEnum = pvproperty(
        value=0,
        name="RESINTLK_LTCH",
        dtype=ChannelType.ENUM,
        enum_strings=("Ok", "Fault"),
    )
    cavity_controller: PvpropertyEnum = SeverityProp(
        value=0,
        name="CTRL_SUM",
    )

    amp_feedback_sum: PvpropertyEnum = pvproperty(
        value=0,
        name="AMPFB_SUM",
        dtype=ChannelType.ENUM,
        enum_strings=("Not clipped", "Clipped RF-only mode", "Clipped beam mode"),
    )
    phase_feedback_sum: PvpropertyEnum = pvproperty(
        value=0,
        name="PHAFB_SUM",
        dtype=ChannelType.ENUM,
        enum_strings=("Not clipped", "Clipped RF-only mode", "Clipped beam mode"),
    )
    feedback_sum: PvpropertyEnum = pvproperty(
        value=0,
        name="FB_SUM",
        dtype=ChannelType.ENUM,
        enum_strings=("Not clipped", "Clipped RF-only mode", "Clipped beam mode"),
    )
    cavity_characterization: PvpropertyEnum = pvproperty(
        value=0,
        name="CAV:CALSTATSUM",
        dtype=ChannelType.ENUM,
        enum_strings=("", "", "Fault"),
    )
    offline: PvpropertyEnum = pvproperty(
        name="HWMODE",
        value=0,
        dtype=ChannelType.ENUM,
        enum_strings=("Online", "Maintenance", "Offline", "Maintenance Done", "Ready"),
    )
    check_phase: PvpropertyInteger = pvproperty(name="CKPSUM", value=0, dtype=ChannelType.INT)
    quench_interlock: PvpropertyEnum = pvproperty(
        name="QUENCH_BYP_RBV",
        value=0,
        dtype=ChannelType.ENUM,
        enum_strings=("Not Bypassed", "Bypassed"),
    )
    amplitude_tol: PvpropertyEnum = SeverityProp(
        name="AACTMEAN",
        value=0,
    )
    phase_tol: PvpropertyEnum = SeverityProp(
        name="PACTMEAN",
        value=0,
    )
    local_oscillator: PvpropertyEnum = pvproperty(
        name="LO_LTCH", value=0, dtype=ChannelType.ENUM, enum_strings=("Ok", "Fault")
    )
    waveform_acquisition: PvpropertyDouble = pvproperty(name="WFACQSUM", value=0, dtype=ChannelType.DOUBLE)
    detune_feedback: PvpropertyDouble = pvproperty(name="FBSTATSUM", value=0, dtype=ChannelType.DOUBLE)


class PPSPVGroup(PVGroup):
    ready_a = pvproperty(
        value=1,
        dtype=ChannelType.ENUM,
        name="BeamReadyA",
        enum_strings=("Not_Ready", "Ready"),
        record="mbbi",
    )
    ready_b = pvproperty(
        value=1,
        dtype=ChannelType.ENUM,
        name="BeamReadyB",
        enum_strings=("Not_Ready", "Ready"),
        record="mbbi",
    )


class BSOICPVGroup(PVGroup):
    sum_a = pvproperty(
        value=1,
        dtype=ChannelType.ENUM,
        name="SumyA",
        enum_strings=("FAULT", "OK"),
        record="mbbi",
    )
    sum_b = pvproperty(
        value=1,
        dtype=ChannelType.ENUM,
        name="SumyB",
        enum_strings=("FAULT", "OK"),
        record="mbbi",
    )


class BeamlineVacuumPVGroup(PVGroup):
    rackA = pvproperty(
        value=0,
        name="BMLNVACA_LTCH",
        dtype=ChannelType.ENUM,
        enum_strings=("Ok", "Fault"),
    )
    rackB = pvproperty(
        value=0,
        name="BMLNVACB_LTCH",
        dtype=ChannelType.ENUM,
        enum_strings=("Ok", "Fault"),
    )


class CouplerVacuumPVGroup(PVGroup):
    rackA = pvproperty(
        value=0,
        name="CPLRVACA_LTCH",
        dtype=ChannelType.ENUM,
        enum_strings=("Ok", "Fault"),
    )
    rackB = pvproperty(
        value=0,
        name="CPLRVACB_LTCH",
        dtype=ChannelType.ENUM,
        enum_strings=("Ok", "Fault"),
    )
