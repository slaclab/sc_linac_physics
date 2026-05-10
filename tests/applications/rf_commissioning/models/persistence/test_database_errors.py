"""Tests for persistence-layer exceptions."""

from sc_linac_physics.applications.rf_commissioning.models.persistence.database_errors import (
    RecordConflictError,
    RecordDeletionDisabledError,
)


def test_record_conflict_error_exposes_context_in_attributes_and_message():
    exc = RecordConflictError(record_id=7, expected_version=2, actual_version=5)

    assert exc.record_id == 7
    assert exc.expected_version == 2
    assert exc.actual_version == 5
    assert (
        str(exc)
        == "Record 7 was modified by another user. Expected version 2, found 5."
    )


def test_record_deletion_disabled_error_exposes_context_in_message():
    exc = RecordDeletionDisabledError(record_id=42)

    assert exc.record_id == 42
    assert (
        str(exc) == "Deletion is disabled for commissioning record 42. "
        "Archive or mark the workflow state instead."
    )
