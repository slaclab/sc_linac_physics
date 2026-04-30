# Shared Utilities

Infrastructure modules under `utils/` used by every application and display.

## EPICS wrappers (`utils/epics/`)

### `PV` class (`core.py`)

A thin but important wrapper around `epics.PV` (pyepics). Use this instead of raw pyepics throughout the codebase.

Key improvements over the raw class:
- **Never returns `None`** — raises a typed exception instead
- **Retry with backoff** — configurable `max_retries` (default 3) and `retry_delay`
- **Thread-safe reconnection** — reentrant lock around reconnect logic
- **Typed exceptions** — `PVConnectionError`, `PVGetError`, `PVPutError`, `PVInvalidError`

```python
from sc_linac_physics.utils.epics import PV

pv = PV("ACCL:L0B:0110:ADES")
pv.put(5.0)           # write (default wait=True, timeout=30s)
val = pv.get()        # read (default timeout=2s)
pv.check_alarm()      # raises if severity >= MAJOR
```

Default timeouts (`PVConfig`):

| Parameter | Default |
|-----------|---------|
| `connection_timeout` | 5 s |
| `get_timeout` | 2 s |
| `put_timeout` | 30 s |
| `max_retries` | 3 |

**Lazy-loading pattern** — PV objects are never created in `__init__`. They are created on first property access and cached:

```python
@property
def ades_pv(self) -> PV:
    if not self._ades_pv:
        self._ades_pv = PV(self.pv_addr("ADES"))
    return self._ades_pv
```

This keeps import time and test startup fast by avoiding hundreds of CA connections at module load.

### `PVBatch` (`batch.py`)

Use for bulk reads/writes. Internally calls `epics.caget_many()` to fetch many PVs in a single round-trip, with fallback to individual reads on partial failure.

```python
from sc_linac_physics.utils.epics.batch import PVBatch

values = PVBatch.get_values(["ACCL:L0B:0110:ADES", "ACCL:L0B:0120:ADES"])
# returns {pv_name: value, ...}

PVBatch.put_values({"ACCL:L0B:0110:ADES": 5.0, "ACCL:L0B:0120:ADES": 5.0})
```

Prefer `PVBatch` when touching more than ~5 PVs at once (e.g., reading all 296 cavity amplitudes).

### Exception types (`exceptions.py`)

| Exception | When raised |
|-----------|-------------|
| `PVConnectionError` | CA connection failed after retries |
| `PVGetError` | Read failed after retries |
| `PVPutError` | Write failed after retries |
| `PVInvalidError` | Value out of allowed range or alarm severity exceeded |

## Platform paths (`utils/platform_paths.py`)

Centralizes the paths that differ between Linux (production) and macOS (development):

```python
from sc_linac_physics.utils.platform_paths import get_log_base_dir, get_database_dir

get_srf_base_dir()   # /home/physics/srf  (Linux) | ~/  (macOS)
get_database_dir()   # /home/physics/srf/databases
get_json_dir()       # /home/physics/srf/json
get_log_base_dir()   # /home/physics/srf/logfiles
```

Always use these functions rather than hardcoding paths.

## Logging (`utils/logger.py`)

`custom_logger()` returns a `logging.Logger` with three sinks:

1. **Colored console output** — human-readable, with `extra_data` rendered as `key=value`
2. **Rotating `.log` file** — plain text, 10 MB max, 5 backups
3. **Rotating `.jsonl` file** — JSON Lines, one record per line, for log aggregation

```python
from sc_linac_physics.utils.logger import custom_logger

logger = custom_logger(
    name="auto_setup",
    log_filename="cavity_01_setup",
    log_dir=get_log_base_dir() / "auto_setup",
)

logger.info("Starting SSA calibration", extra={"extra_data": {"cavity": "CM01:1", "drive_max": 0.8}})
```

Notable behaviors:
- File creation uses a safe umask to set group-writable permissions
- `RetryFileHandlerFilter` retries log file creation every 60 s if the directory is missing (handles NFS mounts)
- Pass `enable_retry=False` in tests to skip retries

## Qt utilities (`utils/qt.py`)

### `Worker(QThread)`

All long-running operations (EPICS sequences, data acquisition) run in a `Worker` to avoid blocking the Qt event loop. Signals:

```python
class Worker(QThread):
    finished = pyqtSignal(str)   # emitted when done; carries result string
    progress = pyqtSignal(int)   # 0–100
    error    = pyqtSignal(str)   # exception message
    status   = pyqtSignal(str)   # human-readable status update
```

### `make_sanity_check_popup(txt) -> bool`

Shows a Yes/Cancel confirmation dialog. Returns `True` if user clicks Yes. Use before any destructive or machine-wide action.

### `RFControls`

Pre-built widget assembly for cavity RF control panels: SSA on/off, RF mode selector, amplitude spinbox + readback, SRF max spinbox + readback. Saves wiring up the same ~10 widgets in every cavity display.

### Other helpers

| Function | Purpose |
|----------|---------|
| `make_error_popup(title, msg)` | Critical error dialog |
| `make_rainbow(n)` | HSV colormap with `n` colors for plotting |
| `get_dimensions(options)` | Square-packing grid size for `n` widgets |
| `CollapsibleGroupBox` | QGroupBox with expand/collapse toggle |
