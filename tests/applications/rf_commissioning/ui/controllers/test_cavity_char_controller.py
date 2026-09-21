"""Tests for the Cavity Characterization controller."""

from unittest.mock import Mock

import pytest

from sc_linac_physics.applications.rf_commissioning.phases.phase_base import (
    PhaseResult,
)
from sc_linac_physics.applications.rf_commissioning.ui.controllers.cavity_char_controller import (  # noqa: E501
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


def _step_result(outcome, message="ok", retry_delay=None):
    r = Mock()
    r.result = outcome
    r.message = message
    r.retry_delay_seconds = retry_delay
    return r


def test_steps_run_in_the_backend_order(controller, monkeypatch):
    phase = Mock()
    phase.get_phase_steps.return_value = BACKEND_STEPS
    controller.phase = phase
    controller.context = Mock()

    ran = []
    monkeypatch.setattr(
        controller, "_execute_single_step", lambda s: ran.append(s) or True
    )
    monkeypatch.setattr(controller, "_finalize_background_phase", lambda: None)
    monkeypatch.setattr("threading.Thread", RunInline)

    controller._run_phase_in_background()
    assert ran == BACKEND_STEPS


def test_a_failed_step_stops_the_run(controller, monkeypatch):
    phase = Mock()
    phase.get_phase_steps.return_value = ["a", "b", "c"]
    controller.phase = phase
    controller.context = Mock()

    ran = []

    def first_then_fail(step):
        ran.append(step)
        return step == "a"

    monkeypatch.setattr(controller, "_execute_single_step", first_then_fail)
    monkeypatch.setattr("threading.Thread", RunInline)

    finished = []
    controller.phase_run_finished.connect(
        lambda ok, msg: finished.append((ok, msg))
    )
    controller._run_phase_in_background()

    assert ran == ["a", "b"]
    assert finished and finished[0][0] is False
    assert "b" in finished[0][1]


def test_an_exception_in_the_worker_is_reported_not_swallowed(
    controller, monkeypatch
):
    phase = Mock()
    phase.get_phase_steps.side_effect = RuntimeError("boom")
    controller.phase = phase
    controller.context = Mock()
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
