import dataclasses
from typing import Optional, Callable

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QPushButton,
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
)
from edmbutton import PyDMEDMDisplayButton
from pydm.widgets import PyDMLabel
from pydm.widgets.display_format import DisplayFormat
from pydm.widgets.line_edit import PyDMLineEdit

from sc_linac_physics.applications.auto_setup.backend.setup_cavity import (
    SetupCavity,
)
from sc_linac_physics.applications.auto_setup.backend.setup_machine import (
    SETUP_MACHINE,
)
from sc_linac_physics.applications.auto_setup.frontend.style import (
    CARD_TEXT,
    MUTED_TEXT,
    NOTE_TEXT,
    card_stylesheet,
    status_icon,
    status_text_color,
    step_label_for_progress,
)
from sc_linac_physics.applications.auto_setup.frontend.utils import Settings
from sc_linac_physics.utils.sc_linac.linac_utils import STATUS_RUNNING_VALUE


class _ChannelWatcher(PyDMLabel):
    """Zero-size PyDMLabel that delivers channel updates to a callback.

    bare PyDMChannel.value_slot does not receive live value changes;
    PyDMWidget subclasses do.
    """

    def __init__(self, init_channel: str, callback):
        super().__init__(init_channel=init_channel)
        self._cb = callback
        self.setFixedSize(0, 0)

    def value_changed(self, new_val):
        self._cb(new_val)


class _StatusMsgLabel(PyDMLabel):
    """PyDMLabel that correctly decodes waveform CHAR arrays (FTVL=CHAR)."""

    def value_changed(self, new_val):
        if hasattr(new_val, "tobytes"):
            self.setText(
                new_val.tobytes()
                .decode("utf-8", errors="replace")
                .rstrip("\x00")
            )
        else:
            super().value_changed(new_val)


@dataclasses.dataclass
class GUICavity:
    number: int
    prefix: str
    cm: str
    settings: Settings
    on_status_changed: Optional[Callable[[int, int], None]] = None

    def __post_init__(self):
        self._cavity: Optional[SetupCavity] = None
        self._status: int = 0
        self.locked: bool = False

        self.frame = QFrame()
        self.frame.setFrameShape(QFrame.StyledPanel)
        self.frame.setStyleSheet(card_stylesheet(self._status))
        self.frame.setFixedWidth(260)
        layout = QVBoxLayout(self.frame)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        title_row = QHBoxLayout()
        self._status_icon_label = QLabel(status_icon(self._status))
        self._status_icon_label.setStyleSheet(
            f"color: {status_text_color(self._status)}; font-weight: bold;"
        )
        self._cav_name_label = QLabel(f"CAV {self.number}")
        self._cav_name_label.setStyleSheet(
            f"color: {CARD_TEXT}; font-weight: bold;"
        )
        self.lock_button = QPushButton("\U0001f512")
        self.lock_button.setFixedSize(24, 24)
        self.lock_button.setCheckable(True)
        self.lock_button.setStyleSheet(
            "QPushButton { border: none; background: transparent; font-size: 12px; }"
        )
        self.lock_button.clicked.connect(self._on_lock_clicked)
        self.expert_screen_button = PyDMEDMDisplayButton()
        self.expert_screen_button.filenames = [
            "$EDM/llrf/rf_srf_cavity_main.edl"
        ]
        self.expert_screen_button.macros = (
            self.cavity.edm_macro_string + ",SELTAB=0,SELCHAR=3"
        )
        self.expert_screen_button.setFixedSize(24, 24)
        title_row.addWidget(self._status_icon_label)
        title_row.addWidget(self._cav_name_label)
        title_row.addStretch()
        title_row.addWidget(self.lock_button)
        title_row.addWidget(self.expert_screen_button)
        layout.addLayout(title_row)

        amp_row = QHBoxLayout()
        amp_row.addWidget(QLabel("ACON"))
        self.acon_edit = PyDMLineEdit(init_channel=self.prefix + "ACON")
        self.acon_edit.precisionFromPV = False
        self.acon_edit.precision = 2
        self.acon_edit.showUnits = True
        self.acon_edit.alarmSensitiveBorder = True
        self.acon_edit.alarmSensitiveContent = True
        self.acon_edit.setFixedWidth(70)
        self.aact_label = PyDMLabel(init_channel=self.prefix + "AACTMEAN")
        self.aact_label.alarmSensitiveBorder = True
        self.aact_label.alarmSensitiveContent = True
        self.aact_label.showUnits = True
        self.aact_label.precisionFromPV = False
        self.aact_label.precision = 2
        amp_row.addWidget(self.acon_edit)
        amp_row.addWidget(QLabel("AACT"))
        amp_row.addWidget(self.aact_label)
        amp_row.addStretch()
        layout.addLayout(amp_row)

        self._step_label = QLabel("SSA Cal \xb7 0%")
        self._step_label.setStyleSheet(
            f"color: {MUTED_TEXT}; font-style: italic; font-size: 10px;"
        )
        layout.addWidget(self._step_label)

        self.status_label = _StatusMsgLabel(
            init_channel=self.cavity.status_msg_pv
        )
        self.status_label.alarmSensitiveContent = False
        self.status_label.alarmSensitiveBorder = False
        self.status_label.setAlignment(Qt.AlignLeft)
        self.status_label.setWordWrap(True)
        self.status_label.setMinimumHeight(36)
        self.status_label.setStyleSheet(
            f"color: {status_text_color(self._status, self.locked)};"
        )
        layout.addWidget(self.status_label)

        self.note_label = PyDMLabel(init_channel=self.cavity.note_pv)
        self.note_label.displayFormat = DisplayFormat.String
        self.note_label.setWordWrap(True)
        self.note_label.setStyleSheet(f"color: {NOTE_TEXT}; font-size: 10px;")

        btn_row = QHBoxLayout()
        self.setup_button = QPushButton("Set Up")
        self.setup_button.clicked.connect(self.trigger_setup)
        self.shutdown_button = QPushButton("Turn Off")
        self.shutdown_button.clicked.connect(self.trigger_shutdown)
        self.abort_button = QPushButton("Abort")
        self.abort_button.setStyleSheet("color: #e08090;")
        self.abort_button.clicked.connect(self.request_abort)
        btn_row.addWidget(self.setup_button)
        btn_row.addWidget(self.shutdown_button)
        btn_row.addWidget(self.abort_button)
        layout.addLayout(btn_row)

        self._status_watcher = _ChannelWatcher(
            init_channel=self.cavity.status_pv,
            callback=self._handle_status_value,
        )
        layout.addWidget(self._status_watcher)
        self._progress_watcher = _ChannelWatcher(
            init_channel=self.cavity.progress_pv,
            callback=self._handle_progress_value,
        )
        layout.addWidget(self._progress_watcher)

    @property
    def cavity(self) -> SetupCavity:
        if not self._cavity:
            self._cavity = SETUP_MACHINE.cryomodules[self.cm].cavities[
                self.number
            ]
        return self._cavity

    def _handle_status_value(self, value):
        if value is None:
            return
        status = int(value)
        self._status = status
        color = status_text_color(status, self.locked)
        self.frame.setStyleSheet(card_stylesheet(status, self.locked))
        self._status_icon_label.setText(status_icon(status))
        self._status_icon_label.setStyleSheet(
            f"color: {color}; font-weight: bold;"
        )
        self.status_label.setStyleSheet(f"color: {color};")
        self.setup_button.setEnabled(
            not self.locked and status != STATUS_RUNNING_VALUE
        )
        if self.on_status_changed:
            self.on_status_changed(self.number, status)

    def _handle_progress_value(self, value):
        if value is None:
            return
        self._step_label.setText(step_label_for_progress(int(value)))

    def _on_lock_clicked(self):
        if self.locked:
            reply = QMessageBox.question(
                self.frame,
                "Unlock Cavity",
                f"Unlock CAV {self.number}? Make sure no one is working on it.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                self._set_locked(False)
            else:
                self.lock_button.setChecked(True)
        else:
            self._set_locked(True)

    def _set_locked(self, locked: bool):
        self.locked = locked
        color = status_text_color(self._status, locked)
        self.lock_button.setChecked(locked)
        self.frame.setStyleSheet(card_stylesheet(self._status, locked))
        self._status_icon_label.setStyleSheet(
            f"color: {color}; font-weight: bold;"
        )
        self.status_label.setStyleSheet(f"color: {color};")
        self.setup_button.setEnabled(
            not locked and self._status != STATUS_RUNNING_VALUE
        )
        self.shutdown_button.setEnabled(not locked)
        self.acon_edit.setEnabled(not locked)
        if self.on_status_changed:
            self.on_status_changed(self.number, self._status)

    def lock(self):
        self._set_locked(True)

    def unlock_no_confirm(self):
        self._set_locked(False)

    def trigger_setup(self):
        if self.locked:
            return
        if self.cavity.script_is_running:
            self.cavity.status_message = f"{self.cavity} script already running"
            return
        if not self.cavity.is_online:
            self.cavity.status_message = f"{self.cavity} not online, skipping"
            return
        self.cavity.ssa_cal_requested = (
            self.settings.ssa_cal_checkbox.isChecked()
        )
        self.cavity.auto_tune_requested = (
            self.settings.auto_tune_checkbox.isChecked()
        )
        self.cavity.cav_char_requested = (
            self.settings.cav_char_checkbox.isChecked()
        )
        self.cavity.rf_ramp_requested = (
            self.settings.rf_ramp_checkbox.isChecked()
        )
        self.cavity.trigger_start()

    def trigger_shutdown(self):
        if self.locked:
            return
        if self.cavity.script_is_running:
            self.cavity.status_message = f"{self.cavity} script already running"
            return
        self.cavity.trigger_shutdown()

    def request_abort(self):
        self.cavity.trigger_abort()
