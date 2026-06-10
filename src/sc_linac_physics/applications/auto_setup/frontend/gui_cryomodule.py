import dataclasses
from typing import Optional, Callable, Dict

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QPushButton,
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QMessageBox,
    QScrollArea,
    QWidget,
)

from sc_linac_physics.applications.auto_setup.frontend.widgets import (
    FlowLayout,
    HeightForWidthWidget,
)

from sc_linac_physics.applications.auto_setup.frontend.gui_cavity import (
    GUICavity,
)
from sc_linac_physics.applications.auto_setup.frontend.style import (
    CARD_BG,
    CARD_TEXT,
    ACCENT_BORDER,
    card_stylesheet,
    dot_stylesheet,
)
from sc_linac_physics.applications.auto_setup.frontend.utils import Settings
from sc_linac_physics.utils.sc_linac.linac_utils import (
    STATUS_READY_VALUE,
    STATUS_RUNNING_VALUE,
    STATUS_ERROR_VALUE,
)


@dataclasses.dataclass
class GUICryomodule:
    linac_idx: int
    name: str
    settings: Settings
    on_status_changed: Optional[Callable[[str, int], None]] = None

    def __post_init__(self):
        self.is_locked: bool = False
        self._pre_cascade_locked: set = set()
        self._cavity_statuses: Dict[int, int] = {
            n: STATUS_READY_VALUE for n in range(1, 9)
        }

        self.gui_cavities: Dict[int, GUICavity] = {}
        for cav_num in range(1, 9):
            gui_cav = GUICavity(
                number=cav_num,
                prefix=f"ACCL:L{self.linac_idx}B:{self.name}{cav_num}0:",
                cm=self.name,
                settings=self.settings,
                on_status_changed=self._on_cavity_status_changed,
            )
            self.gui_cavities[cav_num] = gui_cav

        self.tile = self._build_tile()
        self.detail_panel = self._build_detail_panel()
        self.detail_panel.hide()

    def _build_tile(self) -> QFrame:
        tile = QFrame()
        tile.setFrameShape(QFrame.StyledPanel)
        tile.setStyleSheet(card_stylesheet(STATUS_READY_VALUE))
        tile.setCursor(Qt.PointingHandCursor)
        layout = QVBoxLayout(tile)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(3)
        name_label = QLabel(f"CM{self.name}")
        name_label.setStyleSheet(
            f"color: {CARD_TEXT}; font-weight: bold; font-size: 11px;"
        )
        layout.addWidget(name_label)
        dot_container = QWidget()
        dot_container.setFixedSize(46, 24)
        dot_grid = QGridLayout(dot_container)
        dot_grid.setContentsMargins(0, 0, 0, 0)
        dot_grid.setHorizontalSpacing(2)
        dot_grid.setVerticalSpacing(4)
        self._dots: Dict[int, QLabel] = {}
        for i, cav_num in enumerate(range(1, 9)):
            row, col = i // 4, i % 4
            dot = QLabel()
            dot.setFixedSize(10, 10)
            dot.setStyleSheet(dot_stylesheet(STATUS_READY_VALUE))
            self._dots[cav_num] = dot
            dot_grid.addWidget(dot, row, col)
        layout.addWidget(dot_container)
        return tile

    def _build_detail_panel(self) -> QFrame:
        panel = QFrame()
        panel.setStyleSheet(
            f"QFrame {{ background: {CARD_BG}; border: 1px solid {ACCENT_BORDER}; "
            f"border-radius: 6px; }}"
        )
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 8, 10, 8)
        ctrl_row = QHBoxLayout()
        cm_label = QLabel(f"CM{self.name}")
        cm_label.setStyleSheet(f"color: {CARD_TEXT}; font-weight: bold;")
        ctrl_row.addWidget(cm_label)
        self.setup_all_button = QPushButton("Set Up All")
        self.setup_all_button.clicked.connect(self.trigger_setup_all)
        self.shutdown_all_button = QPushButton("Shut Down All")
        self.shutdown_all_button.clicked.connect(self.trigger_shutdown_all)
        self.abort_all_button = QPushButton("Abort All")
        self.abort_all_button.setStyleSheet("color: #e08090;")
        self.abort_all_button.clicked.connect(self.trigger_abort_all)
        self.lock_cm_button = QPushButton("\U0001f512 Lock CM")
        self.lock_cm_button.setCheckable(True)
        self.lock_cm_button.clicked.connect(self._on_lock_cm_clicked)
        ctrl_row.addWidget(self.setup_all_button)
        ctrl_row.addWidget(self.shutdown_all_button)
        ctrl_row.addWidget(self.abort_all_button)
        ctrl_row.addWidget(self.lock_cm_button)
        ctrl_row.addStretch()
        layout.addLayout(ctrl_row)
        cav_widget = HeightForWidthWidget()
        cav_flow = FlowLayout(cav_widget, h_spacing=6, v_spacing=6)
        for cav_num in range(1, 9):
            cav_flow.addWidget(self.gui_cavities[cav_num].frame)
        cav_scroll = QScrollArea()
        cav_scroll.setWidgetResizable(True)
        cav_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        cav_scroll.setFrameShape(QFrame.NoFrame)
        cav_scroll.setWidget(cav_widget)
        layout.addWidget(cav_scroll, 1)
        return panel

    def _aggregate_status(self) -> int:
        statuses = list(self._cavity_statuses.values())
        if STATUS_ERROR_VALUE in statuses:
            return STATUS_ERROR_VALUE
        if STATUS_RUNNING_VALUE in statuses:
            return STATUS_RUNNING_VALUE
        return STATUS_READY_VALUE

    def _on_cavity_status_changed(self, cav_num: int, status: int):
        self._cavity_statuses[cav_num] = status
        self._dots[cav_num].setStyleSheet(
            dot_stylesheet(status, self.gui_cavities[cav_num].locked)
        )
        agg = self._aggregate_status()
        self.tile.setStyleSheet(card_stylesheet(agg, self.is_locked))
        if self.on_status_changed:
            self.on_status_changed(self.name, agg)

    def _on_lock_cm_clicked(self):
        if self.is_locked:
            reply = QMessageBox.question(
                self.tile,
                "Unlock CM",
                f"Unlock CM{self.name}? Make sure no one is working on it.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                self._do_unlock()
            else:
                self.lock_cm_button.setChecked(True)
        else:
            self._do_lock()

    def _do_lock(self):
        if self.is_locked:
            return
        self._pre_cascade_locked = {
            n for n, g in self.gui_cavities.items() if g.locked
        }
        self.is_locked = True
        self.lock_cm_button.setChecked(True)
        for gui_cav in self.gui_cavities.values():
            gui_cav.lock()
        self.tile.setStyleSheet(card_stylesheet(self._aggregate_status(), True))
        if self.on_status_changed:
            self.on_status_changed(self.name, self._aggregate_status())

    def _do_unlock(self):
        self.is_locked = False
        self.lock_cm_button.setChecked(False)
        for n, gui_cav in self.gui_cavities.items():
            if n not in self._pre_cascade_locked:
                gui_cav.unlock_no_confirm()
        self.tile.setStyleSheet(
            card_stylesheet(self._aggregate_status(), False)
        )
        if self.on_status_changed:
            self.on_status_changed(self.name, self._aggregate_status())

    def lock(self):
        self._do_lock()

    def unlock_no_confirm(self):
        self._do_unlock()

    def trigger_setup_all(self):
        for gui_cav in self.gui_cavities.values():
            if not gui_cav.locked:
                gui_cav.trigger_setup()

    def trigger_shutdown_all(self):
        for gui_cav in self.gui_cavities.values():
            if not gui_cav.locked:
                gui_cav.trigger_shutdown()

    def trigger_abort_all(self):
        for gui_cav in self.gui_cavities.values():
            gui_cav.request_abort()

    def capture_acon(self):
        for gui_cav in self.gui_cavities.values():
            gui_cav.cavity.capture_acon()
