import pytest

from sc_linac_physics.displays.cavity_display.frontend.heatmap.severity_filter import (
    SeverityFilter,
)


class TestSeverityFilterDefaults:
    def test_all_included_by_default(self):
        sf = SeverityFilter()
        assert sf.include_alarms is True
        assert sf.include_warnings is True
        assert sf.include_invalid is True

    def test_filtered_count_with_all_enabled(
        self, severity_filter, sample_fault_counter
    ):
        result = severity_filter.get_filtered_count(sample_fault_counter)
        assert result == 10 + 7 + 3


class TestSeverityFilterCombinations:
    """Test all 8 flag combinations via parametrize. Counter values: alarm=10, ok=500, invalid=3, warning=7."""

    @pytest.mark.parametrize(
        "alarms,warnings,invalid,expected",
        [
            (True, True, True, 20),  # 10 + 7 + 3
            (True, True, False, 17),  # 10 + 7
            (True, False, True, 13),  # 10 + 3
            (True, False, False, 10),  # 10
            (False, True, True, 10),  # 7 + 3
            (False, True, False, 7),  # 7
            (False, False, True, 3),  # 3
            (False, False, False, 0),  # none
        ],
    )
    def test_filter_combination(
        self, sample_fault_counter, alarms, warnings, invalid, expected
    ):
        sf = SeverityFilter(
            include_alarms=alarms,
            include_warnings=warnings,
            include_invalid=invalid,
        )
        assert sf.get_filtered_count(sample_fault_counter) == expected

    def test_ok_count_never_included(self, sample_fault_counter):
        """ok_count=500 must never be included regardless of filter state."""
        sf = SeverityFilter()
        result = sf.get_filtered_count(sample_fault_counter)
        # Must be 20 (alarm+warning+invalid),
        assert result == 20
        assert result != sample_fault_counter.ok_count + 20

    def test_zero_counter_returns_zero(
        self, severity_filter, zero_fault_counter
    ):
        assert severity_filter.get_filtered_count(zero_fault_counter) == 0


class TestSetFilter:
    def test_partial_update_one_flag(self, severity_filter):
        severity_filter.set_filter(include_alarms=False)
        assert severity_filter.include_alarms is False
        assert severity_filter.include_warnings is True
        assert severity_filter.include_invalid is True

    def test_none_args_no_change(self, severity_filter):
        severity_filter.set_filter()
        assert severity_filter.include_alarms is True
        assert severity_filter.include_warnings is True
        assert severity_filter.include_invalid is True

    def test_set_filter_updates_count(
        self, severity_filter, sample_fault_counter
    ):
        severity_filter.set_filter(include_warnings=False)
        assert (
            severity_filter.get_filtered_count(sample_fault_counter) == 10 + 3
        )

    def test_set_filter_multiple_flags_at_once(self, severity_filter):
        severity_filter.set_filter(include_alarms=False, include_warnings=False)
        assert severity_filter.include_alarms is False
        assert severity_filter.include_warnings is False
        assert severity_filter.include_invalid is True

    def test_set_filter_toggle_round_trip(
        self, severity_filter, sample_fault_counter
    ):
        original_count = severity_filter.get_filtered_count(
            sample_fault_counter
        )

        severity_filter.set_filter(include_alarms=False)
        reduced_count = severity_filter.get_filtered_count(sample_fault_counter)
        assert reduced_count < original_count

        severity_filter.set_filter(include_alarms=True)
        restored_count = severity_filter.get_filtered_count(
            sample_fault_counter
        )
        assert restored_count == original_count
