"""Deterministic seeding.

Same PV + (quantized) time range + profile => same data. Mirrors the real
archiver's reproducibility. Timestamps are normalized to UTC and quantized to
whole seconds so tiny epoch jitter between repeated PyDM requests does not
regenerate a different series.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone


def _quantize(dt: datetime) -> int:
    """UTC epoch seconds (int). Naive datetimes are assumed to be UTC."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.astimezone(timezone.utc).timestamp())


def _stable_seed(
    pv_name: str,
    start_time: datetime,
    end_time: datetime,
    profile_hash: str = "",
) -> int:
    """Return a stable 32-bit-ish int seed for random.Random."""
    key = f"{pv_name}|{_quantize(start_time)}|{_quantize(end_time)}|{profile_hash}"
    return int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:8], 16)