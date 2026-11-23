"""Tests for persist_finished_phase, the end-of-phase database writes."""

from unittest.mock import Mock

import pytest

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
)
from sc_linac_physics.applications.rf_commissioning.ui.controllers.phase_persistence import (  # noqa: E501
    FINISH_WRITES,
    persist_finished_phase,
)

PHASE = CommissioningPhase.MP_PROCESSING


@pytest.fixture
def session():
    s = Mock()
    s.complete_active_phase_instance.return_value = True
    s.save_active_record.return_value = True
    s.add_measurement_to_history.return_value = True
    return s


def _persist(session, unsaved=FINISH_WRITES, data=None, instance_id=7):
    data = data if data is not None else Mock(to_dict=lambda: {"x": 1})
    return persist_finished_phase(
        session, PHASE, instance_id, data, "op", set(unsaved), Mock()
    )


def test_all_writes_succeed(session):
    assert _persist(session) == set()
    session.complete_active_phase_instance.assert_called_once_with(
        phase_instance_id=7, phase=PHASE, artifact_payload={"x": 1}
    )
    session.save_active_record.assert_called_once()
    session.add_measurement_to_history.assert_called_once()


def test_a_false_or_raising_write_stays_unsaved(session):
    session.save_active_record.return_value = False
    session.add_measurement_to_history.side_effect = RuntimeError("db")
    assert _persist(session) == {"save", "history"}


def test_a_retry_runs_only_what_failed(session):
    assert _persist(session, unsaved={"history"}) == set()
    session.complete_active_phase_instance.assert_not_called()
    session.save_active_record.assert_not_called()


def test_no_instance_id_counts_as_completed(session):
    assert _persist(session, unsaved={"complete"}, instance_id=None) == set()
    session.complete_active_phase_instance.assert_not_called()
