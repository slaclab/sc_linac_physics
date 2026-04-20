"""Tests for RF commissioning persistence helpers."""

from __future__ import annotations

import json

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
    PhaseStatus,
    SSACharacterization,
)
from sc_linac_physics.applications.rf_commissioning.models.persistence.database_helpers import (
    append_note,
    build_note_entry,
    build_workflow_state,
    coerce_phase,
    parse_json_list,
    serialize_measurement_data,
    update_note,
)


def test_parse_json_list_tolerates_missing_invalid_and_legacy_payloads():
    assert parse_json_list(None) == []
    assert parse_json_list("") == []
    assert parse_json_list("not-json") == []
    assert parse_json_list('{"note": "legacy"}') == []
    assert parse_json_list('[{"note": "ok"}]') == [{"note": "ok"}]


def test_note_helpers_build_append_and_update_canonical_entries():
    initial = build_note_entry(
        operator="tester",
        note="first",
        timestamp="2026-04-17T12:00:00",
    )
    assert initial == {
        "timestamp": "2026-04-17T12:00:00",
        "operator": "tester",
        "note": "first",
    }

    appended = append_note(
        [initial],
        operator="reviewer",
        note="second",
        timestamp="2026-04-17T12:05:00",
    )
    assert appended[-1] == {
        "timestamp": "2026-04-17T12:05:00",
        "operator": "reviewer",
        "note": "second",
    }

    updated = update_note(
        appended,
        note_index=0,
        operator="editor",
        note="edited",
        timestamp="2026-04-17T12:10:00",
    )
    assert updated is not None
    assert updated[0] == {
        "timestamp": "2026-04-17T12:10:00",
        "operator": "editor",
        "note": "edited",
        "edited_at": "2026-04-17T12:10:00",
    }
    assert update_note(appended, note_index=99, operator=None, note="x") is None


def test_serialize_measurement_data_uses_model_to_dict():
    payload = serialize_measurement_data(
        SSACharacterization(max_drive=0.25, initial_drive=0.5, num_attempts=2)
    )

    parsed = json.loads(payload)
    assert parsed["max_drive"] == 0.25
    assert parsed["drive_reduction"] == 0.25
    assert parsed["is_complete"] is True


def test_coerce_phase_falls_back_to_first_phase_for_unknown_values():
    assert (
        coerce_phase(CommissioningPhase.SSA_CHAR) is CommissioningPhase.SSA_CHAR
    )
    assert coerce_phase("ssa_char") is CommissioningPhase.SSA_CHAR
    assert coerce_phase("not-a-phase") is CommissioningPhase.PIEZO_PRE_RF
    assert coerce_phase(None) is CommissioningPhase.PIEZO_PRE_RF


def test_build_workflow_state_defaults_when_run_missing():
    current_phase, overall_status, phase_status = build_workflow_state(None, [])

    assert current_phase is CommissioningPhase.PIEZO_PRE_RF
    assert overall_status == "not_started"
    assert (
        phase_status[CommissioningPhase.PIEZO_PRE_RF] is PhaseStatus.IN_PROGRESS
    )
    assert phase_status[CommissioningPhase.SSA_CHAR] is PhaseStatus.NOT_STARTED


def test_build_workflow_state_uses_latest_attempts_and_ignores_unknown_phases():
    run = {"current_phase": "unknown-phase", "status": "failed"}
    phase_rows = [
        {
            "phase": CommissioningPhase.PIEZO_PRE_RF.value,
            "attempt_number": 1,
            "status": "failed",
        },
        {
            "phase": CommissioningPhase.PIEZO_PRE_RF.value,
            "attempt_number": 2,
            "status": "complete",
        },
        {
            "phase": CommissioningPhase.SSA_CHAR.value,
            "attempt_number": 1,
            "status": "skipped",
        },
        {
            "phase": "unknown_phase",
            "attempt_number": 99,
            "status": "complete",
        },
    ]

    current_phase, overall_status, phase_status = build_workflow_state(
        run,
        phase_rows,
    )

    assert current_phase is CommissioningPhase.PIEZO_PRE_RF
    assert overall_status == "failed"
    assert phase_status[CommissioningPhase.PIEZO_PRE_RF] is PhaseStatus.COMPLETE
    assert phase_status[CommissioningPhase.SSA_CHAR] is PhaseStatus.SKIPPED
    assert (
        phase_status[CommissioningPhase.FREQUENCY_TUNING]
        is PhaseStatus.NOT_STARTED
    )


def test_build_workflow_state_marks_current_phase_in_progress_without_instances():
    current_phase, overall_status, phase_status = build_workflow_state(
        {
            "current_phase": CommissioningPhase.CAVITY_CHAR.value,
            "status": "in_progress",
        },
        [],
    )

    assert current_phase is CommissioningPhase.CAVITY_CHAR
    assert overall_status == "in_progress"
    assert (
        phase_status[CommissioningPhase.CAVITY_CHAR] is PhaseStatus.IN_PROGRESS
    )
