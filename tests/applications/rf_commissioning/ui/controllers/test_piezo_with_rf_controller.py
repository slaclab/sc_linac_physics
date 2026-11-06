"""Tests for PiezoWithRFController.

The bridge's start_segment is replaced with a recorder, and each test hands
_on_segment_finished the SegmentResult a segment would end with. RunnerBridge
and PhaseRun have their own tests (#417); these check which steps run, in
which segment, with which context parameters.
"""

from datetime import datetime
from unittest.mock import Mock

import pytest

from sc_linac_physics.applications.rf_commissioning.models.commissioning_piezo import (  # noqa: E501
    CommissioningPiezo,
)
from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningRecord,
    PiezoWithRFTest,
)
from sc_linac_physics.applications.rf_commissioning.phases.phase_base import (
    PhaseResult,
    PhaseStepResult,
)
from sc_linac_physics.applications.rf_commissioning.phases.step_runner import (
    SegmentOutcome,
    SegmentResult,
)
from sc_linac_physics.applications.rf_commissioning.ui.controllers import (
    piezo_with_rf_controller as module,
)
from sc_linac_physics.applications.rf_commissioning.ui.controllers.piezo_with_rf_controller import (  # noqa: E501
    CHECK_STEPS,
    MEASURE_STEPS,
    PUSH_STEPS,
    PiezoWithRFController,
    live_pv_addresses,
)

OLD = datetime(2026, 10, 20, 11, 52)


@pytest.fixture
def cavity():
    c = Mock()
    c.piezo = Mock(spec=CommissioningPiezo)
    c.abort_flag = True  # left over from an earlier abort
    return c


@pytest.fixture
def record():
    return CommissioningRecord(linac=1, cryomodule="02", cavity_number=1)


@pytest.fixture
def session(record):
    s = Mock()
    s.can_run_phase.return_value = (True, "")
    s.get_active_record.return_value = record
    s.get_active_record_id.return_value = 7
    s.start_active_phase_instance.return_value = Mock(phase_instance_id=42)
    s.save_active_record.return_value = True
    return s


@pytest.fixture
def view():
    v = Mock()
    v.get_current_operator.return_value = "lisa"
    return v


@pytest.fixture
def controller(view, session, cavity):
    c = PiezoWithRFController(view, session)
    c._cavity = cavity
    c.bridge.start_segment = Mock(return_value=True)
    return c


def started_steps(controller):
    """(steps, kwargs) of the last start_segment call."""
    args, kwargs = controller.bridge.start_segment.call_args
    return list(args[1]), kwargs


def completed(**step_data):
    return SegmentResult(
        SegmentOutcome.COMPLETED,
        results={
            step: PhaseStepResult(
                result=PhaseResult.SUCCESS, message="", data=data
            )
            for step, data in step_data.items()
        },
    )


def check_data(ssa_recent=True, char_recent=True):
    return {
        "ssa_calibration_time": OLD,
        "ssa_calibration_good": True,
        "ssa_calibration_recent": ssa_recent,
        "characterization_time": OLD,
        "characterization_complete": True,
        "characterization_recent": char_recent,
    }


READ_DATA = {
    "amplifier_gain_a": 1.23,
    "amplifier_gain_b": 1.19,
    "detune_gain": 0.1 + 0.2,  # 0.30000000000000004: not what fmt shows
    "rf_test_status": "Warning",
}


def to_review(controller):
    controller.on_start_test()
    controller._on_segment_finished(
        completed(verify_initial_state=check_data())
    )
    controller._on_segment_finished(completed(read_results=READ_DATA))


# ----------------------------------------------------------------- start


def test_start_test_runs_only_verify_initial_state_first(controller):
    controller.on_start_test()
    steps, kwargs = started_steps(controller)
    assert steps == list(CHECK_STEPS) == ["verify_initial_state"]
    assert kwargs["then_complete"] is False


def test_start_test_needs_an_operator(controller, view):
    view.get_current_operator.return_value = None
    controller.on_start_test()
    view.show_error.assert_called_once()
    controller.bridge.start_segment.assert_not_called()


def test_start_test_runs_nothing_when_the_attempt_cannot_start(
    controller, session, view
):
    session.start_active_phase_instance.return_value = None
    controller.on_start_test()
    controller.bridge.start_segment.assert_not_called()
    assert "nothing was run" in view.show_error.call_args.args[0]
    assert controller.run is None


class _ThreadRecorder:
    """Stands in for threading.Thread: records the call, runs nothing."""

    made = []

    def __init__(self, target, args=(), daemon=None):
        self.target, self.args, self.daemon = target, args, daemon
        self.started = False
        _ThreadRecorder.made.append(self)

    def start(self):
        self.started = True


def test_abort_sets_the_flag_now_and_writes_the_status_pv_off_thread(
    controller, cavity, monkeypatch
):
    _ThreadRecorder.made = []
    monkeypatch.setattr(module.threading, "Thread", _ThreadRecorder)
    controller.on_start_test()
    controller.run.clear_abort()  # what RunnerBridge does before a segment
    assert cavity.abort_flag is False
    controller.bridge._busy = True  # a segment is running
    controller.on_abort()
    assert controller.context.abort_requested is True
    assert cavity.abort_flag is True
    cavity.request_abort.assert_not_called()
    cavity.set_status_message.assert_not_called()  # not on this thread
    (thread,) = _ThreadRecorder.made
    assert thread.started and thread.daemon
    assert thread.target is cavity.set_status_message
    assert thread.args[0] == "Abort requested"


# ------------------------------------------------------- stale prompts


def test_recent_results_ask_nothing_and_measure(controller, view):
    controller.on_start_test()
    controller._on_segment_finished(
        completed(verify_initial_state=check_data())
    )
    view.ask_rerun.assert_not_called()
    steps, kwargs = started_steps(controller)
    assert steps == list(MEASURE_STEPS)
    assert steps[-1] == "read_results"
    assert "push_detune_gain" not in steps
    assert kwargs["progress_offset"] == 1


def test_two_stale_results_ask_twice_in_a_row(controller, view):
    view.ask_rerun.side_effect = [True, False]
    controller.on_start_test()
    controller._on_segment_finished(
        completed(
            verify_initial_state=check_data(ssa_recent=False, char_recent=False)
        )
    )
    labels = [c.args[0] for c in view.ask_rerun.call_args_list]
    assert labels == ["SSA calibration", "characterization"]
    assert view.ask_rerun.call_args_list[0].args[1:] == ("CALTS", OLD, True)
    params = controller.context.parameters
    assert params["rerun_ssa_calibration"] is True
    assert params["rerun_characterization"] is False
    assert started_steps(controller)[0] == list(MEASURE_STEPS)


def test_cancelling_a_stale_prompt_fails_before_setup_rf(
    controller, view, session, record
):
    view.ask_rerun.return_value = None
    controller.on_start_test()
    controller.bridge.start_segment.reset_mock()
    controller._on_segment_finished(
        completed(verify_initial_state=check_data(ssa_recent=False))
    )
    controller.bridge.start_segment.assert_not_called()
    session.fail_active_phase_instance.assert_called_once()
    assert "nothing written" in view.show_error.call_args.args[0]


# ---------------------------------------------------------------- review


def test_measurement_is_saved_and_shown_but_not_completed(
    controller, view, session
):
    to_review(controller)
    assert controller.stage == "review"
    session.save_active_record.assert_called()
    session.complete_active_phase_instance.assert_not_called()
    view.show_review.assert_called_once_with(READ_DATA)


def test_push_confirms_the_exact_float_read_results_returned(controller):
    to_review(controller)
    controller.on_push()
    confirmed = controller.context.parameters["confirmed_detune_gain"]
    assert confirmed == 0.1 + 0.2
    assert confirmed != float(f"{0.1 + 0.2:.6f}")
    steps, kwargs = started_steps(controller)
    assert steps == list(PUSH_STEPS) == ["push_detune_gain", "record_results"]
    assert kwargs["then_complete"] is True


def test_push_before_review_does_nothing(controller):
    controller.on_start_test()
    controller.bridge.start_segment.reset_mock()
    controller.on_push()
    controller.bridge.start_segment.assert_not_called()


def test_decline_skips_the_push_and_completes(controller, record):
    to_review(controller)
    controller.on_decline_push("  gain looks wrong  ")
    steps, kwargs = started_steps(controller)
    assert steps == ["record_results"]
    assert kwargs["then_complete"] is True
    skip = record.phase_history[-1]
    assert skip.step_name == "push_detune_gain"
    assert skip.measurements["skipped_by"] == "lisa"
    assert skip.measurements["justification"] == "gain looks wrong"
    # phase_history is not saved, so the reason also goes in the notes.
    assert record.piezo_with_rf.notes == (
        "push_detune_gain skipped by lisa: gain looks wrong"
    )
    assert record.piezo_with_rf.detune_gain_pushed is False


def test_decline_without_a_justification_runs_nothing(controller, view):
    to_review(controller)
    controller.bridge.start_segment.reset_mock()
    controller.on_decline_push("   ")
    view.show_error.assert_called_once()
    controller.bridge.start_segment.assert_not_called()


def test_finish_completes_the_instance_and_announces_it(
    controller, session, view, record, qtbot
):
    to_review(controller)
    record.piezo_with_rf = PiezoWithRFTest(detune_gain=0.3)
    controller.on_push()
    with qtbot.waitSignal(controller.phase_completed):
        controller._on_segment_finished(completed(record_results={}))
    session.complete_active_phase_instance.assert_called_once()
    session.add_measurement_to_history.assert_called_once()
    view.on_phase_finished.assert_called_with("COMPLETED")
    assert controller.stage is None


def test_a_failed_save_keeps_the_instance_and_push_retries_only_the_save(
    controller, session, view, record, qtbot
):
    to_review(controller)
    record.piezo_with_rf = PiezoWithRFTest(detune_gain=0.3)
    controller.on_push()
    session.save_active_record.return_value = False
    session.complete_active_phase_instance.return_value = True
    session.add_measurement_to_history.return_value = False
    controller._on_segment_finished(completed(record_results={}))

    assert controller.stage == "unsaved"
    assert controller._active_phase_instance_id == 42
    assert controller._unsaved == {"save", "history"}
    view.on_phase_finished.assert_not_called()
    assert "writes nothing to the cavity" in view.show_error.call_args.args[0]
    view.set_review_enabled.assert_called_with(True)

    controller.bridge.start_segment.reset_mock()
    session.save_active_record.return_value = True
    session.add_measurement_to_history.return_value = True
    with qtbot.waitSignal(controller.phase_completed):
        controller.on_push()
    controller.bridge.start_segment.assert_not_called()  # no second push
    session.complete_active_phase_instance.assert_called_once()
    assert session.add_measurement_to_history.call_count == 2
    view.on_phase_finished.assert_called_with("COMPLETED")
    assert controller.stage is None
    assert controller._active_phase_instance_id is None


def test_a_failed_segment_fails_the_instance(controller, session, view):
    controller.on_start_test()
    controller._on_segment_finished(
        SegmentResult(SegmentOutcome.ABORTED, "Aborted", "setup_rf")
    )
    session.fail_active_phase_instance.assert_called_once()
    view.on_phase_finished.assert_called_with("FAILED")
    view.show_error.assert_called_once_with("Aborted")


def test_a_second_test_after_review_reuses_the_open_instance(
    controller, session
):
    to_review(controller)
    controller.on_start_test()
    session.start_active_phase_instance.assert_called_once()


# ------------------------------------------------------------------- PVs


def test_live_pv_addresses(cavity):
    piezo = cavity.piezo
    piezo.withrf_check_status_pv = "RFTESTSTS"
    piezo.withrf_status_pv = "RFTESTSTAT"
    piezo.amplifiergain_a_pv = "CHA_AMPGAIN"
    piezo.amplifiergain_b_pv = "CHB_AMPGAIN"
    piezo.detunegain_new_pv = "DFGAIN_NEW"
    piezo.pv_addr = lambda suffix: suffix
    cavity.rf_state_pv = "RFSTATE"
    assert live_pv_addresses(cavity) == {
        "pydm_test_run": "RFTESTSTS",
        "pydm_test_status": "RFTESTSTAT",
        "pydm_gain_a": "CHA_AMPGAIN",
        "pydm_gain_b": "CHB_AMPGAIN",
        "pydm_dfgain_new": "DFGAIN_NEW",
        "pydm_dfgain_current": "DFGAIN",
        "pydm_rf_state": "RFSTATE",
    }


def test_changing_cavity_drops_an_unpushed_review(
    controller, view, monkeypatch
):
    to_review(controller)
    other = Mock()
    other.piezo = Mock(spec=CommissioningPiezo)
    monkeypatch.setattr(controller, "_get_machine_cavity", lambda cm, c: other)
    monkeypatch.setattr(module, "apply_pv_mapping", lambda mapping: None)
    controller.update_pv_addresses("03", "2")
    assert controller.review_data is None
    assert controller.stage is None
    view.clear_review.assert_called()


# --------------------------------------------------- pause and step mode


def test_pause_toggles_the_run(controller, view):
    controller.on_start_test()
    controller.bridge._busy = True
    controller.on_pause_test()
    assert controller.run.paused
    view.set_paused.assert_called_with(True)
    controller.on_pause_test()
    assert not controller.run.paused
    view.set_paused.assert_called_with(False)


def test_step_mode_is_copied_onto_the_next_run(controller, view):
    controller.on_toggle_step_mode()
    controller.on_start_test()
    assert controller.run.step_mode
    controller._on_holding("verify_initial_state", "step_mode")
    view.set_next_enabled.assert_called_with(True)
    controller.on_next_step()
    view.set_next_enabled.assert_called_with(False)
    controller.on_toggle_step_mode()
    assert not controller.run.step_mode


def test_step_mode_does_not_hold_between_start_test_and_the_wait(
    controller, view
):
    controller.on_toggle_step_mode()
    controller.on_start_test()
    controller._on_step_started("start_test", 3, 6)
    assert controller.run._step_permits == 1  # wait_for_completion's Next
    view.set_next_enabled.reset_mock()
    controller._on_holding("wait_for_completion", "step_mode")
    view.set_next_enabled.assert_not_called()


def test_start_test_gives_no_extra_next_outside_step_mode(controller):
    controller.on_start_test()
    controller._on_step_started("start_test", 3, 6)
    assert controller.run._step_permits == 0


def test_step_label_counts_across_all_nine_steps(controller, view):
    controller._on_step_started("read_results", 5, 6)
    view.set_step.assert_called_with("read_results (7 of 9)")


def test_abort_with_nothing_running_does_nothing(controller, cavity):
    controller.on_start_test()
    controller.on_abort()
    cavity.request_abort.assert_not_called()
