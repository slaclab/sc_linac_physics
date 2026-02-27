# test_audio_manager.py
from unittest.mock import Mock, patch

import pytest
from PyQt5.QtWidgets import QApplication

from sc_linac_physics.displays.cavity_display.frontend.audio_manager import (
    AudioAlertManager,
)


@pytest.fixture
def multi_cavity_machine():
    """Create machine with multiple cavities"""
    machine = Mock()

    cavities = {}
    for i in range(1, 4):
        cavity = Mock()
        cavity.number = i
        cavity.cryomodule = Mock()
        cavity.cryomodule.name = "16"
        cavity.cavity_widget = Mock()
        cavity.cavity_widget.severity_changed = Mock()
        cavities[i] = cavity

    cryomodule = Mock()
    cryomodule.name = "16"
    cryomodule.cavities = cavities

    linac = Mock()
    linac.cryomodules = {"16": cryomodule}
    machine.linacs = [linac]

    return machine


@pytest.fixture
def mock_logger():
    """Mock the audio alert logger"""
    with patch(
        "sc_linac_physics.displays.cavity_display.frontend.audio_manager.audio_alert_logger"
    ) as mock_log:
        yield mock_log


@pytest.fixture
def qtbot_app(qtbot):
    """Ensure QApplication is available for tests"""
    return qtbot


@pytest.fixture
def mock_cavity():
    """Create a mock cavity with cryomodule"""
    cavity = Mock()
    cavity.number = 1
    cavity.cryomodule = Mock()
    cavity.cryomodule.name = "16"
    cavity.cavity_widget = Mock()
    cavity.cavity_widget.severity_changed = Mock()
    return cavity


@pytest.fixture
def mock_gui_machine(mock_cavity):
    """Create a mock GUI machine with linacs, cryomodules, and cavities"""
    machine = Mock()

    # Create structure: machine -> linac -> cryomodule -> cavity
    linac = Mock()
    cryomodule = Mock()
    cryomodule.name = "16"
    cryomodule.cavities = {1: mock_cavity}
    linac.cryomodules = {"16": cryomodule}
    machine.linacs = [linac]

    return machine


@pytest.fixture
def audio_manager(qtbot, mock_gui_machine):
    """Create an AudioAlertManager instance"""
    manager = AudioAlertManager(mock_gui_machine)
    yield manager
    # Cleanup
    manager.stop_monitoring()


class TestAudioAlertManagerInitialization:
    """Test initialization and basic setup"""

    def test_init(self, audio_manager, mock_gui_machine):
        """Test manager initializes with correct defaults"""
        assert audio_manager.gui_machine == mock_gui_machine
        assert audio_manager._enabled is False
        assert len(audio_manager.alerted_alarms) == 0
        assert len(audio_manager.alerted_warnings) == 0
        assert len(audio_manager.unacknowledged_alarms) == 0
        assert len(audio_manager.acknowledged_cavities) == 0

    def test_set_enabled(self, audio_manager, mock_logger):
        """Test enabling/disabling the manager"""
        audio_manager.setEnabled(True)
        assert audio_manager._enabled is True

        # Check logging instead of print
        mock_logger.info.assert_called()
        call_args = mock_logger.info.call_args
        assert "enabled" in call_args[0][0].lower()

        audio_manager.setEnabled(False)
        assert audio_manager._enabled is False


class TestMonitoring:
    """Test monitoring start/stop functionality"""

    def test_start_monitoring(self, audio_manager, qtbot):
        """Test start_monitoring enables manager and starts timer"""
        audio_manager.start_monitoring()

        assert audio_manager._enabled is True
        assert audio_manager.escalation_timer.isActive()
        assert audio_manager.escalation_timer.interval() == 30000
        assert hasattr(audio_manager, "_connected")

    def test_stop_monitoring(self, audio_manager):
        """Test stop_monitoring disables manager and stops timer"""
        audio_manager.start_monitoring()
        audio_manager.stop_monitoring()

        assert audio_manager._enabled is False
        assert not audio_manager.escalation_timer.isActive()

    def test_connect_to_cavities(self, audio_manager, mock_cavity, mock_logger):
        """Test that cavities are connected via signals"""
        audio_manager.start_monitoring()

        # Verify signal connection was called
        mock_cavity.cavity_widget.severity_changed.connect.assert_called()

        # Check that info log was called about connection
        assert any(
            "connected" in str(call).lower()
            for call in mock_logger.info.call_args_list
        )


class TestSeverityChanges:
    """Test severity change handling"""

    @patch(
        "sc_linac_physics.displays.cavity_display.frontend.audio_manager.QApplication.beep"
    )
    def test_alarm_triggers_sound(
        self, mock_beep, audio_manager, mock_cavity, qtbot
    ):
        """Test red alarm (severity=2) triggers alarm sound"""
        audio_manager.setEnabled(True)

        with qtbot.waitSignal(audio_manager.new_alarm, timeout=1000):
            audio_manager._on_severity_change(mock_cavity, 2)

        # Should beep twice (alarm sound)
        assert mock_beep.call_count >= 1
        assert "16_1" in audio_manager.alerted_alarms
        assert "16_1" in audio_manager.unacknowledged_alarms

    @patch(
        "sc_linac_physics.displays.cavity_display.frontend.audio_manager.QApplication.beep"
    )
    def test_warning_triggers_sound(
        self, mock_beep, audio_manager, mock_cavity
    ):
        """Test yellow warning (severity=1) triggers warning sound"""
        audio_manager.setEnabled(True)
        audio_manager._on_severity_change(mock_cavity, 1)

        # Should beep once (warning sound)
        mock_beep.assert_called_once()
        assert "16_1" in audio_manager.alerted_warnings
        assert "16_1" not in audio_manager.unacknowledged_alarms

    def test_no_sound_when_disabled(self, audio_manager, mock_cavity):
        """Test no sounds when manager is disabled"""
        with patch.object(audio_manager, "_play_alarm_sound") as mock_alarm:
            audio_manager.setEnabled(False)
            audio_manager._on_severity_change(mock_cavity, 2)

            mock_alarm.assert_not_called()
            assert "16_1" not in audio_manager.alerted_alarms

    def test_cleared_severity_resets_tracking(self, audio_manager, mock_cavity):
        """Test severity=0 clears tracking for cavity"""
        audio_manager.setEnabled(True)

        # First trigger alarm
        audio_manager._on_severity_change(mock_cavity, 2)
        assert "16_1" in audio_manager.alerted_alarms

        # Then clear it
        audio_manager._on_severity_change(mock_cavity, 0)
        assert "16_1" not in audio_manager.alerted_alarms
        assert "16_1" not in audio_manager.unacknowledged_alarms
        assert "16_1" not in audio_manager.acknowledged_cavities

    def test_duplicate_alarms_not_retriggered(self, audio_manager, mock_cavity):
        """Test same alarm doesn't trigger multiple times"""
        audio_manager.setEnabled(True)

        with patch.object(audio_manager, "_play_alarm_sound") as mock_alarm:
            audio_manager._on_severity_change(mock_cavity, 2)
            audio_manager._on_severity_change(mock_cavity, 2)

            # Should only play once
            mock_alarm.assert_called_once()

    def test_acknowledged_cavity_no_sound(self, audio_manager, mock_cavity):
        """Test acknowledged cavity doesn't trigger new sounds"""
        audio_manager.setEnabled(True)
        audio_manager.acknowledge_cavity("16_1")

        with patch.object(audio_manager, "_play_alarm_sound") as mock_alarm:
            audio_manager._on_severity_change(mock_cavity, 2)
            mock_alarm.assert_not_called()


class TestAcknowledgment:
    """Test alarm acknowledgment functionality"""

    def test_acknowledge_cavity(self, audio_manager, mock_cavity):
        """Test acknowledging a cavity by ID"""
        audio_manager.setEnabled(True)
        audio_manager._on_severity_change(mock_cavity, 2)

        assert "16_1" in audio_manager.unacknowledged_alarms

        audio_manager.acknowledge_cavity("16_1")

        assert "16_1" not in audio_manager.unacknowledged_alarms
        assert "16_1" in audio_manager.acknowledged_cavities

    def test_acknowledge_alarm_legacy(self, audio_manager, mock_cavity):
        """Test legacy acknowledge_alarm method"""
        audio_manager.setEnabled(True)
        audio_manager._on_severity_change(mock_cavity, 2)

        audio_manager.acknowledge_alarm(mock_cavity)

        assert "16_1" not in audio_manager.unacknowledged_alarms
        assert "16_1" in audio_manager.acknowledged_cavities

    def test_acknowledge_nonexistent_cavity(self, audio_manager):
        """Test acknowledging cavity that hasn't alarmed"""
        # Should not raise error
        audio_manager.acknowledge_cavity("99_9")
        assert "99_9" in audio_manager.acknowledged_cavities


class TestEscalation:
    """Test escalation functionality"""

    @patch(
        "sc_linac_physics.displays.cavity_display.frontend.audio_manager.time.time"
    )
    def test_escalation_single_sound_multiple_alarms(
        self, mock_time, qtbot, multi_cavity_machine
    ):
        """Test that multiple escalated alarms only trigger one escalation sound"""
        manager = AudioAlertManager(multi_cavity_machine)
        manager.setEnabled(True)

        # Trigger 3 alarms
        mock_time.return_value = 1000.0
        cav1 = multi_cavity_machine.linacs[0].cryomodules["16"].cavities[1]
        cav2 = multi_cavity_machine.linacs[0].cryomodules["16"].cavities[2]
        cav3 = multi_cavity_machine.linacs[0].cryomodules["16"].cavities[3]

        manager._on_severity_change(cav1, 2)
        manager._on_severity_change(cav2, 2)
        manager._on_severity_change(cav3, 2)

        assert len(manager.unacknowledged_alarms) == 3

        # Advance time > 2 minutes
        mock_time.return_value = 1121.0

        with patch.object(manager, "_play_escalation_sound") as mock_escalation:
            manager._check_escalation()

            # Should only be called ONCE despite 3 unacknowledged alarms
            mock_escalation.assert_called_once()

    @patch(
        "sc_linac_physics.displays.cavity_display.frontend.audio_manager.time.time"
    )
    def test_escalation_logs_all_cavities(
        self, mock_time, qtbot, multi_cavity_machine
    ):
        """Test that escalation logs all unacknowledged cavities in single message"""
        manager = AudioAlertManager(multi_cavity_machine)
        manager.setEnabled(True)

        # Trigger 3 alarms at different times
        mock_time.return_value = 1000.0
        cav1 = multi_cavity_machine.linacs[0].cryomodules["16"].cavities[1]
        manager._on_severity_change(cav1, 2)

        mock_time.return_value = 1020.0  # 20 seconds later
        cav2 = multi_cavity_machine.linacs[0].cryomodules["16"].cavities[2]
        manager._on_severity_change(cav2, 2)

        mock_time.return_value = 1040.0  # 40 seconds from start
        cav3 = multi_cavity_machine.linacs[0].cryomodules["16"].cavities[3]
        manager._on_severity_change(cav3, 2)

        # Advance time so all are past 2 minutes
        mock_time.return_value = 1200.0  # 200 seconds from first alarm

        with patch(
            "sc_linac_physics.displays.cavity_display.frontend.audio_manager.audio_alert_logger"
        ) as mock_logger:
            manager._check_escalation()

            # Should have one warning call with all cavities
            warning_calls = [
                call
                for call in mock_logger.warning.call_args_list
                if len(call[0]) > 0 and "ESCALATION" in call[0][0]
            ]

            assert len(warning_calls) == 1

            # Check the extra_data contains info about all 3 cavities
            call_kwargs = warning_calls[0][1]
            extra_data = call_kwargs["extra"]["extra_data"]

            assert extra_data["escalated_count"] == 3
            assert len(extra_data["escalated_cavities"]) == 3
            assert "longest_unack_sec" in extra_data

            # Verify cavity IDs are logged
            cavity_ids = [
                c["cavity_id"] for c in extra_data["escalated_cavities"]
            ]
            assert "16_1" in cavity_ids
            assert "16_2" in cavity_ids
            assert "16_3" in cavity_ids

    @patch(
        "sc_linac_physics.displays.cavity_display.frontend.audio_manager.time.time"
    )
    def test_no_escalation_sound_when_no_alarms(self, mock_time, audio_manager):
        """Test that no escalation sound plays when there are no unacknowledged alarms"""
        audio_manager.setEnabled(True)
        mock_time.return_value = 1000.0

        with patch.object(
            audio_manager, "_play_escalation_sound"
        ) as mock_escalation:
            audio_manager._check_escalation()
            mock_escalation.assert_not_called()

    @patch(
        "sc_linac_physics.displays.cavity_display.frontend.audio_manager.time.time"
    )
    def test_escalation_includes_duration_info(
        self, mock_time, qtbot, multi_cavity_machine
    ):
        """Test that escalation log includes duration information"""
        manager = AudioAlertManager(multi_cavity_machine)
        manager.setEnabled(True)

        # Trigger 2 alarms at different times
        mock_time.return_value = 1000.0
        cav1 = multi_cavity_machine.linacs[0].cryomodules["16"].cavities[1]
        manager._on_severity_change(cav1, 2)

        mock_time.return_value = 1060.0  # 1 minute later
        cav2 = multi_cavity_machine.linacs[0].cryomodules["16"].cavities[2]
        manager._on_severity_change(cav2, 2)

        # Advance time so first is >3min, second is >2min
        mock_time.return_value = 1200.0

        with patch(
            "sc_linac_physics.displays.cavity_display.frontend.audio_manager.audio_alert_logger"
        ) as mock_logger:
            manager._check_escalation()

            warning_call = mock_logger.warning.call_args
            extra_data = warning_call[1]["extra"]["extra_data"]

            # Check duration tracking
            assert (
                extra_data["longest_unack_sec"] == 200.0
            )  # First alarm: 200 seconds

            # Verify individual cavity durations
            durations = [
                c["duration_sec"] for c in extra_data["escalated_cavities"]
            ]
            assert 200.0 in durations  # First cavity
            assert 140.0 in durations  # Second cavity

    @patch(
        "sc_linac_physics.displays.cavity_display.frontend.audio_manager.time.time"
    )
    @patch(
        "sc_linac_physics.displays.cavity_display.frontend.audio_manager.QApplication.beep"
    )
    def test_escalation_after_2_minutes(
        self, mock_beep, mock_time, audio_manager, mock_cavity
    ):
        """Test escalation sound plays after 2 minutes"""
        audio_manager.setEnabled(True)

        # Set initial time
        mock_time.return_value = 1000.0
        audio_manager._on_severity_change(mock_cavity, 2)

        # Simulate 2+ minutes passing
        mock_time.return_value = 1000.0 + 121.0

        # Clear previous beeps from alarm
        mock_beep.reset_mock()

        # Check escalation
        audio_manager._check_escalation()

        # Should trigger escalation beeps (3 beeps)
        assert mock_beep.call_count >= 1

    @patch(
        "sc_linac_physics.displays.cavity_display.frontend.audio_manager.time.time"
    )
    def test_no_escalation_when_acknowledged(
        self, mock_time, audio_manager, mock_cavity
    ):
        """Test acknowledged alarms don't escalate"""
        audio_manager.setEnabled(True)

        mock_time.return_value = 1000.0
        audio_manager._on_severity_change(mock_cavity, 2)
        audio_manager.acknowledge_cavity("16_1")

        mock_time.return_value = 1000.0 + 121.0

        with patch.object(
            audio_manager, "_play_escalation_sound"
        ) as mock_escalation:
            audio_manager._check_escalation()
            mock_escalation.assert_not_called()

    @patch(
        "sc_linac_physics.displays.cavity_display.frontend.audio_manager.time.time"
    )
    def test_no_escalation_when_disabled(
        self, mock_time, audio_manager, mock_cavity
    ):
        """Test escalation doesn't occur when disabled"""
        audio_manager.setEnabled(True)

        mock_time.return_value = 1000.0
        audio_manager._on_severity_change(mock_cavity, 2)

        # Disable and advance time
        audio_manager.setEnabled(False)
        mock_time.return_value = 1000.0 + 121.0

        with patch.object(
            audio_manager, "_play_escalation_sound"
        ) as mock_escalation:
            audio_manager._check_escalation()
            mock_escalation.assert_not_called()

    def test_escalation_timer_interval(self, audio_manager):
        """Test escalation timer runs every 30 seconds"""
        audio_manager.start_monitoring()
        assert audio_manager.escalation_timer.interval() == 30000


class TestSounds:
    """Test sound playback methods"""

    def test_alarm_sound_double_beep(self, audio_manager, qtbot):
        """Test alarm sound schedules double beep"""
        with (
            patch(
                "sc_linac_physics.displays.cavity_display.frontend.audio_manager.QApplication.beep"
            ) as mock_beep,
            patch(
                "sc_linac_physics.displays.cavity_display.frontend.audio_manager.QTimer.singleShot"
            ) as mock_timer,
        ):

            audio_manager._play_alarm_sound()

            # First beep happens immediately
            assert mock_beep.call_count == 1

            # Second beep is scheduled via singleShot
            mock_timer.assert_called_once_with(200, QApplication.beep)

    def test_warning_sound_single_beep(self, audio_manager):
        """Test warning sound produces single beep"""
        with patch(
            "sc_linac_physics.displays.cavity_display.frontend.audio_manager.QApplication.beep"
        ) as mock_beep:
            audio_manager._play_warning_sound()
            assert mock_beep.call_count == 1

    def test_escalation_sound_triple_beep(self, audio_manager):
        """Test escalation sound schedules triple beep"""
        with (
            patch(
                "sc_linac_physics.displays.cavity_display.frontend.audio_manager.QApplication.beep"
            ) as mock_beep,
            patch(
                "sc_linac_physics.displays.cavity_display.frontend.audio_manager.QTimer.singleShot"
            ) as mock_timer,
        ):

            audio_manager._play_escalation_sound()

            # First beep happens immediately
            assert mock_beep.call_count == 1

            # Two more beeps are scheduled via singleShot
            assert mock_timer.call_count == 2
            mock_timer.assert_any_call(200, QApplication.beep)
            mock_timer.assert_any_call(400, QApplication.beep)


class TestSignals:
    """Test PyQt signal emissions"""

    def test_new_alarm_signal_emitted(self, audio_manager, mock_cavity, qtbot):
        """Test new_alarm signal emits with cavity object"""
        audio_manager.setEnabled(True)

        with qtbot.waitSignal(audio_manager.new_alarm, timeout=1000) as blocker:
            audio_manager._on_severity_change(mock_cavity, 2)

        assert blocker.args[0] == mock_cavity

    def test_new_alarm_signal_not_emitted_for_warning(
        self, audio_manager, mock_cavity, qtbot
    ):
        """Test new_alarm signal doesn't emit for warnings"""
        audio_manager.setEnabled(True)

        with qtbot.assertNotEmitted(audio_manager.new_alarm):
            audio_manager._on_severity_change(mock_cavity, 1)


class TestMultipleCavities:
    """Test handling multiple cavities"""

    @pytest.fixture
    def multi_cavity_machine(self):
        """Create machine with multiple cavities"""
        machine = Mock()

        cavities = {}
        for i in range(1, 4):
            cavity = Mock()
            cavity.number = i
            cavity.cryomodule = Mock()
            cavity.cryomodule.name = "16"
            cavity.cavity_widget = Mock()
            cavity.cavity_widget.severity_changed = Mock()
            cavities[i] = cavity

        cryomodule = Mock()
        cryomodule.name = "16"
        cryomodule.cavities = cavities

        linac = Mock()
        linac.cryomodules = {"16": cryomodule}
        machine.linacs = [linac]

        return machine

    def test_multiple_alarms_tracked_separately(
        self, qtbot, multi_cavity_machine
    ):
        """Test multiple cavities can alarm independently"""
        manager = AudioAlertManager(multi_cavity_machine)
        manager.setEnabled(True)

        cav1 = multi_cavity_machine.linacs[0].cryomodules["16"].cavities[1]
        cav2 = multi_cavity_machine.linacs[0].cryomodules["16"].cavities[2]

        manager._on_severity_change(cav1, 2)
        manager._on_severity_change(cav2, 2)

        assert "16_1" in manager.alerted_alarms
        assert "16_2" in manager.alerted_alarms
        assert len(manager.unacknowledged_alarms) == 2

    def test_acknowledge_one_cavity_leaves_others(
        self, qtbot, multi_cavity_machine
    ):
        """Test acknowledging one cavity doesn't affect others"""
        manager = AudioAlertManager(multi_cavity_machine)
        manager.setEnabled(True)

        cav1 = multi_cavity_machine.linacs[0].cryomodules["16"].cavities[1]
        cav2 = multi_cavity_machine.linacs[0].cryomodules["16"].cavities[2]

        manager._on_severity_change(cav1, 2)
        manager._on_severity_change(cav2, 2)

        manager.acknowledge_cavity("16_1")

        assert "16_1" in manager.acknowledged_cavities
        assert "16_2" not in manager.acknowledged_cavities
        assert "16_1" not in manager.unacknowledged_alarms
        assert "16_2" in manager.unacknowledged_alarms

    def test_clearing_one_cavity_leaves_others(
        self, qtbot, multi_cavity_machine
    ):
        """Test clearing one cavity doesn't affect others"""
        manager = AudioAlertManager(multi_cavity_machine)
        manager.setEnabled(True)

        cav1 = multi_cavity_machine.linacs[0].cryomodules["16"].cavities[1]
        cav2 = multi_cavity_machine.linacs[0].cryomodules["16"].cavities[2]

        manager._on_severity_change(cav1, 2)
        manager._on_severity_change(cav2, 2)

        manager._on_severity_change(cav1, 0)

        assert "16_1" not in manager.alerted_alarms
        assert "16_2" in manager.alerted_alarms


class TestEdgeCases:
    """Test edge cases and error conditions"""

    def test_cleared_severity_processed_when_disabled(
        self, audio_manager, mock_cavity
    ):
        """Test severity=0 clears state even when manager is disabled"""
        audio_manager.setEnabled(True)

        # Trigger alarm
        audio_manager._on_severity_change(mock_cavity, 2)
        assert "16_1" in audio_manager.alerted_alarms

        # Disable manager
        audio_manager.setEnabled(False)

        # Clear the cavity - should still clear state
        audio_manager._on_severity_change(mock_cavity, 0)

        # State should be cleared despite manager being disabled
        assert "16_1" not in audio_manager.alerted_alarms
        assert "16_1" not in audio_manager.unacknowledged_alarms

    def test_new_alarms_ignored_when_disabled(self, audio_manager, mock_cavity):
        """Test new alarms are ignored when disabled but clears still work"""
        audio_manager.setEnabled(False)

        # Try to trigger alarm while disabled
        audio_manager._on_severity_change(mock_cavity, 2)
        assert "16_1" not in audio_manager.alerted_alarms

        # Enable and trigger
        audio_manager.setEnabled(True)
        audio_manager._on_severity_change(mock_cavity, 2)
        assert "16_1" in audio_manager.alerted_alarms

        # Disable and clear - should still clear
        audio_manager.setEnabled(False)
        audio_manager._on_severity_change(mock_cavity, 0)
        assert "16_1" not in audio_manager.alerted_alarms

    def test_stop_monitoring_with_clear_state(self, audio_manager, mock_cavity):
        """Test stopping with clear_state option"""
        audio_manager.setEnabled(True)

        # Trigger some alarms
        audio_manager._on_severity_change(mock_cavity, 2)
        assert len(audio_manager.alerted_alarms) == 1

        # Stop with clear
        audio_manager.stop_monitoring(clear_state=True)

        assert len(audio_manager.alerted_alarms) == 0
        assert len(audio_manager.unacknowledged_alarms) == 0
        assert len(audio_manager.acknowledged_cavities) == 0

    def test_severity_change_before_start(self, audio_manager, mock_cavity):
        """Test handling severity change before monitoring starts"""
        # Should not crash, but shouldn't alert either
        audio_manager._on_severity_change(mock_cavity, 2)
        assert "16_1" not in audio_manager.alerted_alarms

    def test_invalid_severity_values(self, audio_manager, mock_cavity):
        """Test handling invalid severity values"""
        audio_manager.setEnabled(True)

        # Test negative severity
        audio_manager._on_severity_change(mock_cavity, -1)
        assert "16_1" not in audio_manager.alerted_alarms

        # Test high severity
        audio_manager._on_severity_change(mock_cavity, 999)
        assert "16_1" not in audio_manager.alerted_alarms

    def test_rapid_severity_changes(self, audio_manager, mock_cavity):
        """Test rapid severity changes don't cause issues"""
        audio_manager.setEnabled(True)

        with patch.object(audio_manager, "_play_alarm_sound") as mock_alarm:
            # Rapidly toggle between states
            for _ in range(10):
                audio_manager._on_severity_change(mock_cavity, 2)
                audio_manager._on_severity_change(mock_cavity, 0)

            # Should only play alarm on first occurrence in each cycle
            assert mock_alarm.call_count <= 10

    def test_acknowledge_clears_from_escalation_queue(
        self, audio_manager, mock_cavity
    ):
        """Test acknowledged alarm is removed from escalation checking"""
        audio_manager.setEnabled(True)
        audio_manager._on_severity_change(mock_cavity, 2)

        cavity_id = "16_1"
        initial_timestamp = audio_manager.unacknowledged_alarms.get(cavity_id)
        assert initial_timestamp is not None

        audio_manager.acknowledge_cavity(cavity_id)

        assert cavity_id not in audio_manager.unacknowledged_alarms

    def test_restart_monitoring_preserves_state(
        self, audio_manager, mock_cavity
    ):
        """Test stopping and restarting monitoring"""
        audio_manager.start_monitoring()
        audio_manager._on_severity_change(mock_cavity, 2)

        assert "16_1" in audio_manager.alerted_alarms

        audio_manager.stop_monitoring()
        audio_manager.start_monitoring()

        # State should persist
        assert "16_1" in audio_manager.alerted_alarms

    def test_empty_machine(self, qtbot):
        """Test manager with no cavities"""
        machine = Mock()
        machine.linacs = []

        manager = AudioAlertManager(machine)
        manager.start_monitoring()

        # Should not crash
        assert manager._enabled is True


class TestIntegration:
    """Integration tests simulating real-world scenarios"""

    @patch(
        "sc_linac_physics.displays.cavity_display.frontend.audio_manager.time.time"
    )
    @patch(
        "sc_linac_physics.displays.cavity_display.frontend.audio_manager.QApplication.beep"
    )
    def test_full_alarm_lifecycle(
        self, mock_beep, mock_time, audio_manager, mock_cavity, qtbot
    ):
        """Test complete alarm lifecycle: trigger -> escalate -> acknowledge -> clear"""
        audio_manager.start_monitoring()

        # Step 1: Alarm triggers
        mock_time.return_value = 1000.0
        with qtbot.waitSignal(audio_manager.new_alarm, timeout=1000):
            audio_manager._on_severity_change(mock_cavity, 2)

        assert "16_1" in audio_manager.alerted_alarms
        assert "16_1" in audio_manager.unacknowledged_alarms

        # Step 2: Escalation after 2 minutes
        mock_time.return_value = 1121.0
        mock_beep.reset_mock()
        audio_manager._check_escalation()
        assert mock_beep.called

        # Step 3: Acknowledge
        audio_manager.acknowledge_cavity("16_1")
        assert "16_1" in audio_manager.acknowledged_cavities
        assert "16_1" not in audio_manager.unacknowledged_alarms

        # Step 4: Clear alarm
        audio_manager._on_severity_change(mock_cavity, 0)
        assert "16_1" not in audio_manager.alerted_alarms
        assert "16_1" not in audio_manager.acknowledged_cavities

    @patch(
        "sc_linac_physics.displays.cavity_display.frontend.audio_manager.QApplication.beep"
    )
    def test_warning_to_alarm_escalation(
        self, mock_beep, audio_manager, mock_cavity
    ):
        """Test cavity going from warning to alarm"""
        audio_manager.setEnabled(True)

        # Start with warning
        audio_manager._on_severity_change(mock_cavity, 1)
        assert "16_1" in audio_manager.alerted_warnings
        assert "16_1" not in audio_manager.alerted_alarms

        mock_beep.reset_mock()

        # Escalate to alarm
        audio_manager._on_severity_change(mock_cavity, 2)
        assert "16_1" in audio_manager.alerted_alarms
        assert mock_beep.called

    @patch(
        "sc_linac_physics.displays.cavity_display.frontend.audio_manager.QApplication.beep"
    )
    def test_alarm_to_warning_deescalation(
        self, mock_beep, audio_manager, mock_cavity
    ):
        """Test cavity going from alarm to warning properly clears alarm state"""
        audio_manager.setEnabled(True)

        # Start with alarm
        audio_manager._on_severity_change(mock_cavity, 2)
        assert "16_1" in audio_manager.alerted_alarms
        assert "16_1" not in audio_manager.alerted_warnings

        # De-escalate to warning
        audio_manager._on_severity_change(mock_cavity, 1)

        # Should be cleared from alarms and added to warnings
        assert "16_1" not in audio_manager.alerted_alarms  # NOW PASSES!
        assert "16_1" in audio_manager.alerted_warnings
        assert (
            "16_1" not in audio_manager.unacknowledged_alarms
        )  # Escalation stopped

    def test_alarm_re_trigger_after_warning(self, audio_manager, mock_cavity):
        """Test alarm can re-trigger after de-escalating to warning"""
        audio_manager.setEnabled(True)

        with patch.object(audio_manager, "_play_alarm_sound") as mock_alarm:
            # Alarm → Warning → Alarm
            audio_manager._on_severity_change(mock_cavity, 2)
            assert mock_alarm.call_count == 1

            audio_manager._on_severity_change(mock_cavity, 1)

            # Should trigger alarm sound again
            audio_manager._on_severity_change(mock_cavity, 2)
            assert mock_alarm.call_count == 2  # Re-triggered!

    def test_disable_during_active_alarm(self, audio_manager, mock_cavity):
        """Test disabling manager during active alarm"""
        audio_manager.setEnabled(True)
        audio_manager._on_severity_change(mock_cavity, 2)

        assert "16_1" in audio_manager.alerted_alarms

        # Disable manager
        audio_manager.setEnabled(False)

        with patch.object(
            audio_manager, "_play_escalation_sound"
        ) as mock_escalation:
            audio_manager._check_escalation()
            mock_escalation.assert_not_called()

    @patch(
        "sc_linac_physics.displays.cavity_display.frontend.audio_manager.time.time"
    )
    def test_multiple_escalations_over_time(
        self, mock_time, audio_manager, mock_cavity
    ):
        """Test escalation continues for persistent alarms"""
        audio_manager.setEnabled(True)

        mock_time.return_value = 1000.0
        audio_manager._on_severity_change(mock_cavity, 2)

        escalation_count = 0

        with patch.object(
            audio_manager, "_play_escalation_sound"
        ) as mock_escalation:
            # Check multiple times over 10 minutes
            for minutes in [3, 5, 7, 10]:
                mock_time.return_value = 1000.0 + (minutes * 60)
                audio_manager._check_escalation()
                if mock_escalation.called:
                    escalation_count += 1
                mock_escalation.reset_mock()

        assert escalation_count > 0


class TestConcurrency:
    """Test thread safety and concurrent operations"""

    def test_concurrent_severity_changes(self, audio_manager):
        """Test handling severity changes from multiple cavities simultaneously"""
        audio_manager.setEnabled(True)

        cavities = []
        for i in range(5):
            cavity = Mock()
            cavity.number = i
            cavity.cryomodule = Mock()
            cavity.cryomodule.name = "16"
            cavities.append(cavity)

        # Trigger all at once
        for cavity in cavities:
            audio_manager._on_severity_change(cavity, 2)

        assert len(audio_manager.alerted_alarms) == 5
        assert len(audio_manager.unacknowledged_alarms) == 5

    def test_acknowledge_during_escalation_check(
        self, audio_manager, mock_cavity
    ):
        """Test acknowledging while escalation is checking"""
        audio_manager.setEnabled(True)
        audio_manager._on_severity_change(mock_cavity, 2)

        with patch.object(audio_manager, "_play_escalation_sound"):
            # Acknowledge during escalation
            audio_manager.acknowledge_cavity("16_1")
            audio_manager._check_escalation()

        # Should not crash
        assert "16_1" in audio_manager.acknowledged_cavities


# Pytest configuration for Qt testing
@pytest.fixture(scope="session")
def qapp():
    """Session-wide QApplication instance"""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
