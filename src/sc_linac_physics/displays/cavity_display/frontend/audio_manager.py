# Update audio_manager.py
import os
import time

from PyQt5.QtCore import QTimer, QObject, pyqtSignal
from PyQt5.QtMultimedia import QSound


class AudioAlertManager(QObject):
    """Manages audio alerts with escalation and acknowledgment"""

    new_alarm = pyqtSignal(object)  # Emits cavity when new alarm

    def __init__(self, gui_machine, parent=None):
        super().__init__(parent)
        self.gui_machine = gui_machine

        # Track alerted cavities
        self.alerted_alarms = set()
        self.alerted_warnings = set()
        self.unacknowledged_alarms = {}  # cavity_id: timestamp

        # Setup sounds with QSound (simpler, more reliable)
        self.alarm_sound = None
        self.warning_sound = None
        self.escalation_sound = None

        # Load sound files
        self._load_sounds()

        # Escalation timer - check every 30 seconds
        self.escalation_timer = QTimer()
        self.escalation_timer.timeout.connect(self._check_escalation)
        self.escalation_timer.start(30000)

        # Connect to all cavities
        self._connect_to_cavities()

    def _load_sounds(self):
        """Load audio files if they exist, fallback to system beep"""
        # Get the directory where this file is located
        base_path = os.path.dirname(os.path.abspath(__file__))

        # Try to load custom sounds from sounds subdirectory
        alarm_path = os.path.join(base_path, "sounds", "alarm.wav")
        warning_path = os.path.join(base_path, "sounds", "warning.wav")
        escalation_path = os.path.join(base_path, "sounds", "urgent.wav")

        print(f"Looking for sounds in: {os.path.join(base_path, 'sounds')}")

        if os.path.exists(alarm_path):
            self.alarm_sound = QSound(alarm_path)
            print(f"✓ Loaded alarm sound: {alarm_path}")
        else:
            print(
                f"✗ No alarm sound found at {alarm_path}, will use system beep"
            )

        if os.path.exists(warning_path):
            self.warning_sound = QSound(warning_path)
            print(f"✓ Loaded warning sound: {warning_path}")
        else:
            print(
                f"✗ No warning sound found at {warning_path}, will use system beep"
            )

        if os.path.exists(escalation_path):
            self.escalation_sound = QSound(escalation_path)
            print(f"✓ Loaded escalation sound: {escalation_path}")

    def _connect_to_cavities(self):
        """Connect to all cavity severity changes via signals"""
        cavity_count = 0

        linacs = self.gui_machine.linacs
        if isinstance(linacs, dict):
            linacs = linacs.values()

        for linac in linacs:
            cryomodules = linac.cryomodules
            if isinstance(cryomodules, dict):
                cryomodules = cryomodules.values()

            for cm in cryomodules:
                cavities = cm.cavities
                if isinstance(cavities, dict):
                    cavities = cavities.values()

                for cavity in cavities:
                    cavity_count += 1
                    # Connect to the severity_changed signal
                    cavity.cavity_widget.severity_changed.connect(
                        lambda value, cav=cavity: self._on_severity_change(
                            cav, value
                        )
                    )

        print(
            f"✓ Audio manager connected to {cavity_count} cavities via signals"
        )

    def _on_severity_change(self, cavity, severity):
        """Handle severity change for a cavity"""
        cavity_id = f"{cavity.cryomodule.name}_{cavity.number}"

        print(
            f"Audio manager: CM{cavity.cryomodule.name} Cav{cavity.number} severity={severity}"
        )

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

    def _play_alarm_sound(self):
        """Play alarm sound or system beep"""
        if self.alarm_sound:
            self.alarm_sound.play()
        else:
            # Fallback to system beep
            from PyQt5.QtWidgets import QApplication

            QApplication.beep()
            # Double beep for alarm
            QTimer.singleShot(200, QApplication.beep)

    def _play_warning_sound(self):
        """Play warning sound or system beep"""
        if self.warning_sound:
            self.warning_sound.play()
        else:
            # Fallback to single system beep
            from PyQt5.QtWidgets import QApplication

            QApplication.beep()

    def _check_escalation(self):
        """Play escalation sound for unacknowledged alarms > 2 minutes"""
        current_time = time.time()
        for cavity_id, timestamp in list(self.unacknowledged_alarms.items()):
            if current_time - timestamp > 120:  # 2 minutes
                if self.escalation_sound:
                    self.escalation_sound.play()
                else:
                    # Triple beep for escalation
                    from PyQt5.QtWidgets import QApplication

                    QApplication.beep()
                    QTimer.singleShot(200, QApplication.beep)
                    QTimer.singleShot(400, QApplication.beep)
                print(
                    f"⚠️ ESCALATION: {cavity_id} unacknowledged for 2+ minutes"
                )

    def acknowledge_alarm(self, cavity):
        """Acknowledge an alarm to stop escalation"""
        cavity_id = f"{cavity.cryomodule.name}_{cavity.number}"
        self.unacknowledged_alarms.pop(cavity_id, None)
        print(f"✓ Acknowledged: {cavity_id}")
