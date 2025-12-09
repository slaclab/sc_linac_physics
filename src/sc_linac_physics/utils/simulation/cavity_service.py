from datetime import datetime
from random import randrange, randint

import numpy as np
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
        value=1,
        name="RFCTRL",
        dtype=ChannelType.ENUM,
        enum_strings=("Off", "On"),
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
    chirp_start: PvpropertyInteger = pvproperty(
        name="CHIRP:FREQ_START", value=-200000
    )
    chirp_stop: PvpropertyInteger = pvproperty(
        name="CHIRP:FREQ_STOP", value=200000
    )
    qloaded = pvproperty(name="QLOADED", value=4e7)
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
    probe_cal_start: PvpropertyInteger = pvproperty(
        name="PROBECALSTRT", value=0
    )
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

    # Fault waveforms
    fltawf = pvproperty(
        value=np.zeros(2048, dtype=np.float64),
        name="CAV:FLTAWF",
        dtype=ChannelType.DOUBLE,
        max_length=2048,
        read_only=True,
        doc="Fault amplitude waveform (exponential decay during quench)",
    )

    flttwf = pvproperty(
        value=np.zeros(2048, dtype=np.float64),
        name="CAV:FLTTWF",
        dtype=ChannelType.DOUBLE,
        max_length=2048,
        read_only=True,
        doc="Fault time waveform (relative to quench event, t=0)",
    )

    # Control for simulating different quench types (for testing)
    quench_type: PvpropertyEnum = pvproperty(
        value=0,
        name="SIM:QUENCH_TYPE",
        dtype=ChannelType.ENUM,
        enum_strings=("Real", "Spurious", "Random"),
        doc="Simulated quench type for testing",
    )

    HL_LENGTH = 0.346
    NORMAL_LENGTH = 1.038
    HL_FREQ = 3.9e9
    NORMAL_FREQ = 1.3e9

    def __init__(self, prefix, isHL: bool):
        super().__init__(prefix)
        self.is_hl = isHL
        self.length = self.HL_LENGTH if isHL else self.NORMAL_LENGTH
        self.frequency = self.HL_FREQ if isHL else self.NORMAL_FREQ

    @quench_latch.putter
    async def quench_latch(self, instance, value):
        """Handle quench latch - capture waveforms then drop amplitude."""
        import sys

        print(
            f"DEBUG: quench_latch putter called! value={value}",
            file=sys.stderr,
            flush=True,
        )
        print(f"DEBUG: value type: {type(value)}", file=sys.stderr, flush=True)
        print(
            f"DEBUG: Current amplitude: {self.aact.value}",
            file=sys.stderr,
            flush=True,
        )

        # Enum values come through as strings, not integers
        if value == "Fault" or value == 1:
            quench_type = self._determine_quench_type()
            print(
                f"DEBUG: Generating {quench_type} quench",
                file=sys.stderr,
                flush=True,
            )
            await self._capture_quench_waveforms(quench_type)
            print("DEBUG: Waveforms captured", file=sys.stderr, flush=True)
        else:
            print(
                f"DEBUG: Not a fault trigger (value={value})",
                file=sys.stderr,
                flush=True,
            )

        await self.aact.write(0)
        await self.amean.write(0)
        print("DEBUG: Amplitude set to 0", file=sys.stderr, flush=True)

    def _determine_quench_type(self) -> str:
        """Determine what type of quench to simulate."""
        type_setting = self.quench_type.value

        if type_setting == 0:  # Real
            return "real"
        elif type_setting == 1:  # Spurious
            return "spurious"
        else:  # Random
            return "real" if np.random.random() > 0.3 else "spurious"

    async def _capture_quench_waveforms(self, quench_type: str = "real"):
        """Generate and store quench waveform data."""
        # Get current amplitude BEFORE it drops to zero
        pre_quench_amplitude = self.aact.value
        saved_loaded_q = self.qloaded_new.value

        self.log.info(
            f"Capturing waveforms: A={pre_quench_amplitude:.3f} MV, "
            f"Q={saved_loaded_q:.2e}"
        )

        # Validate we have reasonable values
        if pre_quench_amplitude <= 0:
            self.log.warning(
                f"Pre-quench amplitude is {pre_quench_amplitude}, using 16.6"
            )
            pre_quench_amplitude = 16.6

        if saved_loaded_q <= 0:
            self.log.warning(f"Loaded Q is {saved_loaded_q}, using 4e7")
            saved_loaded_q = 4e7

        # Determine effective Q based on quench type
        if quench_type == "spurious":
            effective_q = saved_loaded_q
            self.log.info("Simulating SPURIOUS quench (normal Q)")
        else:
            # Real quench: Q drops by 50-70%
            q_degradation_factor = np.random.uniform(0.3, 0.5)
            effective_q = saved_loaded_q * q_degradation_factor
            self.log.info(
                f"Simulating REAL quench (Q degraded by "
                f"{(1-q_degradation_factor)*100:.0f}%)"
            )

        # Generate waveforms
        time_wf, amplitude_wf = self._generate_decay_waveform(
            pre_quench_amplitude, effective_q
        )

        # Write to PVs
        await self.fltawf.write(amplitude_wf)
        await self.flttwf.write(time_wf)

        self.log.info(
            f"Waveforms written: {len(amplitude_wf)} points, "
            f"A0={amplitude_wf[512]:.3f} MV"
        )

    def _generate_decay_waveform(
        self, amplitude: float, loaded_q: float
    ) -> tuple:
        """
        Generate exponential decay waveform.

        Time is in SECONDS to match what validate_quench expects.

        Returns:
            Tuple of (time_array_in_seconds, amplitude_array)
        """
        total_points = 2048
        pre_quench_points = 512  # 25% before quench
        post_quench_points = total_points - pre_quench_points

        # Time in SECONDS (not microseconds)
        time_pre = np.linspace(-500e-6, 0, pre_quench_points, endpoint=False)
        time_post = np.linspace(0, 1500e-6, post_quench_points)
        time_wf = np.concatenate([time_pre, time_post])

        # Amplitude waveform
        amplitude_wf = np.zeros(total_points, dtype=np.float64)

        # Pre-quench: stable with small noise
        amplitude_wf[:pre_quench_points] = amplitude * (
            1 + 0.01 * np.random.randn(pre_quench_points)
        )

        # Post-quench: exponential decay
        # A(t) = A0 * e^((-π * f * t)/Q_loaded)
        # Time is already in seconds, no conversion needed
        decay_constant = (np.pi * self.frequency) / loaded_q
        amplitude_wf[pre_quench_points:] = amplitude * np.exp(
            -decay_constant * time_post
        )

        # Add measurement noise
        noise_level = amplitude * 0.001
        amplitude_wf += noise_level * np.random.randn(total_points)

        # Ensure non-negative and minimum value for log calculation
        amplitude_wf = np.maximum(amplitude_wf, 1e-6)

        # Calculate decay time constant for logging
        tau = loaded_q / (np.pi * self.frequency)
        self.log.debug(
            f"Waveform: τ={tau*1e6:.1f}µs, "
            f"f={self.frequency/1e9:.1f}GHz, "
            f"Q={loaded_q:.2e}"
        )

        return time_wf, amplitude_wf

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
        if value == 1:  # Only act on "Reset" command
            await self.quench_latch.write(0)
            await self.ssa_latch.write(0)  # Reset SSA latch too
            # Restore amplitude only if RF is on
            if self.rf_state_act.value == 1:
                await self.aact.write(self.ades.value)
                await self.amean.write(self.ades.value)
            # Reset the command
            await self.interlock_reset.write(0)

    @ades.putter
    async def ades(self, instance, value):
        await self.aact.write(value)
        await self.amean.write(value)
        gradient = value / self.length
        await self.gdes.write(gradient, verify_value=False)  # Skip the putter

    @pdes.putter
    async def pdes(self, instance, value):
        # Normalize phase to [0, 360)
        normalized_value = value % 360
        await self.pact.write(normalized_value)
        await self.pmean.write(normalized_value)
        return normalized_value  # Return the actual written value

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
