"""Tests for the heatmap time slider feature.

Covers:
- FaultEvent dataclass
- CavityFaultResult.get_windowed_counts() with bisect optimization
- FaultDensityBar widget
- FaultHeatmapDisplay slider UI, debounce, and filtering logic
"""

from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest
from PyQt5.QtCore import QPointF

from sc_linac_physics.displays.cavity_display.backend.backend_cavity import (
    SeverityLevel,
)
from sc_linac_physics.displays.cavity_display.backend.fault import (
    FaultEvent,
)
from sc_linac_physics.displays.cavity_display.frontend.heatmap.fault_data_fetcher import (
    CavityFaultResult,
)
from sc_linac_physics.displays.cavity_display.frontend.heatmap.fault_heatmap_display import (
    FaultDensityBar,
    FaultHeatmapDisplay,
)

# ── FaultEvent dataclass ──


class TestFaultEvent:
    def test_basic_creation(self):
        ts = datetime(2025, 4, 27, 10, 0, 0)
        event = FaultEvent(timestamp=ts, tlc="SSA", severity=2)
        assert event.timestamp == ts
        assert event.tlc == "SSA"
        assert event.severity == 2

    def test_equality(self):
        ts = datetime(2025, 4, 27, 10, 0, 0)
        a = FaultEvent(timestamp=ts, tlc="SSA", severity=2)
        b = FaultEvent(timestamp=ts, tlc="SSA", severity=2)
        assert a == b

    def test_inequality_different_tlc(self):
        ts = datetime(2025, 4, 27, 10, 0, 0)
        a = FaultEvent(timestamp=ts, tlc="SSA", severity=2)
        b = FaultEvent(timestamp=ts, tlc="QCH", severity=2)
        assert a != b


# ── CavityFaultResult.get_windowed_counts() with bisect ──


def _ok(ts):
    """A return-to-OK transition (tlc is the cavity number string)."""
    return FaultEvent(ts, "1", SeverityLevel.NO_ALARM)


def _make_events():
    """Create status transitions spread across 4 hours (08:00-12:00).

    Each fault burst is followed by an OK clear, mirroring real archiver
    data where the status PV transitions back to the cavity number.
    """
    base = datetime(2025, 4, 27, 8, 0, 0)
    return [
        # Hour 1 (08:00-09:00): 2 SSA alarms, cleared at 08:45
        FaultEvent(base + timedelta(minutes=10), "SSA", SeverityLevel.ALARM),
        FaultEvent(base + timedelta(minutes=30), "SSA", SeverityLevel.ALARM),
        _ok(base + timedelta(minutes=45)),
        # Hour 2 (09:00-10:00): 1 QCH warning, cleared at 09:30
        FaultEvent(
            base + timedelta(hours=1, minutes=15),
            "QCH",
            SeverityLevel.WARNING,
        ),
        _ok(base + timedelta(hours=1, minutes=30)),
        # Hour 3 (10:00-11:00): 1 SSA invalid + 1 RFP alarm, cleared 10:50
        FaultEvent(
            base + timedelta(hours=2, minutes=5),
            "SSA",
            SeverityLevel.INVALID,
        ),
        FaultEvent(
            base + timedelta(hours=2, minutes=45),
            "RFP",
            SeverityLevel.ALARM,
        ),
        _ok(base + timedelta(hours=2, minutes=50)),
        # Hour 4 (11:00-12:00): 1 QCH alarm, cleared at 11:40
        FaultEvent(
            base + timedelta(hours=3, minutes=20),
            "QCH",
            SeverityLevel.ALARM,
        ),
        _ok(base + timedelta(hours=3, minutes=40)),
    ]


class TestGetWindowedCounts:
    def test_returns_none_when_no_events(self):
        result = CavityFaultResult(
            cm_name="01", cavity_num=1, fault_events=None
        )
        assert (
            result.get_windowed_counts(
                datetime(2025, 1, 1), datetime(2025, 1, 2)
            )
            is None
        )

    def test_full_range_returns_all(self):
        events = _make_events()
        result = CavityFaultResult(
            cm_name="01",
            cavity_num=1,
            fault_counts_by_tlc={},
            fault_events=events,
        )
        base = datetime(2025, 4, 27, 8, 0, 0)
        counts = result.get_windowed_counts(base, base + timedelta(hours=4))
        assert counts["SSA"].alarm_count == 2
        assert counts["SSA"].invalid_count == 1
        assert counts["QCH"].warning_count == 1
        assert counts["QCH"].alarm_count == 1
        assert counts["RFP"].alarm_count == 1

    def test_first_hour_window(self):
        events = _make_events()
        result = CavityFaultResult(
            cm_name="01",
            cavity_num=1,
            fault_counts_by_tlc={},
            fault_events=events,
        )
        base = datetime(2025, 4, 27, 8, 0, 0)
        counts = result.get_windowed_counts(base, base + timedelta(hours=1))
        assert counts["SSA"].alarm_count == 2
        assert "QCH" not in counts
        assert "RFP" not in counts

    def test_second_hour_window(self):
        events = _make_events()
        result = CavityFaultResult(
            cm_name="01",
            cavity_num=1,
            fault_counts_by_tlc={},
            fault_events=events,
        )
        base = datetime(2025, 4, 27, 9, 0, 0)
        counts = result.get_windowed_counts(base, base + timedelta(hours=1))
        assert counts["QCH"].warning_count == 1
        assert "SSA" not in counts

    def test_empty_window_returns_empty_dict(self):
        events = _make_events()
        result = CavityFaultResult(
            cm_name="01",
            cavity_num=1,
            fault_counts_by_tlc={},
            fault_events=events,
        )
        counts = result.get_windowed_counts(
            datetime(2025, 4, 28, 0, 0, 0),
            datetime(2025, 4, 28, 1, 0, 0),
        )
        assert counts == {}

    def test_empty_events_list_returns_empty_dict(self):
        result = CavityFaultResult(
            cm_name="01",
            cavity_num=1,
            fault_counts_by_tlc={},
            fault_events=[],
        )
        counts = result.get_windowed_counts(
            datetime(2025, 1, 1), datetime(2025, 1, 2)
        )
        assert counts == {}

    def test_standing_fault_carries_into_every_window(self):
        """A fault standing since before the fetch shows in every window.

        A cavity stuck in a fault state has no transitions during the
        range, just the archiver's last-known-value sample from before
        the range start.
        """
        fetch_start = datetime(2025, 6, 9, 14, 21, 0)
        events = [
            # The archiver's last-known-value sample, before the range
            FaultEvent(
                fetch_start - timedelta(hours=2), "SSA", SeverityLevel.ALARM
            ),
        ]
        result = CavityFaultResult(
            cm_name="01",
            cavity_num=1,
            fault_counts_by_tlc={},
            fault_events=events,
        )
        # Any window inside the range sees the standing fault
        for offset_hours in (0, 1, 2, 3):
            window_start = fetch_start + timedelta(hours=offset_hours)
            counts = result.get_windowed_counts(
                window_start, window_start + timedelta(hours=1)
            )
            assert (
                counts["SSA"].alarm_count == 1
            ), f"standing fault missing from window at +{offset_hours}h"

    def test_cleared_fault_stops_carrying_into_windows(self):
        """Once the status returns to OK, the fault must stop carrying."""
        base = datetime(2025, 6, 9, 14, 0, 0)
        events = [
            FaultEvent(base - timedelta(hours=2), "SSA", SeverityLevel.ALARM),
            _ok(base + timedelta(hours=1)),  # cleared at 15:00
        ]
        result = CavityFaultResult(
            cm_name="01",
            cavity_num=1,
            fault_counts_by_tlc={},
            fault_events=events,
        )
        # Window while the fault is still standing
        counts = result.get_windowed_counts(base, base + timedelta(hours=1))
        assert counts["SSA"].alarm_count == 1
        # Window after the clear
        counts = result.get_windowed_counts(
            base + timedelta(hours=2), base + timedelta(hours=3)
        )
        assert counts == {}

    def test_ok_transitions_not_counted_as_faults(self):
        """OK transitions inside a window are state markers, not faults."""
        base = datetime(2025, 6, 9, 14, 0, 0)
        events = [
            FaultEvent(
                base + timedelta(minutes=10), "SSA", SeverityLevel.ALARM
            ),
            _ok(base + timedelta(minutes=20)),
        ]
        result = CavityFaultResult(
            cm_name="01",
            cavity_num=1,
            fault_counts_by_tlc={},
            fault_events=events,
        )
        counts = result.get_windowed_counts(base, base + timedelta(hours=1))
        assert counts["SSA"].alarm_count == 1
        assert "1" not in counts  # the OK marker's tlc must not appear

    def test_bisect_boundary_precision(self):
        """Events exactly on window boundaries should be included."""
        base = datetime(2025, 4, 27, 10, 0, 0)
        events = [
            FaultEvent(base, "SSA", SeverityLevel.ALARM),
            FaultEvent(base + timedelta(hours=1), "SSA", SeverityLevel.ALARM),
        ]
        result = CavityFaultResult(
            cm_name="01",
            cavity_num=1,
            fault_counts_by_tlc={},
            fault_events=events,
        )
        counts = result.get_windowed_counts(base, base + timedelta(hours=1))
        # both boundary events should be included
        assert counts["SSA"].alarm_count == 2


# ── FaultDensityBar ──


class TestFaultDensityBar:
    def test_creates_without_crash(self):
        bar = FaultDensityBar()
        assert bar is not None

    def test_set_data_empty(self):
        bar = FaultDensityBar()
        bar.set_data([], None, None)
        assert bar._max_count == 0
        assert bar._buckets == []

    def test_set_data_with_timestamps(self):
        bar = FaultDensityBar()
        base = datetime(2025, 4, 27, 8, 0, 0)
        timestamps = [
            base + timedelta(minutes=10),
            base + timedelta(minutes=11),
            base + timedelta(minutes=12),
            base + timedelta(hours=3),
        ]
        bar.set_data(timestamps, base, base + timedelta(hours=4))
        assert bar._max_count > 0
        assert len(bar._buckets) == FaultDensityBar.NUM_BUCKETS
        # First few buckets should have data, last bucket should too
        assert sum(bar._buckets) == 4

    def test_set_data_none_range_clears(self):
        bar = FaultDensityBar()
        base = datetime(2025, 4, 27, 8, 0, 0)
        bar.set_data([base], base, base + timedelta(hours=1))
        assert bar._max_count > 0
        bar.set_data([], None, None)
        assert bar._max_count == 0

    def test_window_position_overlay(self):
        bar = FaultDensityBar()
        bar.set_window_position(0.25, 0.75)
        assert bar._window_start_frac == 0.25
        assert bar._window_end_frac == 0.75

    def test_window_position_clamped(self):
        bar = FaultDensityBar()
        bar.set_window_position(-0.5, 1.5)
        assert bar._window_start_frac == 0.0
        assert bar._window_end_frac == 1.0

    def test_clear_window_position(self):
        bar = FaultDensityBar()
        bar.set_window_position(0.2, 0.8)
        bar.clear_window_position()
        assert bar._window_start_frac is None
        assert bar._window_end_frac is None

    def test_set_data_skips_out_of_range_timestamps(self):
        """Timestamps outside [start, end] should not land in any bucket.

        The archiver includes a sample from before the requested start,
        which would otherwise wrap to a negative bucket index.
        """
        bar = FaultDensityBar()
        base = datetime(2025, 4, 27, 8, 0, 0)
        end = base + timedelta(hours=1)
        timestamps = [
            base - timedelta(minutes=5),  # before range (archiver sample)
            base + timedelta(minutes=30),  # in range
            end + timedelta(minutes=5),  # after range
        ]
        bar.set_data(timestamps, base, end)
        assert sum(bar._buckets) == 1
        assert bar._buckets[-1] == 0


# ── FaultHeatmapDisplay slider UI ──


@pytest.fixture
def display():
    disp = FaultHeatmapDisplay()
    yield disp
    disp.close()


class TestTimeSliderUI:
    def test_slider_exists_and_disabled_by_default(self, display):
        assert hasattr(display, "_time_slider")
        assert not display._time_slider.isEnabled()

    def test_slider_enable_checkbox_default_off(self, display):
        assert not display._slider_enable_cb.isChecked()

    def test_enable_slider_activates_controls(self, display):
        display._slider_enable_cb.setChecked(True)
        assert display._time_slider.isEnabled()
        assert display._slider_active

    def test_disable_slider_deactivates(self, display):
        display._slider_enable_cb.setChecked(True)
        display._slider_enable_cb.setChecked(False)
        assert not display._time_slider.isEnabled()
        assert not display._slider_active

    def test_slider_label_shows_full_range_when_disabled(self, display):
        assert display._slider_time_label.text() == "Full Range"

    def test_window_duration_parsing(self, display):
        display._window_combo.setCurrentText("15m")
        assert display._get_window_duration() == timedelta(minutes=15)
        display._window_combo.setCurrentText("30m")
        assert display._get_window_duration() == timedelta(minutes=30)
        display._window_combo.setCurrentText("1h")
        assert display._get_window_duration() == timedelta(hours=1)
        display._window_combo.setCurrentText("2h")
        assert display._get_window_duration() == timedelta(hours=2)
        display._window_combo.setCurrentText("4h")
        assert display._get_window_duration() == timedelta(hours=4)

    def test_default_window_is_1h(self, display):
        assert display._window_combo.currentText() == "1h"

    def test_window_combo_is_editable(self, display):
        """Custom window sizes can be typed, not just preset picks."""
        assert display._window_combo.isEditable()

    def test_custom_window_duration_parsing(self, display):
        cases = {
            "45m": timedelta(minutes=45),
            "90m": timedelta(minutes=90),
            "1h30m": timedelta(minutes=90),
            "1.5h": timedelta(minutes=90),
            "45": timedelta(minutes=45),  # bare number means minutes
            "2h": timedelta(hours=2),
        }
        for text, expected in cases.items():
            display._window_combo.setCurrentText(text)
            assert display._get_window_duration() == expected, text

    def test_invalid_window_text_falls_back_to_last_valid(self, display):
        display._window_combo.setCurrentText("30m")
        assert display._get_window_duration() == timedelta(minutes=30)
        display._window_combo.setCurrentText("garbage")
        assert display._get_window_duration() == timedelta(minutes=30)
        # Zero or sub-minute entries are rejected too
        display._window_combo.setCurrentText("0m")
        assert display._get_window_duration() == timedelta(minutes=30)

    def test_zoom_options_preserve_custom_value(self, display):
        """A typed window size survives the post-fetch preset rebuild."""
        base = datetime(2025, 4, 27, 8, 0, 0)
        display._fetch_start = base
        display._fetch_end = base + timedelta(hours=24)
        display._window_combo.setCurrentText("45m")
        display._update_zoom_options()
        assert display._window_combo.currentText() == "45m"

    def test_density_bar_exists(self, display):
        assert hasattr(display, "_density_bar")
        assert isinstance(display._density_bar, FaultDensityBar)

    def test_debounce_timer_exists(self, display):
        assert hasattr(display, "_slider_debounce")
        assert display._slider_debounce.interval() == 50
        assert display._slider_debounce.isSingleShot()

    def test_zoom_label_shown(self, display):
        """The combo label should say 'Zoom:' not 'Window:'."""
        # Find the QLabel immediately before the combo box in the layout
        combo_tooltip = display._window_combo.toolTip()
        assert "Zoom" in combo_tooltip or "zoom" in combo_tooltip


class TestTimeSliderFormatting:
    def test_format_time_short_range(self, display):
        """Within 24h, show only HH:MM."""
        display._fetch_start = datetime(2025, 4, 27, 8, 0, 0)
        display._fetch_end = datetime(2025, 4, 27, 16, 0, 0)
        label = display._format_slider_time(
            datetime(2025, 4, 27, 10, 0, 0),
            datetime(2025, 4, 27, 11, 0, 0),
        )
        assert "10:00" in label
        assert "11:00" in label
        # Should NOT contain date
        assert "/" not in label

    def test_format_time_multi_day_range(self, display):
        """Over 24h, show MM/DD HH:MM."""
        display._fetch_start = datetime(2025, 4, 25, 8, 0, 0)
        display._fetch_end = datetime(2025, 4, 28, 8, 0, 0)
        label = display._format_slider_time(
            datetime(2025, 4, 26, 10, 0, 0),
            datetime(2025, 4, 26, 11, 0, 0),
        )
        assert "04/26" in label
        assert "10:00" in label


class TestTimeSliderLogic:
    def test_no_crash_when_slider_moved_without_data(self, display):
        """Slider should handle gracefully when no data is loaded."""
        display._slider_enable_cb.setChecked(True)
        display._time_slider.setValue(500)
        # Trigger debounce manually since timer won't fire in tests
        display._apply_slider_position()
        # Should not crash

    def test_disabling_slider_restores_full_range_label(self, display):
        display._slider_enable_cb.setChecked(True)
        display._slider_enable_cb.setChecked(False)
        assert display._slider_time_label.text() == "Full Range"

    def test_get_slider_window_none_without_data(self, display):
        assert display._get_slider_window() is None

    def test_get_slider_window_with_data(self, display):
        base = datetime(2025, 4, 27, 8, 0, 0)
        display._fetch_start = base
        display._fetch_end = base + timedelta(hours=24)
        display._results = [
            CavityFaultResult(
                cm_name="01",
                cavity_num=1,
                fault_counts_by_tlc={},
                fault_events=[],
            )
        ]
        display._window_combo.setCurrentText("1h")
        display._time_slider.setValue(0)

        window = display._get_slider_window()
        assert window is not None
        window_start, window_end = window
        assert window_start == base
        diff = (window_end - window_start).total_seconds()
        assert abs(diff - 3600) < 1  # 1 hour window

    def test_get_slider_window_at_end(self, display):
        base = datetime(2025, 4, 27, 8, 0, 0)
        display._fetch_start = base
        display._fetch_end = base + timedelta(hours=24)
        display._results = [
            CavityFaultResult(
                cm_name="01",
                cavity_num=1,
                fault_counts_by_tlc={},
                fault_events=[],
            )
        ]
        display._window_combo.setCurrentText("1h")
        display._time_slider.setValue(1000)

        window = display._get_slider_window()
        assert window is not None
        _, window_end = window
        # Window end should be at fetch_end
        assert window_end == display._fetch_end

    def test_zoom_options_filtered_by_fetch_range(self, display):
        """Zoom combo should only show levels ≤ half the fetch range."""
        base = datetime(2025, 4, 27, 8, 0, 0)

        # 4h fetch → half is 2h → show 15m, 30m, 1h, 2h (not 4h)
        display._fetch_start = base
        display._fetch_end = base + timedelta(hours=4)
        display._update_zoom_options()
        options = [
            display._window_combo.itemText(i)
            for i in range(display._window_combo.count())
        ]
        assert "4h" not in options
        assert "2h" in options
        assert "15m" in options

    def test_zoom_options_short_fetch(self, display):
        """Very short fetch should drop all presets but stay usable."""
        base = datetime(2025, 4, 27, 8, 0, 0)

        # 20m fetch → half is 10m → no preset qualifies (15m > 10m),
        # so the combo defaults to a custom half-range window
        display._fetch_start = base
        display._fetch_end = base + timedelta(minutes=20)
        display._update_zoom_options()
        assert display._window_combo.count() == 0
        assert display._window_combo.currentText() == "10m"
        assert display._get_window_duration() == timedelta(minutes=10)

    def test_zoom_options_24h_fetch(self, display):
        """24h fetch should keep all zoom levels."""
        base = datetime(2025, 4, 27, 8, 0, 0)
        display._fetch_start = base
        display._fetch_end = base + timedelta(hours=24)
        display._update_zoom_options()
        options = [
            display._window_combo.itemText(i)
            for i in range(display._window_combo.count())
        ]
        assert options == ["15m", "30m", "1h", "2h", "4h"]

    def test_zoom_preserves_selection_if_valid(self, display):
        """Previous selection should be preserved after zoom update."""
        base = datetime(2025, 4, 27, 8, 0, 0)
        display._fetch_start = base
        display._fetch_end = base + timedelta(hours=24)
        display._update_zoom_options()
        display._window_combo.setCurrentText("30m")

        # same range again, 30m should still be selected
        display._update_zoom_options()
        assert display._window_combo.currentText() == "30m"

    def test_zoom_falls_back_to_largest_if_previous_removed(self, display):
        """If previous selection is too large, pick the largest remaining."""
        base = datetime(2025, 4, 27, 8, 0, 0)
        display._fetch_start = base
        display._fetch_end = base + timedelta(hours=24)
        display._update_zoom_options()
        display._window_combo.setCurrentText("4h")

        # Shrink to 2h fetch → 4h no longer available, should pick 1h
        display._fetch_end = base + timedelta(hours=2)
        display._update_zoom_options()
        assert display._window_combo.currentText() == "1h"

    def test_density_bar_excludes_ok_transitions(self, display):
        """OK transitions must not paint fault density."""
        base = datetime(2025, 6, 9, 14, 0, 0)
        display._fetch_start = base
        display._fetch_end = base + timedelta(hours=4)
        display._results = [
            CavityFaultResult(
                cm_name="01",
                cavity_num=1,
                fault_counts_by_tlc={},
                fault_events=[
                    FaultEvent(
                        base + timedelta(minutes=10),
                        "SSA",
                        SeverityLevel.ALARM,
                    ),
                    FaultEvent(
                        base + timedelta(minutes=20),
                        "1",
                        SeverityLevel.NO_ALARM,
                    ),
                ],
            )
        ]
        display._update_density_bar()
        assert sum(display._density_bar._buckets) == 1

    def test_scrubbing_pins_color_scale_to_full_range_max(self, display):
        """Windows are colored against the full-range max, not their own."""
        from sc_linac_physics.displays.cavity_display.backend.fault import (
            FaultCounter,
        )

        base = datetime(2025, 4, 27, 8, 0, 0)
        # 10 alarms, all in the first hour of a 4-hour fetch
        events = [
            FaultEvent(
                base + timedelta(minutes=i * 5), "SSA", SeverityLevel.ALARM
            )
            for i in range(10)
        ]
        display._results = [
            CavityFaultResult(
                cm_name="01",
                cavity_num=1,
                fault_counts_by_tlc={"SSA": FaultCounter(alarm_count=10)},
                fault_events=events,
            )
        ]
        display._fetch_start = base
        display._fetch_end = base + timedelta(hours=4)

        # last (empty) hour should still use the full-range max of 10
        display._apply_windowed_results(
            base + timedelta(hours=3), base + timedelta(hours=4)
        )
        assert display._color_mapper.vmax == 10

    def test_window_status_shows_window_max(self, display):
        """While scrubbing, the status bar reflects the current window."""
        from sc_linac_physics.displays.cavity_display.backend.fault import (
            FaultCounter,
        )

        base = datetime(2025, 4, 27, 8, 0, 0)
        events = [
            FaultEvent(base + timedelta(minutes=i), "SSA", SeverityLevel.ALARM)
            for i in range(5)
        ]
        events.append(_ok(base + timedelta(minutes=10)))  # fault cleared
        display._results = [
            CavityFaultResult(
                cm_name="01",
                cavity_num=1,
                fault_counts_by_tlc={"SSA": FaultCounter(alarm_count=5)},
                fault_events=events,
            )
        ]
        display._fetch_start = base
        display._fetch_end = base + timedelta(hours=4)

        display._apply_windowed_results(base, base + timedelta(hours=1))
        text = display._status_label.text()
        assert "Window" in text
        assert "(5)" in text

        # An empty window reports "no faults"
        display._apply_windowed_results(
            base + timedelta(hours=2), base + timedelta(hours=3)
        )
        assert "no faults" in display._status_label.text()

    def test_disabling_slider_restores_full_range_status(self, display):
        display._full_range_status = "40 faulted | 0 OK"
        display._status_label.setText("Window 10:00 — 11:00: no faults")
        display._slider_enable_cb.setChecked(True)
        display._slider_enable_cb.setChecked(False)
        assert display._status_label.text() == "40 faulted | 0 OK"

    def test_page_step_matches_window_width(self, display):
        """Groove clicks should advance exactly one window."""
        base = datetime(2025, 4, 27, 8, 0, 0)
        display._fetch_start = base
        display._fetch_end = base + timedelta(hours=24)
        display._results = [
            CavityFaultResult(
                cm_name="01",
                cavity_num=1,
                fault_counts_by_tlc={},
                fault_events=[],
            )
        ]
        display._window_combo.setCurrentText("1h")
        display._apply_slider_position()
        # 1h window over 23h slidable -> round(3600/82800*1000)
        assert display._time_slider.pageStep() == 43

    def test_density_bar_respects_severity_filter(self, display):
        """Unchecking a severity removes those faults from the bar."""
        base = datetime(2025, 6, 9, 14, 0, 0)
        display._fetch_start = base
        display._fetch_end = base + timedelta(hours=4)
        display._results = [
            CavityFaultResult(
                cm_name="01",
                cavity_num=1,
                fault_counts_by_tlc={},
                fault_events=[
                    FaultEvent(
                        base + timedelta(minutes=10),
                        "SSA",
                        SeverityLevel.ALARM,
                    ),
                    FaultEvent(
                        base + timedelta(minutes=20),
                        "QCH",
                        SeverityLevel.WARNING,
                    ),
                ],
            )
        ]
        display._update_density_bar()
        assert sum(display._density_bar._buckets) == 2

        display._cb_warnings.setChecked(False)
        assert sum(display._density_bar._buckets) == 1

        display._cb_warnings.setChecked(True)
        assert sum(display._density_bar._buckets) == 2

    def test_density_bar_respects_tlc_filter(self, display):
        """Selecting a TLC narrows the bar to that fault type."""
        from sc_linac_physics.displays.cavity_display.backend.fault import (
            FaultCounter,
        )

        base = datetime(2025, 6, 9, 14, 0, 0)
        display._fetch_start = base
        display._fetch_end = base + timedelta(hours=4)
        display._results = [
            CavityFaultResult(
                cm_name="01",
                cavity_num=1,
                fault_counts_by_tlc={
                    "SSA": FaultCounter(alarm_count=1),
                    "QCH": FaultCounter(alarm_count=1),
                },
                fault_events=[
                    FaultEvent(
                        base + timedelta(minutes=10),
                        "SSA",
                        SeverityLevel.ALARM,
                    ),
                    FaultEvent(
                        base + timedelta(minutes=20),
                        "QCH",
                        SeverityLevel.ALARM,
                    ),
                ],
            )
        ]
        display._populate_tlc_combo()
        display._tlc_combo.setCurrentText("SSA")
        assert sum(display._density_bar._buckets) == 1

    def test_windowed_counts_reach_cavity_widgets(self, display):
        """End to end: scrubbing recolors widgets with windowed counts."""
        from sc_linac_physics.displays.cavity_display.backend.fault import (
            FaultCounter,
        )

        base = datetime(2025, 4, 27, 8, 0, 0)
        cm_name = next(iter(display._cm_widgets))
        events = [
            FaultEvent(base + timedelta(minutes=m), "SSA", SeverityLevel.ALARM)
            for m in (10, 20, 30)
        ]
        events.append(_ok(base + timedelta(minutes=40)))
        display._results = [
            CavityFaultResult(
                cm_name=cm_name,
                cavity_num=1,
                fault_counts_by_tlc={"SSA": FaultCounter(alarm_count=3)},
                fault_events=events,
            )
        ]
        display._fetch_start = base
        display._fetch_end = base + timedelta(hours=4)

        cm_widget = display._cm_widgets[cm_name]
        cm_widget.update_cavity = Mock()

        # Window over the fault burst: widget gets the windowed count
        display._apply_windowed_results(base, base + timedelta(hours=1))
        args = cm_widget.update_cavity.call_args[0]
        assert args[0] == 1  # cavity number
        assert args[1] == 3  # windowed count

        # Window after the clear: count drops to zero
        cm_widget.update_cavity.reset_mock()
        display._apply_windowed_results(
            base + timedelta(hours=2), base + timedelta(hours=3)
        )
        args = cm_widget.update_cavity.call_args[0]
        assert args[1] == 0

    def test_density_bar_click_emits_fraction(self):
        from PyQt5.QtCore import QEvent, Qt
        from PyQt5.QtGui import QMouseEvent

        bar = FaultDensityBar()
        bar.resize(200, 16)
        received = []
        bar.time_clicked.connect(received.append)

        event = QMouseEvent(
            QEvent.MouseButtonPress,
            QPointF(100.0, 8.0),
            Qt.LeftButton,
            Qt.LeftButton,
            Qt.NoModifier,
        )
        bar.mousePressEvent(event)
        assert len(received) == 1
        assert abs(received[0] - 0.5) < 0.01

    def test_density_bar_click_centers_window(self, display):
        """Clicking the bar centers the slider window on that time."""
        base = datetime(2025, 4, 27, 8, 0, 0)
        display._fetch_start = base
        display._fetch_end = base + timedelta(hours=24)
        display._results = [
            CavityFaultResult(
                cm_name="01",
                cavity_num=1,
                fault_counts_by_tlc={},
                fault_events=[],
            )
        ]
        display._slider_enable_cb.setChecked(True)
        display._window_combo.setCurrentText("1h")

        # Click the middle of the bar: window centered on hour 12 means
        # window_start = 11.5h, slidable = 23h -> value 500
        display._on_density_bar_clicked(0.5)
        assert display._time_slider.value() == 500

        # Clicks near the edges clamp to the slider range
        display._on_density_bar_clicked(0.0)
        assert display._time_slider.value() == 0
        display._on_density_bar_clicked(1.0)
        assert display._time_slider.value() == 1000

    def test_density_bar_click_ignored_when_slider_inactive(self, display):
        display._time_slider.setValue(0)
        display._on_density_bar_clicked(0.5)
        assert display._time_slider.value() == 0

    def test_play_button_disabled_until_slider_enabled(self, display):
        assert not display._play_btn.isEnabled()
        display._slider_enable_cb.setChecked(True)
        assert display._play_btn.isEnabled()
        display._slider_enable_cb.setChecked(False)
        assert not display._play_btn.isEnabled()

    def test_play_unchecks_itself_without_data(self, display):
        display._slider_enable_cb.setChecked(True)
        display._play_btn.setChecked(True)
        assert not display._play_btn.isChecked()
        assert not display._play_timer.isActive()

    def test_play_step_advances_one_window(self, display):
        base = datetime(2025, 4, 27, 8, 0, 0)
        display._fetch_start = base
        display._fetch_end = base + timedelta(hours=24)
        display._results = [
            CavityFaultResult(
                cm_name="01",
                cavity_num=1,
                fault_counts_by_tlc={},
                fault_events=[],
            )
        ]
        display._window_combo.setCurrentText("1h")
        display._time_slider.setValue(0)

        # 1h window over 23h slidable -> step of round(3600/82800*1000)
        assert display._get_play_step() == 43
        display._play_step()
        assert display._time_slider.value() == 43

    def test_play_stops_at_end_of_range(self, display):
        base = datetime(2025, 4, 27, 8, 0, 0)
        display._fetch_start = base
        display._fetch_end = base + timedelta(hours=24)
        display._results = [
            CavityFaultResult(
                cm_name="01",
                cavity_num=1,
                fault_counts_by_tlc={},
                fault_events=[],
            )
        ]
        display._slider_enable_cb.setChecked(True)
        display._window_combo.setCurrentText("1h")
        display._play_btn.setChecked(True)
        assert display._play_timer.isActive()

        display._time_slider.setValue(990)
        display._play_step()
        assert display._time_slider.value() == 1000
        assert not display._play_btn.isChecked()
        assert not display._play_timer.isActive()

    def test_disabling_slider_stops_playback(self, display):
        base = datetime(2025, 4, 27, 8, 0, 0)
        display._fetch_start = base
        display._fetch_end = base + timedelta(hours=24)
        display._results = [
            CavityFaultResult(
                cm_name="01",
                cavity_num=1,
                fault_counts_by_tlc={},
                fault_events=[],
            )
        ]
        display._slider_enable_cb.setChecked(True)
        display._play_btn.setChecked(True)
        assert display._play_timer.isActive()

        display._slider_enable_cb.setChecked(False)
        assert not display._play_btn.isChecked()
        assert not display._play_timer.isActive()

    def test_fetch_start_end_stored_on_fetch(self, display):
        """_start_fetch stores the time range for slider bounds."""
        display._machine = Mock()
        now = datetime.now()
        display._start_dt.setDateTime(now - timedelta(hours=4))
        display._end_dt.setDateTime(now)

        with pytest.MonkeyPatch.context() as m:
            # patch with an instance, not the class, or Mock treats the
            # machine arg as a spec and errors
            m.setattr(
                "sc_linac_physics.displays.cavity_display.frontend.heatmap"
                ".fault_heatmap_display.FaultDataFetcher",
                Mock(),
            )
            display._start_fetch()

        assert display._fetch_start is not None
        assert display._fetch_end is not None
        diff = (display._fetch_end - display._fetch_start).total_seconds()
        assert abs(diff - 4 * 3600) < 5
