"""Header panel builder for the multi-phase commissioning container."""

from PyQt5.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from sc_linac_physics.applications.rf_commissioning.ui.builders.theme import (
    BG_INTERACTIVE,
    BG_PANEL,
    BORDER,
    BORDER_EMPHASIS,
    RADIUS_MD,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)
from sc_linac_physics.applications.rf_commissioning.ui.magnet_status_badge import (
    MagnetStatusBadge,
)
from sc_linac_physics.utils.sc_linac.linac_utils import ALL_CRYOMODULES

_LINAC_NAMES = ["L0B", "L1B", "L2B", "L3B", "L4B"]

_COMBO_STYLE = f"""
    QComboBox {{
        background-color: {BG_INTERACTIVE};
        color: {TEXT_SECONDARY};
        border: none;
        border-radius: {RADIUS_MD};
        padding: 2px 6px 2px 8px;
        min-height: 24px;
    }}
    QComboBox:hover {{
        background-color: rgba(123, 140, 222, 0.15);
        color: {TEXT_PRIMARY};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 18px;
    }}
"""

_POPUP_STYLE = f"""
    QAbstractItemView {{
        border: 1px solid {BORDER_EMPHASIS};
        outline: none;
        background-color: {BG_INTERACTIVE};
        color: {TEXT_SECONDARY};
        selection-background-color: rgba(123, 140, 222, 0.18);
        selection-color: {TEXT_PRIMARY};
    }}
    QAbstractItemView::item {{
        padding: 3px 6px;
        min-height: 22px;
    }}
"""

_GHOST_BTN = (
    f"QPushButton {{"
    f"  color: {TEXT_SECONDARY}; background: transparent;"
    f"  border: 1px solid {BORDER_EMPHASIS}; border-radius: {RADIUS_MD};"
    f"  padding: 3px 10px; font-size: 11px;"
    f"}}"
    f"QPushButton:hover {{"
    f"  color: #c9cdd6; border-color: #6b7899;"
    f"  background: rgba(123,140,222,0.08);"
    f"}}"
)

_MUTED_LABEL_STYLE = f"QLabel {{ color: {TEXT_MUTED}; font-size: 9pt; }}"


def _vline() -> QFrame:
    sep = QFrame()
    sep.setFrameShape(QFrame.VLine)
    sep.setFrameShadow(QFrame.Sunken)
    sep.setStyleSheet(f"color: {BORDER};")
    return sep


def _make_combo(
    fixed_width: int | None = None, popup_min_width: int = 120
) -> QComboBox:
    combo = QComboBox()
    combo.setStyleSheet(_COMBO_STYLE)
    if fixed_width is not None:
        combo.setFixedWidth(fixed_width)
    combo.view().setStyleSheet(_POPUP_STYLE)
    combo.view().setMinimumWidth(popup_min_width)
    return combo


class _HeaderMixin:
    def _build_header_panel(self) -> QWidget:
        """Build persistent header with operator and cavity selection."""
        # Use object-name scoping so background-color doesn't cascade to children.
        outer = QWidget()
        outer.setObjectName("rfHeader")
        outer.setStyleSheet(
            f"QWidget#rfHeader {{ background-color: {BG_PANEL}; }}"
        )

        outer_layout = QVBoxLayout()
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        row = QHBoxLayout()
        row.setContentsMargins(10, 7, 10, 7)
        row.setSpacing(8)

        # ---- Cavity combos (no QGroupBox) ----
        linac_lbl = QLabel("Linac")
        linac_lbl.setStyleSheet(_MUTED_LABEL_STYLE)
        row.addWidget(linac_lbl)
        self.linac_combo = _make_combo(fixed_width=64, popup_min_width=100)
        self.linac_combo.addItem("All")
        self.linac_combo.addItems(_LINAC_NAMES)
        self.linac_combo.setToolTip("Linac section")
        row.addWidget(self.linac_combo)

        cm_lbl = QLabel("CM")
        cm_lbl.setStyleSheet(_MUTED_LABEL_STYLE)
        row.addWidget(cm_lbl)
        self.cryomodule_combo = _make_combo(fixed_width=80, popup_min_width=100)
        self.cryomodule_combo.addItem("...", "")
        self.cryomodule_combo.addItems(sorted(ALL_CRYOMODULES))
        self.cryomodule_combo.setToolTip("Cryomodule")
        row.addWidget(self.cryomodule_combo)

        cav_lbl = QLabel("Cav")
        cav_lbl.setStyleSheet(_MUTED_LABEL_STYLE)
        row.addWidget(cav_lbl)
        self.cavity_combo = _make_combo(fixed_width=48, popup_min_width=60)
        self.cavity_combo.addItem("...", "")
        self.cavity_combo.addItems([str(i) for i in range(1, 9)])
        self.cavity_combo.setToolTip("Cavity number")
        row.addWidget(self.cavity_combo)

        self.cavity_completion_label = QLabel("0/8")
        self.cavity_completion_label.setToolTip(
            "Cavities in this cryomodule that have completed commissioning"
        )
        self.cavity_completion_label.setStyleSheet(f"""
            QLabel {{
                color: {TEXT_MUTED};
                font-weight: bold;
                padding: 2px 8px;
                background-color: rgba(123, 140, 222, 0.10);
                border-radius: {RADIUS_MD};
                font-size: 9pt;
            }}
        """)
        row.addWidget(self.cavity_completion_label)

        self.linac_combo.currentIndexChanged.connect(
            self._on_linac_selection_changed
        )
        self.cryomodule_combo.currentIndexChanged.connect(
            self._on_cavity_selection_changed
        )
        self.cavity_combo.currentIndexChanged.connect(
            self._on_cavity_selection_changed
        )

        # ---- Operator ----
        row.addWidget(_vline())
        op_lbl = QLabel("Operator:")
        op_lbl.setStyleSheet(_MUTED_LABEL_STYLE)
        row.addWidget(op_lbl)
        self.operator_combo = _make_combo(popup_min_width=250)
        self.operator_combo.setMinimumWidth(160)
        self.operator_combo.setMaximumWidth(240)
        self.operator_combo.currentIndexChanged.connect(
            self._on_operator_changed
        )
        self._populate_operator_combo()
        row.addWidget(self.operator_combo)

        # ---- Sync status (expanding — fills the middle gap) ----
        row.addWidget(_vline())
        self.sync_status = QLabel("← Select Linac › CM › Cavity to begin")
        self.sync_status.setStyleSheet(f"""
            QLabel {{
                color: {TEXT_SECONDARY};
                font-style: italic;
                padding: 2px 6px;
            }}
        """)
        self.sync_status.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Preferred
        )
        row.addWidget(self.sync_status)

        # ---- Magnet Checkout ----
        row.addWidget(_vline())
        magnet_lbl = QLabel("Magnet:")
        magnet_lbl.setStyleSheet(_MUTED_LABEL_STYLE)
        row.addWidget(magnet_lbl)
        self.magnet_status_badge = MagnetStatusBadge()
        self.magnet_status_badge.setToolTip("Cryomodule magnet checkout status")
        self.magnet_status_badge.setFixedWidth(78)
        row.addWidget(self.magnet_status_badge)
        self.open_magnet_checkout_btn = QPushButton("Open")
        self.open_magnet_checkout_btn.setToolTip(
            "Open cryomodule magnet checkout"
        )
        self.open_magnet_checkout_btn.setFixedWidth(52)
        self.open_magnet_checkout_btn.setStyleSheet(f"""
            QPushButton {{
                color: {TEXT_SECONDARY};
                background: transparent;
                border: 1px solid {BORDER};
                border-radius: {RADIUS_MD};
                padding: 3px 8px;
                font-size: 11px;
            }}
            QPushButton:hover {{
                color: {TEXT_PRIMARY};
                border-color: {BORDER_EMPHASIS};
                background: rgba(123, 140, 222, 0.08);
            }}
        """)
        self.open_magnet_checkout_btn.clicked.connect(
            self._open_magnet_checkout_screen
        )
        row.addWidget(self.open_magnet_checkout_btn)

        # ---- Action buttons ----
        row.addWidget(_vline())
        row.addSpacing(4)

        batch_btn = QPushButton("Batch Pre-RF")
        batch_btn.setToolTip(
            "Run Piezo Pre-RF test on multiple cavities at once"
        )
        batch_btn.setStyleSheet(_GHOST_BTN)
        batch_btn.clicked.connect(self._open_batch_pre_rf_window)
        row.addWidget(batch_btn)

        row.addSpacing(4)

        history_btn = QPushButton("Measurements")
        history_btn.setToolTip(
            "View all measurement attempts and filter by phase"
        )
        history_btn.setStyleSheet(_GHOST_BTN)
        history_btn.clicked.connect(self._show_measurement_history)
        row.addWidget(history_btn)

        row.addSpacing(4)

        database_btn = QPushButton("Database")
        database_btn.setToolTip("Browse and load commissioning records")
        database_btn.setStyleSheet(_GHOST_BTN)
        database_btn.clicked.connect(self._show_database_browser)
        row.addWidget(database_btn)

        content = QWidget()
        content.setLayout(row)
        outer_layout.addWidget(content)

        # Bottom border as a separate frame avoids CSS cascade.
        bottom_sep = QFrame()
        bottom_sep.setObjectName("rfHeaderBorder")
        bottom_sep.setFixedHeight(2)
        bottom_sep.setStyleSheet(
            f"QFrame#rfHeaderBorder {{ background-color: {BORDER}; border: none; }}"
        )
        outer_layout.addWidget(bottom_sep)

        outer.setLayout(outer_layout)
        return outer


# Backward-compat alias so existing tests continue to work.
build_header_panel = _HeaderMixin._build_header_panel
