"""Header panel builder for the multi-phase commissioning container."""

from PyQt5.QtWidgets import (
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from sc_linac_physics.applications.rf_commissioning.ui.magnet_status_badge import (
    MagnetStatusBadge,
)
from sc_linac_physics.utils.sc_linac.linac_utils import ALL_CRYOMODULES

_LINAC_NAMES = ["L0B", "L1B", "L2B", "L3B", "L4B"]


def _vline() -> QFrame:
    sep = QFrame()
    sep.setFrameShape(QFrame.VLine)
    sep.setFrameShadow(QFrame.Sunken)
    sep.setStyleSheet("color: #555;")
    return sep


def build_header_panel(host) -> QWidget:
    """Build persistent header with operator and cavity selection."""
    header = QWidget()
    header.setStyleSheet("""
        QWidget {
            background-color: #2b2b2b;
            border-bottom: 2px solid #4a4a4a;
        }
        QGroupBox {
            font-weight: bold;
            border: 1px solid #555;
            border-radius: 4px;
            margin-top: 6px;
            padding-top: 8px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 8px;
            padding: 0 4px;
        }
    """)

    layout = QHBoxLayout()
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(8)

    # ---- Cavity Selection (group box — multi-widget, needs context) ----
    cavity_group = QGroupBox("Cavity Selection")
    cavity_layout = QHBoxLayout()
    cavity_layout.setSpacing(4)

    host.linac_combo = QComboBox()
    host.linac_combo.setFixedWidth(68)
    host.linac_combo.addItem("All")
    host.linac_combo.addItems(_LINAC_NAMES)
    cavity_layout.addWidget(QLabel("Linac:"))
    cavity_layout.addWidget(host.linac_combo)

    host.cryomodule_combo = QComboBox()
    host.cryomodule_combo.setFixedWidth(72)
    host.cryomodule_combo.addItem("CM...", "")
    host.cryomodule_combo.addItems(sorted(ALL_CRYOMODULES))
    cavity_layout.addWidget(QLabel("CM:"))
    cavity_layout.addWidget(host.cryomodule_combo)

    host.cavity_combo = QComboBox()
    host.cavity_combo.setFixedWidth(72)
    host.cavity_combo.addItem("Cav...", "")
    host.cavity_combo.addItems([str(i) for i in range(1, 9)])
    cavity_layout.addWidget(QLabel("Cav:"))
    cavity_layout.addWidget(host.cavity_combo)

    host.cavity_completion_label = QLabel("0/8 Complete")
    host.cavity_completion_label.setStyleSheet("""
        QLabel {
            color: #aaa;
            font-weight: bold;
            padding: 2px 6px;
            background-color: rgba(100, 100, 100, 0.2);
            border-radius: 3px;
            font-size: 9px;
        }
    """)
    cavity_layout.addWidget(host.cavity_completion_label)

    cavity_group.setLayout(cavity_layout)
    layout.addWidget(cavity_group)

    host.linac_combo.currentIndexChanged.connect(
        host._on_linac_selection_changed
    )
    host.cryomodule_combo.currentIndexChanged.connect(
        host._on_cavity_selection_changed
    )
    host.cavity_combo.currentIndexChanged.connect(
        host._on_cavity_selection_changed
    )

    # ---- Operator (inline — single widget, label is enough) ----
    layout.addWidget(_vline())
    layout.addWidget(QLabel("Operator:"))
    host.operator_combo = QComboBox()
    host.operator_combo.setMinimumWidth(140)
    host.operator_combo.setMaximumWidth(200)
    host.operator_combo.currentIndexChanged.connect(host._on_operator_changed)
    host._populate_operator_combo()
    layout.addWidget(host.operator_combo)

    # ---- Sync status ----
    layout.addWidget(_vline())
    host.sync_status = QLabel("No Record")
    host.sync_status.setStyleSheet("""
        QLabel {
            color: #888;
            font-weight: bold;
            padding: 2px 6px;
            background-color: rgba(100, 100, 100, 0.2);
            border-radius: 3px;
        }
    """)
    layout.addWidget(host.sync_status)

    # ---- Magnet Checkout (group box — badge + button need context) ----
    layout.addWidget(_vline())
    magnet_group = QGroupBox("Magnet Checkout")
    magnet_layout = QHBoxLayout()
    magnet_layout.setSpacing(6)

    host.magnet_status_badge = MagnetStatusBadge()
    host.magnet_status_badge.setToolTip("Cryomodule magnet checkout status")
    host.magnet_status_badge.setFixedWidth(78)
    magnet_layout.addWidget(host.magnet_status_badge)

    host.open_magnet_checkout_btn = QPushButton("Open")
    host.open_magnet_checkout_btn.setToolTip("Open cryomodule magnet checkout")
    host.open_magnet_checkout_btn.setFixedWidth(52)
    host.open_magnet_checkout_btn.clicked.connect(
        host._open_magnet_checkout_screen
    )
    magnet_layout.addWidget(host.open_magnet_checkout_btn)

    magnet_group.setLayout(magnet_layout)
    layout.addWidget(magnet_group)

    layout.addStretch()

    # ---- Action buttons ----
    layout.addWidget(_vline())
    layout.addSpacing(4)

    batch_btn = QPushButton("Batch Pre-RF")
    batch_btn.setToolTip("Run Piezo Pre-RF test on multiple cavities at once")
    batch_btn.clicked.connect(host._open_batch_pre_rf_window)
    layout.addWidget(batch_btn)

    layout.addSpacing(4)

    history_btn = QPushButton("📊 Measurements")
    history_btn.setToolTip("View all measurement attempts and filter by phase")
    history_btn.clicked.connect(host._show_measurement_history)
    layout.addWidget(history_btn)

    layout.addSpacing(4)

    database_btn = QPushButton("🗄️ Database")
    database_btn.setToolTip("Browse and load commissioning records")
    database_btn.clicked.connect(host._show_database_browser)
    layout.addWidget(database_btn)

    header.setLayout(layout)
    return header
