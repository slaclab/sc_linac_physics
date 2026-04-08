"""Visual phase tracker widget for RF commissioning workflow.

Displays overall progress across all commissioning phases with visual indicators.
"""

from typing import Optional

from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QPainter, QColor, QPen, QFont
from PyQt5.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QSizePolicy,
)

from sc_linac_physics.applications.rf_commissioning import (
    CommissioningPhase,
    PhaseStatus,
    CommissioningRecord,
)


class PhaseStepWidget(QWidget):
    """Single phase step indicator with status visualization."""

    def __init__(
        self,
        phase: CommissioningPhase,
        phase_number: int,
        total_phases: int,
        parent=None,
    ):
        super().__init__(parent)
        self.phase = phase
        self.phase_number = phase_number
        self.total_phases = total_phases
        self.status = PhaseStatus.NOT_STARTED
        self.is_current = False

        self.setMinimumSize(120, 80)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # Colors
        self.color_not_started = QColor(100, 100, 100)  # Grey
        self.color_in_progress = QColor(33, 150, 243)  # Blue
        self.color_complete = QColor(76, 175, 80)  # Green
        self.color_failed = QColor(244, 67, 54)  # Red
        self.color_skipped = QColor(255, 152, 0)  # Orange

    def set_status(self, status: PhaseStatus, is_current: bool = False) -> None:
        """Update the phase status and trigger repaint."""
        self.status = status
        self.is_current = is_current
        self.update()

    def get_status_color(self) -> QColor:
        """Get color based on current status."""
        status_colors = {
            PhaseStatus.NOT_STARTED: self.color_not_started,
            PhaseStatus.IN_PROGRESS: self.color_in_progress,
            PhaseStatus.COMPLETE: self.color_complete,
            PhaseStatus.FAILED: self.color_failed,
            PhaseStatus.SKIPPED: self.color_skipped,
        }
        return status_colors.get(self.status, self.color_not_started)

    def get_status_symbol(self) -> str:
        """Get symbol based on current status."""
        status_symbols = {
            PhaseStatus.NOT_STARTED: "○",
            PhaseStatus.IN_PROGRESS: "▶",
            PhaseStatus.COMPLETE: "✓",
            PhaseStatus.FAILED: "✗",
            PhaseStatus.SKIPPED: "⊘",
        }
        return status_symbols.get(self.status, "○")

    def paintEvent(self, event):
        """Custom paint for the phase step."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        width = self.width()

        # Get colors
        color = self.get_status_color()
        border_color = (
            color.darker(120) if not self.is_current else QColor(255, 235, 59)
        )

        # Draw circle
        circle_size = 40
        circle_x = (width - circle_size) // 2
        circle_y = 5

        # Draw border if current phase
        if self.is_current:
            painter.setPen(QPen(border_color, 3))
            painter.setBrush(color)
            painter.drawEllipse(
                circle_x - 2,
                circle_y - 2,
                circle_size + 4,
                circle_size + 4,
            )
        else:
            painter.setPen(QPen(border_color, 2))
            painter.setBrush(color)
            painter.drawEllipse(circle_x, circle_y, circle_size, circle_size)

        # Draw status symbol
        symbol = self.get_status_symbol()
        symbol_font = QFont("Arial", 18, QFont.Bold)
        painter.setFont(symbol_font)
        painter.setPen(QColor(255, 255, 255))
        symbol_rect = painter.fontMetrics().boundingRect(symbol)
        symbol_x = (width - symbol_rect.width()) // 2
        symbol_y = circle_y + (circle_size + symbol_rect.height()) // 2 - 2
        painter.drawText(symbol_x, symbol_y, symbol)

        # Draw connector line to next phase (if not last)
        if self.phase_number < self.total_phases:
            line_y = circle_y + circle_size // 2
            line_start_x = circle_x + circle_size + 5
            line_end_x = width

            painter.setPen(
                QPen(
                    (
                        color
                        if self.status == PhaseStatus.COMPLETE
                        else self.color_not_started
                    ),
                    2,
                )
            )
            painter.drawLine(line_start_x, line_y, line_end_x, line_y)

        # Draw phase label
        label_font = QFont(
            "Arial", 9, QFont.Bold if self.is_current else QFont.Normal
        )
        painter.setFont(label_font)
        painter.setPen(
            QColor(255, 255, 255) if self.is_current else QColor(200, 200, 200)
        )

        # Phase name (shortened for display)
        phase_names = {
            CommissioningPhase.PIEZO_PRE_RF: "Piezo\nPre-RF",
            CommissioningPhase.COLD_LANDING: "Cold\nLanding",
            CommissioningPhase.SSA_CHAR: "SSA\nChar",
            CommissioningPhase.PI_MODE: "Pi\nMode",
            CommissioningPhase.CAVITY_CHAR: "Cavity\nChar",
            CommissioningPhase.PIEZO_WITH_RF: "Piezo\nw/ RF",
            CommissioningPhase.HIGH_POWER_RAMP: "HP\nRamp",
            CommissioningPhase.MP_PROCESSING: "MP\nProc",
            CommissioningPhase.ONE_HOUR_RUN: "1-Hr\nRun",
            CommissioningPhase.COMPLETE: "Complete",
        }

        label_text = phase_names.get(self.phase, self.phase.value)
        label_y = circle_y + circle_size + 10

        # Draw multi-line text
        for i, line in enumerate(label_text.split("\n")):
            text_rect = painter.fontMetrics().boundingRect(line)
            text_x = (width - text_rect.width()) // 2
            painter.drawText(text_x, label_y + i * 12, line)


class PhaseTrackerWidget(QWidget):
    """Complete phase tracker showing all commissioning phases."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.record: Optional[CommissioningRecord] = None
        self.phase_widgets: dict[CommissioningPhase, PhaseStepWidget] = {}

        self._init_ui()

    def _init_ui(self):
        """Initialize the UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)

        # Title
        title = QLabel("Commissioning Progress")
        title.setStyleSheet(
            "font-size: 12pt; font-weight: bold; color: #ffffff;"
        )
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Phase steps container
        steps_container = QHBoxLayout()
        steps_container.setSpacing(0)
        steps_container.setContentsMargins(0, 0, 0, 0)

        phase_order = CommissioningPhase.get_phase_order()
        total_phases = len(phase_order)

        for i, phase in enumerate(phase_order, start=1):
            step_widget = PhaseStepWidget(phase, i, total_phases, self)
            self.phase_widgets[phase] = step_widget
            steps_container.addWidget(step_widget)

        layout.addLayout(steps_container)

        # Info label
        self.info_label = QLabel("No active record")
        self.info_label.setStyleSheet("color: #aaaaaa; font-size: 9pt;")
        self.info_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.info_label)

        self.setStyleSheet("background-color: #2b2b2b; border-radius: 5px;")

    def update_from_record(self, record: Optional[CommissioningRecord]):
        """Update the tracker based on a commissioning record."""
        self.record = record

        if not record:
            # Clear all statuses
            for widget in self.phase_widgets.values():
                widget.set_status(PhaseStatus.NOT_STARTED, is_current=False)
            self.info_label.setText("No active record")
            return

        # Update each phase widget
        current_phase = record.current_phase

        for phase, widget in self.phase_widgets.items():
            status = record.get_phase_status(phase)
            is_current = phase == current_phase
            widget.set_status(status, is_current)

        # Update info label
        self.info_label.setText(
            f"{record.short_cavity_name} - {current_phase.value.replace('_', ' ').title()}"
        )

    def sizeHint(self) -> QSize:
        """Provide a reasonable default size."""
        return QSize(800, 120)
