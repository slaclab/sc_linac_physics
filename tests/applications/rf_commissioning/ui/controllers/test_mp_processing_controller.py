"""Tests for MPProcessingController.

As in test_piezo_with_rf_controller.py, the bridge's start_segment is a
recorder, and each test hands _on_segment_finished the SegmentResult a
segment would end with. These check which steps run, with which limits and
context parameters, and what reaches the database.
"""

from datetime import datetime
from unittest.mock import Mock

import pytest

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningRecord,
    MPProcessingData,
)
from sc_linac_physics.applications.rf_commissioning.phases.phase_base import (
    PhaseResult,
    PhaseStepResult,
)
from sc_linac_physics.applications.rf_commissioning.phases.step_runner import (
    HOLD_STEP_MODE,
    SegmentOutcome,
    SegmentResult,
)
from sc_linac_physics.applications.rf_commissioning.ui.controllers import (
    mp_processing_controller as module,
)
from sc_linac_physics.applications.rf_commissioning.ui.controllers.mp_processing_controller import (  # noqa: E501
    CHECK_STEPS,
    RUN_STEPS,
    MPProcessingController,
    live_pv_addresses,
)

OLD = datetime(2026, 10, 20, 11, 52)
SETTINGS = {
    "start_amplitude_mv": 6.0,
    "step_mv": 0.1,
    "step_seconds": 20.0,
    "quench_hold_seconds": 45.0,
    "stable_seconds": 120.0,
}


@pytest.fixture
def cavity():
    c = Mock()
    c.claim.return_value = True
    c.abort_flag = False
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
    s.complete_active_phase_instance.return_value = True
    s.add_measurement_to_history.return_value = True
    return s


@pytest.fixture
def view():
    v = Mock()
    v.get_current_operator.return_value = "lisa"
    v.read_settings.return_value = dict(SETTINGS)
    v.read_fe_fields.return_value = {}
    return v


@pytest.fixture
def controller(view, session, cavity):
    c = MPProcessingController(view, session)
    c._cavity = cavity
    c.bridge.start_segment = Mock(return_value=True)
    return c


def started_steps(controller):
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


def run_to_the_end(controller, record):
    controller.on_start_test()
    controller._on_segment_finished(
        completed(verify_initial_state=check_data())
    )
    record.mp_processing = MPProcessingData(max_amplitude_reached=16.6)
    controller._on_segment_finished(completed(record_results=None))


def test_live_pvs_are_the_cavity_amplitude_and_rf_pvs(cavity):
    assert live_pv_addresses(cavity) == {
        "pydm_ades": cavity.ades_pv,
        "pydm_aact": cavity.aact_pv,
        "pydm_ades_max": cavity.ades_max_pv,
        "pydm_quench_latch": cavity.quench_latch_pv,
        "pydm_rf_mode": cavity.rf_mode_pv,
        "pydm_rf_state": cavity.rf_state_pv,
    }


def test_start_test_checks_first_with_the_settings_box_limits(controller):
    controller.on_start_test()
    steps, kwargs = started_steps(controller)
    assert steps == list(CHECK_STEPS) == ["verify_initial_state"]
    assert kwargs["then_complete"] is False
    limits = controller.phase.limits
    assert limits.start_amplitude_mv == 6.0
    assert limits.step_mv == 0.1
    assert limits.step_seconds == 20.0
    assert limits.quench_hold_seconds == 45.0
    assert limits.stable_seconds == 120.0


def test_start_test_needs_an_operator(controller, view):
    view.get_current_operator.return_value = None
    controller.on_start_test()
    view.show_error.assert_called_once()
    controller.bridge.start_segment.assert_not_called()


def test_another_tab_holding_the_cavity_stops_the_start(
    controller, cavity, view, session
):
    cavity.claim.return_value = False
    controller.on_start_test()
    controller.bridge.start_segment.assert_not_called()
    session.start_active_phase_instance.assert_not_called()
    view.show_error.assert_called_once()


def test_no_attempt_in_the_database_runs_nothing_and_frees_the_cavity(
    controller, cavity, session, view
):
    session.start_active_phase_instance.return_value = None
    controller.on_start_test()
    controller.bridge.start_segment.assert_not_called()
    assert "nothing was run" in view.show_error.call_args.args[0]
    cavity.release.assert_called_once()


def test_recent_results_go_straight_to_the_run(controller, view):
    controller.on_start_test()
    controller._on_segment_finished(
        completed(verify_initial_state=check_data())
    )
    view.ask_rerun.assert_not_called()
    steps, kwargs = started_steps(controller)
    assert steps == list(RUN_STEPS)
    assert steps == ["setup_rf", "process", "record_results"]
    assert kwargs["then_complete"] is True


def test_stale_answers_reach_setup_rf(controller, view):
    view.ask_rerun.side_effect = [False, True]
    controller.on_start_test()
    controller._on_segment_finished(
        completed(verify_initial_state=check_data(False, False))
    )
    assert controller.context.parameters["rerun_ssa_calibration"] is False
    assert controller.context.parameters["rerun_characterization"] is True
    assert started_steps(controller)[0] == list(RUN_STEPS)


def test_cancelling_a_stale_prompt_fails_before_setup_rf(
    controller, view, session
):
    view.ask_rerun.return_value = None
    controller.on_start_test()
    controller.bridge.start_segment.reset_mock()
    controller._on_segment_finished(
        completed(verify_initial_state=check_data(ssa_recent=False))
    )
    controller.bridge.start_segment.assert_not_called()
    session.fail_active_phase_instance.assert_called_once()
    view.on_phase_finished.assert_called_with("FAILED")


def test_a_finished_run_completes_saves_and_announces(
    controller, view, session, record, cavity
):
    announced = Mock()
    controller.phase_completed.connect(announced)
    run_to_the_end(controller, record)
    session.complete_active_phase_instance.assert_called_once()
    kwargs = session.complete_active_phase_instance.call_args.kwargs
    assert kwargs["phase_instance_id"] == 42
    assert kwargs["artifact_payload"]["max_amplitude_reached"] == 16.6
    session.add_measurement_to_history.assert_called_once()
    view.on_phase_finished.assert_called_with("COMPLETED")
    announced.assert_called_once_with(record)
    cavity.release.assert_called()
    assert controller.stage is None


def test_a_failed_save_offers_a_retry_that_writes_only_the_database(
    controller, view, session, record
):
    session.add_measurement_to_history.return_value = False
    run_to_the_end(controller, record)
    assert controller.stage == "unsaved"
    view.set_retry_save.assert_called_once()
    view.on_phase_finished.assert_not_called()

    controller.bridge.start_segment.reset_mock()
    session.add_measurement_to_history.return_value = True
    controller.on_start_test()  # the Retry save button
    controller.bridge.start_segment.assert_not_called()
    assert session.complete_active_phase_instance.call_count == 1
    assert session.add_measurement_to_history.call_count == 2
    view.on_phase_finished.assert_called_with("COMPLETED")


def test_a_failed_run_fails_the_instance_with_its_quenches(
    controller, session, record
):
    controller.on_start_test()
    controller._on_segment_finished(
        completed(verify_initial_state=check_data())
    )
    record.mp_processing = MPProcessingData()
    record.mp_processing.add_quench(amplitude=12.4)
    controller._on_segment_finished(
        SegmentResult(SegmentOutcome.FAILED, "Interlock reset failed")
    )
    kwargs = session.fail_active_phase_instance.call_args.kwargs
    assert kwargs["error_message"] == "Interlock reset failed"
    assert len(kwargs["artifact_payload"]["quench_events"]) == 1


def test_mp_data_is_this_runs_record(controller, record):
    assert controller.mp_data is None
    controller.on_start_test()
    record.mp_processing = MPProcessingData()
    assert controller.mp_data is record.mp_processing


def test_abort_goes_through_the_run(controller):
    controller.on_start_test()
    controller.run.request_abort = Mock()
    controller.bridge._busy = True
    controller.on_abort()
    controller.run.request_abort.assert_called_once()


def test_abort_with_nothing_running_does_nothing(controller):
    controller.on_abort()  # no run yet: no error


def test_step_label_counts_across_all_four_steps(controller, view):
    controller._on_step_started("process", 1, 3)
    view.set_step.assert_called_with("process (3 of 4)")
    view.on_step_started.assert_called_with("process")


def test_step_mode_hold_enables_next(controller, view):
    controller._on_holding("setup_rf", HOLD_STEP_MODE)
    view.set_next_enabled.assert_called_with(True)


def test_changing_cavity_forgets_an_unsaved_run(
    controller, view, session, record, cavity
):
    session.add_measurement_to_history.return_value = False
    run_to_the_end(controller, record)
    controller.forget_run()
    assert controller.stage is None
    assert controller.context is None
    view.clear_run.assert_called()


class _RunNow:
    """Stands in for threading.Thread: runs the target on start()."""

    def __init__(self, target, daemon=None):
        self.target = target

    def start(self):
        self.target()


def to_run_segment(controller):
    controller.on_start_test()
    controller._on_segment_finished(
        completed(verify_initial_state=check_data())
    )


def test_abort_between_steps_turns_rf_off_before_releasing(
    controller, cavity, view, session, monkeypatch
):
    monkeypatch.setattr(module.threading, "Thread", _RunNow)
    to_run_segment(controller)
    cavity.abort_flag = True  # set by the hook; no check_abort ran
    controller._on_segment_finished(
        SegmentResult(SegmentOutcome.ABORTED, "Aborted before process")
    )
    cavity.turn_off.assert_called_once()
    assert cavity.abort_flag is False
    cavity.release.assert_called()
    message = session.fail_active_phase_instance.call_args.kwargs[
        "error_message"
    ]
    assert message == "Aborted before process. RF is off."


def test_abort_inside_a_wait_does_not_turn_rf_off_again(
    controller, cavity, session
):
    to_run_segment(controller)
    # check_abort already turned RF off and cleared the flag.
    controller._on_segment_finished(
        SegmentResult(SegmentOutcome.ABORTED, "Aborted during process")
    )
    cavity.turn_off.assert_not_called()
    session.fail_active_phase_instance.assert_called_once()


def test_a_failed_turn_off_is_in_the_failure_message(
    controller, cavity, session, monkeypatch
):
    monkeypatch.setattr(module.threading, "Thread", _RunNow)
    cavity.turn_off.side_effect = RuntimeError("RF still on")
    to_run_segment(controller)
    cavity.abort_flag = True
    controller._on_segment_finished(
        SegmentResult(SegmentOutcome.ABORTED, "Aborted before process")
    )
    message = session.fail_active_phase_instance.call_args.kwargs[
        "error_message"
    ]
    assert "Turning RF off failed: RF still on" in message


def test_while_rf_turns_off_the_tab_counts_as_running(
    controller, cavity, monkeypatch
):
    held = []
    monkeypatch.setattr(
        module.threading,
        "Thread",
        lambda target, daemon=None: Mock(start=lambda: held.append(target)),
    )
    to_run_segment(controller)
    cavity.abort_flag = True
    controller._on_segment_finished(
        SegmentResult(SegmentOutcome.ABORTED, "Aborted before process")
    )
    assert controller.running
    controller.run.request_abort = Mock()
    controller.on_abort()
    controller.run.request_abort.assert_not_called()
    held[0]()  # the worker finishes
    assert not controller.running


def test_a_failed_check_keeps_the_last_run_off_the_new_attempt(
    controller, session, record
):
    old = MPProcessingData()
    old.add_quench(amplitude=14.0)
    record.mp_processing = old
    controller.on_start_test()
    controller._on_segment_finished(
        SegmentResult(SegmentOutcome.FAILED, "Cavity is not online")
    )
    kwargs = session.fail_active_phase_instance.call_args.kwargs
    assert kwargs["artifact_payload"] is None
    assert record.mp_processing is old


def test_a_failed_failure_write_is_kept_for_retry(controller, session, view):
    session.fail_active_phase_instance.return_value = False
    controller.on_start_test()
    controller._on_segment_finished(
        SegmentResult(SegmentOutcome.FAILED, "Interlock reset failed")
    )
    assert controller.stage == "unsaved_failure"
    assert controller._active_phase_instance_id == 42
    view.set_retry_save.assert_called_once()

    session.fail_active_phase_instance.return_value = True
    controller.bridge.start_segment.reset_mock()
    saves = session.save_active_record.call_count
    controller.on_start_test()  # Retry save
    controller.bridge.start_segment.assert_not_called()
    assert session.save_active_record.call_count == saves  # already saved
    assert session.fail_active_phase_instance.call_count == 2
    assert controller.stage is None
    assert controller._active_phase_instance_id is None


def start_the_run_segment(controller):
    controller.on_start_test()
    controller._on_segment_finished(
        completed(verify_initial_state=check_data())
    )
    controller.bridge._busy = True


def test_pause_and_resume_go_to_the_phase_during_the_run(controller):
    start_the_run_segment(controller)

    controller.on_pause()
    assert controller.pause_state == "pausing"
    # The worker hasn't paused yet: a second press does nothing.
    controller.on_pause()
    assert controller.pause_state == "pausing"
    controller.phase._paused = True  # the worker has stopped writing
    controller.on_pause()
    assert controller.pause_state == "resuming"


def test_pause_does_nothing_during_the_check_or_with_nothing_running(
    controller,
):
    controller.on_pause()  # no run yet: no error
    controller.on_start_test()
    controller.bridge._busy = True
    controller.on_pause()  # verify_initial_state: not the walk
    assert controller.pause_state == "running"


def test_a_finished_run_saves_the_field_emission_box(controller, view, record):
    view.read_fe_fields.return_value = {
        "field_emission_onset": 14.2,
        "fe_50_mr_h_amplitude": None,
    }
    run_to_the_end(controller, record)
    assert record.mp_processing.field_emission_onset == 14.2
    assert record.mp_processing.fe_50_mr_h_amplitude is None


def test_save_fe_writes_the_box_to_the_last_run(controller, view, session):
    record = session.get_active_record()
    record.mp_processing = MPProcessingData(max_amplitude_reached=16.6)
    view.read_fe_fields.return_value = {"fe_50_mr_h_amplitude": 15.1}
    controller.save_fe_fields()
    assert record.mp_processing.fe_50_mr_h_amplitude == 15.1
    session.save_active_record.assert_called_once()


def test_save_fe_needs_a_run_and_nothing_running(controller, view, session):
    controller.save_fe_fields()  # no MP run on the record
    view.show_error.assert_called_once()
    session.save_active_record.assert_not_called()

    session.get_active_record().mp_processing = MPProcessingData()
    controller.bridge._busy = True
    controller.save_fe_fields()
    assert view.show_error.call_count == 2
    session.save_active_record.assert_not_called()


def test_a_failed_run_keeps_the_field_emission_box(
    controller, view, session, record
):
    view.read_fe_fields.return_value = {"field_emission_onset": 13.1}
    controller.on_start_test()
    controller._on_segment_finished(
        completed(verify_initial_state=check_data())
    )
    record.mp_processing = MPProcessingData()
    controller._on_segment_finished(
        SegmentResult(SegmentOutcome.ABORTED, "Aborted — RF is off")
    )
    assert record.mp_processing.field_emission_onset == 13.1
    kwargs = session.fail_active_phase_instance.call_args.kwargs
    assert kwargs["artifact_payload"]["field_emission_onset"] == 13.1


def test_a_failed_check_leaves_the_last_runs_field_emission_alone(
    controller, view, record
):
    old = MPProcessingData(field_emission_onset=12.0)
    record.mp_processing = old
    view.read_fe_fields.return_value = {"field_emission_onset": 13.1}
    controller.on_start_test()
    controller._on_segment_finished(
        SegmentResult(SegmentOutcome.FAILED, "Cavity is not online")
    )
    assert old.field_emission_onset == 12.0


def test_retry_save_keeps_the_field_emission_values_of_the_first_try(
    controller, view, session, record
):
    view.read_fe_fields.return_value = {"field_emission_onset": 13.1}
    session.add_measurement_to_history.return_value = False
    run_to_the_end(controller, record)
    assert controller.stage == "unsaved"

    view.read_fe_fields.return_value = {"field_emission_onset": 99.0}
    session.add_measurement_to_history.return_value = True
    controller.on_start_test()  # Retry save
    assert record.mp_processing.field_emission_onset == 13.1
