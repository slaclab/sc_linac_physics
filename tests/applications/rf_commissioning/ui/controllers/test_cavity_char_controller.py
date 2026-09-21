"""Tests for the Cavity Characterization controller."""

import pathlib
from unittest.mock import Mock, patch

import pytest

from sc_linac_physics.applications.rf_commissioning.phases.phase_base import (
    PhaseResult,
)
from sc_linac_physics.applications.rf_commissioning.ui.controllers.cavity_char_controller import (  # noqa: E501
    MAX_STEP_ATTEMPTS,
    MEASURE_STEPS,
    CavityCharController,
)


class RunInline:
    """Stand-in for threading.Thread that runs the target synchronously.

    The controller starts a daemon thread; a test that waits on a real one is
    a test that can hang CI.
    """

    def __init__(self, target=None, daemon=None, **kwargs):
        self._target = target

    def start(self):
        self._target()


@pytest.fixture
def view():
    v = Mock()
    v.drive_level_spinbox.value.return_value = 10.0
    return v


@pytest.fixture
def controller(view):
    return CavityCharController(view, Mock())


# ---------------------------------------------------------------------------
# Drive level
# ---------------------------------------------------------------------------


def test_drive_level_read_from_the_spinbox(controller):
    assert controller._get_drive_level() == 10.0


def test_drive_level_above_the_limit_is_rejected(controller, view):
    view.drive_level_spinbox.value.return_value = 15.1
    assert controller._get_drive_level() is None
    view.show_error.assert_called_once()


def test_drive_level_at_the_limit_is_accepted(controller, view):
    view.drive_level_spinbox.value.return_value = 15.0
    assert controller._get_drive_level() == 15.0


def test_drive_level_of_zero_is_rejected(controller, view):
    view.drive_level_spinbox.value.return_value = 0.0
    assert controller._get_drive_level() is None


# ---------------------------------------------------------------------------
# Abort
# ---------------------------------------------------------------------------


def test_abort_sets_the_flag_and_writes_no_pv(controller):
    cavity = Mock()
    controller._cavity = cavity
    controller.on_abort()
    cavity.request_abort.assert_called_once()
    cavity.start_characterization.assert_not_called()


def test_abort_says_it_only_stops_waiting(controller, view):
    """There is no characterization abort PV — see the spec.

    An operator told "aborted" who believes the measurement stopped will
    misread the cavity's state, so the copy has to be explicit.
    """
    controller._cavity = Mock()
    controller.on_abort()
    message = view.log_message.call_args[0][0].lower()
    assert "stops waiting" in message or "stops the wait" in message
    assert "continues" in message


def test_abort_with_no_cavity_selected_does_not_raise(controller):
    controller._cavity = None
    controller.on_abort()


# ---------------------------------------------------------------------------
# Threaded execution
# ---------------------------------------------------------------------------

BACKEND_STEPS = [
    "verify_initial_state",
    "set_drive_level",
    "start_characterization",
    "wait_for_completion",
    "read_results",
    "push_results",
    "record_results",
]


def _step_result(outcome, message="ok", retry_delay=None, data=None):
    r = Mock()
    r.result = outcome
    r.message = message
    r.retry_delay_seconds = retry_delay
    # A real mapping: _create_step_checkpoint does dict(result.data or {}),
    # and dict(Mock()) raises.
    r.data = data
    return r


def test_measure_steps_run_in_order(controller, monkeypatch):
    phase = Mock()
    phase.get_phase_steps.return_value = BACKEND_STEPS
    controller.phase = phase
    controller.context = Mock()
    controller.context.is_abort_requested.return_value = False

    ran = []
    monkeypatch.setattr(
        controller, "_execute_single_step", lambda s: ran.append(s) or True
    )
    monkeypatch.setattr(controller, "_finish_measurement", lambda: None)
    monkeypatch.setattr("threading.Thread", RunInline)

    controller._run_phase_in_background()
    assert ran == list(MEASURE_STEPS)


def test_a_failed_step_stops_the_run(controller, monkeypatch):
    controller.phase = Mock()
    controller.context = Mock()
    controller.context.is_abort_requested.return_value = False

    ran = []

    def fail_at_start_characterization(step):
        ran.append(step)
        return step != "start_characterization"

    monkeypatch.setattr(
        controller, "_execute_single_step", fail_at_start_characterization
    )
    monkeypatch.setattr("threading.Thread", RunInline)

    finished = []
    controller.phase_run_finished.connect(
        lambda ok, msg: finished.append((ok, msg))
    )
    controller._run_phase_in_background()

    assert ran == [
        "verify_initial_state",
        "set_drive_level",
        "start_characterization",
    ]
    assert "wait_for_completion" not in ran
    assert finished and finished[0][0] is False
    assert "start_characterization" in finished[0][1]


def test_an_exception_in_the_worker_is_reported_not_swallowed(
    controller, monkeypatch
):
    phase = Mock()
    phase._mark_phase_started.side_effect = RuntimeError("boom")
    controller.phase = phase
    controller.context = Mock()
    controller.context.is_abort_requested.return_value = False
    monkeypatch.setattr("threading.Thread", RunInline)

    finished = []
    controller.phase_run_finished.connect(
        lambda ok, msg: finished.append((ok, msg))
    )
    controller._run_phase_in_background()

    assert finished == [(False, "boom")]


def test_retry_is_not_a_failure(controller, monkeypatch):
    """_read_results returns RETRY while the values are still settling."""
    phase = Mock()
    phase.execute_step.side_effect = [
        _step_result(PhaseResult.RETRY, "settling", retry_delay=0),
        _step_result(PhaseResult.SUCCESS, "read ok"),
    ]
    controller.phase = phase
    monkeypatch.setattr(
        "sc_linac_physics.applications.rf_commissioning.ui.controllers."
        "cavity_char_controller.time.sleep",
        lambda _: None,
    )

    assert controller._execute_single_step("read_results") is True
    assert phase.execute_step.call_count == 2


# ---------------------------------------------------------------------------
# Task 3b: a crash and a timeout must not read the same
# ---------------------------------------------------------------------------


def test_crash_and_timeout_produce_different_status_text(controller, view):
    """Both arrive as FAILED. Collapsing them hides an IOC fault.

    The backend's messages are "Characterization crashed -- check the
    cavity's PROBECALSTS and the RF interlocks" and "Characterization did
    not finish within 300 s".
    """
    phase = Mock()
    controller.phase = phase

    phase.execute_step.return_value = _step_result(
        PhaseResult.FAILED,
        "Characterization crashed — check the cavity's PROBECALSTS and "
        "the RF interlocks",
    )
    assert controller._execute_single_step("wait_for_completion") is False
    crashed_status = view.set_char_status.call_args[0][0]

    phase.execute_step.return_value = _step_result(
        PhaseResult.FAILED, "Characterization did not finish within 300 s"
    )
    assert controller._execute_single_step("wait_for_completion") is False
    timeout_status = view.set_char_status.call_args[0][0]

    assert crashed_status != timeout_status
    assert "crashed" in crashed_status
    assert "did not finish" in timeout_status


# ---------------------------------------------------------------------------
# The path to a machine write
#
# on_run_characterization is what eventually puts SEL_ASET and PROBECALSTRT,
# so each guard that stops short of it gets its own test.
# ---------------------------------------------------------------------------


def _session_ready():
    s = Mock()
    s.can_run_phase.return_value = (True, "ok")
    s.get_active_record_id.return_value = 7
    s.start_active_phase_instance.return_value = Mock(phase_instance_id=42)
    return s


def test_run_stops_on_a_bad_drive_level(view, monkeypatch):
    view.drive_level_spinbox.value.return_value = 99.0
    c = CavityCharController(view, _session_ready())
    c._cavity = Mock()
    called = []
    monkeypatch.setattr(
        c, "_prepare_phase_context", lambda *a: called.append(1) or True
    )
    c.on_run_characterization()
    assert called == []


def test_run_stops_with_no_operator(view, monkeypatch):
    view.get_current_operator.return_value = None
    c = CavityCharController(view, _session_ready())
    c._cavity = Mock()
    called = []
    monkeypatch.setattr(
        c, "_prepare_phase_context", lambda *a: called.append(1) or True
    )
    c.on_run_characterization()
    assert called == []
    view.show_error.assert_called_once()


def test_run_stops_with_no_cavity_selected(view, monkeypatch):
    view.get_current_operator.return_value = "lisa"
    c = CavityCharController(view, _session_ready())
    c._cavity = None
    called = []
    monkeypatch.setattr(
        c, "_prepare_phase_context", lambda *a: called.append(1) or True
    )
    c.on_run_characterization()
    assert called == []


def test_run_reaches_execution_when_every_guard_passes(view, monkeypatch):
    view.get_current_operator.return_value = "lisa"
    c = CavityCharController(view, _session_ready())
    c._cavity = Mock()
    monkeypatch.setattr(c, "_prepare_phase_context", lambda *a: True)
    started = []
    monkeypatch.setattr(c, "_execute_phase_async", lambda: started.append(1))
    c.on_run_characterization()
    assert started == [1]


def test_drive_level_is_passed_into_the_phase_context(view, monkeypatch):
    view.drive_level_spinbox.value.return_value = 12.5
    view.get_current_operator.return_value = "lisa"
    c = CavityCharController(view, _session_ready())
    cavity = Mock()
    c._cavity = cavity

    monkeypatch.setattr(
        "sc_linac_physics.applications.rf_commissioning.ui.controllers."
        "cavity_char_controller.CavityCharPhase",
        Mock(return_value=Mock(validate_prerequisites=lambda: (True, "ok"))),
    )
    assert c._prepare_phase_context(cavity, "lisa", 12.5) is True
    assert c.context.parameters["drive_level"] == 12.5
    assert c.context.parameters["cavity"] is cavity


def test_context_prep_stops_when_the_workflow_refuses(view):
    session = _session_ready()
    session.can_run_phase.return_value = (False, "SSA_CHAR not complete")
    c = CavityCharController(view, session)
    assert c._prepare_phase_context(Mock(), "lisa", 10.0) is False
    assert "SSA_CHAR not complete" in view.show_error.call_args[0][0]


def test_context_prep_stops_when_prerequisites_fail(view, monkeypatch):
    c = CavityCharController(view, _session_ready())
    monkeypatch.setattr(
        "sc_linac_physics.applications.rf_commissioning.ui.controllers."
        "cavity_char_controller.CavityCharPhase",
        Mock(
            return_value=Mock(
                validate_prerequisites=lambda: (False, "no SSA object")
            )
        ),
    )
    assert c._prepare_phase_context(Mock(), "lisa", 10.0) is False
    assert "no SSA object" in view.show_error.call_args[0][0]


# ---------------------------------------------------------------------------
# The Q window the panel renders against
# ---------------------------------------------------------------------------


def test_update_pv_addresses_publishes_the_cavitys_own_q_window(
    view, monkeypatch
):
    """HE, harmonic-linearizer and standard cavities have different windows."""
    c = CavityCharController(view, Mock())
    cavity = Mock()
    cavity.loaded_q_lower_limit = 3.0e7
    cavity.loaded_q_upper_limit = 7.0e7
    monkeypatch.setattr(c, "_get_machine_cavity", lambda cm, cav: cavity)
    monkeypatch.setattr(
        "sc_linac_physics.applications.rf_commissioning.ui.controllers."
        "cavity_char_controller.resolve_cavity_selection",
        lambda v, cm, cav: ("37", "1"),
    )
    c.update_pv_addresses("37", "1")
    assert c._cavity is cavity
    assert view.cavity_loaded_q_window == (3.0e7, 7.0e7)


def test_update_pv_addresses_with_no_selection_is_a_noop(view, monkeypatch):
    c = CavityCharController(view, Mock())
    monkeypatch.setattr(
        "sc_linac_physics.applications.rf_commissioning.ui.controllers."
        "cavity_char_controller.resolve_cavity_selection",
        lambda v, cm, cav: (None, None),
    )
    c.update_pv_addresses()
    assert c._cavity is None


def test_a_broken_cavity_lookup_is_logged_not_raised(view, monkeypatch):
    c = CavityCharController(view, Mock())
    monkeypatch.setattr(
        "sc_linac_physics.applications.rf_commissioning.ui.controllers."
        "cavity_char_controller.resolve_cavity_selection",
        lambda v, cm, cav: ("01", "1"),
    )
    monkeypatch.setattr(
        c, "_get_machine_cavity", Mock(side_effect=KeyError("no such CM"))
    )
    c.update_pv_addresses("01", "1")
    assert "Error setting PVs" in view.log_message.call_args[0][0]


# ---------------------------------------------------------------------------
# Elapsed time
# ---------------------------------------------------------------------------


def test_elapsed_is_emitted_while_running_then_stops(controller, monkeypatch):
    cavity = Mock()
    cavity.characterization_running = True

    emitted = []
    controller.elapsed_updated.connect(emitted.append)
    controller._cavity = cavity

    def stop_after_two(_):
        if len(emitted) >= 2:
            cavity.characterization_running = False

    monkeypatch.setattr(
        "sc_linac_physics.applications.rf_commissioning.ui.controllers."
        "cavity_char_controller.time.sleep",
        stop_after_two,
    )
    controller._emit_elapsed_until_done(0.0)
    assert len(emitted) == 2


# ---------------------------------------------------------------------------
# Start Test must not push
#
# CavityCharPhase.get_phase_steps() ends with push_results, which puts
# PUSH_QLOADED.PROC and PUSH_CAV_SCALE.PROC. Running the list whole would
# commit the measurement to the cavity with no operator review, which is the
# thing the backend's read/push split exists to prevent.
# ---------------------------------------------------------------------------


def test_start_test_stops_after_reading_and_never_pushes(
    controller, monkeypatch
):
    phase = Mock()
    phase.get_phase_steps.return_value = BACKEND_STEPS
    controller.phase = phase
    controller.context = Mock()
    controller.context.is_abort_requested.return_value = False

    ran = []
    monkeypatch.setattr(
        controller, "_execute_single_step", lambda s: ran.append(s) or True
    )
    monkeypatch.setattr("threading.Thread", RunInline)

    controller._run_phase_in_background()

    assert "push_results" not in ran
    assert "record_results" not in ran
    assert ran[-1] == "read_results"


def test_start_test_does_not_advance_the_phase(controller, monkeypatch):
    """Completion belongs after the push, not after the measurement."""
    phase = Mock()
    phase.get_phase_steps.return_value = BACKEND_STEPS
    controller.phase = phase
    controller.context = Mock()
    controller.context.is_abort_requested.return_value = False

    monkeypatch.setattr(controller, "_execute_single_step", lambda s: True)
    monkeypatch.setattr("threading.Thread", RunInline)

    advanced = []
    controller.phase_completed.connect(advanced.append)
    controller._run_phase_in_background()

    assert advanced == []
    phase.finalize_phase.assert_not_called()


def test_measure_steps_are_the_backends_leading_steps():
    """MEASURE_STEPS is a hand-copied slice, so pin it to the source.

    If CavityCharPhase reorders its steps or inserts one before
    read_results, Start Test would silently run the wrong sequence — or, if
    push_results moved earlier, push without review.
    """
    from sc_linac_physics.applications.rf_commissioning.phases.cavity_char import (  # noqa: E501
        CavityCharPhase,
    )

    backend = CavityCharPhase.get_phase_steps(None)
    assert list(MEASURE_STEPS) == backend[: len(MEASURE_STEPS)]
    assert "push_results" in backend
    assert "push_results" not in MEASURE_STEPS


# ---------------------------------------------------------------------------
# What the worker thread is allowed to touch
#
# RunInline runs the worker on the main thread, which is exactly the
# condition that hides a Qt threading violation. These tests pin the
# marshalling instead of the timing.
# ---------------------------------------------------------------------------


def test_log_and_status_are_marshalled_through_signals(view):
    """Widgets must not be touched from the worker thread.

    _execute_single_step runs on a daemon thread. Calling view.log_message()
    or view.set_char_status() from there mutates Qt widgets off the GUI
    thread. ssa_char_controller routes the same updates through
    _log_signal; this controller does the same.
    """
    c = CavityCharController(view, Mock())
    assert hasattr(c, "_log_signal")
    assert hasattr(c, "_status_signal")

    src = pathlib.Path(
        "src/sc_linac_physics/applications/rf_commissioning/ui/"
        "controllers/cavity_char_controller.py"
    ).read_text()
    worker_region = src[src.index("def _execute_single_step") :]
    worker_region = worker_region[
        : worker_region.index("def _finish_measurement")
    ]
    assert "self.view.log_message" not in worker_region
    assert "self.view.set_char_status" not in worker_region


def test_each_step_lands_a_checkpoint_on_the_record(controller):
    """The commissioning record is where a run is visible afterwards."""
    record = Mock()
    record.phase_history = []
    controller.context = Mock(
        record=record, operator="lisa", phase_instance_id=3
    )
    controller.context.is_abort_requested.return_value = False
    phase = Mock()
    phase.phase_type = "cavity_char"
    phase.execute_step.return_value = _step_result(
        PhaseResult.SUCCESS, "Loaded Q 4.100e+07"
    )
    controller.phase = phase

    controller._execute_single_step("read_results")

    assert len(record.phase_history) == 1
    cp = record.phase_history[0]
    assert cp.step_name == "read_results"
    assert cp.success is True
    assert "4.100e+07" in cp.notes
    assert cp.operator == "lisa"


def test_a_failed_step_is_checkpointed_too(controller):
    record = Mock()
    record.phase_history = []
    controller.context = Mock(
        record=record, operator="lisa", phase_instance_id=None
    )
    controller.context.is_abort_requested.return_value = False
    phase = Mock()
    phase.phase_type = "cavity_char"
    phase.execute_step.return_value = _step_result(
        PhaseResult.FAILED, "Characterization did not finish within 300 s"
    )
    controller.phase = phase

    controller._execute_single_step("wait_for_completion")

    assert len(record.phase_history) == 1
    assert record.phase_history[0].success is False


def test_abort_between_steps_stops_the_run(controller, monkeypatch):
    """on_abort only reaches _wait_for_completion's check_abort.

    Between steps the loop has to look at the context itself, or Abort does
    nothing until the next long wait.
    """
    controller.phase = Mock()
    controller.context = Mock()
    controller.context.is_abort_requested.return_value = True

    ran = []
    monkeypatch.setattr(
        controller, "_execute_single_step", lambda s: ran.append(s) or True
    )
    monkeypatch.setattr("threading.Thread", RunInline)
    controller._run_phase_in_background()

    assert ran == []


def test_progress_callback_is_wired_so_the_bar_moves(controller):
    controller.phase = Mock()
    controller.phase.get_phase_steps.return_value = BACKEND_STEPS
    controller.context = Mock()
    controller.context.progress_callback = None
    with patch("PyQt5.QtCore.QTimer.singleShot"):
        controller._execute_phase_async()
    assert controller.context.progress_callback is not None


def test_retry_gives_up_instead_of_looping_forever(controller, monkeypatch):
    """_verify_initial_state returns RETRY on any cavity read exception.

    An uncapped retry loop spins every 3 s forever: no failure, no progress,
    and nothing reaches the machine. ssa_char_controller caps at 3 tries.
    """
    record = Mock()
    record.phase_history = []
    controller.context = Mock(
        record=record, operator="lisa", phase_instance_id=None
    )
    controller.context.is_abort_requested.return_value = False
    phase = Mock()
    phase.phase_type = "cavity_char"
    phase.execute_step.return_value = _step_result(
        PhaseResult.RETRY, "Could not read cavity state: boom", retry_delay=0
    )
    controller.phase = phase
    monkeypatch.setattr(
        "sc_linac_physics.applications.rf_commissioning.ui.controllers."
        "cavity_char_controller.time.sleep",
        lambda _: None,
    )

    assert controller._execute_single_step("verify_initial_state") is False
    assert phase.execute_step.call_count == MAX_STEP_ATTEMPTS
