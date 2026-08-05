"""Activity feed widget replacing the terminal-style Phase History log."""

from datetime import datetime

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .theme import (
    BG_PANEL,
    COLOR_PRIMARY,
    COLOR_SUCCESS,
    SANS_FONT_STACK,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)

_DOT_COLORS = {
    "success": COLOR_SUCCESS,
    "progress": COLOR_PRIMARY,
    "info": TEXT_MUTED,
}


class ActivityFeedWidget(QWidget):
    """Scrollable activity feed that replaces the monospace Phase History log.

    Each entry is a dot-timeline row: colored bullet + message + timestamp.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._count = 0
        self._init_ui()

    def _init_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setStyleSheet(
            f"QScrollArea {{ background: {BG_PANEL}; border: none; }}"
        )

        self._container = QWidget()
        self._container.setStyleSheet(f"background: {BG_PANEL};")
        self._feed_layout = QVBoxLayout(self._container)
        self._feed_layout.setContentsMargins(8, 8, 8, 8)
        self._feed_layout.setSpacing(7)
        self._feed_layout.addStretch()

        self._scroll.setWidget(self._container)
        outer.addWidget(self._scroll)

    def count(self) -> int:
        """Return number of entries currently in the feed."""
        return self._count

    def append(self, message: str, entry_type: str = "info") -> None:
        """Add an entry to the bottom of the feed."""
        row = self._make_row(message, entry_type)
        # Insert before the trailing stretch
        self._feed_layout.insertWidget(self._feed_layout.count() - 1, row)
        self._count += 1
        QTimer.singleShot(0, self._scroll_to_bottom)

    def clear(self) -> None:
        """Remove all entries from the feed."""
        while self._feed_layout.count() > 1:
            item = self._feed_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._count = 0

    def _scroll_to_bottom(self) -> None:
        bar = self._scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _make_row(self, message: str, entry_type: str) -> QWidget:
        timestamp = datetime.now().strftime("%-I:%M %p")
        dot_color = _DOT_COLORS.get(entry_type, TEXT_MUTED)
        msg_color = (
            TEXT_PRIMARY
            if entry_type in ("success", "progress")
            else TEXT_SECONDARY
        )

        row = QWidget()
        row.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignTop)

        dot = QLabel("●")
        dot.setStyleSheet(
            f"color: {dot_color}; font-size: 7px; background: transparent;"
        )
        dot.setFixedWidth(10)
        dot.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        layout.addWidget(dot)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(1)

        msg_label = QLabel(message)
        msg_label.setStyleSheet(
            f"color: {msg_color}; font-size: 11px; "
            f"font-family: {SANS_FONT_STACK}; background: transparent;"
        )
        msg_label.setWordWrap(True)
        text_col.addWidget(msg_label)

        ts_label = QLabel(timestamp)
        ts_label.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 10px; "
            f"font-family: {SANS_FONT_STACK}; background: transparent;"
        )
        text_col.addWidget(ts_label)

        text_widget = QWidget()
        text_widget.setStyleSheet("background: transparent;")
        text_widget.setLayout(text_col)
        layout.addWidget(text_widget)

        return row
