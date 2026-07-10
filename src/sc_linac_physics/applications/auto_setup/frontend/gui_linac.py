import dataclasses
from typing import Optional, Callable, Dict, List

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QPushButton,
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
)

from sc_linac_physics.applications.auto_setup.frontend.gui_cryomodule import (
    GUICryomodule,
)
from sc_linac_physics.applications.auto_setup.frontend.style import (
    CARD_BG,
    ACCENT_TEXT,
    LINAC_COLORS,
    abort_button_stylesheet,
    button_stylesheet,
    card_stylesheet,
    chip_stylesheet,
)
from sc_linac_physics.applications.auto_setup.frontend.utils import Settings
from sc_linac_physics.applications.auto_setup.frontend.widgets import (
    FlowLayout,
    HeightForWidthWidget,
)
from sc_linac_physics.utils.sc_linac.linac_utils import (
    STATUS_READY_VALUE,
    STATUS_RUNNING_VALUE,
    STATUS_ERROR_VALUE,
)
from sc_linac_physics.utils.qt import make_sanity_check_popup


@dataclasses.dataclass
class GUILinac:
    name: str
    idx: int
    cryomodule_names: List[str]
    settings: Settings
    on_tile_clicked: Optional[Callable[["GUILinac"], None]] = None
    on_cm_selected: Optional[Callable[[str, "GUILinac"], None]] = None
    on_machine_cm_status_changed: Optional[Callable[[str, int, bool], None]] = (
        None
    )
    on_machine_cav_status_changed: Optional[
        Callable[[str, int, int, bool], None]
    ] = None

    def __post_init__(self):
        self.is_locked: bool = False
        self._pre_cascade_locked: set = set()
        self._aux_lock_buttons: List["QPushButton"] = []
        self._cm_statuses: Dict[str, int] = {
            name: STATUS_READY_VALUE for name in self.cryomodule_names
        }

        self.gui_cryomodules: Dict[str, GUICryomodule] = {}
        for cm_name in self.cryomodule_names:
            gui_cm = GUICryomodule(
                linac_idx=self.idx,
                name=cm_name,
                settings=self.settings,
                on_status_changed=self._on_cm_status_changed,
                on_cav_status_changed=self._make_cav_callback(cm_name),
            )
            self.gui_cryomodules[cm_name] = gui_cm

        self.tile = self._build_tile()
        self.detail_panel = self._build_detail_panel()
        self.detail_panel.hide()

    @staticmethod
    def _chip_text(cm_name: str, status: int, locked: bool) -> str:
        if locked:
            return f"\U0001f512CM{cm_name}"
        if status == STATUS_RUNNING_VALUE:
            return f"⟳CM{cm_name}"
        if status == STATUS_ERROR_VALUE:
            return f"✗CM{cm_name}"
        return f"CM{cm_name}"

    def _build_tile(self) -> QFrame:
        tile = QFrame()
        tile.setFrameShape(QFrame.StyledPanel)
        tile.setStyleSheet(card_stylesheet(STATUS_READY_VALUE))
        tile.setCursor(Qt.PointingHandCursor)
        tile.mousePressEvent = lambda event: self._on_tile_clicked_handler()
        layout = QVBoxLayout(tile)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)
        title = QLabel(self.name)
        title.setStyleSheet(
            f"color: {ACCENT_TEXT}; font-weight: bold; font-size: 10px;"
        )
        layout.addWidget(title)
        n = len(self.cryomodule_names)
        cols = min(n, 4)
        chip_slot = 60
        chips_w = max(chip_slot, cols * chip_slot - 3)
        chips_widget = HeightForWidthWidget()
        chips_widget.setFixedWidth(chips_w)
        flow = FlowLayout(chips_widget, h_spacing=3, v_spacing=3)
        self._cm_chips: Dict[str, QLabel] = {}
        for cm_name in self.cryomodule_names:
            chip = QLabel(self._chip_text(cm_name, STATUS_READY_VALUE, False))
            chip.setStyleSheet(chip_stylesheet(STATUS_READY_VALUE))
            self._cm_chips[cm_name] = chip
            flow.addWidget(chip)
        layout.addWidget(chips_widget)
        return tile

    def _build_detail_panel(self) -> QFrame:
        color = LINAC_COLORS[self.name]
        panel = QFrame()
        panel.setStyleSheet(
            f"QFrame {{ background: {CARD_BG}; border: 2px solid {color}; "
            f"border-radius: 6px; }}" + button_stylesheet()
        )
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 8, 10, 10)
        ctrl_row = QHBoxLayout()
        linac_label = QLabel(self.name)
        linac_label.setStyleSheet(
            f"color: {color}; font-weight: bold; border: none;"
        )
        ctrl_row.addWidget(linac_label)
        self.setup_button = QPushButton("Set Up")
        self.setup_button.clicked.connect(self.trigger_setup)
        self.shutdown_button = QPushButton("Shut Down")
        self.shutdown_button.clicked.connect(self.trigger_shutdown)
        self.abort_button = QPushButton("Abort")
        self.abort_button.setStyleSheet(abort_button_stylesheet())
        self.abort_button.clicked.connect(self.trigger_abort)
        self.lock_linac_button = QPushButton("\U0001f512 Lock")
        self.lock_linac_button.setCheckable(True)
        self.lock_linac_button.clicked.connect(self._on_lock_linac_clicked)
        ctrl_row.addWidget(self.setup_button)
        ctrl_row.addWidget(self.shutdown_button)
        ctrl_row.addWidget(self.abort_button)
        ctrl_row.addWidget(self.lock_linac_button)
        ctrl_row.addStretch()
        layout.addLayout(ctrl_row)
        self._cms_widget = HeightForWidthWidget()
        cms_flow = FlowLayout(self._cms_widget, h_spacing=10, v_spacing=10)
        for cm_name in self.cryomodule_names:
            gui_cm = self.gui_cryomodules[cm_name]
            gui_cm.tile.mousePressEvent = (
                lambda event, n=cm_name: self._on_cm_tile_clicked(n)
            )
            cms_flow.addWidget(gui_cm.tile)
        layout.addWidget(self._cms_widget, 1)
        return panel

    def _make_cav_callback(self, cm_name: str):
        def _cb(cav_num: int, status: int, locked: bool):
            self._on_cav_status_changed(cm_name, cav_num, status, locked)

        return _cb

    def _on_tile_clicked_handler(self):
        if self.on_tile_clicked:
            self.on_tile_clicked(self)

    def _on_cm_tile_clicked(self, cm_name: str):
        if self.on_cm_selected:
            self.on_cm_selected(cm_name, self)

    def _on_cm_status_changed(self, cm_name: str, status: int):
        self._cm_statuses[cm_name] = status
        locked = self.gui_cryomodules[cm_name].is_locked
        self._cm_chips[cm_name].setText(
            self._chip_text(cm_name, status, locked)
        )
        self._cm_chips[cm_name].setStyleSheet(chip_stylesheet(status, locked))
        agg = self._aggregate_status()
        self.tile.setStyleSheet(card_stylesheet(agg, self.is_locked))
        if self.on_machine_cm_status_changed:
            self.on_machine_cm_status_changed(cm_name, status, locked)

    def _aggregate_status(self) -> int:
        statuses = list(self._cm_statuses.values())
        if STATUS_ERROR_VALUE in statuses:
            return STATUS_ERROR_VALUE
        if STATUS_RUNNING_VALUE in statuses:
            return STATUS_RUNNING_VALUE
        return STATUS_READY_VALUE

    def add_lock_button(self, btn: "QPushButton"):
        self._aux_lock_buttons.append(btn)

    def _sync_lock_buttons(self, checked: bool):
        self.lock_linac_button.setChecked(checked)
        for btn in self._aux_lock_buttons:
            btn.setChecked(checked)

    def _on_lock_linac_clicked(self):
        if self.is_locked:
            popup = make_sanity_check_popup(
                f"Unlock {self.name}? Make sure no one is working on it."
            )
            if popup.exec() == QMessageBox.Yes:
                self._unlock_linac()
            else:
                self._sync_lock_buttons(True)
        else:
            self._lock_linac()

    def _lock_linac(self):
        if self.is_locked:
            return
        self._pre_cascade_locked = {
            name for name, cm in self.gui_cryomodules.items() if cm.is_locked
        }
        self.is_locked = True
        self._sync_lock_buttons(True)
        for gui_cm in self.gui_cryomodules.values():
            gui_cm.lock()
        self.tile.setStyleSheet(card_stylesheet(self._aggregate_status(), True))
        if self.on_machine_cm_status_changed:
            for cm_name in self.gui_cryomodules:
                self.on_machine_cm_status_changed(
                    cm_name, self._cm_statuses[cm_name], True
                )

    def _unlock_linac(self):
        self.is_locked = False
        self._sync_lock_buttons(False)
        for name, gui_cm in self.gui_cryomodules.items():
            if name not in self._pre_cascade_locked:
                gui_cm.unlock_no_confirm()
        self.tile.setStyleSheet(
            card_stylesheet(self._aggregate_status(), False)
        )
        if self.on_machine_cm_status_changed:
            for cm_name, gui_cm in self.gui_cryomodules.items():
                self.on_machine_cm_status_changed(
                    cm_name, self._cm_statuses[cm_name], gui_cm.is_locked
                )

    def _on_cav_status_changed(
        self, cm_name: str, cav_num: int, status: int, locked: bool
    ):
        if self.on_machine_cav_status_changed:
            self.on_machine_cav_status_changed(cm_name, cav_num, status, locked)

    def trigger_setup(self):
        popup = make_sanity_check_popup(
            f"Set up all unlocked cavities in {self.name}?"
        )
        if popup.exec() == QMessageBox.Yes:
            for gui_cm in self.gui_cryomodules.values():
                gui_cm.trigger_setup_all()

    def trigger_shutdown(self):
        popup = make_sanity_check_popup(
            f"Shut down all unlocked cavities in {self.name}?"
        )
        if popup.exec() == QMessageBox.Yes:
            for gui_cm in self.gui_cryomodules.values():
                gui_cm.trigger_shutdown_all()

    def trigger_abort(self):
        popup = make_sanity_check_popup(
            f"Abort all running setup operations in {self.name}?"
        )
        if popup.exec() == QMessageBox.Yes:
            for gui_cm in self.gui_cryomodules.values():
                gui_cm.trigger_abort_all()
