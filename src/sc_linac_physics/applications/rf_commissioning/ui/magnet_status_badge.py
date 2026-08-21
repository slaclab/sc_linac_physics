"""Status badge for magnet checkout display in cavity header."""

from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLabel
from PyQt5.QtGui import QFontDatabase, QColor, QPalette


class MagnetStatusBadge(QWidget):
    """Small status indicator showing magnet checkout status for a cavity/CM.

    Displays compact badge: "✓ PASS / ✗ FAIL / ? PENDING" in header with
    color-coded background.
    """

    def __init__(self):
        """Initialize magnet status badge."""
        super().__init__()
        self.status = "PENDING"
        self.init_ui()

    def init_ui(self):
        """Build the badge UI."""
        layout = QHBoxLayout()
        layout.setContentsMargins(6, 2, 6, 2)

        self.label = QLabel()
        badge_font = QFontDatabase.systemFont(QFontDatabase.FixedFont)
        badge_font.setPointSize(9)
        badge_font.setBold(True)
        self.label.setFont(badge_font)
        layout.addWidget(self.label)

        self.setLayout(layout)
        self.update_display()

    VALID_STATUSES = frozenset({"PASS", "FAIL", "PENDING"})

    def set_status(self, status: str):
        """Update badge status.

        Args:
            status: One of "PASS", "FAIL", or "PENDING" (case-insensitive).

        Raises:
            ValueError: If status is not one of the accepted values.
        """
        normalized = status.upper()
        if normalized not in self.VALID_STATUSES:
            raise ValueError(
                f"Invalid status {status!r}. Must be one of: "
                + ", ".join(sorted(self.VALID_STATUSES))
            )
        self.status = normalized
        self.update_display()

    def update_display(self):
        """Refresh badge appearance based on current status."""
        if self.status == "PASS":
            display_text = "✓ PASS"
            # Muted sage green background
            bg_color = QColor(47, 130, 93)
            text_color = QColor(255, 255, 255)
        elif self.status == "FAIL":
            display_text = "✗ FAIL"
            # Muted terracotta red background
            bg_color = QColor(157, 62, 56)
            text_color = QColor(255, 255, 255)
        else:  # PENDING
            display_text = "? PENDING"
            # Neutral slate background
            bg_color = QColor(69, 76, 94)
            text_color = QColor(201, 205, 214)

        self.label.setText(display_text)

        palette = QPalette()
        palette.setColor(QPalette.Window, bg_color)
        palette.setColor(QPalette.WindowText, text_color)
        self.setPalette(palette)
        self.setAutoFillBackground(True)
