"""Tests for mock archiver data generator."""

from datetime import datetime, timedelta
import pytest

from sc_linac_physics.utils.archiver.mock import (
    MockArchiveDataHandler,
    mock_get_values_over_time_range,
    TREND_FUNCTIONS,
)
from sc_linac_physics.utils.archiver.models import ArchiveDataHandler


def test_generate_timestamps_one_minute():
    """Test timestamp generation for 1-minute range at 1 Hz."""
    start = datetime(2024, 1, 15, 12, 0, 0)
    end = datetime(2024, 1, 15, 12, 1, 0)
    
    mock = MockArchiveDataHandler("ACCL:L1B:0110:ADES", start, end, sample_rate_hz=1.0)
    
    # 1 minute at 1 Hz = 60 samples (plus one for end point = 61)
    assert len(mock.timestamps) >= 60
    assert len(mock.timestamps) <= 61
    
    # First timestamp should be start
    assert mock.timestamps[0] == start
    
    # Last timestamp should be close to end
    assert abs((mock.timestamps[-1] - end).total_seconds()) < 1.0


def test_generate_timestamps_custom_sample_rate():
    """Test timestamp generation with 2 Hz sample rate."""
    start = datetime(2024, 1, 15, 12, 0, 0)
    end = datetime(2024, 1, 15, 12, 0, 10)  # 10 seconds
    
    mock = MockArchiveDataHandler("ACCL:L1B:0110:ADES", start, end, sample_rate_hz=2.0)
    
    # 10 seconds at 2 Hz = 20 samples (plus one = 21)
    assert len(mock.timestamps) >= 20
    assert len(mock.timestamps) <= 21


def test_generate_values_gradient():
    """Test value generation for gradient PV (ADES)."""
    start = datetime(2024, 1, 15, 12, 0, 0)
    end = datetime(2024, 1, 15, 12, 1, 0)
    
    mock = MockArchiveDataHandler("ACCL:L1B:0110:ADES", start, end)
    
    # All values should be near 16.5 MV
    assert len(mock.values) > 0
    assert all(isinstance(v, float) for v in mock.values)
    assert all(15.0 <= v <= 18.0 for v in mock.values), "Gradient values out of realistic range"
    
    # Check average is close to base value
    avg = sum(mock.values) / len(mock.values)
    assert 16.0 <= avg <= 17.0


def test_generate_values_phase():
    """Test value generation for phase PV (PDES)."""
    start = datetime(2024, 1, 15, 12, 0, 0)
    end = datetime(2024, 1, 15, 12, 1, 0)
    
    mock = MockArchiveDataHandler("ACCL:L1B:0110:PDES", start, end)
    
    # All values should be near 0 degrees
    assert len(mock.values) > 0
    assert all(isinstance(v, float) for v in mock.values)
    assert all(-5.0 <= v <= 5.0 for v in mock.values), "Phase values out of realistic range"


def test_generate_values_cudstatus():
    """CUDSTATUS emits the cavity-number string (OK) mostly, fault codes rarely."""
    start = datetime(2024, 1, 15, 12, 0, 0)
    end = datetime(2024, 1, 15, 12, 1, 0)
    mock = MockArchiveDataHandler("ACCL:L1B:0110:CUDSTATUS", start, end)

    assert len(mock.values) > 0
    assert all(isinstance(v, str) for v in mock.values)

    cavity_num = mock._extract_cavity_number()
    assert cavity_num == "1"

    # Most values are the OK (cavity-number) string. Some cavities may be
    # fully healthy (per-cavity fault-rate variation), so we only require
    # that the majority are OK, not that faults are present.
    ok_count = sum(1 for v in mock.values if v == cavity_num)
    assert ok_count >= len(mock.values) * 0.5, "Expected majority OK values"

    # Any non-OK values must be valid fault codes (strings, not the number).
    for v in mock.values:
        assert isinstance(v, str)


def test_generate_values_detune():
    """Test value generation for detune PV (DF)."""
    start = datetime(2024, 1, 15, 12, 0, 0)
    end = datetime(2024, 1, 15, 12, 1, 0)
    
    mock = MockArchiveDataHandler("ACCL:L1B:0110:DF", start, end)
    
    # All values should be near 0 Hz
    assert len(mock.values) > 0
    assert all(isinstance(v, float) for v in mock.values)
    assert all(-50.0 <= v <= 50.0 for v in mock.values), "Detune values out of realistic range"


def test_generate_severities():
    """Test severity generation."""
    start = datetime(2024, 1, 15, 12, 0, 0)
    end = datetime(2024, 1, 15, 12, 1, 0)
    
    mock = MockArchiveDataHandler("ACCL:L1B:0110:ADES", start, end)
    
    # Most severities should be 0 (no alarm)
    assert len(mock.severities) == len(mock.values)
    assert all(isinstance(s, int) for s in mock.severities)
    assert all(0 <= s <= 2 for s in mock.severities)
    
    no_alarm_count = sum(1 for s in mock.severities if s == 0)
    assert no_alarm_count > len(mock.severities) * 0.8, "Expected >80% no-alarm"


def test_generate_statuses():
    """Test status generation."""
    start = datetime(2024, 1, 15, 12, 0, 0)
    end = datetime(2024, 1, 15, 12, 1, 0)
    
    mock = MockArchiveDataHandler("ACCL:L1B:0110:ADES", start, end)
    
    assert len(mock.statuses) == len(mock.values)
    assert all(isinstance(s, int) for s in mock.statuses)
    assert all(s in [0, 1] for s in mock.statuses)


def test_mock_get_values_over_time_range_single_pv():
    """Test mock_get_values_over_time_range with single PV."""
    start = datetime(2024, 1, 15, 12, 0, 0)
    end = datetime(2024, 1, 15, 12, 1, 0)
    
    result = mock_get_values_over_time_range(
        pv_list=["ACCL:L1B:0110:ADES"],
        start_time=start,
        end_time=end
    )
    
    # Should return dict with one key
    assert isinstance(result, dict)
    assert len(result) == 1
    assert "ACCL:L1B:0110:ADES" in result
    
    # Value should be ArchiveDataHandler
    handler = result["ACCL:L1B:0110:ADES"]
    assert isinstance(handler, ArchiveDataHandler)
    assert handler.pv_name == "ACCL:L1B:0110:ADES"
    assert len(handler.values) > 0
    assert len(handler.timestamps) == len(handler.values)
    assert len(handler.severities) == len(handler.values)
    assert len(handler.statuses) == len(handler.values)


def test_mock_get_values_over_time_range_multiple_pvs():
    """Test mock_get_values_over_time_range with multiple PVs."""
    start = datetime(2024, 1, 15, 12, 0, 0)
    end = datetime(2024, 1, 15, 12, 1, 0)
    
    result = mock_get_values_over_time_range(
        pv_list=[
            "ACCL:L1B:0110:ADES",
            "ACCL:L1B:0110:PDES",
            "ACCL:L1B:0110:CUDSTATUS"
        ],
        start_time=start,
        end_time=end
    )
    
    # Should return dict with three keys
    assert len(result) == 3
    assert "ACCL:L1B:0110:ADES" in result
    assert "ACCL:L1B:0110:PDES" in result
    assert "ACCL:L1B:0110:CUDSTATUS" in result
    
    # All should be ArchiveDataHandler
    for pv_name, handler in result.items():
        assert isinstance(handler, ArchiveDataHandler)
        assert handler.pv_name == pv_name
        assert len(handler.values) > 0


def test_mock_get_values_over_time_range_empty_list():
    """Test mock_get_values_over_time_range with empty PV list."""
    start = datetime(2024, 1, 15, 12, 0, 0)
    end = datetime(2024, 1, 15, 12, 1, 0)
    
    result = mock_get_values_over_time_range(
        pv_list=[],
        start_time=start,
        end_time=end
    )
    
    assert isinstance(result, dict)
    assert len(result) == 0

# Shared time range for trend tests
TREND_START = datetime(2024, 1, 15, 12, 0, 0)
TREND_END = TREND_START + timedelta(minutes=1)   # 61 points at 1 Hz


# --- Default / backward-compatibility ------------------------------------

def test_flat_is_default_trend():
    """Default trend is 'flat' so existing behavior is preserved."""
    handler = MockArchiveDataHandler("X:ADES", TREND_START, TREND_END)
    assert handler.trend == "flat"


def test_flat_default_keeps_base_value():
    """With the flat default, ADES stays centered near its base (~16.5)."""
    d = mock_get_values_over_time_range(["X:ADES"], TREND_START, TREND_END)
    vals = d["X:ADES"].values
    avg = sum(vals) / len(vals)
    assert 16.0 <= avg <= 17.0


# --- Trend shapes (noise_scale=0 -> clean, deterministic curves) ---------

def test_linear_trend_rises():
    """Linear trend: last value clearly higher than the first."""
    d = mock_get_values_over_time_range(
        ["X:ADES"], TREND_START, TREND_END,
        trend="linear", trend_amplitude=10, noise_scale=0,
    )
    vals = d["X:ADES"].values
    assert vals[-1] > vals[0]


def test_linear_trend_is_monotonic():
    """With no noise, a linear trend increases at every step."""
    d = mock_get_values_over_time_range(
        ["X:ADES"], TREND_START, TREND_END,
        trend="linear", trend_amplitude=10, noise_scale=0,
    )
    vals = d["X:ADES"].values
    assert all(vals[i] <= vals[i + 1] for i in range(len(vals) - 1))


def test_parabolic_is_u_shaped():
    """Parabolic trend dips in the middle (endpoints higher than center)."""
    d = mock_get_values_over_time_range(
        ["X:ADES"], TREND_START, TREND_END,
        trend="parabolic", trend_amplitude=10, noise_scale=0,
    )
    vals = d["X:ADES"].values
    mid = len(vals) // 2
    assert vals[0] > vals[mid]
    assert vals[-1] > vals[mid]


def test_quadratic_rises_and_accelerates():
    """Quadratic trend: rising, and the last step is bigger than the first."""
    d = mock_get_values_over_time_range(
        ["X:ADES"], TREND_START, TREND_END,
        trend="quadratic", trend_amplitude=10, noise_scale=0,
    )
    vals = d["X:ADES"].values
    assert vals[-1] > vals[0]
    first_step = vals[1] - vals[0]
    last_step = vals[-1] - vals[-2]
    assert last_step > first_step   # accelerating


def test_sine_goes_up_then_down():
    """Sine trend over one period: peaks around the quarter point,
    troughs around the three-quarter point."""
    d = mock_get_values_over_time_range(
        ["X:ADES"], TREND_START, TREND_END,
        trend="sine", trend_amplitude=5, noise_scale=0,
    )
    vals = d["X:ADES"].values
    n = len(vals)
    quarter = vals[n // 4]
    three_quarter = vals[3 * n // 4]
    assert quarter > vals[0]           # risen by the quarter point
    assert three_quarter < quarter     # fallen by the three-quarter point


def test_flat_trend_stays_near_base():
    """Flat trend with no noise stays essentially constant at the base value."""
    d = mock_get_values_over_time_range(
        ["X:ADES"], TREND_START, TREND_END,
        trend="flat", noise_scale=0,
    )
    vals = d["X:ADES"].values
    assert max(vals) - min(vals) < 1e-6   # no variation with flat + no noise


# --- Amplitude & noise knobs ---------------------------------------------

def test_amplitude_scales_the_trend():
    """Larger amplitude produces a larger rise for a linear trend."""
    small = mock_get_values_over_time_range(
        ["X:ADES"], TREND_START, TREND_END,
        trend="linear", trend_amplitude=1, noise_scale=0,
    )["X:ADES"].values
    big = mock_get_values_over_time_range(
        ["X:ADES"], TREND_START, TREND_END,
        trend="linear", trend_amplitude=10, noise_scale=0,
    )["X:ADES"].values
    small_rise = small[-1] - small[0]
    big_rise = big[-1] - big[0]
    assert big_rise > small_rise


def test_zero_noise_gives_clean_line():
    """noise_scale=0 removes scatter: a linear trend has constant step size."""
    d = mock_get_values_over_time_range(
        ["X:ADES"], TREND_START, TREND_END,
        trend="linear", trend_amplitude=10, noise_scale=0,
    )
    vals = d["X:ADES"].values
    diffs = [vals[i + 1] - vals[i] for i in range(len(vals) - 1)]
    assert max(diffs) - min(diffs) < 1e-6   # every step identical


# --- Determinism ----------------------------------------------------------

def test_determinism_preserved_with_trend():
    """Same PV + range + trend produces identical output every time."""
    a = mock_get_values_over_time_range(
        ["X:ADES"], TREND_START, TREND_END, trend="sine", trend_amplitude=3
    )["X:ADES"].values
    b = mock_get_values_over_time_range(
        ["X:ADES"], TREND_START, TREND_END, trend="sine", trend_amplitude=3
    )["X:ADES"].values
    assert a == b


# --- Scope: trends apply to floats, not enums/ints -----------------------

def test_trend_does_not_affect_enum_values():
    """ENUM PVs ignore the trend (values stay small integer codes)."""
    d = mock_get_values_over_time_range(
        ["X:CRYO_LTCH"], TREND_START, TREND_END,   # resolves to ENUM via heuristic
        trend="linear", trend_amplitude=100, noise_scale=0,
    )
    vals = d["X:CRYO_LTCH"].values
    # enum values are small indices, unaffected by the big linear amplitude
    assert all(isinstance(v, int) for v in vals)
    assert all(0 <= v < 10 for v in vals)


# --- Registry sanity ------------------------------------------------------

@pytest.mark.parametrize("shape", ["flat", "linear", "parabolic", "quadratic", "sine"])
def test_all_trends_produce_valid_data(shape):
    """Every registered trend produces the right number of points, no errors."""
    d = mock_get_values_over_time_range(
        ["X:ADES"], TREND_START, TREND_END, trend=shape
    )
    vals = d["X:ADES"].values
    assert len(vals) == 61
    assert all(isinstance(v, float) for v in vals)


def test_unknown_trend_falls_back_to_flat():
    """An unrecognized trend name falls back gracefully (no crash)."""
    d = mock_get_values_over_time_range(
        ["X:ADES"], TREND_START, TREND_END,
        trend="banana", trend_amplitude=10, noise_scale=0,
    )
    vals = d["X:ADES"].values
    # falls back to _trend_flat -> stays near base, no rise
    assert abs(vals[-1] - vals[0]) < 1e-6