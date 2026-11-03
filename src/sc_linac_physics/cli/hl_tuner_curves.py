"""sc-hl-tuner-curves: refit the H1/H2 stepper response curves from the archiver.

Writes one curve per HL cavity: microsteps from cold landing against real
detune, in the format of utils/sc_linac/data/hl_tuner_response.csv.

Read-only. Every PV is read from the archiver, none over CA:

- ``<cavity>STEP:REG_TOTSGN``: signed stepper position, microsteps
- ``<cavity>CHIRP:DF``: detune in chirp mode, Hz
- ``ACCL:L1B:H{1,2}00:RACK{A,B}:FREQ_OFFSET``: the rack's offset, Hz
- ``<cavity>DF_COLD``: cold landing detune, Hz (its value now)

Real detune = ``CHIRP:DF + FREQ_OFFSET``. The method is the one in the
write-up "2026-10-27 HL stepper SCALE, tuning limits", section "How it was
measured", steps 1-5. That and the original scripts (``absdetune.py``,
``fit_curves.py``) are in Lisa Zacarias's Drive folder "Stepper SCALE on HL".
This module is a port of those two scripts; the constants are theirs.
"""

import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd

from sc_linac_physics.utils.archiver import (
    ArchiverError,
    PVNotArchivedError,
    get_series,
    get_values_at_time,
)
from sc_linac_physics.utils.sc_linac.linac_utils import L1BHL

PACKAGED_CSV = (
    Path(__file__).resolve().parent.parent
    / "utils/sc_linac/data/hl_tuner_response.csv"
)
CSV_COLUMNS = [
    "cavity_pv_prefix",
    "real_detune_hz",
    "usteps_from_cold",
    "covered",
]

# Moves (write-up steps 1-2)
MOVE_GAP_S = 30  # REG_TOTSGN changes this close together are one move
BEFORE_S = 30  # detune before = median CHIRP:DF over the 30 s before
AFTER_S = (5, 60)  # detune after = median over 5-60 s after the move ends
MIN_SAMPLES = 3  # CHIRP:DF samples needed in each window
SETTLE_HZ = 200  # "after" samples must spread less than this to count

# Position and runs (steps 4-5)
RESET_JUMP = 2e6  # one-sample jumps this big are REG_TOTSGN resets
RUN_GAP = timedelta(minutes=10)  # moves closer than this are one run
MAX_SEGMENT_USTEPS = 3e7  # longer segments are dropped as bad points

# Bins (step 5)
BIN_HZ = 10e3
MIN_COVER_HZ = 30e3  # a bin counts as covered once segments cross this much
FLAT_HZ = 1e3  # a segment moving the detune less sits in one bin
TOP_HZ = 50e3  # curves run from DF_COLD up to +50 kHz


def hl_cavities() -> List[Tuple[str, str]]:
    """(cavity PV prefix, rack FREQ_OFFSET PV) for the 16 HL cavities."""
    from sc_linac_physics.utils.sc_linac.linac import Machine

    machine = Machine()
    return [
        (cavity.pv_prefix, cavity.rack.pv_addr("FREQ_OFFSET"))
        for cm in L1BHL
        for cavity in machine.cryomodules[cm].cavities.values()
    ]


def _last_at(series: pd.Series, t) -> float:
    """The series' value at t: its last sample at or before t."""
    k = series.index.searchsorted(t, side="right") - 1
    return float(series.iloc[k]) if k >= 0 else np.nan


def find_moves(
    steps: pd.Series, chirp_df: pd.Series, offset: pd.Series
) -> pd.DataFrame:
    """Every stepper move, with real detune before and after it.

    Port of absdetune.py. A move is a run of REG_TOTSGN changes with no gap
    over MOVE_GAP_S. Moves without MIN_SAMPLES of CHIRP:DF in both windows
    are dropped. ``offset_stable`` is False if FREQ_OFFSET changed inside a
    window, which would mix two references.
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
        before = chirp_df[t[i] - timedelta(seconds=BEFORE_S) : t[i]]
        after = chirp_df[
            t[j]
            + timedelta(seconds=AFTER_S[0]) : t[j]
            + timedelta(seconds=AFTER_S[1])
        ]
        if len(before) >= MIN_SAMPLES and len(after) >= MIN_SAMPLES:
            off_before = _last_at(offset, t[i])
            off_after = _last_at(offset, t[j] + timedelta(seconds=AFTER_S[0]))
            stable = (
                _last_at(offset, t[i] - timedelta(seconds=BEFORE_S))
                == off_before
                and _last_at(offset, t[j] + timedelta(seconds=AFTER_S[1]))
                == off_after
            )
            rows.append(
                dict(
                    t=t[j],
                    usteps=steps.iloc[j] - steps.iloc[i - 1],
                    before_hz=before.median() + off_before,
                    after_hz=after.median() + off_after,
                    after_spread_hz=after.max() - after.min(),
                    offset_stable=stable,
                )
            )
        i = j + 1
    return pd.DataFrame(rows)


def unwrap_position(steps: pd.Series) -> pd.Series:
    """REG_TOTSGN with its resets undone (write-up step 4).

    CHECK: a reset shows as a one-sample jump over RESET_JUMP. Real move
    samples stayed under 1.3M in 2023-2025; is that a hardware limit?
    """
    jump = steps.diff().fillna(0)
    return steps - jump.where(jump.abs() > RESET_JUMP, 0).cumsum()


def run_segments(
    moves: pd.DataFrame, position: pd.Series
) -> List[Tuple[float, float, float]]:
    """(low Hz, high Hz, microsteps) for each usable stretch of a tuning run.

    Points are (position, real detune) before each move, plus after it when
    settled. Consecutive points form a segment. A segment is kept only if
    it went the same step direction as the one before, so backlash take-up
    at a reversal isn't counted. That also drops each run's first segment.
    """
    moves = moves[moves.offset_stable].sort_values("t")
    run = (moves.t.diff() > RUN_GAP).cumsum()
    segments = []
    for _, r in moves.groupby(run):
        points = []
        for m in r.itertuples():
            pos_after = _last_at(position, m.t)
            points.append((pos_after - m.usteps, m.before_hz))
            if m.after_spread_hz < SETTLE_HZ:
                points.append((pos_after, m.after_hz))
        prev = 0
        for (p0, d0), (p1, d1) in zip(points, points[1:]):
            sign = np.sign(p1 - p0)
            if (
                sign != 0
                and sign == prev
                and abs(p1 - p0) <= MAX_SEGMENT_USTEPS
            ):
                segments.append((min(d0, d1), max(d0, d1), abs(p1 - p0)))
            if sign != 0:
                prev = sign
    return segments


def fit_curve(
    segments: Iterable[Tuple[float, float, float]], df_cold: float
) -> Optional[pd.DataFrame]:
    """Microsteps from cold at each bin edge, DF_COLD to +TOP_HZ.

    Port of fit_curves.py. Each segment spreads its microsteps evenly over
    the BIN_HZ bins its detune crossed. A segment that moved the detune less
    than FLAT_HZ puts them all in the bin it sat in, so the flat zone is
    counted. Per bin, microsteps per Hz = total microsteps / total Hz
    crossed. Bins crossed by less than MIN_COVER_HZ are uncovered and take
    the nearest covered bin's value. Adding up from DF_COLD gives the curve,
    0 at DF_COLD itself. None if no bin is covered.
    """
    edges = np.arange(
        np.floor(df_cold / BIN_HZ) * BIN_HZ, TOP_HZ + BIN_HZ, BIN_HZ
    )
    usteps, hz = np.zeros(len(edges) - 1), np.zeros(len(edges) - 1)
    for lo, hi, n in segments:
        if hi - lo < FLAT_HZ:
            k = np.clip(
                np.searchsorted(edges, (lo + hi) / 2) - 1, 0, len(hz) - 1
            )
            usteps[k] += n
            hz[k] += hi - lo
            continue
        over = np.minimum(edges[1:], hi) - np.maximum(edges[:-1], lo)
        over = np.clip(over, 0, None)
        usteps += n * over / (hi - lo)
        hz += over
    covered = hz >= MIN_COVER_HZ
    idx = np.flatnonzero(covered)
    if not len(idx):
        return None
    per_hz = np.where(covered, usteps / np.maximum(hz, 1), np.nan)
    nearest = idx[np.abs(idx[None, :] - np.arange(len(hz))[:, None]).argmin(1)]
    per_hz = per_hz[nearest]
    cum = np.concatenate([[0], np.cumsum(per_hz * BIN_HZ)])
    cum -= np.interp(df_cold, edges, cum)
    return pd.DataFrame(
        {
            "real_detune_hz": edges,
            "usteps_from_cold": cum,
            # The top edge has no bin above it; it takes the last bin's flag.
            "covered": np.append(covered, covered[-1]),
        }
    )


def write_csv(
    curves: Dict[str, pd.DataFrame], path: Path, header: Iterable[str]
) -> None:
    """Write curves keyed by cavity PV prefix, after '#' header lines."""
    frame = pd.concat(
        [c.assign(cavity_pv_prefix=p) for p, c in curves.items()]
    )[CSV_COLUMNS]
    frame["real_detune_hz"] = frame.real_detune_hz.round().astype(int)
    frame["usteps_from_cold"] = frame.usteps_from_cold.round().astype(int)
    with open(path, "w") as f:
        f.writelines(f"# {line}\n" for line in header)
        frame.to_csv(f, index=False)


def _fetch(pv: str, start: datetime, end: datetime) -> pd.Series:
    """Valid samples, a quarter at a time; a quarter that errors is skipped.

    The archiver has returned HTTP 500 on some quarters of these PVs. Those
    are reported and the fit goes on without them.
    """
    edges = [start, *pd.date_range(start, end, freq="QS")[1:], end]
    parts = []
    for a, b in zip(edges, edges[1:]):
        try:
            parts.append(get_series([pv], a, b)[pv])
        except PVNotArchivedError:
            raise
        except ArchiverError as e:
            print(f"  skip {pv} {a:%Y-%m-%d}..{b:%Y-%m-%d}: {e}", flush=True)
    s = pd.concat(parts).astype(float) if parts else pd.Series(dtype=float)
    return s[~s.index.duplicated()].sort_index()


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(
        description="Refit the H1/H2 stepper response curves from archived"
        " tuning runs. Reads the archiver only; writes no PV."
    )
    parser.add_argument(
        "start",
        type=datetime.fromisoformat,
        help="archive start, e.g. 2023-01-01 (Pacific time)",
    )
    parser.add_argument(
        "end", type=datetime.fromisoformat, help="archive end, e.g. 2026-01-01"
    )
    parser.add_argument(
        "-o", "--output", type=Path, default=Path("hl_tuner_response.csv")
    )
    args = parser.parse_args(argv)

    cavities = hl_cavities()
    df_cold = get_values_at_time(
        [p + "DF_COLD" for p, _ in cavities], datetime.now()
    )
    offsets: Dict[str, pd.Series] = {}
    curves = {}
    for prefix, offset_pv in cavities:
        # CHECK: the packaged curves used each cavity's own FREQ_OFFSET PV.
        # On 2023-2025 data it matches the rack PV, except 2023-10-25
        # 09:52-10:07: RACKB read -300 kHz while H250/H270's own PVs had no
        # samples (still 0). Refit with RACKB, H2 cav 5 and 7 move by up to
        # 1.2M and 2.3M microsteps. Which offset did those cavities see?
        if offset_pv not in offsets:
            # From a quarter early, so the offset at the first move is known.
            offsets[offset_pv] = _fetch(
                offset_pv, args.start - timedelta(days=92), args.end
            )
        steps = _fetch(prefix + "STEP:REG_TOTSGN", args.start, args.end)
        chirp = _fetch(prefix + "CHIRP:DF", args.start, args.end)
        moves = find_moves(steps, chirp, offsets[offset_pv])
        segments = (
            run_segments(moves, unwrap_position(steps)) if len(moves) else []
        )
        cold = df_cold.get(prefix + "DF_COLD")
        curve = fit_curve(segments, float(cold.value)) if cold else None
        if curve is None:
            print(f"{prefix}: no curve ({len(segments)} segments)", flush=True)
            continue
        curves[prefix] = curve
        total = np.interp(0, curve.real_detune_hz, curve.usteps_from_cold)
        print(
            f"{prefix}: {len(segments)} segments, DF_COLD {cold.value:.0f} Hz,"
            f" {total / 1e6:.1f}M microsteps cold to 0, bins covered"
            f" {curve.covered.mean():.0%}",
            flush=True,
        )

    if not curves:
        raise SystemExit("No curves fitted; nothing written.")
    write_csv(
        curves,
        args.output,
        [
            "H1/H2 stepper response: microsteps from cold landing vs real"
            " detune (CHIRP:DF + RACK FREQ_OFFSET).",
            f"Archive {args.start:%Y-%m-%d} to {args.end:%Y-%m-%d};"
            f" DF_COLD as of {datetime.now():%Y-%m-%d}.",
            "Made by sc-hl-tuner-curves. covered=False: no data in that"
            " bin, filled from the nearest covered bin.",
        ],
    )
    print(f"Wrote {len(curves)} curves to {args.output}")
