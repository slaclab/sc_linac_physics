"""Tests for note, measurement, and operator persistence helpers."""

from __future__ import annotations

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
    CommissioningRecord,
    PiezoPreRFCheck,
)
from sc_linac_physics.applications.rf_commissioning.models.persistence.database import (
    CommissioningDatabase,
    RecordConflictError,
)


def _new_db(tmp_path) -> CommissioningDatabase:
    db = CommissioningDatabase(str(tmp_path / "commissioning.db"))
    db.initialize()
    return db


def _new_record() -> CommissioningRecord:
    return CommissioningRecord(linac=1, cryomodule="02", cavity_number=1)


def test_operator_repository_normalizes_and_deduplicates_names(tmp_path):
    db = _new_db(tmp_path)

    assert db.add_operator("  Alice  ") is True
    assert db.add_operator("Alice") is False
    assert db.add_operator("Bob") is True
    assert db.add_operator("   ") is False
    assert db.get_operators() == ["Alice", "Bob"]


def test_general_notes_round_trip_with_versioned_updates(tmp_path):
    db = _new_db(tmp_path)
    record_id = db.save_record(_new_record())

    loaded = db.get_record_with_version(record_id)
    assert loaded is not None
    _, version = loaded

    assert db.append_general_note(
        record_id,
        operator="tester",
        note="first note",
        expected_version=version,
    )

    notes = db.get_general_notes(record_id)
    assert len(notes) == 1
    assert notes[0]["operator"] == "tester"
    assert notes[0]["note"] == "first note"

    refreshed = db.get_record_with_version(record_id)
    assert refreshed is not None
    _, updated_version = refreshed

    assert db.update_general_note(
        record_id,
        note_index=0,
        operator="reviewer",
        note="edited note",
        expected_version=updated_version,
    )

    updated_notes = db.get_general_notes(record_id)
    assert updated_notes[0]["operator"] == "reviewer"
    assert updated_notes[0]["note"] == "edited note"
    assert "edited_at" in updated_notes[0]

    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE commissioning_records SET version = version + 1 WHERE id = ?",
            (record_id,),
        )

    try:
        db.append_general_note(
            record_id,
            operator="tester",
            note="stale",
            expected_version=updated_version,
        )
    except RecordConflictError as exc:
        assert exc.record_id == record_id
    else:
        raise AssertionError("Expected stale note update to raise conflict")


def test_update_general_note_rejects_invalid_index(tmp_path):
    db = _new_db(tmp_path)
    record_id = db.save_record(_new_record())

    assert (
        db.update_general_note(
            record_id,
            note_index=0,
            operator="tester",
            note="missing",
        )
        is False
    )


def test_measurement_history_serializes_models_and_supports_note_updates(
    tmp_path,
):
    db = _new_db(tmp_path)
    record_id = db.save_record(_new_record())

    entry_id = db.add_measurement_history(
        record_id,
        CommissioningPhase.PIEZO_PRE_RF,
        PiezoPreRFCheck(
            capacitance_a=2.1e-9,
            capacitance_b=2.2e-9,
            channel_a_passed=True,
            channel_b_passed=False,
        ),
        operator="tester",
        notes="initial note",
    )

    history = db.get_measurement_history(
        record_id, CommissioningPhase.PIEZO_PRE_RF
    )
    assert len(history) == 1
    assert history[0]["measurement_data"]["capacitance_a"] == 2.1e-9
    assert history[0]["measurement_data"]["channel_a_passed"] is True
    assert history[0]["notes"][0]["note"] == "initial note"

    assert db.append_measurement_note(entry_id, "tester", "follow-up") is True
    assert (
        db.update_measurement_note(entry_id, 0, "editor", "edited initial")
        is True
    )
    assert (
        db.update_measurement_note(entry_id, 99, "editor", "missing") is False
    )
    assert (
        db.append_measurement_note(entry_id + 1000, "tester", "missing")
        is False
    )

    notes = db.get_measurement_notes(record_id, CommissioningPhase.PIEZO_PRE_RF)
    assert len(notes) == 2
    assert notes[0]["operator"] == "editor"
    assert notes[0]["note"] == "edited initial"
    assert notes[1]["note"] == "follow-up"
