"""SQLite database interface for RF commissioning records."""

import sqlite3
import typing
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, List

if typing.TYPE_CHECKING:
    from sc_linac_physics.applications.rf_commissioning import (
        CommissioningPhase,
    )
from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningRecord,
)


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
        self._connection: Optional[sqlite3.Connection] = None

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
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
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
                    piezo_pre_rf TEXT,
                    cold_landing TEXT,
                    ssa_char TEXT,
                    cavity_char TEXT,
                    piezo_with_rf TEXT,
                    high_power TEXT,

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

            # Migration: Add version column if it doesn't exist
            cursor.execute("""
                SELECT COUNT(*) as count FROM pragma_table_info('commissioning_records')
                WHERE name='version'
            """)
            if cursor.fetchone()[0] == 0:
                cursor.execute("""
                    ALTER TABLE commissioning_records
                    ADD COLUMN version INTEGER NOT NULL DEFAULT 1
                """)

            # Migration: Add general_notes column if it doesn't exist
            cursor.execute("""
                SELECT COUNT(*) as count FROM pragma_table_info('commissioning_records')
                WHERE name='general_notes'
            """)
            if cursor.fetchone()[0] == 0:
                cursor.execute("""
                    ALTER TABLE commissioning_records
                    ADD COLUMN general_notes TEXT NOT NULL DEFAULT '[]'
                """)

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

            # Migration: Ensure linac, cryomodule, cavity_number columns exist and have values
            self._migrate_cavity_fields(cursor)
            self._migrate_linac_number(cursor)

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

            # Consolidate legacy duplicate records before enforcing uniqueness
            self._consolidate_duplicate_records(cursor)

            try:
                cursor.execute("""
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_cavity
                    ON commissioning_records(linac, cryomodule, cavity_number)
                """)
            except sqlite3.IntegrityError as exc:
                print(
                    "Warning: could not create unique cavity index: " f"{exc}"
                )

            # Create operators table for approved operator list
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS operators (
                    name TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL
                )
            """)

    def _migrate_cavity_fields(self, cursor: sqlite3.Cursor) -> None:
        """Migrate old records to have linac, cryomodule, cavity_number fields.

        Handles records created with older schema versions.
        """
        try:
            # Check if the columns exist
            cursor.execute("PRAGMA table_info(commissioning_records)")
            columns = {row[1] for row in cursor.fetchall()}

            # Add missing columns if needed
            if "linac" not in columns:
                cursor.execute("""
                    ALTER TABLE commissioning_records
                    ADD COLUMN linac TEXT
                """)

            if "cryomodule" not in columns:
                cursor.execute("""
                    ALTER TABLE commissioning_records
                    ADD COLUMN cryomodule TEXT
                """)

            if "cavity_number" not in columns:
                cursor.execute("""
                    ALTER TABLE commissioning_records
                    ADD COLUMN cavity_number TEXT
                """)
        except Exception as e:
            # Column might already exist or other migration issue
            print(f"Note: Could not complete cavity fields migration: {e}")

    def _migrate_linac_number(self, cursor: sqlite3.Cursor) -> None:
        """Add and populate the linac_number column when missing."""
        try:
            cursor.execute("PRAGMA table_info(commissioning_records)")
            columns = {row[1] for row in cursor.fetchall()}

            if "linac_number" not in columns:
                cursor.execute("""
                    ALTER TABLE commissioning_records
                    ADD COLUMN linac_number TEXT
                """)

            cursor.execute(
                "SELECT id, linac, linac_number FROM commissioning_records"
            )
            rows = cursor.fetchall()

            for row in rows:
                if row["linac_number"]:
                    continue

                linac_number = self._extract_linac_number(row["linac"])
                if linac_number is None:
                    continue

                cursor.execute(
                    "UPDATE commissioning_records SET linac_number = ? WHERE id = ?",
                    (linac_number, row["id"]),
                )
        except Exception as e:
            print(f"Note: Could not complete linac number migration: {e}")

    def _extract_linac_number(self, linac: Optional[str]) -> Optional[str]:
        """Extract numeric linac identifier from a linac string."""
        import re

        if not linac:
            return None

        digits = re.findall(r"\d+", linac)
        if not digits:
            return None

        return "".join(digits)

    def _parse_notes(self, notes_json: Optional[str]) -> list[dict]:
        """Parse notes JSON string into list of note dictionaries."""
        import json

        if not notes_json:
            return []
        try:
            parsed = json.loads(notes_json)
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []

    def _extract_timestamp(self, phase: str, data: dict) -> Optional[str]:
        """Extract timestamp from phase data payload."""
        if "timestamp" in data:
            return data.get("timestamp")
        if phase == "cold_landing":
            return data.get("final_timestamp") or data.get("initial_timestamp")
        return None

    def _insert_history_from_payload(
        self,
        cursor: sqlite3.Cursor,
        record_id: int,
        phase: str,
        payload_json: str,
        fallback_ts: Optional[str],
    ) -> None:
        """Insert measurement history entry from phase data payload."""
        import json
        from datetime import datetime

        try:
            data = json.loads(payload_json)
        except json.JSONDecodeError:
            return

        timestamp = self._extract_timestamp(phase, data) or fallback_ts
        if not timestamp:
            timestamp = datetime.now().isoformat()

        notes_value = data.get("notes") or None
        cursor.execute(
            """
            INSERT INTO measurement_history (
                record_id, phase, timestamp, operator,
                measurement_data, notes, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record_id,
                phase,
                timestamp,
                None,
                payload_json,
                notes_value,
                datetime.now().isoformat(),
            ),
        )

    def _migrate_phase_data_to_history(
        self,
        cursor: sqlite3.Cursor,
        primary_id: int,
        row: dict,
        fallback_ts: str,
    ) -> None:
        """Migrate all phase data from a duplicate record to measurement history."""
        phase_columns = [
            "piezo_pre_rf",
            "cold_landing",
            "ssa_char",
            "cavity_char",
            "piezo_with_rf",
            "high_power",
        ]

        for phase_col in phase_columns:
            if row[phase_col]:
                self._insert_history_from_payload(
                    cursor,
                    primary_id,
                    phase_col,
                    row[phase_col],
                    fallback_ts,
                )

    def _consolidate_duplicate_group(
        self,
        cursor: sqlite3.Cursor,
        linac: str,
        cryomodule: str,
        cavity_number: str,
    ) -> None:
        """Consolidate a group of duplicate records for a single cavity."""
        import json
        from datetime import datetime

        cursor.execute(
            """
            SELECT id, updated_at, start_time, general_notes,
                   piezo_pre_rf, cold_landing, ssa_char, cavity_char,
                   piezo_with_rf, high_power
            FROM commissioning_records
            WHERE linac = ? AND cryomodule = ? AND cavity_number = ?
            ORDER BY COALESCE(updated_at, start_time) DESC, id DESC
            """,
            (linac, cryomodule, cavity_number),
        )
        rows = cursor.fetchall()
        if not rows:
            return

        primary = rows[0]
        primary_id = primary["id"]

        merged_notes = self._parse_notes(primary["general_notes"])

        for row in rows[1:]:
            old_id = row["id"]
            merged_notes.extend(self._parse_notes(row["general_notes"]))

            fallback_ts = row["updated_at"] or row["start_time"]

            # Migrate all phase data to measurement history
            self._migrate_phase_data_to_history(
                cursor, primary_id, row, fallback_ts
            )

            # Reassign existing measurement history
            cursor.execute(
                "UPDATE measurement_history SET record_id = ? WHERE record_id = ?",
                (primary_id, old_id),
            )

            # Delete duplicate record
            cursor.execute(
                "DELETE FROM commissioning_records WHERE id = ?",
                (old_id,),
            )

        # Update primary record with merged notes
        if len(rows) > 1:
            cursor.execute(
                """
                UPDATE commissioning_records
                SET general_notes = ?, updated_at = ?, version = version + 1
                WHERE id = ?
                """,
                (
                    json.dumps(merged_notes),
                    datetime.now().isoformat(),
                    primary_id,
                ),
            )

    def _consolidate_duplicate_records(self, cursor: sqlite3.Cursor) -> None:
        """Merge duplicate cavity records into a single canonical record.

        This preserves measurement history and notes while keeping one record
        per cavity.
        """
        cursor.execute("""
            SELECT linac, cryomodule, cavity_number, COUNT(*) as count
            FROM commissioning_records
            GROUP BY linac, cryomodule, cavity_number
            HAVING count > 1
            """)
        groups = cursor.fetchall()

        if not groups:
            return

        for group in groups:
            linac = group["linac"]
            cryomodule = group["cryomodule"]
            cavity_number = group["cavity_number"]

            if not linac or not cryomodule or not cavity_number:
                continue

            self._consolidate_duplicate_group(
                cursor, linac, cryomodule, cavity_number
            )

    def save_record(
        self,
        record: "CommissioningRecord",
        record_id: Optional[int] = None,
        expected_version: Optional[int] = None,
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
        import json
        from datetime import datetime

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

        with self._get_connection() as conn:
            cursor = conn.cursor()

            linac_number = self._extract_linac_number(record.linac)

            if record_id is None:
                # Insert new record
                cursor.execute(
                    """
                    INSERT INTO commissioning_records (
                        linac, linac_number, cryomodule, cavity_number, start_time, end_time,
                        current_phase, overall_status,
                        piezo_pre_rf, cold_landing, ssa_char, cavity_char,
                        piezo_with_rf, high_power,
                        phase_status, phase_history,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                        (
                            json.dumps(record.piezo_pre_rf.to_dict())
                            if record.piezo_pre_rf
                            else None
                        ),
                        (
                            json.dumps(record.cold_landing.to_dict())
                            if record.cold_landing
                            else None
                        ),
                        (
                            json.dumps(record.ssa_char.to_dict())
                            if record.ssa_char
                            else None
                        ),
                        (
                            json.dumps(record.cavity_char.to_dict())
                            if record.cavity_char
                            else None
                        ),
                        (
                            json.dumps(record.piezo_with_rf.to_dict())
                            if record.piezo_with_rf
                            else None
                        ),
                        (
                            json.dumps(record.high_power.to_dict())
                            if record.high_power
                            else None
                        ),
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

                cursor.execute(
                    """
                    UPDATE commissioning_records SET
                        linac = ?, linac_number = ?, cryomodule = ?, cavity_number = ?, start_time = ?, end_time = ?,
                        current_phase = ?, overall_status = ?,
                        piezo_pre_rf = ?, cold_landing = ?, ssa_char = ?, cavity_char = ?,
                        piezo_with_rf = ?, high_power = ?,
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
                        (
                            json.dumps(record.piezo_pre_rf.to_dict())
                            if record.piezo_pre_rf
                            else None
                        ),
                        (
                            json.dumps(record.cold_landing.to_dict())
                            if record.cold_landing
                            else None
                        ),
                        (
                            json.dumps(record.ssa_char.to_dict())
                            if record.ssa_char
                            else None
                        ),
                        (
                            json.dumps(record.cavity_char.to_dict())
                            if record.cavity_char
                            else None
                        ),
                        (
                            json.dumps(record.piezo_with_rf.to_dict())
                            if record.piezo_with_rf
                            else None
                        ),
                        (
                            json.dumps(record.high_power.to_dict())
                            if record.high_power
                            else None
                        ),
                        phase_status_json,
                        phase_history_json,
                        now,
                        record_id,
                    ),
                )
                return record_id

    def get_record(self, record_id: int) -> Optional["CommissioningRecord"]:
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
    ) -> Optional[tuple["CommissioningRecord", int]]:
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
    ) -> Optional[tuple["CommissioningRecord", int]]:
        """Alias for get_record_with_version."""
        return self.get_record_with_version(record_id)

    def _row_to_record(self, row: sqlite3.Row) -> "CommissioningRecord":
        """Convert database row to CommissioningRecord.

        Handles deserialization of JSON fields and enum conversion.
        """
        import json
        from datetime import datetime

        from .data_models import (
            CavityCharacterization,
            ColdLandingData,
            CommissioningPhase,
            CommissioningRecord,
            HighPowerRampData,
            PhaseCheckpoint,
            PhaseStatus,
            PiezoPreRFCheck,
            PiezoWithRFTest,
            SSACharacterization,
        )

        # Deserialize phase_status
        phase_status_dict = json.loads(row["phase_status"])
        phase_status = {
            CommissioningPhase(phase): PhaseStatus(status)
            for phase, status in phase_status_dict.items()
        }

        # UPDATED: Deserialize phase_history as list
        phase_history_list = json.loads(row["phase_history"])
        phase_history = []
        for (
            cp_dict
        ) in phase_history_list:  # CHANGED: iterate over list instead of dict
            checkpoint = PhaseCheckpoint(
                phase=CommissioningPhase(cp_dict["phase"]),  # ADD this line
                timestamp=datetime.fromisoformat(cp_dict["timestamp"]),
                operator=cp_dict["operator"],
                step_name=cp_dict["step_name"],  # ADD this line
                success=cp_dict["success"],  # ADD this line
                notes=cp_dict.get("notes", ""),
                measurements=cp_dict.get("measurements", {}),
                error_message=cp_dict.get("error_message"),
            )
            phase_history.append(
                checkpoint
            )  # CHANGED: append to list instead of dict

        # Deserialize phase-specific data
        piezo_pre_rf = None
        if row["piezo_pre_rf"]:
            data = json.loads(row["piezo_pre_rf"])
            piezo_pre_rf = PiezoPreRFCheck(
                capacitance_a=data["capacitance_a"],
                capacitance_b=data["capacitance_b"],
                channel_a_passed=data["channel_a_passed"],
                channel_b_passed=data["channel_b_passed"],
                timestamp=datetime.fromisoformat(data["timestamp"]),
                notes=data["notes"],
            )

        cold_landing = None
        if row["cold_landing"]:
            data = json.loads(row["cold_landing"])
            cold_landing = ColdLandingData(
                initial_detune_hz=data["initial_detune_hz"],
                initial_timestamp=(
                    datetime.fromisoformat(data["initial_timestamp"])
                    if data["initial_timestamp"]
                    else None
                ),
                steps_to_resonance=data["steps_to_resonance"],
                final_detune_hz=data["final_detune_hz"],
                final_timestamp=(
                    datetime.fromisoformat(data["final_timestamp"])
                    if data["final_timestamp"]
                    else None
                ),
                notes=data["notes"],
            )

        ssa_char = None
        if row["ssa_char"]:
            data = json.loads(row["ssa_char"])
            ssa_char = SSACharacterization(
                max_drive=data["max_drive"],
                initial_drive=data["initial_drive"],
                num_attempts=data["num_attempts"],
                timestamp=datetime.fromisoformat(data["timestamp"]),
                notes=data["notes"],
            )

        cavity_char = None
        if row["cavity_char"]:
            data = json.loads(row["cavity_char"])
            cavity_char = CavityCharacterization(
                loaded_q=data["loaded_q"],
                probe_q=data["probe_q"],
                scale_factor=data["scale_factor"],
                timestamp=datetime.fromisoformat(data["timestamp"]),
                notes=data["notes"],
            )

        piezo_with_rf = None
        if row["piezo_with_rf"]:
            data = json.loads(row["piezo_with_rf"])
            piezo_with_rf = PiezoWithRFTest(
                amplifier_gain_a=data["amplifier_gain_a"],
                amplifier_gain_b=data["amplifier_gain_b"],
                detune_gain=data["detune_gain"],
                timestamp=datetime.fromisoformat(data["timestamp"]),
                notes=data["notes"],
            )

        high_power = None
        if row["high_power"]:
            data = json.loads(row["high_power"])
            high_power = HighPowerRampData(
                final_amplitude=data["final_amplitude"],
                one_hour_complete=data["one_hour_complete"],
                timestamp=datetime.fromisoformat(data["timestamp"]),
                notes=data["notes"],
            )

        # Create record
        record = CommissioningRecord(
            linac=row["linac"],
            cryomodule=row["cryomodule"],
            cavity_number=row["cavity_number"],
            start_time=datetime.fromisoformat(row["start_time"]),
            current_phase=CommissioningPhase(row["current_phase"]),
            piezo_pre_rf=piezo_pre_rf,
            cold_landing=cold_landing,
            ssa_char=ssa_char,
            cavity_char=cavity_char,
            piezo_with_rf=piezo_with_rf,
            high_power=high_power,
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

    def get_record_by_cavity(
        self,
        linac: str,
        cryomodule: str,
        cavity_number: str,
        active_only: bool = True,
    ) -> Optional["CommissioningRecord"]:
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

    def load_record(self, record_id: int) -> Optional["CommissioningRecord"]:
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
    ) -> Optional[int]:
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
        self, where_clause: str = "", params: Optional[list] = None
    ) -> List[dict]:
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

        records: List[dict] = []
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

    def get_all_records(self) -> List[dict]:
        """
        Get all commissioning records as dictionaries.

        Returns:
            List of record dictionaries with basic info for browsing
        """
        try:
            return self._get_record_summaries()

        except Exception as e:
            print(f"Error getting all records: {e}")
            import traceback

            traceback.print_exc()
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
        operator: Optional[str] = None,
        notes: Optional[str] = None,
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

    def get_operators(self) -> List[str]:
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
        phase: Optional["CommissioningPhase"] = None,
    ) -> List[dict]:
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
        phase: Optional["CommissioningPhase"] = None,
    ) -> List[dict]:
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
        operator: Optional[str],
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

    def get_general_notes(self, record_id: int) -> List[dict]:
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
        operator: Optional[str],
        note: str,
        expected_version: Optional[int] = None,
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
        operator: Optional[str],
        note: str,
        expected_version: Optional[int] = None,
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
        operator: Optional[str],
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
