import os
import time

from PyQt5.QtCore import QObject, QTimer, pyqtSignal
from PyQt5.QtMultimedia import QSound


class AudioAlertManager(QObject):
    """Manages audio alerts with escalation and acknowledgment"""

    new_alarm = pyqtSignal(object)

    def __init__(self, gui_machine, parent=None):
        super().__init__(parent)
        self.gui_machine = gui_machine
        self._enabled = False  # Start disabled

        # Track alerted cavities
        self.alerted_alarms = set()
        self.alerted_warnings = set()
        self.unacknowledged_alarms = {}
        self.acknowledged_cavities = set()

        # Setup sounds
        self.alarm_sound = None
        self.warning_sound = None
        self.escalation_sound = None
        self._load_sounds()

        # Escalation timer - don't start yet
        self.escalation_timer = QTimer()
        self.escalation_timer.timeout.connect(self._check_escalation)
        # Don't start automatically

    def setEnabled(self, enabled: bool):
        """Enable or disable audio alerts."""
        self._enabled = enabled
        print(f"AudioManager: {'Enabled' if enabled else 'Disabled'}")

    def start_monitoring(self):
        """Start monitoring cavities for alarms."""
        if not hasattr(self, "_connected"):
            self._connect_to_cavities()
            self._connected = True

        self.escalation_timer.start(30000)
        self._enabled = True
        print("AudioManager: Started monitoring")

    def stop_monitoring(self):
        """Stop monitoring and silence all audio."""
        self.escalation_timer.stop()
        self._enabled = False
        self.stop_audio()
        print("AudioManager: Stopped monitoring")

    def _on_severity_change(self, cavity, severity):
        """Handle severity change for a cavity - only if enabled."""
        if not self._enabled:
            return  # Audio is disabled, do nothing

        cavity_id = f"{cavity.cryomodule.name}_{cavity.number}"

        # Check if already acknowledged
        if cavity_id in self.acknowledged_cavities:
            return

        if severity == 2:  # Red alarm
            if cavity_id not in self.alerted_alarms:
                print(f"  -> Playing alarm sound for {cavity_id}")
                self._play_alarm_sound()
                self.alerted_alarms.add(cavity_id)
                self.unacknowledged_alarms[cavity_id] = time.time()
                self.new_alarm.emit(cavity)
                print(
                    f"🔴 NEW ALARM: CM{cavity.cryomodule.name} Cavity {cavity.number}"
                )

        elif severity == 1:  # Yellow warning
            if cavity_id not in self.alerted_warnings:
                print(f"  -> Playing warning sound for {cavity_id}")
                self._play_warning_sound()
                self.alerted_warnings.add(cavity_id)
                print(
                    f"🟡 NEW WARNING: CM{cavity.cryomodule.name} Cavity {cavity.number}"
                )

        else:  # Cleared
            if (
                cavity_id in self.alerted_alarms
                or cavity_id in self.alerted_warnings
            ):
                print(f"  -> Cleared: {cavity_id}")

            self.alerted_alarms.discard(cavity_id)
            self.alerted_warnings.discard(cavity_id)
            self.unacknowledged_alarms.pop(cavity_id, None)
            self.acknowledged_cavities.discard(cavity_id)

    def _check_escalation(self):
        """Play escalation sound for unacknowledged alarms > 2 minutes - only if enabled."""
        if not self._enabled:
            return

        current_time = time.time()

        for cavity_id, timestamp in list(self.unacknowledged_alarms.items()):
            if cavity_id in self.acknowledged_cavities:
                continue

            if current_time - timestamp > 120:  # 2 minutes
                print(
                    f"⚠️ ESCALATION: {cavity_id} unacknowledged for 2+ minutes"
                )

                if self.escalation_sound:
                    self.escalation_sound.play()
                else:
                    from PyQt5.QtWidgets import QApplication

                    QApplication.beep()
                    QTimer.singleShot(200, QApplication.beep)
                    QTimer.singleShot(400, QApplication.beep)

    def acknowledge_cavity(self, cavity_id):
        """
        Acknowledge alarm for a specific cavity and stop audio/escalation.

        Args:
            cavity_id: String in format "CM_NUMBER" e.g. "16_1" for CM16 Cav1
        """
        print(f"AudioManager: Acknowledging {cavity_id}")

        # Remove from unacknowledged alarms (stops escalation)
        if cavity_id in self.unacknowledged_alarms:
            self.unacknowledged_alarms.pop(cavity_id)
            print(f"  Removed {cavity_id} from unacknowledged_alarms")

        # Add to acknowledged list to prevent re-alerting
        self.acknowledged_cavities.add(cavity_id)
        print(f"  Added {cavity_id} to acknowledged_cavities")
        print(f"  Currently acknowledged: {self.acknowledged_cavities}")

    def stop_audio(self):
        """Stop all audio playback"""
        print("AudioManager: Stopping all audio")

        # Stop QSound instances if they're playing
        if self.alarm_sound and hasattr(self.alarm_sound, "stop"):
            self.alarm_sound.stop()
        if self.warning_sound and hasattr(self.warning_sound, "stop"):
            self.warning_sound.stop()
        if self.escalation_sound and hasattr(self.escalation_sound, "stop"):
            self.escalation_sound.stop()

    def _load_sounds(self):
        """Load audio files if they exist, fallback to system beep"""
        base_path = os.path.dirname(os.path.abspath(__file__))

        alarm_path = os.path.join(base_path, "sounds", "alarm.wav")
        warning_path = os.path.join(base_path, "sounds", "warning.wav")
        escalation_path = os.path.join(base_path, "sounds", "urgent.wav")

        if os.path.exists(alarm_path):
            self.alarm_sound = QSound(alarm_path)
            print(f"✓ Loaded alarm sound: {alarm_path}")
        else:
            print(
                f"⚠ Alarm sound not found at {alarm_path}, will use system beep"
            )

        if os.path.exists(warning_path):
            self.warning_sound = QSound(warning_path)
            print(f"✓ Loaded warning sound: {warning_path}")
        else:
            print(
                f"⚠ Warning sound not found at {warning_path}, will use system beep"
            )

        if os.path.exists(escalation_path):
            self.escalation_sound = QSound(escalation_path)
            print(f"✓ Loaded escalation sound: {escalation_path}")
        else:
            print(
                f"⚠ Escalation sound not found at {escalation_path}, will use system beep"
            )

    def _connect_to_cavities(self):
        """Connect to all cavity severity change signals"""
        print("Connecting audio manager to cavity severity signals...")

        cavity_count = 0
        for linac in self.gui_machine.linacs:
            cryomodules = (
                linac.cryomodules.values()
                if isinstance(linac.cryomodules, dict)
                else linac.cryomodules
            )

            for cm in cryomodules:
                cavities = (
                    cm.cavities.values()
                    if isinstance(cm.cavities, dict)
                    else cm.cavities
                )

                for cavity in cavities:
                    cavity_count += 1
                    cavity.cavity_widget.severity_changed.connect(
                        lambda value, cav=cavity: self._on_severity_change(
                            cav, value
                        )
                    )

        print(
            f"✓ Audio manager connected to {cavity_count} cavities via signals"
        )

    def _play_alarm_sound(self):
        """Play alarm sound or system beep"""
        if self.alarm_sound:
            self.alarm_sound.play()
        else:
            from PyQt5.QtWidgets import QApplication

            QApplication.beep()
            QTimer.singleShot(200, QApplication.beep)

    def _play_warning_sound(self):
        """Play warning sound or system beep"""
        if self.warning_sound:
            self.warning_sound.play()
        else:
            from PyQt5.QtWidgets import QApplication

            QApplication.beep()

    def acknowledge_alarm(self, cavity):
        """
        Acknowledge an alarm to stop escalation (legacy method).
        Calls acknowledge_cavity internally.
        """
        cavity_id = f"{cavity.cryomodule.name}_{cavity.number}"
        self.acknowledge_cavity(cavity_id)
        print(f"✓ Acknowledged (legacy): {cavity_id}")
