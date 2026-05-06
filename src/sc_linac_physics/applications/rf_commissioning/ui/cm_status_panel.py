"""Cryomodule status panel showing cavity completion."""

from PyQt5.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
)
from PyQt5.QtGui import QFont, QFontDatabase

from sc_linac_physics.applications.rf_commissioning.models.persistence.database import (
    CommissioningDatabase,
)


class CMStatusPanel(QWidget):
    """Panel showing CM-level cavity completion counts.

    Displays:
    - Overall cavity completion count (X/8 complete)
    """

    def __init__(self, linac: str, cryomodule: str, db: CommissioningDatabase):
        """Initialize CM status panel.

        Args:
            linac: Linac name (e.g., "L1B")
            cryomodule: CM number (e.g., "02")
            db: CommissioningDatabase instance
        """
        super().__init__()
        self.linac = linac
        self.cryomodule = cryomodule
        self.db = db

        self.init_ui()
        self.update_cavity_counts()

    def init_ui(self):
        """Build the status panel UI."""
        layout = QHBoxLayout()
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(12)

        label_font = QFont()
        label_font.setPointSize(9)
        label_font.setBold(True)

        # Cavity completion count
        cavity_count_layout = QVBoxLayout()
        cavity_count_layout.setSpacing(2)

        cavity_label = QLabel("Cavity Completion:")
        cavity_label.setFont(label_font)
        cavity_count_layout.addWidget(cavity_label)

        self.cavity_count_label = QLabel("0/8 Complete")
        cavity_count_font = QFontDatabase.systemFont(QFontDatabase.FixedFont)
        cavity_count_font.setPointSize(10)
        cavity_count_font.setBold(True)
        self.cavity_count_label.setFont(cavity_count_font)
        cavity_count_layout.addWidget(self.cavity_count_label)
        cavity_count_layout.addStretch()

        layout.addLayout(cavity_count_layout)

        layout.addStretch()
        self.setLayout(layout)

        # Keep row visibly present between progress and tabs
        self.setMinimumHeight(82)

        # Set panel background
        self.setStyleSheet("""
            CMStatusPanel {
                background-color: #f3f6fa;
                border-top: 1px solid #d0d7e2;
                border-bottom: 2px solid #aeb9c7;
            }
        """)

    def update_cavity_counts(self):
        """Query cavity completion count for this CM."""
        if not self.cryomodule:
            self.cavity_count_label.setText("0/8 Complete")
            return

        linac_index = int(self.linac[1])
        cavity_records = self.db.get_records_by_cryomodule(
            linac_index, self.cryomodule, active_only=False
        )

        completed = sum(
            1
            for record in cavity_records
            if record.current_phase and record.current_phase.value == "complete"
        )

        self.cavity_count_label.setText(f"{completed}/8 Complete")

    def refresh(self):
        """Refresh all status displays when CM changes or record updates."""
        self.update_cavity_counts()
