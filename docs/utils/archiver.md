# Archiver client (`utils/archiver.py`)

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

- PVs are fetched independently, up to `MAX_WORKERS` (8) at once. The
  archiver spends its time reading each PV, so this is much faster than one
  multi-PV request. A window up to an hour is one request per PV. A longer
  one is one count request per 31 days (two for a string PV), then one
  request per chunk.
- Naive datetimes are read as Pacific time. Returned timestamps are
  timezone-aware. A naive time in a daylight-saving change hour (it happens
  twice, or not at all) raises `ValueError`; pass an aware datetime there.
- A range may or may not include the last sample before `start`: the same
  query a few minutes apart did both. Don't rely on either.
- Windows longer than an hour are fetched in chunks, each PV's chunks one
  after another, so no request reaches the proxy's 60 s cutoff. The chunks
  are planned from the archiver's own hourly sample counts (`count_3600`),
  at most `CHUNK_SAMPLES` (250k, about 25 MB) each:
  <span class="cite">archiver.py::_plan_chunks</span>. The result is the
  same as one request. String PVs get no hourly counts, so they are
  planned from totals (`ncount`), halving any window that is too big.
- Live, 2026-10-12: 60 days of a 1 Hz PV took 21 requests, the largest 25 MB.
  A year of two fault PVs took 16, mostly counts.
- `iter_range_chunks(pv, start, end)` yields the same samples one chunk at a
  time, for processing or storing a long window without holding all of it.
- Memory: parsing peaks at about 6.5x a chunk's JSON, about 190 MB per PV,
  for up to `MAX_WORKERS` PVs at once. The 60-day result was 156 MB. Raw
  pulls of a year or more don't fit in memory. A disk store is planned.
- Errors: `PVNotArchivedError` (names every unknown PV), `ArchiverTimeoutError`,
  `ArchiverConnectionError`, all subclasses of `ArchiverError`. Timeouts,
  connection errors and HTTP 502/503/504 are retried first (`MAX_RETRIES`
  attempts in all). Other HTTP errors, and a 200 whose body isn't the
  expected JSON, raise `ArchiverError` at once.
- `get_values_at_time` leaves out a PV the archiver has no value for.
- Cold queries are slow: value-at-time took 26-63 s on site. A proxy answers
  502 at 60 s, which is retried, so one cold lookup can block for about 4
  minutes before it fails. Keep these calls off the Qt main thread.

## Plotting two signals

`get_series` returns each PV's valid samples as a pandas Series indexed by
time. This fetches CAV7's amplitude and one decarad channel for CM06's
2024-02-02 run from `field_emission_runs.csv`:

```python
from datetime import datetime
from sc_linac_physics.utils.archiver import get_series, pair_by_time
from sc_linac_physics.utils.archiver_plot import plot_over_time

AMP, RAD = "ACCL:L2B:0670:AACTMEAN", "RADM:SYS0:200:06:GAMMAAVE"
series = get_series(
    [AMP, RAD], datetime(2024, 2, 2, 12, 40), datetime(2024, 2, 2, 13, 3)
)
```

**On one time axis.** Each Series gets its own y-axis, drawn as steps, since
an archived value holds until the next sample. Ticks are Pacific time, with
the date shown once:

```python
import matplotlib.pyplot as plt

fig, axes = plot_over_time(series[AMP], series[RAD])
plt.show()
```

**One against the other.** PVs are timestamped separately. `pair_by_time`
matches each amplitude sample with the last radiation sample at or before it:

```python
paired = pair_by_time(series[AMP], series[RAD])
paired = paired[paired[AMP] >= 4]  # the display's AMPLITUDE_THRESHOLD
paired.plot.scatter(x=AMP, y=RAD, marker=".")
plt.show()
```

Field emission does the same pairing for a whole run, with forward-fill, in
`amp_vs_radiation.py::align_pvs_to_common_time`.
