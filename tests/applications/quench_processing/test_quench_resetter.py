from time import time
from unittest.mock import patch, PropertyMock, MagicMock, Mock

import pytest
from lcls_tools.common.controls.pyepics.utils import PVInvalidError

from sc_linac_physics.applications.quench_processing.quench_cavity import (
    QuenchCavity,
)

# Import the module under test
from sc_linac_physics.applications.quench_processing.quench_resetter import (
    CavityResetStats,
    CavityResetTracker,
    _handle_quenched_cavity,
    _update_heartbeat,
    check_cavities,
    initialize_watcher_pv,
    load_cavities,
    _log_final_summary,
    RESET_COOLDOWN_SECONDS,
    MONITORING_CYCLE_SLEEP,
)
from sc_linac_physics.utils.sc_linac.linac_utils import (
    HW_MODE_ONLINE_VALUE,
    CavityFaultError,
    HW_MODE_OFFLINE_VALUE,
)


class TestCavityResetStats:
    """Tests for CavityResetStats dataclass."""

    def test_default_values(self):
        """Test that default values are set correctly."""
        stats = CavityResetStats()
        assert stats.total_resets == 0
        assert stats.total_real_quenches == 0
        assert stats.last_reset_time is None
        assert stats.last_check_was_quenched is False

    def test_custom_values(self):
        """Test initialization with custom values."""
        now = time()
        stats = CavityResetStats(
            total_resets=5,
            total_real_quenches=2,
            last_reset_time=now,
            last_check_was_quenched=True,
        )
        assert stats.total_resets == 5
        assert stats.total_real_quenches == 2
        assert stats.last_reset_time == now
        assert stats.last_check_was_quenched is True


class TestCavityResetTracker:
    """Tests for CavityResetTracker class."""

    @pytest.fixture
    def tracker(self):
        """Create a tracker with short cooldown for testing."""
        return CavityResetTracker(cooldown_seconds=2.0)

    @pytest.fixture
    def mock_cavity(self):
        """Create a mock QuenchCavity."""
        cavity = MagicMock(spec=QuenchCavity)
        cavity.__str__ = MagicMock(return_value="CM01_Cav1")
        return cavity

    def test_initialization(self, tracker):
        """Test tracker initialization."""
        assert tracker.cooldown_seconds == 2.0
        assert tracker.cavity_stats == {}

    def test_get_stats_creates_new_entry(self, tracker, mock_cavity):
        """Test that _get_stats creates a new stats entry."""
        stats = tracker._get_stats(mock_cavity)
        assert isinstance(stats, CavityResetStats)
        assert "CM01_Cav1" in tracker.cavity_stats

    def test_get_stats_returns_existing_entry(self, tracker, mock_cavity):
        """Test that _get_stats returns existing entry."""
        stats1 = tracker._get_stats(mock_cavity)
        stats1.total_resets = 5
        stats2 = tracker._get_stats(mock_cavity)
        assert stats1 is stats2
        assert stats2.total_resets == 5

    def test_can_reset_first_time(self, tracker, mock_cavity):
        """Test that cavity can be reset the first time."""
        can_reset, reason = tracker.can_reset(mock_cavity)
        assert can_reset is True
        assert reason == "ready"

    def test_can_reset_during_cooldown(self, tracker, mock_cavity):
        """Test that reset is blocked during cooldown."""
        tracker.record_fake_quench_reset(mock_cavity)
        can_reset, reason = tracker.can_reset(mock_cavity)
        assert can_reset is False
        assert "cooldown active" in reason
        assert "remaining" in reason

    @patch(
        "sc_linac_physics.applications.quench_processing.quench_resetter.time"
    )
    def test_can_reset_after_cooldown(self, mock_time, tracker, mock_cavity):
        """Test that reset is allowed after cooldown period."""
        # First reset at time 100
        mock_time.return_value = 100.0
        tracker.record_fake_quench_reset(mock_cavity)

        # Check during cooldown (101.5 seconds)
        mock_time.return_value = 101.5
        can_reset, reason = tracker.can_reset(mock_cavity)
        assert can_reset is False

        # Check after cooldown (103 seconds)
        mock_time.return_value = 103.0
        can_reset, reason = tracker.can_reset(mock_cavity)
        assert can_reset is True
        assert reason == "ready"

    @patch(
        "sc_linac_physics.applications.quench_processing.quench_resetter.time"
    )
    def test_record_fake_quench_reset(self, mock_time, tracker, mock_cavity):
        """Test recording a fake quench reset."""
        mock_time.return_value = 100.0
        tracker.record_fake_quench_reset(mock_cavity)

        stats = tracker._get_stats(mock_cavity)
        assert stats.total_resets == 1
        assert stats.last_reset_time == 100.0
        assert stats.total_real_quenches == 0
        # Don't check last_check_was_quenched - it's set by check_cavities, not here

    @patch(
        "sc_linac_physics.applications.quench_processing.quench_resetter.time"
    )
    def test_record_real_quench(self, mock_time, tracker, mock_cavity):
        """Test recording a real quench."""
        mock_time.return_value = 100.0
        tracker.record_real_quench(mock_cavity)

        stats = tracker._get_stats(mock_cavity)
        assert stats.total_resets == 0
        assert stats.total_real_quenches == 1
        assert stats.last_reset_time == 100.0  # Cooldown still applies
        assert stats.last_check_was_quenched is True

    def test_record_not_quenched(self, tracker, mock_cavity):
        """Test recording that a cavity is not quenched."""
        # First mark as quenched via record_real_quench (which does set the flag)
        tracker.record_real_quench(mock_cavity)
        stats = tracker._get_stats(mock_cavity)
        assert stats.last_check_was_quenched is True

        # Then mark as not quenched
        tracker.record_not_quenched(mock_cavity)
        assert stats.last_check_was_quenched is False

    @patch(
        "sc_linac_physics.applications.quench_processing.quench_resetter.time"
    )
    def test_record_multiple_operations(self, mock_time, tracker, mock_cavity):
        """Test recording multiple operations."""
        mock_time.return_value = 100.0
        tracker.record_fake_quench_reset(mock_cavity)

        mock_time.return_value = 105.0
        tracker.record_real_quench(mock_cavity)

        mock_time.return_value = 110.0
        tracker.record_fake_quench_reset(mock_cavity)

        stats = tracker._get_stats(mock_cavity)
        assert stats.total_resets == 2
        assert stats.total_real_quenches == 1
        assert stats.last_reset_time == 110.0

    def test_get_summary_empty(self, tracker):
        """Test summary when no resets have occurred."""
        summary = tracker.get_summary()
        assert summary == {}

    @patch(
        "sc_linac_physics.applications.quench_processing.quench_resetter.time"
    )
    def test_get_summary_with_operations(self, mock_time, tracker):
        """Test summary with multiple cavities."""
        cavity1 = MagicMock(spec=QuenchCavity)
        cavity1.__str__ = MagicMock(return_value="CM01_Cav1")
        cavity2 = MagicMock(spec=QuenchCavity)
        cavity2.__str__ = MagicMock(return_value="CM01_Cav2")

        mock_time.return_value = 100.0
        tracker.record_fake_quench_reset(cavity1)
        tracker.record_real_quench(cavity1)

        mock_time.return_value = 105.0
        tracker.record_fake_quench_reset(cavity2)
        tracker.record_not_quenched(cavity2)  # Cleared

        summary = tracker.get_summary()
        assert len(summary) == 2
        assert summary["CM01_Cav1"]["total_resets"] == 1
        assert summary["CM01_Cav1"]["total_real_quenches"] == 1
        assert summary["CM01_Cav1"]["currently_quenched"] is True
        assert summary["CM01_Cav2"]["total_resets"] == 1
        assert summary["CM01_Cav2"]["total_real_quenches"] == 0
        assert summary["CM01_Cav2"]["currently_quenched"] is False

    def test_get_summary_excludes_no_operations(self, tracker, mock_cavity):
        """Test that summary excludes cavities with no operations."""
        # Just get stats without recording anything
        tracker._get_stats(mock_cavity)
        summary = tracker.get_summary()
        assert summary == {}


class TestHandleQuenchedCavity:
    """Tests for _handle_quenched_cavity function."""

    @pytest.fixture
    def mock_cavity(self):
        """Create a mock QuenchCavity."""
        cavity = MagicMock(spec=QuenchCavity)
        cavity.__str__ = MagicMock(return_value="CM01_Cav1")
        cavity.validate_quench = MagicMock(return_value=False)  # Fake quench
        cavity._interlock_reset_pv_obj = None
        cavity.interlock_reset_pv = "TEST:RESET"
        return cavity

    @pytest.fixture
    def tracker(self):
        """Create a reset tracker."""
        return CavityResetTracker(cooldown_seconds=2.0)

    @pytest.fixture
    def counts(self):
        """Create counts dictionary."""
        return {
            "reset": 0,
            "skipped": 0,
            "error": 0,
            "checked": 0,
            "real_quench": 0,
        }

    @patch("sc_linac_physics.applications.quench_processing.quench_resetter.PV")
    def test_handle_fake_quench_reset(
        self, mock_pv_class, mock_cavity, tracker, counts
    ):
        """Test handling a fake quench with successful reset."""
        mock_pv = MagicMock()
        mock_pv_class.return_value = mock_pv
        mock_cavity.validate_quench.return_value = False  # Fake quench

        _handle_quenched_cavity(mock_cavity, tracker, counts)

        assert counts["reset"] == 1
        assert counts["real_quench"] == 0
        assert counts["skipped"] == 0
        mock_cavity.validate_quench.assert_called_once_with(
            wait_for_update=True
        )
        mock_pv.put.assert_called_once_with(1, wait=False)

    def test_handle_real_quench(self, mock_cavity, tracker, counts):
        """Test handling a real quench (no reset)."""
        mock_cavity.validate_quench.return_value = True  # Real quench

        _handle_quenched_cavity(mock_cavity, tracker, counts)

        assert counts["reset"] == 0
        assert counts["real_quench"] == 1
        assert counts["skipped"] == 0

    @patch(
        "sc_linac_physics.applications.quench_processing.quench_resetter.time"
    )
    def test_handle_quench_during_cooldown(
        self, mock_time, mock_cavity, tracker, counts
    ):
        """Test that cavity is skipped during cooldown."""
        # First reset
        mock_time.return_value = 100.0
        tracker.record_fake_quench_reset(mock_cavity)

        # Try again immediately
        mock_time.return_value = 100.5
        _handle_quenched_cavity(mock_cavity, tracker, counts)

        assert counts["reset"] == 0
        assert counts["skipped"] == 1
        assert counts["real_quench"] == 0
        mock_cavity.validate_quench.assert_not_called()


class TestUpdateHeartbeat:
    """Tests for _update_heartbeat function."""

    def test_update_heartbeat_success(self):
        """Test successful heartbeat update."""
        mock_pv = MagicMock()
        mock_pv.get.return_value = 5

        _update_heartbeat(mock_pv)

        mock_pv.get.assert_called_once()
        mock_pv.put.assert_called_once_with(6)

    def test_update_heartbeat_handles_exception(self):
        """Test that heartbeat errors are handled gracefully."""
        mock_pv = MagicMock()
        mock_pv.get.side_effect = Exception("PV error")

        # Should not raise
        _update_heartbeat(mock_pv)


class TestCheckCavities:
    """Tests for check_cavities function."""

    @pytest.fixture
    def mock_cavities(self):
        """Create list of mock cavities."""
        cavities = []
        for i in range(3):
            cavity = Mock()
            cavity.__str__ = Mock(return_value=f"CM01_Cav{i+1}")
            cavity.hw_mode = HW_MODE_ONLINE_VALUE
            cavity.turned_off = False
            cavity.is_quenched = False
            cavity.validate_quench = Mock(return_value=False)
            cavity._interlock_reset_pv_obj = None
            cavity.interlock_reset_pv = f"TEST:CAV{i+1}:RESET"
            cavities.append(cavity)
        return cavities

    @pytest.fixture
    def mock_pv(self):
        """Create mock PV."""
        pv = MagicMock()
        pv.get.return_value = 0
        return pv

    @pytest.fixture
    def tracker(self):
        """Create reset tracker."""
        return CavityResetTracker()

    def test_check_cavities_no_quench(self, mock_cavities, mock_pv, tracker):
        """Test checking cavities when none are quenched."""
        counts = check_cavities(mock_cavities, mock_pv, tracker)

        assert counts["checked"] == 3
        assert counts["reset"] == 0
        assert counts["real_quench"] == 0
        assert counts["skipped"] == 0
        assert counts["error"] == 0
        mock_pv.put.assert_called_once_with(1)

    @patch("sc_linac_physics.applications.quench_processing.quench_resetter.PV")
    def test_check_cavities_with_fake_quench(
        self, mock_pv_class, mock_cavities, mock_pv, tracker
    ):
        """Test checking cavities with one fake quench."""
        mock_reset_pv = MagicMock()
        mock_pv_class.return_value = mock_reset_pv

        type(mock_cavities[1]).is_quenched = PropertyMock(return_value=True)
        mock_cavities[1].validate_quench = MagicMock(
            return_value=False
        )  # Fake quench

        counts = check_cavities(mock_cavities, mock_pv, tracker)

        assert counts["checked"] == 3
        assert counts["reset"] == 1
        assert counts["real_quench"] == 0
        assert counts["skipped"] == 0
        assert counts["error"] == 0
        mock_reset_pv.put.assert_called_once_with(1, wait=False)

    def test_check_cavities_with_real_quench(
        self, mock_cavities, mock_pv, tracker
    ):
        """Test checking cavities with one real quench."""
        type(mock_cavities[1]).is_quenched = PropertyMock(return_value=True)
        mock_cavities[1].validate_quench = MagicMock(
            return_value=True
        )  # Real quench

        counts = check_cavities(mock_cavities, mock_pv, tracker)

        assert counts["checked"] == 3
        assert counts["reset"] == 0
        assert counts["real_quench"] == 1
        assert counts["skipped"] == 0
        assert counts["error"] == 0

    def test_check_cavities_skips_offline(
        self, mock_cavities, mock_pv, tracker
    ):
        """Test that offline cavities are skipped."""
        mock_cavities[0].hw_mode = HW_MODE_OFFLINE_VALUE

        counts = check_cavities(mock_cavities, mock_pv, tracker)

        # Only online cavities are checked
        assert counts["checked"] == 2
        assert counts["reset"] == 0

    def test_check_cavities_skips_turned_off(
        self, mock_cavities, mock_pv, tracker
    ):
        """Test that turned off cavities are skipped."""
        mock_cavities[0].turned_off = True

        counts = check_cavities(mock_cavities, mock_pv, tracker)

        assert counts["checked"] == 2
        assert counts["reset"] == 0

    def test_check_cavities_handles_cavity_fault_error(
        self, mock_cavities, mock_pv, tracker
    ):
        """Test handling of CavityFaultError."""
        type(mock_cavities[1]).is_quenched = PropertyMock(
            side_effect=CavityFaultError("Fault")
        )

        counts = check_cavities(mock_cavities, mock_pv, tracker)

        assert counts["checked"] == 3
        assert counts["error"] == 1

    def test_check_cavities_handles_pv_invalid_error(
        self, mock_cavities, mock_pv, tracker
    ):
        """Test handling of PVInvalidError."""
        type(mock_cavities[0]).is_quenched = PropertyMock(
            side_effect=PVInvalidError("Invalid PV")
        )

        counts = check_cavities(mock_cavities, mock_pv, tracker)

        assert counts["error"] == 1

    def test_check_cavities_handles_unexpected_exception(
        self, mock_cavities, mock_pv, tracker
    ):
        """Test handling of unexpected exceptions."""
        type(mock_cavities[1]).is_quenched = PropertyMock(
            side_effect=RuntimeError("Unexpected")
        )

        counts = check_cavities(mock_cavities, mock_pv, tracker)

        assert counts["error"] == 1

    def test_check_cavities_records_not_quenched(
        self, mock_cavities, mock_pv, tracker
    ):
        """Test that non-quenched cavities are recorded properly."""
        # First set one as quenched
        tracker.record_fake_quench_reset(mock_cavities[0])

        # Then check again (now not quenched)
        _ = check_cavities(mock_cavities, mock_pv, tracker)

        stats = tracker._get_stats(mock_cavities[0])
        assert stats.last_check_was_quenched is False

    @patch("sc_linac_physics.applications.quench_processing.quench_resetter.PV")
    @patch(
        "sc_linac_physics.applications.quench_processing.quench_resetter.time"
    )
    def test_check_cavities_respects_cooldown(
        self, mock_time, mock_pv_class, mock_cavities, mock_pv, tracker
    ):
        """Test that cooldown prevents repeated resets."""
        mock_reset_pv = MagicMock()
        mock_pv_class.return_value = mock_reset_pv

        type(mock_cavities[0]).is_quenched = PropertyMock(return_value=True)
        mock_cavities[0].validate_quench = MagicMock(return_value=False)

        # First check at time 100
        mock_time.return_value = 100.0
        counts1 = check_cavities(mock_cavities, mock_pv, tracker)
        assert counts1["reset"] == 1

        # Second check at time 101 (during cooldown)
        mock_time.return_value = 101.0
        counts2 = check_cavities(mock_cavities, mock_pv, tracker)
        assert counts2["reset"] == 0
        assert counts2["skipped"] == 1

        # Third check at time 104 (after cooldown)
        mock_time.return_value = 104.0
        counts3 = check_cavities(mock_cavities, mock_pv, tracker)
        assert counts3["reset"] == 1

    def test_check_cavities_heartbeat_failure_handled(
        self, mock_cavities, mock_pv, tracker
    ):
        """Test that heartbeat update failures are handled gracefully."""
        mock_pv.get.side_effect = Exception("Heartbeat error")

        counts = check_cavities(mock_cavities, mock_pv, tracker)

        # Should still return counts despite heartbeat error
        assert "checked" in counts


class TestInitializeWatcherPV:
    """Tests for initialize_watcher_pv function."""

    @patch("sc_linac_physics.applications.quench_processing.quench_resetter.PV")
    def test_initialize_watcher_pv_success(self, mock_pv_class):
        """Test successful PV initialization."""
        mock_pv = MagicMock()
        mock_pv_class.return_value = mock_pv

        result = initialize_watcher_pv()

        mock_pv_class.assert_called_once_with(
            "PHYS:SYS0:1:SC_CAV_QNCH_RESET_HEARTBEAT"
        )
        mock_pv.put.assert_called_once_with(0)
        assert result is mock_pv

    @patch("sc_linac_physics.applications.quench_processing.quench_resetter.PV")
    def test_initialize_watcher_pv_failure(self, mock_pv_class):
        """Test PV initialization failure."""
        mock_pv_class.side_effect = Exception("PV creation failed")

        with pytest.raises(Exception, match="PV creation failed"):
            initialize_watcher_pv()


class TestLoadCavities:
    """Tests for load_cavities function."""

    @patch(
        "sc_linac_physics.applications.quench_processing.quench_resetter.QUENCH_MACHINE"
    )
    def test_load_cavities_success(self, mock_machine):
        """Test successful cavity loading."""
        mock_cavities = [MagicMock(spec=QuenchCavity) for _ in range(5)]
        mock_machine.all_iterator = iter(mock_cavities)

        result = load_cavities()

        assert len(result) == 5
        assert result == mock_cavities

    @patch(
        "sc_linac_physics.applications.quench_processing.quench_resetter.QUENCH_MACHINE"
    )
    def test_load_cavities_failure(self, mock_machine):
        """Test cavity loading failure."""

        def failing_iterator():
            raise Exception("Load failed")
            yield

        mock_machine.all_iterator = failing_iterator()

        with pytest.raises(Exception, match="Load failed"):
            load_cavities()


class TestLogFinalSummary:
    """Tests for _log_final_summary function."""

    @patch(
        "sc_linac_physics.applications.quench_processing.quench_resetter.time"
    )
    def test_log_final_summary_with_cleared_cavities(self, mock_time):
        """Test logging summary with successfully cleared cavities."""
        tracker = CavityResetTracker()
        cavity = MagicMock(spec=QuenchCavity)
        cavity.__str__ = MagicMock(return_value="CM01_Cav1")

        mock_time.return_value = 100.0
        tracker.record_fake_quench_reset(cavity)
        tracker.record_not_quenched(cavity)  # Cleared

        # Should not raise
        _log_final_summary(tracker)

    @patch(
        "sc_linac_physics.applications.quench_processing.quench_resetter.time"
    )
    def test_log_final_summary_with_persistent_quenches(self, mock_time):
        """Test logging summary with persistent quenches."""
        tracker = CavityResetTracker()

        fake_cavity = MagicMock(spec=QuenchCavity)
        fake_cavity.__str__ = MagicMock(return_value="CM01_Cav1")

        real_cavity = MagicMock(spec=QuenchCavity)
        real_cavity.__str__ = MagicMock(return_value="CM01_Cav2")

        mock_time.return_value = 100.0
        tracker.record_fake_quench_reset(fake_cavity)  # Still quenched
        tracker.record_real_quench(real_cavity)  # Real quench

        # Should not raise
        _log_final_summary(tracker)

    @patch(
        "sc_linac_physics.applications.quench_processing.quench_resetter.time"
    )
    def test_log_final_summary_mixed_results(self, mock_time):
        """Test logging summary with mixed results."""
        tracker = CavityResetTracker()

        cleared = MagicMock(spec=QuenchCavity)
        cleared.__str__ = MagicMock(return_value="CM01_Cav1")

        persistent = MagicMock(spec=QuenchCavity)
        persistent.__str__ = MagicMock(return_value="CM01_Cav2")

        mock_time.return_value = 100.0
        tracker.record_fake_quench_reset(cleared)
        tracker.record_not_quenched(cleared)  # Successfully cleared

        tracker.record_real_quench(persistent)  # Still quenched

        # Should not raise
        _log_final_summary(tracker)

    def test_log_final_summary_no_resets(self):
        """Test logging summary with no resets."""
        tracker = CavityResetTracker()

        # Should not raise
        _log_final_summary(tracker)


class TestMain:
    """Tests for main function."""

    @patch(
        "sc_linac_physics.applications.quench_processing.quench_resetter.sleep"
    )
    @patch(
        "sc_linac_physics.applications.quench_processing.quench_resetter.load_cavities"
    )
    @patch(
        "sc_linac_physics.applications.quench_processing.quench_resetter.initialize_watcher_pv"
    )
    @patch(
        "sc_linac_physics.applications.quench_processing.quench_resetter.check_cavities"
    )
    def test_main_keyboard_interrupt(
        self,
        mock_check_cavities,
        mock_init_pv,
        mock_load_cavities,
        mock_sleep,
    ):
        """Test main loop with keyboard interrupt."""
        from sc_linac_physics.applications.quench_processing.quench_resetter import (
            main,
        )

        mock_pv = MagicMock()
        mock_init_pv.return_value = mock_pv
        mock_cavities = [MagicMock(spec=QuenchCavity)]
        mock_load_cavities.return_value = mock_cavities
        mock_check_cavities.return_value = {
            "reset": 0,
            "skipped": 0,
            "error": 0,
            "checked": 1,
            "real_quench": 0,
        }
        mock_sleep.side_effect = [None, KeyboardInterrupt()]

        # Should not raise
        main()

        assert mock_check_cavities.call_count == 2

    @patch(
        "sc_linac_physics.applications.quench_processing.quench_resetter.load_cavities"
    )
    @patch(
        "sc_linac_physics.applications.quench_processing.quench_resetter.initialize_watcher_pv"
    )
    def test_main_initialization_failure(
        self, mock_init_pv, mock_load_cavities
    ):
        """Test main with initialization failure."""
        from sc_linac_physics.applications.quench_processing.quench_resetter import (
            main,
        )

        mock_init_pv.side_effect = Exception("Init failed")

        with pytest.raises(Exception, match="Init failed"):
            main()

    @patch(
        "sc_linac_physics.applications.quench_processing.quench_resetter.sleep"
    )
    @patch(
        "sc_linac_physics.applications.quench_processing.quench_resetter.load_cavities"
    )
    @patch(
        "sc_linac_physics.applications.quench_processing.quench_resetter.initialize_watcher_pv"
    )
    @patch(
        "sc_linac_physics.applications.quench_processing.quench_resetter.check_cavities"
    )
    def test_main_continues_on_error(
        self,
        mock_check_cavities,
        mock_init_pv,
        mock_load_cavities,
        mock_sleep,
    ):
        """Test that main continues after check_cavities errors."""
        from sc_linac_physics.applications.quench_processing.quench_resetter import (
            main,
        )

        mock_pv = MagicMock()
        mock_init_pv.return_value = mock_pv
        mock_cavities = [MagicMock(spec=QuenchCavity)]
        mock_load_cavities.return_value = mock_cavities

        # check_cavities catches exceptions internally
        mock_check_cavities.return_value = {
            "reset": 0,
            "skipped": 0,
            "error": 1,
            "checked": 0,
            "real_quench": 0,
        }
        mock_sleep.side_effect = [None, KeyboardInterrupt()]

        # Should not raise
        main()

        assert mock_check_cavities.call_count == 2


class TestConstants:
    """Test module constants."""

    def test_reset_cooldown_seconds(self):
        """Test RESET_COOLDOWN_SECONDS constant."""
        assert RESET_COOLDOWN_SECONDS == 3.0

    def test_monitoring_cycle_sleep(self):
        """Test MONITORING_CYCLE_SLEEP constant."""
        assert MONITORING_CYCLE_SLEEP == 1.0
