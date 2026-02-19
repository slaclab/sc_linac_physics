"""SQLite database interface for RF commissioning records."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from sc_linac_physics.applications.rf_commissioning import CommissioningRecord


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
                    cavity_name TEXT NOT NULL,
                    cryomodule TEXT NOT NULL,
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
                    updated_at TEXT NOT NULL
                )
            """)

            # Create indexes for common queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_cavity_name
                ON commissioning_records(cavity_name)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_cryomodule
                ON commissioning_records(cryomodule)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_overall_status
                ON commissioning_records(overall_status)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_current_phase
                ON commissioning_records(current_phase)
            """)

    def save_record(
        self, record: "CommissioningRecord", record_id: Optional[int] = None
    ) -> int:
        """Save or update a commissioning record.

        Args:
            record: CommissioningRecord to save
            record_id: If provided, updates existing record. Otherwise creates new.

        Returns:
            Database ID of the saved record

        Example:
            >>> record = CommissioningRecord(cavity_name="L1B_CM02_CAV3", cryomodule="02")
            >>> record_id = db.save_record(record)  # Create
            >>> record.current_phase = CommissioningPhase.SSA_CAL
            >>> db.save_record(record, record_id)  # Update
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

        phase_history_json = json.dumps(
            {
                phase.value: checkpoint.to_dict()
                for phase, checkpoint in record.phase_history.items()
            }
        )

        with self._get_connection() as conn:
            cursor = conn.cursor()

            if record_id is None:
                # Insert new record
                cursor.execute(
                    """
                    INSERT INTO commissioning_records (
                        cavity_name, cryomodule, start_time, end_time,
                        current_phase, overall_status,
                        piezo_pre_rf, cold_landing, ssa_char, cavity_char,
                        piezo_with_rf, high_power,
                        phase_status, phase_history,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        record.cavity_name,
                        record.cryomodule,
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
                # Update existing record
                cursor.execute(
                    """
                    UPDATE commissioning_records SET
                        cavity_name = ?, cryomodule = ?, start_time = ?, end_time = ?,
                        current_phase = ?, overall_status = ?,
                        piezo_pre_rf = ?, cold_landing = ?, ssa_char = ?, cavity_char = ?,
                        piezo_with_rf = ?, high_power = ?,
                        phase_status = ?, phase_history = ?,
                        updated_at = ?
                    WHERE id = ?
                """,
                    (
                        record.cavity_name,
                        record.cryomodule,
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

        # Deserialize phase status
        phase_status = {}
        phase_status_data = json.loads(row["phase_status"])
        for phase_str, status_str in phase_status_data.items():
            phase_status[CommissioningPhase(phase_str)] = PhaseStatus(
                status_str
            )

        # Deserialize phase history
        phase_history = {}
        phase_history_data = json.loads(row["phase_history"])
        for phase_str, checkpoint_dict in phase_history_data.items():
            checkpoint = PhaseCheckpoint(
                timestamp=datetime.fromisoformat(checkpoint_dict["timestamp"]),
                operator=checkpoint_dict["operator"],
                notes=checkpoint_dict["notes"],
                measurements=checkpoint_dict["measurements"],
                error_message=checkpoint_dict["error_message"],
            )
            phase_history[CommissioningPhase(phase_str)] = checkpoint

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
            cavity_name=row["cavity_name"],
            cryomodule=row["cryomodule"],
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
