"""Real EPICS Archiver Appliance client."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .models import ArchiverValue, ArchiveDataHandler


ARCHIVER_BASE_URL = "http://lcls-archapp.slac.stanford.edu/retrieval/data"
RANGE_ENDPOINT_SINGLE = f"{ARCHIVER_BASE_URL}/getData.json"
RANGE_ENDPOINT_MULTI = f"{ARCHIVER_BASE_URL}/getDataForPVs.json"


class ArchiverError(Exception):
    """Base archiver error."""


class ArchiverTimeoutError(ArchiverError):
    """Request timed out."""


class ArchiverConnectionError(ArchiverError):
    """Cannot connect to archiver."""


def _create_session() -> requests.Session:
    """Session with retry logic (3 retries on 5xx/429)."""
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "HEAD"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=4, pool_maxsize=8)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def is_archiver_available(timeout: float = 2.0) -> bool:
    """Quick connectivity check."""
    try:
        r = requests.head(RANGE_ENDPOINT_SINGLE, timeout=timeout)
        return r.status_code < 500
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        return False


def real_get_values_over_time_range(
    pv_list: List[str],
    start_time: datetime,
    end_time: datetime,
) -> Dict[str, ArchiveDataHandler]:
    """Fetch real data from archiver appliance."""
    if not pv_list:
        return {}

    start_str = start_time.isoformat(timespec="microseconds")
    end_str = end_time.isoformat(timespec="microseconds")
    params = {"from": start_str, "to": end_str, "pv": pv_list}

    endpoint = RANGE_ENDPOINT_MULTI if len(pv_list) > 1 else RANGE_ENDPOINT_SINGLE

    session = _create_session()

    try:
        response = session.get(endpoint, params=params, timeout=10)
        response.raise_for_status()
    except requests.exceptions.Timeout as e:
        raise ArchiverTimeoutError("Request timed out") from e
    except requests.exceptions.ConnectionError as e:
        raise ArchiverConnectionError("Cannot connect to archiver") from e
    except requests.exceptions.HTTPError as e:
        raise ArchiverError(f"HTTP {response.status_code}") from e

    data = response.json()
    result: Dict[str, ArchiveDataHandler] = {}
    for pv_data in data:
        pv_name = pv_data["meta"]["name"]
        archiver_values = []
        for point in pv_data.get("data", []):
            ts_secs = point["secs"] + point.get("nanos", 0) / 1e9
            ts = datetime.fromtimestamp(ts_secs, tz=timezone.utc)
            archiver_values.append(
                ArchiverValue(
                    value=point.get("val"),
                    timestamp=ts,
                    severity=int(point.get("severity", 0)),
                    status=int(point.get("status", 0)),
                )
            )
        result[pv_name] = ArchiveDataHandler.from_archiver_values(pv_name, archiver_values)
    return result