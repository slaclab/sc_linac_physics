"""Synthetic archiver data, in the same frames utils.archiver returns.

Same PV, window and profile give the same data every time: the random
generator is seeded from all three. Ported from #280 (Sandy Paez Olivarez).
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Dict, Iterable, Optional

import numpy as np
import pandas as pd

from sc_linac_physics.utils.archiver import COLUMNS, LOCAL_TZ, _localize
from sc_linac_physics.utils.archiver_mock.fault_history import (
    fault_history_frame,
    is_fault_history_pv,
)
from sc_linac_physics.utils.archiver_mock.ioc_types import ioc_kind
from sc_linac_physics.utils.archiver_mock.profiles import (
    PROFILE_STORE,
    PVProfile,
    ProfileStore,
)

# Samples per PV per window, at most. At the default 1 Hz, a two-week window
# would be 1.2 M samples per PV; the fault heatmap asks for 960 PVs.
MAX_SAMPLES = 10_000

# Fraction of analog samples marked MINOR or MAJOR, and with a nonzero
# status. Neither is ever INVALID, so every sample is valid.
ALARM_FRACTION = 0.10
STATUS_FRACTION = 0.05


def _flat(t, amplitude):
    return np.zeros_like(t)


TRENDS = {
    "flat": _flat,
    "linear": lambda t, a: a * t,
    "parabolic": lambda t, a: a * (t - 0.5) ** 2,  # minimum mid-window
    "quadratic": lambda t, a: a * t**2,
    "sine": lambda t, a: a * np.sin(2 * np.pi * t),  # one period
}


def mock_values_over_time_range(
    pvs: Iterable[str],
    start: datetime,
    end: datetime,
    store: Optional[ProfileStore] = None,
) -> Dict[str, pd.DataFrame]:
    """Mock of utils.archiver.get_values_over_time_range.

    One frame per PV with columns COLUMNS, timestamps aware Pacific. Naive
    datetimes are read as Pacific, as the real client reads them.
    """
    store = store or PROFILE_STORE
    start_utc, end_utc = _to_utc(start), _to_utc(end)
    return {
        pv: _frame(pv, start_utc, end_utc, store) for pv in dict.fromkeys(pvs)
    }


def guess_kind(pv: str) -> str:
    """FLOAT, INT or ENUM from the PV name, when no rule sets one."""
    name = pv.upper()
    if any(t in name for t in ("_LTCH", "STATUS", "STATE", "READY", "ALRM")):
        return "ENUM"
    if any(t in name for t in ("COUNT", "CNT", "NUM", "NBR", "INDEX")):
        return "INT"
    return "FLOAT"


def _to_utc(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        moment = _localize(moment)
    return moment.astimezone(timezone.utc)


def _frame(
    pv: str, start: datetime, end: datetime, store: ProfileStore
) -> pd.DataFrame:
    if end <= start:
        return pd.DataFrame(columns=COLUMNS)
    if is_fault_history_pv(pv):
        return fault_history_frame(pv, start, end)
    # A rule's kind wins, then the running IOC's, then the name
    kind = store.rule_kind(pv) or ioc_kind(pv) or guess_kind(pv)
    profile = store.resolve(pv, kind)
    rng = np.random.default_rng(_seed(pv, start, end, profile))

    window = (end - start).total_seconds()
    n = int(min(window * profile.sample_rate_hz + 1, MAX_SAMPLES))
    offsets = np.linspace(0.0, window, n)
    timestamps = (
        pd.to_datetime(start.timestamp() + offsets, unit="s", utc=True)
        .tz_convert(LOCAL_TZ)
        .as_unit("us")
    )

    if kind == "ENUM":
        nonzero = rng.random(n) >= 0.9  # 90% in state 0
        values = np.where(nonzero, rng.integers(1, 3, n), 0)
    elif kind == "INT":
        values = rng.integers(0, 6, n)
    else:
        values = _numeric(rng, offsets / window if window else offsets, profile)

    alarmed = rng.random(n) < ALARM_FRACTION
    severity = np.where(alarmed, rng.integers(1, 3, n), 0)
    status = np.where(rng.random(n) < STATUS_FRACTION, 1, 0)
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "value": values,
            "severity": severity,
            "status": status,
            "valid": np.ones(n, dtype=bool),
        },
        columns=COLUMNS,
    )


def _numeric(rng, t, profile: PVProfile) -> np.ndarray:
    """base + trend + uniform noise, with occasional spikes."""
    trend = TRENDS.get(profile.trend, _flat)(t, profile.trend_amplitude)
    half_width = profile.noise * profile.noise_scale
    noise = rng.uniform(-half_width, half_width, t.size)
    spikes = np.where(
        rng.random(t.size) < profile.spike_prob,
        rng.uniform(-1.0, 1.0, t.size) * profile.spike_scale * half_width,
        0.0,
    )
    return profile.base + trend + noise + spikes


def _seed(pv: str, start: datetime, end: datetime, profile: PVProfile) -> int:
    # Whole seconds, so repeated requests a few ms apart get the same data
    key = (
        f"{pv}|{int(start.timestamp())}|{int(end.timestamp())}|{profile.hash()}"
    )
    return int(hashlib.sha256(key.encode()).hexdigest()[:16], 16)
