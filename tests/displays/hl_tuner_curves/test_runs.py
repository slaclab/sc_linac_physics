"""Tests for the HL tuning-run code on synthetic data; no archiver."""

from datetime import datetime
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from sc_linac_physics.displays.hl_tuner_curves import runs as R
from sc_linac_physics.utils.archiver import ArchiverError

T0 = pd.Timestamp("2026-03-01 12:00")
HZ_PER_USTEP = 0.05
DF_COLD = -600e3
OFFSET = -200e3
MOVE_USTEPS = 500_000


def linear_run(n_moves=6, start=T0, reverse_after=None):
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


def linear_curve(hz_per_ustep=HZ_PER_USTEP):
    detune = np.arange(DF_COLD, 50e3 + 1, 10e3)
    return pd.DataFrame(
        {
            "real_detune_hz": detune,
            "usteps_from_cold": (detune - DF_COLD) / hz_per_ustep,
            "covered": True,
        }
    )


def one_run(**kwargs):
    steps, chirp, offset = linear_run(**kwargs)
    return R.find_runs(R.find_moves(steps, chirp, offset), steps)


def test_packaged_csv_loads():
    curves = R.load_curves()
    assert len(curves) == 16
    for curve in curves.values():
        assert curve.usteps_from_cold.is_monotonic_increasing
    assert R.archive_end() == datetime(2026, 1, 1)


def test_archive_end_needs_header(tmp_path):
    path = tmp_path / "c.csv"
    path.write_text("# no dates here\ncavity_pv_prefix,real_detune_hz\n")
    with pytest.raises(ValueError):
        R.archive_end(path)


def test_rack_offset_pv_matches_machine():
    from sc_linac_physics.utils.sc_linac.linac import Machine

    machine = Machine()
    for prefix in R.load_curves():
        cm = machine.cryomodules[prefix[-5:-3]]
        cavity = cm.cavities[int(prefix[-3])]
        assert cavity.pv_prefix == prefix
        assert R.rack_offset_pv(prefix) == cavity.rack.pv_addr("FREQ_OFFSET")


def test_find_moves_gives_real_detune():
    steps, chirp, offset = linear_run(n_moves=3)
    moves = R.find_moves(steps, chirp, offset)
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
    moves = R.find_moves(steps, chirp, changed)
    assert list(moves.offset_stable) == [False, True]


def test_unwrap_position_undoes_reset():
    idx = pd.date_range(T0, periods=4, freq="1min")
    steps = pd.Series([5e6, 6e6, 0, 1e6], index=idx)
    assert list(R.unwrap_position(steps)) == [5e6, 6e6, 6e6, 7e6]


def test_find_runs_skips_first_and_reversal():
    (run,) = one_run(n_moves=4, reverse_after=2)
    # Moves 2 and 4 kept; 1 is the run's first, 3 reverses.
    assert [s[2] for s in run.segments] == [MOVE_USTEPS, MOVE_USTEPS]


def test_find_runs_splits_on_gap():
    a = linear_run(n_moves=2)
    b = linear_run(n_moves=2, start=T0 + pd.Timedelta(hours=1))
    steps = pd.concat([a[0], b[0] + a[0].iloc[-1]])
    chirp = pd.concat([a[1], b[1] + a[0].iloc[-1] * HZ_PER_USTEP])
    runs = R.find_runs(R.find_moves(steps, chirp, a[2]), steps)
    assert [r.start for r in runs] == [a[0].index[-2], b[0].index[1]]
    assert [len(r.segments) for r in runs] == [1, 1]


def test_find_runs_empty():
    assert R.find_runs(pd.DataFrame(), pd.Series(dtype=float)) == []


def test_step_ratio_is_one_on_matching_curve():
    (run,) = one_run()
    assert R.step_ratio(run, linear_curve()) == pytest.approx(1.0)


def test_step_ratio_flags_stiffer_tuner():
    # The run took twice the microsteps per Hz the curve says.
    (run,) = one_run()
    curve = linear_curve(hz_per_ustep=2 * HZ_PER_USTEP)
    ratio = R.step_ratio(run, curve)
    assert ratio == pytest.approx(2.0)
    assert not R.RATIO_BAND[0] <= ratio <= R.RATIO_BAND[1]


def test_step_ratio_none_without_segments():
    assert R.step_ratio(R.Run(start=T0), linear_curve()) is None


def test_step_ratio_leaves_out_segments_past_curve():
    run = R.Run(start=T0, segments=[(40e3, 60e3, 1e9)])
    assert R.step_ratio(run, linear_curve()) is None
    run.segments.append((-500e3, -400e3, 100e3 / HZ_PER_USTEP))
    assert R.step_ratio(run, linear_curve()) == pytest.approx(1.0)


def test_overlay_follows_matching_curve():
    (run,) = one_run()
    x, y = R.overlay(run, linear_curve())
    np.testing.assert_allclose(y, (x - DF_COLD) / HZ_PER_USTEP)


def test_fetch_skips_failing_quarter():
    idx = pd.DatetimeIndex([T0])

    def series(pvs, a, b):
        if a.month == 4:
            raise ArchiverError("HTTP 500")
        return {"PV": pd.Series([float(a.month)], index=idx + (a - T0))}

    with patch.object(R, "get_series", side_effect=series):
        s = R._fetch("PV", datetime(2026, 1, 1), datetime(2026, 9, 1))
    assert list(s) == [1.0, 7.0]


def test_fetch_raises_when_every_quarter_fails():
    with patch.object(R, "get_series", side_effect=ArchiverError("down")):
        with pytest.raises(ArchiverError, match="Every archiver request"):
            R._fetch("PV", datetime(2026, 1, 1), datetime(2026, 9, 1))


def test_fetch_strict_raises_on_one_failing_quarter():
    def series(pvs, a, b):
        if a.month == 4:
            raise ArchiverError("HTTP 500")
        return {"PV": pd.Series([1.0], index=pd.DatetimeIndex([a]))}

    with patch.object(R, "get_series", side_effect=series):
        with pytest.raises(ArchiverError, match="HTTP 500"):
            R._fetch(
                "PV",
                datetime(2026, 1, 1),
                datetime(2026, 9, 1),
                skip_errors=False,
            )


def test_fetch_runs_reads_rack_offset():
    steps, chirp, offset = linear_run()
    data = {
        "ACCL:L1B:H250:STEP:REG_TOTSGN": steps,
        "ACCL:L1B:H250:CHIRP:DF": chirp,
        "ACCL:L1B:H200:RACKB:FREQ_OFFSET": offset,
    }

    def fetch(pv, a, b, skip_errors=True):
        # Only CHIRP:DF may skip a failing quarter.
        assert skip_errors == pv.endswith("CHIRP:DF")
        return data[pv]

    with patch.object(R, "_fetch", side_effect=fetch):
        runs = R.fetch_runs("ACCL:L1B:H250:", T0, T0)
    assert len(runs) == 1 and runs[0].segments
