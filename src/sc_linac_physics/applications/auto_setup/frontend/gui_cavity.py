import dataclasses
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Callable

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QPushButton,
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
)
from edmbutton import PyDMEDMDisplayButton
from pydm.widgets import PyDMLabel, PyDMSpinbox

from sc_linac_physics.applications.auto_setup.backend.setup_cavity import (
    SetupCavity,
)
from sc_linac_physics.applications.auto_setup.backend.setup_machine import (
    SETUP_MACHINE,
)
from sc_linac_physics.applications.auto_setup.frontend.style import (
    CARD_BG,
    CARD_BORDER,
    CARD_TEXT,
    MUTED_TEXT,
    NOTE_TEXT,
    abort_button_stylesheet,
    card_stylesheet,
    status_icon,
    status_text_color,
    step_label_for_progress,
)
from sc_linac_physics.applications.auto_setup.frontend.utils import Settings
from sc_linac_physics.utils.epics.exceptions import (
    PVConnectionError,
    PVGetError,
    PVPutError,
)
from sc_linac_physics.utils.qt import make_sanity_check_popup
from sc_linac_physics.utils.sc_linac.linac_utils import STATUS_RUNNING_VALUE

_executor = ThreadPoolExecutor(max_workers=os.cpu_count() or 4)


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


class _NoteEdit(QPlainTextEdit):
    """Wrapping plain-text editor bound to a string PV.

    Reads arrive via an embedded _ChannelWatcher; starts read-only.
    on_commit is called when the user finishes editing (focus-out while editable).
    """

    def __init__(self, note_pv: str, on_commit, parent=None):
        super().__init__(parent)
        self._on_commit = on_commit
        self.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.setFixedHeight(44)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setPlaceholderText("notes…")
        self.setReadOnly(True)
        self._watcher = _ChannelWatcher(
            init_channel=note_pv,
            callback=self._on_pv_update,
        )

    def _on_pv_update(self, value):
        if value is None:
            return
        if hasattr(value, "tobytes"):
            text = (
                value.tobytes().decode("utf-8", errors="replace").rstrip("\x00")
            )
        else:
            text = str(value)
        if text != self.toPlainText():
            self.setPlainText(text)

    def focusOutEvent(self, event):
        if not self.isReadOnly():
            self._on_commit()
        super().focusOutEvent(event)


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
        self.lock_button.setFixedSize(32, 24)
        self.lock_button.setCheckable(True)
        self.lock_button.setStyleSheet(
            f"QPushButton {{ border: 1px solid {CARD_BORDER}; background: {CARD_BG}; "
            f"border-radius: 3px; font-size: 15px; }}"
            f"QPushButton:hover {{ border-color: {MUTED_TEXT}; }}"
            f"QPushButton:checked {{ background: {CARD_BORDER}; border-color: {MUTED_TEXT}; }}"
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

        _field_label_style = f"color: {MUTED_TEXT}; font-size: 10px; font-weight: 600; border: none;"
        amp_row = QHBoxLayout()
        acon_lbl = QLabel("ACON")
        acon_lbl.setStyleSheet(_field_label_style)
        amp_row.addWidget(acon_lbl)
        self.acon_edit = PyDMSpinbox(init_channel=self.prefix + "ACON")
        self.acon_edit.showStepExponent = False
        self.acon_edit.alarmSensitiveBorder = False
        self.acon_edit.alarmSensitiveContent = False
        self.acon_edit.setDecimals(2)
        # Prevent PV ctrl-limits (0/0 in fake protocol) from clamping the value
        self.acon_edit.userDefinedLimits = True
        self.acon_edit.setRange(0.0, 25.0)
        self.acon_edit.setFixedWidth(90)
        self.aact_label = PyDMLabel(init_channel=self.prefix + "AACTMEAN")
        self.aact_label.alarmSensitiveBorder = True
        self.aact_label.alarmSensitiveContent = True
        self.aact_label.showUnits = True
        self.aact_label.precisionFromPV = False
        self.aact_label.precision = 2
        amp_row.addWidget(self.acon_edit)
        aact_lbl = QLabel("AACT")
        aact_lbl.setStyleSheet(_field_label_style)
        amp_row.addWidget(aact_lbl)
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

        self.note_edit = _NoteEdit(
            note_pv=self.cavity.note_pv,
            on_commit=self._commit_note,
        )
        self.note_edit.setStyleSheet(
            f"QPlainTextEdit {{ color: {NOTE_TEXT}; font-size: 10px; "
            f"background: transparent; border: none; "
            f"border-bottom: 1px solid {CARD_BORDER}; padding: 1px 0; }}"
            f"QPlainTextEdit:read-only {{ border-bottom-color: transparent; }}"
            f"QPlainTextEdit:focus {{ border-bottom-color: {MUTED_TEXT}; }}"
        )
        self._note_pencil_btn = QPushButton("Edit")
        self._note_pencil_btn.setFixedSize(36, 20)
        self._note_pencil_btn.setCheckable(True)
        self._note_pencil_btn.setStyleSheet(
            f"QPushButton {{ border: 1px solid {CARD_BORDER}; background: {CARD_BG}; "
            f"color: {MUTED_TEXT}; border-radius: 3px; font-size: 10px; padding: 0; }}"
            f"QPushButton:hover {{ border-color: {MUTED_TEXT}; color: {CARD_TEXT}; }}"
            f"QPushButton:checked {{ background: {CARD_BORDER}; color: {CARD_TEXT}; }}"
        )
        self._note_pencil_btn.clicked.connect(self._on_note_pencil_clicked)
        note_row = QHBoxLayout()
        note_row.setSpacing(4)
        note_row.addWidget(self.note_edit, 1)
        note_row.addWidget(self._note_pencil_btn, 0, Qt.AlignTop)
        layout.addLayout(note_row)
        layout.addWidget(self.note_edit._watcher)

        btn_row = QHBoxLayout()
        self.setup_button = QPushButton("Set Up")
        self.setup_button.clicked.connect(self.trigger_setup)
        self.shutdown_button = QPushButton("Turn Off")
        self.shutdown_button.clicked.connect(self.trigger_shutdown)
        self.abort_button = QPushButton("Abort")
        self.abort_button.setStyleSheet(abort_button_stylesheet())
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
            popup = make_sanity_check_popup(
                f"Unlock CAV {self.number}? Make sure no one is working on it."
            )
            confirmed = popup.exec() == QMessageBox.Yes
            if confirmed:
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
        self._note_pencil_btn.setEnabled(not locked)
        if locked and not self.note_edit.isReadOnly():
            self._commit_note()
        if self.on_status_changed:
            self.on_status_changed(self.number, self._status)

    def _on_note_pencil_clicked(self):
        if self._note_pencil_btn.isChecked():
            self.note_edit.setReadOnly(False)
            self._note_pencil_btn.setText("Save")
            self.note_edit.setFocus()
        else:
            self._commit_note()

    def _commit_note(self):
        self.note_edit.setReadOnly(True)
        self._note_pencil_btn.setChecked(False)
        self._note_pencil_btn.setText("Edit")
        self.cavity.note_pv_obj.put(self.note_edit.toPlainText())

    def lock(self):
        self._set_locked(True)

    def unlock_no_confirm(self):
        self._set_locked(False)

    def trigger_setup(self):
        if self.locked:
            return
        # Read checkbox state now on the main thread; EPICS I/O runs off it.
        ssa_cal = self.settings.ssa_cal_checkbox.isChecked()
        auto_tune = self.settings.auto_tune_checkbox.isChecked()
        cav_char = self.settings.cav_char_checkbox.isChecked()
        rf_ramp = self.settings.rf_ramp_checkbox.isChecked()
        cav = self.cavity

        def _run():
            try:
                import epics

                epics.ca.use_initial_context()
            except Exception:
                pass
            try:
                if cav.script_is_running:
                    cav.status_message = f"{cav} script already running"
                    return
                if not cav.is_online:
                    cav.status_message = f"{cav} not online, skipping"
                    return
                cav.ssa_cal_requested = ssa_cal
                cav.auto_tune_requested = auto_tune
                cav.cav_char_requested = cav_char
                cav.rf_ramp_requested = rf_ramp
                cav.trigger_start()
            except (PVConnectionError, PVGetError, PVPutError) as e:
                cav.status_message = f"PV error: {e}"

        _executor.submit(_run)

    def trigger_shutdown(self):
        if self.locked:
            return
        cav = self.cavity

        def _run():
            try:
                import epics

                epics.ca.use_initial_context()
            except Exception:
                pass
            try:
                if cav.script_is_running:
                    cav.status_message = f"{cav} script already running"
                    return
                cav.trigger_shutdown()
            except (PVConnectionError, PVGetError, PVPutError) as e:
                cav.status_message = f"PV error: {e}"

        _executor.submit(_run)

    def request_abort(self):
        _executor.submit(self.cavity.trigger_abort)
