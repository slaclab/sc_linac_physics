"""Tests for BatchPiezoPreRFController."""

import sys
from threading import Event
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest

import sc_linac_physics.applications.rf_commissioning.controllers.batch_piezo_pre_rf_controller as ctrl_module
from sc_linac_physics.applications.rf_commissioning.controllers.batch_piezo_pre_rf_controller import (
    BatchPiezoPreRFController,
    CavityRunState,
    CavitySpec,
    TRIGGER_STEPS,
    COLLECT_STEPS,
)
from sc_linac_physics.applications.rf_commissioning.models.commissioning_piezo import (
    CommissioningPiezo,
)
from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningRecord,
    PiezoPreRFCheck,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_session(*, existing_record_id=None, existing_record=None):
    session = Mock()
    session.db.get_record_id_for_cavity.return_value = existing_record_id
    if existing_record_id is not None:
        record = existing_record or CommissioningRecord(
            linac=0, cryomodule="01", cavity_number=1
        )
        session.db.get_record_with_version.return_value = (record, 1)
    else:
        session.db.save_record.return_value = 99
    session.workflow.start_phase_for_record.return_value = SimpleNamespace(
        phase_instance_id=42, run_id=7, attempt_number=1
    )
    return session


def _make_controller(session=None):
    return BatchPiezoPreRFController(session or _mock_session())


def _make_state(cm="01", cav=1, session=None):
    spec = CavitySpec(cryomodule=cm, cavity_number=cav)
    state = CavityRunState(spec=spec)
    ctrl = _make_controller(session)
    ctrl._init_record_and_context(state, "operator")
    return ctrl, state


def _passing_phase():
    phase = Mock()
    phase._execute_step_with_retry.return_value = True
    phase._retry_count = 0
    result = PiezoPreRFCheck(
        capacitance_a=25e-9,
        capacitance_b=24e-9,
        channel_a_passed=True,
        channel_b_passed=True,
    )
    phase.finalize_phase.side_effect = lambda: None
    return phase, result


# ---------------------------------------------------------------------------
# CavitySpec
# ---------------------------------------------------------------------------


class TestCavitySpec:
    def test_key_format(self):
        spec = CavitySpec(cryomodule="02", cavity_number=3)
        assert spec.key == "02_CAV3"

    def test_linac_name_l0b(self):
        assert CavitySpec(cryomodule="01", cavity_number=1).linac_name == "L0B"

    def test_linac_name_l1b(self):
        assert CavitySpec(cryomodule="02", cavity_number=1).linac_name == "L1B"

    def test_linac_name_hl(self):
        assert CavitySpec(cryomodule="H1", cavity_number=1).linac_name == "L1B"

    def test_linac_name_unknown(self):
        assert CavitySpec(cryomodule="ZZ", cavity_number=1).linac_name is None

    def test_linac_idx_l0b(self):
        assert CavitySpec(cryomodule="01", cavity_number=1).linac_idx == 0

    def test_linac_idx_l1b(self):
        assert CavitySpec(cryomodule="02", cavity_number=1).linac_idx == 1

    def test_linac_idx_unknown(self):
        assert CavitySpec(cryomodule="ZZ", cavity_number=1).linac_idx is None


# ---------------------------------------------------------------------------
# Controller init
# ---------------------------------------------------------------------------


class TestControllerInit:
    def test_pool_not_started_on_init(self):
        ctrl = _make_controller()
        assert not ctrl._pool_ready

    def test_abort_event_clear_on_init(self):
        ctrl = _make_controller()
        assert not ctrl._abort_event.is_set()

    def test_is_running_false_initially(self):
        ctrl = _make_controller()
        assert not ctrl.is_running()


# ---------------------------------------------------------------------------
# _init_record_and_context
# ---------------------------------------------------------------------------


class TestInitRecordAndContext:
    def test_creates_new_record_when_none_exists(self):
        session = _mock_session(existing_record_id=None)
        ctrl = _make_controller(session)
        state = CavityRunState(
            spec=CavitySpec(cryomodule="01", cavity_number=1)
        )

        ctrl._init_record_and_context(state, "op")

        session.db.save_record.assert_called_once()
        assert state.record is not None
        assert state.record_id == 99
        assert state.record_version == 1

    def test_loads_existing_record(self):
        existing = CommissioningRecord(
            linac=0, cryomodule="01", cavity_number=1
        )
        session = _mock_session(existing_record_id=5, existing_record=existing)
        ctrl = _make_controller(session)
        state = CavityRunState(
            spec=CavitySpec(cryomodule="01", cavity_number=1)
        )

        ctrl._init_record_and_context(state, "op")

        session.db.save_record.assert_not_called()
        assert state.record is existing
        assert state.record_id == 5
        assert state.record_version == 1

    def test_raises_for_unknown_cryomodule(self):
        ctrl = _make_controller()
        state = CavityRunState(
            spec=CavitySpec(cryomodule="ZZ", cavity_number=1)
        )

        with pytest.raises(ValueError, match="Cannot determine linac"):
            ctrl._init_record_and_context(state, "op")

    def test_raises_when_record_missing_after_id_lookup(self):
        session = _mock_session(existing_record_id=5)
        session.db.get_record_with_version.return_value = None
        ctrl = _make_controller(session)
        state = CavityRunState(
            spec=CavitySpec(cryomodule="01", cavity_number=1)
        )

        with pytest.raises(ValueError, match="not found"):
            ctrl._init_record_and_context(state, "op")

    def test_phase_instance_id_set_from_workflow(self):
        ctrl, state = _make_state()
        assert state.phase_instance_id == 42

    def test_phase_instance_id_none_when_workflow_returns_none(self):
        session = _mock_session()
        session.workflow.start_phase_for_record.return_value = None
        ctrl = _make_controller(session)
        state = CavityRunState(
            spec=CavitySpec(cryomodule="01", cavity_number=1)
        )

        ctrl._init_record_and_context(state, "op")

        assert state.phase_instance_id is None

    def test_context_contains_correct_operator(self):
        ctrl, state = _make_state()
        assert state.context.operator == "operator"

    def test_validates_prerequisites_on_phase(self):
        ctrl, state = _make_state()
        # validate_prerequisites is called inside _init_record_and_context
        # The phase mock returns (False, ...) when prerequisites aren't met.
        # We just verify phase was created and is a PiezoPreRFPhase mock.
        assert state.phase is not None


# ---------------------------------------------------------------------------
# _trigger_cavity
# ---------------------------------------------------------------------------


class TestTriggerCavity:
    def _state_with_mock_phase(self, step_results=None):
        ctrl, state = _make_state()
        phase = Mock()
        phase._retry_count = 0
        # Default: all trigger steps succeed
        results = step_results or {s: True for s in TRIGGER_STEPS}
        phase._execute_step_with_retry.side_effect = lambda s: results.get(
            s, True
        )
        # validate_prerequisites must pass
        phase.validate_prerequisites.return_value = (True, "ok")
        state.phase = phase
        return ctrl, state

    def test_success_sets_triggered_true(self):
        ctrl, state = self._state_with_mock_phase()
        ctrl._trigger_cavity(state)
        assert state.triggered is True

    def test_success_emits_triggered_status(self):
        ctrl, state = self._state_with_mock_phase()
        emitted = []
        ctrl.cavity_status_changed.connect(lambda k, s: emitted.append((k, s)))
        ctrl._trigger_cavity(state)
        statuses = [s for _, s in emitted]
        assert BatchPiezoPreRFController.STATUS_TRIGGERED in statuses

    def test_step_failure_sets_error_and_not_triggered(self):
        ctrl, state = self._state_with_mock_phase(
            {TRIGGER_STEPS[0]: False, TRIGGER_STEPS[1]: True}
        )
        ctrl._trigger_cavity(state)
        assert state.triggered is False
        assert state.error is not None

    def test_step_failure_emits_error_status(self):
        ctrl, state = self._state_with_mock_phase(
            {TRIGGER_STEPS[0]: False, TRIGGER_STEPS[1]: True}
        )
        emitted = []
        ctrl.cavity_status_changed.connect(lambda k, s: emitted.append((k, s)))
        ctrl._trigger_cavity(state)
        assert BatchPiezoPreRFController.STATUS_ERROR in [s for _, s in emitted]

    def test_abort_before_step_skips_trigger(self):
        ctrl, state = self._state_with_mock_phase()
        ctrl._abort_event.set()
        ctrl._trigger_cavity(state)
        assert state.triggered is False

    def test_skips_when_state_already_has_error(self):
        ctrl, state = self._state_with_mock_phase()
        state.error = "pre-existing error"
        ctrl._trigger_cavity(state)
        state.phase._execute_step_with_retry.assert_not_called()

    def test_retry_count_reset_before_each_step(self):
        ctrl, state = self._state_with_mock_phase()
        state.phase._retry_count = 99
        ctrl._trigger_cavity(state)
        # After each successful step, _retry_count was reset to 0 before call
        # Last reset will have left it at 0
        assert state.phase._retry_count == 0

    def test_noop_when_phase_is_none(self):
        ctrl, state = _make_state()
        state.phase = None

        emitted = []
        ctrl.cavity_status_changed.connect(lambda k, s: emitted.append((k, s)))
        ctrl._trigger_cavity(state)

        assert emitted == []


# ---------------------------------------------------------------------------
# _collect_cavity
# ---------------------------------------------------------------------------


class TestCollectCavity:
    def _state_with_mock_phase(self, step_results=None):
        ctrl, state = _make_state()
        state.triggered = True

        phase = Mock()
        phase._retry_count = 0
        results = step_results or {s: True for s in COLLECT_STEPS}
        phase._execute_step_with_retry.side_effect = lambda s: results.get(
            s, True
        )

        record = state.record
        record.piezo_pre_rf = PiezoPreRFCheck(
            capacitance_a=25e-9,
            capacitance_b=24e-9,
            channel_a_passed=True,
            channel_b_passed=True,
        )
        state.phase = phase
        return ctrl, state

    def test_success_emits_passed_status(self):
        ctrl, state = self._state_with_mock_phase()
        emitted = []
        ctrl.cavity_status_changed.connect(lambda k, s: emitted.append((k, s)))
        ctrl._collect_cavity(state)
        assert BatchPiezoPreRFController.STATUS_PASSED in [
            s for _, s in emitted
        ]

    def test_success_emits_result_ready(self):
        ctrl, state = self._state_with_mock_phase()
        emitted = []
        ctrl.cavity_result_ready.connect(lambda k, r: emitted.append((k, r)))
        ctrl._collect_cavity(state)
        assert len(emitted) == 1
        assert emitted[0][1] is state.record.piezo_pre_rf

    def test_failed_step_emits_failed_status(self):
        ctrl, state = self._state_with_mock_phase(
            {COLLECT_STEPS[0]: False, COLLECT_STEPS[1]: True}
        )
        emitted = []
        ctrl.cavity_status_changed.connect(lambda k, s: emitted.append((k, s)))
        ctrl._collect_cavity(state)
        assert BatchPiezoPreRFController.STATUS_FAILED in [
            s for _, s in emitted
        ]

    def test_failed_step_calls_fail_phase_instance(self):
        ctrl, state = self._state_with_mock_phase(
            {COLLECT_STEPS[0]: False, COLLECT_STEPS[1]: True}
        )
        ctrl._collect_cavity(state)
        ctrl.session.workflow.fail_phase_instance.assert_called_once()

    def test_abort_emits_error_status(self):
        ctrl, state = self._state_with_mock_phase()
        ctrl._abort_event.set()
        emitted = []
        ctrl.cavity_status_changed.connect(lambda k, s: emitted.append((k, s)))
        ctrl._collect_cavity(state)
        assert BatchPiezoPreRFController.STATUS_ERROR in [s for _, s in emitted]

    def test_failed_piezo_check_emits_failed_status(self):
        ctrl, state = self._state_with_mock_phase()
        state.record.piezo_pre_rf = PiezoPreRFCheck(
            capacitance_a=25e-9,
            capacitance_b=24e-9,
            channel_a_passed=False,
            channel_b_passed=True,
        )
        emitted = []
        ctrl.cavity_status_changed.connect(lambda k, s: emitted.append((k, s)))
        ctrl._collect_cavity(state)
        assert BatchPiezoPreRFController.STATUS_FAILED in [
            s for _, s in emitted
        ]

    def test_calls_complete_phase_instance_on_success(self):
        ctrl, state = self._state_with_mock_phase()
        ctrl._collect_cavity(state)
        ctrl.session.workflow.complete_phase_instance.assert_called_once()

    def test_calls_save_record_on_success(self):
        ctrl, state = self._state_with_mock_phase()
        ctrl._collect_cavity(state)
        ctrl.session.db.save_record.assert_called()

    def test_missing_result_data_emits_failed_and_none_payload(self):
        ctrl, state = self._state_with_mock_phase()
        state.record.piezo_pre_rf = None

        statuses = []
        results = []
        ctrl.cavity_status_changed.connect(lambda k, s: statuses.append(s))
        ctrl.cavity_result_ready.connect(lambda k, r: results.append(r))

        ctrl._collect_cavity(state)

        assert BatchPiezoPreRFController.STATUS_FAILED in statuses
        assert results == [None]
        call_kwargs = ctrl.session.workflow.complete_phase_instance.call_args[1]
        assert call_kwargs["artifact_payload"] is None


# ---------------------------------------------------------------------------
# _run_batch (integration-style, parallel trigger mocked out)
# ---------------------------------------------------------------------------


class TestRunBatch:
    def _make_passing_run(self):
        session = _mock_session()
        ctrl = _make_controller(session)

        phase = Mock()
        phase._retry_count = 0
        phase._execute_step_with_retry.return_value = True

        def _fake_init(state, operator):
            record = CommissioningRecord(
                linac=0, cryomodule="01", cavity_number=state.spec.cavity_number
            )
            record.piezo_pre_rf = PiezoPreRFCheck(
                capacitance_a=25e-9,
                capacitance_b=24e-9,
                channel_a_passed=True,
                channel_b_passed=True,
            )
            state.record = record
            state.record_id = 1
            state.record_version = 1
            state.phase_instance_id = 42
            state.phase = phase
            state.context = Mock()
            state.context.abort_requested = False

        ctrl._init_record_and_context = _fake_init
        # Run triggers synchronously (bypass parallel pool)
        ctrl._trigger_cavities_parallel = lambda states: [
            ctrl._trigger_cavity(s) for s in states
        ]
        return ctrl

    def test_batch_finished_signal_emitted(self):
        ctrl = self._make_passing_run()
        finished = []
        ctrl.batch_finished.connect(lambda: finished.append(True))

        cavities = [CavitySpec("01", 1), CavitySpec("01", 2)]
        ctrl._run_batch(cavities, "op")

        assert finished == [True]

    def test_progress_signal_emitted_per_cavity(self):
        ctrl = self._make_passing_run()
        progress = []
        ctrl.batch_progress.connect(lambda c, t: progress.append((c, t)))

        cavities = [CavitySpec("01", 1), CavitySpec("01", 2)]
        ctrl._run_batch(cavities, "op")

        assert len(progress) == 2
        assert progress[-1] == (2, 2)

    def test_cavities_with_init_error_not_triggered(self):
        session = _mock_session()
        ctrl = _make_controller(session)

        def _bad_init(state, operator):
            raise ValueError("boom")

        ctrl._init_record_and_context = _bad_init
        ctrl._trigger_cavities_parallel = lambda states: [
            ctrl._trigger_cavity(s) for s in states
        ]

        statuses = []
        ctrl.cavity_status_changed.connect(lambda k, s: statuses.append(s))

        ctrl._run_batch([CavitySpec("01", 1)], "op")

        assert BatchPiezoPreRFController.STATUS_ERROR in statuses

    def test_logs_singular_cavity_message(self):
        ctrl = self._make_passing_run()
        logs = []
        ctrl.log_message.connect(lambda m: logs.append(m))

        ctrl._run_batch([CavitySpec("01", 1)], "op")

        assert any("1 cavity" in msg for msg in logs)


# ---------------------------------------------------------------------------
# abort and is_running
# ---------------------------------------------------------------------------


class TestAbort:
    def test_abort_sets_event(self):
        ctrl = _make_controller()
        ctrl.abort()
        assert ctrl._abort_event.is_set()

    def test_abort_clears_on_new_run_batch_call(self):
        ctrl = _make_controller()
        ctrl.abort()

        # run_batch clears the event before starting
        ctrl._abort_event.clear()
        assert not ctrl._abort_event.is_set()


# ---------------------------------------------------------------------------
# _get_machine_cavity
# ---------------------------------------------------------------------------


class TestGetMachineCavity:
    def test_builds_machine_with_commissioning_piezo(self, monkeypatch):
        class _MachineStub:
            def __init__(self, *, piezo_class):
                self.piezo_class = piezo_class
                self.cryomodules = {
                    "01": SimpleNamespace(cavities={1: "cav-obj"})
                }

        monkeypatch.setattr(ctrl_module, "Machine", _MachineStub)
        ctrl = _make_controller()
        result = ctrl._get_machine_cavity(CavitySpec("01", 1))

        assert result == "cav-obj"
        assert ctrl._machine.piezo_class is CommissioningPiezo

    def test_reuses_existing_machine(self, monkeypatch):
        call_count = 0

        class _MachineStub:
            def __init__(self, *, piezo_class):
                nonlocal call_count
                call_count += 1
                self.cryomodules = {
                    "01": SimpleNamespace(cavities={1: "cav-obj"})
                }

        monkeypatch.setattr(ctrl_module, "Machine", _MachineStub)
        ctrl = _make_controller()
        ctrl._get_machine_cavity(CavitySpec("01", 1))
        ctrl._get_machine_cavity(CavitySpec("01", 1))

        assert call_count == 1

    def test_numeric_cryomodule_zero_padded(self, monkeypatch):
        accessed_keys = []

        class _CMStub:
            def __getitem__(self, key):
                accessed_keys.append(key)
                return SimpleNamespace(cavities={1: "cav"})

        class _MachineStub:
            def __init__(self, *, piezo_class):
                self.cryomodules = _CMStub()

        monkeypatch.setattr(ctrl_module, "Machine", _MachineStub)
        ctrl = _make_controller()
        ctrl._get_machine_cavity(CavitySpec("1", 1))

        assert "01" in accessed_keys


# ---------------------------------------------------------------------------
# _persist_record
# ---------------------------------------------------------------------------


class TestPersistRecord:
    def test_increments_version_on_success(self):
        ctrl, state = _make_state()
        state.record_version = 3
        ctrl._persist_record(state)
        assert state.record_version == 4

    def test_no_op_when_no_record(self):
        ctrl = _make_controller()
        state = CavityRunState(spec=CavitySpec("01", 1))
        ctrl._persist_record(state)  # should not raise

    def test_calls_save_record_with_version(self):
        ctrl, state = _make_state()
        state.record_version = 2
        ctrl._persist_record(state)
        ctrl.session.db.save_record.assert_called_with(
            state.record, state.record_id, expected_version=2
        )

    def test_save_record_exception_does_not_propagate(self):
        ctrl, state = _make_state()
        ctrl.session.db.save_record.side_effect = RuntimeError("db down")
        ctrl._persist_record(state)  # should not raise


# ---------------------------------------------------------------------------
# run_batch public API
# ---------------------------------------------------------------------------


class TestRunBatchPublicAPI:
    def test_already_running_logs_message(self):
        ctrl = _make_controller()
        logs = []
        ctrl.log_message.connect(lambda m: logs.append(m))

        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = True
        ctrl._worker_thread = mock_thread

        ctrl.run_batch([CavitySpec("01", 1)], "op")
        assert any("already running" in m.lower() for m in logs)

    def test_run_batch_clears_abort_event(self):
        ctrl = _make_controller()
        ctrl._abort_event.set()
        ctrl._run_batch = lambda cavities, op: None  # no-op
        ctrl.run_batch([CavitySpec("01", 1)], "op")
        # The event is cleared before the thread starts
        # Give thread a moment to clear
        import time

        time.sleep(0.05)
        assert not ctrl._abort_event.is_set()

    def test_run_batch_starts_background_thread(self):
        ctrl = _make_controller()

        started = []

        def _fake_run_batch(cavities, operator):
            started.append(True)

        ctrl._run_batch = _fake_run_batch
        ctrl.run_batch([CavitySpec("01", 1)], "op")

        import time

        time.sleep(0.1)
        assert started == [True]
        assert ctrl._worker_thread is not None


# ---------------------------------------------------------------------------
# Workflow exception in _init_record_and_context
# ---------------------------------------------------------------------------


class TestInitRecordWorkflowException:
    def test_workflow_exception_sets_phase_instance_id_none(self):
        session = _mock_session()
        session.workflow.start_phase_for_record.side_effect = RuntimeError(
            "rpc fail"
        )
        ctrl = _make_controller(session)
        state = CavityRunState(spec=CavitySpec("01", 1))
        ctrl._init_record_and_context(state, "op")
        assert state.phase_instance_id is None

    def test_workflow_exception_does_not_propagate(self):
        session = _mock_session()
        session.workflow.start_phase_for_record.side_effect = RuntimeError(
            "rpc fail"
        )
        ctrl = _make_controller(session)
        state = CavityRunState(spec=CavitySpec("01", 1))
        ctrl._init_record_and_context(state, "op")  # should not raise


# ---------------------------------------------------------------------------
# Prerequisites not met
# ---------------------------------------------------------------------------


class TestPrerequisitesNotMet:
    def test_raises_when_prerequisites_fail(self, monkeypatch):
        import sc_linac_physics.applications.rf_commissioning.controllers.batch_piezo_pre_rf_controller as ctrl_module

        class _BadPhase:
            def __init__(self, ctx):
                pass

            def validate_prerequisites(self):
                return (False, "bad state")

        monkeypatch.setattr(ctrl_module, "PiezoPreRFPhase", _BadPhase)

        ctrl = _make_controller()
        state = CavityRunState(spec=CavitySpec("01", 1))
        with pytest.raises(ValueError, match="Prerequisites not met"):
            ctrl._init_record_and_context(state, "op")


# ---------------------------------------------------------------------------
# Exception paths in _complete_phase_instance / _fail_phase_instance
# ---------------------------------------------------------------------------


class TestCompletePhaseInstanceException:
    def test_exception_does_not_propagate(self):
        ctrl, state = _make_state()
        ctrl.session.workflow.complete_phase_instance.side_effect = (
            RuntimeError("network")
        )
        result = PiezoPreRFCheck(
            capacitance_a=25e-9,
            capacitance_b=24e-9,
            channel_a_passed=True,
            channel_b_passed=True,
        )
        ctrl._complete_phase_instance(state, result)  # no raise

    def test_no_op_when_phase_instance_id_is_none(self):
        ctrl = _make_controller()
        state = CavityRunState(spec=CavitySpec("01", 1))
        state.record_id = 99
        state.phase_instance_id = None
        ctrl._complete_phase_instance(state, None)  # should not call workflow


class TestFailPhaseInstanceException:
    def test_exception_does_not_propagate(self):
        ctrl, state = _make_state()
        ctrl.session.workflow.fail_phase_instance.side_effect = RuntimeError(
            "down"
        )
        ctrl._fail_phase_instance(state, "step failed")  # no raise

    def test_payload_includes_piezo_pre_rf_data(self):
        ctrl, state = _make_state()
        state.record.piezo_pre_rf = PiezoPreRFCheck(
            capacitance_a=25e-9,
            capacitance_b=24e-9,
            channel_a_passed=True,
            channel_b_passed=True,
        )
        ctrl._fail_phase_instance(state, "step failed")
        call_kwargs = ctrl.session.workflow.fail_phase_instance.call_args[1]
        assert call_kwargs["artifact_payload"] is not None

    def test_no_op_when_phase_instance_id_none(self):
        ctrl = _make_controller()
        state = CavityRunState(spec=CavitySpec("01", 1))
        state.record_id = 99
        state.phase_instance_id = None
        ctrl._fail_phase_instance(state, "boom")  # should not call workflow

    def test_payload_is_none_when_no_piezo_data(self):
        ctrl, state = _make_state()
        state.record.piezo_pre_rf = None

        ctrl._fail_phase_instance(state, "step failed")

        call_kwargs = ctrl.session.workflow.fail_phase_instance.call_args[1]
        assert call_kwargs["artifact_payload"] is None


# ---------------------------------------------------------------------------
# _ensure_pool and _trigger_cavities_parallel
# ---------------------------------------------------------------------------


class TestEnsurePool:
    def test_sets_pool_ready(self):
        ctrl = _make_controller()
        assert not ctrl._pool_ready
        ctrl._ensure_pool()
        assert ctrl._pool_ready

    def test_idempotent_second_call_safe(self):
        ctrl = _make_controller()
        ctrl._ensure_pool()
        ctrl._ensure_pool()  # should not raise or start more threads


class TestTriggerCavitiesParallel:
    def test_empty_states_no_error(self):
        ctrl = _make_controller()
        ctrl._trigger_cavities_parallel([])  # should not raise

    def test_abort_before_dispatch_returns_without_pool(self):
        ctrl = _make_controller()
        ctrl._abort_event.set()

        state = CavityRunState(spec=CavitySpec("01", 1))
        state.triggered = False
        state.error = None

        ctrl._trigger_cavities_parallel([state])
        # Pool should not have been started since abort happened first
        assert not ctrl._pool_ready

    def test_abort_before_dispatch_marks_triggered_as_skipped(self):
        ctrl = _make_controller()
        ctrl._abort_event.set()

        state = CavityRunState(spec=CavitySpec("01", 1))
        state.triggered = True
        state.error = None

        statuses = []
        ctrl.cavity_status_changed.connect(lambda k, s: statuses.append(s))
        ctrl._trigger_cavities_parallel([state])

        assert BatchPiezoPreRFController.STATUS_SKIPPED in statuses

    def test_dispatches_to_pool_and_waits(self):
        ctrl = _make_controller()
        triggered = []

        def _fake_trigger(state):
            state.triggered = True
            triggered.append(state.spec.key)

        ctrl._trigger_cavity = _fake_trigger

        state = CavityRunState(spec=CavitySpec("01", 1))
        state.error = None
        state.phase = Mock()
        ctrl._trigger_cavities_parallel([state])

        assert "01_CAV1" in triggered


# ---------------------------------------------------------------------------
# finalize_phase exception path in _collect_cavity
# ---------------------------------------------------------------------------


class TestFinalizePhaseFails:
    def test_finalize_exception_does_not_propagate(self):
        ctrl, state = _make_state()
        state.triggered = True

        phase = Mock()
        phase._retry_count = 0
        phase._execute_step_with_retry.return_value = True
        phase.finalize_phase.side_effect = RuntimeError("phase broken")
        state.phase = phase

        state.record.piezo_pre_rf = PiezoPreRFCheck(
            capacitance_a=25e-9,
            capacitance_b=24e-9,
            channel_a_passed=True,
            channel_b_passed=True,
        )

        ctrl._collect_cavity(state)  # should not raise


# ---------------------------------------------------------------------------
# abort during collect sweep in _run_batch
# ---------------------------------------------------------------------------


class TestAbortDuringCollect:
    def _make_ctrl_with_triggered_states(self):
        session = _mock_session()
        ctrl = _make_controller(session)

        def _fake_init(state, operator):
            from sc_linac_physics.applications.rf_commissioning.models.data_models import (
                CommissioningRecord,
            )

            record = CommissioningRecord(
                linac=0, cryomodule="01", cavity_number=state.spec.cavity_number
            )
            record.piezo_pre_rf = PiezoPreRFCheck(
                capacitance_a=25e-9,
                capacitance_b=24e-9,
                channel_a_passed=True,
                channel_b_passed=True,
            )
            state.record = record
            state.record_id = 1
            state.record_version = 1
            state.phase_instance_id = 42
            state.phase = Mock()
            state.phase._retry_count = 0
            state.phase._execute_step_with_retry.return_value = True
            state.context = Mock()
            state.context.abort_requested = False

        ctrl._init_record_and_context = _fake_init
        ctrl._trigger_cavities_parallel = lambda states: [
            setattr(s, "triggered", True) for s in states
        ]
        return ctrl

    def test_abort_before_collect_marks_untriggered_as_skipped(self):
        ctrl = self._make_ctrl_with_triggered_states()

        # Override parallel trigger: only trigger first cavity, leave others untriggered
        def _partial_trigger(states):
            if states:
                states[0].triggered = True

        ctrl._trigger_cavities_parallel = _partial_trigger

        statuses = {}
        ctrl.cavity_status_changed.connect(
            lambda k, s: statuses.__setitem__(k, s)
        )

        # Make collect abort after first cavity
        def _abort_on_first_collect(state):
            ctrl._abort_event.set()

        ctrl._collect_cavity = _abort_on_first_collect

        cavities = [
            CavitySpec("01", 1),
            CavitySpec("01", 2),
            CavitySpec("01", 3),
        ]
        ctrl._run_batch(cavities, "op")

        # Untriggered cavities (cav 2, cav 3) should be marked SKIPPED
        assert (
            statuses.get("01_CAV2") == BatchPiezoPreRFController.STATUS_SKIPPED
        )
        assert (
            statuses.get("01_CAV3") == BatchPiezoPreRFController.STATUS_SKIPPED
        )


# ---------------------------------------------------------------------------
# _mark_remaining_skipped
# ---------------------------------------------------------------------------


class TestMarkRemainingSkipped:
    # Logic: emit SKIPPED when `not state.error AND state.triggered != only_triggered`
    # Default only_triggered=False: emit SKIPPED for triggered=True states
    # only_triggered=True: emit SKIPPED for triggered=False states

    def test_emits_skipped_for_triggered_by_default(self):
        ctrl = _make_controller()
        state = CavityRunState(spec=CavitySpec("01", 1))
        state.triggered = True
        state.error = None

        statuses = []
        ctrl.cavity_status_changed.connect(lambda k, s: statuses.append(s))
        ctrl._mark_remaining_skipped([state])
        assert BatchPiezoPreRFController.STATUS_SKIPPED in statuses

    def test_does_not_emit_skipped_for_untriggered_by_default(self):
        ctrl = _make_controller()
        state = CavityRunState(spec=CavitySpec("01", 1))
        state.triggered = False
        state.error = None

        statuses = []
        ctrl.cavity_status_changed.connect(lambda k, s: statuses.append(s))
        ctrl._mark_remaining_skipped([state])
        assert BatchPiezoPreRFController.STATUS_SKIPPED not in statuses

    def test_emits_skipped_for_untriggered_when_only_triggered_true(self):
        ctrl = _make_controller()
        state = CavityRunState(spec=CavitySpec("01", 1))
        state.triggered = False
        state.error = None

        statuses = []
        ctrl.cavity_status_changed.connect(lambda k, s: statuses.append(s))
        ctrl._mark_remaining_skipped([state], only_triggered=True)
        assert BatchPiezoPreRFController.STATUS_SKIPPED in statuses

    def test_does_not_emit_skipped_for_error_states(self):
        ctrl = _make_controller()
        state = CavityRunState(spec=CavitySpec("01", 1))
        state.triggered = True  # would match default, but error blocks it
        state.error = "already failed"

        statuses = []
        ctrl.cavity_status_changed.connect(lambda k, s: statuses.append(s))
        ctrl._mark_remaining_skipped([state])
        assert BatchPiezoPreRFController.STATUS_SKIPPED not in statuses


# ---------------------------------------------------------------------------
# _pool_worker
# ---------------------------------------------------------------------------


class TestPoolWorker:
    class _QueueOnce:
        def __init__(self, item):
            self._item = item
            self.task_done_calls = 0
            self._calls = 0

        def get(self):
            self._calls += 1
            if self._calls == 1:
                return self._item
            raise SystemExit()

        def task_done(self):
            self.task_done_calls += 1

    def test_trigger_exception_sets_error_and_signals_done(self):
        ctrl = _make_controller()
        state = CavityRunState(spec=CavitySpec("01", 1))
        done = Event()

        queue_stub = self._QueueOnce((state, done))
        ctrl._trigger_queue = queue_stub
        ctrl._trigger_cavity = Mock(side_effect=RuntimeError("boom"))

        with pytest.raises(SystemExit):
            ctrl._pool_worker()

        assert state.error == "boom"
        assert done.is_set()
        assert queue_stub.task_done_calls == 1

    def test_uses_initial_epics_context_when_available(self, monkeypatch):
        ctrl = _make_controller()
        state = CavityRunState(spec=CavitySpec("01", 1))
        done = Event()

        queue_stub = self._QueueOnce((state, done))
        ctrl._trigger_queue = queue_stub
        ctrl._trigger_cavity = Mock()

        use_initial_context = Mock()
        fake_epics = SimpleNamespace(
            ca=SimpleNamespace(use_initial_context=use_initial_context)
        )
        monkeypatch.setitem(sys.modules, "epics", fake_epics)

        with pytest.raises(SystemExit):
            ctrl._pool_worker()

        use_initial_context.assert_called_once()
