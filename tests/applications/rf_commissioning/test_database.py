"""Tests for database layer."""

import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from sc_linac_physics.applications.rf_commissioning import (
    CommissioningRecord,
    CommissioningPhase,
    PhaseStatus,
    PhaseCheckpoint,
    PiezoPreRFCheck,
    ColdLandingData,
    SSACharacterization,
    CavityCharacterization,
    PiezoWithRFTest,
    HighPowerRampData,
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


class TestPhaseSpecificDataSerialization(unittest.TestCase):
    """Test serialization/deserialization of phase-specific data."""

    def setUp(self):
        """Create temporary database for each test."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.db = CommissioningDatabase(str(self.db_path))
        self.db.initialize()

    def tearDown(self):
        """Clean up temporary database."""
        self.temp_dir.cleanup()

    def test_save_and_retrieve_with_piezo_pre_rf(self):
        """Test saving and retrieving record with piezo pre-RF data."""

        record = CommissioningRecord(
            cavity_name="L1B_CM02_CAV3", cryomodule="02"
        )

        record.piezo_pre_rf = PiezoPreRFCheck(
            capacitance_a=1.2e-9,
            capacitance_b=1.3e-9,
            channel_a_passed=True,
            channel_b_passed=True,
            timestamp=datetime(2026, 2, 18, 9, 30, 0),
            notes="Both channels passed",
        )

        record_id = self.db.save_record(record)
        retrieved = self.db.get_record(record_id)

        self.assertIsNotNone(retrieved.piezo_pre_rf)
        self.assertEqual(retrieved.piezo_pre_rf.capacitance_a, 1.2e-9)
        self.assertEqual(retrieved.piezo_pre_rf.capacitance_b, 1.3e-9)
        self.assertTrue(retrieved.piezo_pre_rf.channel_a_passed)
        self.assertTrue(retrieved.piezo_pre_rf.channel_b_passed)
        self.assertEqual(
            retrieved.piezo_pre_rf.timestamp, datetime(2026, 2, 18, 9, 30, 0)
        )
        self.assertEqual(retrieved.piezo_pre_rf.notes, "Both channels passed")

    def test_save_and_retrieve_with_cold_landing(self):
        """Test saving and retrieving record with cold landing data."""

        record = CommissioningRecord(
            cavity_name="L1B_CM02_CAV3", cryomodule="02"
        )

        record.cold_landing = ColdLandingData(
            initial_detune_hz=-143766,
            initial_timestamp=datetime(2026, 2, 18, 10, 0, 0),
            steps_to_resonance=14376,
            final_detune_hz=-234,
            final_timestamp=datetime(2026, 2, 18, 10, 5, 0),
            notes="Cold landing complete",
        )

        record_id = self.db.save_record(record)
        retrieved = self.db.get_record(record_id)

        self.assertIsNotNone(retrieved.cold_landing)
        self.assertEqual(retrieved.cold_landing.initial_detune_hz, -143766)
        self.assertEqual(
            retrieved.cold_landing.initial_timestamp,
            datetime(2026, 2, 18, 10, 0, 0),
        )
        self.assertEqual(retrieved.cold_landing.steps_to_resonance, 14376)
        self.assertEqual(retrieved.cold_landing.final_detune_hz, -234)
        self.assertEqual(
            retrieved.cold_landing.final_timestamp,
            datetime(2026, 2, 18, 10, 5, 0),
        )
        self.assertEqual(retrieved.cold_landing.notes, "Cold landing complete")

    def test_save_and_retrieve_with_ssa_char(self):
        """Test saving and retrieving record with SSA characterization."""

        record = CommissioningRecord(
            cavity_name="L1B_CM02_CAV3", cryomodule="02"
        )

        record.ssa_char = SSACharacterization(
            max_drive=0.75,
            initial_drive=0.95,
            num_attempts=2,
            timestamp=datetime(2026, 2, 18, 11, 0, 0),
            notes="SSA calibrated",
        )

        record_id = self.db.save_record(record)
        retrieved = self.db.get_record(record_id)

        self.assertIsNotNone(retrieved.ssa_char)
        self.assertEqual(retrieved.ssa_char.max_drive, 0.75)
        self.assertEqual(retrieved.ssa_char.initial_drive, 0.95)
        self.assertEqual(retrieved.ssa_char.num_attempts, 2)
        self.assertEqual(
            retrieved.ssa_char.timestamp, datetime(2026, 2, 18, 11, 0, 0)
        )
        self.assertEqual(retrieved.ssa_char.notes, "SSA calibrated")

    def test_save_and_retrieve_with_cavity_char(self):
        """Test saving and retrieving record with cavity characterization."""

        record = CommissioningRecord(
            cavity_name="L1B_CM02_CAV3", cryomodule="02"
        )

        record.cavity_char = CavityCharacterization(
            loaded_q=3.2e7,
            probe_q=1.5e10,
            scale_factor=15.6,
            timestamp=datetime(2026, 2, 18, 12, 0, 0),
            notes="Characterization complete",
        )

        record_id = self.db.save_record(record)
        retrieved = self.db.get_record(record_id)

        self.assertIsNotNone(retrieved.cavity_char)
        self.assertEqual(retrieved.cavity_char.loaded_q, 3.2e7)
        self.assertEqual(retrieved.cavity_char.probe_q, 1.5e10)
        self.assertEqual(retrieved.cavity_char.scale_factor, 15.6)
        self.assertEqual(
            retrieved.cavity_char.timestamp, datetime(2026, 2, 18, 12, 0, 0)
        )
        self.assertEqual(
            retrieved.cavity_char.notes, "Characterization complete"
        )

    def test_save_and_retrieve_with_piezo_with_rf(self):
        """Test saving and retrieving record with piezo with-RF data."""

        record = CommissioningRecord(
            cavity_name="L1B_CM02_CAV3", cryomodule="02"
        )

        record.piezo_with_rf = PiezoWithRFTest(
            amplifier_gain_a=2.5,
            amplifier_gain_b=2.6,
            detune_gain=1.2,
            timestamp=datetime(2026, 2, 18, 13, 0, 0),
            notes="Piezo tested with RF",
        )

        record_id = self.db.save_record(record)
        retrieved = self.db.get_record(record_id)

        self.assertIsNotNone(retrieved.piezo_with_rf)
        self.assertEqual(retrieved.piezo_with_rf.amplifier_gain_a, 2.5)
        self.assertEqual(retrieved.piezo_with_rf.amplifier_gain_b, 2.6)
        self.assertEqual(retrieved.piezo_with_rf.detune_gain, 1.2)
        self.assertEqual(
            retrieved.piezo_with_rf.timestamp, datetime(2026, 2, 18, 13, 0, 0)
        )
        self.assertEqual(retrieved.piezo_with_rf.notes, "Piezo tested with RF")

    def test_save_and_retrieve_with_high_power(self):
        """Test saving and retrieving record with high power data."""

        record = CommissioningRecord(
            cavity_name="L1B_CM02_CAV3", cryomodule="02"
        )

        record.high_power = HighPowerRampData(
            final_amplitude=16.5,
            one_hour_complete=True,
            timestamp=datetime(2026, 2, 18, 15, 0, 0),
            notes="One hour run complete",
        )

        record_id = self.db.save_record(record)
        retrieved = self.db.get_record(record_id)

        self.assertIsNotNone(retrieved.high_power)
        self.assertEqual(retrieved.high_power.final_amplitude, 16.5)
        self.assertTrue(retrieved.high_power.one_hour_complete)
        self.assertEqual(
            retrieved.high_power.timestamp, datetime(2026, 2, 18, 15, 0, 0)
        )
        self.assertEqual(retrieved.high_power.notes, "One hour run complete")

    def test_save_and_retrieve_with_all_phase_data(self):
        """Test saving and retrieving record with all phase-specific data."""

        record = CommissioningRecord(
            cavity_name="L1B_CM02_CAV3", cryomodule="02"
        )

        # Add all phase-specific data
        record.piezo_pre_rf = PiezoPreRFCheck(
            capacitance_a=1.2e-9,
            capacitance_b=1.3e-9,
            channel_a_passed=True,
            channel_b_passed=True,
        )

        record.cold_landing = ColdLandingData(
            initial_detune_hz=-143766,
            steps_to_resonance=14376,
            final_detune_hz=-234,
        )

        record.ssa_char = SSACharacterization(
            max_drive=0.75, initial_drive=0.95, num_attempts=2
        )

        record.cavity_char = CavityCharacterization(
            loaded_q=3.2e7, scale_factor=15.6
        )

        record.piezo_with_rf = PiezoWithRFTest(
            amplifier_gain_a=2.5, amplifier_gain_b=2.6, detune_gain=1.2
        )

        record.high_power = HighPowerRampData(
            final_amplitude=16.5, one_hour_complete=True
        )

        record_id = self.db.save_record(record)
        retrieved = self.db.get_record(record_id)

        # Verify all data is present
        self.assertIsNotNone(retrieved.piezo_pre_rf)
        self.assertIsNotNone(retrieved.cold_landing)
        self.assertIsNotNone(retrieved.ssa_char)
        self.assertIsNotNone(retrieved.cavity_char)
        self.assertIsNotNone(retrieved.piezo_with_rf)
        self.assertIsNotNone(retrieved.high_power)

    def test_save_and_retrieve_with_none_phase_data(self):
        """Test that None phase data is handled correctly."""
        record = CommissioningRecord(
            cavity_name="L1B_CM02_CAV3", cryomodule="02"
        )

        # All phase-specific data is None by default
        record_id = self.db.save_record(record)
        retrieved = self.db.get_record(record_id)

        self.assertIsNone(retrieved.piezo_pre_rf)
        self.assertIsNone(retrieved.cold_landing)
        self.assertIsNone(retrieved.ssa_char)
        self.assertIsNone(retrieved.cavity_char)
        self.assertIsNone(retrieved.piezo_with_rf)
        self.assertIsNone(retrieved.high_power)

    def test_update_adds_phase_data(self):
        """Test updating record to add phase-specific data."""

        record = CommissioningRecord(
            cavity_name="L1B_CM02_CAV3", cryomodule="02"
        )

        # Save without cold landing
        record_id = self.db.save_record(record)

        # Add cold landing and update
        record.cold_landing = ColdLandingData(
            initial_detune_hz=-143766,
            steps_to_resonance=14376,
            final_detune_hz=-234,
        )
        self.db.save_record(record, record_id)

        # Retrieve and verify
        retrieved = self.db.get_record(record_id)
        self.assertIsNotNone(retrieved.cold_landing)
        self.assertEqual(retrieved.cold_landing.initial_detune_hz, -143766)


class TestPhaseTrackingSerialization(unittest.TestCase):
    """Tests for phase status and checkpoint serialization."""

    def setUp(self):
        """Set up test database."""
        self.db_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.db_file.close()
        self.db = CommissioningDatabase(self.db_file.name)
        self.db.initialize()

    def tearDown(self):
        """Clean up test database."""
        if hasattr(self, "db_file") and os.path.exists(self.db_file.name):
            os.unlink(self.db_file.name)

    def test_save_and_retrieve_phase_status(self):
        """Test saving and retrieving phase status."""
        record = CommissioningRecord(
            cavity_name="L1B_CM02_CAV3", cryomodule="02"
        )

        # Update phase status
        record.set_phase_status(
            CommissioningPhase.PRE_CHECKS, PhaseStatus.COMPLETE
        )
        record.set_phase_status(
            CommissioningPhase.COLD_LANDING, PhaseStatus.IN_PROGRESS
        )

        record_id = self.db.save_record(record)

        # Retrieve and verify
        retrieved = self.db.get_record(record_id)

        assert retrieved is not None
        assert (
            retrieved.get_phase_status(CommissioningPhase.PRE_CHECKS)
            == PhaseStatus.COMPLETE
        )
        assert (
            retrieved.get_phase_status(CommissioningPhase.COLD_LANDING)
            == PhaseStatus.IN_PROGRESS
        )

    def test_save_and_retrieve_phase_checkpoint(self):
        """Test saving and retrieving phase checkpoints."""

        record = CommissioningRecord(
            cavity_name="L1B_CM02_CAV3", cryomodule="02"
        )

        # Add checkpoint - UPDATED
        checkpoint = PhaseCheckpoint(
            phase=CommissioningPhase.PRE_CHECKS,
            timestamp=datetime(2026, 2, 18, 10, 0, 0),
            operator="Jane Smith",
            step_name="pre_checks_complete",
            success=True,
            notes="Pre-checks complete",
            measurements={"temperature": 2.04, "pressure": 1.2e-7},
        )

        record.add_checkpoint(checkpoint)

        record_id = self.db.save_record(record)

        # Retrieve and verify
        retrieved = self.db.get_record(record_id)

        assert retrieved is not None
        assert len(retrieved.phase_history) == 1

        cp = retrieved.phase_history[0]
        assert cp.phase == CommissioningPhase.PRE_CHECKS
        assert cp.operator == "Jane Smith"
        assert cp.step_name == "pre_checks_complete"
        assert cp.success is True
        assert cp.notes == "Pre-checks complete"
        assert cp.measurements["temperature"] == 2.04

    def test_save_and_retrieve_multiple_checkpoints(self):
        """Test saving and retrieving multiple phase checkpoints."""

        record = CommissioningRecord(
            cavity_name="L1B_CM02_CAV3", cryomodule="02"
        )

        # Add checkpoints for multiple phases
        checkpoint1 = PhaseCheckpoint(
            phase=CommissioningPhase.PRE_CHECKS,
            timestamp=datetime(2026, 2, 18, 10, 0, 0),
            operator="Jane Smith",
            step_name="pre_checks_complete",
            success=True,
            notes="Pre-checks complete",
        )

        checkpoint2 = PhaseCheckpoint(
            phase=CommissioningPhase.COLD_LANDING,
            timestamp=datetime(2026, 2, 18, 10, 30, 0),
            operator="Jane Smith",
            step_name="landing_step1",
            success=True,
            notes="Cold landing started",
        )

        record.add_checkpoint(checkpoint1)
        record.add_checkpoint(checkpoint2)

        record_id = self.db.save_record(record)

        # Retrieve and verify
        retrieved = self.db.get_record(record_id)

        assert retrieved is not None
        assert len(retrieved.phase_history) == 2

        # Verify both checkpoints
        assert retrieved.phase_history[0].phase == CommissioningPhase.PRE_CHECKS
        assert retrieved.phase_history[0].step_name == "pre_checks_complete"
        assert (
            retrieved.phase_history[1].phase == CommissioningPhase.COLD_LANDING
        )
        assert retrieved.phase_history[1].step_name == "landing_step1"

    def test_save_and_retrieve_checkpoint_with_error(self):
        """Test saving and retrieving checkpoint with error message."""

        record = CommissioningRecord(
            cavity_name="L1B_CM02_CAV3", cryomodule="02"
        )

        checkpoint = PhaseCheckpoint(
            phase=CommissioningPhase.HIGH_POWER_RAMP,
            timestamp=datetime(2026, 2, 18, 10, 0, 0),
            operator="Jane Smith",
            step_name="high_power_ramp",
            success=False,
            notes="Phase failed",
            error_message="Cavity quenched during ramp",
        )

        record.add_checkpoint(checkpoint)

        record_id = self.db.save_record(record)

        # Retrieve and verify
        retrieved = self.db.get_record(record_id)

        assert retrieved is not None
        assert len(retrieved.phase_history) == 1

        cp = retrieved.phase_history[0]
        assert cp.phase == CommissioningPhase.HIGH_POWER_RAMP
        assert cp.success is False
        assert cp.error_message == "Cavity quenched during ramp"


class TestCompleteWorkflowPersistence(unittest.TestCase):
    """Test persisting a complete commissioning workflow."""

    def setUp(self):
        """Create temporary database for each test."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.db = CommissioningDatabase(str(self.db_path))
        self.db.initialize()

    def tearDown(self):
        """Clean up temporary database."""
        self.temp_dir.cleanup()

    def test_complete_workflow_persistence(self):
        """Test persisting a complete commissioning workflow."""

        # Create initial record
        record = CommissioningRecord(
            cavity_name="L1B_CM02_CAV3",
            cryomodule="02",
            start_time=datetime(2026, 2, 18, 9, 0, 0),
        )

        record_id = self.db.save_record(record)

        # Phase 1: Piezo pre-RF check
        record.piezo_pre_rf = PiezoPreRFCheck(
            capacitance_a=1.2e-9,
            capacitance_b=1.3e-9,
            channel_a_passed=True,
            channel_b_passed=True,
            timestamp=datetime(2026, 2, 18, 9, 30, 0),
        )
        checkpoint1 = PhaseCheckpoint(
            phase=CommissioningPhase.PRE_CHECKS,  # ADD
            timestamp=datetime(2026, 2, 18, 9, 30, 0),
            operator="Jane Smith",
            step_name="piezo_pre_rf_check",  # ADD
            success=True,  # ADD
            notes="Pre-checks passed",
        )
        record.add_checkpoint(checkpoint1)  # UPDATED
        record.set_phase_status(
            CommissioningPhase.PRE_CHECKS, PhaseStatus.COMPLETE
        )

        # Phase 2: Cold landing
        record.cold_landing = ColdLandingData(
            initial_detune_hz=-143766,
            steps_to_resonance=14376,
            final_detune_hz=-234,
        )
        checkpoint2 = PhaseCheckpoint(
            phase=CommissioningPhase.COLD_LANDING,  # ADD
            timestamp=datetime(2026, 2, 18, 10, 0, 0),
            operator="Jane Smith",
            step_name="cold_landing_complete",  # ADD
            success=True,  # ADD
            notes="Landed at resonance",
            measurements={"final_detune_hz": -234},
        )
        record.add_checkpoint(checkpoint2)  # UPDATED
        record.set_phase_status(
            CommissioningPhase.COLD_LANDING, PhaseStatus.COMPLETE
        )

        # Phase 3: SSA characterization
        record.ssa_char = SSACharacterization(
            max_drive=0.75,
            initial_drive=0.95,
            num_attempts=2,
        )
        checkpoint3 = PhaseCheckpoint(
            phase=CommissioningPhase.SSA_CAL,  # ADD
            timestamp=datetime(2026, 2, 18, 10, 30, 0),
            operator="Jane Smith",
            step_name="ssa_calibration",  # ADD
            success=True,  # ADD
            notes="SSA calibrated",
        )
        record.add_checkpoint(checkpoint3)  # UPDATED
        record.set_phase_status(
            CommissioningPhase.SSA_CAL, PhaseStatus.COMPLETE
        )

        # Phase 4: Cavity characterization
        record.cavity_char = CavityCharacterization(
            loaded_q=3.2e7,
            scale_factor=15.6,
        )
        checkpoint4 = PhaseCheckpoint(
            phase=CommissioningPhase.CHARACTERIZATION,  # ADD
            timestamp=datetime(2026, 2, 18, 11, 0, 0),
            operator="Jane Smith",
            step_name="cavity_characterization",  # ADD
            success=True,  # ADD
            notes="Cavity characterized",
            measurements={"loaded_q": 3.2e7, "scale_factor": 15.6},
        )
        record.add_checkpoint(checkpoint4)  # UPDATED
        record.set_phase_status(
            CommissioningPhase.CHARACTERIZATION, PhaseStatus.COMPLETE
        )

        # Update current phase
        record.current_phase = CommissioningPhase.CHARACTERIZATION

        # Save updated record
        self.db.save_record(record, record_id)

        # Retrieve and verify complete workflow
        retrieved = self.db.get_record(record_id)

        assert retrieved is not None
        assert retrieved.cavity_name == "L1B_CM02_CAV3"

        # Verify all phase data
        assert retrieved.piezo_pre_rf is not None
        assert retrieved.piezo_pre_rf.channel_a_passed is True

        assert retrieved.cold_landing is not None
        assert retrieved.cold_landing.final_detune_hz == -234

        assert retrieved.ssa_char is not None
        assert retrieved.ssa_char.max_drive == 0.75

        assert retrieved.cavity_char is not None
        assert retrieved.cavity_char.loaded_q == 3.2e7

        # Verify all checkpoints - UPDATED
        assert len(retrieved.phase_history) == 4

        # Verify checkpoint phases
        checkpoint_phases = [cp.phase for cp in retrieved.phase_history]
        assert CommissioningPhase.PRE_CHECKS in checkpoint_phases
        assert CommissioningPhase.COLD_LANDING in checkpoint_phases
        assert CommissioningPhase.SSA_CAL in checkpoint_phases
        assert CommissioningPhase.CHARACTERIZATION in checkpoint_phases

        # Verify phase statuses
        assert (
            retrieved.get_phase_status(CommissioningPhase.PRE_CHECKS)
            == PhaseStatus.COMPLETE
        )
        assert (
            retrieved.get_phase_status(CommissioningPhase.COLD_LANDING)
            == PhaseStatus.COMPLETE
        )
        assert (
            retrieved.get_phase_status(CommissioningPhase.SSA_CAL)
            == PhaseStatus.COMPLETE
        )
        assert (
            retrieved.get_phase_status(CommissioningPhase.CHARACTERIZATION)
            == PhaseStatus.COMPLETE
        )

    def test_resume_interrupted_workflow(self):
        """Test resuming an interrupted workflow from database."""

        # Simulate interrupted workflow
        record = CommissioningRecord(
            cavity_name="L1B_CM02_CAV3",
            cryomodule="02",
            start_time=datetime(2026, 2, 18, 9, 0, 0),
        )

        record.piezo_pre_rf = PiezoPreRFCheck(
            capacitance_a=1.2e-9,
            capacitance_b=1.3e-9,
            channel_a_passed=True,
            channel_b_passed=True,
        )
        record.set_phase_status(
            CommissioningPhase.PRE_CHECKS, PhaseStatus.COMPLETE
        )
        record.current_phase = CommissioningPhase.COLD_LANDING

        self.db.save_record(record)

        # Simulate crash/restart - retrieve active record
        active_records = self.db.get_active_records()
        self.assertEqual(len(active_records), 1)

        resumed = active_records[0]
        self.assertEqual(resumed.cavity_name, "L1B_CM02_CAV3")
        self.assertEqual(resumed.current_phase, CommissioningPhase.COLD_LANDING)
        self.assertIsNotNone(resumed.piezo_pre_rf)

        # Continue from where we left off
        resumed_from_db = self.db.get_record_by_cavity("L1B_CM02_CAV3")
        self.assertIsNotNone(resumed_from_db)
        self.assertEqual(
            resumed_from_db.current_phase, CommissioningPhase.COLD_LANDING
        )


if __name__ == "__main__":
    unittest.main()
