# Auto Setup UI Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite the SRF Auto Setup GUI from a tab-heavy, status-blind UI to a three-level tile hierarchy with color-coded status, lock support, and editable ACON per cavity.

**Architecture:** Single scrollable page; linac tiles (row) → CM tiles (flow-wrapped panel) → cavity cards (4×2 grid). Status colors propagate upward via observer callbacks. Lock state is local UI only. Machine/linac/CM-level operations iterate GUI objects and skip locked cavities instead of calling backend aggregate methods.

**Tech Stack:** PyDM/PyQt5, EPICS PVs via `PyDMChannel`, `PyDMLabel`, `PyDMLineEdit`, `PyDMAnalogIndicator`, `PyDMEDMDisplayButton`. All new UI code stays in `applications/auto_setup/frontend/` and `setup_gui.py`. Backend unchanged.

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `frontend/style.py` | Color constants, `step_label_for_progress()`, `card_stylesheet()`, `chip_stylesheet()`, `dot_stylesheet()`, `status_icon()`, `status_text_color()` |
| Create | `frontend/widgets.py` | `FlowLayout(QLayout)` — wrapping flex-row layout |
| Rewrite | `frontend/gui_cavity.py` | `GUICavity` — assembles `frame: QFrame`, editable ACON, step label, lock toggle, PyDMChannel status/progress subscriptions |
| Rewrite | `frontend/gui_cryomodule.py` | `GUICryomodule` — `tile` (8 dots) + `detail_panel` (8 cavity cards), lock cascade, skip-locked ops |
| Rewrite | `frontend/gui_linac.py` | `GUILinac` — `tile` (CM chips in FlowLayout) + `detail_panel` (CM tiles in FlowLayout), confirmation dialogs, lock cascade |
| Rewrite | `setup_gui.py` | `SetupGUI` — sticky top bar, scroll content, 5 linac tiles, machine-level ops iterate GUI cavities |
| Update | `tests/applications/auto_setup/test_setup_gui.py` | Remove tab-widget tests, add lock + skip-locked + L4B tests |


---

## Task 1: style.py — Color constants and stylesheet helpers

**Files:**
- Create: `src/sc_linac_physics/applications/auto_setup/frontend/style.py`
- Create: `tests/applications/auto_setup/test_style.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/applications/auto_setup/test_style.py
import pytest
from sc_linac_physics.applications.auto_setup.frontend.style import (
    step_label_for_progress,
    card_stylesheet,
    chip_stylesheet,
    dot_stylesheet,
    status_icon,
    STATUS_RUNNING_BORDER,
    STATUS_ERROR_BORDER,
    STATUS_READY_BORDER,
    STATUS_LOCKED_BORDER,
)
from sc_linac_physics.utils.sc_linac.linac_utils import (
    STATUS_READY_VALUE,
    STATUS_RUNNING_VALUE,
    STATUS_ERROR_VALUE,
)


def test_step_label_boundaries():
    assert step_label_for_progress(0) == "SSA Cal · 0%"
    assert step_label_for_progress(25) == "SSA Cal · 25%"
    assert step_label_for_progress(26) == "Auto Tune · 26%"
    assert step_label_for_progress(50) == "Auto Tune · 50%"
    assert step_label_for_progress(51) == "Cavity Char · 51%"
    assert step_label_for_progress(70) == "Cavity Char · 70%"
    assert step_label_for_progress(71) == "RF Ramp · 71%"
    assert step_label_for_progress(100) == "RF Ramp · 100%"


def test_card_stylesheet_running():
    ss = card_stylesheet(STATUS_RUNNING_VALUE)
    assert STATUS_RUNNING_BORDER in ss


def test_card_stylesheet_error():
    ss = card_stylesheet(STATUS_ERROR_VALUE)
    assert STATUS_ERROR_BORDER in ss


def test_card_stylesheet_ready():
    ss = card_stylesheet(STATUS_READY_VALUE)
    assert STATUS_READY_BORDER in ss


def test_card_stylesheet_locked_overrides_status():
    ss = card_stylesheet(STATUS_READY_VALUE, locked=True)
    assert STATUS_LOCKED_BORDER in ss
    assert STATUS_READY_BORDER not in ss


def test_status_icon_values():
    assert status_icon(STATUS_RUNNING_VALUE) == "⟳"
    assert status_icon(STATUS_ERROR_VALUE) == "✗"
    assert status_icon(STATUS_READY_VALUE) == "●"
    assert status_icon(99) == "—"


def test_chip_stylesheet_ready():
    ss = chip_stylesheet(STATUS_READY_VALUE)
    assert STATUS_READY_BORDER in ss


def test_dot_stylesheet_locked():
    ss = dot_stylesheet(STATUS_READY_VALUE, locked=True)
    assert STATUS_LOCKED_BORDER in ss
```

- [ ] **Step 2: Run to verify failure**

```
pytest tests/applications/auto_setup/test_style.py -v
```
Expected: `ModuleNotFoundError` — `style.py` doesn't exist yet.

- [ ] **Step 3: Write the implementation**

```python
# src/sc_linac_physics/applications/auto_setup/frontend/style.py
from sc_linac_physics.utils.sc_linac.linac_utils import (
    STATUS_READY_VALUE,
    STATUS_RUNNING_VALUE,
    STATUS_ERROR_VALUE,
)

PAGE_BG = "#0f1825"
CARD_BG = "#182030"
CARD_BORDER = "#2a3a55"
CARD_TEXT = "#a0b0c8"
MUTED_TEXT = "#8090a8"
NOTE_TEXT = "#506080"
ACCENT_BORDER = "#6688cc"
ACCENT_TEXT = "#a8c8f0"

STATUS_READY_BG = "#182a20"
STATUS_READY_BORDER = "#2a5535"
STATUS_READY_TEXT = "#80c8a0"

STATUS_RUNNING_BG = "#2a2015"
STATUS_RUNNING_BORDER = "#5a4520"
STATUS_RUNNING_TEXT = "#e0b070"

STATUS_ERROR_BG = "#2a1520"
STATUS_ERROR_BORDER = "#5a2840"
STATUS_ERROR_TEXT = "#e08090"

STATUS_LOCKED_BG = "#1a1a28"
STATUS_LOCKED_BORDER = "#303050"
STATUS_LOCKED_TEXT = "#7080a0"

_STATUS_TOKENS = {
    STATUS_READY_VALUE: (STATUS_READY_BG, STATUS_READY_BORDER, STATUS_READY_TEXT),
    STATUS_RUNNING_VALUE: (STATUS_RUNNING_BG, STATUS_RUNNING_BORDER, STATUS_RUNNING_TEXT),
    STATUS_ERROR_VALUE: (STATUS_ERROR_BG, STATUS_ERROR_BORDER, STATUS_ERROR_TEXT),
}
_LOCKED_TOKENS = (STATUS_LOCKED_BG, STATUS_LOCKED_BORDER, STATUS_LOCKED_TEXT)
_DEFAULT_TOKENS = (CARD_BG, CARD_BORDER, CARD_TEXT)


def _tokens(status: int, locked: bool):
    if locked:
        return _LOCKED_TOKENS
    return _STATUS_TOKENS.get(status, _DEFAULT_TOKENS)


def step_label_for_progress(progress: int) -> str:
    if progress <= 25:
        return f"SSA Cal · {progress}%"
    elif progress <= 50:
        return f"Auto Tune · {progress}%"
    elif progress <= 70:
        return f"Cavity Char · {progress}%"
    return f"RF Ramp · {progress}%"


def status_icon(status: int) -> str:
    return {
        STATUS_RUNNING_VALUE: "⟳",
        STATUS_ERROR_VALUE: "✗",
        STATUS_READY_VALUE: "●",
    }.get(status, "—")


def status_text_color(status: int, locked: bool = False) -> str:
    return _tokens(status, locked)[2]


def card_stylesheet(status: int, locked: bool = False) -> str:
    bg, border, _ = _tokens(status, locked)
    return (
        f"QFrame {{ background-color: {bg}; border: 2px solid {border}; "
        f"border-radius: 6px; }}"
    )


def chip_stylesheet(status: int, locked: bool = False) -> str:
    bg, border, color = _tokens(status, locked)
    return (
        f"background-color: {bg}; border: 1px solid {border}; "
        f"color: {color}; border-radius: 4px; padding: 2px 6px; font-weight: 600;"
    )


def dot_stylesheet(status: int, locked: bool = False) -> str:
    _, border, _ = _tokens(status, locked)
    return (
        f"background-color: {border}; border-radius: 5px; "
        f"min-width: 10px; max-width: 10px; min-height: 10px; max-height: 10px;"
    )
```

- [ ] **Step 4: Run to verify tests pass**

```
pytest tests/applications/auto_setup/test_style.py -v
```
Expected: all pass.

- [ ] **Step 5: Commit**

```
git add src/sc_linac_physics/applications/auto_setup/frontend/style.py \
        tests/applications/auto_setup/test_style.py
git commit -m "feat: add style constants and helpers for auto setup UI redesign"
```


---

## Task 2: widgets.py — FlowLayout

**Files:**
- Create: `src/sc_linac_physics/applications/auto_setup/frontend/widgets.py`
- Create: `tests/applications/auto_setup/test_widgets.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/applications/auto_setup/test_widgets.py
from PyQt5.QtWidgets import QWidget, QPushButton
from sc_linac_physics.applications.auto_setup.frontend.widgets import FlowLayout


def test_flow_layout_count(qtbot):
    container = QWidget()
    layout = FlowLayout(container)
    layout.addWidget(QPushButton("x"))
    assert layout.count() == 1


def test_flow_layout_item_at(qtbot):
    container = QWidget()
    layout = FlowLayout(container)
    layout.addWidget(QPushButton("x"))
    assert layout.itemAt(0) is not None
    assert layout.itemAt(1) is None


def test_flow_layout_take_at(qtbot):
    container = QWidget()
    layout = FlowLayout(container)
    layout.addWidget(QPushButton("x"))
    item = layout.takeAt(0)
    assert item is not None
    assert layout.count() == 0


def test_flow_layout_has_height_for_width(qtbot):
    layout = FlowLayout()
    assert layout.hasHeightForWidth() is True


def test_flow_layout_height_non_negative(qtbot):
    container = QWidget()
    layout = FlowLayout(container)
    btn = QPushButton("chip")
    btn.setFixedSize(60, 24)
    layout.addWidget(btn)
    assert layout.heightForWidth(400) >= 0
```

- [ ] **Step 2: Run to verify failure**

```
pytest tests/applications/auto_setup/test_widgets.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation**

```python
# src/sc_linac_physics/applications/auto_setup/frontend/widgets.py
from PyQt5.QtCore import Qt, QRect, QPoint, QSize
from PyQt5.QtWidgets import QLayout


class FlowLayout(QLayout):
    """Wrapping row layout — items flow left-to-right, wrap to next row."""

    def __init__(self, parent=None, h_spacing: int = 6, v_spacing: int = 6):
        super().__init__(parent)
        self._h_spacing = h_spacing
        self._v_spacing = v_spacing
        self._items = []

    def addItem(self, item):
        self._items.append(item)

    def horizontalSpacing(self) -> int:
        return self._h_spacing

    def verticalSpacing(self) -> int:
        return self._v_spacing

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect: QRect):
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        size += QSize(m.left() + m.right(), m.top() + m.bottom())
        return size

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        left, top, right, bottom = self.getContentsMargins()
        r = rect.adjusted(left, top, -right, -bottom)
        x, y, line_h = r.x(), r.y(), 0
        for item in self._items:
            w = item.sizeHint().width()
            h = item.sizeHint().height()
            next_x = x + w + self._h_spacing
            if next_x - self._h_spacing > r.right() and line_h > 0:
                x = r.x()
                y += line_h + self._v_spacing
                next_x = x + w + self._h_spacing
                line_h = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))
            x = next_x
            line_h = max(line_h, h)
        return y + line_h - rect.y() + bottom
```

- [ ] **Step 4: Run to verify tests pass**

```
pytest tests/applications/auto_setup/test_widgets.py -v
```
Expected: all pass.

- [ ] **Step 5: Commit**

```
git add src/sc_linac_physics/applications/auto_setup/frontend/widgets.py \
        tests/applications/auto_setup/test_widgets.py
git commit -m "feat: add FlowLayout widget for auto setup UI"
```


---

## Task 3: gui_cavity.py — Rewrite GUICavity

**Files:**
- Rewrite: `src/sc_linac_physics/applications/auto_setup/frontend/gui_cavity.py`
- Create: `tests/applications/auto_setup/test_gui_cavity.py`

GUICavity is now a dataclass that builds and owns a `QFrame`. It subscribes to STATUS and PROG PVs via `PyDMChannel` to update the card border and step label. A callback (`on_status_changed`) notifies the parent CM when status changes.

- [ ] **Step 1: Write the failing test**

```python
# tests/applications/auto_setup/test_gui_cavity.py
from unittest.mock import patch, MagicMock

import pytest
from PyQt5.QtWidgets import QFrame
from pydm.widgets.line_edit import PyDMLineEdit

from sc_linac_physics.applications.auto_setup.frontend.gui_cavity import GUICavity
from sc_linac_physics.applications.auto_setup.frontend.utils import Settings
from sc_linac_physics.utils.sc_linac.linac_utils import (
    STATUS_READY_VALUE,
    STATUS_RUNNING_VALUE,
)


@pytest.fixture(autouse=True)
def prevent_channel_connections():
    with (
        patch("pydm.widgets.channel.PyDMChannel.connect"),
        patch("pydm.widgets.channel.PyDMChannel.disconnect"),
        patch("pydm.data_plugins.plugin_for_address", return_value=MagicMock()),
    ):
        yield


@pytest.fixture
def gui_cavity(qtbot):
    mock_cavity = MagicMock()
    mock_cavity.status_pv = "fake://STATUS"
    mock_cavity.progress_pv = "fake://PROG"
    mock_cavity.status_msg_pv = "fake://MSG"
    mock_cavity.note_pv = "fake://NOTE"
    mock_cavity.edm_macro_string = "CM=01,CAVNO=1"
    mock_cavity.script_is_running = False
    mock_cavity.is_online = True

    machine = MagicMock()
    machine.cryomodules = {"01": MagicMock(cavities={1: mock_cavity})}

    mock_settings = MagicMock(spec=Settings)
    mock_settings.ssa_cal_checkbox.isChecked.return_value = True
    mock_settings.auto_tune_checkbox.isChecked.return_value = True
    mock_settings.cav_char_checkbox.isChecked.return_value = True
    mock_settings.rf_ramp_checkbox.isChecked.return_value = True

    with patch(
        "sc_linac_physics.applications.auto_setup.frontend.gui_cavity.SETUP_MACHINE",
        machine,
    ):
        cav = GUICavity(
            number=1,
            prefix="ACCL:L0B:0110:",
            cm="01",
            settings=mock_settings,
        )
        qtbot.addWidget(cav.frame)
        yield cav


def test_frame_is_qframe(gui_cavity):
    assert isinstance(gui_cavity.frame, QFrame)


def test_acon_edit_is_line_edit(gui_cavity):
    assert isinstance(gui_cavity.acon_edit, PyDMLineEdit)


def test_initial_state_not_locked(gui_cavity):
    assert gui_cavity.locked is False


def test_setup_button_enabled_when_ready(gui_cavity):
    gui_cavity._handle_status_value(STATUS_READY_VALUE)
    assert gui_cavity.setup_button.isEnabled()


def test_setup_button_disabled_when_running(gui_cavity):
    gui_cavity._handle_status_value(STATUS_RUNNING_VALUE)
    assert not gui_cavity.setup_button.isEnabled()


def test_lock_disables_setup_and_shutdown(gui_cavity):
    gui_cavity.lock()
    assert gui_cavity.locked is True
    assert not gui_cavity.setup_button.isEnabled()
    assert not gui_cavity.shutdown_button.isEnabled()


def test_lock_keeps_abort_enabled(gui_cavity):
    gui_cavity.lock()
    assert gui_cavity.abort_button.isEnabled()


def test_unlock_no_confirm_restores_state(gui_cavity):
    gui_cavity.lock()
    gui_cavity.unlock_no_confirm()
    assert gui_cavity.locked is False
    assert gui_cavity.setup_button.isEnabled()


def test_step_label_updates_on_progress(gui_cavity):
    gui_cavity._handle_progress_value(30)
    assert "Auto Tune" in gui_cavity._step_label.text()
    gui_cavity._handle_progress_value(75)
    assert "RF Ramp" in gui_cavity._step_label.text()


def test_on_status_changed_callback_fires(gui_cavity):
    received = []
    gui_cavity.on_status_changed = lambda num, status: received.append((num, status))
    gui_cavity._handle_status_value(STATUS_RUNNING_VALUE)
    assert received == [(1, STATUS_RUNNING_VALUE)]


def test_trigger_setup_skipped_when_locked(gui_cavity):
    gui_cavity.lock()
    gui_cavity.trigger_setup()
    gui_cavity.cavity.trigger_start.assert_not_called()


def test_trigger_setup_applies_settings(gui_cavity):
    gui_cavity.trigger_setup()
    gui_cavity.cavity.trigger_start.assert_called_once()
    assert gui_cavity.cavity.ssa_cal_requested is True


def test_trigger_shutdown_skipped_when_locked(gui_cavity):
    gui_cavity.lock()
    gui_cavity.trigger_shutdown()
    gui_cavity.cavity.trigger_shutdown.assert_not_called()


def test_request_abort_always_works(gui_cavity):
    gui_cavity.lock()
    gui_cavity.request_abort()
    gui_cavity.cavity.trigger_abort.assert_called_once()
```

- [ ] **Step 2: Run to verify failure**

```
pytest tests/applications/auto_setup/test_gui_cavity.py -v
```
Expected: `ImportError` or `AttributeError`.

- [ ] **Step 3: Write the implementation**

```python
# src/sc_linac_physics/applications/auto_setup/frontend/gui_cavity.py
import dataclasses
from typing import Optional, Callable

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QPushButton, QFrame, QVBoxLayout, QHBoxLayout,
    QLabel, QSizePolicy, QMessageBox,
)
from edmbutton import PyDMEDMDisplayButton
from pydm.widgets import PyDMLabel, analog_indicator
from pydm.widgets.channel import PyDMChannel
from pydm.widgets.display_format import DisplayFormat
from pydm.widgets.line_edit import PyDMLineEdit

from sc_linac_physics.applications.auto_setup.backend.setup_cavity import SetupCavity
from sc_linac_physics.applications.auto_setup.backend.setup_machine import SETUP_MACHINE
from sc_linac_physics.applications.auto_setup.frontend.style import (
    CARD_TEXT, MUTED_TEXT, NOTE_TEXT,
    card_stylesheet, status_icon, status_text_color, step_label_for_progress,
)
from sc_linac_physics.applications.auto_setup.frontend.utils import Settings
from sc_linac_physics.utils.sc_linac.linac_utils import STATUS_RUNNING_VALUE


@dataclasses.dataclass
class GUICavity:
    number: int
    prefix: str
    cm: str
    settings: Settings
    on_status_changed: Optional[Callable[[int, int], None]] = None

    def __post_init__(self):
        self._cavity: Optional[SetupCavity] = None
        self._status: int = 0
        self.locked: bool = False

        self.frame = QFrame()
        self.frame.setFrameShape(QFrame.StyledPanel)
        self.frame.setStyleSheet(card_stylesheet(self._status))
        layout = QVBoxLayout(self.frame)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        # Title row: status icon | cavity name | lock button | expert screen
        title_row = QHBoxLayout()
        self._status_icon_label = QLabel(status_icon(self._status))
        self._status_icon_label.setStyleSheet(
            f"color: {status_text_color(self._status)}; font-weight: bold;"
        )
        self._cav_name_label = QLabel(f"CAV {self.number}")
        self._cav_name_label.setStyleSheet(f"color: {CARD_TEXT}; font-weight: bold;")
        self.lock_button = QPushButton("🔒")
        self.lock_button.setFixedSize(24, 24)
        self.lock_button.setCheckable(True)
        self.lock_button.setStyleSheet(
            "QPushButton { border: none; background: transparent; font-size: 12px; }"
        )
        self.lock_button.clicked.connect(self._on_lock_clicked)
        self.expert_screen_button = PyDMEDMDisplayButton()
        self.expert_screen_button.filenames = ["$EDM/llrf/rf_srf_cavity_main.edl"]
        self.expert_screen_button.macros = (
            self.cavity.edm_macro_string + ",SELTAB=0,SELCHAR=3"
        )
        self.expert_screen_button.setFixedSize(24, 24)
        title_row.addWidget(self._status_icon_label)
        title_row.addWidget(self._cav_name_label)
        title_row.addStretch()
        title_row.addWidget(self.lock_button)
        title_row.addWidget(self.expert_screen_button)
        layout.addLayout(title_row)

        # ACON / AACT row
        amp_row = QHBoxLayout()
        amp_row.addWidget(QLabel("ACON"))
        self.acon_edit = PyDMLineEdit(init_channel=self.prefix + "ACON")
        self.acon_edit.precisionFromPV = False
        self.acon_edit.precision = 2
        self.acon_edit.showUnits = True
        self.acon_edit.setFixedWidth(70)
        self.aact_label = PyDMLabel(init_channel=self.prefix + "AACTMEAN")
        self.aact_label.alarmSensitiveBorder = True
        self.aact_label.alarmSensitiveContent = True
        self.aact_label.showUnits = True
        self.aact_label.precisionFromPV = False
        self.aact_label.precision = 2
        amp_row.addWidget(self.acon_edit)
        amp_row.addWidget(QLabel("MV · AACT"))
        amp_row.addWidget(self.aact_label)
        amp_row.addWidget(QLabel("MV"))
        amp_row.addStretch()
        layout.addLayout(amp_row)

        # Progress row
        prog_row = QHBoxLayout()
        self.progress_bar = analog_indicator.PyDMAnalogIndicator(
            init_channel=self.cavity.progress_pv
        )
        self.progress_bar.backgroundSizeRate = 0.2
        self.progress_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.progress_bar.setFixedHeight(12)
        self._step_label = QLabel("SSA Cal · 0%")
        self._step_label.setStyleSheet(f"color: {MUTED_TEXT}; font-style: italic;")
        prog_row.addWidget(self.progress_bar)
        prog_row.addWidget(self._step_label)
        layout.addLayout(prog_row)

        # Status message
        self.status_label = PyDMLabel(init_channel=self.cavity.status_msg_pv)
        self.status_label.displayFormat = DisplayFormat.String
        self.status_label.setAlignment(Qt.AlignLeft)
        self.status_label.setWordWrap(True)
        self.status_label.alarmSensitiveBorder = True
        self.status_label.alarmSensitiveContent = True
        layout.addWidget(self.status_label)

        # Note field
        self.note_label = PyDMLabel(init_channel=self.cavity.note_pv)
        self.note_label.displayFormat = DisplayFormat.String
        self.note_label.setWordWrap(True)
        self.note_label.setStyleSheet(f"color: {NOTE_TEXT}; font-size: 10px;")
        layout.addWidget(self.note_label)

        # Buttons
        btn_row = QHBoxLayout()
        self.setup_button = QPushButton("Set Up")
        self.setup_button.clicked.connect(self.trigger_setup)
        self.shutdown_button = QPushButton("Turn Off")
        self.shutdown_button.clicked.connect(self.trigger_shutdown)
        self.abort_button = QPushButton("Abort")
        self.abort_button.setStyleSheet("color: #e08090;")
        self.abort_button.clicked.connect(self.request_abort)
        btn_row.addWidget(self.setup_button)
        btn_row.addWidget(self.shutdown_button)
        btn_row.addWidget(self.abort_button)
        layout.addLayout(btn_row)

        # PV subscriptions
        self._status_channel = PyDMChannel(
            address=self.cavity.status_pv,
            value_slot=self._handle_status_value,
        )
        self._status_channel.connect()
        self._progress_channel = PyDMChannel(
            address=self.cavity.progress_pv,
            value_slot=self._handle_progress_value,
        )
        self._progress_channel.connect()

    @property
    def cavity(self) -> SetupCavity:
        if not self._cavity:
            self._cavity = SETUP_MACHINE.cryomodules[self.cm].cavities[self.number]
        return self._cavity

    def _handle_status_value(self, value):
        status = int(value)
        self._status = status
        self.frame.setStyleSheet(card_stylesheet(status, self.locked))
        self._status_icon_label.setText(status_icon(status))
        self._status_icon_label.setStyleSheet(
            f"color: {status_text_color(status, self.locked)}; font-weight: bold;"
        )
        self.setup_button.setEnabled(
            not self.locked and status != STATUS_RUNNING_VALUE
        )
        if self.on_status_changed:
            self.on_status_changed(self.number, status)

    def _handle_progress_value(self, value):
        self._step_label.setText(step_label_for_progress(int(value)))

    def _on_lock_clicked(self):
        if self.locked:
            reply = QMessageBox.question(
                self.frame,
                "Unlock Cavity",
                f"Unlock CAV {self.number}? Make sure no one is working on it.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                self._set_locked(False)
            else:
                self.lock_button.setChecked(True)
        else:
            self._set_locked(True)

    def _set_locked(self, locked: bool):
        self.locked = locked
        self.lock_button.setChecked(locked)
        self.frame.setStyleSheet(card_stylesheet(self._status, locked))
        self._status_icon_label.setStyleSheet(
            f"color: {status_text_color(self._status, locked)}; font-weight: bold;"
        )
        self.setup_button.setEnabled(
            not locked and self._status != STATUS_RUNNING_VALUE
        )
        self.shutdown_button.setEnabled(not locked)
        self.acon_edit.setEnabled(not locked)

    def lock(self):
        self._set_locked(True)

    def unlock_no_confirm(self):
        self._set_locked(False)

    def trigger_setup(self):
        if self.locked:
            return
        if self.cavity.script_is_running:
            self.cavity.status_message = f"{self.cavity} script already running"
            return
        if not self.cavity.is_online:
            self.cavity.status_message = f"{self.cavity} not online, skipping"
            return
        self.cavity.ssa_cal_requested = self.settings.ssa_cal_checkbox.isChecked()
        self.cavity.auto_tune_requested = self.settings.auto_tune_checkbox.isChecked()
        self.cavity.cav_char_requested = self.settings.cav_char_checkbox.isChecked()
        self.cavity.rf_ramp_requested = self.settings.rf_ramp_checkbox.isChecked()
        self.cavity.trigger_start()

    def trigger_shutdown(self):
        if self.locked:
            return
        if self.cavity.script_is_running:
            self.cavity.status_message = f"{self.cavity} script already running"
            return
        self.cavity.trigger_shutdown()

    def request_abort(self):
        self.cavity.trigger_abort()
```

- [ ] **Step 4: Run to verify tests pass**

```
pytest tests/applications/auto_setup/test_gui_cavity.py -v
```
Expected: all pass.

- [ ] **Step 5: Commit**

```
git add src/sc_linac_physics/applications/auto_setup/frontend/gui_cavity.py \
        tests/applications/auto_setup/test_gui_cavity.py
git commit -m "feat: rewrite GUICavity with frame, lock, editable ACON, step label"
```


---

## Task 4: gui_cryomodule.py — Rewrite GUICryomodule

**Files:**
- Rewrite: `src/sc_linac_physics/applications/auto_setup/frontend/gui_cryomodule.py`
- Create: `tests/applications/auto_setup/test_gui_cryomodule.py`

GUICryomodule builds a `tile` (8 status dots) and a `detail_panel` (8 cavity cards + CM controls). It tracks each cavity's status in `_cavity_statuses` and updates dots + tile border via the callback. Lock cascade: `lock()` records which cavities were already locked before the cascade so they are preserved when the CM is later unlocked.

- [ ] **Step 1: Write the failing test**

```python
# tests/applications/auto_setup/test_gui_cryomodule.py
from unittest.mock import patch, MagicMock

import pytest
from sc_linac_physics.applications.auto_setup.frontend.gui_cryomodule import GUICryomodule
from sc_linac_physics.applications.auto_setup.frontend.utils import Settings
from sc_linac_physics.utils.sc_linac.linac_utils import (
    STATUS_READY_VALUE,
    STATUS_RUNNING_VALUE,
    STATUS_ERROR_VALUE,
)


def _mock_cavity(n):
    c = MagicMock()
    c.status_pv = f"fake://S{n}"
    c.progress_pv = f"fake://P{n}"
    c.status_msg_pv = f"fake://M{n}"
    c.note_pv = f"fake://N{n}"
    c.edm_macro_string = f"CM=01,CAVNO={n}"
    c.script_is_running = False
    c.is_online = True
    return c


@pytest.fixture(autouse=True)
def prevent_channel_connections():
    with (
        patch("pydm.widgets.channel.PyDMChannel.connect"),
        patch("pydm.widgets.channel.PyDMChannel.disconnect"),
        patch("pydm.data_plugins.plugin_for_address", return_value=MagicMock()),
    ):
        yield


@pytest.fixture
def gui_cm(qtbot):
    mock_settings = MagicMock(spec=Settings)
    for attr in ("ssa_cal_checkbox", "auto_tune_checkbox", "cav_char_checkbox", "rf_ramp_checkbox"):
        getattr(mock_settings, attr).isChecked.return_value = True

    machine = MagicMock()
    machine.cryomodules = {"01": MagicMock(cavities={n: _mock_cavity(n) for n in range(1, 9)})}

    with patch(
        "sc_linac_physics.applications.auto_setup.frontend.gui_cavity.SETUP_MACHINE",
        machine,
    ):
        gui = GUICryomodule(linac_idx=0, name="01", settings=mock_settings)
        qtbot.addWidget(gui.tile)
        qtbot.addWidget(gui.detail_panel)
        yield gui


def test_tile_and_detail_panel_built(gui_cm):
    assert gui_cm.tile is not None
    assert gui_cm.detail_panel is not None


def test_eight_cavity_cards_built(gui_cm):
    assert len(gui_cm.gui_cavities) == 8


def test_eight_dots_built(gui_cm):
    assert len(gui_cm._dots) == 8


def test_detail_panel_hidden_initially(gui_cm):
    assert gui_cm.detail_panel.isHidden()


def test_on_cavity_status_changed_updates_dot(gui_cm):
    from sc_linac_physics.applications.auto_setup.frontend.style import STATUS_ERROR_BORDER
    gui_cm._on_cavity_status_changed(1, STATUS_ERROR_VALUE)
    assert STATUS_ERROR_BORDER in gui_cm._dots[1].styleSheet()


def test_on_status_changed_callback_fires(gui_cm):
    received = []
    gui_cm.on_status_changed = lambda name, status: received.append((name, status))
    gui_cm._on_cavity_status_changed(1, STATUS_RUNNING_VALUE)
    assert received == [("01", STATUS_RUNNING_VALUE)]


def test_lock_cascades_to_all_cavities(gui_cm):
    gui_cm.lock()
    assert gui_cm.is_locked
    for gui_cav in gui_cm.gui_cavities.values():
        assert gui_cav.locked


def test_unlock_no_confirm_releases_cascade_locked(gui_cm):
    gui_cm.lock()
    gui_cm.unlock_no_confirm()
    assert not gui_cm.is_locked
    for gui_cav in gui_cm.gui_cavities.values():
        assert not gui_cav.locked


def test_unlock_preserves_pre_locked_cavities(gui_cm):
    gui_cm.gui_cavities[3].lock()
    gui_cm.lock()
    gui_cm.unlock_no_confirm()
    assert gui_cm.gui_cavities[3].locked   # was locked before cascade
    assert not gui_cm.gui_cavities[1].locked  # was not locked before cascade


def test_trigger_setup_all_skips_locked(gui_cm):
    gui_cm.gui_cavities[1].lock()
    gui_cm.trigger_setup_all()
    gui_cm.gui_cavities[1].cavity.trigger_start.assert_not_called()
    gui_cm.gui_cavities[2].cavity.trigger_start.assert_called_once()


def test_trigger_abort_all_ignores_lock(gui_cm):
    gui_cm.gui_cavities[1].lock()
    gui_cm.trigger_abort_all()
    gui_cm.gui_cavities[1].cavity.trigger_abort.assert_called_once()
```

- [ ] **Step 2: Run to verify failure**

```
pytest tests/applications/auto_setup/test_gui_cryomodule.py -v
```

- [ ] **Step 3: Write the implementation**

```python
# src/sc_linac_physics/applications/auto_setup/frontend/gui_cryomodule.py
import dataclasses
from typing import Optional, Callable, Dict

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QPushButton, QFrame, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QMessageBox, QWidget,
)

from sc_linac_physics.applications.auto_setup.backend.setup_cryomodule import SetupCryomodule
from sc_linac_physics.applications.auto_setup.backend.setup_machine import SETUP_MACHINE
from sc_linac_physics.applications.auto_setup.frontend.gui_cavity import GUICavity
from sc_linac_physics.applications.auto_setup.frontend.style import (
    CARD_BG, CARD_TEXT, ACCENT_BORDER, card_stylesheet, dot_stylesheet,
)
from sc_linac_physics.applications.auto_setup.frontend.utils import Settings
from sc_linac_physics.utils.sc_linac.linac_utils import (
    STATUS_READY_VALUE,
    STATUS_RUNNING_VALUE,
    STATUS_ERROR_VALUE,
)


@dataclasses.dataclass
class GUICryomodule:
    linac_idx: int
    name: str
    settings: Settings
    on_status_changed: Optional[Callable[[str, int], None]] = None

    def __post_init__(self):
        self._cryomodule: Optional[SetupCryomodule] = None
        self.is_locked: bool = False
        self._pre_cascade_locked: set = set()
        self._cavity_statuses: Dict[int, int] = {
            n: STATUS_READY_VALUE for n in range(1, 9)
        }

        self.gui_cavities: Dict[int, GUICavity] = {}
        for cav_num in range(1, 9):
            gui_cav = GUICavity(
                number=cav_num,
                prefix=f"ACCL:L{self.linac_idx}B:{self.name}{cav_num}0:",
                cm=self.name,
                settings=self.settings,
                on_status_changed=self._on_cavity_status_changed,
            )
            self.gui_cavities[cav_num] = gui_cav

        self.tile = self._build_tile()
        self.detail_panel = self._build_detail_panel()
        self.detail_panel.hide()

    def _build_tile(self) -> QFrame:
        tile = QFrame()
        tile.setFrameShape(QFrame.StyledPanel)
        tile.setStyleSheet(card_stylesheet(STATUS_READY_VALUE))
        tile.setCursor(Qt.PointingHandCursor)
        layout = QVBoxLayout(tile)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(3)
        name_label = QLabel(f"CM{self.name}")
        name_label.setStyleSheet(
            f"color: {CARD_TEXT}; font-weight: bold; font-size: 11px;"
        )
        layout.addWidget(name_label)
        dot_container = QWidget()
        dot_grid = QGridLayout(dot_container)
        dot_grid.setContentsMargins(0, 0, 0, 0)
        dot_grid.setSpacing(2)
        self._dots: Dict[int, QLabel] = {}
        for i, cav_num in enumerate(range(1, 9)):
            row, col = i // 4, i % 4
            dot = QLabel()
            dot.setFixedSize(10, 10)
            dot.setStyleSheet(dot_stylesheet(STATUS_READY_VALUE))
            self._dots[cav_num] = dot
            dot_grid.addWidget(dot, row, col)
        layout.addWidget(dot_container)
        return tile

    def _build_detail_panel(self) -> QFrame:
        panel = QFrame()
        panel.setStyleSheet(
            f"QFrame {{ background: {CARD_BG}; border: 1px solid {ACCENT_BORDER}; "
            f"border-radius: 6px; }}"
        )
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 8, 10, 8)
        ctrl_row = QHBoxLayout()
        cm_label = QLabel(f"CM{self.name}")
        cm_label.setStyleSheet(f"color: {CARD_TEXT}; font-weight: bold;")
        ctrl_row.addWidget(cm_label)
        self.setup_all_button = QPushButton("Set Up All")
        self.setup_all_button.clicked.connect(self.trigger_setup_all)
        self.shutdown_all_button = QPushButton("Shut Down All")
        self.shutdown_all_button.clicked.connect(self.trigger_shutdown_all)
        self.abort_all_button = QPushButton("Abort All")
        self.abort_all_button.setStyleSheet("color: #e08090;")
        self.abort_all_button.clicked.connect(self.trigger_abort_all)
        self.lock_cm_button = QPushButton("🔒 Lock CM")
        self.lock_cm_button.setCheckable(True)
        self.lock_cm_button.clicked.connect(self._on_lock_cm_clicked)
        ctrl_row.addWidget(self.setup_all_button)
        ctrl_row.addWidget(self.shutdown_all_button)
        ctrl_row.addWidget(self.abort_all_button)
        ctrl_row.addWidget(self.lock_cm_button)
        ctrl_row.addStretch()
        layout.addLayout(ctrl_row)
        grid_widget = QWidget()
        cav_grid = QGridLayout(grid_widget)
        cav_grid.setContentsMargins(0, 0, 0, 0)
        cav_grid.setSpacing(6)
        for cav_num in range(1, 9):
            row, col = (cav_num - 1) // 4, (cav_num - 1) % 4
            cav_grid.addWidget(self.gui_cavities[cav_num].frame, row, col)
        layout.addWidget(grid_widget)
        return panel

    def _aggregate_status(self) -> int:
        statuses = list(self._cavity_statuses.values())
        if STATUS_ERROR_VALUE in statuses:
            return STATUS_ERROR_VALUE
        if STATUS_RUNNING_VALUE in statuses:
            return STATUS_RUNNING_VALUE
        return STATUS_READY_VALUE

    def _on_cavity_status_changed(self, cav_num: int, status: int):
        self._cavity_statuses[cav_num] = status
        self._dots[cav_num].setStyleSheet(
            dot_stylesheet(status, self.gui_cavities[cav_num].locked)
        )
        agg = self._aggregate_status()
        self.tile.setStyleSheet(card_stylesheet(agg, self.is_locked))
        if self.on_status_changed:
            self.on_status_changed(self.name, agg)

    def _on_lock_cm_clicked(self):
        if self.is_locked:
            reply = QMessageBox.question(
                self.tile,
                "Unlock CM",
                f"Unlock CM{self.name}? Make sure no one is working on it.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                self._do_unlock()
            else:
                self.lock_cm_button.setChecked(True)
        else:
            self._do_lock()

    def _do_lock(self):
        self._pre_cascade_locked = {n for n, g in self.gui_cavities.items() if g.locked}
        self.is_locked = True
        self.lock_cm_button.setChecked(True)
        for gui_cav in self.gui_cavities.values():
            gui_cav.lock()
        self.tile.setStyleSheet(card_stylesheet(self._aggregate_status(), True))

    def _do_unlock(self):
        self.is_locked = False
        self.lock_cm_button.setChecked(False)
        for n, gui_cav in self.gui_cavities.items():
            if n not in self._pre_cascade_locked:
                gui_cav.unlock_no_confirm()
        self.tile.setStyleSheet(card_stylesheet(self._aggregate_status(), False))

    def lock(self):
        self._do_lock()

    def unlock_no_confirm(self):
        self._do_unlock()

    def trigger_setup_all(self):
        for gui_cav in self.gui_cavities.values():
            if not gui_cav.locked:
                gui_cav.trigger_setup()

    def trigger_shutdown_all(self):
        for gui_cav in self.gui_cavities.values():
            if not gui_cav.locked:
                gui_cav.trigger_shutdown()

    def trigger_abort_all(self):
        for gui_cav in self.gui_cavities.values():
            gui_cav.request_abort()

    def capture_acon(self):
        for gui_cav in self.gui_cavities.values():
            gui_cav.cavity.capture_acon()

    @property
    def cryomodule_object(self) -> SetupCryomodule:
        if not self._cryomodule:
            self._cryomodule = SETUP_MACHINE.cryomodules[self.name]
        return self._cryomodule
```

- [ ] **Step 4: Run to verify tests pass**

```
pytest tests/applications/auto_setup/test_gui_cryomodule.py -v
```

- [ ] **Step 5: Commit**

```
git add src/sc_linac_physics/applications/auto_setup/frontend/gui_cryomodule.py \
        tests/applications/auto_setup/test_gui_cryomodule.py
git commit -m "feat: rewrite GUICryomodule with tile, dots, lock cascade"
```


---

## Task 5: gui_linac.py — Rewrite GUILinac

**Files:**
- Rewrite: `src/sc_linac_physics/applications/auto_setup/frontend/gui_linac.py`
- Create: `tests/applications/auto_setup/test_gui_linac.py`

GUILinac builds a `tile` with CM name chips in a `FlowLayout`, and a `detail_panel` with CM tiles + a linac control bar. Clicking a CM tile toggles that CM's `detail_panel`; other CM detail panels close first. Broad operations create a fresh confirmation popup each time (patched in tests via `make_sanity_check_popup`).

- [ ] **Step 1: Write the failing test**

```python
# tests/applications/auto_setup/test_gui_linac.py
from unittest.mock import patch, MagicMock

import pytest
from PyQt5.QtWidgets import QMessageBox

from sc_linac_physics.applications.auto_setup.frontend.gui_linac import GUILinac
from sc_linac_physics.applications.auto_setup.frontend.utils import Settings
from sc_linac_physics.utils.sc_linac.linac_utils import STATUS_RUNNING_VALUE


def _mock_cavity(n):
    c = MagicMock()
    c.status_pv = f"fake://S{n}"
    c.progress_pv = f"fake://P{n}"
    c.status_msg_pv = f"fake://M{n}"
    c.note_pv = f"fake://N{n}"
    c.edm_macro_string = f"CM=04,CAVNO={n}"
    c.script_is_running = False
    c.is_online = True
    return c


@pytest.fixture(autouse=True)
def prevent_channel_connections():
    with (
        patch("pydm.widgets.channel.PyDMChannel.connect"),
        patch("pydm.widgets.channel.PyDMChannel.disconnect"),
        patch("pydm.data_plugins.plugin_for_address", return_value=MagicMock()),
    ):
        yield


@pytest.fixture
def gui_linac(qtbot):
    mock_settings = MagicMock(spec=Settings)
    for attr in ("ssa_cal_checkbox", "auto_tune_checkbox", "cav_char_checkbox", "rf_ramp_checkbox"):
        getattr(mock_settings, attr).isChecked.return_value = True

    cm_names = ["04", "05"]
    machine = MagicMock()
    for cm_name in cm_names:
        machine.cryomodules[cm_name] = MagicMock(
            cavities={n: _mock_cavity(n) for n in range(1, 9)}
        )

    with patch(
        "sc_linac_physics.applications.auto_setup.frontend.gui_cavity.SETUP_MACHINE",
        machine,
    ):
        linac = GUILinac(
            name="L2B", idx=2, cryomodule_names=cm_names, settings=mock_settings
        )
        qtbot.addWidget(linac.tile)
        qtbot.addWidget(linac.detail_panel)
        yield linac


def test_tile_and_detail_panel_built(gui_linac):
    assert gui_linac.tile is not None
    assert gui_linac.detail_panel is not None


def test_cm_chips_created(gui_linac):
    assert set(gui_linac._cm_chips.keys()) == {"04", "05"}


def test_gui_cryomodules_created(gui_linac):
    assert set(gui_linac.gui_cryomodules.keys()) == {"04", "05"}


def test_detail_panel_hidden_initially(gui_linac):
    assert gui_linac.detail_panel.isHidden()


def test_on_cm_status_changed_updates_chip(gui_linac):
    from sc_linac_physics.applications.auto_setup.frontend.style import STATUS_RUNNING_BORDER
    gui_linac._on_cm_status_changed("04", STATUS_RUNNING_VALUE)
    assert STATUS_RUNNING_BORDER in gui_linac._cm_chips["04"].styleSheet()


def test_lock_linac_cascades_to_cms(gui_linac):
    gui_linac._lock_linac()
    assert gui_linac.is_locked
    for gui_cm in gui_linac.gui_cryomodules.values():
        assert gui_cm.is_locked


def test_unlock_linac_releases_cascade(gui_linac):
    gui_linac._lock_linac()
    gui_linac._unlock_linac()
    assert not gui_linac.is_locked
    for gui_cm in gui_linac.gui_cryomodules.values():
        assert not gui_cm.is_locked


def test_trigger_setup_confirmed(gui_linac):
    with patch(
        "sc_linac_physics.applications.auto_setup.frontend.gui_linac.make_sanity_check_popup"
    ) as mock_popup:
        mock_popup.return_value.exec.return_value = QMessageBox.Yes
        gui_linac.trigger_setup()
    for gui_cm in gui_linac.gui_cryomodules.values():
        for gui_cav in gui_cm.gui_cavities.values():
            gui_cav.cavity.trigger_start.assert_called()


def test_trigger_setup_cancelled(gui_linac):
    with patch(
        "sc_linac_physics.applications.auto_setup.frontend.gui_linac.make_sanity_check_popup"
    ) as mock_popup:
        mock_popup.return_value.exec.return_value = QMessageBox.Cancel
        gui_linac.trigger_setup()
    for gui_cm in gui_linac.gui_cryomodules.values():
        for gui_cav in gui_cm.gui_cavities.values():
            gui_cav.cavity.trigger_start.assert_not_called()
```

- [ ] **Step 2: Run to verify failure**

```
pytest tests/applications/auto_setup/test_gui_linac.py -v
```

- [ ] **Step 3: Write the implementation**

```python
# src/sc_linac_physics/applications/auto_setup/frontend/gui_linac.py
import dataclasses
from typing import Optional, Callable, Dict, List

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QPushButton, QFrame, QVBoxLayout, QHBoxLayout,
    QLabel, QMessageBox, QWidget,
)

from sc_linac_physics.applications.auto_setup.backend.setup_linac import SetupLinac
from sc_linac_physics.applications.auto_setup.backend.setup_machine import SETUP_MACHINE
from sc_linac_physics.applications.auto_setup.frontend.gui_cryomodule import GUICryomodule
from sc_linac_physics.applications.auto_setup.frontend.style import (
    CARD_BG, CARD_TEXT, ACCENT_BORDER, ACCENT_TEXT,
    card_stylesheet, chip_stylesheet,
)
from sc_linac_physics.applications.auto_setup.frontend.utils import Settings
from sc_linac_physics.applications.auto_setup.frontend.widgets import FlowLayout
from sc_linac_physics.utils.sc_linac.linac_utils import (
    STATUS_READY_VALUE, STATUS_RUNNING_VALUE, STATUS_ERROR_VALUE,
)
from sc_linac_physics.utils.qt import make_sanity_check_popup


@dataclasses.dataclass
class GUILinac:
    name: str
    idx: int
    cryomodule_names: List[str]
    settings: Settings
    on_tile_clicked: Optional[Callable[["GUILinac"], None]] = None

    def __post_init__(self):
        self._linac_object: Optional[SetupLinac] = None
        self.is_locked: bool = False
        self._pre_cascade_locked: set = set()
        self._cm_statuses: Dict[str, int] = {
            name: STATUS_READY_VALUE for name in self.cryomodule_names
        }

        self.gui_cryomodules: Dict[str, GUICryomodule] = {}
        for cm_name in self.cryomodule_names:
            gui_cm = GUICryomodule(
                linac_idx=self.idx,
                name=cm_name,
                settings=self.settings,
                on_status_changed=self._on_cm_status_changed,
            )
            self.gui_cryomodules[cm_name] = gui_cm

        self.tile = self._build_tile()
        self.detail_panel = self._build_detail_panel()
        self.detail_panel.hide()

    def _build_tile(self) -> QFrame:
        tile = QFrame()
        tile.setFrameShape(QFrame.StyledPanel)
        tile.setStyleSheet(card_stylesheet(STATUS_READY_VALUE))
        tile.setCursor(Qt.PointingHandCursor)
        tile.mousePressEvent = lambda event: self._on_tile_clicked_handler()
        layout = QVBoxLayout(tile)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)
        title = QLabel(self.name)
        title.setStyleSheet(f"color: {ACCENT_TEXT}; font-weight: bold; font-size: 13px;")
        layout.addWidget(title)
        chips_widget = QWidget()
        flow = FlowLayout(chips_widget, h_spacing=4, v_spacing=4)
        self._cm_chips: Dict[str, QLabel] = {}
        for cm_name in self.cryomodule_names:
            chip = QLabel(f"CM{cm_name}")
            chip.setStyleSheet(chip_stylesheet(STATUS_READY_VALUE))
            self._cm_chips[cm_name] = chip
            flow.addWidget(chip)
        layout.addWidget(chips_widget)
        return tile

    def _build_detail_panel(self) -> QFrame:
        panel = QFrame()
        panel.setStyleSheet(
            f"QFrame {{ background: {CARD_BG}; border: 1px solid {ACCENT_BORDER}; "
            f"border-radius: 6px; }}"
        )
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 8, 10, 10)
        ctrl_row = QHBoxLayout()
        linac_label = QLabel(self.name)
        linac_label.setStyleSheet(f"color: {ACCENT_TEXT}; font-weight: bold;")
        ctrl_row.addWidget(linac_label)
        self.setup_button = QPushButton(f"Set Up {self.name}")
        self.setup_button.clicked.connect(self.trigger_setup)
        self.shutdown_button = QPushButton(f"Shut Down {self.name}")
        self.shutdown_button.clicked.connect(self.trigger_shutdown)
        self.abort_button = QPushButton(f"Abort {self.name}")
        self.abort_button.setStyleSheet("color: #e08090;")
        self.abort_button.clicked.connect(self.trigger_abort)
        self.acon_button = QPushButton("Capture all ACON")
        self.acon_button.clicked.connect(self.capture_acon)
        self.lock_linac_button = QPushButton(f"🔒 Lock {self.name}")
        self.lock_linac_button.setCheckable(True)
        self.lock_linac_button.clicked.connect(self._on_lock_linac_clicked)
        ctrl_row.addWidget(self.setup_button)
        ctrl_row.addWidget(self.shutdown_button)
        ctrl_row.addWidget(self.abort_button)
        ctrl_row.addWidget(self.acon_button)
        ctrl_row.addWidget(self.lock_linac_button)
        ctrl_row.addStretch()
        layout.addLayout(ctrl_row)
        cms_widget = QWidget()
        cms_flow = FlowLayout(cms_widget, h_spacing=6, v_spacing=6)
        for cm_name in self.cryomodule_names:
            gui_cm = self.gui_cryomodules[cm_name]
            cm_container = QWidget()
            cm_v = QVBoxLayout(cm_container)
            cm_v.setContentsMargins(0, 0, 0, 0)
            cm_v.setSpacing(0)
            cm_v.addWidget(gui_cm.tile)
            cm_v.addWidget(gui_cm.detail_panel)
            gui_cm.tile.mousePressEvent = (
                lambda event, n=cm_name: self._on_cm_tile_clicked(n)
            )
            cms_flow.addWidget(cm_container)
        layout.addWidget(cms_widget)
        return panel

    def _on_tile_clicked_handler(self):
        if self.on_tile_clicked:
            self.on_tile_clicked(self)

    def _on_cm_tile_clicked(self, cm_name: str):
        for name, gui_cm in self.gui_cryomodules.items():
            if name != cm_name:
                gui_cm.detail_panel.hide()
        clicked = self.gui_cryomodules[cm_name]
        if clicked.detail_panel.isHidden():
            clicked.detail_panel.show()
        else:
            clicked.detail_panel.hide()

    def _on_cm_status_changed(self, cm_name: str, status: int):
        self._cm_statuses[cm_name] = status
        self._cm_chips[cm_name].setStyleSheet(
            chip_stylesheet(status, self.gui_cryomodules[cm_name].is_locked)
        )
        agg = self._aggregate_status()
        self.tile.setStyleSheet(card_stylesheet(agg, self.is_locked))

    def _aggregate_status(self) -> int:
        statuses = list(self._cm_statuses.values())
        if STATUS_ERROR_VALUE in statuses:
            return STATUS_ERROR_VALUE
        if STATUS_RUNNING_VALUE in statuses:
            return STATUS_RUNNING_VALUE
        return STATUS_READY_VALUE

    def _on_lock_linac_clicked(self):
        if self.is_locked:
            reply = QMessageBox.question(
                self.tile,
                "Unlock Linac",
                f"Unlock {self.name}? Make sure no one is working on it.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                self._unlock_linac()
            else:
                self.lock_linac_button.setChecked(True)
        else:
            self._lock_linac()

    def _lock_linac(self):
        self._pre_cascade_locked = {
            name for name, cm in self.gui_cryomodules.items() if cm.is_locked
        }
        self.is_locked = True
        self.lock_linac_button.setChecked(True)
        for gui_cm in self.gui_cryomodules.values():
            gui_cm.lock()

    def _unlock_linac(self):
        self.is_locked = False
        self.lock_linac_button.setChecked(False)
        for name, gui_cm in self.gui_cryomodules.items():
            if name not in self._pre_cascade_locked:
                gui_cm.unlock_no_confirm()

    def trigger_setup(self):
        popup = make_sanity_check_popup(
            f"Set up all unlocked cavities in {self.name}?"
        )
        if popup.exec() == QMessageBox.Yes:
            for gui_cm in self.gui_cryomodules.values():
                gui_cm.trigger_setup_all()

    def trigger_shutdown(self):
        popup = make_sanity_check_popup(
            f"Shut down all unlocked cavities in {self.name}?"
        )
        if popup.exec() == QMessageBox.Yes:
            for gui_cm in self.gui_cryomodules.values():
                gui_cm.trigger_shutdown_all()

    def trigger_abort(self):
        popup = make_sanity_check_popup(
            f"Abort all running setup operations in {self.name}?"
        )
        if popup.exec() == QMessageBox.Yes:
            for gui_cm in self.gui_cryomodules.values():
                gui_cm.trigger_abort_all()

    def capture_acon(self):
        for gui_cm in self.gui_cryomodules.values():
            gui_cm.capture_acon()

    @property
    def linac_object(self) -> SetupLinac:
        if not self._linac_object:
            self._linac_object = SETUP_MACHINE.linacs[self.idx]
        return self._linac_object
```

- [ ] **Step 4: Run to verify tests pass**

```
pytest tests/applications/auto_setup/test_gui_linac.py -v
```

- [ ] **Step 5: Commit**

```
git add src/sc_linac_physics/applications/auto_setup/frontend/gui_linac.py \
        tests/applications/auto_setup/test_gui_linac.py
git commit -m "feat: rewrite GUILinac with tile, CM chips, confirmation dialogs, lock cascade"
```


---

## Task 6: setup_gui.py — Rewrite SetupGUI

**Files:**
- Rewrite: `src/sc_linac_physics/applications/auto_setup/setup_gui.py`
- Update: `tests/applications/auto_setup/test_setup_gui.py`

SetupGUI has a non-scrolling top bar (machine buttons + checkboxes) and a `QScrollArea` below. Five linac tiles sit in a row; clicking one opens its `detail_panel` in a slot below the tiles (one open at a time, toggle on re-click). Machine-level ops iterate all gui_cavities and skip locked ones. `linac_widgets: List[GUILinac]` is kept as an alias to `gui_linacs.values()` for test compatibility.

- [ ] **Step 1: Write the updated test file**

Replace `tests/applications/auto_setup/test_setup_gui.py` with:

```python
# tests/applications/auto_setup/test_setup_gui.py
from unittest.mock import patch, MagicMock

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QMessageBox

from sc_linac_physics.applications.auto_setup.setup_gui import SetupGUI
from sc_linac_physics.utils.sc_linac.linac_utils import LINAC_CM_MAP


def _mock_cavity(n):
    c = MagicMock()
    c.status_pv = f"fake://S{n}"
    c.progress_pv = f"fake://P{n}"
    c.status_msg_pv = f"fake://M{n}"
    c.note_pv = f"fake://N{n}"
    c.edm_macro_string = f"CAVNO={n}"
    c.script_is_running = False
    c.is_online = True
    return c


def _build_machine_mock():
    machine = MagicMock()
    all_cm_names = [cm for linac_cms in LINAC_CM_MAP for cm in linac_cms]
    for cm_name in all_cm_names:
        cm = MagicMock()
        cm.cavities = {n: _mock_cavity(n) for n in range(1, 9)}
        machine.cryomodules[cm_name] = cm
    return machine


@pytest.fixture(autouse=True)
def prevent_channel_connections():
    with (
        patch("pydm.widgets.channel.PyDMChannel.connect"),
        patch("pydm.widgets.channel.PyDMChannel.disconnect"),
        patch("pydm.data_plugins.plugin_for_address", return_value=MagicMock()),
    ):
        yield


@pytest.fixture
def setup_gui():
    machine = _build_machine_mock()
    with patch(
        "sc_linac_physics.applications.auto_setup.frontend.gui_cavity.SETUP_MACHINE",
        machine,
    ):
        gui = SetupGUI()
        gui.machine_setup_popup.exec = MagicMock(return_value=QMessageBox.Yes)
        gui.machine_shutdown_popup.exec = MagicMock(return_value=QMessageBox.Yes)
        gui.machine_abort_popup.exec = MagicMock(return_value=QMessageBox.Yes)
        yield gui


def test_launches(qtbot, setup_gui):
    qtbot.addWidget(setup_gui)
    assert setup_gui.windowTitle() == "SRF Auto Setup"
    assert setup_gui.ssa_cal_checkbox.isChecked()
    assert setup_gui.autotune_checkbox.isChecked()
    assert setup_gui.cav_char_checkbox.isChecked()
    assert setup_gui.rf_ramp_checkbox.isChecked()


def test_five_linac_widgets(qtbot, setup_gui):
    qtbot.addWidget(setup_gui)
    assert len(setup_gui.linac_widgets) == 5
    assert [w.name for w in setup_gui.linac_widgets] == ["L0B", "L1B", "L2B", "L3B", "L4B"]


def test_machine_setup_calls_unlocked_cavities(qtbot, setup_gui):
    qtbot.addWidget(setup_gui)
    first_linac = setup_gui.linac_widgets[0]
    first_cm = next(iter(first_linac.gui_cryomodules.values()))
    locked_cav = first_cm.gui_cavities[1]
    unlocked_cav = first_cm.gui_cavities[2]
    locked_cav.lock()

    setup_gui.trigger_machine_setup()

    locked_cav.cavity.trigger_start.assert_not_called()
    unlocked_cav.cavity.trigger_start.assert_called()


def test_machine_setup_cancelled(qtbot, setup_gui):
    qtbot.addWidget(setup_gui)
    setup_gui.machine_setup_popup.exec = MagicMock(return_value=QMessageBox.Cancel)
    setup_gui.trigger_machine_setup()
    for linac in setup_gui.linac_widgets:
        for gui_cm in linac.gui_cryomodules.values():
            for gui_cav in gui_cm.gui_cavities.values():
                gui_cav.cavity.trigger_start.assert_not_called()


def test_machine_shutdown_skips_locked(qtbot, setup_gui):
    qtbot.addWidget(setup_gui)
    first_cm = next(iter(setup_gui.linac_widgets[0].gui_cryomodules.values()))
    locked_cav = first_cm.gui_cavities[1]
    locked_cav.lock()
    setup_gui.trigger_machine_shutdown()
    locked_cav.cavity.trigger_shutdown.assert_not_called()


def test_machine_abort_ignores_lock(qtbot, setup_gui):
    qtbot.addWidget(setup_gui)
    first_cm = next(iter(setup_gui.linac_widgets[0].gui_cryomodules.values()))
    locked_cav = first_cm.gui_cavities[1]
    locked_cav.lock()
    setup_gui.trigger_machine_abort()
    locked_cav.cavity.trigger_abort.assert_called()


def test_checkbox_state_propagates(qtbot, setup_gui):
    qtbot.addWidget(setup_gui)
    setup_gui.ssa_cal_checkbox.setChecked(False)
    setup_gui.autotune_checkbox.setChecked(False)
    first_cm = next(iter(setup_gui.linac_widgets[0].gui_cryomodules.values()))
    gui_cav = first_cm.gui_cavities[1]
    setup_gui.trigger_machine_setup()
    assert gui_cav.cavity.ssa_cal_requested is False
    assert gui_cav.cavity.auto_tune_requested is False
```

- [ ] **Step 2: Run existing tests to see what breaks**

```
pytest tests/applications/auto_setup/test_setup_gui.py -v
```
Expected: failures in 5-linac count, skip-locked tests, and missing `tabWidget_linac`.

- [ ] **Step 3: Write the implementation**

```python
# src/sc_linac_physics/applications/auto_setup/setup_gui.py
from typing import List, Optional, Dict

from PyQt5.QtWidgets import (
    QHBoxLayout, QVBoxLayout, QWidget, QPushButton,
    QCheckBox, QMessageBox, QFrame, QScrollArea,
)
from pydm import Display

from sc_linac_physics.applications.auto_setup.frontend.gui_linac import GUILinac
from sc_linac_physics.applications.auto_setup.frontend.style import (
    PAGE_BG, CARD_BG, CARD_BORDER,
)
from sc_linac_physics.applications.auto_setup.frontend.utils import Settings
from sc_linac_physics.utils.qt import make_sanity_check_popup
from sc_linac_physics.utils.sc_linac import linac_utils


class SetupGUI(Display):
    def __init__(self, parent=None, args=None):
        super().__init__(parent=parent, args=args)
        self.setWindowTitle("SRF Auto Setup")

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # Sticky top bar
        top_bar = QFrame()
        top_bar.setStyleSheet(
            f"QFrame {{ background: {CARD_BG}; border-bottom: 1px solid {CARD_BORDER}; }}"
        )
        top_bar_layout = QVBoxLayout(top_bar)
        top_bar_layout.setContentsMargins(12, 8, 12, 8)
        top_bar_layout.setSpacing(6)

        machine_btn_row = QHBoxLayout()
        self.machine_setup_button = QPushButton("Set Up Machine")
        self.machine_shutdown_button = QPushButton("Shut Down Machine")
        self.machine_abort_button = QPushButton("Abort Machine")
        self.machine_abort_button.setStyleSheet("color: #e08090;")

        self.machine_setup_popup = make_sanity_check_popup(
            "Set up all unlocked cavities across the entire machine?"
        )
        self.machine_shutdown_popup = make_sanity_check_popup(
            "Shut down all unlocked cavities across the entire machine?"
        )
        self.machine_abort_popup = make_sanity_check_popup(
            "Abort all running setup operations?"
        )

        self.machine_setup_button.clicked.connect(self.trigger_machine_setup)
        self.machine_shutdown_button.clicked.connect(self.trigger_machine_shutdown)
        self.machine_abort_button.clicked.connect(self.trigger_machine_abort)

        machine_btn_row.addWidget(self.machine_setup_button)
        machine_btn_row.addWidget(self.machine_shutdown_button)
        machine_btn_row.addWidget(self.machine_abort_button)
        machine_btn_row.addStretch()
        top_bar_layout.addLayout(machine_btn_row)

        checkbox_row = QHBoxLayout()
        self.ssa_cal_checkbox = QCheckBox("SSA Calibration")
        self.ssa_cal_checkbox.setChecked(True)
        self.autotune_checkbox = QCheckBox("Auto Tune")
        self.autotune_checkbox.setChecked(True)
        self.cav_char_checkbox = QCheckBox("Cavity Characterization")
        self.cav_char_checkbox.setChecked(True)
        self.rf_ramp_checkbox = QCheckBox("RF Ramp")
        self.rf_ramp_checkbox.setChecked(True)
        checkbox_row.addWidget(self.ssa_cal_checkbox)
        checkbox_row.addWidget(self.autotune_checkbox)
        checkbox_row.addWidget(self.cav_char_checkbox)
        checkbox_row.addWidget(self.rf_ramp_checkbox)
        checkbox_row.addStretch()
        top_bar_layout.addLayout(checkbox_row)
        outer_layout.addWidget(top_bar)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"background: {PAGE_BG};")
        scroll_content = QWidget()
        scroll_content.setStyleSheet(f"background: {PAGE_BG};")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(12, 12, 12, 12)
        scroll_layout.setSpacing(12)

        self.settings = Settings(
            ssa_cal_checkbox=self.ssa_cal_checkbox,
            auto_tune_checkbox=self.autotune_checkbox,
            cav_char_checkbox=self.cav_char_checkbox,
            rf_ramp_checkbox=self.rf_ramp_checkbox,
        )

        self.gui_linacs: Dict[str, GUILinac] = {}
        self.linac_widgets: List[GUILinac] = []

        linac_tile_row = QHBoxLayout()
        linac_tile_row.setSpacing(8)
        for name, idx in [("L0B", 0), ("L1B", 1), ("L2B", 2), ("L3B", 3), ("L4B", 4)]:
            gui_linac = GUILinac(
                name=name,
                idx=idx,
                cryomodule_names=linac_utils.LINAC_CM_MAP[idx],
                settings=self.settings,
                on_tile_clicked=self._on_linac_tile_clicked,
            )
            self.gui_linacs[name] = gui_linac
            self.linac_widgets.append(gui_linac)
            linac_tile_row.addWidget(gui_linac.tile)
        linac_tile_row.addStretch()
        scroll_layout.addLayout(linac_tile_row)

        self._active_linac: Optional[GUILinac] = None
        self._detail_container = QWidget()
        self._detail_layout = QVBoxLayout(self._detail_container)
        self._detail_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.addWidget(self._detail_container)
        scroll_layout.addStretch()

        scroll.setWidget(scroll_content)
        outer_layout.addWidget(scroll)

    def _on_linac_tile_clicked(self, gui_linac: GUILinac):
        if self._active_linac is gui_linac:
            gui_linac.detail_panel.hide()
            self._detail_layout.removeWidget(gui_linac.detail_panel)
            self._active_linac = None
        else:
            if self._active_linac:
                self._active_linac.detail_panel.hide()
                self._detail_layout.removeWidget(self._active_linac.detail_panel)
            self._active_linac = gui_linac
            self._detail_layout.addWidget(gui_linac.detail_panel)
            gui_linac.detail_panel.show()

    def _iter_all_gui_cavities(self):
        for gui_linac in self.gui_linacs.values():
            for gui_cm in gui_linac.gui_cryomodules.values():
                yield from gui_cm.gui_cavities.values()

    def trigger_machine_setup(self):
        if self.machine_setup_popup.exec() == QMessageBox.Yes:
            for gui_cav in self._iter_all_gui_cavities():
                if not gui_cav.locked:
                    gui_cav.trigger_setup()

    def trigger_machine_shutdown(self):
        if self.machine_shutdown_popup.exec() == QMessageBox.Yes:
            for gui_cav in self._iter_all_gui_cavities():
                if not gui_cav.locked:
                    gui_cav.trigger_shutdown()

    def trigger_machine_abort(self):
        if self.machine_abort_popup.exec() == QMessageBox.Yes:
            for gui_cav in self._iter_all_gui_cavities():
                gui_cav.request_abort()
```

- [ ] **Step 4: Run tests**

```
pytest tests/applications/auto_setup/test_setup_gui.py -v
```
Expected: all pass.

- [ ] **Step 5: Run full suite**

```
pytest tests/applications/auto_setup/ -v
```
Expected: all pass.

- [ ] **Step 6: Commit**

```
git add src/sc_linac_physics/applications/auto_setup/setup_gui.py \
        tests/applications/auto_setup/test_setup_gui.py
git commit -m "feat: rewrite SetupGUI with tile hierarchy, 5 linacs, skip-locked machine ops"
```

---

## Task 7: Final verification

- [ ] **Step 1: Full test suite with coverage**

```
pytest tests/applications/auto_setup/ -v \
    --cov=sc_linac_physics.applications.auto_setup \
    --cov-report=term-missing
```
Expected: all pass, coverage >= 80%.

- [ ] **Step 2: Lint**

```
flake8 src/sc_linac_physics/applications/auto_setup/ --max-line-length=120
```
Expected: no errors.

- [ ] **Step 3: Format**

```
black src/sc_linac_physics/applications/auto_setup/
```

- [ ] **Step 4: Commit any formatting fixes**

```
git add -p
git commit -m "style: apply black formatting to auto setup UI files"
```

- [ ] **Step 5: Smoke-test the UI**

```
PYDM_DEFAULT_PROTOCOL=fake python -m sc_linac_physics.applications.auto_setup.setup_gui
```
Verify: window opens with dark navy background, 5 linac tiles visible, clicking a tile expands its CM panel, clicking a CM tile shows cavity cards, lock button dims the card and disables Set Up/Turn Off but not Abort, confirmation dialogs appear for machine-level ops.

---

## Implementation Notes

- `make_sanity_check_popup` returns `QMessageBox.Yes | QMessageBox.Cancel` (not `No`). Tests mock `.exec = MagicMock(return_value=QMessageBox.Yes)`. The unlock dialogs use `QMessageBox.question()` which returns `Yes | No` — intentionally different semantics.
- `LINAC_CM_MAP[1]` already includes HL cavities `['02', '03', 'H1', 'H2']` — no extra work needed for L1B/L1BHL merge.
- `linac_widgets: List[GUILinac]` on `SetupGUI` is kept alongside `gui_linacs: Dict` to preserve test compatibility.
- PyDMChannel `value_slot` receives values only when the channel is connected to a live data source. In tests, `PyDMChannel.connect` is patched, so handlers are tested by calling them directly (e.g., `gui_cav._handle_status_value(1)`).
- The `cavity` property on `GUICavity` accesses `SETUP_MACHINE` lazily and is accessed during `__post_init__` (for PV addresses). Patch `SETUP_MACHINE` in `gui_cavity` module, not `setup_gui` module.
