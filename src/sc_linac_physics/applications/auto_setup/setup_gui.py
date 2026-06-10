from typing import Optional, Dict, Tuple

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
    QPushButton,
    QCheckBox,
    QMessageBox,
    QFrame,
    QGridLayout,
    QLabel,
    QSizePolicy,
)
from pydm import Display
from pydm.utilities.stylesheet import apply_stylesheet

from sc_linac_physics.applications.auto_setup.frontend.gui_linac import GUILinac
from sc_linac_physics.applications.auto_setup.frontend.style import (
    PAGE_BG,
    CARD_BG,
    CARD_BORDER,
    CARD_TEXT,
    MUTED_TEXT,
    NOTE_TEXT,
    ACCENT_BORDER,
    ACCENT_TEXT,
    LINAC_COLORS,
    button_stylesheet,
    chip_frame_stylesheet,
    dot_stylesheet,
    dot_text,
    linac_frame_stylesheet,
    status_text_color,
)
from sc_linac_physics.applications.auto_setup.frontend.utils import Settings
from sc_linac_physics.applications.auto_setup.frontend.widgets import (
    FlowLayout,
    HeightForWidthWidget,
)
from sc_linac_physics.utils.qt import make_sanity_check_popup
from sc_linac_physics.utils.sc_linac import linac_utils
from sc_linac_physics.utils.sc_linac.linac_utils import STATUS_READY_VALUE


class SetupGUI(Display):
    def __init__(self, parent=None, args=None):
        super().__init__(parent=parent, args=args)
        self.setWindowTitle("SRF Auto Setup")
        apply_stylesheet()
        self.setMinimumWidth(920)
        self.resize(920, 910)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # ── Top bar ──────────────────────────────────────────────────────────
        top_bar = QFrame()
        top_bar.setObjectName("topBar")
        top_bar.setStyleSheet(
            f"QFrame#topBar {{ background: {CARD_BG}; border-bottom: 1px solid {CARD_BORDER}; }}"
            + button_stylesheet()
            + f"QCheckBox {{ color: {CARD_TEXT}; font-size: 11px; }}"
        )
        top_bar_layout = QVBoxLayout(top_bar)
        top_bar_layout.setContentsMargins(12, 10, 12, 10)
        top_bar_layout.setSpacing(0)

        machine_btn_row = QHBoxLayout()
        machine_btn_row.setSpacing(6)
        self.machine_setup_button = QPushButton("Set Up Machine")
        self.machine_shutdown_button = QPushButton("Shut Down Machine")
        self.machine_abort_button = QPushButton("Abort Machine")
        self.machine_abort_button.setStyleSheet(
            "QPushButton { color: #e08090; }"
        )

        self.machine_setup_popup = make_sanity_check_popup(
            "Set up all unlocked cavities across the entire machine?"
        )
        self.machine_shutdown_popup = make_sanity_check_popup(
            "Shut down all unlocked cavities across the entire machine?"
        )
        self.machine_abort_popup = make_sanity_check_popup(
            "Abort all running setup operations?"
        )

        self.machine_setup_button.clicked.connect(self.trigger_machine_setup)
        self.machine_shutdown_button.clicked.connect(
            self.trigger_machine_shutdown
        )
        self.machine_abort_button.clicked.connect(self.trigger_machine_abort)

        machine_btn_row.addWidget(self.machine_setup_button)
        machine_btn_row.addWidget(self.machine_shutdown_button)
        machine_btn_row.addWidget(self.machine_abort_button)
        machine_btn_row.addStretch()
        top_bar_layout.addLayout(machine_btn_row)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {CARD_BORDER}; border: none;")
        top_bar_layout.addSpacing(8)
        top_bar_layout.addWidget(sep)
        top_bar_layout.addSpacing(8)

        checkbox_row = QHBoxLayout()
        checkbox_row.setSpacing(14)
        steps_label = QLabel("Steps:")
        steps_label.setStyleSheet(
            f"color: {MUTED_TEXT}; font-size: 10px; font-weight: 600; border: none;"
        )
        checkbox_row.addWidget(steps_label)
        self.ssa_cal_checkbox = QCheckBox("SSA Calibration")
        self.ssa_cal_checkbox.setChecked(True)
        self.autotune_checkbox = QCheckBox("Auto Tune")
        self.autotune_checkbox.setChecked(True)
        self.cav_char_checkbox = QCheckBox("Cavity Characterization")
        self.cav_char_checkbox.setChecked(True)
        self.rf_ramp_checkbox = QCheckBox("RF Ramp")
        self.rf_ramp_checkbox.setChecked(True)
        checkbox_row.addWidget(self.ssa_cal_checkbox)
        checkbox_row.addWidget(self.autotune_checkbox)
        checkbox_row.addWidget(self.cav_char_checkbox)
        checkbox_row.addWidget(self.rf_ramp_checkbox)
        checkbox_row.addStretch()

        notes_widget = QWidget()
        notes_widget.setStyleSheet("background: transparent; border: none;")
        notes_layout = QVBoxLayout(notes_widget)
        notes_layout.setContentsMargins(0, 0, 0, 0)
        notes_layout.setSpacing(2)
        for text in (
            "⚠  Deselecting steps is for expert use only.",
            "\U0001f512  Locking excludes from Set Up, Shut Down, and Abort.",
        ):
            lbl = QLabel(text)
            lbl.setAlignment(Qt.AlignRight)
            lbl.setStyleSheet(
                f"color: {NOTE_TEXT}; font-size: 10px; border: none;"
            )
            notes_layout.addWidget(lbl)
        checkbox_row.addWidget(notes_widget)
        top_bar_layout.addLayout(checkbox_row)
        outer_layout.addWidget(top_bar)

        self.settings = Settings(
            ssa_cal_checkbox=self.ssa_cal_checkbox,
            auto_tune_checkbox=self.autotune_checkbox,
            cav_char_checkbox=self.cav_char_checkbox,
            rf_ramp_checkbox=self.rf_ramp_checkbox,
        )

        # ── Content area ─────────────────────────────────────────────────────
        content_widget = QWidget()
        content_widget.setStyleSheet(f"background: {PAGE_BG};")
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(12, 12, 12, 12)
        content_layout.setSpacing(12)

        # Machine view: two QHBoxLayout rows of bordered linac frames.
        # QHBoxLayout gives all frames in a row the same height (the tallest
        # frame's natural height); Expanding vertical policy ensures each frame
        # fills that height, with content pinned to the top via addStretch.
        self._tiles_widget = QWidget()
        _outer = QVBoxLayout(self._tiles_widget)
        _outer.setContentsMargins(0, 0, 0, 0)
        _outer.setSpacing(8)

        self._machine_cm_chips: Dict[str, Tuple[QFrame, QLabel]] = {}
        self._machine_cav_dots: Dict[str, Dict[int, QLabel]] = {}
        self._cm_linac: Dict[str, GUILinac] = {}
        self.gui_linacs: Dict[str, GUILinac] = {}

        linac_defs = [
            ("L0B", 0),
            ("L1B", 1),
            ("L2B", 2),
            ("L3B", 3),
            ("L4B", 4),
        ]

        _row1 = QHBoxLayout()
        _row1.setSpacing(8)
        _row2 = QHBoxLayout()
        _row2.setSpacing(8)
        _ROW = {
            "L0B": _row1,
            "L1B": _row1,
            "L2B": _row1,
            "L3B": _row2,
            "L4B": _row2,
        }

        for name, idx in linac_defs:
            color = LINAC_COLORS[name]
            gui_linac = GUILinac(
                name=name,
                idx=idx,
                cryomodule_names=linac_utils.LINAC_CM_MAP[idx],
                settings=self.settings,
                on_tile_clicked=None,
                on_cm_selected=self._on_cm_selected,
                on_machine_cm_status_changed=self._on_machine_cm_status_changed,
                on_machine_cav_status_changed=self._on_machine_cav_status_changed,
            )
            self.gui_linacs[name] = gui_linac

            frame = QFrame()
            frame.setStyleSheet(linac_frame_stylesheet(name))
            frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            frame.setCursor(Qt.PointingHandCursor)
            frame.mousePressEvent = (
                lambda e, gl=gui_linac: self._on_linac_label_clicked(gl)
            )
            frame_layout = QVBoxLayout(frame)
            frame_layout.setContentsMargins(10, 10, 10, 10)
            frame_layout.setSpacing(8)

            header_row = QHBoxLayout()
            label = QLabel(name)
            label.setStyleSheet(
                f"color: {color}; font-size: 14px; font-weight: 800; border: none;"
            )
            header_row.addWidget(label)
            header_row.addStretch()
            for btn_text, btn_slot, btn_color in [
                ("Set Up", gui_linac.trigger_setup, color),
                ("Shut Down", gui_linac.trigger_shutdown, color),
                ("Abort", gui_linac.trigger_abort, "#e08090"),
            ]:
                btn = QPushButton(btn_text)
                btn.setStyleSheet(
                    f"QPushButton {{ background: {CARD_BG}; color: {btn_color}; "
                    f"border: 1px solid {btn_color}; border-radius: 3px; "
                    f"padding: 2px 8px; font-size: 10px; }} "
                    f"QPushButton:hover {{ background: {btn_color}22; }}"
                )
                btn.clicked.connect(btn_slot)
                header_row.addWidget(btn)
            lock_btn = QPushButton("\U0001f512")
            lock_btn.setCheckable(True)
            lock_btn.setStyleSheet(
                f"QPushButton {{ background: {CARD_BG}; color: {color}; "
                f"border: 1px solid {color}; border-radius: 3px; "
                f"padding: 2px 6px; font-size: 10px; }} "
                f"QPushButton:checked {{ background: {color}33; }} "
                f"QPushButton:hover {{ background: {color}22; }}"
            )
            lock_btn.clicked.connect(gui_linac._on_lock_linac_clicked)
            gui_linac.add_lock_button(lock_btn)
            header_row.addWidget(lock_btn)
            frame_layout.addLayout(header_row)

            cm_widget = HeightForWidthWidget()
            cm_flow = FlowLayout(cm_widget, h_spacing=6, v_spacing=6)
            for cm_name in linac_utils.LINAC_CM_MAP[idx]:
                chip_frame = QFrame()
                chip_frame.setStyleSheet(
                    chip_frame_stylesheet(STATUS_READY_VALUE)
                )
                chip_frame.setCursor(Qt.PointingHandCursor)
                chip_frame.mousePressEvent = (
                    lambda e, cn=cm_name: self._on_machine_cm_clicked(cn)
                )
                chip_layout = QVBoxLayout(chip_frame)
                chip_layout.setContentsMargins(6, 5, 6, 5)
                chip_layout.setSpacing(4)

                name_label = QLabel(f"CM{cm_name}")
                name_label.setStyleSheet(
                    f"color: {status_text_color(STATUS_READY_VALUE)}; "
                    f"font-size: 12px; font-weight: 700; "
                    f"background: transparent; border: none;"
                )
                chip_layout.addWidget(name_label)

                dot_container = QWidget()
                dot_container.setStyleSheet("background: transparent;")
                dot_grid = QGridLayout(dot_container)
                dot_grid.setContentsMargins(0, 0, 0, 0)
                dot_grid.setHorizontalSpacing(3)
                dot_grid.setVerticalSpacing(3)
                self._machine_cav_dots[cm_name] = {}
                for i in range(8):
                    dot = QLabel()
                    dot.setFixedSize(12, 12)
                    dot.setAlignment(Qt.AlignCenter)
                    dot.setStyleSheet(
                        dot_stylesheet(STATUS_READY_VALUE, font_size=8)
                    )
                    dot.setText(dot_text(STATUS_READY_VALUE))
                    dot_grid.addWidget(dot, i // 4, i % 4)
                    self._machine_cav_dots[cm_name][i + 1] = dot
                chip_layout.addWidget(dot_container)

                self._machine_cm_chips[cm_name] = (chip_frame, name_label)
                self._cm_linac[cm_name] = gui_linac
                cm_flow.addWidget(chip_frame)
            frame_layout.addWidget(cm_widget)
            frame_layout.addStretch(1)

            _ROW[name].addWidget(frame)

        _outer.addLayout(_row1, 1)
        _outer.addLayout(_row2, 1)

        content_layout.addWidget(self._tiles_widget, 1)

        # Detail panel — shown when navigating to linac or CM level.
        self._active_linac: Optional[GUILinac] = None
        self._active_cm: Optional[str] = None
        self._from_machine_direct: bool = False
        self._detail_container = QWidget()
        self._detail_container.setStyleSheet(f"background: {PAGE_BG};")
        self._detail_layout = QVBoxLayout(self._detail_container)
        self._detail_layout.setContentsMargins(0, 0, 0, 0)
        self._detail_layout.setSpacing(6)
        self._back_btn = QPushButton("← Back")
        self._back_btn.setStyleSheet(
            f"QPushButton {{ background: {CARD_BG}; color: {ACCENT_TEXT}; "
            f"border: 2px solid {ACCENT_BORDER}; border-radius: 5px; "
            f"padding: 5px 16px; font-size: 12px; font-weight: 600; }}"
            f"QPushButton:hover {{ background: {ACCENT_BORDER}33; }}"
            f"QPushButton:pressed {{ background: {ACCENT_BORDER}66; }}"
        )
        self._back_btn.hide()
        self._back_btn.clicked.connect(self._on_back_clicked)
        self._detail_layout.addWidget(self._back_btn, 0, Qt.AlignLeft)
        self._detail_container.hide()
        content_layout.addWidget(self._detail_container, 1)

        outer_layout.addWidget(content_widget, 1)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_min_height()

    def _update_min_height(self):
        if not (self._detail_container.isVisible() and self._active_linac):
            self.setMinimumHeight(0)
            return
        if self._active_cm:
            flow_widget = self._active_linac.gui_cryomodules[
                self._active_cm
            ]._cav_widget
        else:
            flow_widget = self._active_linac._cms_widget
        w = flow_widget.width()
        if w <= 0:
            return
        needed_h = flow_widget.heightForWidth(w)
        current_h = flow_widget.height()
        if current_h > 0:
            overhead = max(0, self.height() - current_h)
            self.setMinimumHeight(needed_h + overhead)

    def _on_machine_cm_status_changed(
        self, cm_name: str, status: int, locked: bool
    ):
        frame, label = self._machine_cm_chips[cm_name]
        frame.setStyleSheet(chip_frame_stylesheet(status, locked))
        label.setStyleSheet(
            f"color: {status_text_color(status, locked)}; "
            f"font-size: 11px; font-weight: 700; "
            f"background: transparent; border: none;"
        )

    def _on_machine_cav_status_changed(
        self, cm_name: str, cav_num: int, status: int, locked: bool
    ):
        dot = self._machine_cav_dots[cm_name][cav_num]
        dot.setStyleSheet(dot_stylesheet(status, locked, font_size=8))
        dot.setText(dot_text(status, locked))

    # ── Navigation ────────────────────────────────────────────────────────────

    def _on_machine_cm_clicked(self, cm_name: str):
        gui_linac = self._cm_linac[cm_name]
        self._active_linac = gui_linac
        self._active_cm = cm_name
        self._from_machine_direct = True
        self._tiles_widget.hide()
        gui_cm = gui_linac.gui_cryomodules[cm_name]
        self._detail_layout.addWidget(gui_cm.detail_panel, 1)
        gui_cm.detail_panel.show()
        self._back_btn.setText("← Machine")
        self._back_btn.show()
        self._detail_container.show()
        self._update_min_height()

    def _on_linac_label_clicked(self, gui_linac: GUILinac):
        self._active_linac = gui_linac
        self._active_cm = None
        self._from_machine_direct = False
        self._tiles_widget.hide()
        self._detail_layout.addWidget(gui_linac.detail_panel, 1)
        gui_linac.detail_panel.show()
        self._back_btn.setText("← Machine")
        self._back_btn.show()
        self._detail_container.show()
        self._update_min_height()

    def _on_cm_selected(self, cm_name: str, gui_linac: GUILinac):
        gui_linac.detail_panel.hide()
        self._detail_layout.removeWidget(gui_linac.detail_panel)
        gui_cm = gui_linac.gui_cryomodules[cm_name]
        self._detail_layout.addWidget(gui_cm.detail_panel, 1)
        gui_cm.detail_panel.show()
        self._active_cm = cm_name
        self._from_machine_direct = False
        self._back_btn.setText(f"← {gui_linac.name}")
        self._update_min_height()

    def _on_back_clicked(self):
        if self._active_cm:
            gui_cm = self._active_linac.gui_cryomodules[self._active_cm]
            gui_cm.detail_panel.hide()
            self._detail_layout.removeWidget(gui_cm.detail_panel)
            self._active_cm = None
            if self._from_machine_direct:
                self._active_linac = None
                self._detail_container.hide()
                self._back_btn.hide()
                self._tiles_widget.show()
            else:
                self._detail_layout.addWidget(
                    self._active_linac.detail_panel, 1
                )
                self._active_linac.detail_panel.show()
                self._back_btn.setText("← Machine")
        else:
            self._active_linac.detail_panel.hide()
            self._detail_layout.removeWidget(self._active_linac.detail_panel)
            self._active_linac = None
            self._detail_container.hide()
            self._back_btn.hide()
            self._tiles_widget.show()

    # ── Machine-wide actions ──────────────────────────────────────────────────

    def _iter_all_gui_cavities(self):
        for gui_linac in self.gui_linacs.values():
            for gui_cm in gui_linac.gui_cryomodules.values():
                yield from gui_cm.gui_cavities.values()

    def trigger_machine_setup(self):
        if self.machine_setup_popup.exec() == QMessageBox.Yes:
            for gui_cav in self._iter_all_gui_cavities():
                if not gui_cav.locked:
                    gui_cav.trigger_setup()

    def trigger_machine_shutdown(self):
        if self.machine_shutdown_popup.exec() == QMessageBox.Yes:
            for gui_cav in self._iter_all_gui_cavities():
                if not gui_cav.locked:
                    gui_cav.trigger_shutdown()

    def trigger_machine_abort(self):
        if self.machine_abort_popup.exec() == QMessageBox.Yes:
            for gui_cav in self._iter_all_gui_cavities():
                gui_cav.request_abort()
