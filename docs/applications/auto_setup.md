# Auto Setup

`applications/auto_setup/` automates cavity commissioning: from a cold, unpowered state to a cavity delivering RF to the beam. It provides both a GUI and command-line launchers at four levels of granularity (machine → linac → cryomodule → cavity).

## What "setup" means

For each cavity, setup runs up to four sequential operations:

1. **SSA Calibration** — measures the solid-state amplifier's power transfer curve, sets DAC levels to 0, runs `ssa.calibrate()`
2. **Auto Tune** — moves the cavity to resonance using the stepper tuner (`move_to_resonance(use_sela=False)`)
3. **Cavity Characterization** — measures Q-loaded and scale factor via `cavity.characterize()`, then computes probe Q
4. **RF Ramp** — enables piezo feedback, turns RF on in SELA mode, walks amplitude up to ACON target, centers piezo, switches to SELAP for closed-loop operation

Each step is independently optional (controlled by request flags). The GUI and launchers set these flags before triggering start.

## Class hierarchy

```
SetupMachine  (module singleton: SETUP_MACHINE)
└── SetupLinac  (×4 linac sections)
    └── SetupCryomodule  (×N per linac)
        └── SetupCavity  (×8 per cryomodule)
```

All four classes multiply-inherit from their base linac class (`Machine`, `Linac`, `Cryomodule`, `Cavity`) **and** `SetupLinacObject`. The linac base provides hardware access; `SetupLinacObject` adds setup-specific request flags and trigger methods.

### `SetupLinacObject` (`backend/setup_utils.py`)

Mixin that adds four PV-backed boolean properties:

| Property | PV suffix | Meaning |
|----------|-----------|---------|
| `ssa_cal_requested` | `AUTO:SETUP_SSAREQ` | Run SSA calibration |
| `auto_tune_requested` | `AUTO:SETUP_TUNEREQ` | Run auto-tune |
| `cav_char_requested` | `AUTO:SETUP_CHARREQ` | Run cavity characterization |
| `rf_ramp_requested` | `AUTO:SETUP_RAMPREQ` | Ramp RF to ACON |

These are written by the GUI/CLI before calling `trigger_start()`. The IOC script reads them to decide which steps to execute. All four flag PVs use the `auto_pv_addr()` pattern from `SCLinacObject`.

### `SetupCavity.setup()` (`backend/setup_cavity.py`)

The main state machine. Rough flow:

```
safety check (not running, is online)
→ turn RF off
→ turn SSA on, reset interlocks
→ request_ssa_cal()      [progress: 0→25]
→ request_auto_tune()    [progress: 25→50]
→ request_characterization()  [progress: 50→70]
→ request_ramp()         [progress: 70→100]
→ set status READY
```

`check_abort()` is called between steps. If the abort PV is set (by GUI or operator), `CavityAbortError` is raised and the sequence stops cleanly.

Key properties on `SetupCavity`:
- `status` — `STATUS_READY_VALUE` / `STATUS_RUNNING_VALUE` / `STATUS_ERROR_VALUE`
- `script_is_running` — `True` while setup is active
- `progress` — 0–100 integer (drives GUI progress bar)
- `status_message` — human-readable string shown in GUI

### RF ramp detail

The ramp step is the most sensitive: it starts RF at `min(2 MV, ACON)`, walks amplitude up in 0.1 MV steps to the full ACON target, centers piezo, then switches to SELAP mode. Piezo feedback must be enabled before RF turn-on to maintain resonance during ramping.

`capture_acon()` copies the current ADES reading into ACON — used to "lock in" the current operating amplitude as the new target.

## GUI (`frontend/setup_gui.py`)

`SetupGUI` (PyDM Display) mirrors the physical hierarchy as nested `QTabWidget`s:

```
SetupGUI
├── Machine-level controls (Set Up / Shut Down / Abort all)
├── Checkboxes (SSA Cal, Auto Tune, Characterization, RF Ramp)
└── Tabs: L0B | L1B | L2B | L3B
    └── Tabs: CM01 | CM02 | …
        └── Grid 4×2: GUICavity ×8
            ├── ACON / AACT readbacks
            ├── Set Up / Turn Off / Abort buttons
            ├── Status message label
            └── Progress bar
```

Machine-level and linac-level buttons show a confirmation popup before executing to prevent accidental machine-wide operations.

Checkboxes are stored in a `Settings` dataclass passed down from `SetupGUI` to all child widgets, so they share a single source of truth for which steps are requested.

## CLI launchers

Four entry points, one per hierarchy level:

| Command | Entry point | Required args |
|---------|-------------|---------------|
| `sc-setup-all` | `srf_global_setup_launcher.py` | `--no_hl` (optional), `--shutdown` (optional) |
| `sc-setup-linac` | `srf_linac_setup_launcher.py` | `-l {0..3}` |
| `sc-setup-cm` | `srf_cm_setup_launcher.py` | `-cm {01,02,H1,…}` |
| `sc-setup-cav` | `srf_cavity_setup_launcher.py` | `-cm {CM} -cav {1..8}` |

All launchers:
1. Read current request flags from EPICS (inheriting whatever the GUI last set)
2. Propagate flags from parent object down to cavities
3. Call `setup()` or `shut_down()` on each cavity sequentially
4. Sleep briefly between cavities to avoid IOC overload (0.1–0.5 s)
5. Log structured entries with `extra_data` dicts to `logs/auto_setup/`

Shutdown (`--shutdown` / `-off`) is simpler than setup: turns RF off, turns SSA off.

## Non-obvious behaviors

- **Offline cavities are skipped** — `is_online` check at setup start; cavity remains in `READY` state with a logged message, not `ERROR`.
- **Already-running cavities are skipped** — if `script_is_running`, the launcher logs a warning and moves on.
- **RF off before setup starts** — even when only requesting RF ramp, the sequence always turns RF off first to clear interlock state.
- **ACON = 0 blocks ramp** — if ACON is zero the ramp step is skipped with an error message (no target to ramp to).
- **`SETUP_MACHINE` is a module-level singleton** — all four launchers and the GUI share the same Python object; EPICS PVs are the ultimate source of truth for request flags.
