"""Client for the LCLS archiver appliance.

Replaces ``lcls_tools.common.data.archiver``, which is deprecated.

Measured against the archiver on site (2026-10-05): the time goes into the
archiver reading each PV, not into the response. JSON, CSV and raw protobuf
responses took about as long. So this sends one request per PV and runs up to
MAX_WORKERS of them at once. On 18 PVs that took 0.5 s against 2-3 s for one
multi-PV request (getDataForPVs.json, which lcls_tools used). A PV the
archiver does not know then fails only its own request; the multi-PV endpoint
returns 404 for the whole batch.

Value-at-time is the exception: one POST naming every PV took the same 7-8 s
as splitting it into parallel single-PV POSTs, so it stays one request.

In every test, the first query of a session was slow (55-138 s) whichever
method went first. CHECK: is that the archiver warming up after idle?

Differences from lcls_tools, on purpose:

- Timestamps are timezone-aware (America/Los_Angeles). lcls_tools returned
  naive datetimes in the local time of whatever machine ran the code.
- HTTP errors raise. lcls_tools' get_data_at_time returned {} on one, which a
  caller cannot tell apart from "no data".

Endpoints: https://epicsarchiver.readthedocs.io/en/stable/user/userguide.html
("Retrieving data using other tools" and "Save/Restore API"). That guide is
old; where it is silent, this follows what the LCLS archiver did when tested.
"""

import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from time import sleep
from typing import Dict, Iterable, List, Optional, Union
from zoneinfo import ZoneInfo

import pandas as pd
import requests

from sc_linac_physics.utils.epics.config import EPICS_INVALID_VAL

ARCHIVER_URL = "http://lcls-archapp.slac.stanford.edu/retrieval/data"

# Same limit FaultDataFetcher.MAX_WORKERS uses against this archiver.
MAX_WORKERS = 8

RANGE_TIMEOUT = 90.0  # seconds per PV request; long windows are slow to read
# Same default as lcls_tools. A cold query can take minutes (138 s measured);
# a repeat of it took 7 s, so a retry after a timeout often succeeds.
AT_TIME_TIMEOUT = 15.0

# Same retry policy as utils/epics PVConfig: 3 tries, 0.5 s * attempt between.
MAX_RETRIES = 3
RETRY_DELAY = 0.5

LOCAL_TZ = ZoneInfo("America/Los_Angeles")

COLUMNS = ["timestamp", "value", "severity", "status", "valid"]

Value = Union[float, int, str]


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
    finished. Timeouts and connection errors are retried, then raised.
    """
    pvs = list(pvs)
    params = {"from": _to_utc_iso(start), "to": _to_utc_iso(end)}

    def fetch(pv: str) -> Optional[pd.DataFrame]:
        response = _request(
            "GET",
            f"{ARCHIVER_URL}/getData.json",
            timeout,
            params={**params, "pv": pv},
        )
        if response is None:
            return None
        payload = response.json()
        return _to_frame(payload[0]["data"] if payload else [])

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        frames = dict(zip(pvs, pool.map(fetch, pvs)))

    missing = [pv for pv, frame in frames.items() if frame is None]
    if missing:
        raise PVNotArchivedError(missing)
    return frames


def get_values_at_time(
    pvs: Iterable[str], at: datetime, timeout: float = AT_TIME_TIMEOUT
) -> Dict[str, ArchiverSample]:
    """Return each PV's archived value at a moment, in one request.

    One batch POST is as fast as one request per PV here (measured), unlike
    get_values_over_time_range.

    A PV the archiver has no value for is left out of the result. Naive
    datetimes are read as America/Los_Angeles.
    """
    response = _request(
        "POST",
        f"{ARCHIVER_URL}/getDataAtTime",
        timeout,
        params={"at": _to_utc_iso(at), "includeProxies": "true"},
        json=list(pvs),  # the Save/Restore API takes a JSON list of names
    )
    if response is None:  # 404: none of the PVs are known
        return {}
    return {pv: _to_sample(datum) for pv, datum in response.json().items()}


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
            if response.status_code < 500:
                if not response.ok:
                    raise ArchiverError(
                        f"HTTP {response.status_code} from {url}"
                    )
                return response
            last_error = ArchiverError(
                f"HTTP {response.status_code} from {url}"
            )
        if attempt < MAX_RETRIES:
            sleep(RETRY_DELAY * attempt)
    raise last_error


def _to_utc_iso(moment: datetime) -> str:
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=LOCAL_TZ)
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _timestamp(secs: int, nanos: int) -> datetime:
    return datetime.fromtimestamp(secs + nanos / 1e9, tz=LOCAL_TZ)


def _to_sample(datum: dict) -> ArchiverSample:
    return ArchiverSample(
        timestamp=_timestamp(datum["secs"], datum.get("nanos", 0)),
        value=datum["val"],
        severity=datum.get("severity", 0),
        status=datum.get("status", 0),
    )


def _to_frame(data: List[dict]) -> pd.DataFrame:
    samples = [_to_sample(datum) for datum in data]
    return pd.DataFrame(
        [
            (s.timestamp, s.value, s.severity, s.status, s.valid)
            for s in samples
        ],
        columns=COLUMNS,
    )
