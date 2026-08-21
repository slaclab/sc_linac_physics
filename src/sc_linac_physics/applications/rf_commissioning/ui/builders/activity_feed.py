"""Activity feed widget replacing the terminal-style Phase History log."""

from datetime import datetime

from PyQt5.QtCore import Qt
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
    BORDER,
    COLOR_ERROR,
    COLOR_PRIMARY,
    COLOR_SUCCESS,
    RADIUS_LG,
    SANS_FONT_STACK,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)

_DOT_COLORS = {
    "success": COLOR_SUCCESS,
    "progress": COLOR_PRIMARY,
    "error": COLOR_ERROR,
    "info": TEXT_MUTED,
}

_EMPHASIZED_TYPES = ("success", "progress", "error")


class ActivityFeedWidget(QWidget):
    """Scrollable activity feed that replaces the monospace Phase History log.

    Each entry is a dot-timeline row: colored bullet + message + timestamp.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._count = 0
        # key -> (row widget, message label, dot label) for entries that can be
        # resolved in place. A long-running step logs once when it starts and
        # then updates that same row when it finishes, rather than appending a
        # second near-identical line — the feed was showing every substep twice
        # ("▶ Probing stepper direction..." then "✓ Probing stepper direction"),
        # which doubled its length for no added information.
        self._keyed_rows: dict[str, tuple[QWidget, QLabel, QLabel]] = {}
        self._init_ui()

    def _init_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setStyleSheet(
            f"QScrollArea {{ background: {BG_PANEL}; "
            f"border: 1px solid {BORDER}; border-radius: {RADIUS_LG}; }}"
        )

        self._container = QWidget()
        self._container.setStyleSheet(f"background: {BG_PANEL};")
        self._feed_layout = QVBoxLayout(self._container)
        self._feed_layout.setContentsMargins(8, 8, 8, 8)
        self._feed_layout.setSpacing(7)
        self._feed_layout.addStretch()

        self._scroll.setWidget(self._container)
        self._scroll.verticalScrollBar().rangeChanged.connect(
            lambda _min, max_: self._scroll.verticalScrollBar().setValue(max_)
        )

        self._placeholder = QLabel("Activity will appear here when a test runs")
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 11px; "
            f"font-family: {SANS_FONT_STACK}; font-style: italic;"
        )
        outer.addWidget(self._placeholder)
        outer.addWidget(self._scroll)
        self._scroll.hide()

    def count(self) -> int:
        """Return number of entries currently in the feed."""
        return self._count

    def append(
        self, message: str, entry_type: str = "info", key: str | None = None
    ) -> None:
        """Add an entry to the bottom of the feed.

        Passing ``key`` marks the entry as resolvable: a later ``resolve(key,
        ...)`` rewrites this row in place instead of adding another one.
        """
        row, msg_label, dot = self._make_row(message, entry_type)
        # Insert before the trailing stretch
        self._feed_layout.insertWidget(self._feed_layout.count() - 1, row)
        self._count += 1
        if key is not None:
            self._keyed_rows[key] = (row, msg_label, dot)
        if self._count == 1:
            self._placeholder.hide()
            self._scroll.show()

    def resolve(
        self, key: str, message: str, entry_type: str = "success"
    ) -> bool:
        """Rewrite a previously keyed entry in place.

        Returns True if a row was updated. Falls back to appending a new entry
        when the key is unknown — a step whose start was never logged still has
        to report its outcome.
        """
        entry = self._keyed_rows.pop(key, None)
        if entry is None:
            self.append(message, entry_type)
            return False

        _row, msg_label, dot = entry
        msg_label.setText(message)
        msg_label.setStyleSheet(self._message_style(entry_type))
        dot.setStyleSheet(self._dot_style(entry_type))
        return True

    def clear(self) -> None:
        """Remove all entries from the feed."""
        while self._feed_layout.count() > 1:
            item = self._feed_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._count = 0
        self._keyed_rows.clear()
        self._placeholder.show()
        self._scroll.hide()

    def _scroll_to_bottom(self) -> None:
        bar = self._scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    @staticmethod
    def _dot_style(entry_type: str) -> str:
        dot_color = _DOT_COLORS.get(entry_type, TEXT_MUTED)
        return f"color: {dot_color}; font-size: 7px; background: transparent;"

    @staticmethod
    def _message_style(entry_type: str) -> str:
        msg_color = (
            TEXT_PRIMARY if entry_type in _EMPHASIZED_TYPES else TEXT_SECONDARY
        )
        return (
            f"color: {msg_color}; font-size: 11px; "
            f"font-family: {SANS_FONT_STACK}; background: transparent;"
        )

    def _make_row(
        self, message: str, entry_type: str
    ) -> tuple[QWidget, QLabel, QLabel]:
        """Build one feed row, returning (row, message label, dot label).

        The two labels come back so resolve() can restyle them later.
        """
        timestamp = datetime.now().strftime("%I:%M %p").lstrip("0")

        row = QWidget()
        row.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignTop)

        dot = QLabel("●")
        dot.setStyleSheet(self._dot_style(entry_type))
        dot.setFixedWidth(10)
        dot.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        layout.addWidget(dot)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(1)

        msg_label = QLabel(message)
        msg_label.setStyleSheet(self._message_style(entry_type))
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

        return row, msg_label, dot
