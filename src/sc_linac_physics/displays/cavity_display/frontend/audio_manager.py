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

        # Escalation timer
        self.escalation_timer = QTimer(self)
        self.escalation_timer.timeout.connect(self._check_escalation)

        audio_alert_logger.debug(
            "AudioAlertManager initialized",
            extra={
                "extra_data": {
                    "enabled": self._enabled,
                    "escalation_interval_ms": 30000,
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
        # This ensures state is cleared when cavities return to normal, regardless of enabled state
        if severity == 0:
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
            return

        # Only process alarms/warnings if enabled
        if not self._enabled:
            return

        # Check if already acknowledged (only blocks NEW alarms, not clearing)
        if cavity_id in self.acknowledged_cavities:
            audio_alert_logger.debug(
                "Severity change ignored for acknowledged cavity",
                extra={
                    "extra_data": {
                        "cavity_id": cavity_id,
                        "severity": severity,
                    }
                },
            )
            return

        if severity == 2:  # Red alarm
            if cavity_id not in self.alerted_alarms:
                audio_alert_logger.warning(
                    "NEW ALARM triggered",
                    extra={
                        "extra_data": {
                            "cavity_id": cavity_id,
                            "cm": cavity.cryomodule.name,
                            "cavity_num": cavity.number,
                            "severity": severity,
                            "timestamp": time.time(),
                        }
                    },
                )
                self._play_alarm_sound()
                self.alerted_alarms.add(cavity_id)
                self.unacknowledged_alarms[cavity_id] = time.time()
                self.new_alarm.emit(cavity)

            # Remove from warnings if it was there
            self.alerted_warnings.discard(cavity_id)

        elif severity == 1:  # Yellow warning
            if cavity_id not in self.alerted_warnings:
                audio_alert_logger.info(
                    "NEW WARNING triggered",
                    extra={
                        "extra_data": {
                            "cavity_id": cavity_id,
                            "cm": cavity.cryomodule.name,
                            "cavity_num": cavity.number,
                            "severity": severity,
                        }
                    },
                )
                self._play_warning_sound()
                self.alerted_warnings.add(cavity_id)

            # De-escalating from alarm to warning - clear alarm state
            if cavity_id in self.alerted_alarms:
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
                self.alerted_alarms.discard(cavity_id)
                self.unacknowledged_alarms.pop(cavity_id, None)

    def _check_escalation(self):
        """Play escalation sound for unacknowledged alarms > 2 minutes - only if enabled."""
        if not self._enabled:
            return

        current_time = time.time()
        escalated_cavities = []

        for cavity_id, timestamp in list(self.unacknowledged_alarms.items()):
            if cavity_id in self.acknowledged_cavities:
                continue

            elapsed = current_time - timestamp
            if elapsed > 120:  # 2 minutes
                escalated_cavities.append(
                    {
                        "cavity_id": cavity_id,
                        "duration_sec": round(elapsed, 1),
                        "timestamp": timestamp,
                    }
                )

        if escalated_cavities:
            # Single escalation sound for all unacknowledged alarms
            self._play_escalation_sound()

            audio_alert_logger.warning(
                f"ESCALATION: {len(escalated_cavities)} unacknowledged alarm(s)",
                extra={
                    "extra_data": {
                        "escalated_count": len(escalated_cavities),
                        "total_unacknowledged": len(self.unacknowledged_alarms),
                        "escalated_cavities": escalated_cavities,
                        "longest_unack_sec": max(
                            c["duration_sec"] for c in escalated_cavities
                        ),
                    }
                },
            )

    def acknowledge_cavity(self, cavity_id):
        """
        Acknowledge alarm for a specific cavity and stop audio/escalation.

        Args:
            cavity_id: String in format "CM_NUMBER" e.g. "16_1" for CM16 Cav1
        """
        was_unacknowledged = cavity_id in self.unacknowledged_alarms
        unack_duration = None

        if was_unacknowledged:
            unack_duration = time.time() - self.unacknowledged_alarms[cavity_id]
            self.unacknowledged_alarms.pop(cavity_id)

        self.acknowledged_cavities.add(cavity_id)

        audio_alert_logger.info(
            "Cavity alarm acknowledged",
            extra={
                "extra_data": {
                    "cavity_id": cavity_id,
                    "was_unacknowledged": was_unacknowledged,
                    "acknowledgment_time_sec": (
                        round(unack_duration, 1) if unack_duration else None
                    ),
                    "total_acknowledged": len(self.acknowledged_cavities),
                    "remaining_unacknowledged": len(self.unacknowledged_alarms),
                }
            },
        )

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
        self.acknowledge_cavity(cavity_id)

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
