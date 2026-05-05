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

    def set_status(self, status: str):
        """Update badge status.

        Args:
            status: One of "PASS", "FAIL", or "PENDING"
        """
        self.status = status.upper()
        self.update_display()

    def update_display(self):
        """Refresh badge appearance based on current status."""
        # Format status string
        if self.status == "PASS":
            display_text = "✓ PASS"
            bg_color = QColor(0, 128, 0)  # Green
            text_color = QColor(255, 255, 255)  # White
        elif self.status == "FAIL":
            display_text = "✗ FAIL"
            bg_color = QColor(255, 0, 0)  # Red
            text_color = QColor(255, 255, 255)  # White
        else:  # PENDING
            display_text = "? PENDING"
            bg_color = QColor(192, 192, 192)  # Light gray
            text_color = QColor(0, 0, 0)  # Black

        self.label.setText(display_text)

        palette = QPalette()
        palette.setColor(QPalette.Window, bg_color)
        palette.setColor(QPalette.WindowText, text_color)
        self.setPalette(palette)
        self.setAutoFillBackground(True)
