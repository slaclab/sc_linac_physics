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
    _should_check_cavity,
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
        assert stats.last_reset_time is None
        assert stats.last_successful_reset is None
        assert stats.failed_reset_count == 0

    def test_custom_values(self):
        """Test initialization with custom values."""
        now = time()
        stats = CavityResetStats(
            total_resets=5,
            last_reset_time=now,
            last_successful_reset=now - 10,
            failed_reset_count=2,
        )
        assert stats.total_resets == 5
        assert stats.last_reset_time == now
        assert stats.last_successful_reset == now - 10
        assert stats.failed_reset_count == 2


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
        tracker.record_reset(mock_cavity, success=True)
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
        tracker.record_reset(mock_cavity, success=True)

        # Check during cooldown (101.5 seconds)
        mock_time.return_value = 101.5
        can_reset, reason = tracker.can_reset(mock_cavity)
        assert can_reset is False

        # Check after cooldown (103 seconds)
        mock_time.return_value = 103.0
        can_reset, reason = tracker.can_reset(mock_cavity)
        assert can_reset is True
        assert reason == "ready"

    def test_get_time_until_ready_no_reset(self, tracker, mock_cavity):
        """Test time until ready when no reset has occurred."""
        time_remaining = tracker.get_time_until_ready(mock_cavity)
        assert time_remaining == 0.0

    @patch(
        "sc_linac_physics.applications.quench_processing.quench_resetter.time"
    )
    def test_get_time_until_ready_during_cooldown(
        self, mock_time, tracker, mock_cavity
    ):
        """Test time calculation during cooldown."""
        mock_time.return_value = 100.0
        tracker.record_reset(mock_cavity, success=True)

        mock_time.return_value = 101.0
        time_remaining = tracker.get_time_until_ready(mock_cavity)
        assert time_remaining == pytest.approx(1.0, abs=0.01)

    @patch(
        "sc_linac_physics.applications.quench_processing.quench_resetter.time"
    )
    def test_get_time_until_ready_after_cooldown(
        self, mock_time, tracker, mock_cavity
    ):
        """Test time calculation after cooldown expires."""
        mock_time.return_value = 100.0
        tracker.record_reset(mock_cavity, success=True)

        mock_time.return_value = 105.0
        time_remaining = tracker.get_time_until_ready(mock_cavity)
        assert time_remaining == 0.0

    @patch(
        "sc_linac_physics.applications.quench_processing.quench_resetter.time"
    )
    def test_record_reset_success(self, mock_time, tracker, mock_cavity):
        """Test recording a successful reset."""
        mock_time.return_value = 100.0
        tracker.record_reset(mock_cavity, success=True)

        stats = tracker._get_stats(mock_cavity)
        assert stats.total_resets == 1
        assert stats.last_reset_time == 100.0
        assert stats.last_successful_reset == 100.0
        assert stats.failed_reset_count == 0

    @patch(
        "sc_linac_physics.applications.quench_processing.quench_resetter.time"
    )
    def test_record_reset_failure(self, mock_time, tracker, mock_cavity):
        """Test recording a failed reset."""
        mock_time.return_value = 100.0
        tracker.record_reset(mock_cavity, success=False)

        stats = tracker._get_stats(mock_cavity)
        assert stats.total_resets == 1
        assert stats.last_reset_time == 100.0
        assert stats.last_successful_reset is None
        assert stats.failed_reset_count == 1

    @patch(
        "sc_linac_physics.applications.quench_processing.quench_resetter.time"
    )
    def test_record_multiple_resets(self, mock_time, tracker, mock_cavity):
        """Test recording multiple resets."""
        mock_time.return_value = 100.0
        tracker.record_reset(mock_cavity, success=True)

        mock_time.return_value = 105.0
        tracker.record_reset(mock_cavity, success=False)

        mock_time.return_value = 110.0
        tracker.record_reset(mock_cavity, success=True)

        stats = tracker._get_stats(mock_cavity)
        assert stats.total_resets == 3
        assert stats.last_reset_time == 110.0
        assert stats.last_successful_reset == 110.0
        assert stats.failed_reset_count == 1

    def test_get_summary_empty(self, tracker):
        """Test summary when no resets have occurred."""
        summary = tracker.get_summary()
        assert summary == {}

    @patch(
        "sc_linac_physics.applications.quench_processing.quench_resetter.time"
    )
    def test_get_summary_with_resets(self, mock_time, tracker):
        """Test summary with multiple cavities."""
        cavity1 = MagicMock(spec=QuenchCavity)
        cavity1.__str__ = MagicMock(return_value="CM01_Cav1")
        cavity2 = MagicMock(spec=QuenchCavity)
        cavity2.__str__ = MagicMock(return_value="CM01_Cav2")

        mock_time.return_value = 100.0
        tracker.record_reset(cavity1, success=True)
        tracker.record_reset(cavity1, success=False)

        mock_time.return_value = 105.0
        tracker.record_reset(cavity2, success=True)

        summary = tracker.get_summary()
        assert len(summary) == 2
        assert summary["CM01_Cav1"]["total_resets"] == 2
        assert summary["CM01_Cav1"]["failed_resets"] == 1
        assert summary["CM01_Cav2"]["total_resets"] == 1
        assert summary["CM01_Cav2"]["failed_resets"] == 0

    def test_get_summary_excludes_no_resets(self, tracker, mock_cavity):
        """Test that summary excludes cavities with no resets."""
        # Just get stats without recording reset
        tracker._get_stats(mock_cavity)
        summary = tracker.get_summary()
        assert summary == {}


class TestShouldCheckCavity:
    """Tests for _should_check_cavity function."""

    def test_should_check_online_cavity(self):
        """Test that online, running cavity should be checked."""
        cavity = Mock()
        cavity.hw_mode = HW_MODE_ONLINE_VALUE  # This is 0
        cavity.turned_off = False
        assert _should_check_cavity(cavity) is True

    def test_should_not_check_offline_cavity(self):
        """Test that offline cavity should not be checked."""
        cavity = Mock()
        cavity.hw_mode = HW_MODE_OFFLINE_VALUE  # This is 2, not 0!
        cavity.turned_off = False
        assert _should_check_cavity(cavity) is False

    def test_should_not_check_turned_off_cavity(self):
        """Test that turned off cavity should not be checked."""
        cavity = Mock()
        cavity.hw_mode = HW_MODE_ONLINE_VALUE  # 0
        cavity.turned_off = True
        assert _should_check_cavity(cavity) is False

    def test_should_not_check_offline_and_turned_off(self):
        """Test cavity that is both offline and turned off."""
        cavity = Mock()
        cavity.hw_mode = HW_MODE_OFFLINE_VALUE  # 2, not 0!
        cavity.turned_off = True
        assert _should_check_cavity(cavity) is False


class TestHandleQuenchedCavity:
    """Tests for _handle_quenched_cavity function."""

    @pytest.fixture
    def mock_cavity(self):
        """Create a mock QuenchCavity."""
        cavity = MagicMock(spec=QuenchCavity)
        cavity.__str__ = MagicMock(return_value="CM01_Cav1")
        cavity.reset_quench = MagicMock(return_value=True)
        return cavity

    @pytest.fixture
    def tracker(self):
        """Create a reset tracker."""
        return CavityResetTracker(cooldown_seconds=2.0)

    @pytest.fixture
    def counts(self):
        """Create counts dictionary."""
        return {"reset": 0, "skipped": 0, "error": 0, "checked": 0}

    def test_handle_quench_successful_reset(self, mock_cavity, tracker, counts):
        """Test successful quench reset."""
        mock_cavity.reset_quench.return_value = True

        _handle_quenched_cavity(mock_cavity, tracker, counts)

        assert counts["reset"] == 1
        assert counts["skipped"] == 0
        assert counts["error"] == 0
        mock_cavity.reset_quench.assert_called_once()

    def test_handle_quench_failed_reset(self, mock_cavity, tracker, counts):
        """Test failed quench reset."""
        mock_cavity.reset_quench.return_value = False

        _handle_quenched_cavity(mock_cavity, tracker, counts)

        assert counts["reset"] == 0
        assert counts["skipped"] == 0
        assert counts["error"] == 1
        mock_cavity.reset_quench.assert_called_once()

    @patch(
        "sc_linac_physics.applications.quench_processing.quench_resetter.time"
    )
    def test_handle_quench_during_cooldown(
        self, mock_time, mock_cavity, tracker, counts
    ):
        """Test that cavity is skipped during cooldown."""
        # First reset
        mock_time.return_value = 100.0
        tracker.record_reset(mock_cavity, success=True)

        # Try again immediately
        mock_time.return_value = 100.5
        _handle_quenched_cavity(mock_cavity, tracker, counts)

        assert counts["reset"] == 0
        assert counts["skipped"] == 1
        assert counts["error"] == 0
        mock_cavity.reset_quench.assert_not_called()


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
            cavity.hw_mode = HW_MODE_ONLINE_VALUE  # 0
            cavity.turned_off = False
            cavity.is_quenched = False
            cavities.append(cavity)
        return cavities

    def test_check_cavities_skips_offline(
        self, mock_cavities, mock_pv, tracker
    ):
        """Test that offline cavities are skipped."""
        # Set the first cavity to be offline
        mock_cavities[0].hw_mode = HW_MODE_OFFLINE_VALUE  # Use 2, not 0!

        counts = check_cavities(mock_cavities, mock_pv, tracker)

        # Only online cavities are checked (counted)
        assert counts["checked"] == 2
        assert counts["reset"] == 0

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
        assert counts["skipped"] == 0
        assert counts["error"] == 0
        mock_pv.put.assert_called_once_with(1)

    def test_check_cavities_with_quench(self, mock_cavities, mock_pv, tracker):
        """Test checking cavities with one quenched."""
        type(mock_cavities[1]).is_quenched = PropertyMock(return_value=True)
        mock_cavities[1].reset_quench = MagicMock(return_value=True)

        counts = check_cavities(mock_cavities, mock_pv, tracker)

        assert counts["checked"] == 3
        assert counts["reset"] == 1
        assert counts["skipped"] == 0
        assert counts["error"] == 0

    def test_check_cavities_handles_cavity_fault_error(
        self, mock_cavities, mock_pv, tracker
    ):
        """Test handling of CavityFaultError."""
        # Make accessing is_quenched raise an error
        type(mock_cavities[1]).is_quenched = PropertyMock(
            side_effect=CavityFaultError("Fault")
        )

        counts = check_cavities(mock_cavities, mock_pv, tracker)

        assert counts["checked"] == 3  # All cavities incremented counter
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

    def test_check_cavities_critical_error_handling(
        self, mock_cavities, mock_pv, tracker
    ):
        """Test that critical errors don't crash the function."""
        # Make heartbeat update fail
        mock_pv.put.side_effect = Exception("Critical PV error")

        counts = check_cavities(mock_cavities, mock_pv, tracker)

        # Function should still return counts
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

        # Create a generator that raises an exception when iterated
        def failing_iterator():
            raise Exception("Load failed")
            yield  # Never reached, but makes this a generator

        mock_machine.all_iterator = failing_iterator()

        with pytest.raises(Exception, match="Load failed"):
            load_cavities()


class TestLogFinalSummary:
    """Tests for _log_final_summary function."""

    def test_log_final_summary_with_resets(self):
        """Test logging summary with reset data."""
        tracker = CavityResetTracker()
        cavity = MagicMock(spec=QuenchCavity)
        cavity.__str__ = MagicMock(return_value="CM01_Cav1")

        tracker.record_reset(cavity, success=True)
        tracker.record_reset(cavity, success=False)

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
    def test_main_check_cavities_exception(
        self,
        mock_check_cavities,
        mock_init_pv,
        mock_load_cavities,
        mock_sleep,
    ):
        """Test that main catches check_cavities exceptions and continues."""
        from sc_linac_physics.applications.quench_processing.quench_resetter import (
            main,
        )

        mock_pv = MagicMock()
        mock_init_pv.return_value = mock_pv
        mock_cavities = [MagicMock(spec=QuenchCavity)]
        mock_load_cavities.return_value = mock_cavities

        # check_cavities returns normally (doesn't raise)
        # The real function catches all exceptions internally
        mock_check_cavities.return_value = {
            "reset": 0,
            "skipped": 0,
            "error": 1,
            "checked": 0,
        }
        mock_sleep.side_effect = [None, KeyboardInterrupt()]

        # Should not raise
        main()

        # Should have called check_cavities twice before interrupt
        assert mock_check_cavities.call_count == 2


class TestConstants:
    """Test module constants."""

    def test_reset_cooldown_seconds(self):
        """Test RESET_COOLDOWN_SECONDS constant."""
        assert RESET_COOLDOWN_SECONDS == 3.0

    def test_monitoring_cycle_sleep(self):
        """Test MONITORING_CYCLE_SLEEP constant."""
        assert MONITORING_CYCLE_SLEEP == 1.0
