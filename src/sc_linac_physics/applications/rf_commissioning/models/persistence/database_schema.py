"""Schema helpers for RF commissioning SQLite databases."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable


def _phase_column_definitions(column_names: Iterable[str]) -> str:
    return "\n".join(f"                    {col} TEXT," for col in column_names)


def _add_missing_phase_columns(
    cursor: sqlite3.Cursor, table_name: str, column_names: Iterable[str]
) -> None:
    """Add a TEXT column for each registry phase the table doesn't have.

    ``CREATE TABLE IF NOT EXISTS`` leaves an existing table alone. A phase
    added to the registry after a database file was made would otherwise
    have no column there, and every INSERT/UPDATE naming it would fail.
    New columns start NULL, which ``deserialize_phase_data`` reads as None.
    """
    cursor.execute(f"PRAGMA table_info({table_name})")
    existing = {row[1] for row in cursor.fetchall()}
    for col in column_names:
        if col not in existing:
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {col} TEXT")


def initialize_database_schema(
    cursor: sqlite3.Cursor,
    *,
    phase_column_names: Iterable[str],
    cryomodule_phase_column_names: Iterable[str],
) -> None:
    """Create the RF commissioning schema, or bring an older file up to it.

    Tables and indexes are created if missing. Phase columns the registry
    has gained since the file was made are added.
    """
    phase_column_names = list(phase_column_names)
    cryomodule_phase_column_names = list(cryomodule_phase_column_names)
    phase_col_defs = _phase_column_definitions(phase_column_names)
    cm_phase_col_defs = _phase_column_definitions(cryomodule_phase_column_names)

    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS commissioning_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            linac TEXT NOT NULL,
            linac_number TEXT,
            cryomodule TEXT NOT NULL,
            cavity_number TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT,

            -- Phase-specific data (stored as JSON)
{phase_col_defs}

            -- Metadata
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            general_notes TEXT NOT NULL DEFAULT '[]'
        )
        """)
    _add_missing_phase_columns(
        cursor, "commissioning_records", phase_column_names
    )

    cursor.execute("DROP INDEX IF EXISTS idx_active_record_per_cavity")

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_linac
        ON commissioning_records(linac)
        """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_cavity_number
        ON commissioning_records(cavity_number)
        """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_cryomodule
        ON commissioning_records(cryomodule)
        """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_linac_cryo_cavity
        ON commissioning_records(linac, cryomodule, cavity_number)
        """)
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_cavity
        ON commissioning_records(linac, cryomodule, cavity_number)
        """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS measurement_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_id INTEGER NOT NULL,
            phase_instance_id INTEGER,
            phase TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            operator TEXT,
            measurement_data TEXT NOT NULL,
            notes TEXT,
            created_at TEXT NOT NULL,

            FOREIGN KEY (record_id)
                REFERENCES commissioning_records(id)
                ON DELETE CASCADE,
            FOREIGN KEY (phase_instance_id)
                REFERENCES commissioning_phase_instances(id)
                ON DELETE SET NULL
        )
        """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_measurement_history_record
        ON measurement_history(record_id, phase)
        """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_measurement_history_phase_instance
        ON measurement_history(phase_instance_id)
        """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS commissioning_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_id INTEGER NOT NULL UNIQUE,
            workflow_name TEXT NOT NULL,
            linac TEXT NOT NULL,
            cryomodule TEXT NOT NULL,
            cavity_number TEXT NOT NULL,
            operator TEXT,
            status TEXT NOT NULL,
            current_phase TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,

            FOREIGN KEY (record_id)
                REFERENCES commissioning_records(id)
                ON DELETE CASCADE
        )
        """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_runs_cavity
        ON commissioning_runs(linac, cryomodule, cavity_number)
        """)
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_active_run_per_cavity
        ON commissioning_runs(linac, cryomodule, cavity_number)
        WHERE status = 'in_progress'
        """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS commissioning_phase_instances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            phase TEXT NOT NULL,
            attempt_number INTEGER NOT NULL,
            status TEXT NOT NULL,
            operator TEXT,
            started_at TEXT NOT NULL,
            ended_at TEXT,
            error_message TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,

            FOREIGN KEY (run_id)
                REFERENCES commissioning_runs(id)
                ON DELETE CASCADE,
            UNIQUE(run_id, phase, attempt_number)
        )
        """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_phase_instances_run_phase
        ON commissioning_phase_instances(run_id, phase)
        """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS commissioning_phase_artifacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phase_instance_id INTEGER NOT NULL,
            artifact_type TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL,

            FOREIGN KEY (phase_instance_id)
                REFERENCES commissioning_phase_instances(id)
                ON DELETE CASCADE
        )
        """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_phase_artifacts_instance
        ON commissioning_phase_artifacts(phase_instance_id)
        """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS commissioning_workflow_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            phase_instance_id INTEGER,
            event_type TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL,

            FOREIGN KEY (run_id)
                REFERENCES commissioning_runs(id)
                ON DELETE CASCADE,
            FOREIGN KEY (phase_instance_id)
                REFERENCES commissioning_phase_instances(id)
                ON DELETE SET NULL
        )
        """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_workflow_events_run
        ON commissioning_workflow_events(run_id, created_at)
        """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS operators (
            name TEXT PRIMARY KEY,
            created_at TEXT NOT NULL
        )
        """)
    _seed_operators(cursor)

    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS cryomodule_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            linac TEXT NOT NULL,
            cryomodule TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT,

            -- CM-level phase data (stored as JSON)
{cm_phase_col_defs}

            -- Phase tracking (stored as JSON)
            phase_status TEXT NOT NULL,

            -- Metadata
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            notes TEXT NOT NULL DEFAULT ''
        )
        """)
    _add_missing_phase_columns(
        cursor, "cryomodule_records", cryomodule_phase_column_names
    )
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_cm_linac_cryo
        ON cryomodule_records(linac, cryomodule)
        """)
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_cm_unique
        ON cryomodule_records(linac, cryomodule)
        """)


_DEFAULT_OPERATORS = [
    "Lauren Alsberg",
    "Lisa Zacarias",
    "Nicole Neveu",
    "Ryan Porter",
    "Sebastian Aderhold",
    "Haley Marts",
]


def _seed_operators(cursor: sqlite3.Cursor) -> None:
    for name in _DEFAULT_OPERATORS:
        cursor.execute(
            "INSERT OR IGNORE INTO operators (name, created_at) VALUES (?, datetime('now'))",
            (name,),
        )
