from datetime import datetime
from random import randrange, randint

from caproto import ChannelType
from caproto.server import (
    PVGroup,
    PvpropertyFloat,
    pvproperty,
    PvpropertyFloatRO,
    PvpropertyEnum,
    PvpropertyEnumRO,
    PvpropertyString,
    PvpropertyChar,
    PvpropertyInteger,
    PvpropertyBoolEnum,
)


class CavityPVGroup(PVGroup):
    acon: PvpropertyFloat = pvproperty(value=16.6, name="ACON", precision=2)
    ades: PvpropertyFloat = pvproperty(value=16.6, name="ADES", precision=1)
    aact: PvpropertyFloatRO = pvproperty(
        value=16.6, name="AACT", read_only=True, precision=1
    )
    amean: PvpropertyFloatRO = pvproperty(
        value=16.6, name="AACTMEAN", read_only=True, precision=1
    )
    gdes: PvpropertyFloat = pvproperty(value=16.0, name="GDES", precision=1)
    gact: PvpropertyFloatRO = pvproperty(
        value=16.0, name="GACT", read_only=True, precision=1
    )
    rf_state_des: PvpropertyEnum = pvproperty(
        value=1, name="RFCTRL", dtype=ChannelType.ENUM, enum_strings=("Off", "On")
    )
    # Defaults to pulse
    rf_mode_des: PvpropertyEnum = pvproperty(
        value=4,
        name="RFMODECTRL",
        dtype=ChannelType.ENUM,
        enum_strings=("SELAP", "SELA", "SEL", "SEL Raw", "Pulse", "Chirp"),
    )
    # Defaults to on
    rf_state_act: PvpropertyEnumRO = pvproperty(
        value=1,
        name="RFSTATE",
        dtype=ChannelType.ENUM,
        enum_strings=("Off", "On"),
        read_only=False,
    )
    # Defaults to pulse
    rf_mode_act: PvpropertyEnumRO = pvproperty(
        value=0,
        name="RFMODE",
        dtype=ChannelType.ENUM,
        enum_strings=("SELAP", "SELA", "SEL", "SEL Raw", "Pulse", "Chirp"),
        read_only=True,
    )
    adesMaxSRF: PvpropertyFloat = pvproperty(
        value=21, name="ADES_MAX_SRF", dtype=ChannelType.FLOAT
    )
    adesMax: PvpropertyFloat = pvproperty(
        value=21, name="ADES_MAX", dtype=ChannelType.FLOAT
    )

    pdes: PvpropertyFloat = pvproperty(value=0.0, name="PDES")
    pmean: PvpropertyFloat = pvproperty(value=0.0, name="PMEAN")
    pact: PvpropertyFloatRO = pvproperty(value=0.0, name="PACT", read_only=True)
    rfPermit: PvpropertyEnum = pvproperty(
        value=1,
        name="RFPERMIT",
        dtype=ChannelType.ENUM,
        enum_strings=("RF inhibit", "RF allow"),
    )
    rf_ready_for_beam: PvpropertyEnum = pvproperty(
        value=1,
        name="RFREADYFORBEAM",
        dtype=ChannelType.ENUM,
        enum_strings=("Not Ready", "Ready"),
    )
    parked: PvpropertyEnum = pvproperty(
        value=0,
        name="PARK",
        dtype=ChannelType.ENUM,
        enum_strings=("Not parked", "Parked"),
        record="mbbi",
    )
    # Cavity Summary Display PVs
    cudStatus: PvpropertyString = pvproperty(
        value="TLC", name="CUDSTATUS", dtype=ChannelType.STRING
    )
    cudSevr: PvpropertyEnum = pvproperty(
        value=1,
        name="CUDSEVR",
        dtype=ChannelType.ENUM,
        enum_strings=(
            "NO_ALARM",
            "MINOR",
            "MAJOR",
            "INVALID",
            "MAINTENANCE",
            "OFFLINE",
            "READY",
        ),
    )
    cudDesc: PvpropertyChar = pvproperty(
        value="Name", name="CUDDESC", dtype=ChannelType.CHAR
    )
    ssa_latch: PvpropertyEnum = pvproperty(
        value=0,
        name="SSA_LTCH",
        dtype=ChannelType.ENUM,
        enum_strings=("OK", "Fault"),
        record="mbbi",
    )
    sel_aset: PvpropertyFloat = pvproperty(
        value=0.0, name="SEL_ASET", dtype=ChannelType.FLOAT
    )
    landing_freq = randrange(-10000, 10000)
    detune: PvpropertyInteger = pvproperty(
        value=landing_freq, name="DFBEST", dtype=ChannelType.INT
    )
    detune_rfs: PvpropertyInteger = pvproperty(
        value=landing_freq, name="DF", dtype=ChannelType.INT
    )
    detune_chirp: PvpropertyInteger = pvproperty(
        value=landing_freq, name="CHIRP:DF", dtype=ChannelType.INT
    )
    tune_config: PvpropertyEnum = pvproperty(
        name="TUNE_CONFIG",
        value=0,
        dtype=ChannelType.ENUM,
        enum_strings=("On resonance", "Cold landing", "Parked", "Other"),
    )
    df_cold: PvpropertyFloat = pvproperty(
        value=randint(-10000, 200000), name="DF_COLD", dtype=ChannelType.FLOAT
    )
    step_temp: PvpropertyFloat = pvproperty(
        value=35.0, name="STEPTEMP", dtype=ChannelType.FLOAT
    )

    fscan_stat: PvpropertyEnum = pvproperty(
        name="FSCAN:SEARCHSTAT",
        value=0,
        dtype=ChannelType.ENUM,
        enum_strings=(
            "No errors",
            "None found",
            "Unknown mode",
            "Wrong freq",
            "Data nonsync",
        ),
    )
    fscan_sel: PvpropertyBoolEnum = pvproperty(
        name="FSCAN:SEL",
        value=0,
        dtype=ChannelType.ENUM,
        enum_strings=("Not Selected", "Selected"),
    )
    fscan_res = pvproperty(name="FSCAN:8PI9MODE", value=-800000)
    chirp_start: PvpropertyInteger = pvproperty(name="CHIRP:FREQ_START", value=-200000)
    chirp_stop: PvpropertyInteger = pvproperty(name="CHIRP:FREQ_STOP", value=200000)
    qloaded_new = pvproperty(name="QLOADED_NEW", value=4e7)
    scale_new = pvproperty(name="CAV:CAL_SCALEB_NEW", value=30)
    quench_bypass: PvpropertyEnum = pvproperty(
        name="QUENCH_BYP",
        value=0,
        dtype=ChannelType.ENUM,
        enum_strings=("Not Bypassed", "Bypassed"),
    )
    interlock_reset: PvpropertyEnum = pvproperty(
        dtype=ChannelType.ENUM,
        name="INTLK_RESET_ALL",
        enum_strings=("", "Reset"),
        value=0,
    )
    quench_latch: PvpropertyEnum = pvproperty(
        value=0,
        name="QUENCH_LTCH",
        dtype=ChannelType.ENUM,
        enum_strings=("Ok", "Fault"),
    )
    probe_cal_start: PvpropertyInteger = pvproperty(name="PROBECALSTRT", value=0)
    probe_cal_stat: PvpropertyEnum = pvproperty(
        name="PROBECALSTS",
        dtype=ChannelType.ENUM,
        value=1,
        enum_strings=("Crash", "Complete", "Running"),
    )
    probe_cal_time: PvpropertyString = pvproperty(
        name="PROBECALTS",
        dtype=ChannelType.STRING,
        value=datetime.now().strftime("%Y-%m-%d-%H:%M:%S"),
    )

    ssa_overrange: PvpropertyInteger = pvproperty(
        value=0, name="ASETSUB.VALQ", dtype=ChannelType.INT
    )

    push_ssa_slope: PvpropertyInteger = pvproperty(
        value=0, name="PUSH_SSA_SLOPE.PROC", dtype=ChannelType.INT
    )
    push_loaded_q: PvpropertyInteger = pvproperty(
        value=0, name="PUSH_QLOADED.PROC", dtype=ChannelType.INT
    )

    push_cav_scale: PvpropertyInteger = pvproperty(
        value=0, name="PUSH_CAV_SCALE.PROC", dtype=ChannelType.INT
    )

    data_decim_a: PvpropertyInteger = pvproperty(
        value=255, name="ACQ_DECIM_SEL.A", dtype=ChannelType.INT
    )
    data_decim_c: PvpropertyInteger = pvproperty(
        value=255, name="ACQ_DECIM_SEL.C", dtype=ChannelType.INT
    )

    calc_probe_q: PvpropertyInteger = pvproperty(
        value=0, name="QPROBE_CALC1.PROC", dtype=ChannelType.INT
    )
    sel_poff: PvpropertyFloat = pvproperty(
        value=0.0, name="SEL_POFF", dtype=ChannelType.FLOAT
    )

    q0: PvpropertyFloat = pvproperty(
        value=randrange(int(2.5e10), int(3.5e10), step=int(0.1e10)),
        name="Q0",
        dtype=ChannelType.FLOAT,
    )

    def __init__(self, prefix, isHL: bool):
        super().__init__(prefix)

        self.is_hl = isHL

        if isHL:
            self.length = 0.346
        else:
            self.length = 1.038

    @rf_mode_des.putter
    async def rf_mode_des(self, instance, value):
        await self.rf_mode_act.write(value)

    @probe_cal_start.putter
    async def probe_cal_start(self, instance, value):
        if value == 1:
            await self.probe_cal_time.write(
                datetime.now().strftime("%Y-%m-%d-%H:%M:%S")
            )
            await self.probe_cal_start.write(0)

    @interlock_reset.putter
    async def interlock_reset(self, instance, value):
        # TODO clear all other faults
        await self.quench_latch.write(0)
        await self.aact.write(self.ades.value)
        await self.amean.write(self.ades.value)

    @quench_latch.putter
    async def quench_latch(self, instance, value):
        await self.aact.write(0)
        await self.amean.write(0)

    @ades.putter
    async def ades(self, instance, value):
        await self.aact.write(value)
        await self.amean.write(value)
        gradient = value / self.length
        if self.gact.value != gradient:
            await self.gdes.write(gradient)

    @pdes.putter
    async def pdes(self, instance, value):
        value = value % 360
        await self.pact.write(value)
        await self.pmean.write(value)

    @gdes.putter
    async def gdes(self, instance, value):
        await self.gact.write(value)
        amplitude = value * self.length
        if self.aact.value != amplitude:
            await self.ades.write(amplitude)

    @rf_state_des.putter
    async def rf_state_des(self, instance, value):
        if value == "Off":
            await self.power_off()
        elif value == "On":
            await self.power_on()

    async def power_off(self):
        await self.amean.write(0)
        await self.aact.write(0)
        await self.gact.write(0)
        await self.rf_state_act.write("Off")

    async def power_on(self):
        await self.aact.write(self.ades.value)
        await self.amean.write(self.ades.value)
        await self.gact.write(self.gdes.value)
        await self.rf_state_act.write("On")
