import logging
import time

from PyQt5.QtCore import QTimer, QObject, pyqtSignal
from PyQt5.QtWidgets import QApplication

from sc_linac_physics.displays.cavity_display.utils.utils import (
    CAV_LOG_DIR,
    DEBUG,
)
from sc_linac_physics.utils.logger import custom_logger

# Create logger for audio manager
audio_alert_logger = custom_logger(
    name="cavity.audio.alert",
    log_filename="cavity_audio_alert",
    log_dir=CAV_LOG_DIR,
    level=logging.DEBUG if DEBUG else logging.INFO,
)


class AudioAlertManager(QObject):
    """Manages audio alerts with escalation and acknowledgment using system sounds"""

    new_alarm = pyqtSignal(object)

    def __init__(self, gui_machine, parent=None):
        super().__init__(parent)
        self.gui_machine = gui_machine
        self._enabled = False

        # Track alerted cavities
        self.alerted_alarms = set()
        self.alerted_warnings = set()
        self.unacknowledged_alarms = {}
        self.acknowledged_cavities = set()

        # Escalation tracking
        self._last_escalation_sound_time = 0
        self._escalation_sound_interval = 300  # Only play sound every 5 minutes
        self._per_cavity_escalation = (
            {}
        )  # Track when each cavity was last escalated

        # Escalation timer with proper Qt parent
        self.escalation_timer = QTimer(self)
        self.escalation_timer.timeout.connect(self._check_escalation)

        audio_alert_logger.debug(
            "AudioAlertManager initialized",
            extra={
                "extra_data": {
                    "enabled": self._enabled,
                    "escalation_interval_ms": 30000,
                    "escalation_sound_interval_sec": self._escalation_sound_interval,
                }
            },
        )

    def _check_escalation(self):
        """Check for unacknowledged alarms and escalate with rate limiting."""
        if not self._enabled:
            return

        current_time = time.time()
        escalated_cavities = []

        for cavity_id, timestamp in list(self.unacknowledged_alarms.items()):
            if cavity_id in self.acknowledged_cavities:
                continue

            elapsed = current_time - timestamp
            if elapsed > 120:  # 2 minutes
                # Check if this cavity needs logging (every 5 min per cavity)
                last_logged = self._per_cavity_escalation.get(cavity_id, 0)
                should_log = (
                    current_time - last_logged
                ) >= self._escalation_sound_interval  # 5 minutes

                escalated_cavities.append(
                    {
                        "cavity_id": cavity_id,
                        "duration_sec": round(elapsed, 1),
                        "timestamp": timestamp,
                        "should_log": should_log,
                    }
                )

                if should_log:
                    self._per_cavity_escalation[cavity_id] = current_time

        if escalated_cavities:
            # Capture PREVIOUS timestamp before updating
            previous_sound_time = self._last_escalation_sound_time

            # Determine if we should play sound (global rate limit)
            should_play_sound = (
                current_time - previous_sound_time
            ) >= self._escalation_sound_interval

            # Filter cavities that should be logged this cycle
            newly_escalated = [c for c in escalated_cavities if c["should_log"]]

            # Calculate time since last sound BEFORE updating
            time_since_last_sound = (
                round(current_time - previous_sound_time, 1)
                if previous_sound_time > 0
                else None
            )

            if should_play_sound and escalated_cavities:
                self._play_escalation_sound()
                self._last_escalation_sound_time = (
                    current_time  # Update AFTER capturing
                )
                log_level = logging.WARNING
                message_prefix = "ESCALATION (sound)"
            else:
                log_level = logging.DEBUG
                message_prefix = "Escalation check (silent)"

            # Log newly escalated or if sound was played
            if newly_escalated or should_play_sound:
                audio_alert_logger.log(
                    log_level,
                    f"{message_prefix}: {len(escalated_cavities)} unacknowledged alarm(s)",
                    extra={
                        "extra_data": {
                            "escalated_count": len(escalated_cavities),
                            "newly_escalated_count": len(newly_escalated),
                            "total_unacknowledged": len(
                                self.unacknowledged_alarms
                            ),
                            "escalated_cavities": (
                                newly_escalated
                                if newly_escalated
                                else escalated_cavities
                            ),
                            "sound_played": should_play_sound,
                            "longest_unack_sec": max(
                                c["duration_sec"] for c in escalated_cavities
                            ),
                            "time_since_last_sound_sec": time_since_last_sound,
                        }
                    },
                )

    def setEnabled(self, enabled: bool):
        """Enable or disable audio alerts."""
        self._enabled = enabled
        audio_alert_logger.info(
            f"Audio alerts {'enabled' if enabled else 'disabled'}",
            extra={"extra_data": {"enabled": enabled}},
        )

    def start_monitoring(self):
        """Start monitoring cavities for alarms."""
        if not hasattr(self, "_connected"):
            self._connect_to_cavities()
            self._connected = True

        self.escalation_timer.start(30000)
        self._enabled = True
        audio_alert_logger.info(
            "Audio alert monitoring started",
            extra={
                "extra_data": {
                    "escalation_interval_sec": 30,
                    "connected": self._connected,
                }
            },
        )

    def stop_monitoring(self, clear_state=False):
        """
        Stop monitoring and silence all audio.

        Args:
            clear_state: If True, clear all tracked alarms/warnings when stopping
        """
        self.escalation_timer.stop()
        self._enabled = False

        if clear_state:
            cleared_count = len(self.alerted_alarms) + len(
                self.alerted_warnings
            )
            self.alerted_alarms.clear()
            self.alerted_warnings.clear()
            self.unacknowledged_alarms.clear()
            self.acknowledged_cavities.clear()
            self._per_cavity_escalation.clear()  # Clear escalation tracking too

            if cleared_count > 0:
                audio_alert_logger.info(
                    "Cleared all tracked alarms on stop",
                    extra={"extra_data": {"cleared_count": cleared_count}},
                )

        audio_alert_logger.info(
            "Audio alert monitoring stopped",
            extra={
                "extra_data": {
                    "active_alarms": len(self.alerted_alarms),
                    "active_warnings": len(self.alerted_warnings),
                    "unacknowledged": len(self.unacknowledged_alarms),
                    "state_cleared": clear_state,
                }
            },
        )

    def _on_severity_change(self, cavity, severity):
        """Handle severity change for a cavity - only if enabled."""
        cavity_id = f"{cavity.cryomodule.name}_{cavity.number}"

        # Special handling for severity 0 (cleared) - ALWAYS process, even when disabled
        if severity == 0:
            self._handle_cleared_severity(cavity_id, cavity)
            return

        # Only process alarms/warnings if enabled
        if not self._enabled:
            return

        # Track if this cavity is acknowledged
        is_acknowledged = cavity_id in self.acknowledged_cavities

        if severity == 2:  # Red alarm
            self._handle_alarm_severity(cavity_id, cavity, is_acknowledged)
        elif severity == 1:  # Yellow warning
            self._handle_warning_severity(cavity_id, cavity, is_acknowledged)

    def _handle_cleared_severity(self, cavity_id: str, cavity) -> None:
        """Handle severity 0 (cleared) state."""
        was_active = (
            cavity_id in self.alerted_alarms
            or cavity_id in self.alerted_warnings
        )
        was_acknowledged = cavity_id in self.acknowledged_cavities

        if was_active:
            audio_alert_logger.info(
                "Cavity alarm/warning cleared",
                extra={
                    "extra_data": {
                        "cavity_id": cavity_id,
                        "cm": cavity.cryomodule.name,
                        "cavity_num": cavity.number,
                        "was_alarm": cavity_id in self.alerted_alarms,
                        "was_warning": cavity_id in self.alerted_warnings,
                        "was_acknowledged": was_acknowledged,
                        "manager_enabled": self._enabled,
                    }
                },
            )

        # Clear all tracking for this cavity
        self.alerted_alarms.discard(cavity_id)
        self.alerted_warnings.discard(cavity_id)
        self.unacknowledged_alarms.pop(cavity_id, None)
        self.acknowledged_cavities.discard(cavity_id)
        self._per_cavity_escalation.pop(
            cavity_id, None
        )  # Clear escalation tracking too

    def _handle_alarm_severity(
        self, cavity_id: str, cavity, is_acknowledged: bool
    ) -> None:
        """Handle severity 2 (alarm) state."""
        # Always update state, even if acknowledged
        was_already_alarm = cavity_id in self.alerted_alarms
        self.alerted_alarms.add(cavity_id)
        self.alerted_warnings.discard(
            cavity_id
        )  # Remove from warnings if escalating

        # Only play sound and emit signal if NOT acknowledged AND new alarm
        if not is_acknowledged and not was_already_alarm:
            audio_alert_logger.warning(
                "NEW ALARM triggered",
                extra={
                    "extra_data": {
                        "cavity_id": cavity_id,
                        "cm": cavity.cryomodule.name,
                        "cavity_num": cavity.number,
                        "severity": 2,
                        "timestamp": time.time(),
                    }
                },
            )
            self._play_alarm_sound()
            self.unacknowledged_alarms[cavity_id] = time.time()
            self.new_alarm.emit(cavity)
        elif is_acknowledged:
            audio_alert_logger.debug(
                "Alarm state updated for acknowledged cavity (no sound)",
                extra={
                    "extra_data": {
                        "cavity_id": cavity_id,
                        "severity": 2,
                    }
                },
            )

    def _handle_warning_severity(
        self, cavity_id: str, cavity, is_acknowledged: bool
    ) -> None:
        """Handle severity 1 (warning) state."""
        # Always update state
        was_already_warning = cavity_id in self.alerted_warnings
        self.alerted_warnings.add(cavity_id)

        # Check if de-escalating from alarm to warning
        was_alarm = cavity_id in self.alerted_alarms
        if was_alarm:
            self._handle_alarm_deescalation(cavity_id, is_acknowledged)

        # Only play sound if NOT acknowledged AND new warning (and wasn't just de-escalated)
        if not is_acknowledged and not was_already_warning and not was_alarm:
            audio_alert_logger.info(
                "NEW WARNING triggered",
                extra={
                    "extra_data": {
                        "cavity_id": cavity_id,
                        "cm": cavity.cryomodule.name,
                        "cavity_num": cavity.number,
                        "severity": 1,
                    }
                },
            )
            self._play_warning_sound()

    def _handle_alarm_deescalation(
        self, cavity_id: str, is_acknowledged: bool
    ) -> None:
        """Handle de-escalation from alarm to warning."""
        self.alerted_alarms.discard(cavity_id)
        self.unacknowledged_alarms.pop(cavity_id, None)

        # Reset per-cavity escalation tracking so future alarms are not rate-limited
        self._per_cavity_escalation.pop(cavity_id, None)

        # Clear acknowledgment on de-escalation so future alarms can trigger
        if is_acknowledged:
            self.acknowledged_cavities.discard(cavity_id)
            audio_alert_logger.info(
                "Alarm de-escalated to warning, clearing acknowledgment",
                extra={
                    "extra_data": {
                        "cavity_id": cavity_id,
                        "from_severity": 2,
                        "to_severity": 1,
                    }
                },
            )
        else:
            audio_alert_logger.info(
                "Alarm de-escalated to warning",
                extra={
                    "extra_data": {
                        "cavity_id": cavity_id,
                        "from_severity": 2,
                        "to_severity": 1,
                    }
                },
            )

    def acknowledge_cavity(self, cavity_id, force=False):
        """
        Acknowledge alarm for a specific cavity and stop audio/escalation.

        Args:
            cavity_id: String in format "CM_NUMBER" e.g. "16_1" for CM16 Cav1
            force: If True, acknowledge even if not currently alarmed (use with caution)

        Returns:
            bool: True if acknowledged, False if cavity was not in alarm state
        """
        is_alarmed = cavity_id in self.alerted_alarms
        is_warned = cavity_id in self.alerted_warnings
        is_unacknowledged = cavity_id in self.unacknowledged_alarms

        # Only acknowledge if actually in an alarm/warning state (unless forced)
        if not force and not is_alarmed and not is_warned:
            audio_alert_logger.info(
                "Acknowledge request ignored - cavity not in alarm state",
                extra={
                    "extra_data": {
                        "cavity_id": cavity_id,
                        "reason": "not_alarmed",
                        "current_alarms": len(self.alerted_alarms),
                        "current_warnings": len(self.alerted_warnings),
                    }
                },
            )
            return False

        unack_duration = None
        if is_unacknowledged:
            unack_duration = time.time() - self.unacknowledged_alarms[cavity_id]
            self.unacknowledged_alarms.pop(cavity_id)

        self.acknowledged_cavities.add(cavity_id)

        # Clear from per-cavity escalation tracking
        self._per_cavity_escalation.pop(cavity_id, None)

        audio_alert_logger.info(
            "Cavity alarm acknowledged",
            extra={
                "extra_data": {
                    "cavity_id": cavity_id,
                    "was_alarm": is_alarmed,
                    "was_warning": is_warned,
                    "was_unacknowledged": is_unacknowledged,
                    "acknowledgment_time_sec": (
                        round(unack_duration, 1) if unack_duration else None
                    ),
                    "forced": force,
                    "total_acknowledged": len(self.acknowledged_cavities),
                    "remaining_unacknowledged": len(self.unacknowledged_alarms),
                }
            },
        )

        return True

    def acknowledge_alarm(self, cavity):
        """
        Acknowledge an alarm to stop escalation (legacy method).
        Calls acknowledge_cavity internally.
        """
        cavity_id = f"{cavity.cryomodule.name}_{cavity.number}"
        audio_alert_logger.debug(
            "Legacy acknowledge_alarm called",
            extra={
                "extra_data": {
                    "cavity_id": cavity_id,
                    "method": "acknowledge_alarm (legacy)",
                }
            },
        )
        return self.acknowledge_cavity(cavity_id)

    def _connect_to_cavities(self):
        """Connect to all cavity severity changes via signals"""
        cavity_count = 0

        for linac in self.gui_machine.linacs:
            for cm in linac.cryomodules.values():
                for cavity in cm.cavities.values():
                    cavity_count += 1
                    cavity.cavity_widget.severity_changed.connect(
                        lambda value, cav=cavity: self._on_severity_change(
                            cav, value
                        )
                    )

        audio_alert_logger.info(
            "Audio manager connected to cavity signals",
            extra={
                "extra_data": {
                    "cavity_count": cavity_count,
                    "connection_method": "signal",
                }
            },
        )

    def _play_alarm_sound(self):
        """Play alarm sound - double beep"""
        audio_alert_logger.debug("Playing alarm sound (double beep)")
        QApplication.beep()
        QTimer.singleShot(200, QApplication.beep)

    def _play_warning_sound(self):
        """Play warning sound - single beep"""
        audio_alert_logger.debug("Playing warning sound (single beep)")
        QApplication.beep()

    def _play_escalation_sound(self):
        """Play escalation sound - triple beep"""
        audio_alert_logger.debug("Playing escalation sound (triple beep)")
        QApplication.beep()
        QTimer.singleShot(200, QApplication.beep)
        QTimer.singleShot(400, QApplication.beep)
