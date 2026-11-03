"""Tests for sc-hl-tuner-curves on synthetic data; no archiver."""

from datetime import datetime
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from sc_linac_physics.cli import hl_tuner_curves as H
from sc_linac_physics.utils.archiver import ArchiverError, ArchiverSample
from sc_linac_physics.utils.sc_linac.linac_utils import (
    L1BHL,
    build_cavity_pv_prefix,
)

T0 = pd.Timestamp("2024-03-01 12:00")
HZ_PER_USTEP = 0.05
DF_COLD = -600e3
OFFSET = -200e3
MOVE_USTEPS = 500_000


def linear_run(n_moves=26, start=T0, reverse_after=None):
    """REG_TOTSGN, CHIRP:DF and FREQ_OFFSET for one run on a linear tuner.

    One move every 2 minutes. CHIRP:DF is sampled every 5 s and reads real
    detune minus the offset.
    """
    move_t = [start + pd.Timedelta(minutes=2 * k) for k in range(n_moves + 1)]
    sign = [
        1 if reverse_after is None or k < reverse_after else -1
        for k in range(n_moves)
    ]
    pos = np.concatenate([[0], np.cumsum(np.array(sign) * MOVE_USTEPS)])
    steps = pd.Series(pos.astype(float), index=pd.DatetimeIndex(move_t))
    t = pd.date_range(
        start - pd.Timedelta(minutes=1),
        move_t[-1] + pd.Timedelta(minutes=2),
        freq="5s",
    )
    k = np.searchsorted(steps.index, t, side="left") - 1
    real = DF_COLD + pos[np.clip(k, 0, None)] * HZ_PER_USTEP
    chirp = pd.Series(real - OFFSET, index=t)
    offset = pd.Series([OFFSET], index=[start - pd.Timedelta(days=1)])
    return steps, chirp, offset


def three_runs():
    """Three identical runs from DF_COLD, 2 hours apart.

    Each run starts back at 0 microsteps; that jump reads as a reset. One
    crossing per bin is 10 kHz, under MIN_COVER_HZ, so three are needed.
    """
    runs = [linear_run(start=T0 + pd.Timedelta(hours=2 * r)) for r in range(3)]
    return tuple(pd.concat(parts) for parts in zip(*runs))


def test_find_moves_gives_real_detune():
    steps, chirp, offset = linear_run(n_moves=3)
    moves = H.find_moves(steps, chirp, offset)
    assert list(moves.usteps) == [MOVE_USTEPS] * 3
    assert moves.before_hz.iloc[0] == pytest.approx(DF_COLD)
    assert moves.after_hz.iloc[0] == pytest.approx(
        DF_COLD + MOVE_USTEPS * HZ_PER_USTEP
    )
    assert moves.offset_stable.all()


def test_find_moves_marks_offset_change_in_window():
    steps, chirp, offset = linear_run(n_moves=2)
    changed = pd.concat(
        [offset, pd.Series([0.0], index=[steps.index[1] - pd.Timedelta("10s")])]
    )
    moves = H.find_moves(steps, chirp, changed)
    assert list(moves.offset_stable) == [False, True]


def test_unwrap_position_undoes_reset():
    idx = pd.date_range(T0, periods=4, freq="1min")
    steps = pd.Series([5e6, 6e6, 0, 1e6], index=idx)
    assert list(H.unwrap_position(steps)) == [5e6, 6e6, 6e6, 7e6]


def test_run_segments_skips_first_and_reversal():
    steps, chirp, offset = linear_run(n_moves=4, reverse_after=2)
    moves = H.find_moves(steps, chirp, offset)
    segments = H.run_segments(moves, steps)
    # Moves 2 and 4 kept; 1 is the run's first, 3 reverses.
    assert [s[2] for s in segments] == [MOVE_USTEPS, MOVE_USTEPS]


def test_run_segments_new_run_after_gap():
    a = linear_run(n_moves=2)
    b = linear_run(n_moves=2, start=T0 + pd.Timedelta(hours=1))
    steps = pd.concat([a[0], b[0] + a[0].iloc[-1]])
    chirp = pd.concat([a[1], b[1] + a[0].iloc[-1] * HZ_PER_USTEP])
    moves = H.find_moves(steps, chirp, a[2])
    # Each run loses its first segment, so one kept per run.
    assert len(H.run_segments(moves, steps)) == 2


def test_linear_tuner_gives_straight_curve():
    steps, chirp, offset = three_runs()
    position = H.unwrap_position(steps)
    segments = H.run_segments(H.find_moves(steps, chirp, offset), position)
    curve = H.fit_curve(segments, DF_COLD)
    assert curve.real_detune_hz.iloc[0] == DF_COLD
    assert curve.real_detune_hz.iloc[-1] == H.TOP_HZ
    expected = (curve.real_detune_hz - DF_COLD) / HZ_PER_USTEP
    np.testing.assert_allclose(curve.usteps_from_cold, expected, rtol=1e-9)
    # The first segment (from DF_COLD) is skipped, so the bottom bin has
    # no data and is filled.
    assert not curve.covered.iloc[0]
    assert curve.covered.iloc[5:].all()


def test_flat_segment_lands_in_one_bin():
    segments = [(-600e3, 0.0, 12e6)] * 3 + [(-250e3, -249.5e3, 3e6)]
    curve = H.fit_curve(segments, -600e3)
    cum = curve.set_index("real_detune_hz").usteps_from_cold
    straight = 12e6 / 600e3 * H.BIN_HZ
    assert cum[-240e3] - cum[-250e3] == pytest.approx(
        (3 * straight + 3e6) / (3 * H.BIN_HZ + 500) * H.BIN_HZ
    )
    assert cum[-300e3] - cum[-310e3] == pytest.approx(straight)
    # Above 0 nothing crossed; filled from the bin below 0.
    assert not curve.covered[curve.real_detune_hz > 0].any()
    assert cum[50e3] - cum[40e3] == pytest.approx(straight)


def test_fit_curve_zero_at_df_cold_between_edges():
    curve = H.fit_curve([(-700e3, 0.0, 14e6)] * 3, -655e3)
    assert np.interp(
        -655e3, curve.real_detune_hz, curve.usteps_from_cold
    ) == pytest.approx(0)


def test_fit_curve_none_without_coverage():
    # Two crossings: 20 kHz per bin, under MIN_COVER_HZ.
    assert H.fit_curve([(-600e3, 0.0, 1e7)] * 2, -600e3) is None


def test_write_csv_format(tmp_path):
    curve = H.fit_curve([(-600e3, 0.0, 12e6)] * 3, -600e3)
    path = tmp_path / "out.csv"
    H.write_csv({"ACCL:L1B:H110:": curve}, path, ["line one", "line two"])
    lines = path.read_text().splitlines()
    assert lines[:3] == ["# line one", "# line two", ",".join(H.CSV_COLUMNS)]
    assert lines[3] == "ACCL:L1B:H110:,-600000,0,True"


def test_packaged_csv_has_16_monotonic_curves():
    d = pd.read_csv(H.PACKAGED_CSV, comment="#")
    assert list(d.columns) == H.CSV_COLUMNS
    expected = {
        build_cavity_pv_prefix("L1B", cm, n)
        for cm in L1BHL
        for n in range(1, 9)
    }
    assert set(d.cavity_pv_prefix) == expected
    for prefix, g in d.groupby("cavity_pv_prefix"):
        assert (np.diff(g.real_detune_hz) == H.BIN_HZ).all(), prefix
        assert (np.diff(g.usteps_from_cold) > 0).all(), prefix
        assert g.real_detune_hz.iloc[-1] == H.TOP_HZ, prefix
        assert g.covered.dtype == bool, prefix


def test_main_fits_from_archiver(tmp_path):
    prefix, offset_pv = "ACCL:L1B:H110:", "ACCL:L1B:H100:RACKA:FREQ_OFFSET"
    steps, chirp, offset = three_runs()
    data = {
        prefix + "STEP:REG_TOTSGN": steps,
        prefix + "CHIRP:DF": chirp,
        offset_pv: offset,
    }

    def get_series(pvs, a, b):
        (pv,) = pvs
        if pv == prefix + "CHIRP:DF" and a >= datetime(2024, 4, 1):
            raise ArchiverError("HTTP 500")  # a quarter with no moves in it
        s = data[pv]
        return {pv: s[(s.index >= a) & (s.index < b)]}

    cold = {prefix + "DF_COLD": ArchiverSample(datetime.now(), DF_COLD, 0, 0)}
    out = tmp_path / "curves.csv"
    with (
        patch.object(H, "hl_cavities", return_value=[(prefix, offset_pv)]),
        patch.object(H, "get_series", side_effect=get_series),
        patch.object(H, "get_values_at_time", return_value=cold),
    ):
        H.main(["2024-01-01", "2024-06-01", "-o", str(out)])

    d = pd.read_csv(out, comment="#")
    assert set(d.cavity_pv_prefix) == {prefix}
    np.testing.assert_allclose(
        d.usteps_from_cold,
        (d.real_detune_hz - DF_COLD) / HZ_PER_USTEP,
        atol=1,
    )


def test_main_skips_cavity_without_df_cold(tmp_path, capsys):
    prefix, offset_pv = "ACCL:L1B:H110:", "ACCL:L1B:H100:RACKA:FREQ_OFFSET"
    empty = pd.Series(dtype=float, index=pd.DatetimeIndex([]))
    out = tmp_path / "curves.csv"
    with (
        patch.object(H, "hl_cavities", return_value=[(prefix, offset_pv)]),
        patch.object(
            H, "get_series", side_effect=lambda p, a, b: {p[0]: empty}
        ),
        patch.object(H, "get_values_at_time", return_value={}),
    ):
        with pytest.raises(SystemExit, match="No curves"):
            H.main(["2024-01-01", "2024-03-01", "-o", str(out)])
    assert "no curve" in capsys.readouterr().out
    assert not out.exists()


def test_hl_cavities_racks():
    cavities = dict(H.hl_cavities())
    assert len(cavities) == 16
    assert cavities["ACCL:L1B:H140:"] == "ACCL:L1B:H100:RACKA:FREQ_OFFSET"
    assert cavities["ACCL:L1B:H250:"] == "ACCL:L1B:H200:RACKB:FREQ_OFFSET"


def test_offset_change_and_back_inside_window_is_unstable():
    steps, chirp, offset = linear_run(n_moves=2)
    t = steps.index[1]
    blip = pd.Series(
        [0.0, OFFSET], index=[t - pd.Timedelta("20s"), t - pd.Timedelta("10s")]
    )
    moves = H.find_moves(steps, chirp, pd.concat([offset, blip]))
    assert list(moves.offset_stable) == [False, True]


def test_flat_segment_outside_range_is_dropped():
    base = [(-600e3, 0.0, 12e6)] * 3
    below = H.fit_curve(base + [(-900e3, -899.5e3, 3e6)], -600e3)
    pd.testing.assert_frame_equal(below, H.fit_curve(base, -600e3))


def test_reset_mid_run_adds_no_steps():
    steps, chirp, offset = three_runs()
    clean = H.run_segments(
        H.find_moves(H.unwrap_position(steps), chirp, offset),
        H.unwrap_position(steps),
    )
    # REG_TOTSGN resets to 0 between two moves of the first run.
    t_reset = steps.index[5] + pd.Timedelta("50s")
    reset = steps.copy()
    reset[reset.index > t_reset] -= steps.iloc[5]
    reset[t_reset] = 0.0
    reset = reset.sort_index()
    position = H.unwrap_position(reset)
    moves = H.find_moves(position, chirp, offset)
    assert H.run_segments(moves, position) == clean


def test_fetch_splits_on_quarters_inside_range():
    windows = []

    def get_series(pvs, a, b):
        windows.append((a, b))
        return {pvs[0]: pd.Series(dtype=float, index=pd.DatetimeIndex([]))}

    start, end = datetime(2024, 1, 15), datetime(2024, 7, 1)
    with patch.object(H, "get_series", side_effect=get_series):
        H._fetch("X", start, end)
    assert windows == [
        (start, pd.Timestamp(2024, 4, 1)),
        (pd.Timestamp(2024, 4, 1), end),
    ]


def test_main_skips_invalid_df_cold(tmp_path, capsys):
    prefix, offset_pv = "ACCL:L1B:H110:", "ACCL:L1B:H100:RACKA:FREQ_OFFSET"
    steps, chirp, offset = three_runs()
    data = {
        prefix + "STEP:REG_TOTSGN": steps,
        prefix + "CHIRP:DF": chirp,
        offset_pv: offset,
    }
    invalid = ArchiverSample(datetime.now(), DF_COLD, 3, 0)
    with (
        patch.object(H, "hl_cavities", return_value=[(prefix, offset_pv)]),
        patch.object(
            H, "get_series", side_effect=lambda p, a, b: {p[0]: data[p[0]]}
        ),
        patch.object(
            H, "get_values_at_time", return_value={prefix + "DF_COLD": invalid}
        ),
    ):
        with pytest.raises(SystemExit):
            H.main(["2024-01-01", "2024-03-01", "-o", str(tmp_path / "c.csv")])
    assert "no curve" in capsys.readouterr().out
