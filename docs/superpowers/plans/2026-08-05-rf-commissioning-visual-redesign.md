# RF Commissioning Visual Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the neon-green/cyan dark theme with a softer muted dark palette (periwinkle + sage), use system fonts for labels, and replace the terminal-style Phase History log with an activity-feed widget.

**Architecture:** Create a single `theme.py` constants module; update `styles.py` to reference it; build a new `ActivityFeedWidget` to replace the `QTextEdit` history log; then sweep through all container and display files replacing hardcoded hex colors with named theme constants.

**Tech Stack:** PyQt5, Python 3.10+. Run UI headless with `PYDM_DEFAULT_PROTOCOL=fake`. Tests use `pytest-qt` (`qtbot` fixture).

---

## File Map

| Action | Path |
|--------|------|
| Create | `src/sc_linac_physics/applications/rf_commissioning/ui/builders/theme.py` |
| Create | `src/sc_linac_physics/applications/rf_commissioning/ui/builders/activity_feed.py` |
| Create | `tests/applications/rf_commissioning/ui/builders/test_activity_feed.py` |
| Modify | `src/.../ui/builders/styles.py` |
| Modify | `src/.../ui/builders/__init__.py` |
| Modify | `src/.../ui/builders/base.py` |
| Modify | `src/.../ui/phase_display_base.py` |
| Modify | `src/.../ui/container/header.py` |
| Modify | `src/.../ui/container/sync.py` |
| Modify | `src/.../ui/container/progress_panel.py` |
| Modify | `src/.../ui/container/notes.py` |
| Modify | `src/.../ui/magnet_status_badge.py` |
| Modify | `src/.../ui/displays/base_placeholder.py` |
| Modify | `src/.../ui/displays/ssa_char.py` |
| Modify | `src/.../ui/displays/piezo_pre_rf.py` |
| Modify | `src/.../ui/displays/batch_piezo_pre_rf.py` |
| Modify | `tests/.../ui/builders/test_phase_ui_base.py` |

All paths under `src/` are relative to `src/sc_linac_physics/applications/rf_commissioning/`.
All paths under `tests/` are relative to `tests/applications/rf_commissioning/`.

---

## Task 1 — Create `theme.py`

**Files:**
- Create: `src/sc_linac_physics/applications/rf_commissioning/ui/builders/theme.py`

- [ ] **Step 1: Create the file**

```python
"""Centralized visual theme tokens for the RF commissioning UI."""

import sys

# ── Fonts ──────────────────────────────────────────────────────────────────────

if sys.platform == "darwin":
    MONO_FONT_STACK = (
        "'Menlo', 'Monaco', 'Consolas', 'DejaVu Sans Mono', "
        "'Liberation Mono', 'Noto Sans Mono'"
    )
elif sys.platform.startswith("linux"):
    MONO_FONT_STACK = (
        "'DejaVu Sans Mono', 'Liberation Mono', 'Noto Sans Mono', "
        "'Consolas', 'Menlo', 'Monaco'"
    )
else:
    MONO_FONT_STACK = (
        "'Consolas', 'DejaVu Sans Mono', 'Liberation Mono', "
        "'Noto Sans Mono', 'Menlo', 'Monaco'"
    )

SANS_FONT_STACK = (
    "system-ui, -apple-system, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif"
)

# ── Backgrounds ────────────────────────────────────────────────────────────────

BG_DEEP = "#1c1f26"
BG_PANEL = "#242830"
BG_INTERACTIVE = "#2d3344"
BG_INSET = "#1c2030"
BG_PV = "#1c2030"
BG_LOCAL = "#211d18"

# Status display backgrounds (used in stored-data status labels)
BG_STATUS_PASS = "#1e3020"
BG_STATUS_FAIL = "#2d1a1a"
BG_STATUS_INCOMPLETE = "#2d2415"

# ── Borders ────────────────────────────────────────────────────────────────────

BORDER = "#353a45"
BORDER_EMPHASIS = "#454c5e"

# ── Text ───────────────────────────────────────────────────────────────────────

TEXT_PRIMARY = "#c9cdd6"
TEXT_SECONDARY = "#8b96a8"
TEXT_MUTED = "#5a6278"
TEXT_DISABLED = "#5a6278"

# ── Semantic colors ────────────────────────────────────────────────────────────

COLOR_SUCCESS = "#4ab782"
COLOR_PRIMARY = "#7b8cde"
COLOR_WARNING = "#d4956a"
COLOR_ERROR = "#c0544a"
COLOR_DISABLED = "#353a45"

# Accent colors for label left-border stripes
ACCENT_PV = "#8b96c4"
ACCENT_LOCAL = "#c4956b"

# Translucent tinted backgrounds for badge/chip use
COLOR_SUCCESS_BG = "rgba(74, 183, 130, 0.12)"
COLOR_SUCCESS_BORDER = "rgba(74, 183, 130, 0.25)"
COLOR_WARNING_BG = "rgba(212, 149, 106, 0.15)"
COLOR_PRIMARY_BG = "rgba(123, 140, 222, 0.12)"
COLOR_PRIMARY_BORDER = "#3d4560"

# Text colors for status labels
COLOR_STATUS_PASS = "#6ebf8e"
COLOR_STATUS_FAIL = "#d47070"
COLOR_STATUS_INCOMPLETE = "#d4af70"

# ── Shape ──────────────────────────────────────────────────────────────────────

RADIUS_LG = "8px"
RADIUS_MD = "6px"
RADIUS_SM = "5px"
```

- [ ] **Step 2: Verify no import errors**

```bash
cd /Users/zacarias/sc_linac_physics
python -c "from src.sc_linac_physics.applications.rf_commissioning.ui.builders.theme import COLOR_SUCCESS, COLOR_PRIMARY; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/sc_linac_physics/applications/rf_commissioning/ui/builders/theme.py
git commit -m "feat(rf-commissioning): add centralized visual theme module"
```

---

## Task 2 — Update `styles.py` and `__init__.py`

**Files:**
- Modify: `src/sc_linac_physics/applications/rf_commissioning/ui/builders/styles.py`
- Modify: `src/sc_linac_physics/applications/rf_commissioning/ui/builders/__init__.py`

- [ ] **Step 1: Replace `styles.py` entirely**

```python
"""Shared style constants for RF commissioning UI builders."""

from .theme import (
    ACCENT_LOCAL,
    ACCENT_PV,
    BG_INSET,
    BG_LOCAL,
    BG_STATUS_FAIL,
    BG_STATUS_INCOMPLETE,
    BG_STATUS_PASS,
    BORDER,
    COLOR_STATUS_FAIL,
    COLOR_STATUS_INCOMPLETE,
    COLOR_STATUS_PASS,
    MONO_FONT_STACK,
    RADIUS_SM,
    SANS_FONT_STACK,
)

__all__ = [
    "LOCAL_CAP_STYLE",
    "LOCAL_LABEL_STYLE",
    "MONO_FONT_STACK",
    "PV_CAP_STYLE",
    "PV_LABEL_STYLE",
    "SANS_FONT_STACK",
    "STATUS_LABEL_FAIL",
    "STATUS_LABEL_INCOMPLETE",
    "STATUS_LABEL_PASS",
]

PV_LABEL_STYLE = (
    f"background: {BG_INSET}; padding: 2px 6px; "
    f"border: 1px solid {ACCENT_PV}; border-left: 3px solid {ACCENT_PV}; "
    f"font-size: 11px; border-radius: {RADIUS_SM};"
)

PV_CAP_STYLE = (
    f"background-color: {BG_INSET}; padding: 2px 6px; "
    f"border: 1px solid {ACCENT_PV}; border-left: 3px solid {ACCENT_PV}; "
    f"font-family: {MONO_FONT_STACK}; font-size: 11px; border-radius: {RADIUS_SM};"
)

LOCAL_LABEL_STYLE = (
    f"background: {BG_LOCAL}; padding: 2px 6px; "
    f"border: 1px solid {ACCENT_LOCAL}; border-left: 3px solid {ACCENT_LOCAL}; "
    f"font-size: 11px; border-radius: {RADIUS_SM};"
)

LOCAL_CAP_STYLE = (
    f"background-color: {BG_LOCAL}; padding: 2px 6px; "
    f"border: 1px solid {ACCENT_LOCAL}; border-left: 3px solid {ACCENT_LOCAL}; "
    f"font-family: {MONO_FONT_STACK}; font-size: 11px; border-radius: {RADIUS_SM};"
)

STATUS_LABEL_PASS = (
    f"background: {BG_STATUS_PASS}; padding: 2px 6px; "
    f"border: 1px solid {ACCENT_LOCAL}; border-left: 3px solid {ACCENT_LOCAL}; "
    f"font-size: 11px; border-radius: {RADIUS_SM}; "
    f"color: {COLOR_STATUS_PASS}; font-weight: bold;"
)

STATUS_LABEL_FAIL = (
    f"background: {BG_STATUS_FAIL}; padding: 2px 6px; "
    f"border: 1px solid {ACCENT_LOCAL}; border-left: 3px solid {ACCENT_LOCAL}; "
    f"font-size: 11px; border-radius: {RADIUS_SM}; "
    f"color: {COLOR_STATUS_FAIL}; font-weight: bold;"
)

STATUS_LABEL_INCOMPLETE = (
    f"background: {BG_STATUS_INCOMPLETE}; padding: 2px 6px; "
    f"border: 1px solid {ACCENT_LOCAL}; border-left: 3px solid {ACCENT_LOCAL}; "
    f"font-size: 11px; border-radius: {RADIUS_SM}; "
    f"color: {COLOR_STATUS_INCOMPLETE};"
)
```

- [ ] **Step 2: Update `__init__.py` to export new symbols**

Replace the full content of `src/sc_linac_physics/applications/rf_commissioning/ui/builders/__init__.py`:

```python
"""Public exports for RF commissioning UI builder modules."""

from .base import PhaseUIBase
from .phase_builders import (
    GenericPhaseUI,
    PiezoPreRFUI,
    SSACharUI,
)
from .styles import (
    LOCAL_CAP_STYLE,
    LOCAL_LABEL_STYLE,
    MONO_FONT_STACK,
    PV_CAP_STYLE,
    PV_LABEL_STYLE,
    SANS_FONT_STACK,
    STATUS_LABEL_FAIL,
    STATUS_LABEL_INCOMPLETE,
    STATUS_LABEL_PASS,
)

__all__ = [
    "PhaseUIBase",
    "PiezoPreRFUI",
    "SSACharUI",
    "GenericPhaseUI",
    "MONO_FONT_STACK",
    "SANS_FONT_STACK",
    "PV_LABEL_STYLE",
    "PV_CAP_STYLE",
    "LOCAL_LABEL_STYLE",
    "LOCAL_CAP_STYLE",
    "STATUS_LABEL_PASS",
    "STATUS_LABEL_FAIL",
    "STATUS_LABEL_INCOMPLETE",
]
```

- [ ] **Step 3: Run existing builder tests**

```bash
cd /Users/zacarias/sc_linac_physics
pytest tests/applications/rf_commissioning/ui/builders/ -v
```

Expected: all tests pass (style strings changed values but no tests assert specific hex codes).

- [ ] **Step 4: Commit**

```bash
git add src/sc_linac_physics/applications/rf_commissioning/ui/builders/styles.py \
        src/sc_linac_physics/applications/rf_commissioning/ui/builders/__init__.py
git commit -m "refactor(rf-commissioning): centralise color tokens in theme.py"
```

---

## Task 3 — Create `ActivityFeedWidget` (TDD)

**Files:**
- Create: `tests/applications/rf_commissioning/ui/builders/test_activity_feed.py`
- Create: `src/sc_linac_physics/applications/rf_commissioning/ui/builders/activity_feed.py`
- Modify: `src/sc_linac_physics/applications/rf_commissioning/ui/builders/__init__.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/applications/rf_commissioning/ui/builders/test_activity_feed.py`:

```python
"""Tests for ActivityFeedWidget."""

import pytest

from sc_linac_physics.applications.rf_commissioning.ui.builders.activity_feed import (
    ActivityFeedWidget,
)


@pytest.fixture
def feed(qtbot):
    widget = ActivityFeedWidget()
    qtbot.addWidget(widget)
    return widget


def test_starts_empty(feed):
    assert feed.count() == 0


def test_append_increments_count(feed):
    feed.append("Step done")
    assert feed.count() == 1


def test_append_multiple(feed):
    feed.append("First")
    feed.append("Second")
    feed.append("Third")
    assert feed.count() == 3


def test_clear_resets_count(feed):
    feed.append("Step A")
    feed.append("Step B")
    feed.clear()
    assert feed.count() == 0


def test_clear_on_empty_is_safe(feed):
    feed.clear()
    assert feed.count() == 0


def test_append_after_clear(feed):
    feed.append("Before")
    feed.clear()
    feed.append("After")
    assert feed.count() == 1


@pytest.mark.parametrize("entry_type", ["info", "success", "progress"])
def test_valid_entry_types_accepted(feed, entry_type):
    feed.append("message", entry_type=entry_type)
    assert feed.count() == 1


def test_default_entry_type_is_info(feed):
    feed.append("plain message")
    assert feed.count() == 1
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /Users/zacarias/sc_linac_physics
pytest tests/applications/rf_commissioning/ui/builders/test_activity_feed.py -v
```

Expected: `ImportError` — `activity_feed` module does not exist yet.

- [ ] **Step 3: Implement `ActivityFeedWidget`**

Create `src/sc_linac_physics/applications/rf_commissioning/ui/builders/activity_feed.py`:

```python
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
    ACCENT_LOCAL,
    BG_PANEL,
    BORDER,
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
        msg_color = TEXT_PRIMARY if entry_type in ("success", "progress") else TEXT_SECONDARY

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
```

- [ ] **Step 4: Run tests — expect pass**

```bash
cd /Users/zacarias/sc_linac_physics
pytest tests/applications/rf_commissioning/ui/builders/test_activity_feed.py -v
```

Expected: all 9 tests pass.

- [ ] **Step 5: Add `ActivityFeedWidget` to `__init__.py`**

In `src/sc_linac_physics/applications/rf_commissioning/ui/builders/__init__.py`, add to imports:

```python
from .activity_feed import ActivityFeedWidget
```

And add `"ActivityFeedWidget"` to `__all__`.

- [ ] **Step 6: Commit**

```bash
git add src/sc_linac_physics/applications/rf_commissioning/ui/builders/activity_feed.py \
        src/sc_linac_physics/applications/rf_commissioning/ui/builders/__init__.py \
        tests/applications/rf_commissioning/ui/builders/test_activity_feed.py
git commit -m "feat(rf-commissioning): add ActivityFeedWidget for phase history"
```

---

## Task 4 — Update `base.py`

**Files:**
- Modify: `src/sc_linac_physics/applications/rf_commissioning/ui/builders/base.py`
- Modify: `tests/applications/rf_commissioning/ui/builders/test_phase_ui_base.py`

- [ ] **Step 1: Update the failing test for `_build_history`**

In `tests/applications/rf_commissioning/ui/builders/test_phase_ui_base.py`, replace the `test_build_history_creates_readonly_bounded_text_widget` test:

```python
from sc_linac_physics.applications.rf_commissioning.ui.builders.activity_feed import (
    ActivityFeedWidget,
)

def test_build_history_creates_activity_feed(base):
    group = base._build_history()
    history_widget = base.widgets["history_text"]

    assert group.title() == "Phase History"
    assert isinstance(history_widget, ActivityFeedWidget)
    assert history_widget.count() == 0
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd /Users/zacarias/sc_linac_physics
pytest tests/applications/rf_commissioning/ui/builders/test_phase_ui_base.py::test_build_history_creates_activity_feed -v
```

Expected: FAIL — `history_text` is a `QTextEdit`, not an `ActivityFeedWidget`.

- [ ] **Step 3: Replace `base.py` entirely**

```python
"""Base UI builder used by RF commissioning phase screens."""

from collections.abc import Callable
from typing import TypeVar

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

from .activity_feed import ActivityFeedWidget
from .styles import LOCAL_LABEL_STYLE
from .theme import (
    ACCENT_LOCAL,
    BG_LOCAL,
    BG_PANEL,
    BORDER,
    BORDER_EMPHASIS,
    COLOR_DISABLED,
    COLOR_ERROR,
    COLOR_PRIMARY,
    COLOR_SUCCESS,
    COLOR_WARNING,
    MONO_FONT_STACK,
    RADIUS_LG,
    RADIUS_MD,
    SANS_FONT_STACK,
    TEXT_DISABLED,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class PhaseUIBase:
    """Base UI builder with common components for all commissioning phases."""

    def __init__(
        self,
        parent,
        callbacks: dict[str, Callable[[], None]] | None = None,
    ) -> None:
        self.parent = parent
        self.callbacks = callbacks or {}
        self.widgets: dict[str, object] = {}

    _W = TypeVar("_W")

    def _register(self, name: str, widget: _W) -> _W:
        """Register a widget by name for easy access."""
        self.widgets[name] = widget
        return widget

    def _connect(self, widget, callback_key: str) -> None:
        """Connect widget signal to callback if callback exists."""
        callback = self.callbacks.get(callback_key)
        if callback:
            widget.clicked.connect(callback)

    def _build_main_toolbar(self) -> QVBoxLayout:
        """Create an enhanced toolbar with better controls and visual hierarchy."""
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        toolbar.setContentsMargins(4, 4, 4, 4)

        primary_group = QHBoxLayout()
        primary_group.setSpacing(4)

        run_button = self._register("run_button", QPushButton("▶ Start Test"))
        run_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_PRIMARY};
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: {RADIUS_MD};
                border: none;
                font-size: 11pt;
                font-family: {SANS_FONT_STACK};
            }}
            QPushButton:hover {{
                background-color: #6a7bce;
            }}
            QPushButton:pressed {{
                background-color: #5a6abf;
            }}
            QPushButton:disabled {{
                background-color: {COLOR_DISABLED};
                color: {TEXT_DISABLED};
            }}
        """)
        run_button.setFixedHeight(40)
        run_button.setMinimumWidth(120)
        self._connect(run_button, "on_run_automated_test")

        pause_button = self._register("pause_button", QPushButton("⏸ Pause"))
        pause_button.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {TEXT_SECONDARY};
                font-weight: bold;
                padding: 10px 16px;
                border-radius: {RADIUS_MD};
                border: 1px solid {BORDER_EMPHASIS};
                font-family: {SANS_FONT_STACK};
            }}
            QPushButton:hover {{
                background-color: {BORDER_EMPHASIS};
                color: {TEXT_PRIMARY};
            }}
            QPushButton:disabled {{
                background-color: transparent;
                color: {TEXT_DISABLED};
                border-color: {BORDER};
            }}
        """)
        pause_button.setFixedHeight(40)
        pause_button.setEnabled(False)
        self._connect(pause_button, "on_pause_test")

        abort_button = self._register("abort_button", QPushButton("⏹ Abort"))
        abort_button.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {COLOR_ERROR};
                font-weight: bold;
                padding: 10px 16px;
                border-radius: {RADIUS_MD};
                border: 1px solid {COLOR_ERROR};
                font-family: {SANS_FONT_STACK};
            }}
            QPushButton:hover {{
                background-color: rgba(192, 84, 74, 0.12);
            }}
            QPushButton:disabled {{
                background-color: transparent;
                color: {TEXT_DISABLED};
                border-color: {BORDER};
            }}
        """)
        abort_button.setFixedHeight(40)
        abort_button.setEnabled(False)
        self._connect(abort_button, "on_abort_test")

        primary_group.addWidget(run_button)
        primary_group.addWidget(pause_button)
        primary_group.addWidget(abort_button)

        sep1 = QFrame()
        sep1.setFrameShape(QFrame.VLine)
        sep1.setFrameShadow(QFrame.Sunken)
        sep1.setStyleSheet(f"QFrame {{ color: {BORDER}; }}")

        secondary_group = QHBoxLayout()
        secondary_group.setSpacing(4)

        step_mode_btn = self._register(
            "step_mode_btn", QPushButton("Step Mode")
        )
        step_mode_btn.setCheckable(True)
        step_mode_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {BORDER_EMPHASIS};
                color: {TEXT_SECONDARY};
                padding: 8px 12px;
                border-radius: {RADIUS_MD};
                border: 1px solid {BORDER_EMPHASIS};
                font-family: {SANS_FONT_STACK};
            }}
            QPushButton:checked {{
                background-color: {COLOR_SUCCESS};
                color: white;
                border: 1px solid {COLOR_SUCCESS};
            }}
            QPushButton:hover {{
                background-color: {BORDER};
            }}
        """)
        step_mode_btn.setFixedHeight(40)
        self._connect(step_mode_btn, "on_toggle_step_mode")

        next_step_btn = self._register("next_step_btn", QPushButton("Next →"))
        next_step_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_PRIMARY};
                color: white;
                padding: 8px 12px;
                border-radius: {RADIUS_MD};
                font-family: {SANS_FONT_STACK};
            }}
            QPushButton:disabled {{
                background-color: {BORDER_EMPHASIS};
                color: {TEXT_MUTED};
            }}
        """)
        next_step_btn.setFixedHeight(40)
        next_step_btn.setEnabled(False)
        self._connect(next_step_btn, "on_next_step")

        secondary_group.addWidget(step_mode_btn)
        secondary_group.addWidget(next_step_btn)

        status_section = QVBoxLayout()
        status_section.setSpacing(2)

        status_indicator = self._register("status_indicator", QLabel("● READY"))
        status_indicator.setStyleSheet(f"""
            QLabel {{
                color: {COLOR_SUCCESS};
                font-weight: bold;
                font-size: 10pt;
                font-family: {SANS_FONT_STACK};
            }}
        """)
        status_indicator.setAlignment(Qt.AlignRight)

        timestamp_label = self._register("timestamp_label", QLabel("--:--:--"))
        timestamp_label.setAlignment(Qt.AlignRight)
        timestamp_label.setStyleSheet(f"""
            QLabel {{
                color: {TEXT_MUTED};
                font-size: 9pt;
                font-family: {MONO_FONT_STACK};
            }}
        """)

        status_section.addWidget(status_indicator)
        status_section.addWidget(timestamp_label)

        toolbar.addLayout(primary_group)
        toolbar.addWidget(sep1)
        toolbar.addLayout(secondary_group)
        toolbar.addStretch()
        toolbar.addLayout(status_section)

        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {BG_PANEL};
                border: 1px solid {BORDER};
                border-radius: {RADIUS_LG};
                padding: 4px;
            }}
        """)
        frame.setLayout(toolbar)

        wrapper = QVBoxLayout()
        wrapper.setContentsMargins(0, 0, 0, 0)
        wrapper.addWidget(frame)

        return wrapper

    def update_toolbar_state(self, state: str) -> None:
        """Update toolbar button states based on test state."""
        run_btn = self.widgets.get("run_button")
        pause_btn = self.widgets.get("pause_button")
        abort_btn = self.widgets.get("abort_button")
        status_ind = self.widgets.get("status_indicator")

        if any(w is None for w in (run_btn, pause_btn, abort_btn, status_ind)):
            raise RuntimeError(
                "update_toolbar_state() called before _build_main_toolbar() "
                "completed; one or more toolbar widgets are not registered."
            )

        _status_style = (
            "QLabel {{ color: {}; font-weight: bold; font-size: 10pt; "
            f"font-family: {SANS_FONT_STACK}; }}"
        )

        if state == "idle":
            run_btn.setEnabled(True)
            run_btn.setText("▶ Start Test")
            pause_btn.setEnabled(False)
            abort_btn.setEnabled(False)
            status_ind.setText("● READY")
            status_ind.setStyleSheet(_status_style.format(COLOR_SUCCESS))

        elif state == "running":
            run_btn.setEnabled(False)
            pause_btn.setEnabled(True)
            abort_btn.setEnabled(True)
            status_ind.setText("● RUNNING")
            status_ind.setStyleSheet(_status_style.format(COLOR_PRIMARY))

        elif state == "paused":
            run_btn.setEnabled(True)
            run_btn.setText("▶ Resume")
            pause_btn.setEnabled(False)
            abort_btn.setEnabled(True)
            status_ind.setText("● PAUSED")
            status_ind.setStyleSheet(_status_style.format(COLOR_WARNING))

        elif state == "complete":
            run_btn.setEnabled(True)
            run_btn.setText("▶ Start Test")
            pause_btn.setEnabled(False)
            abort_btn.setEnabled(False)
            status_ind.setText("✓ COMPLETE")
            status_ind.setStyleSheet(_status_style.format(COLOR_SUCCESS))

        elif state == "error":
            run_btn.setEnabled(True)
            run_btn.setText("▶ Retry")
            pause_btn.setEnabled(False)
            abort_btn.setEnabled(False)
            status_ind.setText("✗ ERROR")
            status_ind.setStyleSheet(_status_style.format(COLOR_ERROR))

    def _build_history(self) -> QGroupBox:
        """Build the phase activity feed section."""
        group = QGroupBox("Phase History")

        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(3)

        feed = self._register("history_text", ActivityFeedWidget())
        feed.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        feed.setMinimumHeight(60)
        feed.setMaximumHeight(180)

        layout.addWidget(feed)
        group.setLayout(layout)
        return group

    def _build_basic_results_section(self, phase_name: str) -> QGroupBox:
        """Build a basic results section for placeholder phases."""
        group = QGroupBox(f"{phase_name} - Status && Results")
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)

        step_label = QLabel("Current Step:")
        step_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(step_label)

        current_step = self._register("local_current_step", QLabel("-"))
        current_step.setStyleSheet(
            LOCAL_LABEL_STYLE + "min-height: 30px; font-size: 12pt;"
        )
        current_step.setAlignment(Qt.AlignCenter)
        layout.addWidget(current_step)

        phase_label = QLabel("Test Status:")
        phase_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        layout.addWidget(phase_label)

        phase_status = self._register("local_phase_status", QLabel("-"))
        phase_status.setStyleSheet(
            LOCAL_LABEL_STYLE + "min-height: 30px; font-size: 12pt;"
        )
        phase_status.setAlignment(Qt.AlignCenter)
        layout.addWidget(phase_status)

        layout.addStretch()
        group.setLayout(layout)
        return group

    def _make_local_label(self, text: str) -> QLabel:
        """Create a local (non-EPICS) label with standard styling."""
        label = QLabel(text)
        label.setStyleSheet(LOCAL_LABEL_STYLE)
        label.setAlignment(Qt.AlignCenter)
        return label

    def _build_stored_data_section(
        self, fields: list[tuple[str, str]] | None = None
    ) -> QGroupBox:
        """Build a generalized 'Stored Data' section with standard fields."""
        fields = fields if fields is not None else []
        group = QGroupBox("Stored Data")
        layout = QVBoxLayout()
        layout.setSpacing(5)
        layout.setContentsMargins(8, 8, 8, 8)

        grid = QGridLayout()
        grid.setSpacing(5)
        grid.setColumnMinimumWidth(0, 110)
        grid.setColumnStretch(1, 1)

        row = 0

        grid.addWidget(QLabel("Progress:"), row, 0)
        progress_bar = self._register("local_progress_bar", QProgressBar())
        progress_bar.setStyleSheet(
            f"QProgressBar {{ border: 1px solid {ACCENT_LOCAL}; border-radius: 3px; "
            f"background-color: {BG_LOCAL}; text-align: center; color: white; "
            f"min-height: 20px; max-height: 20px; }} "
            f"QProgressBar::chunk {{ background-color: {ACCENT_LOCAL}; }}"
        )
        grid.addWidget(progress_bar, row, 1)
        row += 1

        grid.addWidget(QLabel("Status:"), row, 0)
        status_label = self._register(
            "local_stored_status", self._make_local_label("-")
        )
        grid.addWidget(status_label, row, 1)
        row += 1

        for label_text, widget_name in fields:
            grid.addWidget(QLabel(f"  {label_text}:"), row, 0)
            value_label = self._register(
                widget_name, self._make_local_label("-")
            )
            grid.addWidget(value_label, row, 1)
            row += 1

        grid.addWidget(QLabel("Stored At:"), row, 0)
        timestamp_label = self._register(
            "local_stored_timestamp", self._make_local_label("-")
        )
        grid.addWidget(timestamp_label, row, 1)
        row += 1

        grid.addWidget(QLabel("Notes:"), row, 0)
        notes_label = self._register(
            "local_stored_notes", self._make_local_label("-")
        )
        notes_label.setWordWrap(True)
        notes_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        grid.addWidget(notes_label, row, 1)

        layout.addLayout(grid)
        layout.addStretch()
        group.setLayout(layout)
        return group

    def _get_parent_stored_data_fields(self) -> list[tuple[str, str]]:
        """Get stored-data field definitions from the parent display."""
        if hasattr(self.parent, "get_phase_stored_field_specs"):
            return [
                (spec.label, spec.widget_name)
                for spec in self.parent.get_phase_stored_field_specs()
            ]
        return []
```

Note: `QSizePolicy` is used inside `_build_history` — add it to the import list at the top of the file:

```python
from PyQt5.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)
```

- [ ] **Step 4: Run all builder tests**

```bash
cd /Users/zacarias/sc_linac_physics
pytest tests/applications/rf_commissioning/ui/builders/ -v
```

Expected: all tests pass, including `test_build_history_creates_activity_feed`.

- [ ] **Step 5: Commit**

```bash
git add src/sc_linac_physics/applications/rf_commissioning/ui/builders/base.py \
        tests/applications/rf_commissioning/ui/builders/test_phase_ui_base.py
git commit -m "feat(rf-commissioning): update toolbar + stored-data colors, swap history to ActivityFeedWidget"
```

---

## Task 5 — Update `phase_display_base.py`

**Files:**
- Modify: `src/sc_linac_physics/applications/rf_commissioning/ui/phase_display_base.py`

The `log_message` method calls `self.history_text.append(f"[{timestamp}] {message}")`. Update it to call `append(message, entry_type)` directly so the feed widget receives clean data.

- [ ] **Step 1: Update `log_message` in `phase_display_base.py`**

Replace the `log_message` method (lines 101–105):

```python
def log_message(self, message: str, entry_type: str = "info") -> None:
    """Add a message to the phase activity feed."""
    if hasattr(self, "history_text"):
        self.history_text.append(message, entry_type=entry_type)
```

- [ ] **Step 2: Run tests**

```bash
cd /Users/zacarias/sc_linac_physics
pytest tests/applications/rf_commissioning/ -v -x
```

Expected: all pass.

- [ ] **Step 3: Commit**

```bash
git add src/sc_linac_physics/applications/rf_commissioning/ui/phase_display_base.py
git commit -m "refactor(rf-commissioning): update log_message to use activity feed entry types"
```

---

## Task 6 — Update container files

**Files:**
- Modify: `src/sc_linac_physics/applications/rf_commissioning/ui/container/header.py`
- Modify: `src/sc_linac_physics/applications/rf_commissioning/ui/container/sync.py`
- Modify: `src/sc_linac_physics/applications/rf_commissioning/ui/container/progress_panel.py`
- Modify: `src/sc_linac_physics/applications/rf_commissioning/ui/container/notes.py`

- [ ] **Step 1: Update `header.py`**

Add import at the top (after existing imports):

```python
from sc_linac_physics.applications.rf_commissioning.ui.builders.theme import (
    BG_PANEL,
    BORDER,
    BORDER_EMPHASIS,
    RADIUS_LG,
    RADIUS_MD,
    TEXT_MUTED,
    TEXT_SECONDARY,
)
```

Replace the `_vline()` function:

```python
def _vline() -> QFrame:
    sep = QFrame()
    sep.setFrameShape(QFrame.VLine)
    sep.setFrameShadow(QFrame.Sunken)
    sep.setStyleSheet(f"color: {BORDER};")
    return sep
```

Replace the `header.setStyleSheet(...)` call in `_build_header_panel`:

```python
header.setStyleSheet(f"""
    QWidget {{
        background-color: {BG_PANEL};
        border-bottom: 2px solid {BORDER};
    }}
    QGroupBox {{
        font-weight: bold;
        border: 1px solid {BORDER};
        border-radius: {RADIUS_MD};
        margin-top: 6px;
        padding-top: 8px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 8px;
        padding: 0 4px;
    }}
""")
```

Replace the `self.cavity_completion_label.setStyleSheet(...)` call:

```python
self.cavity_completion_label.setStyleSheet(f"""
    QLabel {{
        color: {TEXT_MUTED};
        font-weight: bold;
        padding: 2px 6px;
        background-color: rgba(123, 140, 222, 0.12);
        border-radius: {RADIUS_MD};
        font-size: 9px;
    }}
""")
```

Replace `self.sync_status.setStyleSheet(...)`:

```python
self.sync_status.setStyleSheet(f"""
    QLabel {{
        color: {TEXT_MUTED};
        font-weight: bold;
        padding: 2px 6px;
        background-color: rgba(90, 98, 120, 0.2);
        border-radius: {RADIUS_MD};
    }}
""")
```

- [ ] **Step 2: Update `sync.py`**

Add import at the top:

```python
from sc_linac_physics.applications.rf_commissioning.ui.builders.theme import (
    BORDER,
    BORDER_EMPHASIS,
    COLOR_SUCCESS,
    COLOR_SUCCESS_BG,
    COLOR_SUCCESS_BORDER,
    COLOR_WARNING,
    COLOR_WARNING_BG,
    RADIUS_MD,
    TEXT_PRIMARY,
)
```

Replace `_update_sync_status` inline stylesheet strings:

```python
def _update_sync_status(self, is_synced: bool, message: str = "") -> None:
    """Update the global sync status indicator."""
    if is_synced:
        self.sync_status.setText("● Synced")
        self.sync_status.setStyleSheet(f"""
            QLabel {{
                color: {COLOR_SUCCESS};
                font-weight: bold;
                padding: 5px 10px;
                background-color: {COLOR_SUCCESS_BG};
                border: 1px solid {COLOR_SUCCESS_BORDER};
                border-radius: {RADIUS_MD};
            }}
        """)
    else:
        self.sync_status.setText(f"⚠ {message or 'Out of Sync'}")
        self.sync_status.setStyleSheet(f"""
            QLabel {{
                color: {COLOR_WARNING};
                font-weight: bold;
                padding: 5px 10px;
                background-color: {COLOR_WARNING_BG};
                border-radius: {RADIUS_MD};
                border: 1px solid {COLOR_WARNING};
            }}
        """)
```

Replace `_show_update_banner` stylesheet string:

```python
self._update_banner.setStyleSheet(f"""
    QWidget {{
        background-color: {COLOR_WARNING};
        border: 2px solid rgba(180, 120, 80, 0.8);
        border-left: 5px solid rgba(180, 120, 80, 0.8);
    }}
    QLabel {{
        color: white;
        font-weight: bold;
        padding: 5px;
    }}
    QPushButton {{
        background-color: white;
        color: {COLOR_WARNING};
        font-weight: bold;
        padding: 8px 16px;
        border-radius: {RADIUS_MD};
        border: none;
    }}
    QPushButton:hover {{
        background-color: #f5f5f5;
    }}
""")
```

- [ ] **Step 3: Update `progress_panel.py`**

Add import at the top:

```python
from sc_linac_physics.applications.rf_commissioning.ui.builders.theme import (
    BG_DEEP,
    BORDER,
    COLOR_ERROR,
    COLOR_PRIMARY,
    COLOR_SUCCESS,
    TEXT_MUTED,
    TEXT_SECONDARY,
)
```

Replace the `widget.setStyleSheet(...)` in `_build_compact_progress_bar`:

```python
widget.setStyleSheet(f"""
    QWidget {{
        background-color: {BG_DEEP};
        border-bottom: 1px solid {BORDER};
    }}
""")
```

Replace `title.setStyleSheet(...)`:

```python
title.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px; font-weight: bold;")
```

Replace the initial `circle.setStyleSheet(...)`:

```python
circle.setStyleSheet(f"""
    font-size: 28px;
    color: {TEXT_MUTED};
    background-color: transparent;
""")
```

Replace `text.setStyleSheet(...)`:

```python
text.setStyleSheet(
    f"font-size: 9px; color: {TEXT_MUTED}; background-color: transparent;"
)
```

Replace `connector.setStyleSheet(...)`:

```python
connector.setStyleSheet(f"""
    color: {TEXT_MUTED};
    font-size: 16px;
    padding: 0px;
    margin: 0px 4px 24px 4px;
    background-color: transparent;
""")
```

In `update_progress_indicator`, replace all four `indicator.setStyleSheet(...)` blocks:

```python
# complete/skipped
indicator.setText("✔")
indicator.setStyleSheet(f"""
    font-size: 28px;
    color: {COLOR_SUCCESS};
    font-weight: bold;
    background-color: rgba(74, 183, 130, 0.15);
    border-radius: 16px;
    border: 2px solid {COLOR_SUCCESS};
""")

# failed
indicator.setText("✖")
indicator.setStyleSheet(f"""
    font-size: 24px;
    color: {COLOR_ERROR};
    font-weight: bold;
    background-color: rgba(192, 84, 74, 0.15);
    border-radius: 16px;
    border: 2px solid {COLOR_ERROR};
""")

# current
indicator.setText("▶")
indicator.setStyleSheet(f"""
    font-size: 24px;
    color: {COLOR_PRIMARY};
    font-weight: bold;
    background-color: rgba(123, 140, 222, 0.2);
    border-radius: 16px;
    border: 2px solid {COLOR_PRIMARY};
""")

# pending
indicator.setText("○")
indicator.setStyleSheet(f"""
    font-size: 28px;
    color: {TEXT_MUTED};
    background-color: transparent;
    border-radius: 16px;
""")
```

Replace both connector `setStyleSheet` calls in the connector loop:

```python
# filled connector (before current)
connector.setStyleSheet(f"""
    color: {COLOR_SUCCESS};
    font-size: 16px;
    font-weight: bold;
    padding: 0px;
    margin: 0px 4px 24px 4px;
    background-color: transparent;
""")

# unfilled connector
connector.setStyleSheet(f"""
    color: {TEXT_MUTED};
    font-size: 16px;
    padding: 0px;
    margin: 0px 4px 24px 4px;
    background-color: transparent;
""")
```

- [ ] **Step 4: Update `notes.py`**

Add import at the top:

```python
from sc_linac_physics.applications.rf_commissioning.ui.builders.theme import (
    BG_PANEL,
    BORDER,
    COLOR_SUCCESS,
    RADIUS_MD,
    TEXT_PRIMARY,
)
```

Replace `widget.setStyleSheet(...)`:

```python
widget.setStyleSheet(f"""
    QWidget {{
        background-color: {BG_PANEL};
        border-top: 1px solid {BORDER};
    }}
""")
```

Replace `title.setStyleSheet(...)`:

```python
title.setStyleSheet(f"font-weight: bold; font-size: 14px; color: {TEXT_PRIMARY};")
```

Replace `quick_add.setStyleSheet(...)`:

```python
quick_add.setStyleSheet(f"""
    QPushButton {{
        background-color: {COLOR_SUCCESS};
        color: white;
        border-radius: {RADIUS_MD};
        padding: 5px 15px;
        font-weight: bold;
    }}
    QPushButton:hover {{
        background-color: #3da870;
    }}
""")
```

- [ ] **Step 5: Run container tests**

```bash
cd /Users/zacarias/sc_linac_physics
pytest tests/applications/rf_commissioning/ui/test_container_helpers.py \
       tests/applications/rf_commissioning/ui/test_container_ui_builders.py \
       tests/applications/rf_commissioning/ui/test_multi_phase_screen.py -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/sc_linac_physics/applications/rf_commissioning/ui/container/header.py \
        src/sc_linac_physics/applications/rf_commissioning/ui/container/sync.py \
        src/sc_linac_physics/applications/rf_commissioning/ui/container/progress_panel.py \
        src/sc_linac_physics/applications/rf_commissioning/ui/container/notes.py
git commit -m "feat(rf-commissioning): apply muted dark theme to container widgets"
```

---

## Task 7 — Update `magnet_status_badge.py`

**Files:**
- Modify: `src/sc_linac_physics/applications/rf_commissioning/ui/magnet_status_badge.py`

- [ ] **Step 1: Update `update_display` to use theme colors**

The badge uses `QPalette` with raw `QColor` objects. Replace the three color definitions inside `update_display`:

```python
from sc_linac_physics.applications.rf_commissioning.ui.builders.theme import (
    BG_INTERACTIVE,
    COLOR_ERROR,
    COLOR_SUCCESS,
    TEXT_PRIMARY,
)
```

Replace the body of `update_display`:

```python
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
```

- [ ] **Step 2: Run the existing badge test**

```bash
cd /Users/zacarias/sc_linac_physics
pytest tests/applications/rf_commissioning/ui/test_status_widgets.py -v
```

Expected: all pass (test checks `.label.text()` and `.status`, not palette colors).

- [ ] **Step 3: Commit**

```bash
git add src/sc_linac_physics/applications/rf_commissioning/ui/magnet_status_badge.py
git commit -m "feat(rf-commissioning): apply muted dark theme to MagnetStatusBadge"
```

---

## Task 8 — Update display files

**Files:**
- Modify: `src/sc_linac_physics/applications/rf_commissioning/ui/displays/base_placeholder.py`
- Modify: `src/sc_linac_physics/applications/rf_commissioning/ui/displays/ssa_char.py`
- Modify: `src/sc_linac_physics/applications/rf_commissioning/ui/displays/piezo_pre_rf.py`
- Modify: `src/sc_linac_physics/applications/rf_commissioning/ui/displays/batch_piezo_pre_rf.py`

- [ ] **Step 1: Update `base_placeholder.py` imports**

In `base_placeholder.py`, update the import from `builders`:

```python
from sc_linac_physics.applications.rf_commissioning.ui.builders import (
    GenericPhaseUI,
    LOCAL_LABEL_STYLE,
    STATUS_LABEL_FAIL,
    STATUS_LABEL_INCOMPLETE,
    STATUS_LABEL_PASS,
)
```

- [ ] **Step 2: Update `_get_stored_status_presentation` in `base_placeholder.py`**

Replace the method body:

```python
def _get_stored_status_presentation(self, phase_data) -> tuple[str, str]:
    """Choose the stored-data status text and styling."""
    if hasattr(phase_data, "is_complete"):
        if not phase_data.is_complete:
            return "INCOMPLETE", STATUS_LABEL_INCOMPLETE
        passed = getattr(phase_data, "passed", True)
        if passed:
            return "PASS", STATUS_LABEL_PASS
        return "FAIL", STATUS_LABEL_FAIL

    return "AVAILABLE", LOCAL_LABEL_STYLE
```

- [ ] **Step 3: Update `ssa_char.py` imports and status style usage**

In `ssa_char.py`, update the import from `builders`:

```python
from sc_linac_physics.applications.rf_commissioning.ui.builders import (
    LOCAL_LABEL_STYLE,
    SSACharUI,
    STATUS_LABEL_FAIL,
    STATUS_LABEL_PASS,
)
```

In `_update_local_results` (lines 85–92), replace:

```python
pass_style = (
    LOCAL_LABEL_STYLE.replace("#2a2a1a", "#2d5016")
    + "color: #90ee90; font-weight: bold;"
)
fail_style = (
    LOCAL_LABEL_STYLE.replace("#2a2a1a", "#5c1a1a")
    + "color: #ff6b6b; font-weight: bold;"
)
```

with:

```python
pass_style = STATUS_LABEL_PASS
fail_style = STATUS_LABEL_FAIL
```

- [ ] **Step 4: Update `piezo_pre_rf.py` imports and status style usage**

In `piezo_pre_rf.py`, update the import:

```python
from sc_linac_physics.applications.rf_commissioning.ui.builders import (
    LOCAL_CAP_STYLE,
    LOCAL_LABEL_STYLE,
    PiezoPreRFUI,
    STATUS_LABEL_FAIL,
    STATUS_LABEL_PASS,
)
```

In `_update_local_results` (lines 94–101), replace:

```python
pass_style = (
    LOCAL_LABEL_STYLE.replace("#2a2a1a", "#2d5016")
    + "color: #90ee90; font-weight: bold;"
)
fail_style = (
    LOCAL_LABEL_STYLE.replace("#2a2a1a", "#5c1a1a")
    + "color: #ff6b6b; font-weight: bold;"
)
```

with:

```python
pass_style = STATUS_LABEL_PASS
fail_style = STATUS_LABEL_FAIL
```

- [ ] **Step 5: Update `batch_piezo_pre_rf.py` status color map**

Add import at the top of the file:

```python
from sc_linac_physics.applications.rf_commissioning.ui.builders.theme import (
    COLOR_ERROR,
    COLOR_PRIMARY,
    COLOR_SUCCESS,
    COLOR_WARNING,
    TEXT_MUTED,
    TEXT_SECONDARY,
)
```

Replace the `_STATUS_COLORS` dict:

```python
_STATUS_COLORS: dict[str, str] = {
    "PENDING": TEXT_MUTED,
    "TRIGGERING": COLOR_PRIMARY,
    "TRIGGERED": COLOR_PRIMARY,
    "COLLECTING": COLOR_WARNING,
    "PASSED": COLOR_SUCCESS,
    "FAILED": COLOR_ERROR,
    "ERROR": "#8b7cde",   # Muted violet — distinct from FAILED
    "SKIPPED": TEXT_SECONDARY,
}
```

- [ ] **Step 6: Run the full RF commissioning test suite**

```bash
cd /Users/zacarias/sc_linac_physics
pytest tests/applications/rf_commissioning/ -v
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add src/sc_linac_physics/applications/rf_commissioning/ui/displays/base_placeholder.py \
        src/sc_linac_physics/applications/rf_commissioning/ui/displays/ssa_char.py \
        src/sc_linac_physics/applications/rf_commissioning/ui/displays/piezo_pre_rf.py \
        src/sc_linac_physics/applications/rf_commissioning/ui/displays/batch_piezo_pre_rf.py
git commit -m "feat(rf-commissioning): apply muted dark theme to all phase displays"
```

---

## Verification

After all tasks complete, run the full suite and check coverage:

```bash
cd /Users/zacarias/sc_linac_physics
pytest tests/applications/rf_commissioning/ -v --tb=short
```

To visually verify the UI without hardware:

```bash
PYDM_DEFAULT_PROTOCOL=fake python -m sc_linac_physics.cli rf-commissioning
```
