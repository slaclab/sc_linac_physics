from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from sc_linac_physics.utils import archiver
from sc_linac_physics.utils.archiver_mock import (
    MAX_SAMPLES,
    ProfileStore,
    guess_kind,
    mock_values_over_time_range,
)

START = datetime(2025, 6, 2, 12, 0, tzinfo=archiver.LOCAL_TZ)
END = START + timedelta(minutes=10)
AMP = "ACCL:L1B:0210:AACTMEAN"


@pytest.fixture
def store(tmp_path):
    """Shipped rules only, whatever is in the developer's home directory."""
    return ProfileStore(user_file=tmp_path / "none.yaml")


def _get(pv, store, start=START, end=END):
    return mock_values_over_time_range([pv], start, end, store=store)[pv]


def test_frame_matches_the_real_client(store):
    frame = _get(AMP, store)
    real = archiver._to_frame([{"secs": 1748890800, "val": 1.0}])
    assert list(frame.columns) == archiver.COLUMNS
    assert frame.dtypes["timestamp"] == real.dtypes["timestamp"]
    assert frame["valid"].all()
    assert set(frame["severity"]) <= {0, 1, 2}


def test_same_request_same_data(store):
    pd.testing.assert_frame_equal(_get(AMP, store), _get(AMP, store))


def test_other_window_other_data(store):
    a = _get(AMP, store)["value"].to_numpy()
    b = _get(AMP, store, END, END + (END - START))["value"].to_numpy()
    assert not np.array_equal(a, b)


def test_timestamps_span_the_window_at_1_hz(store):
    frame = _get(AMP, store)
    assert len(frame) == 601
    assert frame["timestamp"].iloc[0] == START
    assert frame["timestamp"].iloc[-1] == END


def test_long_window_is_capped(store):
    frame = _get(AMP, store, START, START + timedelta(days=14))
    assert len(frame) == MAX_SAMPLES


def test_rule_sets_the_level(store):
    values = _get(AMP, store)["value"]
    # defaults.yaml: *AACTMEAN* base 16.5, noise 0.1, spikes up to 5x noise
    assert values.median() == pytest.approx(16.5, abs=0.05)
    assert values.between(16.5 - 0.6, 16.5 + 0.6).all()


def test_sine_trend_has_one_period(store):
    pv = "CLL:CM02:2601:DS:LVL"  # base 90, sine amplitude 4
    values = _get(pv, store)["value"].to_numpy()
    quarter = len(values) // 4
    assert values[quarter - 20 : quarter + 20].mean() > 92
    assert values[3 * quarter - 20 : 3 * quarter + 20].mean() < 88


def test_kind_from_name(store):
    assert guess_kind("ACCL:L1B:0210:RFSTATE") == "ENUM"
    assert guess_kind("ACCL:L1B:0210:QUENCH_CNT") == "INT"
    enum_values = _get("ACCL:L1B:0210:RFSTATE", store)["value"]
    assert set(enum_values) <= {0, 1, 2}
    assert (enum_values == 0).mean() > 0.8


def test_override_changes_and_clears(store):
    before = _get(AMP, store)
    store.set_override(AMP, base=5.0)
    assert _get(AMP, store)["value"].median() == pytest.approx(5.0, abs=0.05)
    store.clear_override(AMP)
    pd.testing.assert_frame_equal(_get(AMP, store), before)


def test_user_file_rules_and_saved_overrides(tmp_path):
    user = tmp_path / "mine.yaml"
    store = ProfileStore(user_file=tmp_path / "none.yaml")
    store.set_override("TEST:PV:*", base=42.0, noise=0.0, spike_prob=0.0)
    store.save_overrides(user)

    loaded = ProfileStore(user_file=user)
    values = _get("TEST:PV:ONE", loaded)["value"]
    assert (values == 42.0).all()


def test_naive_time_is_pacific(store):
    naive = START.replace(tzinfo=None)
    pd.testing.assert_frame_equal(
        _get(AMP, store, naive, naive + (END - START)), _get(AMP, store)
    )


def test_naive_time_in_dst_change_hour_is_refused(store):
    with pytest.raises(ValueError, match="daylight saving"):
        _get(AMP, store, datetime(2024, 11, 3, 1, 30), datetime(2024, 11, 3, 3))


def test_aware_utc_time_is_accepted(store):
    utc = START.astimezone(timezone.utc)
    pd.testing.assert_frame_equal(
        _get(AMP, store, utc, utc + (END - START)), _get(AMP, store)
    )


@pytest.mark.parametrize("suffix", ["CUDSTATUS", "CUDSEVR"])
def test_fault_history_pvs_are_empty_for_now(store, suffix):
    frame = _get(f"ACCL:L1B:0210:{suffix}", store)
    assert frame.empty
    assert list(frame.columns) == archiver.COLUMNS


def test_empty_window_and_no_pvs(store):
    assert _get(AMP, store, END, START).empty
    assert mock_values_over_time_range([], START, END, store=store) == {}


def test_repeated_pvs_returned_once(store):
    result = mock_values_over_time_range([AMP, AMP], START, END, store=store)
    assert list(result) == [AMP]
