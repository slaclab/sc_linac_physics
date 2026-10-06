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

pv_names = ["ACCL:L0B:0110:ADES", "ACCL:L0B:0120:ADES"]
values = PVBatch.get_values(pv_names)
# returns [val_for_pv1, val_for_pv2] — same order as input; None for disconnected PVs

PVBatch.put_values(pv_names, [5.0, 5.0])
# returns [True, True] — per-PV success flags
```

Prefer `PVBatch` when touching more than ~5 PVs at once (e.g., reading all 296 cavity amplitudes).

### Exception types (`exceptions.py`)

| Exception | When raised |
|-----------|-------------|
| `PVConnectionError` | CA connection failed after retries |
| `PVGetError` | Read failed after retries |
| `PVPutError` | Write failed after retries |
| `PVInvalidError` | Value out of allowed range or alarm severity exceeded |

## Archiver (`utils/archiver.py`)

Reads past PV values from the LCLS archiver appliance. Replaces
`lcls_tools.common.data.archiver`, which is deprecated.

```python
from datetime import datetime
from sc_linac_physics.utils.archiver import (
    get_values_over_time_range,
    get_values_at_time,
)

frames = get_values_over_time_range(
    ["ACCL:L0B:0110:AACTMEAN"], datetime(2023, 10, 2, 9, 13), datetime(2023, 10, 2, 10)
)
# {pv: DataFrame with columns timestamp, value, severity, status, valid}

samples = get_values_at_time(["ACCL:L0B:0110:AACTMEAN"], datetime(2023, 10, 2, 9, 30))
# {pv: ArchiverSample(timestamp, value, severity, status)}; .valid
```

- One request per PV, up to `MAX_WORKERS` (8) at once. The archiver spends its
  time reading each PV, so this is much faster than one multi-PV request.
- Naive datetimes are read as Pacific time. Returned timestamps are
  timezone-aware.
- A range may or may not include the last sample before `start`: the same
  query a few minutes apart did both. Don't rely on either.
- Errors: `PVNotArchivedError` (names every unknown PV), `ArchiverTimeoutError`,
  `ArchiverConnectionError`, all subclasses of `ArchiverError`. Timeouts,
  connection errors and 5xx responses are retried 3 times first.
- `get_values_at_time` leaves out a PV the archiver has no value for.
- Cold queries are slow: value-at-time took 26-63 s on site. A proxy answers
  502 at 60 s, which is retried, so one cold lookup can block for about 4
  minutes before it fails. Keep these calls off the Qt main thread.

### Plotting two signals

This fetches CAV7's amplitude and one decarad channel for CM06's 2024-02-02 run
from `field_emission_runs.csv`.

```python
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
from sc_linac_physics.utils.archiver import get_values_over_time_range

amp, rad = "ACCL:L2B:0670:AACTMEAN", "RADM:SYS0:200:06:GAMMAAVE"
frames = get_values_over_time_range(
    [amp, rad], datetime(2024, 2, 2, 12, 40), datetime(2024, 2, 2, 13, 3)
)
x = frames[amp][frames[amp]["valid"]]
y = frames[rad][frames[rad]["valid"]]
```

**On one time axis.** Give each signal its own y-axis. Archived values hold
until the next sample, so draw them as steps:

```python
fig, ax_amp = plt.subplots()
ax_rad = ax_amp.twinx()
ax_amp.step(x["timestamp"], x["value"], where="post", color="C0")
ax_rad.step(y["timestamp"], y["value"], where="post", color="C1")
ax_amp.set_ylabel(amp, color="C0")
ax_rad.set_ylabel(rad, color="C1")
fig.autofmt_xdate()
plt.show()
```

**One against the other.** The archiver timestamps each PV separately, so pair
samples by time first. `merge_asof` matches each amplitude sample with the last
radiation sample at or before it:

```python
paired = pd.merge_asof(
    x[["timestamp", "value"]],
    y[["timestamp", "value"]],
    on="timestamp",
    suffixes=("_amp", "_rad"),
).dropna()
paired = paired[paired["value_amp"] >= 4]  # the display's AMPLITUDE_THRESHOLD

fig, ax = plt.subplots()
ax.scatter(paired["value_amp"], paired["value_rad"], marker=".")
ax.set_xlabel(amp)
ax.set_ylabel(rad)
plt.show()
```

Which cavity a channel sits beside is not fixed. A decarad has 10 heads, one
at each end of the cryomodule and one at each cavity's tuner access port, and
the two decarads are moved between cryomodules and set up per run. Nothing in
`field_emission_runs.csv` records that setup. Channel 6 here was picked from
the data, not from a known mapping. In this run CAV3 and CAV4 were also above
4 MV, so plot all 8 amplitudes on the time axis to see which cavities overlap.

Field emission does the same pairing for a whole run, with forward-fill, in
`amp_vs_radiation.py::align_pvs_to_common_time`.

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
