"""Tests for RF commissioning database integrity behavior."""

from __future__ import annotations

import sqlite3

import pytest

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
    CommissioningRecord,
)
from sc_linac_physics.applications.rf_commissioning.models.persistence.database import (
    CommissioningDatabase,
    RecordConflictError,
    RecordDeletionDisabledError,
)
from sc_linac_physics.applications.rf_commissioning.services.workflow_service import (
    WorkflowService,
)


def _new_record() -> CommissioningRecord:
    return CommissioningRecord(linac=1, cryomodule="02", cavity_number=1)


def test_foreign_keys_are_enforced_per_connection(tmp_path):
    db = CommissioningDatabase(str(tmp_path / "commissioning.db"))
    db.initialize()

    with pytest.raises(sqlite3.IntegrityError):
        with db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO measurement_history (
                    record_id, phase_instance_id, phase, timestamp,
                    operator, measurement_data, notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    999999,
                    None,
                    "piezo_pre_rf",
                    "2026-04-17T12:00:00",
                    "tester",
                    "{}",
                    "[]",
                    "2026-04-17T12:00:00",
                ),
            )


def test_save_record_raises_conflict_for_stale_version(tmp_path):
    db = CommissioningDatabase(str(tmp_path / "commissioning.db"))
    db.initialize()

    record = _new_record()
    record_id = db.save_record(record)

    loaded = db.get_record_with_version(record_id)
    assert loaded is not None
    stale_record, stale_version = loaded

    # Simulate another writer completing an update first.
    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE commissioning_records
            SET linac_number = ?, version = version + 1, updated_at = ?
            WHERE id = ?
            """,
            (
                "1",
                "2026-04-17T13:00:00",
                record_id,
            ),
        )

    with pytest.raises(RecordConflictError):
        db.save_record(
            stale_record,
            record_id=record_id,
            expected_version=stale_version,
        )


def test_record_summaries_prefer_normalized_workflow_state(tmp_path):
    db = CommissioningDatabase(str(tmp_path / "commissioning.db"))
    db.initialize()
    svc = WorkflowService(db)

    record = _new_record()
    record_id = db.save_record(record)

    started = svc.start_phase_for_record(
        record_id=record_id,
        phase=CommissioningPhase.PIEZO_PRE_RF,
        operator="tester",
    )
    svc.fail_phase_instance(
        record_id=record_id,
        phase_instance_id=started.phase_instance_id,
        phase=CommissioningPhase.PIEZO_PRE_RF,
        error_message="failed",
    )

    summaries = db.get_all_records()
    assert len(summaries) == 1
    assert summaries[0]["overall_status"] == "failed"
    assert (
        summaries[0]["current_phase"] == CommissioningPhase.PIEZO_PRE_RF.value
    )


def test_active_queries_use_workflow_runs_status(tmp_path):
    db = CommissioningDatabase(str(tmp_path / "commissioning.db"))
    db.initialize()
    svc = WorkflowService(db)

    record = _new_record()
    record_id = db.save_record(record)

    # Records are not active until a workflow run exists.
    assert db.get_active_records() == []
    assert db.get_record_by_cavity(1, "02", "1", active_only=True) is None
    assert db.get_active_record_id_for_cavity(1, "02", "1") is None

    started = svc.start_phase_for_record(
        record_id=record_id,
        phase=CommissioningPhase.PIEZO_PRE_RF,
        operator="tester",
    )
    assert started.phase_instance_id > 0

    active = db.get_active_records()
    assert len(active) == 1
    active_by_cavity = db.get_record_by_cavity(1, "02", "1", active_only=True)
    assert active_by_cavity is not None


def test_unique_cavity_record_prevents_duplicate_insert(tmp_path):
    db = CommissioningDatabase(str(tmp_path / "commissioning.db"))
    db.initialize()

    first_record_id = db.save_record(_new_record())
    assert first_record_id > 0

    with pytest.raises(sqlite3.IntegrityError):
        db.save_record(_new_record())


def test_database_stats_use_workflow_runs(tmp_path):
    db = CommissioningDatabase(str(tmp_path / "commissioning.db"))
    db.initialize()
    svc = WorkflowService(db)

    record = _new_record()
    record_id = db.save_record(record)

    started = svc.start_phase_for_record(
        record_id=record_id,
        phase=CommissioningPhase.PIEZO_PRE_RF,
        operator="tester",
    )
    svc.complete_phase_instance(
        record_id=record_id,
        phase_instance_id=started.phase_instance_id,
        phase=CommissioningPhase.PIEZO_PRE_RF,
        artifact_payload={"result": "ok"},
    )

    stats = db.get_database_stats()
    assert stats["total_records"] == 1
    assert stats["by_status"].get("in_progress", 0) == 1
    assert stats["by_phase"].get(CommissioningPhase.SSA_CHAR.value, 0) == 1


def test_initialize_is_idempotent_for_fresh_schema(tmp_path):
    db = CommissioningDatabase(str(tmp_path / "commissioning.db"))
    db.initialize()
    db.initialize()

    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(commissioning_records)")
        cols = {row["name"] for row in cursor.fetchall()}

    assert {
        "version",
        "general_notes",
        "linac",
        "cryomodule",
        "cavity_number",
    }.issubset(cols)
    assert {
        "current_phase",
        "overall_status",
        "phase_status",
        "phase_history",
    }.isdisjoint(cols)


def test_measurement_notes_expect_list_json(tmp_path):
    db = CommissioningDatabase(str(tmp_path / "commissioning.db"))
    db.initialize()

    record = _new_record()
    record_id = db.save_record(record)
    entry_id = db.add_measurement_history(
        record_id,
        CommissioningPhase.PIEZO_PRE_RF,
        {"ok": True},
    )

    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE measurement_history SET notes = ? WHERE id = ?",
            ('"legacy-string"', entry_id),
        )

    # Non-list payloads are ignored; appending writes canonical list JSON.
    assert db.append_measurement_note(entry_id, "tester", "new-note") is True
    history = db.get_measurement_history(
        record_id, CommissioningPhase.PIEZO_PRE_RF
    )
    assert len(history[0]["notes"]) == 1
    assert history[0]["notes"][0]["operator"] == "tester"
    assert history[0]["notes"][0]["note"] == "new-note"


def test_delete_record_is_disabled_and_keeps_normalized_rows(tmp_path):
    db = CommissioningDatabase(str(tmp_path / "commissioning.db"))
    db.initialize()
    svc = WorkflowService(db)

    record_id = db.save_record(_new_record())
    started = svc.start_phase_for_record(
        record_id=record_id,
        phase=CommissioningPhase.PIEZO_PRE_RF,
        operator="tester",
    )
    phase_instance_id = started.phase_instance_id
    db.add_measurement_history(
        record_id,
        CommissioningPhase.PIEZO_PRE_RF,
        {"value": 1},
        phase_instance_id=phase_instance_id,
    )

    with pytest.raises(RecordDeletionDisabledError):
        db.delete_record(record_id)

    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM commissioning_records")
        assert cursor.fetchone()[0] == 1
        cursor.execute("SELECT COUNT(*) FROM commissioning_runs")
        assert cursor.fetchone()[0] == 1
        cursor.execute("SELECT COUNT(*) FROM commissioning_phase_instances")
        assert cursor.fetchone()[0] == 1
        cursor.execute("SELECT COUNT(*) FROM measurement_history")
        assert cursor.fetchone()[0] == 1


def test_save_record_keeps_workflow_state_derived_from_runs(tmp_path):
    db = CommissioningDatabase(str(tmp_path / "commissioning.db"))
    db.initialize()
    svc = WorkflowService(db)

    record = _new_record()
    record_id = db.save_record(record)

    started = svc.start_phase_for_record(
        record_id=record_id,
        phase=CommissioningPhase.PIEZO_PRE_RF,
        operator="tester",
    )
    svc.complete_phase_instance(
        record_id=record_id,
        phase_instance_id=started.phase_instance_id,
        phase=CommissioningPhase.PIEZO_PRE_RF,
        artifact_payload={"ok": True},
    )

    loaded = db.get_record_with_version(record_id)
    assert loaded is not None
    stale_record, version = loaded
    stale_record.current_phase = CommissioningPhase.COMPLETE
    stale_record.overall_status = "failed"
    assert (
        db.save_record(stale_record, record_id, expected_version=version)
        == record_id
    )

    reloaded = db.get_record(record_id)
    assert reloaded is not None
    assert reloaded.current_phase == CommissioningPhase.SSA_CHAR
    assert reloaded.overall_status == "in_progress"
