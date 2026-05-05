"""Targeted tests for Piezo Pre-RF controller helpers."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import sc_linac_physics.applications.rf_commissioning.ui.controllers.piezo_pre_rf_controller as controller_module
from sc_linac_physics.applications.rf_commissioning.ui.controllers.piezo_pre_rf_controller import (
    PiezoPreRFController,
)
from sc_linac_physics.applications.rf_commissioning.models.commissioning_piezo import (
    CommissioningPiezo,
)
from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningRecord,
    PiezoPreRFCheck,
)
from sc_linac_physics.applications.rf_commissioning.phases.phase_base import (
    PhaseContext,
    PhaseResult,
    PhaseStepResult,
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
        selected_operator: str = "",
        cavity: tuple[str, str] | None = ("L1B_CM02_CAV1", "02"),
    ):
        self._current_operator = current_operator
        self._selected_operator = selected_operator
        self._cavity = cavity
        self.logs: list[str] = []
        self.errors: list[str] = []

        self.run_button = _ButtonStub()
        self.pause_button = _ButtonStub()
        self.abort_button = _ButtonStub()
        self.next_step_btn = _ButtonStub()
        self.local_phase_status = Mock()
        self.local_progress_bar = Mock()
        self.ui = SimpleNamespace(update_toolbar_state=Mock())
        self.step_progress_signal = SimpleNamespace(emit=Mock())
        self.update_piezo_readbacks = Mock()
        self._update_local_results = Mock()
        self._update_stored_readout = Mock()

    def get_current_operator(self) -> str:
        return self._current_operator

    def get_selected_operator(self) -> str:
        return self._selected_operator

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
    return PiezoPreRFController(view or _ViewStub(), session or Mock())


def _record_with_result() -> CommissioningRecord:
    record = CommissioningRecord(linac=1, cryomodule="02", cavity_number=1)
    record.piezo_pre_rf = PiezoPreRFCheck(
        capacitance_a=25.3e-9,
        capacitance_b=24.8e-9,
        channel_a_passed=True,
        channel_b_passed=True,
    )
    return record


def test_append_measurement_history_uses_active_phase_instance_id() -> None:
    session = Mock()
    controller = _make_controller(session=session)
    record = _record_with_result()
    controller.context = PhaseContext(record=record, operator="Test Operator")
    controller._active_phase_instance_id = 42

    controller._append_measurement_history()

    session.add_measurement_to_history.assert_called_once()
    args, kwargs = session.add_measurement_to_history.call_args
    assert kwargs["phase_instance_id"] == 42
    assert kwargs["operator"] == "Test Operator"
    assert args[1] is record.piezo_pre_rf


def test_append_measurement_history_adds_error_note() -> None:
    session = Mock()
    controller = _make_controller(session=session)
    controller.context = PhaseContext(
        record=_record_with_result(), operator="op"
    )

    controller._append_measurement_history(error_msg="boom")

    kwargs = session.add_measurement_to_history.call_args[1]
    assert kwargs["notes"] == "Phase failed: boom"


def test_append_measurement_history_no_context_is_noop() -> None:
    session = Mock()
    controller = _make_controller(session=session)
    controller.context = None

    controller._append_measurement_history()

    session.add_measurement_to_history.assert_not_called()


def test_get_machine_cavity_builds_machine_with_commissioning_piezo(
    monkeypatch,
) -> None:
    class _MachineStub:
        def __init__(self, *, piezo_class):
            self.piezo_class = piezo_class
            self.cryomodules = {
                "02": SimpleNamespace(cavities={1: "cavity-object"})
            }

    monkeypatch.setattr(controller_module, "Machine", _MachineStub)
    controller = _make_controller()

    cavity = controller._get_machine_cavity(2, 1)

    assert cavity == "cavity-object"
    assert isinstance(controller.machine, _MachineStub)
    assert controller.machine.piezo_class is CommissioningPiezo


def test_get_operator_falls_back_to_legacy_selector() -> None:
    view = _ViewStub(current_operator="", selected_operator="Legacy Operator")
    controller = _make_controller(view=view)

    assert controller._get_operator() == "Legacy Operator"


def test_update_pv_addresses_no_selection_logs_message() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller._resolve_cavity_selection = Mock(return_value=(None, None))

    controller.update_pv_addresses()

    assert "No cavity selected" in view.logs


def test_update_pv_addresses_parse_error_logs_message() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller._resolve_cavity_selection = Mock(return_value=("02", "bad"))
    controller._get_piezo_from_selection = Mock(side_effect=ValueError("bad"))

    controller.update_pv_addresses()

    assert any("Error parsing cavity info" in msg for msg in view.logs)


def test_update_pv_addresses_success_runs_mapping_and_sync() -> None:
    controller = _make_controller()
    controller._resolve_cavity_selection = Mock(return_value=("02", "1"))
    controller._get_piezo_from_selection = Mock(return_value=(Mock(), 2, 1))
    controller._build_pv_mapping = Mock(return_value={"k": Mock()})
    controller._apply_pv_mapping = Mock()
    controller._log_pv_update = Mock()
    controller._sync_piezo_readbacks = Mock()

    controller.update_pv_addresses()

    controller._apply_pv_mapping.assert_called_once()
    controller._log_pv_update.assert_called_once_with("02", "1", 2, 1)
    controller._sync_piezo_readbacks.assert_called_once()


def test_get_selected_cavity_info_handles_missing_cavity() -> None:
    view = _ViewStub(cavity=None)
    controller = _make_controller(view=view)

    assert controller._get_selected_cavity_info() is None
    assert "Unable to determine cavity information" in view.errors[0]


def test_get_selected_cavity_info_handles_parse_error() -> None:
    view = _ViewStub(cavity=("bad-format", "02"))
    controller = _make_controller(view=view)
    controller._parse_cavity_from_record = Mock(side_effect=ValueError())

    assert controller._get_selected_cavity_info() is None
    assert "Invalid cavity name format" in view.errors[0]


def test_get_selected_cavity_info_returns_parsed_values() -> None:
    controller = _make_controller()
    controller._parse_cavity_from_record = Mock(return_value=(2, 1))

    result = controller._get_selected_cavity_info()

    assert result == ("L1B_CM02_CAV1", 2, 1)


def test_execute_step_with_retries_success_calls_success_handler() -> None:
    controller = _make_controller()
    controller.phase = Mock()
    controller.phase.execute_step.return_value = PhaseStepResult(
        result=PhaseResult.SUCCESS,
        message="ok",
    )
    controller._create_step_checkpoint = Mock()
    controller._handle_step_success = Mock(return_value=True)

    result = controller._execute_step_with_retries("setup_piezo", max_retries=3)

    assert result is True
    controller._create_step_checkpoint.assert_called_once()
    controller._handle_step_success.assert_called_once()


def test_execute_step_with_retries_retry_exhausted_returns_false() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller.phase = Mock()
    controller.phase.execute_step.return_value = PhaseStepResult(
        result=PhaseResult.RETRY,
        message="try again",
    )
    controller._create_step_checkpoint = Mock()

    result = controller._execute_step_with_retries("validate", max_retries=2)

    assert result is False
    assert any("Failed after 2 retries" in msg for msg in view.logs)


def test_execute_step_with_retries_failed_result_returns_false() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller.phase = Mock()
    controller.phase.execute_step.return_value = PhaseStepResult(
        result=PhaseResult.FAILED,
        message="bad",
    )
    controller._create_step_checkpoint = Mock()

    result = controller._execute_step_with_retries("validate", max_retries=2)

    assert result is False
    assert any("validate failed" in msg for msg in view.logs)


def test_execute_step_with_retries_exception_exhausted_returns_false() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller.phase = Mock()
    controller.phase.execute_step.side_effect = RuntimeError("rpc down")

    result = controller._execute_step_with_retries("validate", max_retries=2)

    assert result is False
    assert any("Exception after 2 retries" in msg for msg in view.logs)


def test_on_phase_run_finished_routes_to_completed_handler() -> None:
    controller = _make_controller()
    controller._sync_piezo_readbacks = Mock()
    controller.on_phase_completed = Mock()
    controller.on_phase_failed = Mock()

    controller._on_phase_run_finished(True, "")

    controller._sync_piezo_readbacks.assert_called_once()
    controller.on_phase_completed.assert_called_once()
    controller.on_phase_failed.assert_not_called()


def test_on_phase_run_finished_uses_default_error_message() -> None:
    controller = _make_controller()
    controller._sync_piezo_readbacks = Mock()
    controller.on_phase_completed = Mock()
    controller.on_phase_failed = Mock()

    controller._on_phase_run_finished(False, "")

    controller.on_phase_failed.assert_called_once_with("Phase execution failed")


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


def test_on_pause_test_toggles_pause_state_and_button_text() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)

    controller.on_pause_test()
    assert controller._paused is True
    assert view.pause_button.text == "\u25b6 Resume"

    controller.on_pause_test()
    assert controller._paused is False
    assert view.pause_button.text == "\u23f8 Pause"


def test_set_next_button_enabled_no_next_step_button_is_safe() -> None:
    controller = PiezoPreRFController(SimpleNamespace(), Mock())
    controller._set_next_button_enabled(True)


@pytest.mark.parametrize(
    "view_like",
    [SimpleNamespace(), SimpleNamespace(ui=SimpleNamespace())],
)
def test_update_toolbar_state_without_handler_is_safe(view_like) -> None:
    controller = PiezoPreRFController(view_like, Mock())
    controller._update_toolbar_state("running")


def test_setup_pv_connections_updates_when_active_record_exists() -> None:
    session = Mock()
    session.has_active_record.return_value = True
    controller = _make_controller(session=session)
    controller.update_pv_addresses = Mock()

    controller.setup_pv_connections()

    controller.update_pv_addresses.assert_called_once()


def test_resolve_and_get_piezo_wrappers(monkeypatch) -> None:
    controller = _make_controller()
    piezo = Mock()

    monkeypatch.setattr(
        controller_module,
        "resolve_cavity_selection",
        lambda view, cm, cav: ("02", "1"),
    )
    monkeypatch.setattr(
        controller_module,
        "get_piezo_from_selection",
        lambda machine, cm, cav: (piezo, 2, 1, "machine-obj"),
    )

    assert controller._resolve_cavity_selection(None, None) == ("02", "1")
    result = controller._get_piezo_from_selection("02", "1")
    assert result == (piezo, 2, 1)
    assert controller.machine == "machine-obj"


def test_update_pv_addresses_generic_error_logs_message() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller._resolve_cavity_selection = Mock(return_value=("02", "1"))
    controller._get_piezo_from_selection = Mock(
        side_effect=RuntimeError("oops")
    )

    controller.update_pv_addresses()

    assert any("Error setting PVs" in msg for msg in view.logs)


def test_update_pv_addresses_mapping_error_logs_message() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller._resolve_cavity_selection = Mock(return_value=("02", "1"))
    controller._get_piezo_from_selection = Mock(return_value=(Mock(), 2, 1))
    controller._build_pv_mapping = Mock(side_effect=RuntimeError("map fail"))

    controller.update_pv_addresses()

    assert any("Error setting PVs" in msg for msg in view.logs)


def test_build_apply_log_wrappers_delegate(monkeypatch) -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    piezo = Mock()
    called = {"apply": False}

    monkeypatch.setattr(
        controller_module,
        "build_pv_mapping",
        lambda in_view, in_piezo: {"ok": (in_view, in_piezo)},
    )
    monkeypatch.setattr(
        controller_module,
        "apply_pv_mapping",
        lambda mapping: called.__setitem__("apply", bool(mapping)),
    )
    monkeypatch.setattr(
        controller_module,
        "format_pv_update_message",
        lambda cm, cav, cm_i, cav_i: f"{cm}-{cav}-{cm_i}-{cav_i}",
    )

    mapping = controller._build_pv_mapping(piezo)
    controller._apply_pv_mapping(mapping)
    controller._log_pv_update("02", "1", 2, 1)

    assert called["apply"] is True
    assert view.logs[-1] == "02-1-2-1"


def test_sync_piezo_readbacks_branches() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    piezo = Mock()

    controller._sync_piezo_readbacks(piezo)
    view.update_piezo_readbacks.assert_called_once_with(piezo)

    controller._resolve_cavity_selection = Mock(return_value=("02", "1"))
    controller._get_piezo_from_selection = Mock(return_value=(piezo, 2, 1))
    controller._sync_piezo_readbacks(None)
    assert controller._get_piezo_from_selection.called


def test_sync_piezo_readbacks_error_and_no_handler_paths() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller._resolve_cavity_selection = Mock(return_value=("02", "1"))
    controller._get_piezo_from_selection = Mock(
        side_effect=RuntimeError("rb fail")
    )

    controller._sync_piezo_readbacks(None)
    assert any("Readback sync failed" in msg for msg in view.logs)

    controller_no_hook = PiezoPreRFController(SimpleNamespace(), Mock())
    controller_no_hook._sync_piezo_readbacks(Mock())


def test_parse_cavity_from_record() -> None:
    controller = _make_controller()
    assert controller._parse_cavity_from_record("L1B_CM02_CAV8", "02") == (2, 8)
    assert controller._parse_cavity_from_record("SHORT", "02") == (2, 1)


def test_prepare_phase_context_can_run_false() -> None:
    view = _ViewStub()
    session = Mock()
    session.get_active_record.return_value = _record_with_result()
    session.get_active_record_id.return_value = 7
    session.can_run_phase.return_value = (False, "blocked")
    controller = _make_controller(view=view, session=session)

    ok = controller._prepare_phase_context(Mock(), "op")

    assert ok is False
    assert any("ERROR: blocked" in msg for msg in view.logs)


def test_prepare_phase_context_prerequisites_fail(monkeypatch) -> None:
    view = _ViewStub()
    session = Mock()
    session.get_active_record.return_value = _record_with_result()
    session.get_active_record_id.return_value = 7
    session.can_run_phase.return_value = (True, "")
    session.start_active_phase_instance.return_value = SimpleNamespace(
        phase_instance_id=99
    )

    class _PhaseStub:
        def __init__(self, context):
            self.context = context

        def validate_prerequisites(self):
            return (False, "bad state")

    monkeypatch.setattr(controller_module, "PiezoPreRFPhase", _PhaseStub)
    controller = _make_controller(view=view, session=session)

    ok = controller._prepare_phase_context(Mock(), "op")

    assert ok is False
    assert any("ERROR: bad state" in msg for msg in view.logs)


def test_prepare_phase_context_success_without_record_id(monkeypatch) -> None:
    session = Mock()
    session.get_active_record.return_value = _record_with_result()
    session.get_active_record_id.return_value = None
    session.can_run_phase.return_value = (True, "")

    class _PhaseStub:
        def __init__(self, context):
            self.context = context

        def validate_prerequisites(self):
            return (True, "ok")

    monkeypatch.setattr(controller_module, "PiezoPreRFPhase", _PhaseStub)
    controller = _make_controller(session=session)

    ok = controller._prepare_phase_context(Mock(), "op")

    assert ok is True
    assert controller._active_phase_instance_id is None


def test_set_running_ui_state_sets_expected_controls() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)

    controller._set_running_ui_state()

    assert view.run_button.enabled is False
    assert view.pause_button.enabled is True
    assert view.abort_button.enabled is True
    view.local_phase_status.setText.assert_called_once_with("RUNNING")


def test_on_run_automated_test_no_operator_focuses_parent() -> None:
    view = _ViewStub(current_operator="")
    controller = _make_controller(view=view)
    controller._focus_parent_widget = Mock()

    controller.on_run_automated_test()

    controller._focus_parent_widget.assert_called_once_with("operator_combo")


def test_on_run_automated_test_stops_when_auto_create_fails() -> None:
    session = Mock()
    session.has_active_record.return_value = False
    controller = _make_controller(session=session)
    controller._auto_create_record = Mock(return_value=False)

    controller.on_run_automated_test()

    controller._auto_create_record.assert_called_once()


def test_on_run_automated_test_stops_when_no_cavity() -> None:
    session = Mock()
    session.has_active_record.return_value = True
    controller = _make_controller(session=session)
    controller._get_selected_cavity_info = Mock(return_value=None)

    controller.on_run_automated_test()

    controller._get_selected_cavity_info.assert_called_once()


def test_on_run_automated_test_success_path() -> None:
    view = _ViewStub()
    session = Mock()
    session.has_active_record.return_value = True
    controller = _make_controller(view=view, session=session)
    controller._get_selected_cavity_info = Mock(
        return_value=("L1B_CM02_CAV1", 2, 1)
    )
    controller.update_pv_addresses = Mock()
    controller._get_machine_cavity = Mock(return_value=Mock())
    controller._prepare_phase_context = Mock(return_value=True)
    controller._set_running_ui_state = Mock()
    controller.execute_phase_steps = Mock()

    controller.on_run_automated_test()

    controller.update_pv_addresses.assert_called_once_with("02", "1")
    controller._set_running_ui_state.assert_called_once()
    controller.execute_phase_steps.assert_called_once()


def test_on_run_automated_test_exception_is_logged() -> None:
    view = _ViewStub()
    session = Mock()
    session.has_active_record.return_value = True
    controller = _make_controller(view=view, session=session)
    controller._get_selected_cavity_info = Mock(
        return_value=("L1B_CM02_CAV1", 2, 1)
    )
    controller.update_pv_addresses = Mock(side_effect=RuntimeError("kaboom"))

    controller.on_run_automated_test()

    assert any("Failed to start test" in msg for msg in view.errors)


def test_auto_create_record_paths(monkeypatch) -> None:
    view = _ViewStub()
    session = Mock()
    controller = _make_controller(view=view, session=session)

    controller._get_cavity_from_parent = Mock(return_value=(None, None))
    controller._focus_parent_widget = Mock()
    assert controller._auto_create_record() is False

    controller._get_cavity_from_parent = Mock(return_value=("02", "1"))
    session.start_new_record.return_value = (_record_with_result(), 10, True)
    controller._notify_parent_record_created = Mock()
    controller.update_pv_addresses = Mock()
    assert controller._auto_create_record() is True

    session.start_new_record.return_value = (_record_with_result(), 10, False)
    assert controller._auto_create_record() is True

    controller._get_cavity_from_parent = Mock(return_value=("02", "1"))
    session.start_new_record.side_effect = RuntimeError("db down")
    assert controller._auto_create_record() is False


class _Combo:
    def __init__(self, text):
        self._text = text

    def currentText(self):
        return self._text


class _ParentWithCavitySelection:
    def __init__(self, cm="02", cav="1"):
        self.cryomodule_combo = _Combo(cm)
        self.cavity_combo = _Combo(cav)

    def parent(self):
        return None


class _BrokenCombo:
    def currentText(self):
        raise RuntimeError("bad parent")


class _BadParentWithBrokenCombos:
    def __init__(self):
        self.cryomodule_combo = _BrokenCombo()
        self.cavity_combo = _BrokenCombo()

    def parent(self):
        return None


class _FocusableParent:
    def __init__(self):
        self.operator_combo = SimpleNamespace(setFocus=Mock())

    def parent(self):
        return None


class _ChainParent:
    def __init__(self, parent_obj):
        self._parent_obj = parent_obj

    def parent(self):
        return self._parent_obj


def test_get_cavity_from_parent_returns_selected_cm_and_cavity() -> None:
    controller = _make_controller()
    view = _ViewStub()
    view.parent = lambda: _ParentWithCavitySelection(cm="02", cav="1")
    controller.view = view

    assert controller._get_cavity_from_parent() == ("02", "1")


def test_get_cavity_from_parent_returns_none_when_selection_empty() -> None:
    controller = _make_controller()
    view = _ViewStub()
    view.parent = lambda: _ParentWithCavitySelection(cm="", cav="")
    controller.view = view

    assert controller._get_cavity_from_parent() == (None, None)


def test_get_cavity_from_parent_returns_none_when_parent_combo_fails() -> None:
    controller = _make_controller()
    view = _ViewStub()
    view.parent = lambda: _BadParentWithBrokenCombos()
    controller.view = view

    assert controller._get_cavity_from_parent() == (None, None)


def test_focus_parent_widget_focuses_direct_parent_attribute() -> None:
    controller = _make_controller()
    view = _ViewStub()
    focus_parent = _FocusableParent()
    view.parent = lambda: focus_parent
    controller.view = view

    controller._focus_parent_widget("operator_combo")

    focus_parent.operator_combo.setFocus.assert_called_once()


def test_focus_parent_widget_traverses_parent_chain() -> None:
    controller = _make_controller()
    view = _ViewStub()
    focus_parent = _FocusableParent()
    view.parent = lambda: _ChainParent(focus_parent)
    controller.view = view

    controller._focus_parent_widget("operator_combo")

    focus_parent.operator_combo.setFocus.assert_called_once()


def test_on_run_automated_test_stops_when_prepare_context_fails() -> None:
    session = Mock()
    session.has_active_record.return_value = True
    controller = _make_controller(session=session)
    controller._get_selected_cavity_info = Mock(
        return_value=("L1B_CM02_CAV1", 2, 1)
    )
    controller.update_pv_addresses = Mock()
    controller._get_machine_cavity = Mock(return_value=Mock())
    controller._prepare_phase_context = Mock(return_value=False)
    controller.execute_phase_steps = Mock()

    controller.on_run_automated_test()

    controller.execute_phase_steps.assert_not_called()


def test_execute_phase_steps_paths(monkeypatch) -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)

    controller.context = None
    controller.phase = None
    controller.execute_phase_steps()
    assert "No phase context available" in view.errors[-1]

    controller.context = PhaseContext(
        record=_record_with_result(), operator="op"
    )
    controller.phase = Mock()
    controller.phase.get_phase_steps.return_value = ["a"]
    controller._step_mode = True
    controller._set_next_button_enabled = Mock()
    monkeypatch.setattr(
        controller_module.QTimer, "singleShot", lambda _ms, fn: fn()
    )

    controller.execute_phase_steps()
    controller._set_next_button_enabled.assert_called_once_with(True)

    controller._step_mode = False
    controller._run_phase_in_background = Mock(
        side_effect=RuntimeError("run boom")
    )
    controller.on_phase_failed = Mock()
    controller.execute_phase_steps()
    controller.on_phase_failed.assert_called_once_with("run boom")


def test_run_phase_in_background_worker_paths(monkeypatch) -> None:
    controller = _make_controller()
    controller.phase = Mock()
    controller.phase.get_phase_steps.return_value = ["step"]
    controller._check_pause_and_abort = Mock(return_value=False)

    class _ThreadStub:
        def __init__(self, target, daemon):
            self.target = target

        def start(self):
            self.target()

    monkeypatch.setattr(controller_module, "Thread", _ThreadStub)
    controller._run_phase_in_background()

    controller = _make_controller()
    controller.phase = Mock()
    controller.phase.get_phase_steps.return_value = ["step"]
    controller.phase._execute_step_with_retry.return_value = False
    controller._check_pause_and_abort = Mock(return_value=True)
    monkeypatch.setattr(controller_module, "Thread", _ThreadStub)
    emitted = []
    controller.phase_run_finished.connect(
        lambda ok, msg: emitted.append((ok, msg))
    )
    controller._run_phase_in_background()
    assert emitted[-1] == (False, "Step failed: step")

    controller = _make_controller()
    controller.phase = Mock()
    controller.phase.get_phase_steps.side_effect = RuntimeError("worker fail")
    monkeypatch.setattr(controller_module, "Thread", _ThreadStub)
    emitted = []
    controller.phase_run_finished.connect(
        lambda ok, msg: emitted.append((ok, msg))
    )
    controller._run_phase_in_background()
    assert emitted[-1] == (False, "worker fail")

    controller = _make_controller()
    controller.phase = Mock()
    controller.phase.get_phase_steps.return_value = ["step"]
    controller.phase._execute_step_with_retry.return_value = True
    controller._check_pause_and_abort = Mock(return_value=True)
    controller._finalize_background_phase = Mock()
    monkeypatch.setattr(controller_module, "Thread", _ThreadStub)
    controller._run_phase_in_background()
    controller._finalize_background_phase.assert_called_once()


def test_check_pause_and_abort_paths(monkeypatch) -> None:
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

    controller = _make_controller()
    assert controller._check_pause_and_abort() is True


def test_finalize_background_phase_paths() -> None:
    controller = _make_controller()
    controller.phase = Mock()
    emitted = []
    controller.phase_run_finished.connect(
        lambda ok, msg: emitted.append((ok, msg))
    )
    controller._finalize_background_phase()
    assert emitted[-1] == (True, "")

    controller = _make_controller()
    controller.phase = Mock()
    controller.phase.finalize_phase.side_effect = RuntimeError("finalize fail")
    emitted = []
    controller.phase_run_finished.connect(
        lambda ok, msg: emitted.append((ok, msg))
    )
    controller._finalize_background_phase()
    assert emitted[-1] == (False, "finalize fail")


def test_execute_single_step_and_wait_notify_helpers(monkeypatch) -> None:
    controller = _make_controller()
    controller._wait_for_unpause = Mock(return_value=False)
    assert controller._execute_single_step("step") is False

    view = _ViewStub()
    controller = _make_controller(view=view)
    controller._wait_for_unpause = Mock(return_value=True)
    controller.context = PhaseContext(
        record=_record_with_result(), operator="op"
    )
    controller.context.request_abort()
    assert controller._execute_single_step("step") is False
    assert any("Abort during step" in msg for msg in view.logs)

    controller = _make_controller()
    controller._wait_for_unpause = Mock(return_value=True)
    controller._notify_step_progress = Mock()
    controller._execute_step_with_retries = Mock(return_value=True)
    assert controller._execute_single_step("step") is True

    controller = _make_controller()
    assert controller._wait_for_unpause() is True
    controller._paused = True
    calls = {"n": 0}
    monkeypatch.setattr(
        controller_module.QTimer, "singleShot", lambda _ms, fn: fn()
    )

    def _sleep(_):
        calls["n"] += 1
        if calls["n"] == 1:
            controller._paused = False

    monkeypatch.setitem(
        __import__("sys").modules, "time", SimpleNamespace(sleep=_sleep)
    )
    assert controller._wait_for_unpause() is True

    events = []
    controller.context = PhaseContext(
        record=_record_with_result(), operator="op"
    )
    controller.context.progress_callback = lambda step, prog: events.append(
        (step, prog)
    )
    controller._steps = ["a", "b"]
    controller._notify_step_progress("b")
    controller._notify_step_progress("x")
    assert events[0] == ("b", 50)
    assert events[1] == ("x", 0)


def test_execute_step_with_retries_skip_and_retry_then_success() -> None:
    controller = _make_controller()
    controller.phase = Mock()
    controller.phase.execute_step.return_value = PhaseStepResult(
        result=PhaseResult.SKIP,
        message="skip",
    )
    controller._create_step_checkpoint = Mock()
    controller._handle_step_success = Mock(return_value=True)
    assert controller._execute_step_with_retries("step", 2) is True

    controller = _make_controller(view=_ViewStub())
    controller.phase = Mock()
    controller.phase.execute_step.side_effect = [
        PhaseStepResult(result=PhaseResult.RETRY, message="retry"),
        PhaseStepResult(result=PhaseResult.SUCCESS, message="ok"),
    ]
    controller._create_step_checkpoint = Mock()
    controller._handle_step_success = Mock(return_value=True)
    assert controller._execute_step_with_retries("step", 3) is True


def test_execute_step_with_retries_zero_retries_returns_false() -> None:
    controller = _make_controller()
    controller.phase = Mock()
    assert controller._execute_step_with_retries("step", 0) is False


def test_create_checkpoint_and_handle_step_success_paths() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    record = _record_with_result()
    record.phase_history = []
    controller.context = PhaseContext(record=record, operator="op")
    controller.phase = Mock()
    controller.phase.phase_type = "PHASE"

    result = PhaseStepResult(
        result=PhaseResult.SUCCESS, message="done", data={"a": 1}
    )
    controller._create_step_checkpoint("step", result)
    assert len(record.phase_history) == 1

    controller._sync_piezo_readbacks = Mock()
    assert controller._handle_step_success("setup_piezo", result) is True
    controller._sync_piezo_readbacks.assert_called_once()

    skip = PhaseStepResult(result=PhaseResult.SKIP, message="skip")
    assert controller._handle_step_success("validate", skip) is True


def test_finalize_phase_execution_paths() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller.phase = Mock()
    controller.context = PhaseContext(
        record=_record_with_result(), operator="op"
    )
    controller.on_phase_completed = Mock()
    controller._finalize_phase_execution()
    controller.on_phase_completed.assert_called_once()

    controller = _make_controller(view=_ViewStub())
    controller.phase = Mock()
    rec = _record_with_result()
    rec.piezo_pre_rf = None
    controller.context = PhaseContext(record=rec, operator="op")
    controller.on_phase_completed = Mock()
    controller._finalize_phase_execution()
    assert any("not populated" in msg for msg in controller.view.logs)

    controller = _make_controller(view=_ViewStub())
    controller.phase = Mock()
    controller.phase.finalize_phase.side_effect = RuntimeError("boom")
    controller.context = PhaseContext(
        record=_record_with_result(), operator="op"
    )
    controller.on_phase_failed = Mock()
    controller._finalize_phase_execution()
    controller.on_phase_failed.assert_called_once_with("boom")


def test_on_phase_completed_paths() -> None:
    view = _ViewStub()
    session = Mock()
    session.complete_active_phase_instance.return_value = True
    session.has_active_record.return_value = True
    session.get_active_record.return_value = SimpleNamespace(
        current_phase=SimpleNamespace(value="NEXT")
    )
    session.save_active_record.return_value = True
    session.get_active_record_id.return_value = 77
    controller = _make_controller(view=view, session=session)
    controller.context = PhaseContext(
        record=_record_with_result(), operator="op"
    )
    controller._active_phase_instance_id = 3
    captured = []
    controller.phase_completed.connect(lambda rec: captured.append(rec))
    controller._append_measurement_history = Mock()

    controller.on_phase_completed()

    assert controller._active_phase_instance_id is None
    assert view.run_button.enabled is True
    assert captured

    view2 = _ViewStub()
    session2 = Mock()
    session2.complete_active_phase_instance.return_value = False
    session2.save_active_record.return_value = False
    controller2 = _make_controller(view=view2, session=session2)
    controller2.context = PhaseContext(
        record=_record_with_result(), operator="op"
    )
    controller2._active_phase_instance_id = 5
    controller2.on_phase_completed()
    assert any("Warning: Failed to advance" in msg for msg in view2.logs)
    assert any("Warning: Failed to save" in msg for msg in view2.logs)

    view3 = _ViewStub()
    controller3 = _make_controller(view=view3, session=Mock())
    rec = _record_with_result()
    rec.piezo_pre_rf = None
    controller3.context = PhaseContext(record=rec, operator="op")
    controller3.on_phase_completed()
    assert any("No piezo_pre_rf" in msg for msg in view3.logs)


def test_on_phase_completed_exception_fails_active_phase() -> None:
    view = _ViewStub()
    session = Mock()
    session.complete_active_phase_instance.side_effect = RuntimeError(
        "svc down"
    )
    controller = _make_controller(view=view, session=session)
    controller.context = PhaseContext(
        record=_record_with_result(), operator="op"
    )
    controller._active_phase_instance_id = 11

    controller.on_phase_completed()

    session.fail_active_phase_instance.assert_called_once()


def test_on_phase_failed_paths() -> None:
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

    session.fail_active_phase_instance.assert_called_once()
    assert view.run_button.enabled is True
    assert view.pause_button.enabled is False
    assert view.abort_button.enabled is False

    view2 = _ViewStub()
    session2 = Mock()
    controller2 = _make_controller(view=view2, session=session2)
    controller2.phase = Mock()
    rec = _record_with_result()
    rec.piezo_pre_rf = None
    controller2.context = PhaseContext(record=rec, operator="op")
    controller2._active_phase_instance_id = 4
    controller2.on_phase_failed("bad2")
    kwargs = session2.fail_active_phase_instance.call_args[1]
    assert kwargs["artifact_payload"] is None


def test_on_phase_failed_exception_branch() -> None:
    view = _ViewStub()
    session = Mock()
    session.save_active_record.side_effect = RuntimeError("db exploded")
    controller = _make_controller(view=view, session=session)
    controller.phase = Mock()
    controller.context = PhaseContext(
        record=_record_with_result(), operator="op"
    )
    controller._active_phase_instance_id = 10

    controller.on_phase_failed("orig")

    session.fail_active_phase_instance.assert_called_once()


def test_get_operator_empty_when_no_methods() -> None:
    controller = PiezoPreRFController(SimpleNamespace(), Mock())
    assert controller._get_operator() == ""


def test_on_abort_without_context_is_noop() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller.context = None
    controller.on_abort()
    assert view.abort_button.enabled is True


def test_set_next_button_enabled_and_update_toolbar_positive_paths() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller._set_next_button_enabled(True)
    assert view.next_step_btn.enabled is True

    controller._update_toolbar_state("running")
    view.ui.update_toolbar_state.assert_called_once_with("running")


def test_toggle_step_mode_and_next_step_paths(monkeypatch) -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller._set_next_button_enabled = Mock()

    controller.on_toggle_step_mode()
    assert controller._step_mode is True

    controller.on_toggle_step_mode()
    assert controller._step_mode is False
    controller._set_next_button_enabled.assert_called_with(False)

    controller._step_mode = False
    controller._step_executing = False
    controller.on_next_step()

    controller._step_mode = True
    controller._step_executing = True
    controller.on_next_step()

    controller._step_executing = False
    controller._steps = ["a"]
    controller._current_step_index = 1
    controller.on_next_step()
    assert any("All steps completed" in msg for msg in view.logs)

    monkeypatch.setattr(
        controller_module.QTimer, "singleShot", lambda _ms, fn: fn()
    )
    controller._current_step_index = 0
    controller._steps = ["a", "b"]
    controller._execute_single_step = Mock(return_value=True)
    controller._set_next_button_enabled = Mock()
    controller.on_next_step()
    assert controller._current_step_index == 1

    controller._steps = ["a"]
    controller._current_step_index = 0
    controller._execute_single_step = Mock(return_value=True)
    controller._finalize_phase_execution = Mock()
    controller.on_next_step()
    controller._finalize_phase_execution.assert_called_once()

    controller._steps = ["a"]
    controller._current_step_index = 0
    controller._execute_single_step = Mock(return_value=False)
    controller.on_phase_failed = Mock()
    controller.on_next_step()
    controller.on_phase_failed.assert_called_once_with("Step execution failed")

    controller._steps = ["a"]
    controller._current_step_index = 0
    controller._execute_single_step = Mock(
        side_effect=RuntimeError("step kaboom")
    )
    controller.on_phase_failed = Mock()
    controller.on_next_step()
    controller.on_phase_failed.assert_called_once_with("step kaboom")


def test_notify_parent_record_created_logs_message() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    record = _record_with_result()

    controller._notify_parent_record_created(record, 1)

    assert any("Notified parent container" in msg for msg in view.logs)


def test_get_cavity_from_parent_returns_none_when_no_matching_parent() -> None:
    controller = _make_controller()

    class _NoCombos:
        def parent(self):
            return None

    controller.view.parent = lambda: _NoCombos()

    assert controller._get_cavity_from_parent() == (None, None)
