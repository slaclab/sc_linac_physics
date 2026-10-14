"""Tests for reviewing and pushing cavity characterization results."""

from unittest.mock import Mock, patch

import pytest
from PyQt5.QtWidgets import QPushButton, QWidget

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CavityCharacterization,
    CommissioningPhase,
    CommissioningRecord,
)
from sc_linac_physics.applications.rf_commissioning.phases.phase_base import (
    PhaseResult,
)
from sc_linac_physics.applications.rf_commissioning.session_manager import (
    CommissioningSession,
)
from sc_linac_physics.applications.rf_commissioning.ui.builders import (
    CavityCharUI,
)
from sc_linac_physics.applications.rf_commissioning.ui.controllers.cavity_char_controller import (  # noqa: E501
    PUSH_STEPS,
    CavityCharController,
)


class RunInline:
    """threading.Thread stand-in that runs the target on this thread."""

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


def _in_window():
    return {
        "loaded_q": 4.1e7,
        "scale_factor": 31.5,
        "probe_q": 8.5e11,
        "loaded_q_in_tolerance": True,
        "scale_factor_in_tolerance": True,
        "drive_level": 10.0,
    }


def _out_of_window():
    return dict(_in_window(), loaded_q=6.0e7, loaded_q_in_tolerance=False)


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


def test_push_button_is_built_disabled(qapp_global):
    ui = CavityCharUI(QWidget(), callbacks={})
    ui.build()
    button = ui.widgets["push_results_button"]
    assert isinstance(button, QPushButton)
    assert not button.isEnabled()


def test_results_rows_are_built(qapp_global):
    ui = CavityCharUI(QWidget(), callbacks={})
    ui.build()
    for name in (
        "loaded_q_label",
        "q_window_label",
        "scale_factor_label",
        "probe_q_label",
        "tolerance_label",
    ):
        assert name in ui.widgets


# ---------------------------------------------------------------------------
# Controller
# ---------------------------------------------------------------------------


@pytest.fixture
def view():
    return Mock()


def _measured_controller(view, monkeypatch):
    session = Mock()
    session.get_active_record.return_value = Mock()
    c = CavityCharController(view, session)
    c.context = Mock()
    c.context.parameters = {}
    c.context.record.cavity_char = CavityCharacterization(loaded_q=4.1e7)
    c.phase = Mock()
    c.phase._loaded_q = 4.1e7
    c._active_phase_instance_id = 42
    monkeypatch.setattr("threading.Thread", RunInline)
    return c


def test_push_with_nothing_measured_does_not_write(view):
    c = CavityCharController(view, Mock())
    c.phase = None
    c.on_push_results()
    view.show_error.assert_called_once()


def test_push_confirms_the_loaded_q_it_was_shown(view, monkeypatch):
    """CavityCharPhase._push_results refuses unless these match."""
    c = _measured_controller(view, monkeypatch)
    c.phase.execute_step.return_value = _result(PhaseResult.SUCCESS)
    c.on_push_results()
    assert c.context.parameters["confirmed_loaded_q"] == 4.1e7


def test_push_runs_push_then_record_then_finalizes(view, monkeypatch):
    c = _measured_controller(view, monkeypatch)
    c.phase.execute_step.return_value = _result(PhaseResult.SUCCESS)
    finished = []
    c.push_finished.connect(lambda ok, msg: finished.append(ok))

    c.on_push_results()

    ran = [call.args[0] for call in c.phase.execute_step.call_args_list]
    assert ran == list(PUSH_STEPS) == ["push_results", "record_results"]
    c.phase.finalize_phase.assert_called_once()
    assert finished == [True]


def test_a_refused_push_does_not_finalize(view, monkeypatch):
    """E.g. a value changed since review: nothing was pushed."""
    c = _measured_controller(view, monkeypatch)
    c.phase.execute_step.return_value = _result(
        PhaseResult.FAILED, "QLOADED_NEW changed since the values were reviewed"
    )
    finished = []
    c.push_finished.connect(lambda ok, msg: finished.append((ok, msg)))

    c.on_push_results()

    c.phase.finalize_phase.assert_not_called()
    assert finished == [
        (False, "QLOADED_NEW changed since the values were reviewed")
    ]


def test_a_successful_push_completes_and_advances(view, monkeypatch):
    c = _measured_controller(view, monkeypatch)
    advanced = []
    c.phase_completed.connect(advanced.append)

    c._on_push_finished(True, "")

    c.session.complete_active_phase_instance.assert_called_once()
    kwargs = c.session.complete_active_phase_instance.call_args.kwargs
    assert kwargs["phase_instance_id"] == 42
    assert kwargs["phase"] is CommissioningPhase.CAVITY_CHAR
    c.session.save_active_record.assert_called_once()
    c.session.add_measurement_to_history.assert_called_once()
    view.refresh_from_record.assert_called_once()
    assert advanced == [c.session.get_active_record.return_value]
    assert c._active_phase_instance_id is None


def test_a_refused_push_keeps_the_phase_open(view, monkeypatch):
    c = _measured_controller(view, monkeypatch)
    c._on_push_finished(False, "nothing pushed")
    c.session.complete_active_phase_instance.assert_not_called()
    c.session.fail_active_phase_instance.assert_not_called()
    view.show_error.assert_called_once_with("nothing pushed")


def test_read_results_publishes_the_values_for_review(view, monkeypatch):
    c = _measured_controller(view, monkeypatch)
    c.phase.execute_step.return_value = _result(
        PhaseResult.SUCCESS, data=_in_window()
    )
    seen = []
    c.results_ready.connect(seen.append)
    assert c._execute_single_step("read_results")
    assert seen == [_in_window()]


def test_a_rerun_reuses_the_open_phase_instance(view):
    """A measurement that was never pushed leaves its instance open.

    Starting another would leave that one in_progress for good.
    """
    session = Mock()
    session.can_run_phase.return_value = (True, "ok")
    session.get_active_record_id.return_value = 7
    c = CavityCharController(view, session)
    c._active_phase_instance_id = 42
    with patch(
        "sc_linac_physics.applications.rf_commissioning.ui.controllers."
        "cavity_char_controller.CavityCharPhase"
    ) as phase_cls:
        phase_cls.return_value.validate_prerequisites.return_value = (
            True,
            "ok",
        )
        assert c._prepare_phase_context(Mock(), "lisa", 10.0)
    session.start_active_phase_instance.assert_not_called()
    assert c.context.phase_instance_id == 42


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------


@pytest.fixture
def display(qtbot, tmp_path):
    from sc_linac_physics.applications.rf_commissioning.ui.displays.cavity_char import (  # noqa: E501
        CavityCharDisplay,
    )

    s = CommissioningSession(db_path=str(tmp_path / "cav.db"))
    with patch("PyQt5.QtCore.QTimer.singleShot"):
        d = CavityCharDisplay(session=s)
        qtbot.addWidget(d)
        d.cavity_loaded_q_window = (3.5e7, 4.5e7)
        return d


def test_push_button_enables_after_a_read(display):
    display.on_results_ready(_in_window())
    assert display.push_results_button.isEnabled()
    assert display.loaded_q_label.text() == "4.100e+07"
    assert display.probe_q_label.text() == "8.500e+11"


def test_an_out_of_window_read_says_so(display):
    display.on_results_ready(_out_of_window())
    assert "outside" in display.tolerance_label.text().lower()
    # Pushing it is still the operator's call (CavityCharPhase._push_results).
    assert display.push_results_button.isEnabled()


def test_confirm_text_names_the_pvs_and_values(display):
    text = display._confirm_push_text(_in_window())
    for expected in (
        "PUSH_QLOADED.PROC",
        "PUSH_CAV_SCALE.PROC",
        "PUSH_QPROBECALC.PROC",
        "4.100e+07",
        "31.5",
        "8.500e+11",
    ):
        assert expected in text


def test_confirm_text_flags_an_out_of_window_value(display):
    text = display._confirm_push_text(_out_of_window())
    assert "outside" in text.lower()


def test_a_declined_confirm_does_not_push(display, monkeypatch):
    display.on_results_ready(_in_window())
    monkeypatch.setattr(display, "_ask_confirm", lambda text: False)
    pushed = []
    monkeypatch.setattr(
        display.controller, "on_push_results", lambda: pushed.append(1)
    )
    display.on_push_results()
    assert pushed == []


def test_an_accepted_confirm_pushes(display, monkeypatch):
    display.on_results_ready(_in_window())
    monkeypatch.setattr(display, "_ask_confirm", lambda text: True)
    pushed = []
    monkeypatch.setattr(
        display.controller, "on_push_results", lambda: pushed.append(1)
    )
    display.on_push_results()
    assert pushed == [1]


def test_a_successful_push_disables_the_button(display):
    display.on_results_ready(_in_window())
    display._on_push_finished(True, "")
    assert not display.push_results_button.isEnabled()


def test_a_loaded_record_shows_values_but_cannot_push(display):
    """The push gate lives on the phase that read the values.

    A record loaded from the database has values but no such phase, so
    pushing them needs a fresh measurement.
    """
    record = CommissioningRecord(linac=0, cryomodule="01", cavity_number=1)
    record.cavity_char = CavityCharacterization(
        loaded_q=4.1e7, scale_factor=31.5, loaded_q_in_tolerance=True
    )
    display.refresh_from_record(record)
    assert display.loaded_q_label.text() == "4.100e+07"
    assert not display.push_results_button.isEnabled()
