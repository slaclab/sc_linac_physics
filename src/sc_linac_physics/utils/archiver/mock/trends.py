"""Trend shapes and per-PV trend rules.

Each trend fn takes a normalized position t (0..1) and an amplitude, returning
the trend's contribution at that point. Noise is added separately by the
generators. _TREND_RULES map PV-name substrings to (trend, amplitude,
noise_scale); these seed defaults.yaml and remain as a code fallback.
"""

from __future__ import annotations

import math


def _trend_flat(t: float, amplitude: float) -> float:
    return 0.0


def _trend_linear(t: float, amplitude: float) -> float:
    return amplitude * t


def _trend_parabolic(t: float, amplitude: float) -> float:
    return amplitude * ((t - 0.5) ** 2)  # U-shape, minimum in the middle


def _trend_quadratic(t: float, amplitude: float) -> float:
    return amplitude * (t ** 2)  # upward curve


def _trend_sine(t: float, amplitude: float) -> float:
    return amplitude * math.sin(2 * math.pi * t)


TREND_FUNCTIONS = {
    "flat": _trend_flat,
    "linear": _trend_linear,
    "parabolic": _trend_parabolic,
    "quadratic": _trend_quadratic,
    "sine": _trend_sine,
}


# (PV-name substring, (trend, amplitude, noise_scale)). First match wins.
_TREND_RULES = [
    ("AACTMEANSUM", ("quadratic", 30.0, 1.0)),  # amplitude sum ramps up
    ("DS:LVL", ("sine", 4.0, 0.5)),             # downstream level oscillates
    ("US:LVL", ("sine", 4.0, 0.5)),             # upstream level oscillates
    ("PVJT", ("sine", 8.0, 1.0)),               # JT valve oscillates
    ("ORBV", ("sine", 8.0, 1.0)),
    ("DETUNE", ("sine", 5.0, 1.0)),             # detune oscillates
    ("DFBEST", ("sine", 5.0, 1.0)),
    ("DF_COLD", ("linear", 5.0, 1.0)),          # cold detune drifts
]

_DEFAULT_TREND = ("flat", 1.0, 1.0)


def _trend_for_pv(pv_name: str) -> tuple[str, float, float]:
    """Return (trend, amplitude, noise_scale) for a PV based on its name."""
    for pattern, params in _TREND_RULES:
        if pattern in pv_name:
            return params
    return _DEFAULT_TREND