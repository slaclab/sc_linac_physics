# Cavity Characterization Phase UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the CAVITY_CHAR commissioning phase a real display that runs the
characterization, shows the measured loaded Q and scale factor against the
cavity's own Q window, and pushes them to the machine only on an explicit click.

**Architecture:** The established four-layer phase pattern, mirroring SSA_CHAR —
a `CavityCharUI` builder in `phase_builders.py`, a `CavityCharController` that
drives `CavityCharPhase` on a daemon thread, a real `CavityCharDisplay`, and a
registry repoint off the `standard.py` placeholder.

**Tech Stack:** PyQt5, PyDM (`PyDMLabel`, `PyDMSpinbox`), pytest with
`QT_QPA_PLATFORM=offscreen` (set by `tests/conftest.py`), EPICS PVs mocked via
`unittest.mock`.

**Spec:** `docs/superpowers/specs/2026-09-10-cavity-char-ui-design.md`

**Backend:** `CavityCharPhase` in
`src/sc_linac_physics/applications/rf_commissioning/phases/cavity_char.py`,
added by PR #285. This branch is stacked on `feat/cavity-char-phase`.

## Global Constraints

- Black line length 80; flake8 max-line-length 120, max-complexity 10.
- Coverage must stay above 80% (CI enforces).
- `applications/rf_commissioning/` is single-maintainer: favor explicit naming
  and docstrings on phase logic over compact code.
- Threading: daemon `threading.Thread` plus `pyqtSignal`, matching
  `ssa_char_controller`, `piezo_pre_rf_controller` and
  `frequency_tuning_controller`. Do **not** use `Worker(QThread)` — `utils.qt`
  is not imported anywhere in `rf_commissioning`.
- Never write a PV from the Qt main thread.
- Drive level: default `linac_utils.SAFE_PULSED_DRIVE_LEVEL` (10), max
  `CavityCharLimits.max_drive_level` (15.0). Validity is `0 < drive <= 15`.
- Probe Q is omitted from the panel entirely. `_read_probe_q()` returns None by
  design; there is no readback PV and no `PUSH_QPROBE`.
- Abort ends the `_wait_for_completion` poll and writes nothing to the machine.
  Any Abort copy must say that, not "stop the characterization".
- PV writes in this feature: `SEL_ASET` (drive level), `PROBECALSTRT` (start),
  `PUSH_QLOADED.PROC` and `PUSH_CAV_SCALE.PROC` (the push, value 1,
  `wait=False`).

---

## PR 1 — controller, drive level, run/abort, live status

Machine writes: `SEL_ASET`, `PROBECALSTRT`. Target ~350 lines.

### Task 1: CavityCharUI builder — inputs and toolbar

**Files:**
- Modify: `src/sc_linac_physics/applications/rf_commissioning/ui/builders/phase_builders.py` (add `CavityCharUI` after `SSACharUI`)
- Modify: `src/sc_linac_physics/applications/rf_commissioning/ui/builders/__init__.py` (export `CavityCharUI`)
- Test: `tests/applications/rf_commissioning/ui/builders/test_cavity_char_ui.py`

**Interfaces:**
- Consumes: `PhaseUIBase._register`, `PhaseUIBase._connect`,
  `PhaseUIBase._build_main_toolbar`, `PhaseUIBase._build_history`,
  `PhaseUIBase._build_stored_data_section`,
  `PhaseUIBase._get_parent_stored_data_fields`.
- Produces: `CavityCharUI(parent, callbacks).build() -> QHBoxLayout`, and these
  registered widget names: `drive_level_spinbox`, `char_status_label`,
  `elapsed_label`, `local_phase_status`. Callback keys consumed:
  `on_run_automated_test`, `on_pause_test`, `on_abort_test`.

- [ ] **Step 1: Write the failing test**

```python
from PyQt5.QtWidgets import QWidget

from sc_linac_physics.applications.rf_commissioning.ui.builders import (
    CavityCharUI,
)


def test_build_registers_the_documented_widgets(qapp_global):
    parent = QWidget()
    ui = CavityCharUI(parent, callbacks={})
    ui.build()
    for name in (
        "drive_level_spinbox",
        "char_status_label",
        "elapsed_label",
        "local_phase_status",
    ):
        assert name in ui.widgets, name


def test_drive_level_spinbox_defaults_to_safe_pulsed_level(qapp_global):
    parent = QWidget()
    ui = CavityCharUI(parent, callbacks={})
    ui.build()
    spin = ui.widgets["drive_level_spinbox"]
    assert spin.value() == 10
    assert spin.userMaximum == 15.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/applications/rf_commissioning/ui/builders/test_cavity_char_ui.py -v`
Expected: FAIL with `ImportError: cannot import name 'CavityCharUI'`

- [ ] **Step 3: Write minimal implementation**

In `phase_builders.py`, after `SSACharUI`:

```python
class CavityCharUI(PhaseUIBase):
    """Builds the Cavity Characterization display UI.

    The drive level spinbox is the only operator input. It defaults to
    SAFE_PULSED_DRIVE_LEVEL and is capped at CavityCharLimits.max_drive_level;
    the phase re-validates the value before writing SEL_ASET.
    """

    def build(self) -> QHBoxLayout:
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(8)

        left_panel = QVBoxLayout()
        left_panel.setSpacing(6)
        left_panel.addLayout(self._build_main_toolbar())
        left_panel.addWidget(self._build_char_inputs())
        left_panel.addWidget(self._build_history(), stretch=1)

        right_panel = QVBoxLayout()
        right_panel.setSpacing(6)
        right_panel.addWidget(
            self._build_stored_data_section(
                self._get_parent_stored_data_fields()
            )
        )
        right_panel.addStretch()

        main_layout.addLayout(left_panel, 1)
        main_layout.addLayout(right_panel, 1)
        return main_layout

    def _build_char_inputs(self) -> QGroupBox:
        group = QGroupBox("Cavity Characterization")
        layout = QGridLayout()
        layout.setSpacing(6)
        layout.setContentsMargins(8, 8, 8, 8)

        layout.addWidget(QLabel("Drive level (%):"), 0, 0)
        spin = self._register(
            "drive_level_spinbox", QDoubleSpinBox(parent=self.parent)
        )
        spin.setRange(0.01, CavityCharLimits.max_drive_level)
        spin.setSingleStep(1.0)
        spin.setDecimals(2)
        spin.setValue(linac_utils.SAFE_PULSED_DRIVE_LEVEL)
        spin.userMaximum = CavityCharLimits.max_drive_level
        spin.setFixedWidth(90)
        layout.addWidget(spin, 0, 1)
        layout.addWidget(QLabel("(0, 15]"), 0, 2)

        layout.addWidget(QLabel("Status:"), 1, 0)
        layout.addWidget(
            self._register(
                "char_status_label", self._make_local_label("-")
            ),
            1,
            1,
            1,
            2,
        )

        layout.addWidget(QLabel("Elapsed:"), 2, 0)
        layout.addWidget(
            self._register("elapsed_label", self._make_local_label("-")),
            2,
            1,
            1,
            2,
        )

        layout.addWidget(QLabel("Phase:"), 3, 0)
        layout.addWidget(
            self._register(
                "local_phase_status", self._make_local_label("-")
            ),
            3,
            1,
            1,
            2,
        )

        group.setLayout(layout)
        return group
```

Add the imports this needs at the top of `phase_builders.py` if absent:
`QDoubleSpinBox` from `PyQt5.QtWidgets`, and

```python
from sc_linac_physics.applications.rf_commissioning.phases.cavity_char import (
    CavityCharLimits,
)
from sc_linac_physics.utils.sc_linac import linac_utils
```

Export it from `ui/builders/__init__.py` alongside `SSACharUI`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/applications/rf_commissioning/ui/builders/test_cavity_char_ui.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Format, lint, commit**

```bash
black src/sc_linac_physics/applications/rf_commissioning/ui/builders/ tests/applications/rf_commissioning/ui/builders/
flake8 src/sc_linac_physics/applications/rf_commissioning/ui/builders/ --count --max-complexity=10 --max-line-length=120
git add src/sc_linac_physics/applications/rf_commissioning/ui/builders/ tests/applications/rf_commissioning/ui/builders/test_cavity_char_ui.py
git commit -m "feat(rf-commissioning): add the cavity characterization UI builder"
```

---

### Task 2: CavityCharController — run the phase

**Files:**
- Create: `src/sc_linac_physics/applications/rf_commissioning/ui/controllers/cavity_char_controller.py`
- Test: `tests/applications/rf_commissioning/ui/controllers/test_cavity_char_controller.py`

**Interfaces:**
- Consumes: `CavityCharPhase`, `CavityCharLimits`, `PhaseContext`,
  `PhaseResult`, `CommissioningSession`, `CommissioningPhase.CAVITY_CHAR`,
  and from Task 1 the widget names bound onto the view.
- Produces: `CavityCharController(view, session)` with
  `phase_completed = pyqtSignal(object)`,
  `phase_run_finished = pyqtSignal(bool, str)`,
  `elapsed_updated = pyqtSignal(float)`, and methods
  `setup_pv_connections()`, `update_pv_addresses(cryomodule=None,
  cavity_number=None)`, `on_run_characterization()`, `on_abort()`,
  `on_pause_test()`, `_get_drive_level() -> float | None`.

- [ ] **Step 1: Write the failing test**

```python
from unittest.mock import Mock

import pytest

from sc_linac_physics.applications.rf_commissioning.ui.controllers.cavity_char_controller import (  # noqa: E501
    CavityCharController,
)


@pytest.fixture
def view():
    v = Mock()
    v.drive_level_spinbox.value.return_value = 10.0
    return v


def test_drive_level_read_from_the_spinbox(view):
    c = CavityCharController(view, Mock())
    assert c._get_drive_level() == 10.0


def test_drive_level_above_max_is_rejected(view):
    view.drive_level_spinbox.value.return_value = 15.1
    c = CavityCharController(view, Mock())
    assert c._get_drive_level() is None
    view.show_error.assert_called_once()


def test_drive_level_of_zero_is_rejected(view):
    view.drive_level_spinbox.value.return_value = 0.0
    c = CavityCharController(view, Mock())
    assert c._get_drive_level() is None


def test_abort_requests_abort_and_does_not_write_a_pv(view):
    c = CavityCharController(view, Mock())
    cavity = Mock()
    c._cavity = cavity
    c.on_abort()
    cavity.request_abort.assert_called_once()
    cavity.start_characterization.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/applications/rf_commissioning/ui/controllers/test_cavity_char_controller.py -v`
Expected: FAIL with `ModuleNotFoundError: ... cavity_char_controller`

- [ ] **Step 3: Write minimal implementation**

```python
"""Controller for the Cavity Characterization display."""

import time
from threading import Thread

from PyQt5.QtCore import QObject, QTimer, pyqtSignal

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
)
from sc_linac_physics.applications.rf_commissioning.phases.cavity_char import (
    CavityCharLimits,
    CavityCharPhase,
)
from sc_linac_physics.applications.rf_commissioning.phases.phase_base import (
    PhaseContext,
    PhaseResult,
)
from sc_linac_physics.applications.rf_commissioning.session_manager import (
    CommissioningSession,
)
from sc_linac_physics.utils.sc_linac.linac import Machine


class CavityCharController(QObject):
    """Owns CavityCharPhase execution for the Cavity Characterization display."""

    phase_completed = pyqtSignal(object)
    phase_run_finished = pyqtSignal(bool, str)
    # Seconds since start_characterization, emitted from the poll thread so
    # the elapsed label updates on the GUI thread.
    elapsed_updated = pyqtSignal(float)

    def __init__(self, view, session: CommissioningSession) -> None:
        super().__init__()
        self.view = view
        self.session = session
        self.limits = CavityCharLimits()
        self.context: PhaseContext | None = None
        self.phase: CavityCharPhase | None = None
        self.machine: Machine | None = None
        self._cavity = None
        self._paused = False
        self._active_phase_instance_id: int | None = None
        self.phase_run_finished.connect(self._on_phase_run_finished)

    def _get_drive_level(self) -> float | None:
        """Read the spinbox and apply CavityCharLimits' own bounds.

        The phase re-validates before writing SEL_ASET; checking here as well
        means the operator gets told before a phase instance is opened.
        """
        drive = float(self.view.drive_level_spinbox.value())
        if not 0 < drive <= self.limits.max_drive_level:
            self.view.show_error(
                f"Drive level must be in (0, "
                f"{self.limits.max_drive_level:.0f}]"
            )
            return None
        return drive

    def on_abort(self) -> None:
        """Stop the wait loop. Writes nothing to the machine.

        There is no characterization abort PV — see the spec's hardware
        assumptions. request_abort() sets abort_flag, which check_abort()
        reads inside _wait_for_completion.
        """
        if self._cavity is not None:
            self._cavity.request_abort()
        self.view.log_message(
            "Abort requested — this stops waiting for the result. The "
            "characterization itself continues in the IOC."
        )

    def on_pause_test(self) -> None:
        self._paused = not self._paused

    def _on_phase_run_finished(self, success: bool, error_msg: str) -> None:
        if success:
            self.phase_completed.emit(self.context.record)
        else:
            self.view.show_error(error_msg)

    # --- PV wiring and the run entry point ---------------------------------

    def setup_pv_connections(self) -> None:
        if self.session.has_active_record():
            self.update_pv_addresses()

    def update_pv_addresses(
        self,
        cryomodule: str | None = None,
        cavity_number: str | None = None,
    ) -> None:
        """Resolve the selected cavity and cache it on the controller.

        Also publishes the cavity's own loaded-Q window to the view, which the
        results panel renders alongside the measurement.
        """
        cryomodule, cavity_number = resolve_cavity_selection(
            self.view, cryomodule, cavity_number
        )
        if cryomodule is None or cavity_number is None:
            return
        try:
            cavity = self._get_machine_cavity(
                int(cryomodule), int(cavity_number)
            )
            self._cavity = cavity
            self.view.cavity_loaded_q_window = (
                cavity.loaded_q_lower_limit,
                cavity.loaded_q_upper_limit,
            )
        except Exception as exc:
            self.view.log_message(f"Error setting PVs: {exc}")

    def _get_machine_cavity(self, cm: int, cav: int):
        if self.machine is None:
            self.machine = Machine()
        return self.machine.cryomodules[str(cm).zfill(2)].cavities[cav]

    def on_run_characterization(self) -> None:
        """Validate, open a phase instance, then run on a thread."""
        drive_level = self._get_drive_level()
        if drive_level is None:
            return
        operator = self.view.get_current_operator()
        if not operator:
            self.view.show_error("Select an operator before running")
            return
        if self._cavity is None:
            self.view.show_error("No cavity selected")
            return
        if not self._prepare_phase_context(
            self._cavity, operator, drive_level
        ):
            return
        self.view.push_results_button.setEnabled(False)
        self._execute_phase_async()
```

Task 2 also needs these imports:

```python
from sc_linac_physics.applications.rf_commissioning.ui.controllers.piezo_pre_rf_pv import (  # noqa: E501
    resolve_cavity_selection,
)
```

`_prepare_phase_context` and `_execute_phase_async` land in Task 3; until then
`on_run_characterization` will fail its own test, so leave it uncovered until
Task 3 and assert only `_get_drive_level` and `on_abort` here.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/applications/rf_commissioning/ui/controllers/test_cavity_char_controller.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
black src/sc_linac_physics/applications/rf_commissioning/ui/controllers/ tests/applications/rf_commissioning/ui/controllers/
flake8 src/sc_linac_physics/applications/rf_commissioning/ui/controllers/cavity_char_controller.py --count --max-complexity=10 --max-line-length=120
git add src/sc_linac_physics/applications/rf_commissioning/ui/controllers/cavity_char_controller.py tests/applications/rf_commissioning/ui/controllers/test_cavity_char_controller.py
git commit -m "feat(rf-commissioning): add the cavity characterization controller"
```

---

### Task 3: Run the phase on a thread, with elapsed time

**Files:**
- Modify: `src/sc_linac_physics/applications/rf_commissioning/ui/controllers/cavity_char_controller.py`
- Test: `tests/applications/rf_commissioning/ui/controllers/test_cavity_char_controller.py`

**Interfaces:**
- Consumes: Task 2's `CavityCharController`.
- Produces: `_prepare_phase_context(cavity, operator, drive_level) -> bool`,
  `_execute_phase_async()`, `_run_phase_in_background()`,
  `_execute_single_step(step_name) -> bool`, `_emit_elapsed_until_done()`.

- [ ] **Step 1: Write the failing test**

```python
def test_steps_run_in_the_backend_order(view, monkeypatch):
    c = CavityCharController(view, Mock())
    phase = Mock()
    phase.get_phase_steps.return_value = [
        "verify_initial_state",
        "set_drive_level",
        "start_characterization",
        "wait_for_completion",
        "read_results",
        "push_results",
        "record_results",
    ]
    result = Mock()
    result.result = PhaseResult.SUCCESS
    phase.execute_step.return_value = result
    c.phase = phase
    c.context = Mock()

    ran = []
    monkeypatch.setattr(
        c, "_execute_single_step", lambda s: ran.append(s) or True
    )
    monkeypatch.setattr(c, "_finalize_background_phase", lambda: None)
    monkeypatch.setattr("threading.Thread", _RunInline)

    c._run_phase_in_background()
    assert ran == phase.get_phase_steps.return_value


def test_a_failed_step_stops_the_run(view, monkeypatch):
    c = CavityCharController(view, Mock())
    phase = Mock()
    phase.get_phase_steps.return_value = ["a", "b", "c"]
    c.phase = phase
    c.context = Mock()

    ran = []

    def one_then_fail(step):
        ran.append(step)
        return step == "a"

    monkeypatch.setattr(c, "_execute_single_step", one_then_fail)
    monkeypatch.setattr("threading.Thread", _RunInline)

    finished = []
    c.phase_run_finished.connect(lambda ok, msg: finished.append((ok, msg)))
    c._run_phase_in_background()

    assert ran == ["a", "b"]
    assert finished and finished[0][0] is False
```

Add this helper at the top of the test module — the controller starts a daemon
thread, and a test that waits on real threads is a test that hangs in CI:

```python
class _RunInline:
    """Stand-in for threading.Thread that runs the target synchronously."""

    def __init__(self, target=None, daemon=None, **kwargs):
        self._target = target

    def start(self):
        self._target()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/applications/rf_commissioning/ui/controllers/test_cavity_char_controller.py -k background -v`
Expected: FAIL with `AttributeError: ... has no attribute '_run_phase_in_background'`

- [ ] **Step 3: Write minimal implementation**

Add to `CavityCharController`:

```python
    def _prepare_phase_context(
        self, cavity, operator: str, drive_level: float
    ) -> bool:
        record = self.session.get_active_record()
        record_id = self.session.get_active_record_id()

        can_run, reason = self.session.can_run_phase(
            CommissioningPhase.CAVITY_CHAR
        )
        if not can_run:
            self.view.show_error(
                f"Cannot run CAVITY_CHAR phase: {reason}"
            )
            return False

        if record_id is not None:
            phase_start = self.session.start_active_phase_instance(
                CommissioningPhase.CAVITY_CHAR, operator=operator
            )
            self._active_phase_instance_id = (
                phase_start.phase_instance_id if phase_start else None
            )

        self.context = PhaseContext(
            record=record,
            operator=operator,
            parameters={"cavity": cavity, "drive_level": drive_level},
            phase_instance_id=self._active_phase_instance_id,
            run_intent="commissioning",
        )
        self.phase = CavityCharPhase(self.context, self.limits)

        is_valid, message = self.phase.validate_prerequisites()
        if not is_valid:
            self.view.show_error(f"Prerequisites not met: {message}")
            return False
        return True

    def _execute_phase_async(self) -> None:
        if not self.context or not self.phase:
            return
        QTimer.singleShot(100, self._run_phase_in_background)

    def _run_phase_in_background(self) -> None:
        def worker() -> None:
            try:
                self.phase._mark_phase_started()
                for step_name in self.phase.get_phase_steps():
                    if not self._execute_single_step(step_name):
                        self.phase_run_finished.emit(
                            False, f"Step failed: {step_name}"
                        )
                        return
                self._finalize_background_phase()
            except Exception as exc:
                self.phase_run_finished.emit(False, str(exc))

        Thread(target=worker, daemon=True).start()

    def _execute_single_step(self, step_name: str) -> bool:
        """Run one step, retrying while the backend asks for a retry."""
        while True:
            result = self.phase.execute_step(step_name)
            if result.result is PhaseResult.RETRY:
                self.view.log_message(f"{step_name}: {result.message}")
                time.sleep(result.retry_delay_seconds or 1.0)
                continue
            if result.result is PhaseResult.SUCCESS:
                self.view.log_message(f"{step_name}: {result.message}")
                return True
            self.view.log_message(f"{step_name} failed: {result.message}")
            return False

    def _finalize_background_phase(self) -> None:
        self.phase.finalize_phase()
        self.phase_run_finished.emit(True, "")

    def _emit_elapsed_until_done(self, started_at: float) -> None:
        """Emit elapsed seconds while the characterization is running.

        PROBECALSTS reports running or crashed and nothing in between, so
        elapsed time is the only progress the panel can honestly show.
        """
        while self._cavity is not None and self._cavity.characterization_running:
            self.elapsed_updated.emit(time.monotonic() - started_at)
            time.sleep(self.limits.status_poll_interval)
```

`import threading` is not needed — `Thread` is imported directly, and the test
patches `threading.Thread`, so change the call site to `threading.Thread(...)`
and `import threading` instead of `from threading import Thread` so the patch
takes effect.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/applications/rf_commissioning/ui/controllers/test_cavity_char_controller.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add -u
git commit -m "feat(rf-commissioning): run the cavity characterization on a thread"
```

---

### Task 3b: A crash and a timeout must not read the same

**Files:**
- Modify: `src/sc_linac_physics/applications/rf_commissioning/ui/displays/cavity_char.py`
- Test: `tests/applications/rf_commissioning/ui/controllers/test_cavity_char_controller.py`

**Interfaces:**
- Consumes: Task 3's `_execute_single_step`.
- Produces: `CavityCharDisplay.set_char_status(text)` and distinct copy for the
  two terminal states.

The backend returns FAILED for both, with different messages — "Characterization
crashed — check the cavity's PROBECALSTS and the RF interlocks" versus
"Characterization did not finish within 300 s". Conflating them in the panel
hides an IOC fault behind what looks like a slow measurement.

- [ ] **Step 1: Write the failing test**

```python
def test_crash_and_timeout_produce_different_status_text(view):
    c = CavityCharController(view, Mock())
    phase = Mock()
    c.phase = phase

    crashed = Mock()
    crashed.result = PhaseResult.FAILED
    crashed.message = (
        "Characterization crashed — check the cavity's PROBECALSTS and "
        "the RF interlocks"
    )
    timed_out = Mock()
    timed_out.result = PhaseResult.FAILED
    timed_out.message = "Characterization did not finish within 300 s"

    phase.execute_step.return_value = crashed
    assert c._execute_single_step("wait_for_completion") is False
    first = view.log_message.call_args[0][0]

    phase.execute_step.return_value = timed_out
    assert c._execute_single_step("wait_for_completion") is False
    second = view.log_message.call_args[0][0]

    assert first != second
    assert "crashed" in first
    assert "did not finish" in second
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/applications/rf_commissioning/ui/controllers/test_cavity_char_controller.py -k crash -v`
Expected: PASS already if `_execute_single_step` logs `result.message`
verbatim — in which case this task is a regression guard rather than a change.
If it FAILS, the failure branch is collapsing the message; fix that.

- [ ] **Step 3: Write minimal implementation**

`_execute_single_step` already logs `result.message` on the failure branch, so
the distinction is preserved. Add the panel wiring so the operator sees it
without opening the log:

```python
    def set_char_status(self, text: str) -> None:
        if hasattr(self, "char_status_label"):
            self.char_status_label.setText(text)
```

and have the controller call `self.view.set_char_status(result.message)` on the
failure branch of `_execute_single_step`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/applications/rf_commissioning/ui/controllers/ -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -u && git commit -m "feat(rf-commissioning): surface char crash and timeout distinctly"
```

---

### Task 4: Real CavityCharDisplay, placeholder deleted

**Files:**
- Create: `src/sc_linac_physics/applications/rf_commissioning/ui/displays/cavity_char.py`
- Modify: `src/sc_linac_physics/applications/rf_commissioning/ui/displays/standard.py` (delete `CavityCharDisplay`)
- Modify: `src/sc_linac_physics/applications/rf_commissioning/ui/displays/registry.py` (import from `.cavity_char`)
- Modify: `src/sc_linac_physics/applications/rf_commissioning/ui/displays/__init__.py` and `ui/__init__.py` (repoint the re-export)
- Test: `tests/applications/rf_commissioning/ui/test_displays.py`

**Interfaces:**
- Consumes: Task 1's `CavityCharUI`, Task 3's `CavityCharController`.
- Produces: `CavityCharDisplay(BasePlaceholderDisplay)` with
  `UI_CLASS = CavityCharUI`, `PHASE_NAME = "Cavity Characterization"`,
  `DATA_ATTR = "cavity_char"`, `DATA_MODEL = CavityCharacterization`.

This is the manoeuvre the spec flags as a hazard: #270 left a placeholder
`FrequencyTuningDisplay` re-exported while the registry used the real class.
Delete the placeholder and repoint every re-export in this one task. #297's
test, parametrized over `PHASE_DISPLAY_MAP`, then covers CAVITY_CHAR.

- [ ] **Step 1: Write the failing test**

Add to `tests/applications/rf_commissioning/ui/test_displays.py`:

```python
def test_cavity_char_display_is_not_a_placeholder():
    from sc_linac_physics.applications.rf_commissioning.ui.displays import (
        CavityCharDisplay,
    )
    from sc_linac_physics.applications.rf_commissioning.ui.builders import (
        CavityCharUI,
        GenericPhaseUI,
    )

    assert CavityCharDisplay.UI_CLASS is CavityCharUI
    assert CavityCharDisplay.UI_CLASS is not GenericPhaseUI


def test_cavity_char_export_matches_the_registry():
    from sc_linac_physics.applications.rf_commissioning.ui import (
        displays as displays_pkg,
    )
    from sc_linac_physics.applications.rf_commissioning.ui.displays.registry import (  # noqa: E501
        PHASE_DISPLAY_MAP,
    )
    from sc_linac_physics.applications.rf_commissioning.models.data_models import (  # noqa: E501
        CommissioningPhase,
    )

    registry_cls = PHASE_DISPLAY_MAP[CommissioningPhase.CAVITY_CHAR]
    assert displays_pkg.CavityCharDisplay is registry_cls
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/applications/rf_commissioning/ui/test_displays.py -k cavity_char -v`
Expected: FAIL — `UI_CLASS` is `GenericPhaseUI`

- [ ] **Step 3: Write minimal implementation**

```python
"""Cavity Characterization commissioning display."""

from PyQt5.QtCore import pyqtSlot

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CavityCharacterization,
    CommissioningRecord,
)
from sc_linac_physics.applications.rf_commissioning.session_manager import (
    CommissioningSession,
)
from sc_linac_physics.applications.rf_commissioning.ui.builders import (
    CavityCharUI,
)
from sc_linac_physics.applications.rf_commissioning.ui.controllers.cavity_char_controller import (  # noqa: E501
    CavityCharController,
)

from .base_placeholder import BasePlaceholderDisplay


class CavityCharDisplay(BasePlaceholderDisplay):
    """Display for the Cavity Characterization phase."""

    UI_CLASS = CavityCharUI
    PHASE_NAME = "Cavity Characterization"
    DATA_ATTR = "cavity_char"
    DATA_MODEL = CavityCharacterization

    def __init__(
        self, parent=None, session: CommissioningSession | None = None
    ):
        super().__init__(parent, session=session)
        self.setWindowTitle("Cavity Characterization - PyDM")
        self.controller = CavityCharController(self, self.session)
        self.controller.elapsed_updated.connect(self._on_elapsed)
        self.controller.setup_pv_connections()

    def setup_ui(self):
        callbacks = {
            "on_run_automated_test": self.on_run_characterization,
            "on_pause_test": self.on_pause_test,
            "on_abort_test": self.on_abort,
        }
        self.ui = self.UI_CLASS(self, callbacks)
        main_layout = self.ui.build()
        self._bind_ui_widgets()
        self.setLayout(main_layout)
        self.update_timestamp()

    def refresh_from_record(self, record: CommissioningRecord) -> None:
        self._update_stored_readout(record.cavity_char)

    def on_record_loaded(
        self, record: CommissioningRecord, record_id: int
    ) -> None:
        self.controller.update_pv_addresses(
            record.cryomodule, str(record.cavity_number)
        )
        self.refresh_from_record(record)

    def _update_stored_readout(self, result) -> None:
        if result is None:
            self._clear_phase_specific_readouts()
            return
        self._set_generic_stored_data(result)
        self._apply_phase_specific_readouts(result)

    def _on_elapsed(self, seconds: float) -> None:
        limit = self.controller.limits.characterization_timeout_seconds
        if hasattr(self, "elapsed_label"):
            self.elapsed_label.setText(f"{seconds:.0f} s / {limit:.0f} s")

    @pyqtSlot()
    def on_run_characterization(self):
        self.controller.on_run_characterization()

    @pyqtSlot()
    def on_abort(self):
        self.controller.on_abort()

    @pyqtSlot()
    def on_pause_test(self):
        self.controller.on_pause_test()
```

Then: delete `CavityCharDisplay` from `standard.py` (and its now-unused
`CavityCharacterization` import if nothing else there uses it); in
`registry.py` replace the `standard` import of `CavityCharDisplay` with
`from .cavity_char import CavityCharDisplay`; in `displays/__init__.py` move
`CavityCharDisplay` out of the `.standard` import block into
`from .cavity_char import CavityCharDisplay`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/applications/rf_commissioning/ -v`
Expected: PASS, including the two new tests

- [ ] **Step 5: Commit and open PR 1**

```bash
black . && flake8 . --count --max-complexity=10 --max-line-length=120
pytest -q
git add -A
git commit -m "feat(rf-commissioning): replace the cavity char placeholder display"
```

PR 1 description must include, under `## Operator-visible`: the CAVITY_CHAR tab
changes from a generic placeholder to a working panel with a drive-level entry,
a live status and elapsed readout, and Run/Abort. Abort stops waiting, not the
characterization.

---

## PR 2 — results review panel (read-only)

Machine writes: none. Target ~250 lines.

### Task 5: Render loaded Q and scale factor against the cavity's Q window

**Files:**
- Modify: `src/sc_linac_physics/applications/rf_commissioning/ui/builders/phase_builders.py` (`CavityCharUI._build_char_results`)
- Modify: `src/sc_linac_physics/applications/rf_commissioning/ui/displays/cavity_char.py`
- Test: `tests/applications/rf_commissioning/ui/builders/test_cavity_char_ui.py`, `tests/applications/rf_commissioning/ui/test_cavity_char_results.py`

**Interfaces:**
- Consumes: Task 1's builder, Task 4's display.
- Produces: registered widgets `loaded_q_label`, `scale_factor_label`,
  `q_window_label`, `tolerance_label`; and on the display
  `render_results(loaded_q, scale_factor, in_tolerance, lower, upper)`.

No probe Q row. `_read_probe_q()` returns None by design.

- [ ] **Step 1: Write the failing test**

```python
def test_q_window_shows_the_loaded_cavity_bounds(qapp_global):
    parent = QWidget()
    ui = CavityCharUI(parent, callbacks={})
    ui.build()
    assert "q_window_label" in ui.widgets
    assert "probe_q_label" not in ui.widgets


def test_results_render_with_the_cavity_window(display):
    display.render_results(
        loaded_q=4.1e7,
        scale_factor=31.5,
        in_tolerance=True,
        lower=2.5e7,
        upper=5.1e7,
    )
    assert "4.100e+07" in display.loaded_q_label.text()
    assert "31.5" in display.scale_factor_label.text()
    assert "2.50e+07" in display.q_window_label.text()
    assert "5.10e+07" in display.q_window_label.text()
    assert display.tolerance_label.text() == "IN TOLERANCE"


def test_out_of_window_result_says_so(display):
    display.render_results(
        loaded_q=6.0e7,
        scale_factor=31.5,
        in_tolerance=False,
        lower=2.5e7,
        upper=5.1e7,
    )
    assert display.tolerance_label.text() == "OUT OF TOLERANCE"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/applications/rf_commissioning/ui/test_cavity_char_results.py -v`
Expected: FAIL — `render_results` does not exist

- [ ] **Step 3: Write minimal implementation**

Add to `CavityCharUI`, and call it from `build()` in the right panel above
`_build_stored_data_section`:

```python
    def _build_char_results(self) -> QGroupBox:
        """Measured values and the window they were judged against.

        No probe Q row: CavityCharPhase._read_probe_q() returns None because
        there is no readback PV for it and no PUSH_QPROBE to pair with one.
        """
        group = QGroupBox("Measured")
        layout = QGridLayout()
        layout.setSpacing(6)
        layout.setContentsMargins(8, 8, 8, 8)

        for row, (label, name) in enumerate(
            (
                ("Loaded Q:", "loaded_q_label"),
                ("Cavity scale factor:", "scale_factor_label"),
                ("Expected Q window:", "q_window_label"),
                ("", "tolerance_label"),
            )
        ):
            layout.addWidget(QLabel(label), row, 0)
            layout.addWidget(
                self._register(name, self._make_local_label("-")), row, 1
            )

        group.setLayout(layout)
        return group
```

Then on the display:

```python
    def render_results(
        self,
        loaded_q: float,
        scale_factor: float,
        in_tolerance: bool,
        lower: float,
        upper: float,
    ) -> None:
        """Show the measured values beside the window they were judged against.

        The bounds come from the loaded Cavity's own loaded_q_lower_limit /
        loaded_q_upper_limit, which differ for harmonic-linearizer, HE and
        standard cavities, so they are passed in rather than hard-coded.
        """
        self.loaded_q_label.setText(f"{loaded_q:.3e}")
        self.scale_factor_label.setText(f"{scale_factor:.1f}")
        self.q_window_label.setText(f"[{lower:.2e}, {upper:.2e}]")
        self.tolerance_label.setText(
            "IN TOLERANCE" if in_tolerance else "OUT OF TOLERANCE"
        )
        self.tolerance_label.setStyleSheet(
            STATUS_LABEL_PASS if in_tolerance else STATUS_LABEL_FAIL
        )
```

Import `STATUS_LABEL_PASS` / `STATUS_LABEL_FAIL` from `ui.builders`, as
`ssa_char.py` does.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/applications/rf_commissioning/ui/ -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -u && git commit -m "feat(rf-commissioning): show cavity char results against the Q window"
```

---

### Task 6: Wire read_results into the panel and refresh_from_record

**Files:**
- Modify: `src/sc_linac_physics/applications/rf_commissioning/ui/controllers/cavity_char_controller.py`
- Modify: `src/sc_linac_physics/applications/rf_commissioning/ui/displays/cavity_char.py`
- Test: `tests/applications/rf_commissioning/ui/test_cavity_char_results.py`

**Interfaces:**
- Consumes: Task 5's `render_results`.
- Produces: `results_ready = pyqtSignal(dict)` on the controller, emitted after
  the `read_results` step with the keys `CavityCharPhase._result_data()`
  returns: `loaded_q`, `scale_factor`, `probe_q`, `loaded_q_in_tolerance`,
  `drive_level`.

- [ ] **Step 1: Write the failing test**

```python
def test_a_record_with_no_cavity_char_renders_empty(display):
    record = Mock()
    record.cavity_char = None
    display.refresh_from_record(record)
    assert display.loaded_q_label.text() == "-"


def test_reloading_a_record_shows_its_stored_values(display):
    record = Mock()
    record.cavity_char = CavityCharacterization(
        loaded_q=4.1e7, scale_factor=31.5, loaded_q_in_tolerance=True
    )
    display.cavity_loaded_q_window = (2.5e7, 5.1e7)
    display.refresh_from_record(record)
    assert "4.100e+07" in display.loaded_q_label.text()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/applications/rf_commissioning/ui/test_cavity_char_results.py -k record -v`
Expected: FAIL — `refresh_from_record` does not populate the labels

- [ ] **Step 3: Write minimal implementation**

Declare `results_ready = pyqtSignal(dict)` on the controller and emit it from
`_execute_single_step` when `step_name == "read_results"` and the result
succeeded:

```python
            if result.result is PhaseResult.SUCCESS:
                self.view.log_message(f"{step_name}: {result.message}")
                if step_name == "read_results":
                    self.results_ready.emit(self.phase._result_data())
                return True
```

On the display, connect it in `__init__` and add:

```python
        self.cavity_loaded_q_window: tuple[float, float] | None = None
        self.controller.results_ready.connect(self.on_results_ready)
```

```python
    def on_results_ready(self, data: dict) -> None:
        """Render a fresh measurement.

        cavity_loaded_q_window is set by the controller when a record loads.
        Without it there is nothing honest to judge the value against, so the
        bounds render as "-" rather than defaulting to the standard pair.
        """
        lower, upper = self.cavity_loaded_q_window or (None, None)
        self.render_results(
            loaded_q=data["loaded_q"],
            scale_factor=data["scale_factor"],
            in_tolerance=bool(data["loaded_q_in_tolerance"]),
            lower=lower,
            upper=upper,
        )

    def refresh_from_record(self, record: CommissioningRecord) -> None:
        result = record.cavity_char
        if result is None or result.loaded_q is None:
            self.clear_results()
        else:
            lower, upper = self.cavity_loaded_q_window or (None, None)
            self.render_results(
                loaded_q=result.loaded_q,
                scale_factor=result.scale_factor,
                in_tolerance=result.loaded_q_in_tolerance is not False,
                lower=lower,
                upper=upper,
            )
        self._update_stored_readout(result)

    def clear_results(self):
        super().clear_results()
        for name in (
            "loaded_q_label",
            "scale_factor_label",
            "q_window_label",
            "tolerance_label",
        ):
            if hasattr(self, name):
                getattr(self, name).setText("-")
```

`render_results` must tolerate `lower`/`upper` being None — format the window
as `"-"` in that case rather than crashing on `f"{None:.2e}"`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/applications/rf_commissioning/ -q`
Expected: PASS

- [ ] **Step 5: Commit and open PR 2**

```bash
black . && flake8 . --count --max-complexity=10 --max-line-length=120 && pytest -q
git add -A && git commit -m "feat(rf-commissioning): populate the cavity char panel from the record"
```

---

### Task 6b: Stale prerequisite warning banner

**Files:**
- Modify: `src/sc_linac_physics/applications/rf_commissioning/ui/builders/phase_builders.py`
- Modify: `src/sc_linac_physics/applications/rf_commissioning/ui/displays/cavity_char.py`
- Test: `tests/applications/rf_commissioning/ui/test_cavity_char_results.py`

**Interfaces:**
- Consumes: `CavityCharPhase._stale_prerequisites() -> list[str]`, which reads
  the record's `ssa_char` and `frequency_tuning` timestamps against
  `prerequisite_staleness_hours` (24 h).
- Produces: registered widget `stale_warning_label`, and
  `CavityCharDisplay.show_stale_warning(items: list[str])`.

A warning, never a block — the backend treats staleness the same way, because
the workflow already enforces that those phases ran at all.

- [ ] **Step 1: Write the failing test**

```python
def test_no_banner_when_prerequisites_are_fresh(display):
    display.show_stale_warning([])
    assert display.stale_warning_label.text() == ""
    assert not display.stale_warning_label.isVisible()


def test_banner_lists_every_stale_prerequisite(display):
    display.show_stale_warning(
        ["SSA calibration is 72 h old", "frequency tuning is 40 h old"]
    )
    text = display.stale_warning_label.text()
    assert "SSA calibration is 72 h old" in text
    assert "frequency tuning is 40 h old" in text


def test_a_stale_prerequisite_does_not_disable_the_run(display):
    display.show_stale_warning(["SSA calibration is 72 h old"])
    assert display.run_button.isEnabled()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/applications/rf_commissioning/ui/test_cavity_char_results.py -k stale -v`
Expected: FAIL — no `stale_warning_label`

- [ ] **Step 3: Write minimal implementation**

Register the label at the top of the left panel in `build()`:

```python
        warn = self._register(
            "stale_warning_label", self._make_local_label("")
        )
        warn.setStyleSheet(STATUS_LABEL_FAIL)
        warn.setWordWrap(True)
        warn.setVisible(False)
        left_panel.addWidget(warn)
```

On the display:

```python
    def show_stale_warning(self, items: list[str]) -> None:
        """Warn on stale upstream results without blocking the run.

        The workflow already enforces that SSA_CHAR and FREQUENCY_TUNING ran;
        this is only about how long ago, so it is the operator's call.
        """
        if not hasattr(self, "stale_warning_label"):
            return
        if not items:
            self.stale_warning_label.setText("")
            self.stale_warning_label.setVisible(False)
            return
        self.stale_warning_label.setText(
            "Characterizing against stale inputs: " + "; ".join(items)
        )
        self.stale_warning_label.setVisible(True)
```

Call it from `on_record_loaded`, building a throwaway `CavityCharPhase` on the
loaded record so `_stale_prerequisites()` can read it without starting a run.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/applications/rf_commissioning/ -q`
Expected: PASS

- [ ] **Step 5: Commit and open PR 2**

```bash
black . && flake8 . --count --max-complexity=10 --max-line-length=120 && pytest -q
git add -A && git commit -m "feat(rf-commissioning): warn when cavity char inputs are stale"
```

PR 2 description: `## Operator-visible` — the panel now shows measured loaded Q
and scale factor with the window they were judged against, and warns when the
SSA calibration or frequency tuning behind them is over 24 h old. Read-only;
nothing is written to the machine in this PR.

---

## PR 3 — the gated push

Machine writes: `PUSH_QLOADED.PROC`, `PUSH_CAV_SCALE.PROC`. Target ~200 lines.

### Task 7: Push button, disabled until a read succeeds

**Files:**
- Modify: `src/sc_linac_physics/applications/rf_commissioning/ui/builders/phase_builders.py`
- Modify: `src/sc_linac_physics/applications/rf_commissioning/ui/controllers/cavity_char_controller.py`
- Modify: `src/sc_linac_physics/applications/rf_commissioning/ui/displays/cavity_char.py`
- Test: `tests/applications/rf_commissioning/ui/test_cavity_char_push.py`

**Interfaces:**
- Consumes: Task 6's `results_ready`.
- Produces: registered widget `push_results_button`, callback key
  `on_push_results`, and `CavityCharController.on_push_results()`.

- [ ] **Step 1: Write the failing test**

```python
def test_push_button_starts_disabled(display):
    assert not display.push_results_button.isEnabled()


def test_push_button_enables_after_an_in_window_read(display):
    display.on_results_ready(
        {
            "loaded_q": 4.1e7,
            "scale_factor": 31.5,
            "probe_q": None,
            "loaded_q_in_tolerance": True,
            "drive_level": 10.0,
        }
    )
    assert display.push_results_button.isEnabled()


def test_push_with_nothing_measured_does_not_write(view):
    c = CavityCharController(view, Mock())
    c.phase = None
    c.on_push_results()
    view.show_error.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/applications/rf_commissioning/ui/test_cavity_char_push.py -v`
Expected: FAIL — no `push_results_button`

- [ ] **Step 3: Write minimal implementation**

Register the button in `_build_char_results`, `setEnabled(False)` at build
time, connect it through `self._connect(button, "on_push_results")`, and add:

```python
    def on_push_results(self) -> None:
        """Push the reviewed values. Two PV writes, both value 1.

        PUSH_QLOADED.PROC sets the cavity's operational loaded Q from
        QLOADED_NEW; PUSH_CAV_SCALE.PROC sets the cavity scale factor from
        CAV:CAL_SCALEB_NEW. The second can fail after the first succeeds, so
        the panel reports the step result rather than assuming both landed.
        """
        if self.phase is None or self.phase._loaded_q is None:
            self.view.show_error(
                "Nothing measured yet — run the characterization first"
            )
            return
        threading.Thread(
            target=self._push_in_background, daemon=True
        ).start()

    def _push_in_background(self) -> None:
        result = self.phase.execute_step("push_results")
        self.push_finished.emit(
            result.result is PhaseResult.SUCCESS, result.message
        )
```

Add `push_finished = pyqtSignal(bool, str)`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/applications/rf_commissioning/ui/test_cavity_char_push.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -u && git commit -m "feat(rf-commissioning): gate the cavity char push behind a read"
```

---

### Task 8: An out-of-window push requires a typed reason

**Files:**
- Modify: `src/sc_linac_physics/applications/rf_commissioning/ui/builders/phase_builders.py`
- Modify: `src/sc_linac_physics/applications/rf_commissioning/ui/displays/cavity_char.py`
- Modify: `src/sc_linac_physics/applications/rf_commissioning/ui/controllers/cavity_char_controller.py`
- Test: `tests/applications/rf_commissioning/ui/test_cavity_char_push.py`

**Interfaces:**
- Consumes: Task 7's `push_results_button`.
- Produces: registered widget `override_reason_edit` (a `QLineEdit`), and the
  reason written to `CavityCharacterization.notes` before the push runs.

- [ ] **Step 1: Write the failing test**

```python
def test_out_of_window_read_leaves_the_push_disabled(display):
    display.on_results_ready(_out_of_window())
    assert not display.push_results_button.isEnabled()
    assert display.override_reason_edit.isEnabled()


def test_typing_a_reason_enables_the_push(display):
    display.on_results_ready(_out_of_window())
    display.override_reason_edit.setText("accepted per RDP, see elog 12345")
    assert display.push_results_button.isEnabled()


def test_whitespace_is_not_a_reason(display):
    display.on_results_ready(_out_of_window())
    display.override_reason_edit.setText("   ")
    assert not display.push_results_button.isEnabled()


def test_the_reason_reaches_the_record(display):
    display.on_results_ready(_out_of_window())
    display.override_reason_edit.setText("accepted per RDP")
    display.on_push_results()
    assert (
        "accepted per RDP"
        in display.controller.context.record.cavity_char.notes
    )


def _out_of_window():
    return {
        "loaded_q": 6.0e7,
        "scale_factor": 31.5,
        "probe_q": None,
        "loaded_q_in_tolerance": False,
        "drive_level": 10.0,
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/applications/rf_commissioning/ui/test_cavity_char_push.py -k reason -v`
Expected: FAIL — no `override_reason_edit`

- [ ] **Step 3: Write minimal implementation**

Register `override_reason_edit` disabled by default. In `on_results_ready`,
when `loaded_q_in_tolerance` is False: enable the reason field, leave the push
disabled, and connect `textChanged` to a handler that enables the push only
when `text.strip()` is non-empty. In the controller, before running
`push_results`, write the reason onto the record:

```python
    def record_override_reason(self, reason: str) -> None:
        """Persist why an out-of-window loaded Q was accepted.

        CavityCharacterization.passed is already False for an out-of-window
        record; this is the only place the reason survives.
        """
        record = getattr(self.context, "record", None)
        if record is None or not reason.strip():
            return
        data = record.cavity_char or CavityCharacterization()
        stamp = datetime.now().isoformat(timespec="seconds")
        note = f"[{stamp}] loaded Q out of window, pushed anyway: {reason}"
        data.notes = f"{data.notes}\n{note}".strip() if data.notes else note
        record.cavity_char = data
```

Task 8 adds these imports to the controller:

```python
from datetime import datetime

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CavityCharacterization,
    CommissioningPhase,
)
```

And the display calls `self.controller.record_override_reason(...)` with the
field's text before invoking the push, so the note is on the record even if the
push then fails.

Also pin the record consequence, which the spec calls for and nothing else
covers:

```python
def test_an_out_of_window_record_does_not_pass():
    data = CavityCharacterization(
        loaded_q=6.0e7, scale_factor=31.5, loaded_q_in_tolerance=False
    )
    data.completed = True
    assert data.passed is False
```

Check `CavityCharacterization.is_complete` before writing that last test — if
completeness is derived rather than set by a `completed` flag, set whatever
`is_complete` actually reads so the assertion exercises `passed` and not
`is_complete`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/applications/rf_commissioning/ui/test_cavity_char_push.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -u && git commit -m "feat(rf-commissioning): require a reason to push an out-of-window loaded Q"
```

---

### Task 9: Name the PVs in the confirm step

**Files:**
- Modify: `src/sc_linac_physics/applications/rf_commissioning/ui/displays/cavity_char.py`
- Test: `tests/applications/rf_commissioning/ui/test_cavity_char_push.py`

**Interfaces:**
- Consumes: Task 8.
- Produces: `CavityCharDisplay._confirm_push_text(loaded_q, scale_factor) -> str`.

- [ ] **Step 1: Write the failing test**

```python
def test_confirm_text_names_both_pvs_and_values(display):
    text = display._confirm_push_text(4.1e7, 31.5)
    assert "PUSH_QLOADED.PROC" in text
    assert "PUSH_CAV_SCALE.PROC" in text
    assert "4.100e+07" in text
    assert "31.5" in text


def test_a_declined_confirm_does_not_push(display, monkeypatch):
    monkeypatch.setattr(
        display, "_ask_confirm", lambda text: False
    )
    pushed = []
    monkeypatch.setattr(
        display.controller, "on_push_results", lambda: pushed.append(1)
    )
    display.on_push_results()
    assert pushed == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/applications/rf_commissioning/ui/test_cavity_char_push.py -k confirm -v`
Expected: FAIL — `_confirm_push_text` does not exist

- [ ] **Step 3: Write minimal implementation**

```python
    def _cavity_label(self) -> str:
        """"CM01 cavity 3" for the confirm text, or a neutral fallback."""
        selection = self.get_current_cavity()
        if not selection:
            return "the selected cavity"
        cryomodule, cavity_number = selection
        return f"CM{cryomodule} cavity {cavity_number}"

    def _confirm_push_text(
        self, loaded_q: float, scale_factor: float
    ) -> str:
        """Spell out both writes before they happen."""
        return (
            f"Push these values to {self._cavity_label()}?\n\n"
            f"  loaded Q {loaded_q:.3e}  ->  PUSH_QLOADED.PROC\n"
            f"  scale factor {scale_factor:.1f}  ->  PUSH_CAV_SCALE.PROC\n\n"
            "Both are processed with a 1. This replaces the cavity's "
            "operational loaded Q and scale factor."
        )

    def _ask_confirm(self, text: str) -> bool:
        return (
            QMessageBox.question(
                self,
                "Push characterization results",
                text,
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            == QMessageBox.Yes
        )
```

`get_current_cavity()` comes from `PhaseDisplayBase` and returns
`tuple[str, str] | None`. Import `QMessageBox` from `PyQt5.QtWidgets`.

Route `on_push_results` through `_ask_confirm(self._confirm_push_text(...))`,
implemented with `QMessageBox.question`, and only call the controller on Yes.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest -q`
Expected: PASS, coverage above 80%

- [ ] **Step 5: Commit and open PR 3**

```bash
black . && flake8 . --count --max-complexity=10 --max-line-length=120 && pytest -q
git add -A && git commit -m "feat(rf-commissioning): name the push PVs in the confirm dialog"
```

PR 3 description, under `## Operator-visible`: measured loaded Q and scale
factor no longer reach the cavity without an explicit click, the confirm names
`PUSH_QLOADED.PROC` and `PUSH_CAV_SCALE.PROC`, and pushing an out-of-window
loaded Q requires typing a reason that is saved to the record.

---

## Open questions carried from the spec

These are `CHECK:` items, not blockers. Flag them in the PR that touches them
rather than answering them in a comment.

- Once `PROBECALSTRT` is written, does the IOC always reach either a settled
  status or `CHARACTERIZATION_CRASHED_VALUE`? PR 1 assumes so, because there is
  nothing it can send to stop it.
- Is `status_settle_delay` (2 s) enough for `QPROBE_CALC1.PROC` to settle on
  hardware? PR 2 inherits the backend's value.
- Ryan's 10% / 15% drive split by SSA power rating stays operator knowledge —
  no rating PV exists. PR 1 ships the operator-entered spinbox.
