"""Tests for RF commissioning schema initialization helpers."""

from __future__ import annotations

import sqlite3
from contextlib import closing

from sc_linac_physics.applications.rf_commissioning.models.persistence.database import (
    CommissioningDatabase,
)
from sc_linac_physics.applications.rf_commissioning.models.persistence.database_schema import (
    initialize_database_schema,
)


def test_initialize_database_schema_creates_expected_tables_and_columns():
    with closing(sqlite3.connect(":memory:")) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        initialize_database_schema(
            cursor,
            phase_column_names=["phase_alpha", "phase_beta"],
            cryomodule_phase_column_names=["cm_phase_alpha"],
        )

        cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        tables = {row["name"] for row in cursor.fetchall()}
        assert {
            "commissioning_records",
            "measurement_history",
            "commissioning_runs",
            "commissioning_phase_instances",
            "commissioning_phase_artifacts",
            "commissioning_workflow_events",
            "operators",
            "cryomodule_records",
        }.issubset(tables)

        cursor.execute("PRAGMA table_info(commissioning_records)")
        record_columns = {row["name"] for row in cursor.fetchall()}
        assert {
            "phase_alpha",
            "phase_beta",
            "version",
            "general_notes",
        }.issubset(record_columns)

        cursor.execute("PRAGMA table_info(cryomodule_records)")
        cm_columns = {row["name"] for row in cursor.fetchall()}
        assert {
            "cm_phase_alpha",
            "phase_status",
            "notes",
            "version",
        }.issubset(cm_columns)


def test_initialize_database_schema_creates_expected_indexes():
    with closing(sqlite3.connect(":memory:")) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        initialize_database_schema(
            cursor,
            phase_column_names=["phase_alpha", "phase_beta"],
            cryomodule_phase_column_names=["cm_phase_alpha"],
        )

        cursor.execute("PRAGMA index_list('commissioning_records')")
        commissioning_indexes = {row["name"]: row for row in cursor.fetchall()}
        assert "idx_unique_cavity" in commissioning_indexes
        assert commissioning_indexes["idx_unique_cavity"]["unique"] == 1
        assert "idx_active_record_per_cavity" not in commissioning_indexes

        cursor.execute("PRAGMA index_list('commissioning_runs')")
        run_indexes = {row["name"]: row for row in cursor.fetchall()}
        assert "idx_active_run_per_cavity" in run_indexes
        assert run_indexes["idx_active_run_per_cavity"]["unique"] == 1
        assert run_indexes["idx_active_run_per_cavity"]["partial"] == 1


def test_initialize_database_schema_is_idempotent_on_same_connection():
    with closing(sqlite3.connect(":memory:")) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        initialize_database_schema(
            cursor,
            phase_column_names=["phase_alpha"],
            cryomodule_phase_column_names=["cm_phase_alpha"],
        )
        initialize_database_schema(
            cursor,
            phase_column_names=["phase_alpha"],
            cryomodule_phase_column_names=["cm_phase_alpha"],
        )

        cursor.execute(
            "SELECT COUNT(*) AS count FROM sqlite_master WHERE type = 'table' AND name = 'commissioning_runs'"
        )
        assert cursor.fetchone()["count"] == 1


def test_initialize_database_schema_sets_expected_on_delete_actions():
    with closing(sqlite3.connect(":memory:")) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        initialize_database_schema(
            cursor,
            phase_column_names=["phase_alpha"],
            cryomodule_phase_column_names=["cm_phase_alpha"],
        )

        cursor.execute("PRAGMA foreign_key_list('measurement_history')")
        measurement_fks = {
            row["from"]: row["on_delete"] for row in cursor.fetchall()
        }
        assert measurement_fks["record_id"] == "CASCADE"
        assert measurement_fks["phase_instance_id"] == "SET NULL"

        cursor.execute("PRAGMA foreign_key_list('commissioning_runs')")
        run_fks = {row["from"]: row["on_delete"] for row in cursor.fetchall()}
        assert run_fks["record_id"] == "CASCADE"

        cursor.execute(
            "PRAGMA foreign_key_list('commissioning_phase_instances')"
        )
        instance_fks = {
            row["from"]: row["on_delete"] for row in cursor.fetchall()
        }
        assert instance_fks["run_id"] == "CASCADE"

        cursor.execute(
            "PRAGMA foreign_key_list('commissioning_phase_artifacts')"
        )
        artifact_fks = {
            row["from"]: row["on_delete"] for row in cursor.fetchall()
        }
        assert artifact_fks["phase_instance_id"] == "CASCADE"

        cursor.execute(
            "PRAGMA foreign_key_list('commissioning_workflow_events')"
        )
        workflow_event_fks = {
            row["from"]: row["on_delete"] for row in cursor.fetchall()
        }
        assert workflow_event_fks["run_id"] == "CASCADE"
        assert workflow_event_fks["phase_instance_id"] == "SET NULL"


def _columns(cursor, table):
    cursor.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cursor.fetchall()}


def test_an_older_file_gains_registry_phase_columns_and_keeps_its_rows(
    tmp_path,
):
    """A phase added to the registry must work on a file made before it."""
    path = tmp_path / "commissioning.db"
    phases = list(CommissioningDatabase.PHASE_DATA_MODELS)
    cm_phases = list(CommissioningDatabase.CRYOMODULE_PHASE_DATA_MODELS)
    newest, cm_newest = phases[-1], cm_phases[-1]

    old = sqlite3.connect(path)
    initialize_database_schema(
        old.cursor(),
        phase_column_names=phases[:-1],
        cryomodule_phase_column_names=cm_phases[:-1],
    )
    old.execute(
        "INSERT INTO commissioning_records (linac, cryomodule, cavity_number,"
        " start_time, created_at, updated_at) VALUES ('1', '02', '1', "
        "'2026-01-01T00:00:00', 'now', 'now')"
    )
    old.commit()
    assert newest not in _columns(old.cursor(), "commissioning_records")
    old.close()

    db = CommissioningDatabase(str(path))
    db.initialize()
    db.initialize()  # running it again adds nothing and doesn't fail

    with db.connection() as conn:
        cursor = conn.cursor()
        assert newest in _columns(cursor, "commissioning_records")
        assert cm_newest in _columns(cursor, "cryomodule_records")

    record, version = db.get_record_with_version(1)
    assert getattr(record, newest) is None
    db.save_record(record, record_id=1, expected_version=version)
    assert db.get_record(1).cryomodule == "02"
