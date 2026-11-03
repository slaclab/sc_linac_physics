"""Tuning runs on H1/H2 cavities, checked against the packaged curves.

Read-only. Every PV is read from the archiver, none over CA:

- ``<cavity>STEP:REG_TOTSGN``: signed stepper position, microsteps
- ``<cavity>CHIRP:DF``: detune in chirp mode, Hz
- ``ACCL:L1B:H{1,2}00:RACK{A,B}:FREQ_OFFSET``: the rack's offset, Hz

Real detune = ``CHIRP:DF + FREQ_OFFSET``. ``find_moves``,
``unwrap_position`` and the segment rule in ``find_runs`` are the code that
fitted ``hl_tuner_response.csv`` (kept in Drive, Planning/"FREQ_OFFSET
automation on HL"/hl_tuner_curves_fit/hl_tuner_curves.py), with its
constants. That code reproduces the CSV to <50 microsteps on 2023-2025 data.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from sc_linac_physics.utils.archiver import (
    ArchiverError,
    PVNotArchivedError,
    get_series,
)

CURVES_CSV = (
    Path(__file__).resolve().parents[2]
    / "utils/sc_linac/data/hl_tuner_response.csv"
)

# Moves
MOVE_GAP_S = 30  # REG_TOTSGN changes this close together are one move
BEFORE_S = 30  # detune before = median CHIRP:DF over the 30 s before
AFTER_S = (5, 60)  # detune after = median over 5-60 s after the move ends
MIN_SAMPLES = 3  # CHIRP:DF samples needed in each window
SETTLE_HZ = 200  # "after" samples must spread less than this to count

# Position and runs
RESET_JUMP = 2e6  # one-sample jumps this big are REG_TOTSGN resets
RUN_GAP = timedelta(minutes=10)  # moves closer than this are one run
MAX_SEGMENT_USTEPS = 3e7  # longer segments are dropped as bad points

# The plan's refit trigger: a run's actual / curve microsteps leaves this.
RATIO_BAND = (0.85, 1.15)

logger = logging.getLogger(__name__)


@dataclass
class Run:
    """One tuning run: moves less than RUN_GAP apart."""

    start: pd.Timestamp
    # (position in microsteps, real detune in Hz), before and after moves
    points: List[Tuple[float, float]] = field(default_factory=list)
    # (low Hz, high Hz, microsteps) for the stretches the ratio counts
    segments: List[Tuple[float, float, float]] = field(default_factory=list)


def load_curves(path: Path = CURVES_CSV) -> Dict[str, pd.DataFrame]:
    """The packaged curves, keyed by cavity PV prefix, sorted by detune."""
    frame = pd.read_csv(path, comment="#")
    return {
        prefix: curve.sort_values("real_detune_hz").reset_index(drop=True)
        for prefix, curve in frame.groupby("cavity_pv_prefix", sort=True)
    }


def archive_end(path: Path = CURVES_CSV) -> datetime:
    """End of the archive the curves were fitted on, from the CSV header.

    The header has a line like "Archive 2023-01-01 to 2026-01-01".
    """
    with open(path) as f:
        for line in f:
            if not line.startswith("#"):
                break
            found = re.search(r"Archive \S+ to (\d{4}-\d{2}-\d{2})", line)
            if found:
                return datetime.fromisoformat(found.group(1))
    raise ValueError(f"No 'Archive ... to <date>' line in {path}'s header")


def rack_offset_pv(prefix: str) -> str:
    """Rack FREQ_OFFSET PV for a cavity prefix like ``ACCL:L1B:H110:``.

    Cavities 1-4 are on rack A, 5-8 on rack B.
    """
    cm, cavity = prefix[:-3], int(prefix[-3])
    return f"{cm}00:RACK{'A' if cavity <= 4 else 'B'}:FREQ_OFFSET"


def _last_at(series: pd.Series, t) -> float:
    """The series' value at t: its last sample at or before t."""
    k = series.index.searchsorted(t, side="right") - 1
    return float(series.iloc[k]) if k >= 0 else np.nan


def _offset_in(offset: pd.Series, a, b) -> float:
    """FREQ_OFFSET over [a, b], or NaN if it took more than one value there."""
    values = {_last_at(offset, a), *offset[a:b]}
    return values.pop() if len(values) == 1 else np.nan


def unwrap_position(steps: pd.Series) -> pd.Series:
    """REG_TOTSGN with its resets undone.

    CHECK: a reset shows as a one-sample jump over RESET_JUMP. Real move
    samples stayed under 1.3M in 2023-2025; is that a hardware limit?
    """
    jump = steps.diff().fillna(0)
    return steps - jump.where(jump.abs() > RESET_JUMP, 0).cumsum()


def find_moves(
    steps: pd.Series, chirp_df: pd.Series, offset: pd.Series
) -> pd.DataFrame:
    """Every stepper move, with real detune before and after it.

    A move is a run of REG_TOTSGN changes with no gap over MOVE_GAP_S. Pass
    REG_TOTSGN through unwrap_position first. Moves without MIN_SAMPLES of
    CHIRP:DF in both windows are dropped. ``offset_stable`` is False if
    FREQ_OFFSET took more than one value inside a window.
    """
    rows = []
    changed = steps.diff().fillna(0).to_numpy() != 0
    t = steps.index
    i = 1
    while i < len(steps):
        if not changed[i]:
            i += 1
            continue
        j = i
        while (
            j + 1 < len(steps)
            and changed[j + 1]
            and (t[j + 1] - t[j]).total_seconds() <= MOVE_GAP_S
        ):
            j += 1
        b0, b1 = t[i] - timedelta(seconds=BEFORE_S), t[i]
        a0 = t[j] + timedelta(seconds=AFTER_S[0])
        a1 = t[j] + timedelta(seconds=AFTER_S[1])
        before, after = chirp_df[b0:b1], chirp_df[a0:a1]
        if len(before) >= MIN_SAMPLES and len(after) >= MIN_SAMPLES:
            off_before = _offset_in(offset, b0, b1)
            off_after = _offset_in(offset, a0, a1)
            rows.append(
                dict(
                    t=t[j],
                    usteps=steps.iloc[j] - steps.iloc[i - 1],
                    before_hz=before.median() + off_before,
                    after_hz=after.median() + off_after,
                    after_spread_hz=after.max() - after.min(),
                    offset_stable=not (
                        np.isnan(off_before) or np.isnan(off_after)
                    ),
                )
            )
        i = j + 1
    return pd.DataFrame(rows)


def find_runs(moves: pd.DataFrame, position: pd.Series) -> List[Run]:
    """Group moves into runs, with the points and segments of each.

    Points are (position, real detune) before each move, plus after it when
    settled. A segment between two points is kept only if it went the same
    step direction as the one before, so backlash at a reversal isn't
    counted. That also drops each run's first segment.
    """
    if moves.empty:
        return []
    moves = moves[moves.offset_stable].sort_values("t")
    runs = []
    for _, group in moves.groupby((moves.t.diff() > RUN_GAP).cumsum()):
        run = Run(start=group.t.iloc[0])
        for m in group.itertuples():
            pos_after = _last_at(position, m.t)
            run.points.append((pos_after - m.usteps, m.before_hz))
            if m.after_spread_hz < SETTLE_HZ:
                run.points.append((pos_after, m.after_hz))
        prev = 0
        for (p0, d0), (p1, d1) in zip(run.points, run.points[1:]):
            sign = np.sign(p1 - p0)
            if (
                sign != 0
                and sign == prev
                and abs(p1 - p0) <= MAX_SEGMENT_USTEPS
            ):
                run.segments.append((min(d0, d1), max(d0, d1), abs(p1 - p0)))
            if sign != 0:
                prev = sign
        runs.append(run)
    return runs


def _curve_at(curve: pd.DataFrame, detune_hz) -> np.ndarray:
    return np.interp(detune_hz, curve.real_detune_hz, curve.usteps_from_cold)


def step_ratio(run: Run, curve: pd.DataFrame) -> Optional[float]:
    """Actual microsteps / the curve's microsteps, over the run's segments.

    The curve's count for a segment is its rise between the segment's low
    and high detune. None if the run has no segments or the curve doesn't
    rise over them.
    """
    if not run.segments:
        return None
    lo, hi, actual = np.array(run.segments).T
    expected = np.sum(_curve_at(curve, hi) - _curve_at(curve, lo))
    return float(actual.sum() / expected) if expected > 0 else None


def overlay(run: Run, curve: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
    """(detune Hz, microsteps from cold) to draw a run over its curve.

    REG_TOTSGN has no fixed zero, so the run's first point is put on the
    curve and the rest follow by how far the stepper moved from there.
    """
    if not run.points:
        return np.array([]), np.array([])
    pos, detune = np.array(run.points).T
    return detune, _curve_at(curve, detune[0]) + (pos - pos[0])


def _fetch(pv: str, start: datetime, end: datetime) -> pd.Series:
    """Valid samples, a quarter at a time; a quarter that errors is skipped.

    The archiver has returned HTTP 500 on some quarters of these PVs.
    """
    quarters = pd.date_range(start, end, freq="QS")
    edges = [start, *(q for q in quarters if start < q < end), end]
    parts = []
    for a, b in zip(edges, edges[1:]):
        try:
            parts.append(get_series([pv], a, b)[pv])
        except PVNotArchivedError:
            raise
        except ArchiverError as e:
            logger.warning(f"Skipped {pv} {a:%Y-%m-%d}..{b:%Y-%m-%d}: {e}")
    s = pd.concat(parts).astype(float) if parts else pd.Series(dtype=float)
    return s[~s.index.duplicated()].sort_index()


def fetch_runs(prefix: str, start: datetime, end: datetime) -> List[Run]:
    """Tuning runs on one cavity between start and end, from the archiver."""
    # CHECK: the packaged curves used each cavity's own FREQ_OFFSET PV; this
    # reads the rack's. They agree on 2023-2025 data except 2023-10-25
    # 09:52-10:07, when H200:RACKB read -300 kHz and H250/H270's own PVs had
    # no samples (still 0). Which offset did those cavities see?
    # From a quarter early, so the offset at the first move is known.
    offset = _fetch(rack_offset_pv(prefix), start - timedelta(days=92), end)
    position = unwrap_position(_fetch(prefix + "STEP:REG_TOTSGN", start, end))
    chirp = _fetch(prefix + "CHIRP:DF", start, end)
    return find_runs(find_moves(position, chirp, offset), position)
