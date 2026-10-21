"""Cavity char UI fixes from the #395 review."""

from unittest.mock import Mock, patch

import pytest

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CavityCharacterization,
)
from sc_linac_physics.applications.rf_commissioning.phases.phase_base import (
    PhaseResult,
)
from sc_linac_physics.applications.rf_commissioning.ui.container.record_lifecycle import (  # noqa: E501
    _RecordLifecycleMixin,
)
from sc_linac_physics.applications.rf_commissioning.ui.controllers.cavity_char_controller import (  # noqa: E501
    MEASURE_STEPS,
    CavityCharController,
)

MODULE = (
    "sc_linac_physics.applications.rf_commissioning.ui.controllers."
    "cavity_char_controller"
)
BACKEND_STEPS = list(MEASURE_STEPS) + ["push_results", "record_results"]


class RunInline:
    def __init__(self, target=None, daemon=None, **kwargs):
        self._target = target

    def start(self):
        self._target()


def _result(outcome, message="ok", data=None):
    r = Mock()
    r.result = outcome
    r.message = message
    r.retry_delay_seconds = None
    r.data = data or {}
    return r


@pytest.fixture
def view():
    return Mock()


def _controller(view):
    c = CavityCharController(view, Mock())
    c.context = Mock()
    c.context.parameters = {}
    c.context.is_abort_requested.return_value = False
    c.context.record.cavity_char = CavityCharacterization(loaded_q=4.1e7)
    c.phase = Mock()
    c.phase._loaded_q = 4.1e7
    c.phase.get_phase_steps.return_value = BACKEND_STEPS
    c._active_phase_instance_id = 42
    return c


# ---------------------------------------------------------------------------
# H1 / H2 cryomodules
# ---------------------------------------------------------------------------


def test_hl_cryomodules_are_looked_up_by_name(view):
    c = CavityCharController(view, Mock())
    hl_cavity, cm01_cavity = Mock(), Mock()
    c.machine = Mock()
    c.machine.cryomodules = {
        "H1": Mock(cavities={1: hl_cavity}),
        "01": Mock(cavities={1: cm01_cavity}),
    }
    assert c._get_machine_cavity("H1", 1) is hl_cavity
    assert c._get_machine_cavity("1", 1) is cm01_cavity
    assert c._get_machine_cavity("01", 1) is cm01_cavity


def test_a_failed_lookup_clears_the_cached_cavity(view, monkeypatch):
    """Otherwise Start Test drives the last cavity that did resolve."""
    c = CavityCharController(view, Mock())
    c._cavity = Mock(name="previous cavity")

    def boom(cm, cav):
        raise KeyError(cm)

    monkeypatch.setattr(c, "_get_machine_cavity", boom)
    monkeypatch.setattr(
        f"{MODULE}.resolve_cavity_selection", lambda v, cm, cav: ("H9", "1")
    )
    c.update_pv_addresses("H9", "1")
    assert c._cavity is None


# ---------------------------------------------------------------------------
# No record change during a run
# ---------------------------------------------------------------------------


class _Container(_RecordLifecycleMixin):
    def __init__(self, running: bool):
        display = Mock()
        display.is_running_phase.return_value = running
        self._phase_displays = [display]
        self.session = Mock()


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.start_new_record("01", "2"),
        lambda c: c.load_record(9),
    ],
)
def test_the_record_cannot_change_during_a_run(call):
    container = _Container(running=True)
    with patch(
        "sc_linac_physics.applications.rf_commissioning.ui.container."
        "record_lifecycle.QMessageBox"
    ) as box:
        assert call(container) is False
    box.warning.assert_called_once()
    container.session.start_new_record.assert_not_called()
    container.session.load_record.assert_not_called()


def test_the_display_reports_a_run(qtbot, tmp_path):
    from sc_linac_physics.applications.rf_commissioning.session_manager import (  # noqa: E501
        CommissioningSession,
    )
    from sc_linac_physics.applications.rf_commissioning.ui.displays.cavity_char import (  # noqa: E501
        CavityCharDisplay,
    )

    with patch("PyQt5.QtCore.QTimer.singleShot"):
        d = CavityCharDisplay(
            session=CommissioningSession(db_path=str(tmp_path / "c.db"))
        )
        qtbot.addWidget(d)
    assert d.is_running_phase() is False
    d.controller._running = True
    assert d.is_running_phase() is True


# ---------------------------------------------------------------------------
# Abort between attempts
# ---------------------------------------------------------------------------


def test_abort_is_checked_before_every_attempt(view, monkeypatch):
    """A retry delay must not end in another write."""
    c = _controller(view)
    c.context.is_abort_requested.side_effect = [False, True]
    c.phase.execute_step.return_value = _result(PhaseResult.RETRY, "settling")
    monkeypatch.setattr(f"{MODULE}.time.sleep", lambda s: None)

    assert c._execute_single_step("set_drive_level") is False
    assert c.phase.execute_step.call_count == 1


def test_push_clears_a_stale_abort(view, monkeypatch):
    c = _controller(view)
    c.context.abort_requested = True
    c.phase.execute_step.return_value = _result(PhaseResult.SUCCESS)
    monkeypatch.setattr("threading.Thread", RunInline)
    c.on_push_results()
    assert c.context.abort_requested is False


# ---------------------------------------------------------------------------
# Persistence after a push
# ---------------------------------------------------------------------------


def test_a_failed_save_after_a_push_is_not_reported_as_complete(view):
    c = _controller(view)
    c.session.complete_active_phase_instance.return_value = False
    c.session.save_active_record.return_value = True
    c.session.add_measurement_to_history.return_value = True
    advanced = []
    c.phase_completed.connect(advanced.append)

    c._on_push_finished(True, "")

    assert advanced == []
    assert c._active_phase_instance_id == 42
    view.offer_save_retry.assert_called_once()
    message = view.show_error.call_args[0][0].lower()
    assert "pushed" in message and "not saved" in message


def test_retry_save_repeats_only_what_failed_and_writes_nothing(view):
    c = _controller(view)
    c.session.complete_active_phase_instance.return_value = False
    c.session.save_active_record.return_value = True
    c.session.add_measurement_to_history.return_value = True
    c._on_push_finished(True, "")

    c.session.complete_active_phase_instance.return_value = True
    advanced = []
    c.phase_completed.connect(advanced.append)
    c.on_push_results()

    c.phase.execute_step.assert_not_called()
    assert c.session.complete_active_phase_instance.call_count == 2
    assert c.session.save_active_record.call_count == 1
    assert c.session.add_measurement_to_history.call_count == 1
    assert advanced == [c.session.get_active_record.return_value]
    assert c._active_phase_instance_id is None


# ---------------------------------------------------------------------------
# Progress and elapsed
# ---------------------------------------------------------------------------


def test_progress_is_reported_for_each_step(view):
    c = _controller(view)
    c.phase.execute_step.return_value = _result(PhaseResult.SUCCESS)
    c._execute_single_step("read_results")
    c.context.progress_callback.assert_called_once_with(
        "read_results", int(6 / 9 * 100)
    )


def test_elapsed_runs_from_start_until_the_wait_settles(view, monkeypatch):
    c = _controller(view)
    c.context.abort_requested = False
    c.phase.execute_step.return_value = _result(PhaseResult.SUCCESS)
    monkeypatch.setattr("threading.Thread", RunInline)
    events = []
    c._char_started.connect(lambda: events.append("started"))
    c._char_settled.connect(lambda: events.append("settled"))
    c.phase.execute_step.side_effect = lambda step: (
        events.append(step) or _result(PhaseResult.SUCCESS)
    )

    c._run_phase_in_background()

    assert events.index("started") == events.index("start_characterization") + 1
    assert events.index("settled") == events.index("wait_for_completion") + 1


def test_elapsed_settles_when_the_run_fails_early(view, monkeypatch):
    c = _controller(view)
    monkeypatch.setattr("threading.Thread", RunInline)
    settled = []
    c._char_settled.connect(lambda: settled.append(1))
    c.phase.execute_step.return_value = _result(PhaseResult.FAILED, "no")
    c._run_phase_in_background()
    assert settled == [1]


def test_elapsed_timer_ticks_between_start_and_settle(view):
    c = _controller(view)
    emitted = []
    c.elapsed_updated.connect(emitted.append)
    c._on_char_started()
    assert c._elapsed_timer.isActive()
    c._tick_elapsed()
    c._on_char_settled()
    assert not c._elapsed_timer.isActive()
    assert len(emitted) == 1 and emitted[0] >= 0
