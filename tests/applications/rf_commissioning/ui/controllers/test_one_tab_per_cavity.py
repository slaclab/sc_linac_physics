"""A cavity another tab is running is refused before anything is written."""

from unittest.mock import Mock

import pytest

from sc_linac_physics.applications.rf_commissioning.models.commissioning_machine import (
    get_commissioning_machine,
)
from sc_linac_physics.applications.rf_commissioning.phases.step_runner import (
    SegmentOutcome,
)
from sc_linac_physics.applications.rf_commissioning.ui.controllers.batch_piezo_pre_rf_controller import (
    BatchPiezoPreRFController,
    CavityRunState,
    CavitySpec,
)
from sc_linac_physics.applications.rf_commissioning.ui.controllers.cavity_char_controller import (
    CavityCharController,
)
from sc_linac_physics.applications.rf_commissioning.ui.controllers.cavity_hold import (
    CavityHold,
    refusal_message,
)
from sc_linac_physics.applications.rf_commissioning.ui.controllers.frequency_tuning_controller import (
    FrequencyTuningController,
)
from sc_linac_physics.applications.rf_commissioning.ui.controllers.piezo_pre_rf_controller import (
    PiezoPreRFController,
)
from sc_linac_physics.applications.rf_commissioning.ui.controllers.piezo_with_rf_controller import (
    PiezoWithRFController,
)
from sc_linac_physics.applications.rf_commissioning.ui.controllers.ssa_char_controller import (
    SSACharController,
)


@pytest.fixture
def cavity():
    return get_commissioning_machine().cryomodules["02"].cavities[1]


@pytest.fixture
def other_tab(cavity):
    """Another tab already running the cavity."""
    hold = CavityHold("the Other tab")
    assert hold.take(cavity)
    return hold


def _refused(view) -> bool:
    view.show_error.assert_called_once()
    return "the Other tab" in view.show_error.call_args.args[0]


# ---------------------------------------------------------------------------
# CavityHold
# ---------------------------------------------------------------------------


def test_hold_release_frees_every_cavity():
    machine = get_commissioning_machine()
    first = machine.cryomodules["02"].cavities[1]
    second = machine.cryomodules["02"].cavities[2]
    hold = CavityHold("the Test tab")
    assert hold.take(first) and hold.take(second)

    hold.release()

    assert first.claimed_by is None
    assert second.claimed_by is None


def test_hold_refused_while_another_hold_has_it(cavity, other_tab):
    assert not CavityHold("the Test tab").take(cavity)
    assert "the Other tab" in refusal_message(cavity)


def test_every_tab_gets_the_same_cavity_object():
    ft = FrequencyTuningController(Mock(), Mock())
    cc = CavityCharController(Mock(), Mock())

    assert ft._get_machine_cavity("02", 1) is cc._get_machine_cavity("02", 1)


# ---------------------------------------------------------------------------
# Refused starts write nothing to the database or the machine
# ---------------------------------------------------------------------------


def test_frequency_tuning_stage_1_refused(cavity, other_tab):
    view, session = Mock(), Mock()
    c = FrequencyTuningController(view, session)
    c.update_pv_addresses = Mock()

    c._start_stage(1, ["verify_initial_state"], False, "02", 1, "op")

    assert _refused(view)
    session.can_run_phase.assert_not_called()
    session.start_active_phase_instance.assert_not_called()


def test_frequency_tuning_later_stage_refused(cavity, other_tab):
    view = Mock()
    c = FrequencyTuningController(view, Mock())
    c._get_operator = Mock(return_value="op")
    c._check_data_prerequisites = Mock(return_value=True)
    c.phase, c.context, c._cavity = Mock(), Mock(), cavity

    c.run_stage_2()

    assert _refused(view)
    assert not c._stage_running


def _frequency_tuning_holding(cavity):
    c = FrequencyTuningController(Mock(), Mock())
    c._cavity = cavity
    assert c._take_cavity()
    return c


def test_frequency_tuning_keeps_the_cavity_between_stages(cavity):
    c = _frequency_tuning_holding(cavity)

    # What a finished stage does before enabling the next one.
    c._clear_running_ui()

    assert cavity.claimed_by is c._cavity_hold


@pytest.mark.parametrize(
    "end", [lambda c: c.on_phase_completed(), lambda c: c.on_phase_failed("x")]
)
def test_frequency_tuning_releases_when_the_phase_ends(cavity, end):
    c = _frequency_tuning_holding(cavity)

    end(c)

    assert cavity.claimed_by is None


def test_frequency_tuning_releases_on_another_cavity(cavity, monkeypatch):
    c = _frequency_tuning_holding(cavity)
    other = get_commissioning_machine().cryomodules["02"].cavities[2]
    monkeypatch.setattr(
        "sc_linac_physics.applications.rf_commissioning.ui.controllers."
        "frequency_tuning_controller.resolve_cavity_selection",
        lambda view, cm, cav: (cm, cav),
    )
    c._apply_stepper_pv_mapping = Mock()

    c.update_pv_addresses("02", "2")

    assert cavity.claimed_by is None
    assert c._cavity is other


def test_frequency_tuning_failed_restart_keeps_an_earlier_hold(cavity):
    session = Mock()
    session.can_run_phase.return_value = (False, "gated")
    c = FrequencyTuningController(Mock(), session)
    c.update_pv_addresses = Mock()
    c._cavity = cavity
    assert c._take_cavity()

    c._start_stage(1, ["verify_initial_state"], False, "02", 1, "op")

    assert cavity.claimed_by is c._cavity_hold


def test_ssa_refused(cavity, other_tab):
    view, session = Mock(), Mock()
    c = SSACharController(view, session)
    c.update_pv_addresses = Mock()
    c._get_drive_max = Mock(return_value=0.8)

    c._start_run_for_target("02", 1, "op")

    assert _refused(view)
    session.start_active_phase_instance.assert_not_called()


def test_ssa_releases_on_failure(cavity):
    c = SSACharController(Mock(), Mock())
    assert c._cavity_hold.take(cavity)

    c.on_phase_failed("boom")

    assert cavity.claimed_by is None


def test_piezo_pre_rf_refused(cavity, other_tab):
    view, session = Mock(), Mock()
    c = PiezoPreRFController(view, session)
    c._get_operator = Mock(return_value="op")
    c._get_selected_cavity_info = Mock(return_value=("02-1", "02", 1))
    c.update_pv_addresses = Mock()
    c._prepare_phase_context = Mock()

    c.on_run_automated_test()

    assert _refused(view)
    c._prepare_phase_context.assert_not_called()


def test_cavity_char_refused(cavity, other_tab):
    view = Mock()
    view.get_current_operator.return_value = "op"
    c = CavityCharController(view, Mock())
    c._get_drive_level = Mock(return_value=10.0)
    c._cavity = cavity

    c.on_run_characterization()

    assert _refused(view)
    assert not c._running


def test_piezo_with_rf_refused(cavity, other_tab):
    view, session = Mock(), Mock()
    view.get_current_operator.return_value = "op"
    session.can_run_phase.return_value = (True, "")
    c = PiezoWithRFController(view, session)
    c._cavity = cavity

    c.on_start_test()

    assert _refused(view)
    session.start_active_phase_instance.assert_not_called()


def test_batch_skips_a_cavity_another_tab_is_running(cavity, other_tab):
    session = Mock()
    ctrl = BatchPiezoPreRFController(session)
    state = CavityRunState(spec=CavitySpec(cryomodule="02", cavity_number=1))

    with pytest.raises(ValueError, match="the Other tab"):
        ctrl._init_record_and_context(state, "op")

    session.get_record_id_for_cavity.assert_not_called()


def test_batch_releases_when_the_run_ends(cavity):
    ctrl = BatchPiezoPreRFController(Mock())
    assert ctrl._cavity_hold.take(cavity)

    ctrl._run_batch([], "op")

    assert cavity.claimed_by is None


def _piezo_with_rf_holding(cavity):
    c = PiezoWithRFController(Mock(), Mock())
    c._cavity = cavity
    assert c._cavity_hold.take(cavity)
    return c


def test_piezo_with_rf_keeps_the_cavity_between_segments(cavity):
    c = _piezo_with_rf_holding(cavity)
    c.stage = "measure"
    c._on_measured = Mock()
    result = Mock(outcome=SegmentOutcome.COMPLETED, results={})
    result.results = {"read_results": Mock(data={})}

    c._on_segment_finished(result)

    assert cavity.claimed_by is c._cavity_hold


@pytest.mark.parametrize(
    "end", [lambda c: c._on_failed("x"), lambda c: c.drop_review()]
)
def test_piezo_with_rf_releases(cavity, end):
    c = _piezo_with_rf_holding(cavity)
    c.context = None

    end(c)

    assert cavity.claimed_by is None


# ---------------------------------------------------------------------------
# Stage 1 claims before it loads the record, and frees what it claimed
# ---------------------------------------------------------------------------


def _stage1_controller(session, monkeypatch):
    monkeypatch.setattr(
        "sc_linac_physics.applications.rf_commissioning.ui.controllers."
        "frequency_tuning_controller.resolve_cavity_selection",
        lambda view, cm, cav: ("02", "1"),
    )
    view = Mock()
    c = FrequencyTuningController(view, session)
    c._get_operator = Mock(return_value="op")
    c._set_stage_status_not_started = Mock()
    c.update_pv_addresses = Mock()
    c._decide_ssa_calibration = Mock(return_value=(True, None))
    return c, view


def test_stage_1_refused_before_the_record_is_loaded(
    cavity, other_tab, monkeypatch
):
    session = Mock()
    c, view = _stage1_controller(session, monkeypatch)

    c.run_stage_1()

    assert _refused(view)
    session.start_new_record.assert_not_called()
    c._set_stage_status_not_started.assert_called_once_with(1)


def test_stage_1_releases_its_claim_when_the_start_raises(cavity, monkeypatch):
    session = Mock()
    session.can_run_phase.side_effect = RuntimeError("db down")
    c, _ = _stage1_controller(session, monkeypatch)
    assert c._claim_for_stage1("02", 1)
    c._pending_stage1 = ("02", 1, "op")

    c._on_last_ssa_cal_read(None, "")

    assert cavity.claimed_by is None
    c._set_stage_status_not_started.assert_called_once_with(1)


def test_stage_1_gated_keeps_a_hold_from_an_earlier_stage(cavity, monkeypatch):
    session = Mock()
    session.can_run_phase.return_value = (False, "gated")
    c, _ = _stage1_controller(session, monkeypatch)
    c._cavity = cavity
    assert c._take_cavity()
    assert c._claim_for_stage1("02", 1)
    c._pending_stage1 = ("02", 1, "op")

    c._on_last_ssa_cal_read(None, "")

    assert cavity.claimed_by is c._cavity_hold


# ---------------------------------------------------------------------------
# A new claim starts with no abort pending
# ---------------------------------------------------------------------------


def test_new_claim_clears_stale_abort_flags(cavity):
    cavity.abort_flag = True
    cavity.stepper_tuner.abort_flag = True

    assert CavityHold("the Test tab").take(cavity)

    assert cavity.abort_flag is False
    assert cavity.stepper_tuner.abort_flag is False


def test_retaking_a_held_cavity_keeps_its_abort_flags(cavity):
    hold = CavityHold("the Test tab")
    assert hold.take(cavity)
    cavity.abort_flag = True

    assert hold.take(cavity)

    assert cavity.abort_flag is True
