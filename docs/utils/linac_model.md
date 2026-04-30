# Linac Hardware Model

`utils/sc_linac/` defines the Python object hierarchy that mirrors the physical SC Linac. Every application in the codebase instantiates a subclass of `Machine` and navigates this tree to read/write EPICS PVs.

## Object hierarchy

```
Machine
└── Linac  (×5: L0B, L1B, L2B, L3B, L4B)
    └── Cryomodule  (up to 23 per linac, 60 total)
        ├── Rack A  →  Cavities 1–4
        │              └── SSA, StepperTuner, Piezo (one each)
        ├── Rack B  →  Cavities 5–8
        │              └── SSA, StepperTuner, Piezo (one each)
        └── Magnets  (QUAD, XCOR, YCOR) — non-HL cryomodules only
```

All classes inherit from `SCLinacObject`, which provides:
- Abstract property `pv_prefix` — every subclass builds its own prefix string
- `pv_addr(suffix)` → full PV name
- `auto_pv_addr(suffix)` → `{prefix}AUTO:{suffix}` automation PV name

## PV naming conventions

PV names are hierarchical strings encoding linac section, cryomodule number, and cavity number:

| Level | Pattern | Example |
|-------|---------|---------|
| Linac | `ACCL:L{N}B:1:{suffix}` | `ACCL:L0B:1:HEARTBEAT` |
| Cryomodule | `ACCL:L{N}B:{CM}00:{suffix}` | `ACCL:L1B:0200:DSSTAT` |
| Cavity | `ACCL:L{N}B:{CM}{CAV}0:{suffix}` | `ACCL:L0B:0110:ADES` |
| SSA | `ACCL:L{N}B:{CM}{CAV}0:SSA:{suffix}` | `ACCL:L0B:0110:SSA:STATUS` |
| Stepper | `ACCL:L{N}B:{CM}{CAV}0:STEP:{suffix}` | `ACCL:L0B:0110:STEP:NSTEP` |
| Piezo | `ACCL:L{N}B:{CM}{CAV}0:PZT:{suffix}` | `ACCL:L0B:0110:PZT:VOLTAGE` |
| Magnet | `{TYPE}:L{N}B:{CM}85:{suffix}` | `QUAD:L0B:0185:BDES` |

Helper functions in `linac_utils.py`:

```python
build_cavity_pv_base(linac_name, cm_name, cav_num)   # → "ACCL:L0B:0110"
build_cavity_pv_prefix(linac_name, cm_name, cav_num)  # → "ACCL:L0B:0110:"
build_cavity_pv(linac_name, cm_name, cav_num, suffix) # → full PV string
```

### Cryogenic subsystem prefixes (per cryomodule)

| Prefix variable | Pattern | Subsystem |
|-----------------|---------|-----------|
| `cte_prefix` | `CTE:CM{name}:` | Temperature |
| `cvt_prefix` | `CVT:CM{name}:` | Valve/temperature |
| `cpv_prefix` | `CPV:CM{name}:` | Pressure/valve |
| JT valve | `CLIC:CM{name}:3001:PVJT:` | |
| Heater | `CPIC:CM{name}:0000:EHCV:` | |

## Cryomodule groupings

```python
L0B    = ["01"]                              # 1 CM
L1B    = ["02", "03"]                        # 2 CMs
L1BHL  = ["H1", "H2"]                       # 2 Harmonic Linearizers (3.9 GHz)
L2B    = ["04" … "15"]                       # 12 CMs
L3B    = ["16" … "35"]                       # 20 CMs
L4B    = ["37" … "59"]                       # 23 CMs (no "36")

ALL_CRYOMODULES       = L0B + L1B + L1BHL + L2B + L3B + L4B  # 60 total
ALL_CRYOMODULES_NO_HL = L0B + L1B + L2B + L3B + L4B           # 58 (no HL)
LINAC_CM_MAP          = [L0B, L1B+L1BHL, L2B, L3B, L4B]       # indexed 0–4
```

Harmonic Linearizers (`H1`, `H2`) differ from normal cavities:
- Frequency: **3.9 GHz** (normal: 1.3 GHz)
- Cavity length: **0.346 m** (normal: 1.038 m)
- SSA: 4 SSAs shared across 8 cavities via `HL_SSA_MAP = {1:1, 2:2, 3:3, 4:4, 5:1, 6:2, 7:3, 8:4}`
- Q-loaded limits: 1.5×10⁷ – 3.5×10⁷ (normal: 2.5×10⁷ – 5.1×10⁷)
- `cryo_name` maps `H1` → `HL01`, `H2` → `HL02`

## Instantiation pattern

`Machine.__init__` accepts optional class parameters for every level of the hierarchy, allowing applications to substitute their own subclasses:

```python
# Application-specific singleton
SETUP_MACHINE = SetupMachine(
    linac_class=SetupLinac,
    cryomodule_class=SetupCryomodule,
    cavity_class=SetupCavity,
)

# Generic access
machine = Machine()  # uses base Linac, Cryomodule, Cavity
cavity  = machine.cryomodules["01"].cavities[3]  # Cryomodule "01", Cavity 3
```

`Machine` exposes:
- `machine.cryomodules` — flat dict of all 60 CMs (convenient shortcut)
- `machine.linacs` — dict indexed by linac number (0–4)
- `non_hl_iterator`, `hl_iterator`, `all_iterator` — generators over all cavities

## Key classes

### Cavity (`cavity.py`)

The most feature-rich class. Key attributes and methods:

| Member | Purpose |
|--------|---------|
| `ssa` | `SSA` sub-object (lazy) |
| `stepper` | `StepperTuner` sub-object (lazy) |
| `piezo` | `Piezo` sub-object (lazy) |
| `turn_on()` / `turn_off()` | RF on/off |
| `characterize()` | Cavity Q measurement sequence |
| `move_to_resonance(use_sela)` | Piezo + stepper resonance finding |
| `walk_amp(target, step)` | Gradual amplitude ramp |
| `reset_interlocks()` | Clear hardware faults |
| `is_online` | `hw_mode == HW_MODE_ONLINE_VALUE` |

### SSA (`ssa.py`)

```python
ssa.turn_on()        # Powers on solid-state amplifier
ssa.calibrate(drive_max)  # Full calibration sequence
ssa.is_on            # bool property
ssa.is_faulted       # bool property
```

### StepperTuner (`stepper.py`)

```python
stepper.move(num_steps, max_steps, speed)
stepper.abort()
stepper.motor_moving  # bool property
stepper.hz_per_microstep  # frequency sensitivity
```

### Piezo (`piezo.py`)

```python
piezo.enable()
piezo.enable_feedback()   # Closed-loop feedback
piezo.disable_feedback()  # Open-loop manual
piezo.voltage             # Current voltage (R/W)
```

### LauncherLinacObject (`linac_utils.py`)

Mixin added by all setup/commissioning classes. Provides:
- `trigger_start()`, `trigger_abort()`, `trigger_stop()`, `clear_abort()` via AUTO: PVs
- These PVs are how the GUI/CLI signal the IOC scripts to begin or halt operations

## Key constants

### RF modes

```python
RF_MODE_SELAP  = 0  # Self-Excited Loop Amplitude+Phase (closed-loop)
RF_MODE_SELA   = 1  # Self-Excited Loop Amplitude (piezo + coarse)
RF_MODE_SEL    = 2  # Self-Excited Loop (open-loop coarse)
RF_MODE_PULSE  = 4  # Pulsed operation
RF_MODE_CHIRP  = 5  # Frequency sweep
```

### Hardware mode

```python
HW_MODE_ONLINE_VALUE      = 0  # Normal operation
HW_MODE_MAINTENANCE_VALUE = 1
HW_MODE_OFFLINE_VALUE     = 2
```

### Operation status

```python
STATUS_READY_VALUE   = 0
STATUS_RUNNING_VALUE = 1
STATUS_ERROR_VALUE   = 2
```

### SSA status

```python
SSA_STATUS_ON_VALUE      = 3
SSA_STATUS_FAULTED_VALUE = 1
SSA_STATUS_OFF_VALUE     = 2
```

### Tuning config

```python
TUNE_CONFIG_RESONANCE_VALUE = 0
TUNE_CONFIG_COLD_VALUE      = 1
TUNE_CONFIG_PARKED_VALUE    = 2
TUNE_CONFIG_OTHER_VALUE     = 3
```

## Exception hierarchy

All exceptions are defined in `linac_utils.py`:

- `CavityAbortError` — abort flag was set; safe stop requested
- `CavityFaultError` — cavity fault condition
- `CavityHWModeError` — hardware not in expected mode
- `QuenchError` — superconducting quench detected
- `SSACalibrationError` / `SSACalibrationToleranceError`
- `CavityQLoadedCalibrationError` / `CavityScaleFactorCalibrationError`
- `DetuneError` — frequency out of tolerance
- `StepperError` / `StepperAbortError`
- `PulseError`

## Simulation

`utils/simulation/sc_linac_physics_service.py` is a caproto-based EPICS IOC that publishes simulated PVs for the entire linac. Run with `sc-sim`. Set `PYDM_DEFAULT_PROTOCOL=fake` to use PyDM's built-in fake protocol for UI testing without the simulation IOC.
