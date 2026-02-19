"""SQLite database interface for RF commissioning records."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional


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
