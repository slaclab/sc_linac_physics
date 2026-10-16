"""Client for the LCLS archiver appliance.

Replaces ``lcls_tools.common.data.archiver``, which is deprecated.

Measured against the archiver on site (2026-10-05): the time goes into the
archiver reading each PV, not into the response. JSON, CSV and raw protobuf
responses took about as long. So this sends one request per PV and runs up to
MAX_WORKERS of them at once. On 18 PVs that took 0.5 s against 2-3 s for one
multi-PV request (getDataForPVs.json, which lcls_tools used). A PV the
archiver does not know then fails only its own request; the multi-PV endpoint
returns 404 for the whole batch.

getDataForPVs is not in the user guide. Its server side, doGetMultiPV in
DataRetrievalServlet.java, reads the PVs one at a time on one thread
("For now, we only use the current thread to execute in serial."):
https://github.com/archiver-appliance/epicsarchiverap, file
src/main/org/epics/archiverappliance/retrieval/DataRetrievalServlet.java

Value-at-time is the exception: one POST naming every PV took the same 7-8 s
as splitting it into parallel single-PV POSTs, so it stays one request.

Cold queries are slow whichever method is used: the first query of a
session took 55-138 s, and cold value-at-time lookups 26-63 s. CHECK: is that
the archiver reading from slower storage?

Differences from lcls_tools, on purpose:

- Timestamps are timezone-aware (America/Los_Angeles). lcls_tools returned
  naive datetimes in the local time of whatever machine ran the code.
- HTTP errors raise. lcls_tools' get_data_at_time returned {} on one, which a
  caller cannot tell apart from "no data".

Endpoints: https://epicsarchiver.readthedocs.io/en/stable/user/userguide.html
("Retrieving data using other tools" and "Save/Restore API"). That guide is
old; where it is silent, this follows what the LCLS archiver did when tested.
"""

import io
import math
import queue
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from time import sleep
from typing import (
    Callable,
    Dict,
    Iterable,
    List,
    NamedTuple,
    Optional,
    TypeVar,
    Union,
)
from zoneinfo import ZoneInfo

import pandas as pd
import requests

from sc_linac_physics.utils.epics.config import EPICS_INVALID_VAL

ARCHIVER_BASE_URL = "http://lcls-archapp.slac.stanford.edu"
ARCHIVER_URL = f"{ARCHIVER_BASE_URL}/retrieval/data"

# Measured on site (2026-10-06), 28 PVs x 2 h, uncached windows, median of 3:
# 1 worker 6.9 s, 2: 3.6 s, 4: 1.9 s, 8: 1.1 s, 16: 1.3 s. Same value as
# FaultDataFetcher.MAX_WORKERS.
MAX_WORKERS = 8

# A proxy in front of the archiver answers 502 at 60 s, so a longer timeout
# never helps; 75 s lets the proxy's 502 arrive and be retried. Measured: range
# requests took 12 s at most (72 h window); cold value-at-time took 26-63 s.
# CHECK: who configures the 60 s proxy limit?
RANGE_TIMEOUT = 75.0
AT_TIME_TIMEOUT = 75.0

# Cold value-at-time lookups took up to 4 attempts (502, 502, then 200), each
# about 60 s. So one lookup can block for about 4 minutes before it fails.
MAX_RETRIES = 4
RETRY_DELAY = 0.5

# Only gateway errors are retried: the proxy's 502 at 60 s above, and 503/504
# from it or the archiver. Other 5xx, like a 500, fail the same way each time,
# so retrying them only turned one failure into about 5 minutes of waiting.
RETRY_STATUS = frozenset({502, 503, 504})

# A proxy cuts every request off at 60 s, and a long window holds more samples
# than one request can return in that time, so ranges are fetched in chunks.
# Measured on site (2026-10-12), ACCL:L2B:0410:AACTMEAN, uncached windows:
# requests of 8-94 MB ran at 20-25 MB/s plus about 0.2 s each; 234 MB and
# 468 MB ran at about 12 MB/s. JSON is about 99 bytes per scalar sample.
#
# Memory sets the JSON chunk size, not time: parsing a chunk peaks at 6.5x its
# JSON size (one dict per sample), and MAX_WORKERS PVs fetch at once. At 250k
# samples (about 25 MB) that is about 190 MB per PV, 1.5 GB for 8, with about
# 2 s per request. Chunks count samples, which assumes scalar PVs: waveforms
# are not archived (Lisa Zacarias, 2026-10-12). A waveform sample would be
# many times bigger. JSON is used for string PVs and windows up to COUNT_BIN.
CHUNK_SAMPLES = 250_000

# Numeric PVs are read as CSV (_csv_chunk), which parses at a quarter of
# JSON's memory, so their chunks can be bigger. Measured on site
# (2026-10-12): 60 days of one 1 Hz PV took 20 s in 250k chunks and 14.5 s
# in 1 M (6 requests); 8 PVs x 30 days in parallel peaked at 1.68 GB and
# 1.86 GB, most of it the 18.9 M rows returned.
CSV_CHUNK_SAMPLES = 1_000_000

# Chunks are planned from the archiver's own sample counts, not guessed:
# count_3600(pv) returns the samples in each UTC hour, timestamped at the
# hour's midpoint (checked on site; counts matched raw). The archiver reads
# every sample to count them, about 2 M samples/s, so counts are asked for
# COUNT_WINDOW at a time to keep each request short. A window no longer than
# COUNT_BIN is fetched in one request without counting.
COUNT_BIN = timedelta(hours=1)
# 31 days, so one calendar month is one window (utils/archiver_store.py).
COUNT_WINDOW = timedelta(days=31)
# _split_by_total stops halving here: 250k samples in a minute is over 4 kHz.
MIN_SPLIT = timedelta(minutes=1)

LOCAL_TZ = ZoneInfo("America/Los_Angeles")

COLUMNS = ["timestamp", "value", "severity", "status", "valid"]
# Set, not inferred: pandas 2 infers ns from datetimes and pandas 3 infers
# us, and frames from the CSV and JSON paths must match to pair or concat.
TIMESTAMP_DTYPE = f"datetime64[us, {LOCAL_TZ.key}]"

Value = Union[float, int, str]

T = TypeVar("T")
R = TypeVar("R")


class ArchiverError(Exception):
    """The archiver request failed."""


class ArchiverTimeoutError(ArchiverError):
    """The archiver did not answer in time, on every attempt."""


class ArchiverConnectionError(ArchiverError):
    """The archiver could not be reached, on every attempt."""


class PVNotArchivedError(ArchiverError):
    """The archiver does not know one or more PVs (HTTP 404)."""

    def __init__(self, pvs: List[str]):
        self.pvs = pvs
        super().__init__(f"not in the archiver: {', '.join(pvs)}")


@dataclass(frozen=True)
class ArchiverSample:
    """One archived value."""

    timestamp: datetime
    value: Value
    severity: int
    status: int

    @property
    def valid(self) -> bool:
        return self.severity != EPICS_INVALID_VAL


def get_values_over_time_range(
    pvs: Iterable[str],
    start: datetime,
    end: datetime,
    timeout: float = RANGE_TIMEOUT,
    max_workers: int = MAX_WORKERS,
) -> Dict[str, pd.DataFrame]:
    """Return every archived sample of each PV between start and end.

    One DataFrame per PV, with columns COLUMNS. A PV with no samples in the
    window gets an empty DataFrame, not an error. Naive datetimes are read as
    America/Los_Angeles.

    Raises PVNotArchivedError, naming every unknown PV, once all requests have
    finished. Timeouts, connection errors and HTTP 502/503/504 are retried,
    then raised. Any other error, including a 200 whose body isn't the
    expected JSON, raises ArchiverError naming the PV.
    """
    pvs = list(pvs)
    # Chunk in UTC: adding a timedelta to a Pacific time is wall-clock
    # arithmetic, which skips or repeats an hour across a DST change.
    start = _aware(start).astimezone(timezone.utc)
    end = _aware(end).astimezone(timezone.utc)

    def fetch(pv: str) -> Optional[pd.DataFrame]:
        try:
            return _fetch_range(pv, start, end, timeout)
        except ArchiverError as e:
            # Every range request has the same URL; name the PV that failed.
            raise type(e)(f"{pv}: {e}") from e
        except (KeyError, IndexError, TypeError) as e:
            # A 200 whose JSON isn't the shape planning and fetching read.
            raise ArchiverError(f"{pv}: unexpected response: {e!r}") from e

    frames = dict(zip(pvs, _map_in_daemon_threads(fetch, pvs, max_workers)))

    missing = [pv for pv, frame in frames.items() if frame is None]
    if missing:
        raise PVNotArchivedError(missing)
    return frames


def _fetch_range(
    pv: str, start: datetime, end: datetime, timeout: float
) -> Optional[pd.DataFrame]:
    """Fetch one PV between start and end in chunks; None if not archived.

    A window can start with the last sample before "from", and a sample
    exactly on a boundary came back in both windows around it (checked on
    site, 2026-10-12). So each chunk after the first keeps only samples after
    the last one already kept. That holds whether or not the earlier sample
    comes back. Stitched that way, the chunks matched one request for the
    whole window (60 days, checked on site).

    Each chunk becomes a DataFrame as it arrives. Holding every chunk's JSON
    until the end peaked at 3.7 GB for a 156 MB result (60 days, 4.7 M
    samples, measured 2026-10-12).
    """
    plan = _plan_chunks(pv, start, end, timeout)
    if plan is None:
        return None
    get_chunk = _csv_chunk if plan.numeric else _json_chunk
    frames: List[pd.DataFrame] = []
    last: Optional[tuple] = None
    for chunk_start, chunk_end in zip(plan.bounds, plan.bounds[1:]):
        chunk = get_chunk(pv, chunk_start, chunk_end, timeout, last)
        if chunk is None:
            return None
        frame, chunk_last = chunk
        if chunk_last is not None:
            last = chunk_last
            frames.append(frame)
    # An empty frame's columns are object dtype; mixing one in would turn
    # the timestamps into objects too.
    if not frames:
        return _to_frame([])
    return pd.concat(frames, ignore_index=True)


class _Plan(NamedTuple):
    bounds: List[datetime]
    # The archiver gave hourly counts, which it does only for numeric PVs
    # (count_3600 of a string PV is empty). Numeric chunks are read as CSV.
    numeric: bool


def _plan_chunks(
    pv: str, start: datetime, end: datetime, timeout: float
) -> Optional[_Plan]:
    """Return chunk boundaries from start to end; None if not archived.

    Planned COUNT_WINDOW at a time, from hourly counts where the archiver
    gives them and from totals where it does not (_split_by_total). A
    window up to COUNT_BIN is not planned, and read as JSON.
    """
    if end - start <= COUNT_BIN:
        return _Plan([start, end], numeric=False)
    bounds, numeric = [start], False
    window_start = start
    while window_start < end:
        window_end = min(window_start + COUNT_WINDOW, end)
        planned = _plan_window(pv, window_start, window_end, timeout)
        if planned is None:
            return None
        bounds.extend(planned.bounds[1:])
        numeric = numeric or planned.numeric
        window_start = window_end
    return _Plan(bounds, numeric)


def _plan_window(
    pv: str, start: datetime, end: datetime, timeout: float
) -> Optional[_Plan]:
    # The archiver applies an operator to a PV when the operator wraps the
    # PV's name in the "pv" parameter: "count_3600(ACCL:...)" returns how
    # many samples fall in each 3600 s bin instead of the samples. That is
    # the retrieval API's way to ask for processed data; see "Processing of
    # data" in the user guide linked at the top. Built from COUNT_BIN so the
    # bins asked for are the ones _group_bins walks.
    operator = f"count_{int(COUNT_BIN.total_seconds())}({pv})"
    payload = _get_json(operator, start, end, timeout)
    if payload is None:
        return None
    bins = payload[0]["data"] if payload else []
    if not bins:
        bounds = _split_by_total(pv, start, end, timeout)
        return None if bounds is None else _Plan(bounds, numeric=False)
    counts = {_bin_start(datum["secs"]): datum["val"] for datum in bins}
    return _Plan(_group_bins(start, end, counts), numeric=True)


def _split_by_total(
    pv: str, start: datetime, end: datetime, timeout: float
) -> Optional[List[datetime]]:
    """Bound start..end for a PV count_3600 gives no bins for.

    That is a string PV, or a PV with nothing archived in the window
    (checked on site, 2026-10-12: count_3600 of CUDSTATUS was empty, of
    CUDSEVR, an enum, was not). ncount(pv), one total for the window, does
    work on strings, and matched the raw samples. A string PV can change
    fast (a CUDSTATUS flapping between the cavity number and POT), so a
    window over CHUNK_SAMPLES is halved, and each half counted again.
    """
    payload = _get_json(f"ncount({pv})", start, end, timeout)
    if payload is None:
        return None
    data = payload[0]["data"] if payload else []
    total = data[0]["val"] if data else 0
    if total <= CHUNK_SAMPLES or end - start <= MIN_SPLIT:
        return [start, end]
    middle = start + (end - start) / 2
    left = _split_by_total(pv, start, middle, timeout)
    if left is None:
        return None
    right = _split_by_total(pv, middle, end, timeout)
    if right is None:
        return None
    return left + right[1:]


def _group_bins(
    start: datetime,
    end: datetime,
    counts: Dict[int, float],
    limit: int = CSV_CHUNK_SAMPLES,
) -> List[datetime]:
    """Cut start..end into chunks of at most limit samples.

    counts maps each COUNT_BIN's start (UTC epoch seconds) to its samples;
    a missing bin has none. A bin with more than limit is split into
    equal parts, assuming its samples are spread evenly.
    """
    step = int(COUNT_BIN.total_seconds())
    bounds, in_chunk = [start], 0.0
    t = _bin_start(start.timestamp())
    while t < end.timestamp():
        lo = max(_utc(t), start)
        hi = min(_utc(t + step), end)
        n = counts.get(t, 0.0)
        if in_chunk and in_chunk + n > limit:
            bounds.append(lo)
            in_chunk = 0.0
        parts = max(1, math.ceil(n / limit))
        bounds.extend(lo + (hi - lo) * k / parts for k in range(1, parts))
        in_chunk += n / parts
        t += step
    bounds.append(end)
    return bounds


def _get_json(
    pv: str, start: datetime, end: datetime, timeout: float
) -> Optional[list]:
    response = _request(
        "GET",
        f"{ARCHIVER_URL}/getData.json",
        timeout,
        params={"pv": pv, "from": _to_utc_iso(start), "to": _to_utc_iso(end)},
    )
    return None if response is None else _json(response, "getData.json")


def _json_chunk(
    pv: str, start: datetime, end: datetime, timeout: float, last
) -> Optional[tuple]:
    """(frame, last key) for samples after last; (None, None) if none.

    None if the archiver doesn't know the PV.
    """
    payload = _get_json(pv, start, end, timeout)
    if payload is None:
        return None
    data = payload[0]["data"] if payload else []
    if last is not None:
        data = [datum for datum in data if _key(datum) > last]
    if not data:
        return None, None
    return _to_frame(data), _key(data[-1])


def _csv_chunk(
    pv: str, start: datetime, end: datetime, timeout: float, last
) -> Optional[tuple]:
    """Like _json_chunk, from getData.csv: for numeric PVs only.

    Measured on site (2026-10-12), 551k samples: CSV is half the bytes of
    JSON, parses 8x faster and peaks at a quarter of the memory, with an
    identical frame. CSV doesn't say a value's type and doesn't quote
    strings, so a string PV is read as JSON instead.
    """
    response = _request(
        "GET",
        f"{ARCHIVER_URL}/getData.csv",
        timeout,
        params={"pv": pv, "from": _to_utc_iso(start), "to": _to_utc_iso(end)},
    )
    if response is None:
        return None
    if not response.content.strip():
        return None, None
    try:
        return _parse_csv_chunk(response.content, last)
    except (ValueError, TypeError) as e:
        # The server said the request succeeded but sent something other
        # than the expected CSV, such as a proxy's login or error page.
        # Raise ArchiverError, as _json does for a bad JSON reply, so callers
        # handle one kind of failure. pandas reports an unreadable file as a
        # ValueError, so this except catches it.
        raise ArchiverError(
            f"getData.csv: response is not the expected CSV: {e}"
        ) from e


def _parse_csv_chunk(content: bytes, last) -> tuple:
    # Columns secs, val, severity, status, nanos, with no header (checked
    # on site). round_trip: the default parser can be a bit off.
    raw = pd.read_csv(
        io.BytesIO(content),
        header=None,
        names=["secs", "value", "severity", "status", "nanos"],
        float_precision="round_trip",
    )
    # Check before any arithmetic: on a text column, raw["secs"] * 10**9
    # repeats the string a billion times. A proxy's HTML page parses that way.
    columns = ["secs", "value", "severity", "status", "nanos"]
    if not all(pd.api.types.is_numeric_dtype(raw[c]) for c in columns):
        raise ValueError(f"non-numeric columns: {dict(raw.dtypes.astype(str))}")
    if last is not None:
        secs, nanos = last
        raw = raw[
            (raw["secs"] > secs)
            | ((raw["secs"] == secs) & (raw["nanos"] > nanos))
        ]
    if raw.empty:
        return None, None
    tail = raw.iloc[-1]
    return _csv_to_frame(raw), (int(tail["secs"]), int(tail["nanos"]))


def _csv_to_frame(raw: pd.DataFrame) -> pd.DataFrame:
    """The frame _to_frame builds, from parsed CSV columns.

    Timestamps round to the nearest microsecond, as _timestamp's
    timedelta does, so both paths give the same frame.
    """
    raw = raw.reset_index(drop=True)
    frame = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                raw["secs"] * 1_000_000_000 + raw["nanos"], utc=True
            )
            .dt.round("us")
            .astype("datetime64[us, UTC]")
            .dt.tz_convert(LOCAL_TZ),
            "value": raw["value"],
            "severity": raw["severity"],
            "status": raw["status"],
        }
    )
    frame["valid"] = frame["severity"] != EPICS_INVALID_VAL
    return frame[COLUMNS]


def _bin_start(secs: float) -> int:
    step = int(COUNT_BIN.total_seconds())
    return int(secs // step) * step


def _utc(secs: int) -> datetime:
    return datetime.fromtimestamp(secs, tz=timezone.utc)


def _key(datum: dict) -> tuple:
    return datum["secs"], datum.get("nanos", 0)


def get_series(
    pvs: Iterable[str], start: datetime, end: datetime, **kwargs
) -> Dict[str, pd.Series]:
    """Return each PV's valid samples between start and end, as a Series.

    Indexed by timestamp and named by PV, so a Series plots against time
    directly. Samples with INVALID severity are dropped. Keyword arguments go
    to get_values_over_time_range.
    """
    frames = get_values_over_time_range(pvs, start, end, **kwargs)
    return {
        pv: pd.Series(
            frame.loc[frame["valid"], "value"].to_numpy(),
            index=pd.DatetimeIndex(frame.loc[frame["valid"], "timestamp"]),
            name=pv,
        )
        for pv, frame in frames.items()
    }


def pair_by_time(x: pd.Series, y: pd.Series) -> pd.DataFrame:
    """Pair each x sample with the last y sample at or before it.

    Archived PVs are timestamped separately; this lines them up to plot one
    against the other. Columns are the two Series' names. Rows before y's
    first sample are dropped.
    """
    paired = pd.merge_asof(  # needs both sorted by time
        x.sort_index().rename("x").rename_axis("timestamp").reset_index(),
        y.sort_index().rename("y").rename_axis("timestamp").reset_index(),
        on="timestamp",
    ).dropna()
    return paired.set_index("timestamp").rename(
        columns={"x": x.name, "y": y.name}
    )


def get_values_at_time(
    pvs: Iterable[str], at: datetime, timeout: float = AT_TIME_TIMEOUT
) -> Dict[str, ArchiverSample]:
    """Return each PV's archived value at a moment, in one request.

    One batch POST is as fast as one request per PV here (measured), unlike
    get_values_over_time_range.

    A PV the archiver has no value for is left out of the result. Naive
    datetimes are read as America/Los_Angeles. No PVs means no request.
    """
    pvs = list(pvs)
    if not pvs:
        return {}
    response = _request(
        "POST",
        f"{ARCHIVER_URL}/getDataAtTime",
        timeout,
        params={"at": _to_utc_iso(at), "includeProxies": "true"},
        json=pvs,  # the Save/Restore API takes a JSON list of names
    )
    if response is None:  # 404: none of the PVs are known
        return {}
    payload = _json(response, "getDataAtTime")
    try:
        return {pv: _to_sample(datum) for pv, datum in payload.items()}
    except (AttributeError, KeyError, TypeError) as e:
        raise ArchiverError(f"getDataAtTime: unexpected response: {e!r}") from e


def _map_in_daemon_threads(
    fn: Callable[[T], R], items: List[T], max_workers: int
) -> List[R]:
    """Return [fn(item) for item in items], running up to max_workers at once.

    Waits for every call, then raises the first error in item order, as
    ThreadPoolExecutor.map did.

    Not ThreadPoolExecutor: Python joins its worker threads at exit, so one
    request stuck for its ~5 minutes of retries kept the app open after its
    window closed. These threads are daemons, so exit drops them.

    A fixed set of workers pulls items from a queue, rather than one thread
    per item, so each worker reuses its session's connection across PVs as
    the pool's workers did.
    """
    if max_workers <= 0:
        raise ValueError("max_workers must be greater than 0")
    results: List[Optional[R]] = [None] * len(items)
    errors: List[Optional[BaseException]] = [None] * len(items)
    todo: "queue.SimpleQueue" = queue.SimpleQueue()
    for index, item in enumerate(items):
        todo.put((index, item))

    workers = [
        threading.Thread(
            target=_work, args=(fn, todo, results, errors), daemon=True
        )
        for _ in range(min(max_workers, len(items)))
    ]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()
    first_error = next((e for e in errors if e is not None), None)
    if first_error is not None:
        raise first_error
    return results


def _work(fn, todo, results, errors) -> None:
    """Run fn on queued (index, item) pairs until the queue is empty."""
    while True:
        try:
            index, item = todo.get_nowait()
        except queue.Empty:
            return
        try:
            results[index] = fn(item)
        except BaseException as e:  # raised again in the caller's thread
            errors[index] = e


_local = threading.local()


def _session() -> requests.Session:
    """One session per thread; requests.Session is not thread-safe."""
    if not hasattr(_local, "session"):
        _local.session = requests.Session()
    return _local.session


def _request(
    method: str, url: str, timeout: float, **kwargs
) -> Optional[requests.Response]:
    """Send with retries. Returns None on 404; raises on anything else."""
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = _session().request(
                method, url, timeout=timeout, **kwargs
            )
        except requests.exceptions.Timeout as e:
            last_error = ArchiverTimeoutError(f"no answer from {url}: {e}")
        except requests.exceptions.ConnectionError as e:
            last_error = ArchiverConnectionError(f"cannot reach {url}: {e}")
        else:
            if response.status_code == 404:
                return None
            if response.ok:
                return response
            error = ArchiverError(f"HTTP {response.status_code} from {url}")
            if response.status_code not in RETRY_STATUS:
                raise error
            last_error = error
        if attempt < MAX_RETRIES:
            sleep(RETRY_DELAY * attempt)
    raise last_error


def _json(response: requests.Response, what: str):
    """response.json(), raising ArchiverError if the body isn't JSON.

    A proxy can report success but send a login or error page instead.
    """
    try:
        return response.json()
    except ValueError as e:  # requests reports bad JSON as a ValueError
        raise ArchiverError(f"{what}: response is not JSON: {e}") from e


def _aware(moment: datetime) -> datetime:
    return _localize(moment) if moment.tzinfo is None else moment


def _to_utc_iso(moment: datetime) -> str:
    return (
        _aware(moment)
        .astimezone(timezone.utc)
        .strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    )


def _localize(naive: datetime) -> datetime:
    """Read a naive time as Pacific, refusing times DST makes unclear.

    In the fall-back hour (e.g. 01:30 on the first Sunday of November) a wall
    time happens twice; in the spring-forward hour it never happens. Guessing
    would query the wrong window, so pass an aware datetime for those.
    """
    first = naive.replace(tzinfo=LOCAL_TZ, fold=0)
    second = naive.replace(tzinfo=LOCAL_TZ, fold=1)
    if first.utcoffset() != second.utcoffset():
        raise ValueError(
            f"{naive} is ambiguous or does not exist in Pacific time "
            "(daylight saving change); pass a timezone-aware datetime"
        )
    return first


def _timestamp(secs: int, nanos: int) -> datetime:
    # Not fromtimestamp(secs + nanos / 1e9): a float near 1.7e9 s resolves
    # about 0.24 us, so 1 in 17 timestamps came out 1 us off. That made
    # samples of two PVs collide, or stop colliding, when aligned.
    # Add in UTC, then convert: adding a timedelta to a Pacific datetime
    # resets fold to 0, which moved the fall-back hour's samples an hour early.
    moment = datetime.fromtimestamp(secs, tz=timezone.utc) + timedelta(
        microseconds=nanos / 1000
    )
    return moment.astimezone(LOCAL_TZ)


def _to_sample(datum: dict) -> ArchiverSample:
    return ArchiverSample(
        timestamp=_timestamp(datum["secs"], datum.get("nanos", 0)),
        value=datum["val"],
        severity=datum.get("severity", 0),
        status=datum.get("status", 0),
    )


def _to_frame(data: List[dict]) -> pd.DataFrame:
    samples = [_to_sample(datum) for datum in data]
    frame = pd.DataFrame(
        [
            (s.timestamp, s.value, s.severity, s.status, s.valid)
            for s in samples
        ],
        columns=COLUMNS,
    )
    frame["timestamp"] = frame["timestamp"].astype(TIMESTAMP_DTYPE)
    return frame
