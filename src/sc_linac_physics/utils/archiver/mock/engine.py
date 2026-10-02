"""Orchestrator: MockArchiveDataHandler.

Public constructor signature is unchanged from the original mock.py. Behavior
now flows through PROFILE_STORE so it is user-adjustable, while explicit
per-call trend/amplitude/noise arguments still override for backward compat.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta

from .profiles import PROFILE_STORE
from .resolver import resolve_kind
from .seeding import _stable_seed
from . import generators as gen


class MockArchiveDataHandler:
    """Generates mock time-series for one PV."""

    def __init__(
        self,
        pv_name: str,
        start_time: datetime,
        end_time: datetime,
        sample_rate_hz: float | None = None,
        trend: str | None = None,
        trend_amplitude: float | None = None,
        noise_scale: float | None = None,
    ):
        self.pv_name = pv_name
        self.start_time = start_time
        self.end_time = end_time

        # Resolve type first (CUDSTATUS/CUDSEVR handled in _generate_values).
        self.kind, self.enum_strings = resolve_kind(pv_name)

        # Build the effective profile, then apply per-call overrides.
        base_profile = PROFILE_STORE.resolve(pv_name, self.kind)
        self.profile = base_profile.merged(
            trend=trend,
            trend_amplitude=trend_amplitude,
            noise_scale=noise_scale,
            sample_rate_hz=sample_rate_hz,
        )

        self.sample_rate_hz = self.profile.sample_rate_hz

        # Expose these for any legacy callers/tests that peeked at them.
        self.trend = self.profile.trend
        self.trend_amplitude = self.profile.trend_amplitude
        self.noise_scale = self.profile.noise_scale

        self.rng = random.Random(
            _stable_seed(pv_name, start_time, end_time, self.profile.hash())
        )

        self.timestamps = self._generate_timestamps()
        self.values = self._generate_values()
        self.severities = gen.generate_severities(self.rng, len(self.timestamps))
        self.statuses = gen.generate_statuses(self.rng, len(self.timestamps))

    def _generate_timestamps(self) -> list[datetime]:
        timestamps: list[datetime] = []
        current = self.start_time
        interval = timedelta(seconds=1.0 / self.sample_rate_hz)
        while current <= self.end_time:
            timestamps.append(current)
            current += interval
        return timestamps

    def _generate_values(self):
        pv = self.pv_name
        n = len(self.timestamps)

        if "CUDSTATUS" in pv:
            return gen.generate_fault_codes(self.rng, n, pv)
        if "CUDSEVR" in pv:
            return gen.generate_severity_codes(self.rng, n)

        kind = self.profile.kind or self.kind
        if kind == "ENUM":
            return gen.generate_enum(self.rng, n, self.enum_strings)
        if kind == "INT":
            return gen.generate_int(self.rng, n)
        if kind == "STRING":
            return gen.generate_fault_codes(self.rng, n, pv)

        # FLOAT
        return gen.generate_numeric(self.rng, n, self.profile)