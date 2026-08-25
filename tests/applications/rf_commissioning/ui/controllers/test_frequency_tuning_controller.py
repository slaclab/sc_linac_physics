"""Targeted tests for the Frequency Tuning controller."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import sc_linac_physics.applications.rf_commissioning.ui.controllers.frequency_tuning_controller as controller_module  # noqa: E501
from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningRecord,
    FrequencyTuningData,
)
from sc_linac_physics.applications.rf_commissioning.ui.builders.stage_status import (
    PUSH_DF_COLD_ATTENTION,
    PUSH_DF_COLD_NEUTRAL,
)
from sc_linac_physics.applications.rf_commissioning.ui.cold_landing_dialog import (
    ColdLandingChoice,
    SOURCE_ENTERED,
    SOURCE_MEASURED,
)
from sc_linac_physics.applications.rf_commissioning.phases.phase_base import (
    PhaseContext,
    PhaseResult,
    PhaseStepResult,
)
from sc_linac_physics.applications.rf_commissioning.ui.controllers.frequency_tuning_controller import (  # noqa: E501
    FrequencyTuningController,
)


class _ButtonStub:
    def __init__(self):
        self.enabled = True
        self.text = ""
        self.style = ""
        self.visible = True

    def setEnabled(self, enabled: bool) -> None:
        self.enabled = enabled

    def setText(self, text: str) -> None:
        self.text = text

    def setStyleSheet(self, style: str) -> None:
        self.style = style

    def setVisible(self, visible: bool) -> None:
        self.visible = visible

    def setToolTip(self, tip: str) -> None:
        self.tooltip = tip


class _SpinboxStub:
    def __init__(self, value: float = 0.0):
        self._value = value
        self.enabled = True

    def value(self) -> float:
        return self._value

    def setValue(self, value: float) -> None:
        self._value = value

    def setEnabled(self, enabled: bool) -> None:
        self.enabled = enabled

    def blockSignals(self, _block: bool) -> None:
        return None


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
        self.stage1_run_btn = _ButtonStub()
        self.stage2_run_btn = _ButtonStub()
        self.stage3_run_btn = _ButtonStub()
        self.stage4_run_btn = _ButtonStub()
        self.stage1_status_label = _ButtonStub()
        self.stage2_status_label = _ButtonStub()
        self.stage3_status_label = _ButtonStub()
        self.stage4_status_label = _ButtonStub()
        self.confirm_probe_fit_button = _ButtonStub()
        self.hz_per_step_spinbox = _SpinboxStub()
        self.speed_spinbox = _SpinboxStub(value=2.0)

        self.local_phase_status = Mock()
        self.local_progress_bar = Mock()
        self.ui = SimpleNamespace(update_toolbar_state=Mock())
        self.step_progress_signal = SimpleNamespace(emit=Mock())
        self.tuning_data_signal = SimpleNamespace(emit=Mock())
        self._update_local_results = Mock()
        self._update_stored_readout = Mock()
        self.show_probe_fit = Mock()

    def get_current_operator(self) -> str:
        return self._current_operator

    def get_current_cavity(self):
        return self._cavity

    def log_message(
        self, message: str, entry_type: str = "info", key: str | None = None
    ) -> None:
        # Mirrors PhaseDisplayBase.log_message, which takes entry_type/key.
        self.logs.append(message)

    def show_error(self, message: str) -> None:
        self.errors.append(message)

    def clear_results(self) -> None:
        return None

    def reset_plot(self) -> None:
        return None

    def parent(self):
        return None

    def _notify_parent_of_record_update(self, record, message: str) -> None:
        return None


def _make_controller(view=None, session=None):
    return FrequencyTuningController(view or _ViewStub(), session or Mock())


def _record() -> CommissioningRecord:
    record = CommissioningRecord(linac=1, cryomodule="02", cavity_number=1)
    return record


class _ThreadStub:
    """Runs the target synchronously on .start()."""

    def __init__(self, target, args=(), daemon=False):
        self.target = target
        self.args = args

    def start(self):
        self.target(*self.args)


@pytest.fixture(autouse=True)
def _fast_and_deterministic(monkeypatch):
    """No real sleeps, no real threads, no deferred timers."""
    monkeypatch.setattr(controller_module.time, "sleep", lambda *_: None)
    monkeypatch.setattr(
        controller_module.QTimer, "singleShot", lambda _ms, fn: fn()
    )
    monkeypatch.setattr(controller_module, "Thread", _ThreadStub)


# ------------------------------------------------------------------
# Helpers / getters
# ------------------------------------------------------------------


def test_get_operator_returns_value() -> None:
    view = _ViewStub(current_operator="Alice")
    assert _make_controller(view=view)._get_operator() == "Alice"


def test_get_operator_empty_when_no_method() -> None:
    controller = FrequencyTuningController(SimpleNamespace(), Mock())
    assert controller._get_operator() == ""


def test_get_hz_per_step_from_view_uses_method() -> None:
    view = _ViewStub()
    view.get_current_hz_per_step = lambda: 1.25
    assert _make_controller(view=view)._get_hz_per_step_from_view() == 1.25


def test_get_hz_per_step_from_view_uses_spinbox() -> None:
    view = _ViewStub()
    view.hz_per_step_spinbox.setValue(3.5)
    assert _make_controller(view=view)._get_hz_per_step_from_view() == 3.5


def test_get_hz_per_step_from_view_none_when_unavailable() -> None:
    controller = FrequencyTuningController(SimpleNamespace(), Mock())
    assert controller._get_hz_per_step_from_view() is None


def test_update_toolbar_state_delegates_to_ui() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller._update_toolbar_state("running")
    view.ui.update_toolbar_state.assert_called_once_with("running")


def test_update_toolbar_state_without_ui_is_safe() -> None:
    FrequencyTuningController(SimpleNamespace(), Mock())._update_toolbar_state(
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


def test_update_pv_addresses_no_selection_returns_early(monkeypatch) -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    monkeypatch.setattr(
        controller_module,
        "resolve_cavity_selection",
        lambda *_: (None, None),
    )
    controller._get_machine_cavity = Mock()

    controller.update_pv_addresses()

    controller._get_machine_cavity.assert_not_called()


def test_update_pv_addresses_success_applies_mapping() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller._get_machine_cavity = Mock(return_value=Mock())
    controller._apply_stepper_pv_mapping = Mock()

    controller.update_pv_addresses("02", "1")

    controller._apply_stepper_pv_mapping.assert_called_once()
    assert any("CM" in msg or "Cav" in msg for msg in view.logs)


def test_update_pv_addresses_exception_logs_error() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller._get_machine_cavity = Mock(side_effect=RuntimeError("oops"))

    controller.update_pv_addresses("02", "1")

    assert any("Error setting PVs" in msg for msg in view.logs)


def test_apply_stepper_pv_mapping_builds_map(monkeypatch) -> None:
    captured = {}
    monkeypatch.setattr(
        controller_module,
        "apply_pv_mapping",
        lambda mapping: captured.update({"mapping": mapping}),
    )
    view = _ViewStub()
    view.steps_spinbox = _SpinboxStub()
    view.net_steps_label = _ButtonStub()
    controller = _make_controller(view=view)

    cavity = Mock()
    cavity.stepper_tuner.step_des_pv = "PV:STEPDES"
    cavity.stepper_tuner.step_signed_pv = "PV:STEPSIGNED"
    cavity.rack.pv_prefix = "ACCL:L0B:0100:"
    cavity.detune_chirp_pv = "PV:CHIRP"
    cavity.pv_addr.return_value = "PV:ADDR"

    controller._apply_stepper_pv_mapping(cavity)

    assert "mapping" in captured
    assert view.steps_spinbox in captured["mapping"]
    assert view.net_steps_label in captured["mapping"]


def test_apply_stepper_pv_mapping_wires_piezo_and_drive(monkeypatch) -> None:
    """Piezo enable/mode and RF drive level are reachable from the tuning tab.

    setup_tuning() sets these automatically, but piezo feedback fighting the
    stepper is a real mid-tune failure mode, so the operator needs the state
    visible and the controls writable without switching tabs.
    """
    captured = {}
    monkeypatch.setattr(
        controller_module,
        "apply_pv_mapping",
        lambda mapping: captured.update({"mapping": mapping}),
    )
    view = _ViewStub()
    view.piezo_enable_stat_readback = _ButtonStub()
    view.piezo_enable_ctrl = _ButtonStub()
    view.piezo_mode_stat_readback = _ButtonStub()
    view.piezo_mode_ctrl = _ButtonStub()
    view.drive_level_readback = _ButtonStub()
    controller = _make_controller(view=view)

    cavity = Mock()
    cavity.rack.pv_prefix = "ACCL:L0B:0100:"
    cavity.detune_chirp_pv = "PV:CHIRP"
    cavity.pv_addr.return_value = "PV:ADDR"
    cavity.drive_level_pv = "PV:SEL_ASET"
    cavity.piezo.enable_pv = "PV:PZT:ENABLE"
    cavity.piezo.enable_stat_pv = "PV:PZT:ENABLESTAT"
    cavity.piezo.feedback_control_pv = "PV:PZT:MODECTRL"
    cavity.piezo.feedback_stat_pv = "PV:PZT:MODESTAT"

    controller._apply_stepper_pv_mapping(cavity)

    mapping = captured["mapping"]
    assert mapping[view.piezo_enable_stat_readback] == "PV:PZT:ENABLESTAT"
    assert mapping[view.piezo_enable_ctrl] == "PV:PZT:ENABLE"
    assert mapping[view.piezo_mode_stat_readback] == "PV:PZT:MODESTAT"
    assert mapping[view.piezo_mode_ctrl] == "PV:PZT:MODECTRL"
    assert mapping[view.drive_level_readback] == "PV:SEL_ASET"


def test_get_machine_cavity_builds_machine(monkeypatch) -> None:
    class _MachineStub:
        def __init__(self):
            self.cryomodules = {
                "02": SimpleNamespace(cavities={1: "cavity-object"})
            }

    monkeypatch.setattr(controller_module, "Machine", _MachineStub)
    controller = _make_controller()

    cavity = controller._get_machine_cavity(2, 1)

    assert cavity == "cavity-object"
    assert isinstance(controller.machine, _MachineStub)


# ------------------------------------------------------------------
# _resolve_target
# ------------------------------------------------------------------


def test_resolve_target_no_selection_shows_error(monkeypatch) -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    monkeypatch.setattr(
        controller_module,
        "resolve_cavity_selection",
        lambda *_: (None, None),
    )

    assert controller._resolve_target() is None
    assert any("Unable to determine cavity" in m for m in view.errors)


def test_resolve_target_invalid_int_shows_error(monkeypatch) -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    monkeypatch.setattr(
        controller_module,
        "resolve_cavity_selection",
        lambda *_: ("02", "bad"),
    )

    assert controller._resolve_target() is None
    assert any("Invalid cavity selection" in m for m in view.errors)


def test_resolve_target_success(monkeypatch) -> None:
    view = _ViewStub()
    session = Mock()
    session.start_new_record.return_value = (_record(), 5, True)
    controller = _make_controller(view=view, session=session)
    monkeypatch.setattr(
        controller_module,
        "resolve_cavity_selection",
        lambda *_: ("02", "1"),
    )

    assert controller._resolve_target() == ("CM02_CAV1", 2, 1)
    assert any("Created" in m for m in view.logs)


def test_resolve_target_record_error_shows_error(monkeypatch) -> None:
    view = _ViewStub()
    session = Mock()
    session.start_new_record.side_effect = RuntimeError("db down")
    controller = _make_controller(view=view, session=session)
    monkeypatch.setattr(
        controller_module,
        "resolve_cavity_selection",
        lambda *_: ("02", "1"),
    )

    assert controller._resolve_target() is None
    assert any("Failed to get/create record" in m for m in view.errors)


# ------------------------------------------------------------------
# Stage entry points
# ------------------------------------------------------------------


def test_run_stage_1_no_operator_shows_error() -> None:
    view = _ViewStub(current_operator="")
    _make_controller(view=view).run_stage_1()
    assert any("operator" in m.lower() for m in view.errors)


def test_on_run_automated_test_aliases_stage_1() -> None:
    controller = _make_controller()
    controller.run_stage_1 = Mock()
    controller.on_run_automated_test()
    controller.run_stage_1.assert_called_once()


def test_run_stage_1_target_none_stops() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller._resolve_target = Mock(return_value=None)
    controller._start_stage = Mock()

    controller.run_stage_1()

    controller._start_stage.assert_not_called()


def test_run_stage_1_marks_running_before_resolving_target() -> None:
    """The status flips on the button press, not after record setup.

    Operators reported missing the state change entirely because it landed
    after _resolve_target() had done its database work, by which point the Run
    button had already greyed out with nothing else visibly changing.
    """
    view = _ViewStub()
    controller = _make_controller(view=view)
    status_at_resolve_time = {}

    def _resolve():
        status_at_resolve_time["text"] = view.stage1_status_label.text
        return ("CM02_CAV1", 2, 1)

    controller._resolve_target = _resolve
    controller._start_stage = Mock()

    controller.run_stage_1()

    assert "Running" in status_at_resolve_time["text"]


def test_run_stage_1_reverts_status_when_target_unresolved() -> None:
    """A stage that never starts must not be left showing "Running"."""
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller._resolve_target = Mock(return_value=None)
    controller._start_stage = Mock()

    controller.run_stage_1()

    assert "Not started" in view.stage1_status_label.text


def test_run_stage_1_reverts_status_when_start_raises() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller._resolve_target = Mock(return_value=("CM02_CAV1", 2, 1))
    controller._start_stage = Mock(side_effect=RuntimeError("boom"))

    controller.run_stage_1()

    assert "Not started" in view.stage1_status_label.text


def test_stage_done_hides_description_but_failure_keeps_it() -> None:
    """A finished stage drops its blurb; a failed one keeps it for the retry."""
    view = _ViewStub()
    view.stage1_description = _ButtonStub()
    view.stage2_description = _ButtonStub()
    controller = _make_controller(view=view)

    controller._set_stage_done_ui(1, success=True)
    assert view.stage1_description.visible is False

    controller._set_stage_done_ui(2, success=False)
    assert view.stage2_description.visible is True


def test_reset_all_stages_restores_descriptions() -> None:
    view = _ViewStub()
    view.stage1_description = _ButtonStub()
    controller = _make_controller(view=view)
    controller._set_stage_done_ui(1, success=True)

    controller._reset_all_stages()

    assert view.stage1_description.visible is True


def _history_session(rows):
    session = Mock()
    session.get_measurement_history.return_value = rows
    return session


def test_restore_recovers_cold_landing_from_record_blob() -> None:
    """A history row missing df_cold_hz falls back to the record blob."""
    view = _ViewStub()
    session = _history_session(
        [{"measurement_data": {"step": "cold_landing", "df_cold_hz": None}}]
    )
    controller = _make_controller(view=view, session=session)
    controller._rebuild_phase_context = Mock()
    record = _record()
    record.frequency_tuning = FrequencyTuningData(df_cold_hz=3739.0)

    controller.restore_from_record(record)

    assert controller._df_cold_hz == 3739.0
    assert view.stage2_run_btn.enabled is True


def test_restore_without_any_cold_landing_keeps_stage_2_locked() -> None:
    """Reopening a cavity whose cold landing never persisted must not dead-end.

    The stage-1 history row can exist with df_cold_hz null. Marking stage 1
    Done and unlocking stage 2 on that basis let the operator click Run Stage 2
    and get an immediate "Cold landing not recorded" error with no way forward.
    Stage 1 has to stay runnable instead.
    """
    view = _ViewStub()
    session = _history_session(
        [{"measurement_data": {"step": "cold_landing", "df_cold_hz": None}}]
    )
    controller = _make_controller(view=view, session=session)
    controller._rebuild_phase_context = Mock()
    record = _record()
    record.frequency_tuning = None

    controller.restore_from_record(record)

    assert controller._df_cold_hz is None
    assert view.stage2_run_btn.enabled is False
    assert view.stage1_run_btn.enabled is True
    assert "Not started" in view.stage1_status_label.text
    assert any("cold landing" in m.lower() for m in view.logs)


def test_stage_1_without_a_cold_landing_is_not_reported_done() -> None:
    """Don't persist a stage 1 'success' that stage 2 can never build on."""
    view = _ViewStub()
    # Mirror the real initial state: stage 2 is locked until stage 1 succeeds.
    view.stage2_run_btn.setEnabled(False)
    controller = _make_controller(view=view)
    controller._save_stage_to_history = Mock(return_value=True)
    controller._df_cold_hz = None

    controller._on_stage1_done()

    assert "Failed" in view.stage1_status_label.text
    assert view.stage2_run_btn.enabled is False
    controller._save_stage_to_history.assert_not_called()


def test_stage_1_persists_cold_landing_onto_the_record() -> None:
    """measurement_history alone is not enough to survive a restart.

    The phase gates stage 2 on the record, since phase_history checkpoints are
    in-memory only. Writing the frequency to history but not the record left
    stage 2 failing after a relaunch with "Cold landing frequency was not
    recorded".
    """
    view = _ViewStub()
    session = Mock()
    record = _record()
    record.frequency_tuning = None
    session.get_active_record.return_value = record
    controller = _make_controller(view=view, session=session)
    controller._save_stage_to_history = Mock(return_value=True)
    controller._update_partial_results = Mock()
    controller._df_cold_hz = 9196.0

    controller._on_stage1_done()

    assert record.frequency_tuning.df_cold_hz == 9196.0
    session.save_active_record.assert_called_once()


def test_persist_cold_landing_skips_redundant_save() -> None:
    """Don't bump the record version when the value is already durable."""
    view = _ViewStub()
    session = Mock()
    record = _record()
    record.frequency_tuning = FrequencyTuningData(df_cold_hz=9196.0)
    session.get_active_record.return_value = record
    controller = _make_controller(view=view, session=session)
    controller._df_cold_hz = 9196.0

    controller._persist_df_cold_to_record()

    session.save_active_record.assert_not_called()


def test_restore_backfills_cold_landing_onto_older_records() -> None:
    """Records whose frequency only reached history get healed on load."""
    view = _ViewStub()
    session = _history_session(
        [{"measurement_data": {"step": "cold_landing", "df_cold_hz": 9196.0}}]
    )
    record = _record()
    record.frequency_tuning = None
    session.get_active_record.return_value = record
    controller = _make_controller(view=view, session=session)
    controller._rebuild_phase_context = Mock()

    controller.restore_from_record(record)

    assert record.frequency_tuning.df_cold_hz == 9196.0


def test_completion_closes_an_instance_opened_in_an_earlier_session() -> None:
    """Only Stage 1 opens a phase instance, so a resumed run has no id cached.

    Leaving the instance at in_progress means the workflow never advances and
    the tab keeps reading "In progress" after Stage 4, because tab state comes
    from instance status rather than from record.set_phase_status.
    """
    view = _ViewStub()
    session = Mock()
    record = _record()
    record.frequency_tuning = FrequencyTuningData(df_cold_hz=9196.0)
    session.get_active_record.return_value = record
    session.save_active_record.return_value = True
    session.get_active_phase_instances.return_value = [
        {"id": 8, "phase": "frequency_tuning", "status": "in_progress"},
        {"id": 3, "phase": "ssa_char", "status": "complete"},
    ]
    controller = _make_controller(view=view, session=session)
    controller.context = SimpleNamespace(record=record)
    controller._active_phase_instance_id = None

    controller.on_phase_completed()

    _, kwargs = session.complete_active_phase_instance.call_args
    assert kwargs["phase_instance_id"] == 8


def test_completion_ignores_already_finished_instances() -> None:
    view = _ViewStub()
    session = Mock()
    record = _record()
    record.frequency_tuning = FrequencyTuningData(df_cold_hz=9196.0)
    session.get_active_record.return_value = record
    session.get_active_phase_instances.return_value = [
        {"id": 8, "phase": "frequency_tuning", "status": "complete"},
    ]
    controller = _make_controller(view=view, session=session)
    controller.context = SimpleNamespace(record=record)
    controller._active_phase_instance_id = None

    controller.on_phase_completed()

    session.complete_active_phase_instance.assert_not_called()


def test_stage_2_awaiting_confirm_is_not_reported_as_idle() -> None:
    """Blocked-on-operator must not read IDLE in the status bar.

    Nothing is executing once Stage 2 measures its Hz/step, but the run is
    waiting on Confirm Fit, so "idle" would contradict the phase status.
    """
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller.phase = SimpleNamespace(
        _hz_per_microstep=0.0055, limits=SimpleNamespace(probe_steps=1000)
    )
    controller._probe_s_d0 = None
    states: list[str] = []
    controller._update_toolbar_state = lambda state: states.append(state)

    controller._on_stage2_done()

    assert states[-1] == "awaiting"


def test_run_stage_1_success_calls_start_stage() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller._resolve_target = Mock(return_value=("CM02_CAV1", 2, 1))
    controller._start_stage = Mock()

    controller.run_stage_1()

    controller._start_stage.assert_called_once()


def test_run_stage_1_start_stage_exception_logged() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller._resolve_target = Mock(return_value=("CM02_CAV1", 2, 1))
    controller._start_stage = Mock(side_effect=RuntimeError("boom"))

    controller.run_stage_1()

    assert any("Failed to start Stage 1" in m for m in view.errors)


def test_run_stage_2_no_operator_shows_error() -> None:
    view = _ViewStub(current_operator="")
    _make_controller(view=view).run_stage_2()
    assert any("operator" in m.lower() for m in view.errors)


def test_run_stage_2_without_phase_shows_error() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller.phase = None
    controller.context = None

    controller.run_stage_2()

    assert any("Run Stage 1 first" in m for m in view.errors)


def test_run_stage_2_success_runs_background() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller.phase = Mock()
    controller.context = Mock()
    controller._df_cold_hz = 5000.0
    controller._run_phase_in_background = Mock()

    controller.run_stage_2()

    controller._run_phase_in_background.assert_called_once()
    assert controller._current_stage == 2
    assert view.confirm_probe_fit_button.enabled is False


def test_run_stage_3_no_operator_shows_error() -> None:
    view = _ViewStub(current_operator="")
    _make_controller(view=view).run_stage_3()
    assert any("operator" in m.lower() for m in view.errors)


def test_run_stage_3_without_phase_shows_error() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller.phase = None
    controller.context = None

    controller.run_stage_3()

    assert any("Run Stage 2 first" in m for m in view.errors)


def test_run_stage_3_success_sets_hz_and_runs() -> None:
    view = _ViewStub()
    view.hz_per_step_spinbox.setValue(2.0)
    controller = _make_controller(view=view)
    controller.phase = Mock()
    controller.phase._hz_per_microstep = 1.0
    controller.context = Mock()
    controller._probe_stage_confirmed = True
    controller._run_phase_in_background = Mock()

    controller.run_stage_3()

    assert controller._current_stage == 3
    assert controller.phase._hz_per_microstep == 2.0
    controller._run_phase_in_background.assert_called_once()


def test_on_confirm_and_tune_aliases_stage_3() -> None:
    controller = _make_controller()
    controller.run_stage_3 = Mock()
    controller.on_confirm_and_tune()
    controller.run_stage_3.assert_called_once()


def test_run_stage_4_no_operator_shows_error() -> None:
    view = _ViewStub(current_operator="")
    _make_controller(view=view).run_stage_4()
    assert any("operator" in m.lower() for m in view.errors)


def test_run_stage_4_without_phase_shows_error() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller.phase = None
    controller.context = None

    controller.run_stage_4()

    assert any("Run Stage 3 first" in m for m in view.errors)


def test_run_stage_4_success_runs_background() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller.phase = Mock()
    controller.context = Mock()
    controller._run_phase_in_background = Mock()

    controller.run_stage_4()

    assert controller._current_stage == 4
    controller._run_phase_in_background.assert_called_once()


def test_confirm_and_save_without_phase_shows_error() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller.phase = None
    controller.context = None

    controller.confirm_and_save()

    assert any("Complete Stage 4 first" in m for m in view.errors)


def test_confirm_and_save_success_runs_background() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller.phase = Mock()
    controller.context = Mock()
    controller._run_phase_in_background = Mock()

    controller.confirm_and_save()

    assert controller._current_stage == 5
    assert controller._finalize_after_run is True
    controller._run_phase_in_background.assert_called_once()


# ------------------------------------------------------------------
# _start_stage
# ------------------------------------------------------------------


def test_start_stage_cannot_run_shows_error() -> None:
    view = _ViewStub()
    session = Mock()
    session.get_active_record.return_value = _record()
    session.get_active_record_id.return_value = 7
    session.can_run_phase.return_value = (False, "blocked")
    controller = _make_controller(view=view, session=session)
    controller.update_pv_addresses = Mock()
    controller._get_machine_cavity = Mock(return_value=Mock())

    controller._start_stage(1, ["a"], False, 2, 1, "op")

    assert any("blocked" in m for m in view.errors)


def test_start_stage_prerequisites_fail_shows_error(monkeypatch) -> None:
    view = _ViewStub()
    session = Mock()
    session.get_active_record.return_value = _record()
    session.get_active_record_id.return_value = 7
    session.can_run_phase.return_value = (True, "")
    session.start_active_phase_instance.return_value = SimpleNamespace(
        phase_instance_id=99
    )

    class _PhaseStub:
        def __init__(self, ctx):
            pass

        def validate_prerequisites(self):
            return (False, "no good")

    monkeypatch.setattr(controller_module, "FrequencyTuningPhase", _PhaseStub)
    controller = _make_controller(view=view, session=session)
    controller.update_pv_addresses = Mock()
    controller._get_machine_cavity = Mock(return_value=Mock())

    controller._start_stage(1, ["a"], False, 2, 1, "op")

    assert any("Prerequisites not met" in m for m in view.errors)
    assert controller._active_phase_instance_id == 99


def test_start_stage_success_runs_background(monkeypatch) -> None:
    view = _ViewStub()
    session = Mock()
    session.get_active_record.return_value = _record()
    session.get_active_record_id.return_value = None
    session.can_run_phase.return_value = (True, "")

    class _PhaseStub:
        def __init__(self, ctx):
            pass

        def validate_prerequisites(self):
            return (True, "ok")

    monkeypatch.setattr(controller_module, "FrequencyTuningPhase", _PhaseStub)
    controller = _make_controller(view=view, session=session)
    controller.update_pv_addresses = Mock()
    controller._get_machine_cavity = Mock(return_value=Mock())
    controller._run_phase_in_background = Mock()

    controller._start_stage(1, ["a"], False, 2, 1, "op")

    assert controller._active_phase_instance_id is None
    controller._run_phase_in_background.assert_called_once()


# ------------------------------------------------------------------
# UI state helpers
# ------------------------------------------------------------------


def test_set_stage_running_ui_sets_controls() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)

    controller._set_stage_running_ui(1)

    assert view.stage1_run_btn.enabled is False
    assert "Running" in view.stage1_status_label.text
    assert view.pause_button.enabled is True
    assert view.abort_button.enabled is True
    view.local_phase_status.setText.assert_called_with("RUNNING")


def test_set_stage_running_ui_none_stage_safe() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller._set_stage_running_ui(None)
    assert view.pause_button.enabled is True


def test_set_stage_done_ui_success() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller._set_stage_done_ui(2, success=True)
    assert "Done" in view.stage2_status_label.text
    assert view.stage2_run_btn.enabled is False


def test_set_stage_done_ui_failure() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller._set_stage_done_ui(3, success=False)
    assert "Failed" in view.stage3_status_label.text
    assert view.stage3_run_btn.enabled is True


def test_enable_stage_btn() -> None:
    view = _ViewStub()
    view.stage2_run_btn.setEnabled(False)
    controller = _make_controller(view=view)
    controller._enable_stage_btn(2)
    assert view.stage2_run_btn.enabled is True


def test_clear_running_ui() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller._clear_running_ui()
    assert view.pause_button.enabled is False
    assert view.pause_button.text == "⏸ Pause"
    assert view.abort_button.enabled is False


# ------------------------------------------------------------------
# Background execution
# ------------------------------------------------------------------


def test_reset_abort_and_speed() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller.context = PhaseContext(record=_record(), operator="op")
    controller.context.abort_requested = True
    cavity = Mock()
    controller._cavity = cavity
    controller.phase = Mock()

    controller._reset_abort_and_speed()

    assert controller.context.abort_requested is False
    assert cavity.stepper_tuner.abort_flag is False
    assert controller.phase.limits.move_speed == 2.0


def test_run_phase_in_background_no_context_returns() -> None:
    controller = _make_controller()
    controller.context = None
    controller.phase = None
    controller._reset_abort_and_speed = Mock()

    controller._run_phase_in_background()

    controller._reset_abort_and_speed.assert_not_called()


def test_run_phase_in_background_step_fail_emits() -> None:
    controller = _make_controller()
    controller.context = PhaseContext(record=_record(), operator="op")
    controller.phase = Mock()
    controller._steps = ["step"]
    controller._finalize_after_run = False
    controller._check_pause_and_abort = Mock(return_value=True)
    controller._execute_single_step = Mock(return_value=False)
    emitted = []
    controller.phase_run_finished.connect(
        lambda ok, msg: emitted.append((ok, msg))
    )

    controller._run_phase_in_background()

    assert emitted[-1] == (False, "Step failed: Step")


def test_run_phase_in_background_abort_returns() -> None:
    controller = _make_controller()
    controller.context = PhaseContext(record=_record(), operator="op")
    controller.phase = Mock()
    controller._steps = ["step"]
    controller._check_pause_and_abort = Mock(return_value=False)
    controller._execute_single_step = Mock()

    controller._run_phase_in_background()

    controller._execute_single_step.assert_not_called()


def test_run_phase_in_background_finalize() -> None:
    controller = _make_controller()
    controller.context = PhaseContext(record=_record(), operator="op")
    controller.phase = Mock()
    controller._steps = ["step"]
    controller._finalize_after_run = True
    controller._check_pause_and_abort = Mock(return_value=True)
    controller._execute_single_step = Mock(return_value=True)
    controller._finalize_background_phase = Mock()

    controller._run_phase_in_background()

    controller._finalize_background_phase.assert_called_once()


def test_run_phase_in_background_emits_stage_done() -> None:
    controller = _make_controller()
    controller.context = PhaseContext(record=_record(), operator="op")
    controller.phase = Mock()
    controller._steps = ["step"]
    controller._finalize_after_run = False
    controller._current_stage = 1
    controller._check_pause_and_abort = Mock(return_value=True)
    controller._execute_single_step = Mock(return_value=True)
    # Replace stage handlers so the real signal slot does no real work.
    controller._on_stage1_done = Mock()
    emitted = []
    controller._stage_done.connect(lambda stage: emitted.append(stage))

    controller._run_phase_in_background()

    assert emitted[-1] == 1
    controller._on_stage1_done.assert_called_once()


def test_run_phase_in_background_exception_emits() -> None:
    controller = _make_controller()
    controller.context = PhaseContext(record=_record(), operator="op")
    controller.phase = Mock()
    controller.phase._mark_phase_started.side_effect = RuntimeError("boom")
    controller._steps = ["step"]
    emitted = []
    controller.phase_run_finished.connect(
        lambda ok, msg: emitted.append((ok, msg))
    )

    controller._run_phase_in_background()

    assert emitted[-1] == (False, "boom")


# ------------------------------------------------------------------
# Stage completion handlers
# ------------------------------------------------------------------


def test_on_stage_done_dispatches() -> None:
    controller = _make_controller()
    controller._on_stage1_done = Mock()
    controller._on_stage2_done = Mock()
    controller._on_stage3_done = Mock()
    controller._on_stage4_done = Mock()

    controller._on_stage_done(1)
    controller._on_stage_done(2)
    controller._on_stage_done(3)
    controller._on_stage_done(4)

    controller._on_stage1_done.assert_called_once()
    controller._on_stage2_done.assert_called_once()
    controller._on_stage3_done.assert_called_once()
    controller._on_stage4_done.assert_called_once()


def test_on_stage1_done_saved() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller._save_stage_to_history = Mock(return_value=True)
    controller._update_partial_results = Mock()
    controller._df_cold_hz = 12.3

    controller._on_stage1_done()

    assert view.stage2_run_btn.enabled is True
    controller._update_partial_results.assert_called_once()


def test_on_stage1_done_save_fails_stops() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller._save_stage_to_history = Mock(return_value=False)
    controller._enable_stage_btn = Mock()

    controller._on_stage1_done()

    controller._enable_stage_btn.assert_not_called()


def test_on_stage2_done_populates_pending_and_enables_confirm() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller.phase = Mock()
    controller.phase._hz_per_microstep = 1.5
    controller.phase.limits.probe_steps = 100
    controller._probe_s_d0 = 0
    controller._probe_s_d1 = 100
    controller._probe_d0_hz = 0.0
    controller._probe_d1_hz = 150.0

    controller._on_stage2_done()

    assert controller._pending_stage2_data["hz_per_microstep"] == 1.5
    assert view.confirm_probe_fit_button.enabled is True
    assert view.hz_per_step_spinbox.enabled is True
    view.show_probe_fit.assert_called_once()


def test_confirm_probe_fit_no_data_shows_error() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller._pending_stage2_data = {}

    controller.confirm_probe_fit()

    assert any("No probe data" in m for m in view.errors)


def test_confirm_probe_fit_success() -> None:
    view = _ViewStub()
    view.hz_per_step_spinbox.setValue(2.0)
    controller = _make_controller(view=view)
    controller.phase = Mock()
    controller._pending_stage2_data = {"hz_per_microstep": 1.0}
    controller._save_stage_to_history = Mock(return_value=True)
    controller._update_partial_results = Mock()
    controller.push_hz_per_step_to_scale = Mock()

    controller.confirm_probe_fit()

    assert controller._probe_stage_confirmed is True
    assert view.stage3_run_btn.enabled is True
    assert view.confirm_probe_fit_button.enabled is False
    controller.push_hz_per_step_to_scale.assert_called_once()


def test_confirm_probe_fit_save_fails_stops() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller._pending_stage2_data = {"hz_per_microstep": 1.0}
    controller._save_stage_to_history = Mock(return_value=False)
    controller.push_hz_per_step_to_scale = Mock()

    controller.confirm_probe_fit()

    controller.push_hz_per_step_to_scale.assert_not_called()


def test_on_stage3_done() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller._save_stage_to_history = Mock(return_value=True)
    controller._update_partial_results = Mock()
    controller._net_steps = -10
    controller._tune_step_data = {
        "cold_landing_steps": 10,
        "total_steps": 50,
    }

    controller._on_stage3_done()

    assert view.stage4_run_btn.enabled is True


def test_on_stage3_done_save_fails() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller._save_stage_to_history = Mock(return_value=False)
    controller._enable_stage_btn = Mock()

    controller._on_stage3_done()

    controller._enable_stage_btn.assert_not_called()


def test_on_stage4_done() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller._save_stage_to_history = Mock(return_value=True)
    controller._update_partial_results = Mock()
    controller._pi_mode_data = {"mode_8pi_9_hz": 100.0, "mode_7pi_9_hz": None}

    controller._on_stage4_done()

    assert view.stage4_run_btn.enabled is True


def test_on_stage4_done_save_fails() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller._save_stage_to_history = Mock(return_value=False)
    controller._update_partial_results = Mock()

    controller._on_stage4_done()

    controller._update_partial_results.assert_not_called()


def test_update_partial_results_calls_view() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller._df_cold_hz = 5.0

    controller._update_partial_results()

    view._update_local_results.assert_called_once()
    arg = view._update_local_results.call_args[0][0]
    assert isinstance(arg, FrequencyTuningData)


def test_on_hz_chunk_update_emits_estimate() -> None:
    controller = _make_controller()
    emitted = []
    controller.hz_per_step_updated.connect(lambda v: emitted.append(v))

    controller._on_hz_chunk_update(10, 20.0)

    assert emitted[-1] == 2.0


def test_on_hz_chunk_update_ignores_nonpositive() -> None:
    controller = _make_controller()
    emitted = []
    controller.hz_per_step_updated.connect(lambda v: emitted.append(v))

    controller._on_hz_chunk_update(0, 0.0)

    assert emitted == []


# ------------------------------------------------------------------
# Step execution
# ------------------------------------------------------------------


def test_execute_single_step_abort_returns_false() -> None:
    controller = _make_controller()
    controller.context = PhaseContext(record=_record(), operator="op")
    controller.context.request_abort()

    assert controller._execute_single_step("step") is False


def test_execute_single_step_calls_retries() -> None:
    controller = _make_controller()
    controller.context = PhaseContext(record=_record(), operator="op")
    controller.context.progress_callback = Mock()
    controller._steps = ["step"]
    controller._current_stage = 1
    controller._execute_step_with_retries = Mock(return_value=True)

    assert controller._execute_single_step("step") is True
    controller.context.progress_callback.assert_called_once()


def test_execute_step_with_retries_success() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller.phase = Mock()
    controller.phase.execute_step.return_value = PhaseStepResult(
        result=PhaseResult.SUCCESS, message="ok"
    )
    controller._create_step_checkpoint = Mock()
    controller._on_step_succeeded = Mock()

    assert controller._execute_step_with_retries("step", 3) is True
    controller._on_step_succeeded.assert_called_once()


def test_execute_step_with_retries_skip() -> None:
    controller = _make_controller()
    controller.phase = Mock()
    controller.phase.execute_step.return_value = PhaseStepResult(
        result=PhaseResult.SKIP, message="skip"
    )
    controller._create_step_checkpoint = Mock()
    controller._on_step_succeeded = Mock()

    assert controller._execute_step_with_retries("step", 3) is True


def test_execute_step_with_retries_failed() -> None:
    controller = _make_controller()
    controller.phase = Mock()
    controller.phase.execute_step.return_value = PhaseStepResult(
        result=PhaseResult.FAILED, message="bad"
    )
    controller._create_step_checkpoint = Mock()

    assert controller._execute_step_with_retries("step", 3) is False


def test_execute_step_with_retries_retry_then_success() -> None:
    controller = _make_controller()
    controller.phase = Mock()
    controller.phase.execute_step.side_effect = [
        PhaseStepResult(
            result=PhaseResult.RETRY, message="again", retry_delay_seconds=0.0
        ),
        PhaseStepResult(result=PhaseResult.SUCCESS, message="ok"),
    ]
    controller._create_step_checkpoint = Mock()
    controller._on_step_succeeded = Mock()

    assert controller._execute_step_with_retries("step", 3) is True


def test_execute_step_with_retries_retry_exhausted() -> None:
    controller = _make_controller()
    controller.phase = Mock()
    controller.phase.execute_step.return_value = PhaseStepResult(
        result=PhaseResult.RETRY, message="again", retry_delay_seconds=0.0
    )
    controller._create_step_checkpoint = Mock()

    assert controller._execute_step_with_retries("step", 2) is False


def test_execute_step_with_retries_exception_exhausted() -> None:
    controller = _make_controller()
    controller.phase = Mock()
    controller.phase.execute_step.side_effect = RuntimeError("rpc down")

    assert controller._execute_step_with_retries("step", 2) is False


def test_execute_step_with_retries_zero_retries() -> None:
    controller = _make_controller()
    controller.phase = Mock()
    assert controller._execute_step_with_retries("step", 0) is False


def test_on_step_succeeded_routes_data() -> None:
    controller = _make_controller()

    controller._on_step_succeeded("record_cold_landing", {"df_cold_hz": 9.0})
    assert controller._df_cold_hz == 9.0

    controller._on_step_succeeded(
        "probe_stepper_direction",
        {"d0_hz": 1.0, "d1_hz": 2.0, "s_d0": 0, "s_d1": 50},
    )
    assert controller._probe_d0_hz == 1.0
    assert controller._probe_s_d1 == 50

    controller._on_step_succeeded(
        "tune_to_resonance", {"cold_landing_steps": 30, "total_steps": 60}
    )
    assert controller._net_steps == -30

    controller._on_step_succeeded("measure_pi_modes", {"mode_8pi_9_hz": 100.0})
    assert controller._pi_mode_data == {"mode_8pi_9_hz": 100.0}


def test_save_stage_to_history_success() -> None:
    session = Mock()
    session.add_measurement_to_history.return_value = True
    controller = _make_controller(session=session)

    assert controller._save_stage_to_history("step", {"a": 1}) is True


def test_save_stage_to_history_exception() -> None:
    view = _ViewStub()
    session = Mock()
    session.add_measurement_to_history.side_effect = RuntimeError("db")
    controller = _make_controller(view=view, session=session)

    assert controller._save_stage_to_history("step", {}) is False


def test_create_step_checkpoint_appends() -> None:
    controller = _make_controller()
    record = _record()
    record.phase_history = []
    controller.context = PhaseContext(
        record=record, operator="op", phase_instance_id=7
    )
    controller.phase = Mock()
    controller.phase.phase_type = "FREQUENCY_TUNING"

    controller._create_step_checkpoint(
        "verify_initial_state",
        PhaseStepResult(
            result=PhaseResult.SUCCESS, message="ok", data={"a": 1}
        ),
    )

    assert len(record.phase_history) == 1
    assert record.phase_history[0].step_name == "verify_initial_state"
    assert record.phase_history[0].success is True


def test_finalize_background_phase_success() -> None:
    controller = _make_controller()
    controller.phase = Mock()
    emitted = []
    controller.phase_run_finished.connect(
        lambda ok, msg: emitted.append((ok, msg))
    )

    controller._finalize_background_phase()

    assert emitted[-1] == (True, "")


def test_finalize_background_phase_exception() -> None:
    controller = _make_controller()
    controller.phase = Mock()
    controller.phase.finalize_phase.side_effect = RuntimeError("fail")
    emitted = []
    controller.phase_run_finished.connect(
        lambda ok, msg: emitted.append((ok, msg))
    )

    controller._finalize_background_phase()

    assert emitted[-1] == (False, "fail")


def test_check_pause_and_abort_normal() -> None:
    assert _make_controller()._check_pause_and_abort() is True


def test_check_pause_and_abort_aborted() -> None:
    controller = _make_controller()
    controller.context = PhaseContext(record=_record(), operator="op")
    controller.context.request_abort()
    emitted = []
    controller.phase_run_finished.connect(
        lambda ok, msg: emitted.append((ok, msg))
    )

    assert controller._check_pause_and_abort() is False
    assert emitted[-1] == (False, "Aborted")


# ------------------------------------------------------------------
# Phase completion
# ------------------------------------------------------------------


def test_on_phase_run_finished_routes_to_completed() -> None:
    controller = _make_controller()
    controller.on_phase_completed = Mock()
    controller.on_phase_failed = Mock()

    controller._on_phase_run_finished(True, "")

    controller.on_phase_completed.assert_called_once()


def test_on_phase_run_finished_routes_to_failed() -> None:
    controller = _make_controller()
    controller.on_phase_completed = Mock()
    controller.on_phase_failed = Mock()

    controller._on_phase_run_finished(False, "boom")

    controller.on_phase_failed.assert_called_once_with("boom")


def test_on_phase_run_finished_default_error() -> None:
    controller = _make_controller()
    controller.on_phase_completed = Mock()
    controller.on_phase_failed = Mock()

    controller._on_phase_run_finished(False, "")

    controller.on_phase_failed.assert_called_once_with("Phase execution failed")


def test_on_phase_completed_success_saves() -> None:
    view = _ViewStub()
    session = Mock()
    session.save_active_record.return_value = True
    session.get_active_record_id.return_value = 42
    controller = _make_controller(view=view, session=session)
    record = _record()
    record.frequency_tuning = FrequencyTuningData(df_cold_hz=5.0)
    controller.context = PhaseContext(record=record, operator="op")
    controller._active_phase_instance_id = 3
    captured = []
    controller.phase_completed.connect(lambda rec: captured.append(rec))

    controller.on_phase_completed()

    assert controller._active_phase_instance_id is None
    assert captured
    view.local_progress_bar.setValue.assert_called_with(100)


def test_on_phase_completed_save_fails_logs() -> None:
    view = _ViewStub()
    session = Mock()
    session.save_active_record.return_value = False
    controller = _make_controller(view=view, session=session)
    record = _record()
    record.frequency_tuning = FrequencyTuningData(df_cold_hz=5.0)
    controller.context = PhaseContext(record=record, operator="op")

    controller.on_phase_completed()

    assert any("failed to save" in m.lower() for m in view.logs)


def test_on_phase_completed_no_tuning_data_safe() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view, session=Mock())
    record = _record()
    record.frequency_tuning = None
    controller.context = PhaseContext(record=record, operator="op")

    controller.on_phase_completed()

    view.local_phase_status.setText.assert_called_with("COMPLETED")


def test_on_phase_failed_resets_and_shows_error() -> None:
    view = _ViewStub()
    session = Mock()
    session.save_active_record.return_value = True
    controller = _make_controller(view=view, session=session)
    controller.phase = Mock()
    record = _record()
    record.frequency_tuning = FrequencyTuningData(df_cold_hz=5.0)
    controller.context = PhaseContext(record=record, operator="op")
    controller._active_phase_instance_id = 9
    controller._current_stage = 2

    controller.on_phase_failed("bad")

    assert view.pause_button.enabled is False
    assert view.abort_button.enabled is False
    assert any("bad" in m for m in view.errors)
    session.fail_active_phase_instance.assert_called_once()


def test_on_phase_failed_exception_still_clears() -> None:
    view = _ViewStub()
    session = Mock()
    session.save_active_record.side_effect = RuntimeError("db exploded")
    controller = _make_controller(view=view, session=session)
    controller.phase = Mock()
    controller.context = PhaseContext(record=_record(), operator="op")
    controller._active_phase_instance_id = 10
    controller._current_stage = 4

    controller.on_phase_failed("orig")

    assert controller._active_phase_instance_id is None
    assert any("orig" in m for m in view.errors)


# ------------------------------------------------------------------
# Pause / abort
# ------------------------------------------------------------------


def test_on_abort_requests_abort() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller.context = PhaseContext(record=_record(), operator="op")
    cavity = Mock()
    controller._cavity = cavity

    controller.on_abort()

    assert controller.context.abort_requested is True
    assert view.abort_button.enabled is False
    assert cavity.stepper_tuner.abort_flag is True


def test_on_abort_without_context_is_noop() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller.context = None

    controller.on_abort()

    assert view.abort_button.enabled is True


def test_on_pause_test_toggles() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)

    controller.on_pause_test()
    assert controller._paused is True
    assert view.pause_button.text == "▶ Resume"

    controller.on_pause_test()
    assert controller._paused is False
    assert view.pause_button.text == "⏸ Pause"


# ------------------------------------------------------------------
# Manual stepper controls / getters
# ------------------------------------------------------------------


def test_get_live_detune_none_without_cavity() -> None:
    assert _make_controller()._cavity is None
    assert _make_controller().get_live_detune() is None


def test_get_live_detune_reads_cavity() -> None:
    controller = _make_controller()
    controller._cavity = Mock()
    controller._cavity.detune_chirp = 42.0
    assert controller.get_live_detune() == 42.0


def test_get_live_detune_exception_returns_none() -> None:
    controller = _make_controller()
    cavity = Mock()
    type(cavity).detune_chirp = property(
        lambda self: (_ for _ in ()).throw(RuntimeError("x"))
    )
    controller._cavity = cavity
    assert controller.get_live_detune() is None


def test_get_live_steps_none_without_cavity() -> None:
    assert _make_controller().get_live_steps() is None


def test_get_live_steps_reads_pv(monkeypatch) -> None:
    controller = _make_controller()
    controller._cavity = Mock()
    controller._cavity.stepper_tuner.step_signed_pv = "PV:STEP"
    fake_pv = Mock()
    fake_pv.get.return_value = 5
    monkeypatch.setattr(
        "sc_linac_physics.utils.epics.PV", lambda *_a, **_k: fake_pv
    )

    assert controller.get_live_steps() == 5


def test_get_live_steps_exception_returns_none(monkeypatch) -> None:
    controller = _make_controller()
    controller._cavity = Mock()
    controller._cavity.stepper_tuner.step_signed_pv = "PV:STEP"
    monkeypatch.setattr(
        "sc_linac_physics.utils.epics.PV",
        Mock(side_effect=RuntimeError("no pv")),
    )

    assert controller.get_live_steps() is None


def test_get_signed_hz_per_step() -> None:
    controller = _make_controller()
    assert controller.get_signed_hz_per_step() is None
    controller.phase = Mock()
    controller.phase._hz_per_microstep = 1.7
    assert controller.get_signed_hz_per_step() == 1.7


def test_get_probe_anchor() -> None:
    controller = _make_controller()
    assert controller.get_probe_anchor() is None
    controller._probe_s_d0 = 0
    controller._probe_d0_hz = 1.0
    controller._probe_s_d1 = 50
    assert controller.get_probe_anchor() == (0, 1.0, 50)


def test_push_hz_per_step_to_scale_no_cavity() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller.push_hz_per_step_to_scale()
    assert any("No cavity selected" in m for m in view.logs)


def test_push_hz_per_step_to_scale_no_value() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller._cavity = Mock()
    controller._get_hz_per_step_from_view = Mock(return_value=0.0)
    controller.push_hz_per_step_to_scale()
    assert any("No Hz/step value" in m for m in view.logs)


def test_push_hz_per_step_to_scale_puts() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller._cavity = Mock()
    controller._get_hz_per_step_from_view = Mock(return_value=2.5)

    controller.push_hz_per_step_to_scale()

    # STEP:SCALE is derived/read-only — persist via set_hz_per_microstep
    # (writes SCALE_CALC.B), not a direct SCALE put.
    controller._cavity.stepper_tuner.set_hz_per_microstep.assert_called_once_with(
        2.5
    )
    assert any("Pushed" in m for m in view.logs)


def test_push_hz_per_step_to_scale_exception() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller._cavity = Mock()
    controller._cavity.stepper_tuner.set_hz_per_microstep.side_effect = (
        RuntimeError("pv fail")
    )
    controller._get_hz_per_step_from_view = Mock(return_value=2.5)

    controller.push_hz_per_step_to_scale()

    assert any("Failed to push" in m for m in view.logs)


def test_push_detune_to_df_cold_no_cavity() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller.push_detune_to_df_cold()
    assert any("No cavity selected" in m for m in view.logs)


def test_push_detune_to_df_cold_cancelled_does_nothing(monkeypatch) -> None:
    """Committing is never automatic — cancelling must not touch DF_COLD."""
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller._cavity = Mock()
    controller.get_live_detune = Mock(return_value=12.0)
    monkeypatch.setattr(
        controller_module, "ask_for_cold_landing", lambda *_a, **_k: None
    )
    fake_pv = Mock()
    monkeypatch.setattr(
        "sc_linac_physics.utils.epics.PV", lambda *_a, **_k: fake_pv
    )

    controller.push_detune_to_df_cold()

    fake_pv.put.assert_not_called()


def test_commit_writes_pv_and_record_to_the_same_value(monkeypatch) -> None:
    """The PV and the record must never disagree.

    The old button pushed whatever the live detune happened to be, which could
    differ from the value Stage 1 recorded — producing the exact DF_COLD/record
    mismatch the tuning gates reject at 1 Hz.
    """
    view = _ViewStub()
    session = Mock()
    record = _record()
    record.frequency_tuning = None
    session.get_active_record.return_value = record
    controller = _make_controller(view=view, session=session)
    controller._cavity = Mock()
    controller._cavity.pv_addr.return_value = "PV:DFCOLD"
    controller._df_cold_hz = 3739.0
    controller.get_live_detune = Mock(return_value=3800.0)

    choice = ColdLandingChoice(value_hz=3739.0, source=SOURCE_MEASURED)
    monkeypatch.setattr(
        controller_module, "ask_for_cold_landing", lambda *_a, **_k: choice
    )
    fake_pv = Mock()
    monkeypatch.setattr(
        "sc_linac_physics.utils.epics.PV", lambda *_a, **_k: fake_pv
    )

    controller.push_detune_to_df_cold()

    fake_pv.put.assert_called_once_with(3739.0)
    assert record.frequency_tuning.df_cold_hz == 3739.0
    assert controller._df_cold_hz == 3739.0


def test_commit_records_provenance_for_an_entered_value(monkeypatch) -> None:
    """A value that was not measured here has to explain itself."""
    view = _ViewStub()
    controller = _make_controller(view=view, session=Mock())
    controller._cavity = Mock()
    controller._persist_df_cold_to_record = Mock()
    saved: list = []
    controller._save_stage_to_history = lambda step, data: saved.append(data)
    monkeypatch.setattr(
        "sc_linac_physics.utils.epics.PV", lambda *_a, **_k: Mock()
    )
    choice = ColdLandingChoice(
        value_hz=1234.0,
        source=SOURCE_ENTERED,
        justification="measured at JLab during VTS",
    )
    monkeypatch.setattr(
        controller_module, "ask_for_cold_landing", lambda *_a, **_k: choice
    )

    controller.push_detune_to_df_cold()

    assert saved[0]["source"] == SOURCE_ENTERED
    assert saved[0]["justification"] == "measured at JLab during VTS"
    assert any("JLab" in m for m in view.logs)


def test_commit_logs_pv_failure(monkeypatch) -> None:
    view = _ViewStub()
    controller = _make_controller(view=view, session=Mock())
    controller._cavity = Mock()
    controller._persist_df_cold_to_record = Mock()
    controller._save_stage_to_history = Mock(return_value=True)
    monkeypatch.setattr(
        controller_module,
        "ask_for_cold_landing",
        lambda *_a, **_k: ColdLandingChoice(1.0, SOURCE_MEASURED),
    )
    monkeypatch.setattr(
        "sc_linac_physics.utils.epics.PV",
        Mock(side_effect=RuntimeError("pv fail")),
    )

    controller.push_detune_to_df_cold()

    assert any("Failed to push to DF_COLD" in m for m in view.logs)


def test_cold_landing_prompt_highlights_until_df_cold_matches() -> None:
    """The button must look like the next required action, not an extra."""
    view = _ViewStub()
    view.push_df_cold_button = _ButtonStub()
    controller = _make_controller(view=view)
    controller._cavity = Mock()
    controller._df_cold_hz = 3739.0
    controller._cavity.df_cold_pv_obj.get.return_value = 0.0

    controller.refresh_cold_landing_prompt()
    assert (
        PUSH_DF_COLD_ATTENTION.strip() == view.push_df_cold_button.style.strip()
    )

    controller._cavity.df_cold_pv_obj.get.return_value = 3739.0
    controller.refresh_cold_landing_prompt()
    assert (
        PUSH_DF_COLD_NEUTRAL.strip() == view.push_df_cold_button.style.strip()
    )


def test_cold_landing_prompt_neutral_before_stage_1() -> None:
    """Nothing recorded yet means nothing to prompt for."""
    view = _ViewStub()
    view.push_df_cold_button = _ButtonStub()
    controller = _make_controller(view=view)

    controller.refresh_cold_landing_prompt()

    assert (
        PUSH_DF_COLD_NEUTRAL.strip() == view.push_df_cold_button.style.strip()
    )


def test_on_move_left_no_cavity() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller.on_move_left()
    assert any("No cavity selected" in m for m in view.logs)


def test_on_move_left_spawns_move() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    cavity = Mock()
    controller._cavity = cavity

    controller.on_move_left()

    cavity.stepper_tuner.move_negative.assert_called_once()


def test_on_move_right_no_cavity() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller.on_move_right()
    assert any("No cavity selected" in m for m in view.logs)


def test_on_move_right_spawns_move() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    cavity = Mock()
    controller._cavity = cavity

    controller.on_move_right()

    cavity.stepper_tuner.move_positive.assert_called_once()


def test_do_stepper_move_exception_logged() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    cavity = Mock()
    cavity.stepper_tuner.move_positive.side_effect = RuntimeError("stuck")

    controller._do_stepper_move(cavity, True)

    assert any("Stepper move error" in m for m in view.logs)


# ------------------------------------------------------------------
# Record restore
# ------------------------------------------------------------------


def test_restore_from_record_none_is_noop() -> None:
    controller = _make_controller()
    controller._reset_all_stages = Mock()
    controller.restore_from_record(None)
    controller._reset_all_stages.assert_not_called()


def test_restore_from_record_all_stages() -> None:
    controller = _make_controller()
    controller._reset_all_stages = Mock()
    controller._restore_stage1 = Mock()
    controller._restore_stage2 = Mock()
    controller._restore_stage3 = Mock()
    controller._restore_stage4 = Mock()
    controller._load_stage_history = Mock(
        return_value={
            "cold_landing": {"df_cold_hz": 1.0},
            "probe_direction": {"hz_per_microstep": 2.0},
            "tune_to_resonance": {"net_steps": -5},
            "pi_modes": {"mode_8pi_9_hz": 100.0},
        }
    )

    controller.restore_from_record(_record())

    controller._restore_stage1.assert_called_once()
    controller._restore_stage2.assert_called_once()
    controller._restore_stage3.assert_called_once()
    controller._restore_stage4.assert_called_once()


def test_restore_from_record_stage3_no_stage4_enables_btn() -> None:
    controller = _make_controller()
    controller._reset_all_stages = Mock()
    controller._restore_stage1 = Mock()
    controller._restore_stage3 = Mock()
    controller._enable_stage_btn = Mock()
    controller._load_stage_history = Mock(
        return_value={
            "cold_landing": {"df_cold_hz": 1.0},
            "tune_to_resonance": {"net_steps": -5},
        }
    )

    controller.restore_from_record(_record())

    controller._enable_stage_btn.assert_called_once_with(4)


def test_load_stage_history_from_rows() -> None:
    session = Mock()
    session.get_measurement_history.return_value = [
        {"measurement_data": {"step": "cold_landing", "df_cold_hz": 1}},
        {"measurement_data": {"step": "probe_direction"}},
    ]
    controller = _make_controller(session=session)

    history = controller._load_stage_history(_record())

    assert "cold_landing" in history
    assert "probe_direction" in history


def test_load_stage_history_falls_back_to_blob() -> None:
    session = Mock()
    session.get_measurement_history.return_value = []
    controller = _make_controller(session=session)
    record = _record()
    record.frequency_tuning = FrequencyTuningData(df_cold_hz=7.0)

    history = controller._load_stage_history(record)

    assert "cold_landing" in history


def test_synthesize_history_from_blob_none() -> None:
    controller = _make_controller()
    record = _record()
    record.frequency_tuning = None
    assert controller._synthesize_history_from_blob(record) == {}


def test_synthesize_history_from_blob_full() -> None:
    controller = _make_controller()
    record = _record()
    record.frequency_tuning = FrequencyTuningData(
        df_cold_hz=1.0,
        hz_per_microstep=2.0,
        cold_landing_steps=10,
        steps_to_resonance=50,
    )

    result = controller._synthesize_history_from_blob(record)

    assert "cold_landing" in result
    assert "probe_direction" in result
    assert "tune_to_resonance" in result
    assert result["tune_to_resonance"]["net_steps"] == -10


def test_reset_all_stages() -> None:
    view = _ViewStub()
    view.stage2_run_btn.setEnabled(True)
    controller = _make_controller(view=view)
    controller.phase = Mock()
    controller.context = Mock()

    controller._reset_all_stages()

    assert view.stage1_run_btn.enabled is True
    assert view.stage2_run_btn.enabled is False
    assert controller.phase is None
    assert controller.context is None
    assert view.hz_per_step_spinbox.enabled is False


def test_restore_stage1_rebuilds_context() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller._rebuild_phase_context = Mock()
    controller._enable_stage_btn = Mock()

    controller._restore_stage1({"df_cold_hz": 3.0}, _record(), has_probe=False)

    assert controller._df_cold_hz == 3.0
    assert view.stage1_run_btn.enabled is False
    controller._rebuild_phase_context.assert_called_once()
    controller._enable_stage_btn.assert_called_once_with(2)


def test_rebuild_phase_context_success(monkeypatch) -> None:
    class _PhaseStub:
        def __init__(self, ctx):
            self.context = ctx

        def validate_prerequisites(self):
            return (True, "ok")

    monkeypatch.setattr(controller_module, "FrequencyTuningPhase", _PhaseStub)
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller._get_machine_cavity = Mock(return_value=Mock())
    controller._apply_stepper_pv_mapping = Mock()

    controller._rebuild_phase_context(_record())

    assert controller.phase is not None
    assert controller._phase_started is True


def test_rebuild_phase_context_exception_logged() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller._get_machine_cavity = Mock(side_effect=RuntimeError("bad"))

    controller._rebuild_phase_context(_record())

    assert any("could not rebuild phase context" in m for m in view.logs)


def test_restore_stage2_sets_hz() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller.phase = Mock()
    controller.phase.limits.probe_steps = 50000
    controller._enable_stage_btn = Mock()

    controller._restore_stage2({"hz_per_microstep": 2.5}, has_tune=False)

    assert controller.phase._hz_per_microstep == 2.5
    assert controller._probe_stage_confirmed is True
    assert view.hz_per_step_spinbox.value() == 2.5
    controller._enable_stage_btn.assert_called_once_with(3)


def test_restore_stage2_seeds_hz_estimator_accumulators() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller.phase = Mock()
    controller.phase.limits.probe_steps = 100
    controller._enable_stage_btn = Mock()

    controller._restore_stage2({"hz_per_microstep": 2.5}, has_tune=False)

    assert controller._hz_est_total_steps == 100
    assert controller._hz_est_total_hz == 2.5 * 100


def test_restore_stage2_does_not_crash_when_phase_is_none() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller.phase = None
    controller._enable_stage_btn = Mock()

    # Should not raise even when phase is None and signed_hz is nonzero
    controller._restore_stage2({"hz_per_microstep": 2.5}, has_tune=False)

    # Accumulators should remain at their default (0.0) since phase is None
    assert controller._hz_est_total_steps == 0.0
    assert controller._hz_est_total_hz == 0.0


def test_restore_stage3_sets_net_steps() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)

    controller._restore_stage3({"net_steps": -7})

    assert controller._net_steps == -7
    view.local_phase_status.setText.assert_called_with("AT RESONANCE")


def test_restore_stage4_sets_pi_modes() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)

    controller._restore_stage4({"mode_8pi_9_hz": 100.0, "mode_7pi_9_hz": 80.0})

    assert controller._pi_mode_data["mode_8pi_9_hz"] == 100.0
    view.local_phase_status.setText.assert_called_with("PI MODES DONE")


# ------------------------------------------------------------------
# _auto_create_record
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


def test_auto_create_record_no_cavity_shows_error() -> None:
    view = _ViewStub()
    view.parent = lambda: _ParentWithCombos(cm="", cav="")
    controller = _make_controller(view=view)

    assert controller._auto_create_record() is False
    assert view.errors


def test_auto_create_record_success() -> None:
    view = _ViewStub()
    view.parent = lambda: _ParentWithCombos(cm="02", cav="1")
    session = Mock()
    session.start_new_record.return_value = (_record(), 10, True)
    controller = _make_controller(view=view, session=session)
    controller.update_pv_addresses = Mock()

    assert controller._auto_create_record() is True


def test_auto_create_record_exception_shows_error() -> None:
    view = _ViewStub()
    view.parent = lambda: _ParentWithCombos(cm="02", cav="1")
    session = Mock()
    session.start_new_record.side_effect = RuntimeError("db down")
    controller = _make_controller(view=view, session=session)

    assert controller._auto_create_record() is False
    assert view.errors


# ------------------------------------------------------------------
# _check_data_prerequisites
# ------------------------------------------------------------------


def test_check_data_prereqs_stage2_missing_df_cold_logs_error() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller._df_cold_hz = None

    result = controller._check_data_prerequisites(2)

    assert result is False
    assert any("cold landing" in m.lower() for m in view.logs)


def test_check_data_prereqs_stage2_with_df_cold_logs_success() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller._df_cold_hz = 5000.0

    result = controller._check_data_prerequisites(2)

    assert result is True
    assert any("5000" in m for m in view.logs)


def test_check_data_prereqs_stage3_missing_probe_logs_error() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller._probe_stage_confirmed = False

    result = controller._check_data_prerequisites(3)

    assert result is False
    assert any("hz/step" in m.lower() for m in view.logs)


def test_check_data_prereqs_stage3_confirmed_logs_success() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller._probe_stage_confirmed = True

    result = controller._check_data_prerequisites(3)

    assert result is True
    assert any("hz/step" in m.lower() for m in view.logs)


def test_check_data_prereqs_stage4_always_passes() -> None:
    controller = _make_controller()
    assert controller._check_data_prerequisites(4) is True


# ------------------------------------------------------------------
# run_stage_2/3/4 data prereq integration
# ------------------------------------------------------------------


def test_run_stage_2_missing_df_cold_stops_before_background() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller.phase = Mock()
    controller.context = Mock()
    controller._df_cold_hz = None
    controller._run_phase_in_background = Mock()

    controller.run_stage_2()

    controller._run_phase_in_background.assert_not_called()
    assert any("cold landing" in m.lower() for m in view.logs)


def test_run_stage_2_with_df_cold_proceeds() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller.phase = Mock()
    controller.context = Mock()
    controller._df_cold_hz = 5000.0
    controller._run_phase_in_background = Mock()

    controller.run_stage_2()

    controller._run_phase_in_background.assert_called_once()


def test_run_stage_3_missing_probe_stops_before_background() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller.phase = Mock()
    controller.phase._hz_per_microstep = None
    controller.context = Mock()
    controller._probe_stage_confirmed = False
    controller._run_phase_in_background = Mock()

    controller.run_stage_3()

    controller._run_phase_in_background.assert_not_called()
    assert any("hz/step" in m.lower() for m in view.logs)


def test_run_stage_3_with_probe_proceeds() -> None:
    view = _ViewStub()
    controller = _make_controller(view=view)
    controller.phase = Mock()
    controller.phase._hz_per_microstep = 2.0
    controller.context = Mock()
    controller._probe_stage_confirmed = True
    controller._run_phase_in_background = Mock()

    controller.run_stage_3()

    controller._run_phase_in_background.assert_called_once()
