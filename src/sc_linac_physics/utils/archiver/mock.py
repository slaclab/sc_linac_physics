"""Mock archiver data generator."""

from __future__ import annotations

import hashlib
import math
import random
from datetime import datetime, timedelta

from .models import ArchiverValue, ArchiveDataHandler

_LIVE_QUERY_TIMEOUT_S = 0.5


# --- Trend shapes ---------------------------------------------------------
# Each takes a normalized position t (0..1) and an amplitude, and returns the
# trend's contribution at that point. Noise is added separately.
def _trend_flat(t: float, amplitude: float) -> float:
    return 0.0

def _trend_linear(t: float, amplitude: float) -> float:
    return amplitude * t

def _trend_parabolic(t: float, amplitude: float) -> float:
    return amplitude * ((t - 0.5) ** 2)       # U-shape, minimum in the middle

def _trend_quadratic(t: float, amplitude: float) -> float:
    return amplitude * (t ** 2)               # upward curve

def _trend_sine(t: float, amplitude: float) -> float:
    return amplitude * math.sin(2 * math.pi * t)

TREND_FUNCTIONS = {
    "flat": _trend_flat,
    "linear": _trend_linear,
    "parabolic": _trend_parabolic,
    "quadratic": _trend_quadratic,
    "sine": _trend_sine,
}


# --- Per-PV trend rules ---------------------------------------------------
# Maps PV-name substrings to (trend, amplitude, noise_scale). Because each
# module (heatmap, cryo plots, tuner, ...) plots different PVs, mapping trends
# to PV patterns gives per-module behavior for free. Checked in order; first
# substring match wins. Amplitudes are scaled to each PV's value range so the
# trend is visible against the noise (see _analog_range).
_TREND_RULES = [
    # (PV-name substring, (trend, amplitude, noise_scale))
    ("AACTMEANSUM", ("quadratic", 30.0, 1.0)),   # amplitude sum ramps up
    ("DS:LVL",      ("sine", 4.0, 0.5)),          # downstream level oscillates
    ("US:LVL",      ("sine", 4.0, 0.5)),          # upstream level oscillates
    ("PVJT",        ("sine", 8.0, 1.0)),          # JT valve oscillates
    ("ORBV",        ("sine", 8.0, 1.0)),
    ("DETUNE",      ("sine", 5.0, 1.0)),          # detune oscillates
    ("DFBEST",      ("sine", 5.0, 1.0)),
    ("DF_COLD",     ("linear", 5.0, 1.0)),        # cold detune drifts
]

_DEFAULT_TREND = ("flat", 1.0, 1.0)


def _trend_for_pv(pv_name: str) -> tuple[str, float, float]:
    """Return (trend, amplitude, noise_scale) for a PV based on its name.

    Falls back to a flat trend if no rule matches.
    """
    for pattern, params in _TREND_RULES:
        if pattern in pv_name:
            return params
    return _DEFAULT_TREND


def _stable_seed(pv_name: str, start_time: datetime, end_time: datetime) -> int:
    key = f"{pv_name}|{start_time.isoformat()}|{end_time.isoformat()}".encode("utf-8")
    return int(hashlib.sha256(key).hexdigest()[:8], 16)


def _live_kind(pv_name: str) -> tuple[str, tuple] | None:
    """
    Ask the running IOC for a PV's native type.
    Returns (kind, enum_strings) or None if the IOC is unreachable.
    kind is one of "FLOAT", "INT", "ENUM", "STRING".
    """
    try:
        """try adding cache to avoid repeated queries"""
        from caproto.sync.client import read
        resp = read(pv_name, data_type="control", timeout=_LIVE_QUERY_TIMEOUT_S)
    except Exception:
        return None

    ct = getattr(resp, "data_type", None)
    if ct is None:
        return None

    name = getattr(ct, "name", str(ct)).upper()
    enum_strings = tuple(
        getattr(getattr(resp, "metadata", None), "enum_strings", ()) or ()
    )
    if "ENUM" in name:
        return "ENUM", enum_strings
    if "LONG" in name or "INT" in name or "CHAR" in name:
        return "INT", ()
    if "DOUBLE" in name or "FLOAT" in name:
        return "FLOAT", ()
    if "STRING" in name:
        return "STRING", ()
    return "FLOAT", ()  # safe default


class MockArchiveDataHandler:
    """Generates mock time-series for one PV."""

    def __init__(
        self,
        pv_name: str,
        start_time: datetime,
        end_time: datetime,
        sample_rate_hz: float = 1.0,
        trend: str | None = None,           # None -> auto-select from PV name
        trend_amplitude: float | None = None,
        noise_scale: float | None = None,
    ):
        self.pv_name = pv_name
        self.start_time = start_time
        self.end_time = end_time
        self.sample_rate_hz = sample_rate_hz

        # If any trend param is left unset, derive the whole set from the PV
        # name. If a caller passes explicit values, those win (per-call override).
        auto_trend, auto_amp, auto_noise = _trend_for_pv(pv_name)
        self.trend = trend if trend is not None else auto_trend
        self.trend_amplitude = (
            trend_amplitude if trend_amplitude is not None else auto_amp
        )
        self.noise_scale = noise_scale if noise_scale is not None else auto_noise

        self.rng = random.Random(_stable_seed(pv_name, start_time, end_time))
        self.kind, self.enum_strings = self._resolve_kind()

        self.timestamps = self._generate_timestamps()
        self.values = self._generate_values()
        self.severities = self._generate_severities()
        self.statuses = self._generate_statuses()

    def _resolve_kind(self) -> tuple[str, tuple]:
        pv = self.pv_name.upper()
        # CUDSTATUS/CUDSEVR are special-cased in _generate_values; skip the live query.
        if "CUDSTATUS" in pv or "CUDSEVR" in pv:
            return "STRING", ()

        live = _live_kind(self.pv_name)
        if live is not None:
            return live

        # Fallback heuristic when IOC unreachable
        if any(t in pv for t in ("_LTCH", "STATUS", "STATE", "READY", "ALRM", "BYP")):
            return "ENUM", ()
        if any(t in pv for t in ("COUNT", "CNT", "NUM", "RATE", "NBR", "INDEX")):
            return "INT", ()
        return "FLOAT", ()

    def _generate_timestamps(self) -> list[datetime]:
        timestamps: list[datetime] = []
        current = self.start_time
        interval = timedelta(seconds=1.0 / self.sample_rate_hz)

        while current <= self.end_time:
            timestamps.append(current)
            current += interval

        return timestamps

    def _generate_values(self) -> list[float | int | str]:
        # CUDSTATUS keeps its historical string behavior
        if "CUDSTATUS" in self.pv_name:
            return self._generate_fault_codes()

        # CUDSEVR is a severity: mostly 0 (NO_ALARM), occasionally 1/2
        if "CUDSEVR" in self.pv_name:
            return self._generate_severity_codes()

        if self.kind == "ENUM":
            return self._generate_enum_values()
        if self.kind == "INT":
            return self._generate_int_values()
        if self.kind == "STRING":
            return self._generate_fault_codes()

        # FLOAT: pick a realistic range, else generic.
        base, noise = self._analog_range()
        return self._generate_numeric_values(base_value=base, noise_range=noise)

    def _analog_range(self) -> tuple[float, float]:
        pv = self.pv_name

        # Cavity amplitude sum — axis 0-144, sit mid-range
        if "AACTMEANSUM" in pv:
            return 100.0, 5.0
        # Cavity amplitude/gradient — ~16.5 MV/m
        if any(k in pv for k in ("ADES", "AACT", "GDES", "GACT", "AACTMEAN")):
            return 16.5, 0.1
        if any(k in pv for k in ("PDES", "PACT")):
            return 0.0, 0.5
        if any(k in pv for k in ("DF", "DETUNE")):
            return 0.0, 10.0
        if "SEL_ASET" in pv:
            return 0.0, 0.5
        # JT valve position (ORBV) — axis 0-80, sit ~40%
        if "PVJT" in pv or "ORBV" in pv:
            return 40.0, 3.0
        # Downstream liquid level — axis 80-100, sit ~90
        if "DS:LVL" in pv:
            return 90.0, 2.0
        # Upstream liquid level — axis 60-80, sit ~70
        if "US:LVL" in pv:
            return 70.0, 2.0

        return 0.0, 0.1  # generic float default

    def _generate_int_values(self) -> list[int]:
        return [self.rng.randint(0, 5) for _ in self.timestamps]

    def _generate_enum_values(self) -> list[int]:
        # MODE showed enum_strings can be empty -> fall back to small cardinality.
        n_states = len(self.enum_strings) if self.enum_strings else 3
        values: list[int] = []
        for _ in self.timestamps:
            if self.rng.random() < 0.9:
                values.append(0)   # nominal state
            else:
                values.append(self.rng.randint(1, max(1, n_states - 1)))
        return values

    def _generate_numeric_values(self, base_value: float, noise_range: float) -> list[float]:
        trend_fn = TREND_FUNCTIONS.get(self.trend, _trend_flat)
        n = len(self.timestamps)
        values: list[float] = []
        for i in range(n):
            t = i / (n - 1) if n > 1 else 0.0                 # normalized 0..1
            trend = trend_fn(t, self.trend_amplitude)          # the visible shape
            noise = self.rng.uniform(
                -noise_range * self.noise_scale,
                 noise_range * self.noise_scale,
            )
            if self.rng.random() < 0.02:
                fault_spike = self.rng.uniform(
                    -5 * noise_range * self.noise_scale,
                     5 * noise_range * self.noise_scale,
                )
                v = base_value + trend + noise + fault_spike
            else:
                v = base_value + trend + noise
            values.append(v)
        return values

    def _generate_fault_codes(self) -> list[str]:
        cavity_num = self._extract_cavity_number()
        ok_value = cavity_num if cavity_num is not None else "1"
        fault_codes = ["BLM", "QNCH", "RES", "CTL"]

        # Give each cavity its OWN fault rate so the heatmap varies.
        # Most cavities healthy, a few bad — like real life.
        cavity_fault_rate = self.rng.random() ** 2 * 0.5   # 0..0.5, skewed toward low

        values: list[str] = []
        for _ in self.timestamps:
            if self.rng.random() > cavity_fault_rate:
                values.append(ok_value)                       # OK
            else:
                values.append(self.rng.choice(fault_codes))   # fault
        return values

    def _extract_cavity_number(self) -> str | None:
        """e.g. 'ACCL:L0B:0110:CUDSTATUS' -> '1'; '...0180...' -> '8'."""
        import re
        m = re.search(r":\w{2}(\d)0:", self.pv_name)
        return m.group(1) if m else None

    def _generate_severities(self) -> list[int]:
        severities: list[int] = []
        for _ in self.timestamps:
            if self.rng.random() < 0.9:
                severities.append(0)
            else:
                severities.append(self.rng.choice([1, 2]))
        return severities

    def _generate_severity_codes(self) -> list[int]:
        """CUDSEVR values: EPICS severity levels (0=NO_ALARM, 1=WARNING, 2=ALARM).
        count_severity expects exactly 0, 1, or 2, so emit those, mostly 0.
        """
        values: list[int] = []
        for _ in self.timestamps:
            r = self.rng.random()
            if r < 0.5:
                values.append(0)  # NO_ALARM
            elif r < 0.8:
                values.append(1)  # WARNING
            else:
                values.append(2)  # ALARM
        return values

    def _generate_statuses(self) -> list[int]:
        statuses: list[int] = []
        for _ in self.timestamps:
            if self.rng.random() < 0.95:
                statuses.append(0)
            else:
                statuses.append(1)
        return statuses


def mock_get_values_over_time_range(
    pv_list: list[str],
    start_time: datetime,
    end_time: datetime,
    trend: str | None = None,            # None -> auto-select per PV from its name
    trend_amplitude: float | None = None,
    noise_scale: float | None = None,
) -> dict[str, ArchiveDataHandler]:
    """Generate mock data for multiple PVs.

    If trend/amplitude/noise are left as None, each PV auto-selects a
    characteristic trend based on its name (see _trend_for_pv). Callers may
    pass explicit values to override for all PVs in the call.
    """
    if not pv_list:
        return {}

    result: dict[str, ArchiveDataHandler] = {}
    for pv_name in pv_list:
        mock = MockArchiveDataHandler(
            pv_name, start_time, end_time,
            trend=trend, trend_amplitude=trend_amplitude, noise_scale=noise_scale,
        )

        archiver_values = [
            ArchiverValue(value=val, timestamp=ts, severity=sev, status=stat)
            for val, ts, sev, stat in zip(
                mock.values,
                mock.timestamps,
                mock.severities,
                mock.statuses,
            )
        ]
        result[pv_name] = ArchiveDataHandler.from_archiver_values(pv_name, archiver_values)

    return result