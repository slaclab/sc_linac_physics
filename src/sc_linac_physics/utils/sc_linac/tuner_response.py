"""Per-cavity H1/H2 stepper response curves: microsteps vs real detune.

The H1/H2 tuners don't move a fixed number of Hz per microstep. Some cavities
move about half as far per microstep between -300 and -200 kHz as near
resonance (Lisa Zacarias, "Stepper SCALE on the harmonic linearizers",
2026-11-02). One SCALE can't size moves across that, so long HL tunes size
them from each cavity's measured curve instead.

The curves are packaged in data/hl_tuner_response.csv. Each row is one 10 kHz
bin: cavity PV prefix, real detune (CHIRP:DF + FREQ_OFFSET) in Hz, microsteps
from cold landing, and whether archived moves covered that bin. The file's
header says where it came from. sc-hl-tuner-curves refits it.
"""

import csv
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional, Union

import numpy as np

CURVES_CSV = Path(__file__).parent / "data" / "hl_tuner_response.csv"


class TunerResponse:
    """One cavity's microsteps from cold landing as a function of real detune.

    Between bins the curve is linear. Past either end, the end bin's slope is
    extended, so a detune a little outside the fitted range still gets a step
    estimate. covered() says when that has happened.
    """

    def __init__(self, detune_hz, usteps_from_cold, covered):
        order = np.argsort(detune_hz)
        self.detune_hz = np.asarray(detune_hz, dtype=float)[order]
        self.usteps_from_cold = np.asarray(usteps_from_cold, dtype=float)[order]
        self.bin_covered = np.asarray(covered, dtype=bool)[order]
        if len(self.detune_hz) < 2:
            raise ValueError("a response curve needs at least two bins")
        if np.any(np.diff(self.usteps_from_cold) <= 0):
            raise ValueError(
                "usteps_from_cold must rise with detune: a flat or falling "
                "curve would mean steps that don't move the detune"
            )

    @classmethod
    def for_cavity(cls, cavity) -> Optional["TunerResponse"]:
        """The curve for a cavity, or None if it has none.

        cavity is a Cavity or its PV prefix, e.g. "ACCL:L1B:H110:".
        """
        prefix = getattr(cavity, "pv_prefix", cavity)
        return _load_curves().get(prefix)

    def position(self, real_hz: float) -> float:
        """Microsteps from cold landing at real detune real_hz."""
        x, y = self.detune_hz, self.usteps_from_cold
        if real_hz < x[0]:
            return y[0] + (real_hz - x[0]) * (y[1] - y[0]) / (x[1] - x[0])
        if real_hz > x[-1]:
            return y[-1] + (real_hz - x[-1]) * (y[-1] - y[-2]) / (x[-1] - x[-2])
        return float(np.interp(real_hz, x, y))

    def steps_between(self, from_hz: float, to_hz: float) -> float:
        """Signed microsteps to go from from_hz to to_hz. Positive raises
        the detune."""
        return self.position(to_hz) - self.position(from_hz)

    def hz_per_microstep(self, real_hz: float) -> float:
        """Local Hz per microstep at real_hz, from the bin containing it."""
        x, y = self.detune_hz, self.usteps_from_cold
        i = int(np.clip(np.searchsorted(x, real_hz) - 1, 0, len(x) - 2))
        return (x[i + 1] - x[i]) / (y[i + 1] - y[i])

    def covered(self, from_hz: float, to_hz: float) -> bool:
        """Whether every bin from from_hz to to_hz came from archived moves.

        False if either end is outside the curve, or any bin between was
        filled from a neighbor.
        """
        lo, hi = sorted((from_hz, to_hz))
        x = self.detune_hz
        if lo < x[0] or hi > x[-1]:
            return False
        first = max(int(np.searchsorted(x, lo, side="right")) - 1, 0)
        last = int(np.searchsorted(x, hi, side="left"))
        return bool(np.all(self.bin_covered[first : last + 1]))


@lru_cache(maxsize=None)
def _load_curves(
    path: Union[str, Path] = CURVES_CSV,
) -> Dict[str, TunerResponse]:
    """Read the curves once, on first use, keyed by cavity PV prefix."""
    rows: Dict[str, list] = {}
    with open(path, newline="") as f:
        lines = (line for line in f if not line.startswith("#"))
        for row in csv.DictReader(lines):
            rows.setdefault(row["cavity_pv_prefix"], []).append(row)
    return {
        prefix: TunerResponse(
            [float(r["real_detune_hz"]) for r in cav_rows],
            [float(r["usteps_from_cold"]) for r in cav_rows],
            [r["covered"].strip() == "True" for r in cav_rows],
        )
        for prefix, cav_rows in rows.items()
    }
