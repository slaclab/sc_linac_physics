"""Tests for SSA Calibration controller."""

from types import SimpleNamespace
from unittest.mock import Mock

import sc_linac_physics.applications.rf_commissioning.ui.controllers.ssa_char_controller as controller_module
from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningRecord,
    SSACharacterization,
)
from sc_linac_physics.applications.rf_commissioning.phases.phase_base import (
    PhaseContext,
    PhaseResult,
    PhaseStepResult,
)
from sc_linac_physics.applications.rf_commissioning.ui.controllers.ssa_char_controller import (
    SSACharController,
)


class _ButtonStub:
    def __init__(self):
        self.enabled = True
        self.text = ""

    def setEnabled(self, enabled: bool) -> None:
        self.enabled = enabled

    def setText(self, text: str) -> None:
        self.text = text


class _ViewStub:
    def __init__(
        self,
        *,
        current_operator: str = "Test Operator",
        cavity: tuple[str, str] | None = ("L1B_CM02_CAV1", "02"),
    ):
        self._current_operator = current_operator
        self._cavity = cavity
        self.logs: list[str] = []
        self.errors: list[str] = []

        self.run_button = _ButtonStub()
        self.pause_button = _ButtonStub()
        self.abort_button = _ButtonStub()
        self.local_phase_status = Mock()
        self.local_progress_bar = Mock()
        self.ui = SimpleNamespace(update_toolbar_state=Mock())
        self.step_progress_signal = SimpleNamespace(emit=Mock())
        self.drive_max_spinbox = SimpleNamespace(value=Mock(return_value=0.670))
        self._update_local_results = Mock()
        self._update_stored_readout = Mock()

    def get_current_operator(self) -> str:
        return self._current_operator

    def get_current_cavity(self):
        return self._cavity

    def log_message(self, message: str) -> None:
        self.logs.append(message)

    def show_error(self, message: str) -> None:
        self.errors.append(message)

    def clear_results(self) -> None:
        return None

    def parent(self):
        return None

    def _notify_parent_of_record_update(self, record, message: str) -> None:
        return None


def _make_controller(view=None, session=None):
    return SSACharController(view or _ViewStub(), session or Mock())


def _record_with_result() -> CommissioningRecord:
    record = CommissioningRecord(linac=1, cryomodule="02", cavity_number=1)
    record.ssa_char = SSACharacterization(
        max_drive=0.670,
        slope_new=1.02345,
        max_fwd_pwr_w=4500.0,
        calibration_passed=True,
    )
    return record


class _ThreadStub:
    def __init__(self, target, daemon):
        self.target = target

    def start(self):
        self.target()


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def test_get_operator_returns_value() -> None:
    view = _ViewStub(current_operator="Alice")
    assert _make_controller(view=view)._get_operator() == "Alice"


def test_get_operator_empty_when_no_method() -> None:
    assert SSACharController(SimpleNamespace(), Mock())._get_operator() == ""


def test_parse_cavity_from_record_full_name() -> None:
    controller = _make_controller()
    assert controller._parse_cavity_from_record("L1B_CM02_CAV8", "02") == (2, 8)


def test_parse_cavity_from_record_short_name_defaults_to_cav1() -> None:
    controller = _make_controller()
    assert controller._parse_cavity_from_record("SHORT", "02") == (2, 1)


def test_update_toolbar_state_delegates_to_ui() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller._update_toolbar_state("running")
    view.ui.update_toolbar_state.assert_called_once_with("running")


def test_update_toolbar_state_without_ui_is_safe() -> None:
    SSACharController(SimpleNamespace(), Mock())._update_toolbar_state(
        "running"
    )


# ------------------------------------------------------------------
# PV wiring
# ------------------------------------------------------------------


def test_setup_pv_connections_calls_update_when_active() -> None:
    session = Mock()
    session.has_active_record.return_value = True
    controller = _make_controller(session=session)
    controller.update_pv_addresses = Mock()

    controller.setup_pv_connections()

    controller.update_pv_addresses.assert_called_once()


def test_setup_pv_connections_skips_when_no_active_record() -> None:
    session = Mock()
    session.has_active_record.return_value = False
    controller = _make_controller(session=session)
    controller.update_pv_addresses = Mock()

    controller.setup_pv_connections()

    controller.update_pv_addresses.assert_not_called()


def test_update_pv_addresses_no_selection_logs_message() -> None:
    view = _ViewStub(cavity=None)
    controller = _make_controller(view=view)

    controller.update_pv_addresses()

    assert "No cavity selected" in view.logs


def test_update_pv_addresses_invalid_int_logs_message(monkeypatch) -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    monkeypatch.setattr(
        controller_module, "resolve_cavity_selection", lambda *_: ("02", "bad")
    )

    controller.update_pv_addresses()

    assert any("Invalid cavity/CM value" in msg for msg in view.logs)


def test_update_pv_addresses_exception_logs_error() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller._get_machine_cavity = Mock(side_effect=RuntimeError("oops"))

    controller.update_pv_addresses("02", "1")

    assert any("Error setting PVs" in msg for msg in view.logs)


# ------------------------------------------------------------------
# on_run_calibration
# ------------------------------------------------------------------


def test_on_run_calibration_no_operator_shows_error() -> None:
    view = _ViewStub(current_operator="")
    _make_controller(view=view).on_run_calibration()
    assert any("operator" in msg.lower() for msg in view.errors)


def test_on_run_calibration_auto_create_fails_stops() -> None:
    session = Mock()
    session.has_active_record.return_value = False
    controller = _make_controller(session=session)
    controller._auto_create_record = Mock(return_value=False)

    controller.on_run_calibration()

    controller._auto_create_record.assert_called_once()


def test_on_run_calibration_no_cavity_shows_error() -> None:
    session = Mock()
    session.has_active_record.return_value = True
    view = _ViewStub(cavity=None)
    _make_controller(view=view, session=session).on_run_calibration()
    assert any("cavity" in msg.lower() for msg in view.errors)


def test_on_run_calibration_success_path() -> None:
    view = _ViewStub()
    session = Mock()
    session.has_active_record.return_value = True
    controller = _make_controller(view=view, session=session)
    controller.update_pv_addresses = Mock()
    controller._get_machine_cavity = Mock(return_value=Mock())
    controller._prepare_phase_context = Mock(return_value=True)
    controller._set_running_ui_state = Mock()
    controller._execute_phase_async = Mock()

    controller.on_run_calibration()

    controller._set_running_ui_state.assert_called_once()
    controller._execute_phase_async.assert_called_once()


def test_on_run_calibration_prepare_context_fails_stops() -> None:
    session = Mock()
    session.has_active_record.return_value = True
    controller = _make_controller(session=session)
    controller.update_pv_addresses = Mock()
    controller._get_machine_cavity = Mock(return_value=Mock())
    controller._prepare_phase_context = Mock(return_value=False)
    controller._execute_phase_async = Mock()

    controller.on_run_calibration()

    controller._execute_phase_async.assert_not_called()


def test_on_run_calibration_exception_is_logged() -> None:
    view = _ViewStub()
    session = Mock()
    session.has_active_record.return_value = True
    controller = _make_controller(view=view, session=session)
    controller.update_pv_addresses = Mock(side_effect=RuntimeError("boom"))

    controller.on_run_calibration()

    assert any("Failed to start calibration" in msg for msg in view.errors)


# ------------------------------------------------------------------
# _prepare_phase_context
# ------------------------------------------------------------------


def test_prepare_phase_context_can_run_false() -> None:
    session = Mock()
    session.get_active_record.return_value = _record_with_result()
    session.get_active_record_id.return_value = 7
    session.can_run_phase.return_value = (False, "blocked")
    view = _ViewStub()
    controller = _make_controller(view=view, session=session)

    assert controller._prepare_phase_context(Mock(), "op", 0.670) is False
    assert any("blocked" in msg for msg in view.errors)


def test_prepare_phase_context_prerequisites_fail(monkeypatch) -> None:
    session = Mock()
    session.get_active_record.return_value = _record_with_result()
    session.get_active_record_id.return_value = 7
    session.can_run_phase.return_value = (True, "")
    session.start_active_phase_instance.return_value = SimpleNamespace(
        phase_instance_id=99
    )

    class _PhaseStub:
        def __init__(self, ctx):
            pass

        def validate_prerequisites(self):
            return (False, "no SSA")

    monkeypatch.setattr(controller_module, "SSACharPhase", _PhaseStub)
    view = _ViewStub()
    controller = _make_controller(view=view, session=session)

    assert controller._prepare_phase_context(Mock(), "op", 0.670) is False
    assert any("no SSA" in msg for msg in view.errors)


def test_prepare_phase_context_success_no_record_id(monkeypatch) -> None:
    session = Mock()
    session.get_active_record.return_value = _record_with_result()
    session.get_active_record_id.return_value = None
    session.can_run_phase.return_value = (True, "")

    class _PhaseStub:
        def __init__(self, ctx):
            pass

        def validate_prerequisites(self):
            return (True, "ok")

    monkeypatch.setattr(controller_module, "SSACharPhase", _PhaseStub)
    controller = _make_controller(session=session)

    assert controller._prepare_phase_context(Mock(), "op", 0.670) is True
    assert controller._active_phase_instance_id is None


# ------------------------------------------------------------------
# UI state
# ------------------------------------------------------------------


def test_set_running_ui_state() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)

    controller._set_running_ui_state()

    assert view.run_button.enabled is False
    assert view.pause_button.enabled is True
    assert view.abort_button.enabled is True
    view.local_phase_status.setText.assert_called_once_with("RUNNING")


# ------------------------------------------------------------------
# Pause / abort
# ------------------------------------------------------------------


def test_on_abort_requests_abort_and_disables_button() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller.context = PhaseContext(
        record=_record_with_result(), operator="op"
    )

    controller.on_abort()

    assert controller.context.abort_requested is True
    assert view.abort_button.enabled is False
    assert "Abort requested..." in view.logs


def test_on_abort_without_context_is_noop() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller.context = None

    controller.on_abort()

    assert view.abort_button.enabled is True


def test_on_pause_test_toggles_state_and_button_text() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)

    controller.on_pause_test()
    assert controller._paused is True
    assert view.pause_button.text == "▶ Resume"

    controller.on_pause_test()
    assert controller._paused is False
    assert view.pause_button.text == "⏸ Pause"


# ------------------------------------------------------------------
# _check_pause_and_abort
# ------------------------------------------------------------------


def test_check_pause_and_abort_normal_proceeds() -> None:
    assert _make_controller()._check_pause_and_abort() is True


def test_check_pause_and_abort_aborted() -> None:
    controller = _make_controller()
    controller.context = PhaseContext(
        record=_record_with_result(), operator="op"
    )
    controller.context.request_abort()
    emitted = []
    controller.phase_run_finished.connect(
        lambda ok, msg: emitted.append((ok, msg))
    )

    assert controller._check_pause_and_abort() is False
    assert emitted[-1] == (False, "Aborted")


def test_check_pause_and_abort_paused_then_abort(monkeypatch) -> None:
    controller = _make_controller()
    controller.context = PhaseContext(
        record=_record_with_result(), operator="op"
    )
    controller._paused = True

    def _sleep(_):
        controller.context.request_abort()

    monkeypatch.setitem(
        __import__("sys").modules, "time", SimpleNamespace(sleep=_sleep)
    )
    emitted = []
    controller.phase_run_finished.connect(
        lambda ok, msg: emitted.append((ok, msg))
    )

    assert controller._check_pause_and_abort() is False
    assert emitted[-1] == (False, "Aborted")


# ------------------------------------------------------------------
# Step execution
# ------------------------------------------------------------------


def test_execute_step_with_retries_success() -> None:
    controller = _make_controller()
    controller.phase = Mock()
    controller.phase.execute_step.return_value = PhaseStepResult(
        result=PhaseResult.SUCCESS, message="ok"
    )
    controller._create_step_checkpoint = Mock()

    assert controller._execute_step_with_retries("step", max_retries=3) is True
    assert any("✓" in msg for msg in controller.view.logs)


def test_execute_step_with_retries_skip() -> None:
    controller = _make_controller()
    controller.phase = Mock()
    controller.phase.execute_step.return_value = PhaseStepResult(
        result=PhaseResult.SKIP, message="skip"
    )
    controller._create_step_checkpoint = Mock()

    assert controller._execute_step_with_retries("step", max_retries=3) is True


def test_execute_step_with_retries_failed() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller.phase = Mock()
    controller.phase.execute_step.return_value = PhaseStepResult(
        result=PhaseResult.FAILED, message="bad"
    )
    controller._create_step_checkpoint = Mock()

    assert controller._execute_step_with_retries("step", max_retries=3) is False
    assert any("✗" in msg for msg in view.logs)


def test_execute_step_with_retries_retry_exhausted() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller.phase = Mock()
    controller.phase.execute_step.return_value = PhaseStepResult(
        result=PhaseResult.RETRY, message="again", retry_delay_seconds=0.0
    )
    controller._create_step_checkpoint = Mock()

    assert controller._execute_step_with_retries("step", max_retries=2) is False
    assert any("Failed after 2 retries" in msg for msg in view.logs)


def test_execute_step_with_retries_exception_exhausted() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller.phase = Mock()
    controller.phase.execute_step.side_effect = RuntimeError("rpc down")

    assert controller._execute_step_with_retries("step", max_retries=2) is False
    assert any("Exception after 2 retries" in msg for msg in view.logs)


def test_create_step_checkpoint_appends_to_history() -> None:
    controller = _make_controller()
    record = _record_with_result()
    record.phase_history = []
    controller.context = PhaseContext(record=record, operator="op")
    controller.phase = Mock()
    controller.phase.phase_type = "SSA_CHAR"

    controller._create_step_checkpoint(
        "verify_initial_state",
        PhaseStepResult(
            result=PhaseResult.SUCCESS, message="ok", data={"a": 1}
        ),
    )

    assert len(record.phase_history) == 1
    assert record.phase_history[0].step_name == "verify_initial_state"
    assert record.phase_history[0].success is True


# ------------------------------------------------------------------
# Background phase finalization
# ------------------------------------------------------------------


def test_finalize_background_phase_emits_success() -> None:
    controller = _make_controller()
    controller.phase = Mock()
    emitted = []
    controller.phase_run_finished.connect(
        lambda ok, msg: emitted.append((ok, msg))
    )

    controller._finalize_background_phase()

    assert emitted[-1] == (True, "")


def test_finalize_background_phase_emits_failure_on_exception() -> None:
    controller = _make_controller()
    controller.phase = Mock()
    controller.phase.finalize_phase.side_effect = RuntimeError("fail")
    emitted = []
    controller.phase_run_finished.connect(
        lambda ok, msg: emitted.append((ok, msg))
    )

    controller._finalize_background_phase()

    assert emitted[-1] == (False, "fail")


def test_on_phase_run_finished_routes_to_completed() -> None:
    controller = _make_controller()
    controller.on_phase_completed = Mock()
    controller.on_phase_failed = Mock()

    controller._on_phase_run_finished(True, "")

    controller.on_phase_completed.assert_called_once()
    controller.on_phase_failed.assert_not_called()


def test_on_phase_run_finished_routes_to_failed_with_message() -> None:
    controller = _make_controller()
    controller.on_phase_completed = Mock()
    controller.on_phase_failed = Mock()

    controller._on_phase_run_finished(False, "boom")

    controller.on_phase_failed.assert_called_once_with("boom")


def test_on_phase_run_finished_uses_default_error_message() -> None:
    controller = _make_controller()
    controller.on_phase_completed = Mock()
    controller.on_phase_failed = Mock()

    controller._on_phase_run_finished(False, "")

    controller.on_phase_failed.assert_called_once_with("Phase execution failed")


# ------------------------------------------------------------------
# _run_phase_in_background
# ------------------------------------------------------------------


def test_run_phase_in_background_abort_path(monkeypatch) -> None:
    controller = _make_controller()
    controller.phase = Mock()
    controller.phase.get_phase_steps.return_value = ["step"]
    controller._check_pause_and_abort = Mock(return_value=False)
    monkeypatch.setattr(controller_module, "Thread", _ThreadStub)

    controller._run_phase_in_background()


def test_run_phase_in_background_step_fails_emits_signal(monkeypatch) -> None:
    controller = _make_controller()
    controller.phase = Mock()
    controller.phase.get_phase_steps.return_value = ["step"]
    controller._check_pause_and_abort = Mock(return_value=True)
    controller._execute_single_step = Mock(return_value=False)
    emitted = []
    controller.phase_run_finished.connect(
        lambda ok, msg: emitted.append((ok, msg))
    )
    monkeypatch.setattr(controller_module, "Thread", _ThreadStub)

    controller._run_phase_in_background()

    assert emitted[-1] == (False, "Step failed: step")


def test_run_phase_in_background_exception_emits_signal(monkeypatch) -> None:
    controller = _make_controller()
    controller.phase = Mock()
    controller.phase.get_phase_steps.side_effect = RuntimeError("worker fail")
    emitted = []
    controller.phase_run_finished.connect(
        lambda ok, msg: emitted.append((ok, msg))
    )
    monkeypatch.setattr(controller_module, "Thread", _ThreadStub)

    controller._run_phase_in_background()

    assert emitted[-1] == (False, "worker fail")


# ------------------------------------------------------------------
# on_phase_completed
# ------------------------------------------------------------------


def test_on_phase_completed_success_resets_buttons() -> None:
    view = _ViewStub()
    session = Mock()
    session.save_active_record.return_value = True
    session.get_active_record_id.return_value = 42
    controller = _make_controller(view=view, session=session)
    controller.context = PhaseContext(
        record=_record_with_result(), operator="op"
    )
    controller._active_phase_instance_id = 3
    controller._append_measurement_history = Mock()
    captured = []
    controller.phase_completed.connect(lambda rec: captured.append(rec))

    controller.on_phase_completed()

    assert view.run_button.enabled is True
    assert view.pause_button.enabled is False
    assert controller._active_phase_instance_id is None
    assert captured


def test_on_phase_completed_save_fails_logs_warning() -> None:
    view = _ViewStub()
    session = Mock()
    session.save_active_record.return_value = False
    controller = _make_controller(view=view, session=session)
    controller.context = PhaseContext(
        record=_record_with_result(), operator="op"
    )
    controller._append_measurement_history = Mock()

    controller.on_phase_completed()

    assert any("failed to save" in msg.lower() for msg in view.logs)


def test_on_phase_completed_no_ssa_char_data_logs_warning() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view, session=Mock())
    record = CommissioningRecord(linac=1, cryomodule="02", cavity_number=1)
    record.ssa_char = None
    controller.context = PhaseContext(record=record, operator="op")

    controller.on_phase_completed()

    assert any("no ssa_char data" in msg.lower() for msg in view.logs)


def test_on_phase_completed_exception_calls_fail_instance() -> None:
    session = Mock()
    session.save_active_record.side_effect = RuntimeError("db down")
    controller = _make_controller(session=session)
    controller.context = PhaseContext(
        record=_record_with_result(), operator="op"
    )
    controller._active_phase_instance_id = 5

    controller.on_phase_completed()

    session.fail_active_phase_instance.assert_called_once()


# ------------------------------------------------------------------
# on_phase_failed
# ------------------------------------------------------------------


def test_on_phase_failed_resets_buttons_and_shows_error() -> None:
    view = _ViewStub()
    session = Mock()
    session.save_active_record.return_value = True
    controller = _make_controller(view=view, session=session)
    controller.phase = Mock()
    controller.context = PhaseContext(
        record=_record_with_result(), operator="op"
    )
    controller._active_phase_instance_id = 9
    controller._append_measurement_history = Mock()

    controller.on_phase_failed("bad")

    assert view.run_button.enabled is True
    assert view.pause_button.enabled is False
    assert view.abort_button.enabled is False
    assert any("bad" in msg for msg in view.errors)
    session.fail_active_phase_instance.assert_called_once()


def test_on_phase_failed_exception_still_calls_fail_instance() -> None:
    session = Mock()
    session.save_active_record.side_effect = RuntimeError("db exploded")
    controller = _make_controller(session=session)
    controller.phase = Mock()
    controller.context = PhaseContext(
        record=_record_with_result(), operator="op"
    )
    controller._active_phase_instance_id = 10

    controller.on_phase_failed("orig")

    session.fail_active_phase_instance.assert_called_once()


# ------------------------------------------------------------------
# on_push_slope
# ------------------------------------------------------------------


def test_on_push_slope_calls_cavity_push(monkeypatch) -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    cavity = Mock()
    controller._cavity = cavity
    monkeypatch.setattr(controller_module, "Thread", _ThreadStub)

    controller.on_push_slope()

    cavity.push_ssa_slope.assert_called_once()
    assert any("SSA slope pushed" in msg for msg in view.logs)


def test_on_push_slope_logs_exception(monkeypatch) -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    cavity = Mock()
    cavity.push_ssa_slope.side_effect = RuntimeError("push fail")
    controller._cavity = cavity
    monkeypatch.setattr(controller_module, "Thread", _ThreadStub)

    controller.on_push_slope()

    assert any("Push failed" in msg for msg in view.logs)


def test_on_push_slope_no_cavity_logs_message() -> None:
    view = _ViewStub(cavity=None)
    _make_controller(view=view).on_push_slope()
    assert any("No cavity selected" in msg for msg in view.logs)


# ------------------------------------------------------------------
# on_plot
# ------------------------------------------------------------------


def test_on_plot_no_directory_logs_message(monkeypatch, tmp_path) -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller._cavity = Mock()
    controller._cavity.pv_prefix = "ACCL:L0B:0110:"
    monkeypatch.setattr(
        controller_module, "get_ssa_cal_base_dir", lambda: tmp_path
    )

    controller.on_plot()

    assert any("No SSA cal directory" in msg for msg in view.logs)


def test_on_plot_no_png_found(monkeypatch, tmp_path) -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller._cavity = Mock()
    controller._cavity.pv_prefix = "ACCL:L0B:0110:"
    monkeypatch.setattr(
        controller_module, "get_ssa_cal_base_dir", lambda: tmp_path
    )
    (tmp_path / "ACCL_L0B_0110" / "ACCL_L0B_0110_20251203_081722").mkdir(
        parents=True
    )

    controller.on_plot()

    assert any("No ssa_cal.png" in msg for msg in view.logs)


def test_on_plot_finds_most_recent_png_and_shows(monkeypatch, tmp_path) -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller._cavity = Mock()
    controller._cavity.pv_prefix = "ACCL:L0B:0110:"
    monkeypatch.setattr(
        controller_module, "get_ssa_cal_base_dir", lambda: tmp_path
    )
    subdir = tmp_path / "ACCL_L0B_0110" / "ACCL_L0B_0110_20251203_081722"
    subdir.mkdir(parents=True)
    png = subdir / "ssa_cal.png"
    png.write_bytes(b"")
    controller._show_plot = Mock()

    controller.on_plot()

    controller._show_plot.assert_called_once_with(png)


# ------------------------------------------------------------------
# _resolve_cavity
# ------------------------------------------------------------------


def test_resolve_cavity_returns_cached() -> None:
    controller = _make_controller()
    cavity = Mock()
    controller._cavity = cavity

    assert controller._resolve_cavity() is cavity


def test_resolve_cavity_looks_up_from_view() -> None:
    controller = _make_controller()
    mock_cavity = Mock()
    controller._parse_cavity_from_record = Mock(return_value=(2, 1))
    controller._get_machine_cavity = Mock(return_value=mock_cavity)

    result = controller._resolve_cavity()

    assert result is mock_cavity


def test_resolve_cavity_no_info_logs_and_returns_none() -> None:
    view = _ViewStub(cavity=None)
    controller = _make_controller(view=view)

    assert controller._resolve_cavity() is None
    assert "No cavity selected" in view.logs


# ------------------------------------------------------------------
# _append_measurement_history
# ------------------------------------------------------------------


def test_append_measurement_history_no_context_is_noop() -> None:
    session = Mock()
    controller = _make_controller(session=session)
    controller.context = None

    controller._append_measurement_history()

    session.add_measurement_to_history.assert_not_called()


def test_append_measurement_history_calls_session_with_instance_id() -> None:
    session = Mock()
    controller = _make_controller(session=session)
    controller.context = PhaseContext(
        record=_record_with_result(), operator="op"
    )
    controller._active_phase_instance_id = 42

    controller._append_measurement_history()

    kwargs = session.add_measurement_to_history.call_args[1]
    assert kwargs["phase_instance_id"] == 42
    assert kwargs["operator"] == "op"


def test_append_measurement_history_adds_error_note() -> None:
    session = Mock()
    controller = _make_controller(session=session)
    controller.context = PhaseContext(
        record=_record_with_result(), operator="op"
    )

    controller._append_measurement_history(error_msg="boom")

    kwargs = session.add_measurement_to_history.call_args[1]
    assert kwargs["notes"] == "Phase failed: boom"


# ------------------------------------------------------------------
# _auto_create_record
# ------------------------------------------------------------------


def test_auto_create_record_no_cavity_shows_error() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller._get_cavity_from_parent = Mock(return_value=(None, None))

    assert controller._auto_create_record() is False
    assert view.errors


def test_auto_create_record_success() -> None:
    session = Mock()
    session.start_new_record.return_value = (_record_with_result(), 10, True)
    view = _ViewStub()
    controller = _make_controller(view=view, session=session)
    controller._get_cavity_from_parent = Mock(return_value=("02", "1"))
    controller.update_pv_addresses = Mock()

    assert controller._auto_create_record() is True


def test_auto_create_record_exception_shows_error() -> None:
    session = Mock()
    session.start_new_record.side_effect = RuntimeError("db down")
    view = _ViewStub()
    controller = _make_controller(view=view, session=session)
    controller._get_cavity_from_parent = Mock(return_value=("02", "1"))

    assert controller._auto_create_record() is False
    assert view.errors


# ------------------------------------------------------------------
# _get_cavity_from_parent
# ------------------------------------------------------------------


class _Combo:
    def __init__(self, text):
        self._text = text

    def currentText(self):
        return self._text


class _ParentWithCombos:
    def __init__(self, cm="02", cav="1"):
        self.cryomodule_combo = _Combo(cm)
        self.cavity_combo = _Combo(cav)

    def parent(self):
        return None


def test_get_cavity_from_parent_returns_selection() -> None:
    controller = _make_controller()
    controller.view.parent = lambda: _ParentWithCombos(cm="02", cav="1")

    assert controller._get_cavity_from_parent() == ("02", "1")


def test_get_cavity_from_parent_empty_returns_none() -> None:
    controller = _make_controller()
    controller.view.parent = lambda: _ParentWithCombos(cm="", cav="")

    assert controller._get_cavity_from_parent() == (None, None)


def test_get_cavity_from_parent_no_parent_returns_none() -> None:
    controller = _make_controller()
    controller.view.parent = lambda: None

    assert controller._get_cavity_from_parent() == (None, None)
