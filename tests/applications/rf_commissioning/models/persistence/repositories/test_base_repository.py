"""Tests for BaseRepository.update_versioned_row."""

from __future__ import annotations

import pytest

from sc_linac_physics.applications.rf_commissioning.models.cryomodule_models import (
    CryomoduleCheckoutRecord,
)
from sc_linac_physics.applications.rf_commissioning.models.data_models import (
    CommissioningRecord,
)
from sc_linac_physics.applications.rf_commissioning.models.persistence.database import (
    CommissioningDatabase,
    RecordConflictError,
)
from sc_linac_physics.applications.rf_commissioning.models.persistence.repositories.base import (
    BaseRepository,
)


@pytest.fixture
def db_and_id(tmp_path):
    db = CommissioningDatabase(str(tmp_path / "commissioning.db"))
    db.initialize()
    record = CommissioningRecord(linac=1, cryomodule="02", cavity_number=1)
    return db, db.save_record(record)


def _update(db, row_id, expected_version):
    with db.connection() as conn:
        return BaseRepository(db).update_versioned_row(
            cursor=conn.cursor(),
            table_name="commissioning_records",
            row_id=row_id,
            set_clause="cryomodule = ?",
            params=("03",),
            expected_version=expected_version,
            missing_message=f"Record {row_id} not found",
        )


def _version(db, row_id):
    return db.get_record_with_version(row_id)[1]


def test_matching_version_updates_and_bumps(db_and_id):
    db, row_id = db_and_id
    start = _version(db, row_id)

    assert _update(db, row_id, start) is True

    record, version = db.get_record_with_version(row_id)
    assert record.cryomodule == "03"
    assert version == start + 1


def test_stale_version_raises_conflict_and_changes_nothing(db_and_id):
    db, row_id = db_and_id
    start = _version(db, row_id)

    with pytest.raises(RecordConflictError) as err:
        _update(db, row_id, start - 1)

    assert err.value.actual_version == start
    assert db.get_record(row_id).cryomodule == "02"


def test_missing_row_with_version_raises_value_error(db_and_id):
    db, _ = db_and_id
    with pytest.raises(ValueError, match="Record 999 not found"):
        _update(db, 999, 1)


def test_without_version_updates_any_version(db_and_id):
    db, row_id = db_and_id
    start = _version(db, row_id)

    assert _update(db, row_id, None) is True
    assert _version(db, row_id) == start + 1


def test_missing_row_without_version_returns_false(db_and_id):
    db, _ = db_and_id
    assert _update(db, 999, None) is False


# save_record and save_cryomodule_record go through update_versioned_row and
# keep their own errors for a missing row.


@pytest.mark.parametrize("expected_version", [None, 1])
def test_save_record_on_a_missing_row_raises(db_and_id, expected_version):
    db, _ = db_and_id
    record = CommissioningRecord(linac=1, cryomodule="02", cavity_number=1)
    with pytest.raises(ValueError, match="Record 999 not found"):
        db.save_record(record, record_id=999, expected_version=expected_version)


def test_save_cryomodule_record_conflict_and_missing_row(tmp_path):
    db = CommissioningDatabase(str(tmp_path / "commissioning.db"))
    db.initialize()
    record = CryomoduleCheckoutRecord(linac="L1B", cryomodule="02")
    row_id = db.save_cryomodule_record(record)
    _, version = db.get_cryomodule_record_with_version("L1B", "02")

    record.notes = "first"
    db.save_cryomodule_record(record, row_id, expected_version=version)
    record.notes = "stale"
    with pytest.raises(RecordConflictError):
        db.save_cryomodule_record(record, row_id, expected_version=version)
    assert db.get_cryomodule_record("L1B", "02").notes == "first"

    for expected_version in (None, version):
        with pytest.raises(ValueError, match="CM record 999 not found"):
            db.save_cryomodule_record(
                record, record_id=999, expected_version=expected_version
            )
