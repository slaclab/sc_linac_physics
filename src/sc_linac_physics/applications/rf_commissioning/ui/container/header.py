"""Header panel builder for the multi-phase commissioning container."""

from PyQt5.QtWidgets import (
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from sc_linac_physics.utils.sc_linac.linac_utils import ALL_CRYOMODULES
from sc_linac_physics.applications.rf_commissioning.ui.magnet_status_badge import (
    MagnetStatusBadge,
)


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
                border-radius: 5px;
                margin-top: 6px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
    layout = QHBoxLayout()
    layout.setContentsMargins(10, 10, 10, 10)

    # Cavity section - comes FIRST (don't need operator to browse)
    cavity_group = QGroupBox("Cavity Selection")
    cavity_layout = QHBoxLayout()

    host.cryomodule_combo = QComboBox()
    host.cryomodule_combo.setMinimumWidth(80)
    host.cryomodule_combo.addItem("Select CM...", "")
    host.cryomodule_combo.addItems(sorted(ALL_CRYOMODULES))
    cavity_layout.addWidget(QLabel("CM:"))
    cavity_layout.addWidget(host.cryomodule_combo)

    host.cavity_combo = QComboBox()
    host.cavity_combo.setMinimumWidth(60)
    host.cavity_combo.addItem("Select Cav...", "")
    host.cavity_combo.addItems([str(i) for i in range(1, 9)])
    cavity_layout.addWidget(QLabel("Cav:"))
    cavity_layout.addWidget(host.cavity_combo)

    cavity_group.setLayout(cavity_layout)
    layout.addWidget(cavity_group)

    # Cavity completion counter
    host.cavity_completion_label = QLabel("0/8 Complete")
    host.cavity_completion_label.setStyleSheet("""
            QLabel {
                color: #aaa;
                font-weight: bold;
                padding: 5px 10px;
                background-color: rgba(100, 100, 100, 0.2);
                border-radius: 3px;
                font-size: 9px;
            }
        """)
    host.cavity_completion_label.setMaximumWidth(100)
    layout.addWidget(host.cavity_completion_label)

    # Update PVs and load record when cavity selection changes
    host.cryomodule_combo.currentIndexChanged.connect(
        host._on_cavity_selection_changed
    )
    host.cavity_combo.currentIndexChanged.connect(
        host._on_cavity_selection_changed
    )

    # Separator
    separator = QFrame()
    separator.setFrameShape(QFrame.VLine)
    separator.setFrameShadow(QFrame.Sunken)
    separator.setStyleSheet("color: #555;")
    layout.addWidget(separator)

    # Operator section - needed for running tests
    op_group = QGroupBox("Operator (Required for Tests)")
    op_layout = QHBoxLayout()
    host.operator_combo = QComboBox()
    host.operator_combo.setMinimumWidth(200)
    host.operator_combo.currentIndexChanged.connect(host._on_operator_changed)
    host._populate_operator_combo()
    op_layout.addWidget(host.operator_combo)
    op_group.setLayout(op_layout)
    layout.addWidget(op_group)

    # Sync status indicator
    host.sync_status = QLabel("○ No Record Loaded")
    host.sync_status.setStyleSheet("""
            QLabel {
                color: #888;
                font-weight: bold;
                padding: 5px 10px;
                background-color: rgba(100, 100, 100, 0.2);
                border-radius: 3px;
            }
        """)
    layout.addWidget(host.sync_status)

    # Magnet checkout section (prominent status + open action)
    magnet_group = QGroupBox("Magnet Checkout")
    magnet_layout = QVBoxLayout()
    magnet_layout.setSpacing(6)

    host.magnet_status_badge = MagnetStatusBadge()
    host.magnet_status_badge.setToolTip("Cryomodule magnet checkout status")
    host.magnet_status_badge.setMinimumWidth(120)
    magnet_layout.addWidget(host.magnet_status_badge)

    host.open_magnet_checkout_btn = QPushButton("Open Magnet Checkout")
    host.open_magnet_checkout_btn.setToolTip(
        "Open the cryomodule magnet checkout screen"
    )
    host.open_magnet_checkout_btn.clicked.connect(
        host._open_magnet_checkout_screen
    )
    magnet_layout.addWidget(host.open_magnet_checkout_btn)

    magnet_group.setLayout(magnet_layout)
    layout.addWidget(magnet_group)

    layout.addStretch()

    # Quick actions
    batch_btn = QPushButton("Batch Pre-RF")
    batch_btn.setToolTip("Run Piezo Pre-RF test on multiple cavities at once")
    batch_btn.clicked.connect(host._open_batch_pre_rf_window)
    layout.addWidget(batch_btn)

    history_btn = QPushButton("📊 Measurements")
    history_btn.setToolTip("View all measurement attempts and filter by phase")
    history_btn.clicked.connect(host._show_measurement_history)
    layout.addWidget(history_btn)

    database_btn = QPushButton("🗄️ Database")
    database_btn.setToolTip("Browse and load commissioning records")
    database_btn.clicked.connect(host._show_database_browser)
    layout.addWidget(database_btn)

    header.setLayout(layout)
    return header
