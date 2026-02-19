"""Tests for database layer."""

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from sc_linac_physics.applications.rf_commissioning import (
    CommissioningRecord,
    CommissioningPhase,
)
from sc_linac_physics.applications.rf_commissioning.database import (
    CommissioningDatabase,
)


class TestDatabaseInitialization(unittest.TestCase):
    """Test database initialization and schema creation."""

    def setUp(self):
        """Create temporary database for each test."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.db = CommissioningDatabase(str(self.db_path))

    def tearDown(self):
        """Clean up temporary database."""
        self.temp_dir.cleanup()

    def test_initialize_creates_database_file(self):
        """Test that initialize creates database file."""
        self.assertFalse(self.db_path.exists())

        self.db.initialize()

        self.assertTrue(self.db_path.exists())

    def test_initialize_creates_tables(self):
        """Test that initialize creates required tables."""
        self.db.initialize()

        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='commissioning_records'
            """)
            result = cursor.fetchone()

        self.assertIsNotNone(result)
        self.assertEqual(result[0], "commissioning_records")

    def test_initialize_creates_indexes(self):
        """Test that initialize creates required indexes."""
        self.db.initialize()

        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='index'
            """)
            indexes = [row[0] for row in cursor.fetchall()]

        self.assertIn("idx_cavity_name", indexes)
        self.assertIn("idx_cryomodule", indexes)
        self.assertIn("idx_overall_status", indexes)
        self.assertIn("idx_current_phase", indexes)

    def test_initialize_idempotent(self):
        """Test that initialize can be called multiple times safely."""
        self.db.initialize()
        self.db.initialize()  # Should not raise error

        # Verify table still exists
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='commissioning_records'
            """)
            result = cursor.fetchone()

        self.assertIsNotNone(result)


class TestSaveAndRetrieve(unittest.TestCase):
    """Test saving and retrieving records."""

    def setUp(self):
        """Create temporary database for each test."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.db = CommissioningDatabase(str(self.db_path))
        self.db.initialize()

    def tearDown(self):
        """Clean up temporary database."""
        self.temp_dir.cleanup()

    def test_save_new_record_returns_id(self):
        """Test saving a new record returns a valid ID."""
        record = CommissioningRecord(
            cavity_name="L1B_CM02_CAV3", cryomodule="02"
        )

        record_id = self.db.save_record(record)

        self.assertIsNotNone(record_id)
        self.assertIsInstance(record_id, int)
        self.assertGreater(record_id, 0)

    def test_save_and_retrieve_basic_record(self):
        """Test saving and retrieving a basic record."""
        start_time = datetime(2026, 2, 18, 10, 0, 0)

        record = CommissioningRecord(
            cavity_name="L1B_CM02_CAV3", cryomodule="02", start_time=start_time
        )

        record_id = self.db.save_record(record)
        retrieved = self.db.get_record(record_id)

        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.cavity_name, "L1B_CM02_CAV3")
        self.assertEqual(retrieved.cryomodule, "02")
        self.assertEqual(retrieved.start_time, start_time)
        self.assertEqual(retrieved.current_phase, CommissioningPhase.PRE_CHECKS)
        self.assertEqual(retrieved.overall_status, "in_progress")

    def test_get_nonexistent_record(self):
        """Test retrieving a record that doesn't exist."""
        result = self.db.get_record(99999)

        self.assertIsNone(result)

    def test_update_existing_record(self):
        """Test updating an existing record."""
        record = CommissioningRecord(
            cavity_name="L1B_CM02_CAV3", cryomodule="02"
        )

        # Save initial record
        record_id = self.db.save_record(record)

        # Update record
        record.current_phase = CommissioningPhase.COLD_LANDING
        record.overall_status = "in_progress"

        # Save update
        updated_id = self.db.save_record(record, record_id)

        # Should return same ID
        self.assertEqual(updated_id, record_id)

        # Retrieve and verify
        retrieved = self.db.get_record(record_id)
        self.assertEqual(
            retrieved.current_phase, CommissioningPhase.COLD_LANDING
        )

    def test_save_multiple_records(self):
        """Test saving multiple records."""
        record1 = CommissioningRecord(
            cavity_name="L1B_CM02_CAV1", cryomodule="02"
        )
        record2 = CommissioningRecord(
            cavity_name="L1B_CM02_CAV2", cryomodule="02"
        )

        id1 = self.db.save_record(record1)
        id2 = self.db.save_record(record2)

        # IDs should be different
        self.assertNotEqual(id1, id2)

        # Both should be retrievable
        self.assertIsNotNone(self.db.get_record(id1))
        self.assertIsNotNone(self.db.get_record(id2))


class TestQueryMethods(unittest.TestCase):
    """Test query methods."""

    def setUp(self):
        """Create temporary database for each test."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.db = CommissioningDatabase(str(self.db_path))
        self.db.initialize()

    def tearDown(self):
        """Clean up temporary database."""
        self.temp_dir.cleanup()

    def test_get_record_by_cavity(self):
        """Test retrieving record by cavity name."""
        record = CommissioningRecord(
            cavity_name="L1B_CM02_CAV3", cryomodule="02"
        )

        self.db.save_record(record)

        retrieved = self.db.get_record_by_cavity("L1B_CM02_CAV3")

        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.cavity_name, "L1B_CM02_CAV3")

    def test_get_record_by_cavity_not_found(self):
        """Test querying for nonexistent cavity."""
        retrieved = self.db.get_record_by_cavity("L1B_CM99_CAV99")

        self.assertIsNone(retrieved)

    def test_get_record_by_cavity_active_only(self):
        """Test retrieving only active records by cavity."""
        record = CommissioningRecord(
            cavity_name="L1B_CM02_CAV3",
            cryomodule="02",
            overall_status="complete",
        )

        self.db.save_record(record)

        # Should not find completed record when active_only=True
        retrieved = self.db.get_record_by_cavity(
            "L1B_CM02_CAV3", active_only=True
        )
        self.assertIsNone(retrieved)

        # Should find when active_only=False
        retrieved = self.db.get_record_by_cavity(
            "L1B_CM02_CAV3", active_only=False
        )
        self.assertIsNotNone(retrieved)

    def test_get_record_by_cavity_most_recent(self):
        """Test that get_record_by_cavity returns most recent record."""
        # Create two records for same cavity
        record1 = CommissioningRecord(
            cavity_name="L1B_CM02_CAV3",
            cryomodule="02",
            start_time=datetime(2026, 2, 18, 10, 0, 0),
        )
        record2 = CommissioningRecord(
            cavity_name="L1B_CM02_CAV3",
            cryomodule="02",
            start_time=datetime(2026, 2, 19, 10, 0, 0),  # Next day
        )

        self.db.save_record(record1)
        self.db.save_record(record2)

        retrieved = self.db.get_record_by_cavity(
            "L1B_CM02_CAV3", active_only=False
        )

        # Should get the more recent one
        self.assertEqual(retrieved.start_time, datetime(2026, 2, 19, 10, 0, 0))

    def test_get_records_by_cryomodule(self):
        """Test retrieving all records for a cryomodule."""
        record1 = CommissioningRecord(
            cavity_name="L1B_CM02_CAV1", cryomodule="02"
        )
        record2 = CommissioningRecord(
            cavity_name="L1B_CM02_CAV2", cryomodule="02"
        )
        record3 = CommissioningRecord(
            cavity_name="L1B_CM03_CAV1", cryomodule="03"
        )

        self.db.save_record(record1)
        self.db.save_record(record2)
        self.db.save_record(record3)

        cm02_records = self.db.get_records_by_cryomodule("02")

        self.assertEqual(len(cm02_records), 2)
        cavity_names = {r.cavity_name for r in cm02_records}
        self.assertEqual(cavity_names, {"L1B_CM02_CAV1", "L1B_CM02_CAV2"})

    def test_get_records_by_cryomodule_active_only(self):
        """Test retrieving only active records for a cryomodule."""
        record1 = CommissioningRecord(
            cavity_name="L1B_CM02_CAV1",
            cryomodule="02",
            overall_status="in_progress",
        )
        record2 = CommissioningRecord(
            cavity_name="L1B_CM02_CAV2",
            cryomodule="02",
            overall_status="complete",
        )

        self.db.save_record(record1)
        self.db.save_record(record2)

        active_records = self.db.get_records_by_cryomodule(
            "02", active_only=True
        )

        self.assertEqual(len(active_records), 1)
        self.assertEqual(active_records[0].cavity_name, "L1B_CM02_CAV1")

    def test_get_records_by_cryomodule_empty(self):
        """Test querying for cryomodule with no records."""
        records = self.db.get_records_by_cryomodule("99")

        self.assertEqual(len(records), 0)

    def test_get_records_by_cryomodule_sorted(self):
        """Test that records are sorted by start time (newest first)."""
        record1 = CommissioningRecord(
            cavity_name="L1B_CM02_CAV1",
            cryomodule="02",
            start_time=datetime(2026, 2, 18, 10, 0, 0),
        )
        record2 = CommissioningRecord(
            cavity_name="L1B_CM02_CAV2",
            cryomodule="02",
            start_time=datetime(2026, 2, 19, 10, 0, 0),
        )

        self.db.save_record(record1)
        self.db.save_record(record2)

        records = self.db.get_records_by_cryomodule("02")

        # Should be sorted newest first
        self.assertEqual(records[0].start_time, datetime(2026, 2, 19, 10, 0, 0))
        self.assertEqual(records[1].start_time, datetime(2026, 2, 18, 10, 0, 0))

    def test_get_active_records(self):
        """Test retrieving all active records."""
        record1 = CommissioningRecord(
            cavity_name="L1B_CM02_CAV1",
            cryomodule="02",
            overall_status="in_progress",
        )
        record2 = CommissioningRecord(
            cavity_name="L1B_CM02_CAV2",
            cryomodule="02",
            overall_status="complete",
        )
        record3 = CommissioningRecord(
            cavity_name="L1B_CM03_CAV1",
            cryomodule="03",
            overall_status="in_progress",
        )

        self.db.save_record(record1)
        self.db.save_record(record2)
        self.db.save_record(record3)

        active = self.db.get_active_records()

        self.assertEqual(len(active), 2)
        cavity_names = {r.cavity_name for r in active}
        self.assertEqual(cavity_names, {"L1B_CM02_CAV1", "L1B_CM03_CAV1"})

    def test_get_active_records_empty(self):
        """Test get_active_records when no active records exist."""
        record = CommissioningRecord(
            cavity_name="L1B_CM02_CAV1",
            cryomodule="02",
            overall_status="complete",
        )

        self.db.save_record(record)

        active = self.db.get_active_records()

        self.assertEqual(len(active), 0)


class TestDeleteAndStats(unittest.TestCase):
    """Test delete and statistics methods."""

    def setUp(self):
        """Create temporary database for each test."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.db = CommissioningDatabase(str(self.db_path))
        self.db.initialize()

    def tearDown(self):
        """Clean up temporary database."""
        self.temp_dir.cleanup()

    def test_delete_record(self):
        """Test deleting a record."""
        record = CommissioningRecord(
            cavity_name="L1B_CM02_CAV3", cryomodule="02"
        )

        record_id = self.db.save_record(record)

        # Verify it exists
        self.assertIsNotNone(self.db.get_record(record_id))

        # Delete it
        deleted = self.db.delete_record(record_id)
        self.assertTrue(deleted)

        # Verify it's gone
        self.assertIsNone(self.db.get_record(record_id))

    def test_delete_nonexistent_record(self):
        """Test deleting a record that doesn't exist."""
        deleted = self.db.delete_record(99999)

        self.assertFalse(deleted)

    def test_get_database_stats_empty(self):
        """Test database stats with no records."""
        stats = self.db.get_database_stats()

        self.assertEqual(stats["total_records"], 0)
        self.assertEqual(stats["by_status"], {})
        self.assertEqual(stats["by_phase"], {})
        self.assertEqual(stats["by_cryomodule"], {})

    def test_get_database_stats_with_records(self):
        """Test database stats with multiple records."""
        record1 = CommissioningRecord(
            cavity_name="L1B_CM02_CAV1",
            cryomodule="02",
            overall_status="in_progress",
            current_phase=CommissioningPhase.PRE_CHECKS,
        )
        record2 = CommissioningRecord(
            cavity_name="L1B_CM02_CAV2",
            cryomodule="02",
            overall_status="complete",
            current_phase=CommissioningPhase.COMPLETE,
        )
        record3 = CommissioningRecord(
            cavity_name="L1B_CM03_CAV1",
            cryomodule="03",
            overall_status="in_progress",
            current_phase=CommissioningPhase.COLD_LANDING,
        )

        self.db.save_record(record1)
        self.db.save_record(record2)
        self.db.save_record(record3)

        stats = self.db.get_database_stats()

        self.assertEqual(stats["total_records"], 3)
        self.assertEqual(stats["by_status"]["in_progress"], 2)
        self.assertEqual(stats["by_status"]["complete"], 1)
        self.assertEqual(stats["by_phase"]["pre_checks"], 1)
        self.assertEqual(stats["by_phase"]["cold_landing"], 1)
        self.assertEqual(stats["by_phase"]["complete"], 1)
        self.assertEqual(stats["by_cryomodule"]["02"], 2)
        self.assertEqual(stats["by_cryomodule"]["03"], 1)


class TestTransactionHandling(unittest.TestCase):
    """Test transaction and error handling."""

    def setUp(self):
        """Create temporary database for each test."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.db = CommissioningDatabase(str(self.db_path))
        self.db.initialize()

    def tearDown(self):
        """Clean up temporary database."""
        self.temp_dir.cleanup()

    def test_context_manager_commits_on_success(self):
        """Test that context manager commits changes on success."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO commissioning_records (
                    cavity_name, cryomodule, start_time, current_phase,
                    overall_status, phase_status, phase_history,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    "L1B_CM02_CAV3",
                    "02",
                    datetime.now().isoformat(),
                    "pre_checks",
                    "in_progress",
                    "{}",
                    "{}",
                    datetime.now().isoformat(),
                    datetime.now().isoformat(),
                ),
            )

        # Verify record was committed
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM commissioning_records")
            count = cursor.fetchone()[0]
            self.assertEqual(count, 1)

    def test_context_manager_rolls_back_on_error(self):
        """Test that context manager rolls back changes on error."""
        try:
            with self.db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO commissioning_records (
                        cavity_name, cryomodule, start_time, current_phase,
                        overall_status, phase_status, phase_history,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        "L1B_CM02_CAV3",
                        "02",
                        datetime.now().isoformat(),
                        "pre_checks",
                        "in_progress",
                        "{}",
                        "{}",
                        datetime.now().isoformat(),
                        datetime.now().isoformat(),
                    ),
                )
                # Force an error
                raise ValueError("Test error")
        except ValueError:
            pass

        # Verify nothing was committed
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM commissioning_records")
            count = cursor.fetchone()[0]
            self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
