"""Tests for RF commissioning schema initialization helpers."""

from __future__ import annotations

import sqlite3
from contextlib import closing

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
