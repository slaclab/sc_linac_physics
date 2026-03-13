"""SQLite database interface for RF commissioning records."""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningPhase,
    CommissioningRecord,
    PhaseCheckpoint,
    PhaseStatus,
    PHASE_REGISTRY,
    deserialize_model,
)

logger = logging.getLogger(__name__)


class RecordConflictError(Exception):
    """Raised when optimistic locking detects a conflict.

    This occurs when another user/process has modified the record
    since it was last loaded.
    """

    def __init__(
        self, record_id: int, expected_version: int, actual_version: int
    ):
        self.record_id = record_id
        self.expected_version = expected_version
        self.actual_version = actual_version
        super().__init__(
            f"Record {record_id} was modified by another user. "
            f"Expected version {expected_version}, found {actual_version}."
        )


class CommissioningDatabase:
    """SQLite database manager for commissioning records.

    Provides local persistence for all commissioning data with support for:
    - Creating and updating commissioning records
    - Querying by cavity, cryomodule, or status
    - Resume capability for interrupted sessions
    - Historical record tracking

    Schema:
        commissioning_records: Main table with all commissioning data
        - Uses JSON columns for complex nested data
        - Indexes on cavity_name, cryomodule, and status for fast queries

    Example:
        >>> db = CommissioningDatabase("commissioning.db")
        >>> db.initialize()
    """

    def __init__(self, db_path: str = "commissioning.db"):
        """Initialize database connection.

        Args:
            db_path: Path to SQLite database file. Created if doesn't exist.
        """
        self.db_path = Path(db_path)

    # Maps record attribute name → data model class for all phases that
    # store data.  Derived automatically from PHASE_REGISTRY so adding a
    # new phase here requires only an entry in the registry.
    PHASE_DATA_MODELS: dict[str, type] = {
        reg.record_attr: reg.data_model
        for reg in PHASE_REGISTRY.values()
        if reg.record_attr and reg.data_model
    }

    @contextmanager
    def _get_connection(self):
        """Context manager for database connections.

        Ensures connections are properly closed and provides transaction support.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self):
        """Create database schema if it doesn't exist.

        Creates the commissioning_records table with all necessary columns
        and indexes for efficient querying.

        Phase-specific data columns are generated dynamically from
        ``PHASE_DATA_MODELS`` (which itself is derived from ``PHASE_REGISTRY``),
        so adding a new phase to the registry automatically provisions its
        column when a fresh database is created or migrated.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Build phase-data column declarations dynamically so that new
            # phases registered in PHASE_REGISTRY are included without any
            # manual SQL changes here.
            phase_col_defs = "\n".join(
                f"                    {col} TEXT,"
                for col in self.PHASE_DATA_MODELS
            )

            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS commissioning_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    linac TEXT NOT NULL,
                    linac_number TEXT,
                    cryomodule TEXT NOT NULL,
                    cavity_number TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    current_phase TEXT NOT NULL,
                    overall_status TEXT NOT NULL,

                    -- Phase-specific data (stored as JSON)
{phase_col_defs}

                    -- Phase tracking (stored as JSON)
                    phase_status TEXT NOT NULL,
                    phase_history TEXT NOT NULL,

                    -- Metadata
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    general_notes TEXT NOT NULL DEFAULT '[]'
                )
            """)

            # ----------------------------------------------------------------
            # Migrations: ensure every column exists on databases created
            # before a column (or phase) was added.
            # ----------------------------------------------------------------
            cursor.execute("PRAGMA table_info(commissioning_records)")
            existing_columns = {row[1] for row in cursor.fetchall()}

            # Legacy scalar columns
            for col_name, ddl in [
                ("version", "INTEGER NOT NULL DEFAULT 1"),
                ("general_notes", "TEXT NOT NULL DEFAULT '[]'"),
            ]:
                if col_name not in existing_columns:
                    cursor.execute(
                        f"ALTER TABLE commissioning_records "
                        f"ADD COLUMN {col_name} {ddl}"
                    )

            # Phase data columns – one migration per registered phase that is
            # missing from the schema (handles databases predating a new phase).
            for col_name in self.PHASE_DATA_MODELS:
                if col_name not in existing_columns:
                    cursor.execute(
                        f"ALTER TABLE commissioning_records "
                        f"ADD COLUMN {col_name} TEXT"
                    )

            # Create indexes for common queries
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
                CREATE INDEX IF NOT EXISTS idx_overall_status
                ON commissioning_records(overall_status)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_current_phase
                ON commissioning_records(current_phase)
            """)

            # Create measurement history table for tracking all measurement attempts
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS measurement_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    record_id INTEGER NOT NULL,
                    phase TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    operator TEXT,
                    measurement_data TEXT NOT NULL,
                    notes TEXT,
                    created_at TEXT NOT NULL,

                    FOREIGN KEY (record_id) REFERENCES commissioning_records(id)
                )
            """)

            # Create index for efficient history queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_measurement_history_record
                ON measurement_history(record_id, phase)
            """)

            try:
                cursor.execute("""
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_cavity
                    ON commissioning_records(linac, cryomodule, cavity_number)
                """)
            except sqlite3.IntegrityError as exc:
                logger.warning("Could not create unique cavity index: %s", exc)

            # Create operators table for approved operator list
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS operators (
                    name TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL
                )
            """)

    def _extract_linac_number(self, linac: str | None) -> str | None:
        """Extract numeric linac identifier from a linac string."""
        import re

        if not linac:
            return None

        digits = re.findall(r"\d+", linac)
        if not digits:
            return None

        return "".join(digits)

    def save_record(
        self,
        record: "CommissioningRecord",
        record_id: int | None = None,
        expected_version: int | None = None,
    ) -> int:
        """Save or update a commissioning record with optimistic locking.

        Args:
            record: CommissioningRecord to save
            record_id: If provided, updates existing record. Otherwise creates new.
            expected_version: For updates, the version expected. Raises RecordConflictError if mismatch.

        Returns:
            Database ID of the saved record

        Raises:
            RecordConflictError: If expected_version doesn't match current version (concurrent modification)

        Example:
            >>> record, version = db.load_record_with_version(record_id)
            >>> record.current_phase = CommissioningPhase.SSA_CAL
            >>> db.save_record(record, record_id, expected_version=version)  # Safe update
        """
        now = datetime.now().isoformat()

        # Convert complex objects to JSON
        phase_status_json = json.dumps(
            {
                phase.value: status.value
                for phase, status in record.phase_status.items()
            }
        )

        # UPDATED: phase_history is now a list, not a dict
        phase_history_json = json.dumps(
            [
                checkpoint.to_dict() for checkpoint in record.phase_history
            ]  # CHANGED THIS LINE
        )
        phase_data_json = {
            attr_name: self._serialize_phase_data(getattr(record, attr_name))
            for attr_name in self.PHASE_DATA_MODELS
        }

        with self._get_connection() as conn:
            cursor = conn.cursor()

            linac_number = self._extract_linac_number(record.linac)

            # Build phase-data portions of the query dynamically so that new
            # phases registered in PHASE_DATA_MODELS require no SQL changes here.
            phase_col_names = list(self.PHASE_DATA_MODELS.keys())
            phase_values = [phase_data_json[col] for col in phase_col_names]

            if record_id is None:
                # Insert new record
                phase_col_list = ", ".join(phase_col_names)
                phase_placeholders = ", ".join("?" * len(phase_col_names))
                cursor.execute(
                    f"""
                    INSERT INTO commissioning_records (
                        linac, linac_number, cryomodule, cavity_number, start_time, end_time,
                        current_phase, overall_status,
                        {phase_col_list},
                        phase_status, phase_history,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, {phase_placeholders}, ?, ?, ?, ?)
                """,
                    (
                        record.linac,
                        linac_number,
                        record.cryomodule,
                        record.cavity_number,
                        record.start_time.isoformat(),
                        (
                            record.end_time.isoformat()
                            if record.end_time
                            else None
                        ),
                        record.current_phase.value,
                        record.overall_status,
                        *phase_values,
                        phase_status_json,
                        phase_history_json,
                        now,
                        now,
                    ),
                )
                return cursor.lastrowid
            else:
                # Update existing record with optimistic locking
                if expected_version is not None:
                    # Check current version
                    cursor.execute(
                        "SELECT version FROM commissioning_records WHERE id = ?",
                        (record_id,),
                    )
                    row = cursor.fetchone()
                    if row is None:
                        raise ValueError(f"Record {record_id} not found")

                    current_version = row[0]
                    if current_version != expected_version:
                        raise RecordConflictError(
                            record_id, expected_version, current_version
                        )

                phase_set_clauses = ", ".join(
                    f"{col} = ?" for col in phase_col_names
                )
                cursor.execute(
                    f"""
                    UPDATE commissioning_records SET
                        linac = ?, linac_number = ?, cryomodule = ?, cavity_number = ?, start_time = ?, end_time = ?,
                        current_phase = ?, overall_status = ?,
                        {phase_set_clauses},
                        phase_status = ?, phase_history = ?,
                        updated_at = ?,
                        version = version + 1
                    WHERE id = ?
                """,
                    (
                        record.linac,
                        linac_number,
                        record.cryomodule,
                        record.cavity_number,
                        record.start_time.isoformat(),
                        (
                            record.end_time.isoformat()
                            if record.end_time
                            else None
                        ),
                        record.current_phase.value,
                        record.overall_status,
                        *phase_values,
                        phase_status_json,
                        phase_history_json,
                        now,
                        record_id,
                    ),
                )
                return record_id

    def get_record(self, record_id: int) -> "CommissioningRecord" | None:
        """Retrieve a record by database ID.

        Args:
            record_id: Database ID of the record

        Returns:
            CommissioningRecord if found, None otherwise
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM commissioning_records WHERE id = ?", (record_id,)
            )
            row = cursor.fetchone()

            if row is None:
                return None

            return self._row_to_record(row)

    def get_record_with_version(
        self, record_id: int
    ) -> tuple["CommissioningRecord", int] | None:
        """Retrieve a record with its version number for optimistic locking.

        Args:
            record_id: Database ID of the record

        Returns:
            Tuple of (CommissioningRecord, version) if found, None otherwise
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM commissioning_records WHERE id = ?", (record_id,)
            )
            row = cursor.fetchone()

            if row is None:
                return None

            version = row["version"] if "version" in row.keys() else 1
            return self._row_to_record(row), version

    def load_record_with_version(
        self, record_id: int
    ) -> tuple["CommissioningRecord", int] | None:
        """Alias for get_record_with_version."""
        return self.get_record_with_version(record_id)

    def _row_to_record(self, row: sqlite3.Row) -> "CommissioningRecord":
        """Convert database row to CommissioningRecord.

        Handles deserialization of JSON fields and enum conversion.
        """
        # Deserialize phase_status
        phase_status_dict = json.loads(row["phase_status"])
        phase_status = {
            CommissioningPhase(phase): PhaseStatus(status)
            for phase, status in phase_status_dict.items()
        }

        # UPDATED: Deserialize phase_history as list
        phase_history_list = json.loads(row["phase_history"])
        phase_history = [
            deserialize_model(PhaseCheckpoint, cp_dict)
            for cp_dict in phase_history_list
        ]

        # Build phase data kwargs dynamically so that new phases require no
        # changes here.  Note: CommissioningRecord must still declare a typed
        # field whose name matches the registry's record_attr.
        phase_data = {
            attr_name: self._deserialize_phase_data(row[attr_name], model_cls)
            for attr_name, model_cls in self.PHASE_DATA_MODELS.items()
        }

        # Create record
        record = CommissioningRecord(
            linac=row["linac"],
            cryomodule=row["cryomodule"],
            cavity_number=row["cavity_number"],
            start_time=datetime.fromisoformat(row["start_time"]),
            current_phase=CommissioningPhase(row["current_phase"]),
            **phase_data,
            phase_history=phase_history,
            phase_status=phase_status,
            end_time=(
                datetime.fromisoformat(row["end_time"])
                if row["end_time"]
                else None
            ),
            overall_status=row["overall_status"],
        )
        return record

    @staticmethod
    def _serialize_phase_data(phase_data) -> str | None:
        """Serialize a phase dataclass to JSON for storage."""
        if phase_data is None:
            return None
        return json.dumps(phase_data.to_dict())

    @staticmethod
    def _deserialize_phase_data(payload: str | None, model_cls):
        """Deserialize a stored phase payload into its dataclass."""
        if not payload:
            return None
        return deserialize_model(model_cls, json.loads(payload))

    def get_record_by_cavity(
        self,
        linac: str,
        cryomodule: str,
        cavity_number: str,
        active_only: bool = True,
    ) -> "CommissioningRecord" | None:
        """Get most recent record for a cavity.

        Args:
            linac: Linac name (e.g., "L1B")
            cryomodule: Cryomodule identifier (e.g., "02")
            cavity_number: Cavity number (e.g., "1")
            active_only: If True, only return if status is "in_progress"

        Returns:
            Most recent CommissioningRecord for cavity, or None

        Example:
            >>> # Get active session for cavity
            >>> record = db.get_record_by_cavity("L1B", "02", "3")
            >>>
            >>> # Get most recent session (completed or active)
            >>> record = db.get_record_by_cavity("L1B", "02", "3", active_only=False)
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            query = """
                SELECT * FROM commissioning_records
                WHERE linac = ? AND cryomodule = ? AND cavity_number = ?
            """
            params = [linac, cryomodule, cavity_number]

            if active_only:
                query += " AND overall_status = ?"
                params.append("in_progress")

            query += " ORDER BY start_time DESC LIMIT 1"

            cursor.execute(query, params)
            row = cursor.fetchone()

            if row is None:
                return None

            return self._row_to_record(row)

    def get_records_by_cryomodule(
        self, cryomodule: str, active_only: bool = False
    ) -> list["CommissioningRecord"]:
        """Get all records for a cryomodule.

        Args:
            cryomodule: Cryomodule number (e.g., "02")
            active_only: If True, only return records with status "in_progress"

        Returns:
            List of CommissioningRecords, sorted by start time (newest first)

        Example:
            >>> # Get all records for CM02
            >>> records = db.get_records_by_cryomodule("02")
            >>>
            >>> # Get only active sessions
            >>> active = db.get_records_by_cryomodule("02", active_only=True)
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            query = """
                SELECT * FROM commissioning_records
                WHERE cryomodule = ?
            """
            params = [cryomodule]

            if active_only:
                query += " AND overall_status = ?"
                params.append("in_progress")

            query += " ORDER BY start_time DESC"

            cursor.execute(query, params)
            rows = cursor.fetchall()

            return [self._row_to_record(row) for row in rows]

    def load_record(self, record_id: int) -> "CommissioningRecord" | None:
        """Alias for get_record for compatibility."""
        return self.get_record(record_id)

    def find_records_for_cavity(
        self, linac: str, cryomodule: str, cavity_number: str
    ) -> list[dict]:
        """Find all commissioning records for a specific cavity.

        Args:
            linac: Linac name (e.g., "L1B")
            cryomodule: Cryomodule identifier (e.g., "02")
            cavity_number: Cavity number (e.g., "1")

        Returns:
            List of record dictionaries for this cavity
        """
        return self._get_record_summaries(
            where_clause="linac = ? AND cryomodule = ? AND cavity_number = ?",
            params=[linac, cryomodule, cavity_number],
        )

    def get_record_id_for_cavity(
        self, linac: str, cryomodule: str, cavity_number: str
    ) -> int | None:
        """Get the canonical record ID for a cavity, if it exists."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id FROM commissioning_records
                WHERE linac = ? AND cryomodule = ? AND cavity_number = ?
                ORDER BY COALESCE(updated_at, start_time) DESC, id DESC
                LIMIT 1
                """,
                (linac, cryomodule, cavity_number),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return row["id"]

    def _get_record_summaries(
        self, where_clause: str = "", params: list | None = None
    ) -> list[dict]:
        """Return lightweight record summaries for browsing."""
        import json

        params = params or []
        query = """
            SELECT id, linac, linac_number, cryomodule, cavity_number,
                   start_time, end_time, current_phase, overall_status,
                   updated_at, piezo_pre_rf
            FROM commissioning_records
        """
        if where_clause:
            query += " WHERE " + where_clause
        query += " ORDER BY start_time DESC"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()

        records: list[dict] = []
        for row in rows:
            record = {
                "id": row["id"],
                "linac": row["linac"] or "?",
                "linac_number": row["linac_number"],
                "cryomodule": row["cryomodule"] or "?",
                "cavity_number": row["cavity_number"] or "?",
                "start_time": row["start_time"],
                "end_time": row["end_time"],
                "current_phase": row["current_phase"],
                "overall_status": row["overall_status"],
                "updated_at": row["updated_at"],
            }

            if row["piezo_pre_rf"]:
                try:
                    data = json.loads(row["piezo_pre_rf"])
                    record["piezo_pre_rf"] = {
                        "channel_a_passed": data.get("channel_a_passed"),
                        "channel_b_passed": data.get("channel_b_passed"),
                        "capacitance_a": data.get("capacitance_a"),
                        "capacitance_b": data.get("capacitance_b"),
                    }
                except json.JSONDecodeError:
                    pass

            records.append(record)

        return records

    def get_all_records(self) -> list[dict]:
        """
        Get all commissioning records as dictionaries.

        Returns:
            List of record dictionaries with basic info for browsing
        """
        try:
            return self._get_record_summaries()

        except Exception as e:
            logger.exception("Error getting all records: %s", e)
            return []

    def get_active_records(self) -> list["CommissioningRecord"]:
        """Get all in-progress commissioning records.

        Returns:
            List of CommissioningRecords with status "in_progress",
            sorted by start time (newest first)

        Example:
            >>> # Resume all interrupted sessions
            >>> active_sessions = db.get_active_records()
            >>> for session in active_sessions:
            ...     print(f"Resume: {session.cavity_name} at {session.current_phase.value}")
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM commissioning_records
                WHERE overall_status = ?
                ORDER BY start_time DESC
            """,
                ("in_progress",),
            )
            rows = cursor.fetchall()

            return [self._row_to_record(row) for row in rows]

    def delete_record(self, record_id: int) -> bool:
        """Delete a commissioning record.

        Args:
            record_id: Database ID of record to delete

        Returns:
            True if record was deleted, False if not found

        Example:
            >>> if db.delete_record(record_id):
            ...     print("Record deleted")
            ... else:
            ...     print("Record not found")
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM commissioning_records WHERE id = ?", (record_id,)
            )
            return cursor.rowcount > 0

    def get_database_stats(self) -> dict:
        """Get statistics about the database.

        Returns:
            Dictionary with counts of records by status, phase, and cryomodule

        Example:
            >>> stats = db.get_database_stats()
            >>> print(f"Total records: {stats['total_records']}")
            >>> print(f"Active: {stats['by_status'].get('in_progress', 0)}")
            >>> print(f"CM02 cavities: {stats['by_cryomodule'].get('02', 0)}")
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Total records
            cursor.execute("SELECT COUNT(*) FROM commissioning_records")
            total = cursor.fetchone()[0]

            # By status
            cursor.execute("""
                SELECT overall_status, COUNT(*)
                FROM commissioning_records
                GROUP BY overall_status
            """)
            by_status = dict(cursor.fetchall())

            # By current phase
            cursor.execute("""
                SELECT current_phase, COUNT(*)
                FROM commissioning_records
                GROUP BY current_phase
            """)
            by_phase = dict(cursor.fetchall())

            # By cryomodule
            cursor.execute("""
                SELECT cryomodule, COUNT(*)
                FROM commissioning_records
                GROUP BY cryomodule
            """)
            by_cryomodule = dict(cursor.fetchall())

            return {
                "total_records": total,
                "by_status": by_status,
                "by_phase": by_phase,
                "by_cryomodule": by_cryomodule,
            }

    def add_measurement_history(
        self,
        record_id: int,
        phase: "CommissioningPhase",
        measurement_data,
        operator: str | None = None,
        notes: str | None = None,
    ) -> int:
        """Add a measurement attempt to history (append-only, no conflicts).

        This allows multiple users to take measurements concurrently without
        version conflicts. Each measurement is recorded separately.

        Args:
            record_id: ID of the commissioning record
            phase: Which phase this measurement is for
            measurement_data: The phase-specific data object (PiezoPreRFCheck, etc.)
            operator: Who took the measurement
            notes: Optional notes about this measurement

        Returns:
            History entry ID

        Example:
            >>> # User A takes a measurement
            >>> piezo_data = PiezoPreRFCheck(...)
            >>> db.add_measurement_history(record_id, CommissioningPhase.PIEZO_PRE_RF, piezo_data)
            >>>
            >>> # User B can also take a measurement - both get recorded!
            >>> piezo_data2 = PiezoPreRFCheck(...)
            >>> db.add_measurement_history(record_id, CommissioningPhase.PIEZO_PRE_RF, piezo_data2)
        """
        import json
        from datetime import datetime

        now = datetime.now().isoformat()

        # Serialize measurement data
        if hasattr(measurement_data, "to_dict"):
            data_json = json.dumps(measurement_data.to_dict())
        else:
            data_json = json.dumps(measurement_data)

        notes_payload = []
        if notes:
            notes_payload.append(
                {"timestamp": now, "operator": operator, "note": notes}
            )

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO measurement_history (
                    record_id, phase, timestamp, operator, measurement_data, notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    phase.value,
                    now,
                    operator,
                    data_json,
                    json.dumps(notes_payload),
                    now,
                ),
            )
            return cursor.lastrowid

    def get_operators(self) -> list[str]:
        """Return the list of approved operators."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM operators ORDER BY name")
            rows = cursor.fetchall()
            return [row[0] for row in rows]

    def add_operator(self, name: str) -> bool:
        """Add a new operator to the approved list."""
        from datetime import datetime

        clean_name = name.strip()
        if not clean_name:
            return False

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO operators (name, created_at) VALUES (?, ?)",
                (clean_name, datetime.now().isoformat()),
            )
            return cursor.rowcount > 0

    def get_measurement_history(
        self,
        record_id: int,
        phase: "CommissioningPhase" | None = None,
    ) -> list[dict]:
        """Get all measurement attempts for a record.

        Args:
            record_id: ID of the commissioning record
            phase: Optional - filter to specific phase only

        Returns:
            List of measurement history entries with metadata

        Example:
            >>> # Get all measurements
            >>> history = db.get_measurement_history(record_id)
            >>>
            >>> # Get just piezo pre-RF attempts
            >>> piezo_history = db.get_measurement_history(
            ...     record_id, CommissioningPhase.PIEZO_PRE_RF
            ... )
            >>> print(f"Took {len(piezo_history)} piezo measurements")
        """
        import json

        with self._get_connection() as conn:
            cursor = conn.cursor()

            if phase:
                cursor.execute(
                    """
                    SELECT * FROM measurement_history
                    WHERE record_id = ? AND phase = ?
                    ORDER BY timestamp DESC
                    """,
                    (record_id, phase.value),
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM measurement_history
                    WHERE record_id = ?
                    ORDER BY timestamp DESC
                    """,
                    (record_id,),
                )

            rows = cursor.fetchall()

            history = []
            for row in rows:
                notes_value = row["notes"]
                notes_list = []
                if notes_value:
                    try:
                        parsed = json.loads(notes_value)
                        if isinstance(parsed, list):
                            notes_list = parsed
                        elif isinstance(parsed, str):
                            notes_list = [
                                {
                                    "timestamp": None,
                                    "operator": None,
                                    "note": parsed,
                                }
                            ]
                    except json.JSONDecodeError:
                        notes_list = [
                            {
                                "timestamp": None,
                                "operator": None,
                                "note": notes_value,
                            }
                        ]

                entry = {
                    "id": row["id"],
                    "phase": row["phase"],
                    "timestamp": row["timestamp"],
                    "operator": row["operator"],
                    "notes": notes_list,
                    "measurement_data": json.loads(row["measurement_data"]),
                }
                history.append(entry)

            return history

    def get_measurement_notes(
        self,
        record_id: int,
        phase: "CommissioningPhase" | None = None,
    ) -> list[dict]:
        """Flatten measurement notes across history entries.

        Returns a list of notes with entry_id and note index for editing.
        """
        history = self.get_measurement_history(record_id, phase)
        notes = []

        for entry in history:
            notes_list = entry.get("notes") or []
            for index, note_item in enumerate(notes_list):
                notes.append(
                    {
                        "entry_id": entry["id"],
                        "note_index": index,
                        "phase": entry["phase"],
                        "measurement_timestamp": entry.get("timestamp"),
                        "timestamp": note_item.get("timestamp"),
                        "operator": note_item.get("operator"),
                        "note": note_item.get("note", ""),
                    }
                )

        def sort_key(item: dict) -> str:
            return (
                item.get("timestamp") or item.get("measurement_timestamp") or ""
            )

        return sorted(notes, key=sort_key, reverse=True)

    def append_measurement_note(
        self,
        entry_id: int,
        operator: str | None,
        note: str,
    ) -> bool:
        """Append a note to a measurement history entry.

        Args:
            entry_id: Measurement history entry ID
            operator: Note author
            note: Note text

        Returns:
            True if updated, False if entry not found
        """
        import json
        from datetime import datetime

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT notes FROM measurement_history WHERE id = ?",
                (entry_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return False

            existing = row[0]
            notes_list = []
            if existing:
                try:
                    parsed = json.loads(existing)
                    if isinstance(parsed, list):
                        notes_list = parsed
                    elif isinstance(parsed, str):
                        notes_list = [
                            {
                                "timestamp": None,
                                "operator": None,
                                "note": parsed,
                            }
                        ]
                except json.JSONDecodeError:
                    notes_list = [
                        {"timestamp": None, "operator": None, "note": existing}
                    ]

            notes_list.append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "operator": operator,
                    "note": note,
                }
            )

            cursor.execute(
                "UPDATE measurement_history SET notes = ? WHERE id = ?",
                (json.dumps(notes_list), entry_id),
            )
            return cursor.rowcount > 0

    # ==================== GENERAL NOTES METHODS ====================

    def get_general_notes(self, record_id: int) -> list[dict]:
        """Get all general notes for a commissioning record.

        Args:
            record_id: Commissioning record ID

        Returns:
            List of note dicts with timestamp, operator, note
        """
        import json

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT general_notes FROM commissioning_records WHERE id = ?",
                (record_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return []

            general_notes_str = row[0] or "[]"
            try:
                notes_list = json.loads(general_notes_str)
                if not isinstance(notes_list, list):
                    return []
                return notes_list
            except json.JSONDecodeError:
                return []

    def append_general_note(
        self,
        record_id: int,
        operator: str | None,
        note: str,
        expected_version: int | None = None,
    ) -> bool:
        """Append a general note to a commissioning record.

        Args:
            record_id: Commissioning record ID
            operator: Note author
            note: Note text
            expected_version: Optional optimistic locking version

        Returns:
            True if updated, False if record not found
        """
        import json
        from datetime import datetime

        now = datetime.now().isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT general_notes, version FROM commissioning_records WHERE id = ?",
                (record_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return False

            current_version = row["version"]
            if (
                expected_version is not None
                and current_version != expected_version
            ):
                raise RecordConflictError(
                    record_id, expected_version, current_version
                )

            existing = row[0] or "[]"
            try:
                notes_list = json.loads(existing)
                if not isinstance(notes_list, list):
                    notes_list = []
            except json.JSONDecodeError:
                notes_list = []

            notes_list.append(
                {
                    "timestamp": now,
                    "operator": operator,
                    "note": note,
                }
            )

            cursor.execute(
                """
                UPDATE commissioning_records
                SET general_notes = ?, updated_at = ?, version = version + 1
                WHERE id = ?
                """,
                (json.dumps(notes_list), now, record_id),
            )
            return cursor.rowcount > 0

    def update_general_note(
        self,
        record_id: int,
        note_index: int,
        operator: str | None,
        note: str,
        expected_version: int | None = None,
    ) -> bool:
        """Update a specific general note by index.

        Args:
            record_id: Commissioning record ID
            note_index: Index of note to update
            operator: Note author
            note: Note text
            expected_version: Optional optimistic locking version

        Returns:
            True if updated, False if record/note not found
        """
        import json
        from datetime import datetime

        now = datetime.now().isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT general_notes, version FROM commissioning_records WHERE id = ?",
                (record_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return False

            current_version = row["version"]
            if (
                expected_version is not None
                and current_version != expected_version
            ):
                raise RecordConflictError(
                    record_id, expected_version, current_version
                )

            existing = row[0] or "[]"
            try:
                notes_list = json.loads(existing)
                if not isinstance(notes_list, list):
                    notes_list = []
            except json.JSONDecodeError:
                notes_list = []

            if note_index < 0 or note_index >= len(notes_list):
                return False

            notes_list[note_index] = {
                "timestamp": now,
                "operator": operator,
                "note": note,
                "edited_at": now,
            }

            cursor.execute(
                """
                UPDATE commissioning_records
                SET general_notes = ?, updated_at = ?, version = version + 1
                WHERE id = ?
                """,
                (json.dumps(notes_list), now, record_id),
            )
            return cursor.rowcount > 0

    def update_measurement_note(
        self,
        entry_id: int,
        note_index: int,
        operator: str | None,
        note: str,
    ) -> bool:
        """Update a specific note entry by index."""
        import json
        from datetime import datetime

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT notes FROM measurement_history WHERE id = ?",
                (entry_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return False

            existing = row[0]
            notes_list = []
            if existing:
                try:
                    parsed = json.loads(existing)
                    if isinstance(parsed, list):
                        notes_list = parsed
                    elif isinstance(parsed, str):
                        notes_list = [
                            {
                                "timestamp": None,
                                "operator": None,
                                "note": parsed,
                            }
                        ]
                except json.JSONDecodeError:
                    notes_list = [
                        {"timestamp": None, "operator": None, "note": existing}
                    ]

            if note_index < 0 or note_index >= len(notes_list):
                return False

            notes_list[note_index] = {
                "timestamp": datetime.now().isoformat(),
                "operator": operator,
                "note": note,
                "edited_at": datetime.now().isoformat(),
            }

            cursor.execute(
                "UPDATE measurement_history SET notes = ? WHERE id = ?",
                (json.dumps(notes_list), entry_id),
            )
            return cursor.rowcount > 0
