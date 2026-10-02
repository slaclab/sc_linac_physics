"""Per-kind value generators. Each takes an rng, timestamps, and a PVProfile."""

from __future__ import annotations

import random
import re

from .trends import TREND_FUNCTIONS, _trend_flat


def generate_numeric(rng: random.Random, n: int, profile) -> list[float]:
    trend_fn = TREND_FUNCTIONS.get(profile.trend, _trend_flat)
    noise_range = profile.noise
    values: list[float] = []
    for i in range(n):
        t = i / (n - 1) if n > 1 else 0.0
        trend = trend_fn(t, profile.trend_amplitude)
        noise = rng.uniform(
            -noise_range * profile.noise_scale,
            noise_range * profile.noise_scale,
        )
        if rng.random() < profile.spike_prob:
            spike = rng.uniform(
                -profile.spike_scale * noise_range * profile.noise_scale,
                profile.spike_scale * noise_range * profile.noise_scale,
            )
            values.append(profile.base + trend + noise + spike)
        else:
            values.append(profile.base + trend + noise)
    return values


def generate_int(rng: random.Random, n: int) -> list[int]:
    return [rng.randint(0, 5) for _ in range(n)]


def generate_enum(rng: random.Random, n: int, enum_strings: tuple) -> list[int]:
    n_states = len(enum_strings) if enum_strings else 3
    values: list[int] = []
    for _ in range(n):
        if rng.random() < 0.9:
            values.append(0)  # nominal
        else:
            values.append(rng.randint(1, max(1, n_states - 1)))
    return values


def _extract_cavity_number(pv_name: str) -> str | None:
    """e.g. 'ACCL:L0B:0110:CUDSTATUS' -> '1'; '...0180...' -> '8'."""
    m = re.search(r":\w{2}(\d)0:", pv_name)
    return m.group(1) if m else None


def generate_fault_codes(rng: random.Random, n: int, pv_name: str) -> list[str]:
    cavity_num = _extract_cavity_number(pv_name)
    ok_value = cavity_num if cavity_num is not None else "1"
    fault_codes = ["BLM", "QNCH", "RES", "CTL"]

    # Each cavity gets its own fault rate so the heatmap varies. Skewed low.
    cavity_fault_rate = rng.random() ** 2 * 0.5

    values: list[str] = []
    for _ in range(n):
        if rng.random() > cavity_fault_rate:
            values.append(ok_value)
        else:
            values.append(rng.choice(fault_codes))
    return values


def generate_severity_codes(rng: random.Random, n: int) -> list[int]:
    """CUDSEVR: EPICS severity (0=NO_ALARM, 1=WARNING, 2=ALARM), mostly 0."""
    values: list[int] = []
    for _ in range(n):
        r = rng.random()
        if r < 0.5:
            values.append(0)
        elif r < 0.8:
            values.append(1)
        else:
            values.append(2)
    return values


def generate_severities(rng: random.Random, n: int) -> list[int]:
    out: list[int] = []
    for _ in range(n):
        out.append(0 if rng.random() < 0.9 else rng.choice([1, 2]))
    return out


def generate_statuses(rng: random.Random, n: int) -> list[int]:
    out: list[int] = []
    for _ in range(n):
        out.append(0 if rng.random() < 0.95 else 1)
    return out