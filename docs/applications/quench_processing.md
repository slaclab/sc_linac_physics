# Quench Processing

`applications/quench_processing/` monitors all cavities for quench events (loss of superconductivity) and automatically resets *fake* quenches (transient noise trips) while logging and preserving information about real quenches for operator review.

## The fake vs. real quench problem

When a cavity quenches, its interlock trips and RF turns off. Many trips are transient (noise, beam-induced, cosmic ray) and the cavity recovers immediately — these are "fake quenches". Resetting them automatically avoids lengthy manual recovery cycles. Real quenches (mechanical, thermal, magnetic flux entry) require investigation before reset.

The distinction is made by re-reading the fault PV after a short delay (~100 ms):
- If the fault clears on re-read → transient noise → send reset
- If the fault persists → real quench → log warning, do NOT reset, alert operators

## Main components

### `quench_resetter.py` — monitoring loop

`check_cavities()` is the main loop, called repeatedly by the watcher service:

```
for each cavity:
    if fault PV is set:
        if within cooldown window → skip
        re-read after 100 ms delay
        if fault cleared → fake quench → put(1) to interlock_reset_pv
        if fault persists → real quench → log warning, record stats
    increment heartbeat PV
```

### `CavityResetTracker`

Per-cavity state: enforces a minimum cooldown between successive resets (default 3 s) to prevent rapid re-triggering on intermittent faults. Tracks:
- Total resets sent
- Real quenches detected
- Timestamp of last reset

### `QuenchCavity` (`quench_cavity.py`)

Extends `Cavity` with:
- `validate_quench()` — re-read fault PV after delay to classify quench type
- `interlock_reset_pv` — the PV that sends the reset command

### `QuenchGUI` / `QuenchWorker`

GUI display showing quench history per cavity and live fault state. The worker thread manages the monitoring loop lifecycle (start/stop/pause) in response to GUI controls.

## Key design choices

- **Non-blocking reset** — `pv.put(1, wait=False)` keeps the monitor loop running without stalling on IOC acknowledgment.
- **Heartbeat PV** — incremented every loop iteration. SRF Home watches this PV; a static value means the watcher process is stuck.
- **Per-cavity cooldown** — prevents alert storms when a cavity has an intermittent contact fault that repeatedly trips.
- **No database writes per cycle** — stats are in-memory counters, keeping the inner loop fast. Historical data is available from EPICS archiver queries.

## Entry points

```bash
sc-quench          # GUI
sc-watcher start quench_resetter  # background watcher (from SRF Home or CLI)
```
