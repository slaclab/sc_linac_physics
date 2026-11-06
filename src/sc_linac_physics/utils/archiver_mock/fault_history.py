"""Mock CUDSTATUS / CUDSEVR, written the way the cavity fault runner writes them.

BackendCavity._update_status_pvs writes, together:
- OK: CUDSTATUS = the cavity number ("1".."8"), CUDSEVR = 0
- a fault: CUDSTATUS = its three-letter code, CUDSEVR = its Severity column
  in faults.csv (1, 2, 4 or 5; count_severity counts 4 and 5 as invalid)

So both PVs here come from one timeline per cavity, sampled at the same
times, and codes and severities come from the runner's own fault list. Each
cavity gets its own fault rate, so a heatmap of mock data varies.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from functools import lru_cache
from typing import List, Tuple

import numpy as np
import pandas as pd

from sc_linac_physics.utils.archiver import COLUMNS, LOCAL_TZ

STATUS_SUFFIX = ":CUDSTATUS"
SEVERITY_SUFFIX = ":CUDSEVR"

# A cavity's fault rate is MAX_FAULTS_PER_DAY * u**2, u uniform on [0, 1):
# most cavities quiet, a few busy. Faults last MEAN_FAULT_MINUTES on average.
MAX_FAULTS_PER_DAY = 40.0
MEAN_FAULT_MINUTES = 10.0
MAX_FAULTS_PER_WINDOW = 5_000
# BackendCavity.process_fault_history rounds timestamps to 10 ms before it
# pairs a status with a severity. Two transitions 20 ms apart stay distinct
# after that rounding, so a short fault keeps its own severity.
MIN_EVENT_SPACING_S = 0.02


def is_fault_history_pv(pv: str) -> bool:
    return pv.endswith((STATUS_SUFFIX, SEVERITY_SUFFIX))


def fault_history_frame(
    pv: str, start: datetime, end: datetime
) -> pd.DataFrame:
    """One cavity's mock CUDSTATUS or CUDSEVR between start and end (UTC)."""
    prefix = pv.rsplit(":", 1)[0]
    times, codes, severities = _timeline(prefix, start, end)
    values = codes if pv.endswith(STATUS_SUFFIX) else severities
    n = len(times)
    return pd.DataFrame(
        {
            "timestamp": pd.to_datetime(times, unit="s", utc=True)
            .tz_convert(LOCAL_TZ)
            .as_unit("us"),
            "value": values,
            "severity": np.zeros(n, dtype=int),  # the PVs' own alarm state
            "status": np.zeros(n, dtype=int),
            "valid": np.ones(n, dtype=bool),
        },
        columns=COLUMNS,
    )


def cavity_number(prefix: str) -> str:
    """'ACCL:L1B:0210' -> '1', 'ACCL:L1B:H180' -> '8'."""
    match = re.search(r":\w{2}(\d)0$", prefix)
    return match.group(1) if match else "1"


def _timeline(
    prefix: str, start: datetime, end: datetime
) -> Tuple[np.ndarray, List[str], List[int]]:
    """Event times (epoch s), CUDSTATUS values, CUDSEVR values.

    Seeded by the cavity prefix and window only, so both PVs of a cavity get
    the same timeline whichever is fetched first.
    """
    t0, t1 = start.timestamp(), end.timestamp()
    ok = cavity_number(prefix)
    if t1 <= t0:
        return np.array([]), [], []
    key = f"{prefix}|{int(t0)}|{int(t1)}"
    rng = np.random.default_rng(
        int(hashlib.sha256(key.encode()).hexdigest()[:16], 16)
    )

    rate = MAX_FAULTS_PER_DAY * rng.random() ** 2
    n_faults = min(
        int(rng.poisson(rate * (t1 - t0) / 86400.0)), MAX_FAULTS_PER_WINDOW
    )
    fault_starts = np.sort(rng.uniform(t0, t1, n_faults))
    durations = rng.exponential(MEAN_FAULT_MINUTES * 60.0, n_faults)
    fault_codes = _fault_codes(prefix)
    rows = rng.integers(0, len(fault_codes), n_faults)

    times, codes, severities = [t0], [ok], [0]  # OK when the window opens
    for i, (fault_start, row) in enumerate(zip(fault_starts, rows)):
        next_start = fault_starts[i + 1] if i + 1 < n_faults else t1
        if fault_start < times[-1] + MIN_EVENT_SPACING_S:
            continue  # starts before (or right as) the previous one cleared
        code, severity = fault_codes[row]
        times.append(fault_start)
        codes.append(code)
        severities.append(severity)
        cleared = fault_start + max(durations[i], MIN_EVENT_SPACING_S)
        if cleared < next_start:
            times.append(cleared)
            codes.append(ok)
            severities.append(0)
    return np.array(times), codes, severities


def _fault_codes(prefix: str) -> Tuple[Tuple[str, int], ...]:
    """(three-letter code, Severity) for every fault the runner checks on
    this cavity.

    Same row filter as BackendCavity._build_fault_pv: RACK rows only for the
    cavity's own rack (A = cavities 1-4, B = 5-8), and CM rows only for the
    matching CM Type (3.9 for H1/H2, 1.3 for the rest).
    """
    harmonic = prefix.rsplit(":", 1)[-1].startswith("H")
    rack = "A" if int(cavity_number(prefix)) <= 4 else "B"
    return _fault_codes_for(rack, harmonic)


@lru_cache(maxsize=4)
def _fault_codes_for(rack: str, harmonic: bool) -> Tuple[Tuple[str, int], ...]:
    # Data only: the cavity display's own fault list, so mock codes are ones
    # the heatmap's code filter knows.
    from sc_linac_physics.displays.cavity_display.utils.utils import parse_csv

    skip_cm_type = "1.3" if harmonic else "3.9"
    return tuple(
        (row["Three Letter Code"], int(row["Severity"]))
        for row in parse_csv()
        if not (row["Level"] == "RACK" and row["Rack"] != rack)
        and not (row["Level"] == "CM" and row["CM Type"] == skip_cm_type)
    )
