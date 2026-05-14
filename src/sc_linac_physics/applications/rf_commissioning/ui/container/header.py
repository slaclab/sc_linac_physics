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


class _HeaderMixin:
    def _build_header_panel(self) -> QWidget:
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

        cavity_group = QGroupBox("Cavity Selection")
        cavity_layout = QHBoxLayout()

        self.cryomodule_combo = QComboBox()
        self.cryomodule_combo.setMinimumWidth(80)
        self.cryomodule_combo.addItem("Select CM...", "")
        self.cryomodule_combo.addItems(sorted(ALL_CRYOMODULES))
        cavity_layout.addWidget(QLabel("CM:"))
        cavity_layout.addWidget(self.cryomodule_combo)

        self.cavity_combo = QComboBox()
        self.cavity_combo.setMinimumWidth(60)
        self.cavity_combo.addItem("Select Cav...", "")
        self.cavity_combo.addItems([str(i) for i in range(1, 9)])
        cavity_layout.addWidget(QLabel("Cav:"))
        cavity_layout.addWidget(self.cavity_combo)

        cavity_group.setLayout(cavity_layout)
        layout.addWidget(cavity_group)

        self.cavity_completion_label = QLabel("0/8 Complete")
        self.cavity_completion_label.setStyleSheet("""
                QLabel {
                    color: #aaa;
                    font-weight: bold;
                    padding: 5px 10px;
                    background-color: rgba(100, 100, 100, 0.2);
                    border-radius: 3px;
                    font-size: 9px;
                }
            """)
        self.cavity_completion_label.setMaximumWidth(100)
        layout.addWidget(self.cavity_completion_label)

        self.cryomodule_combo.currentIndexChanged.connect(
            self._on_cavity_selection_changed
        )
        self.cavity_combo.currentIndexChanged.connect(
            self._on_cavity_selection_changed
        )

        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setStyleSheet("color: #555;")
        layout.addWidget(separator)

        op_group = QGroupBox("Operator (Required for Tests)")
        op_layout = QHBoxLayout()
        self.operator_combo = QComboBox()
        self.operator_combo.setMinimumWidth(200)
        self.operator_combo.currentIndexChanged.connect(
            self._on_operator_changed
        )
        self._populate_operator_combo()
        op_layout.addWidget(self.operator_combo)
        op_group.setLayout(op_layout)
        layout.addWidget(op_group)

        self.sync_status = QLabel("○ No Record Loaded")
        self.sync_status.setStyleSheet("""
                QLabel {
                    color: #888;
                    font-weight: bold;
                    padding: 5px 10px;
                    background-color: rgba(100, 100, 100, 0.2);
                    border-radius: 3px;
                }
            """)
        layout.addWidget(self.sync_status)

        magnet_group = QGroupBox("Magnet Checkout")
        magnet_layout = QVBoxLayout()
        magnet_layout.setSpacing(6)

        self.magnet_status_badge = MagnetStatusBadge()
        self.magnet_status_badge.setToolTip("Cryomodule magnet checkout status")
        self.magnet_status_badge.setMinimumWidth(120)
        magnet_layout.addWidget(self.magnet_status_badge)

        self.open_magnet_checkout_btn = QPushButton("Open Magnet Checkout")
        self.open_magnet_checkout_btn.setToolTip(
            "Open the cryomodule magnet checkout screen"
        )
        self.open_magnet_checkout_btn.clicked.connect(
            self._open_magnet_checkout_screen
        )
        magnet_layout.addWidget(self.open_magnet_checkout_btn)

        magnet_group.setLayout(magnet_layout)
        layout.addWidget(magnet_group)

        layout.addStretch()

        batch_btn = QPushButton("Batch Pre-RF")
        batch_btn.setToolTip(
            "Run Piezo Pre-RF test on multiple cavities at once"
        )
        batch_btn.clicked.connect(self._open_batch_pre_rf_window)
        layout.addWidget(batch_btn)

        history_btn = QPushButton("📊 Measurements")
        history_btn.setToolTip(
            "View all measurement attempts and filter by phase"
        )
        history_btn.clicked.connect(self._show_measurement_history)
        layout.addWidget(history_btn)

        database_btn = QPushButton("🗄️ Database")
        database_btn.setToolTip("Browse and load commissioning records")
        database_btn.clicked.connect(self._show_database_browser)
        layout.addWidget(database_btn)

        header.setLayout(layout)
        return header


# Backward-compat alias so existing tests continue to work.
build_header_panel = _HeaderMixin._build_header_panel
